import asyncio
import logging
from datetime import datetime, timezone
import MetaTrader5 as mt5

from app.core.config import cfg
from app.ui.state import state
from app.mt5_client.client import mt5_client
from app.mt5_client.symbol_resolver import SymbolResolver
from app.core.sessions import any_active
from app.db.session import SessionLocal
from app.db.models import SessionRecord, SymbolCache

from app.strategy.htf_bias import calculate_htf_bias
from app.strategy.mtf_zones import calculate_mtf_zones
from app.strategy.ltf_trigger import calculate_ltf_trigger
from app.strategy.scoring import calculate_score

from app.engine.signal_engine import process_signal

logger = logging.getLogger("scanner")
resolver = SymbolResolver(mt5_client)

async def scanner_loop():
    while state.engine_running:
        try:
            await asyncio.sleep(cfg.scan_interval_seconds)
            
            if not mt5_client.is_connected():
                continue
                
            db = SessionLocal()
            sessions = db.query(SessionRecord).all()
            db.close()
            
            if not any_active(sessions, datetime.now(timezone.utc)):
                logger.info("No active session, skipping scan")
                continue
                
            for sym in cfg.symbols:
                resolved = await resolver.resolve(sym)
                if not resolved:
                    continue
                    
                # Get symbol info for point/digits
                info = await asyncio.to_thread(mt5.symbol_info, resolved)
                if not info: continue
                
                # Fetch data
                df_4h = await mt5_client.get_rates(resolved, mt5.TIMEFRAME_H4, 200)
                df_15m = await mt5_client.get_rates(resolved, mt5.TIMEFRAME_M15, 300)
                df_5m = await mt5_client.get_rates(resolved, mt5.TIMEFRAME_M5, 500)
                
                if df_4h.empty or df_15m.empty or df_5m.empty: continue
                
                # HTF Pipeline
                bias, htf_str, htf_reason = calculate_htf_bias(df_4h)
                if bias == 'neutral': continue
                
                # MTF Pipeline
                mtf_res = calculate_mtf_zones(df_15m, bias)
                if not mtf_res: continue
                z_high, z_low, z_qual, z_reason = mtf_res
                
                # LTF Pipeline
                ltf_res = calculate_ltf_trigger(df_5m, z_high, z_low, bias, info.point, cfg.reward_ratio)
                if not ltf_res: continue
                entry, sl, tp, trig_type, ltf_str = ltf_res
                
                # Score
                score = calculate_score(htf_str, z_qual, 80, ltf_str, 100)
                
                if score >= cfg.signal_threshold:
                    await process_signal({
                        'symbol': resolved,
                        'direction': bias,
                        'score': score,
                        'htf_bias': bias,
                        'entry': entry,
                        'sl': sl,
                        'tp': tp,
                        'reason': {'htf': htf_reason, 'mtf': z_reason, 'trigger': trig_type}
                    })
                    
        except Exception as e:
            logger.error(f"Scanner error: {e}")
            state.last_error = str(e)
