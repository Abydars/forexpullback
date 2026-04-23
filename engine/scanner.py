import asyncio
import pandas as pd
from datetime import datetime
from core.config import config_manager
from core.state import engine_state
from core.logging import log_event
from mt5_client.client import mt5_client
from mt5_client.symbol_resolver import symbol_resolver
from strategy.htf_bias import run_htf_bias
from strategy.mtf_zones import run_mtf_zones
from strategy.ltf_trigger import run_ltf_trigger
from strategy.scoring import calculate_score
from engine.signal_engine import emit_signal

async def scanner_loop():
    while True:
        try:
            if not engine_state.is_running or not mt5_client.is_connected():
                await asyncio.sleep(1)
                continue
                
            engine_state.last_loop_time = datetime.utcnow().isoformat()
            
            symbols = config_manager.get("symbols", ["EURUSD"])
            resolved_symbols = symbol_resolver.resolve_many(symbols)
            
            for gen_sym, broker_sym in resolved_symbols.items():
                if not broker_sym:
                    continue
                    
                rates_4h = mt5_client.copy_rates_from_pos(broker_sym, 16388, 0, 500)
                if rates_4h is None: continue
                df_4h = pd.DataFrame(rates_4h)
                
                bias, str_htf, reason_htf = run_htf_bias(df_4h)
                if bias == "neutral":
                    continue
                    
                rates_15m = mt5_client.copy_rates_from_pos(broker_sym, 15, 0, 500)
                if rates_15m is None: continue
                df_15m = pd.DataFrame(rates_15m)
                
                zone, str_mtf, reason_mtf = run_mtf_zones(df_15m, bias)
                if not zone:
                    continue
                    
                rates_5m = mt5_client.copy_rates_from_pos(broker_sym, 5, 0, 100)
                if rates_5m is None: continue
                df_5m = pd.DataFrame(rates_5m)
                
                trigger, entry, sl, str_ltf, reason_ltf = run_ltf_trigger(df_5m, bias, zone)
                if trigger:
                    score = calculate_score(str_htf, str_mtf, str_ltf, 80.0, 100.0)
                    if score >= config_manager.get("signal_threshold", 65.0):
                        tp = entry + ((entry - sl) * config_manager.get("reward_ratio", 2.0))
                        await emit_signal(
                            gen_sym, bias, score, entry, sl, tp, 
                            {"htf": reason_htf, "mtf": reason_mtf, "ltf": reason_ltf}
                        )
                        
            await asyncio.sleep(config_manager.get("scan_interval_seconds", 10))
            
        except Exception as e:
            log_event("error", "scanner", f"Loop error: {e}")
            await asyncio.sleep(5)
