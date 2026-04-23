import asyncio
import logging
from datetime import datetime
from backend.core.config import config_manager
from backend.core.sessions import any_active, Session
from backend.core.state import engine_state
from backend.mt5_client.client import mt5_client
from backend.mt5_client.symbol_resolver import symbol_resolver
from backend.strategy.htf_bias import run_htf_bias
from backend.strategy.mtf_zones import run_mtf_zones
from backend.strategy.ltf_trigger import run_ltf_trigger
from backend.strategy.scoring import calculate_score
from backend.engine.signal_engine import emit_signal
from backend.db.session import SessionLocal
from backend.db.models import TradingSession
from backend.core.logging import log_event

async def scanner_loop():
    while True:
        try:
            if not engine_state.is_running:
                await asyncio.sleep(5)
                continue
                
            interval = config_manager.get("scan_interval_seconds", 10)
            
            if not mt5_client.is_connected():
                await asyncio.sleep(interval)
                continue
                
            with SessionLocal() as db:
                sessions = db.query(TradingSession).all()
                session_objs = [Session(s.id, s.name, datetime.strptime(s.start_time, "%H:%M").time(), 
                                        datetime.strptime(s.end_time, "%H:%M").time(), 
                                        s.tz, s.days_mask, s.enabled) for s in sessions]
                                        
            if not any_active(session_objs, datetime.utcnow()):
                await asyncio.sleep(interval)
                continue
                
            symbols = config_manager.get("symbols", [])
            for generic_sym in symbols:
                resolved = symbol_resolver.resolve(generic_sym)
                if not resolved:
                    continue
                    
                info = symbol_resolver.get_info(generic_sym)
                if not info:
                    continue
                    
                # check existing positions
                positions = mt5_client.get_positions(resolved)
                if len(positions) >= config_manager.get("max_per_symbol", 1):
                    continue
                    
                df_4h = mt5_client.get_rates(resolved, 16384, 200) # mt5.TIMEFRAME_H4
                df_15m = mt5_client.get_rates(resolved, 15, 300)   # mt5.TIMEFRAME_M15
                df_5m = mt5_client.get_rates(resolved, 5, 500)     # mt5.TIMEFRAME_M5
                
                if df_4h.empty or df_15m.empty or df_5m.empty:
                    continue
                    
                bias, htf_strength, reason = run_htf_bias(df_4h)
                if bias == "neutral":
                    continue
                    
                zone_result = run_mtf_zones(df_15m, bias)
                if not zone_result:
                    continue
                    
                zone_high, zone_low, quality, zone_reason = zone_result
                
                trigger_result = run_ltf_trigger(df_5m, bias, zone_high, zone_low, info["point"])
                if not trigger_result:
                    continue
                    
                entry, sl, tp, trigger_type, ltf_strength = trigger_result
                
                # Mock RSI alignment and session weight for now
                score = calculate_score(htf_strength, quality, 80.0, ltf_strength, 100.0)
                
                if score >= config_manager.get("signal_threshold", 65.0):
                    reason.update(zone_reason)
                    reason["trigger"] = trigger_type
                    await emit_signal(resolved, bias, score, entry, sl, tp, reason)
                    
            engine_state.last_loop_time = datetime.utcnow().isoformat()
            await asyncio.sleep(interval)
            
        except Exception as e:
            log_event("error", "scanner", f"Scanner loop error: {str(e)}")
            await asyncio.sleep(10)
