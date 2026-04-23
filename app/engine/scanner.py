import asyncio
import MetaTrader5 as mt5
from datetime import datetime
import pytz
from app.mt5_client.client import mt5_client
from app.mt5_client.symbol_resolver import SymbolResolver
from app.strategy.htf_bias import calculate_htf_bias
from app.strategy.mtf_zones import find_mtf_zone
from app.strategy.ltf_trigger import find_ltf_trigger
from app.strategy.scoring import calculate_score
from app.core.config import get_config
from app.db.session import AsyncSessionLocal
from app.db.models import Signal, Session as SessionModel
from app.core.sessions import active_sessions, any_active, Session
from app.ws.manager import broadcast
from sqlalchemy import select

symbol_resolver = SymbolResolver(mt5_client)

async def scan_loop():
    while True:
        try:
            cfg = await get_config()
            interval = cfg.get("scan_interval_seconds", 10)
            
            from app.core.state import state
            if not state.engine_running or not mt5_client.is_connected():
                await asyncio.sleep(interval)
                continue
                
            now_utc = datetime.now(pytz.utc)
            async with AsyncSessionLocal() as db:
                result = await db.execute(select(SessionModel))
                session_models = result.scalars().all()
                sessions = [Session(id=s.id, name=s.name, start_time=datetime.strptime(s.start_time, "%H:%M").time(),
                                   end_time=datetime.strptime(s.end_time, "%H:%M").time(), timezone=s.tz,
                                   days_mask=s.days_mask, enabled=s.enabled) for s in session_models]
            
            is_active = any_active(sessions, now_utc)
            state.active_sessions_count = len(active_sessions(sessions, now_utc))
            
            if not is_active:
                await asyncio.sleep(interval)
                continue
                
            await symbol_resolver.refresh()
                
            symbols = cfg.get("symbols", [])
            for generic in symbols:
                resolved = symbol_resolver.resolve(generic)
                if not resolved:
                    continue
                    
                df_4h = await mt5_client.get_rates(resolved, mt5.TIMEFRAME_H4, 200)
                df_15m = await mt5_client.get_rates(resolved, mt5.TIMEFRAME_M15, 300)
                df_5m = await mt5_client.get_rates(resolved, mt5.TIMEFRAME_M5, 500)
                
                if df_4h.empty or df_15m.empty or df_5m.empty: continue
                
                htf = calculate_htf_bias(df_4h)
                bias = htf['bias']
                if bias == 'neutral': continue
                
                mtf_zone = find_mtf_zone(df_15m, bias)
                if not mtf_zone: continue
                
                point = 0.0001
                try:
                    info = mt5.symbol_info(resolved)
                    if info: point = info.point
                except: pass
                    
                ltf_trigger = find_ltf_trigger(df_5m, mtf_zone, bias, point, float(cfg.get("reward_ratio", 2.0)))
                if not ltf_trigger: continue
                
                score = calculate_score(htf['strength'], mtf_zone['quality'], ltf_trigger['strength'], True)
                
                status = 'FIRED' if score >= int(cfg.get("signal_threshold", 65)) else 'REJECTED'
                
                async with AsyncSessionLocal() as db:
                    sig = Signal(symbol=resolved, direction=bias, score=score, htf_bias=bias, 
                                entry=ltf_trigger['entry'], sl=ltf_trigger['sl'], tp=ltf_trigger['tp'],
                                reason={"htf": htf, "zone": mtf_zone, "trigger": ltf_trigger}, status=status)
                    db.add(sig)
                    await db.commit()
                    await db.refresh(sig)
                    
                    await broadcast({
                        "type": "signal.new",
                        "signal": {
                            "id": sig.id, "symbol": generic, "direction": bias, "score": score,
                            "status": status, "reason": sig.reason, "created_at": sig.created_at.isoformat()
                        }
                    })
                    
                if status == 'FIRED':
                    from app.engine.order_manager import send_order
                    await send_order(sig, resolved, bias, cfg)
                    
            await asyncio.sleep(interval)
        except Exception as e:
            print("Scanner error:", e)
            await asyncio.sleep(5)
