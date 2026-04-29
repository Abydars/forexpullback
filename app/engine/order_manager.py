import asyncio
import MetaTrader5 as mt5
from app.mt5_client.client import mt5_client
from app.db.session import AsyncSessionLocal
from app.db.models import Trade, Event
from datetime import datetime
from app.ws.manager import broadcast
from sqlalchemy import select
import pytz

import time

async def send_order(sig, resolved: str, bias: str, cfg: dict, is_dca=False, dca_data=None, timings=None):
    if timings is None: timings = {}
    try:
        magic = int(cfg.get("magic_number", 123456))
        positions = await mt5_client.get_positions()
        
        bot_positions = [p for p in positions if p.get('magic') == magic]
        
        if len(bot_positions) >= int(cfg.get("max_open_positions", 5)):
            return
            
        if not is_dca:
            sym_pos = [p for p in bot_positions if p['symbol'] == resolved]
            if len(sym_pos) >= int(cfg.get("max_per_symbol", 1)):
                return
                
            dir_type = 0 if bias == 'bullish' else 1
            sym_dir_pos = [p for p in sym_pos if p['type'] == dir_type]
            if len(sym_dir_pos) >= int(cfg.get("max_per_direction", 3)):
                return
            
        acc = await mt5_client.account_info()
        balance = acc['balance']
        
        info = mt5.symbol_info(resolved)
        if not info: return
        
        tick = mt5.symbol_info_tick(resolved)
        if not tick: return
        actual_price = tick.ask if bias == 'bullish' else tick.bid
        
        # Spread check (Dynamic Percentage of Stop Loss)
        spread = tick.ask - tick.bid
        sl_distance = abs(actual_price - sig.sl)
        
        # Calculate what percentage of the risk (SL distance) is eaten by the spread
        spread_pct = (spread / sl_distance) * 100 if sl_distance > 0 else 100
        max_spread_pct = float(cfg.get("max_spread_pct", 20.0))
        
        if spread_pct > max_spread_pct:
            async with AsyncSessionLocal() as db:
                err_msg = f"Order {resolved} rejected: Spread is {spread_pct:.1f}% of SL distance (Max allowed: {max_spread_pct}%)"
                e = Event(level="WARN", component="order_manager", message=err_msg)
                db.add(e)
                await db.commit()
                await broadcast({"type": "log.event", "level": "WARN", "component": "order_manager", "message": err_msg, "created_at": datetime.now(pytz.utc).isoformat()})
            return
        
        if sl_distance <= 0:
            async with AsyncSessionLocal() as db:
                err_msg = f"Order {resolved} rejected: SL distance is zero or invalid"
                e = Event(level="WARN", component="order_manager", message=err_msg)
                db.add(e)
                await db.commit()
                await broadcast({"type": "log.event", "level": "WARN", "component": "order_manager", "message": err_msg, "created_at": datetime.now(pytz.utc).isoformat()})
            return

        risk_pct = float(cfg.get("risk_percent", 1.0))
        risk_amount = balance * risk_pct / 100
        
        def _calc_profit():
            action_type = mt5.ORDER_TYPE_BUY if bias == 'bullish' else mt5.ORDER_TYPE_SELL
            return mt5.order_calc_profit(action_type, resolved, 1.0, actual_price, sig.sl)
            
        profit_1_lot = await asyncio.to_thread(_calc_profit)
        
        # Risk per 1 lot calculation without random 1.0 fallbacks
        if profit_1_lot is not None and profit_1_lot < 0:
            loss_for_1_lot = abs(profit_1_lot)
        else:
            sl_points = sl_distance / info.point if info.point else 0
            if info.trade_tick_value and sl_points > 0:
                loss_for_1_lot = sl_points * info.trade_tick_value
            else:
                async with AsyncSessionLocal() as db:
                    err_msg = f"Order {resolved} rejected: Cannot calculate risk (profit_1_lot={profit_1_lot}, tick_value={info.trade_tick_value})"
                    e = Event(level="WARN", component="order_manager", message=err_msg)
                    db.add(e)
                    await db.commit()
                    await broadcast({"type": "log.event", "level": "WARN", "component": "order_manager", "message": err_msg, "created_at": datetime.now(pytz.utc).isoformat()})
                return

        if is_dca and dca_data:
            lot = dca_data.get('dca_lot', info.volume_min)
        else:
            lot = risk_amount / loss_for_1_lot
            
            # precise volume calculation to prevent MT5 invalid volume errors
            steps = round(lot / info.volume_step)
            lot = steps * info.volume_step
            lot = max(info.volume_min, min(info.volume_max, lot))
            lot = float(f"{lot:.8f}".rstrip('0').rstrip('.')) if '.' in f"{lot:.8f}" else float(lot)
            
        print(f"[{resolved}] ORDER LOT CALC: Balance={balance:.2f}, RiskAmt={risk_amount:.2f}, SL_Dist={sl_distance:.5f}, RiskPer1Lot={loss_for_1_lot:.2f}, FinalLot={lot}")

        action = mt5.TRADE_ACTION_DEAL
        type_ = mt5.ORDER_TYPE_BUY if bias == 'bullish' else mt5.ORDER_TYPE_SELL
        
        # dynamically determine correct filling mode based on broker/symbol limits
        filling_type = mt5.ORDER_FILLING_IOC
        if info.filling_mode & 1:
            filling_type = mt5.ORDER_FILLING_FOK
        elif info.filling_mode & 2:
            filling_type = mt5.ORDER_FILLING_IOC
        else:
            filling_type = mt5.ORDER_FILLING_RETURN
        
        request = {
            "action": action,
            "symbol": resolved,
            "volume": float(lot),
            "type": type_,
            "price": actual_price,
            "sl": sig.sl,
            "tp": sig.tp,
            "deviation": 20,
            "magic": magic,
            "comment": f"Sig {sig.id}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": filling_type,
        }
        
        # 1. Check Broker Stop Levels
        stops_level_points = info.trade_stops_level * info.point
        if abs(actual_price - sig.sl) <= stops_level_points:
            async with AsyncSessionLocal() as db:
                err_msg = f"Order {resolved} rejected: SL distance is closer than broker stops_level ({info.trade_stops_level} points)"
                e = Event(level="WARN", component="order_manager", message=err_msg)
                db.add(e)
                await db.commit()
                await broadcast({"type": "log.event", "level": "WARN", "component": "order_manager", "message": err_msg, "created_at": datetime.now(pytz.utc).isoformat()})
            return
            
        # 2. Dry-run Order Check
        def _check_order():
            return mt5.order_check(request)
            
        check_result = await asyncio.to_thread(_check_order)
        timings["order_check_done"] = time.time() * 1000
        # order_check() returns 0 on success, NOT TRADE_RETCODE_DONE (10009)
        if check_result is None or check_result.retcode != 0:
            async with AsyncSessionLocal() as db:
                comment = check_result.comment if check_result else 'Unknown Error'
                code = check_result.retcode if check_result else 'None'
                err_msg = f"Order {resolved} failed dry-run: {comment} (Code {code})"
                e = Event(level="WARN", component="order_manager", message=err_msg)
                db.add(e)
                await db.commit()
                await broadcast({"type": "log.event", "level": "WARN", "component": "order_manager", "message": err_msg, "created_at": datetime.now(pytz.utc).isoformat()})
            return
        
        timings["order_send_called"] = time.time() * 1000
        res = await mt5_client.order_send(request)
        timings["order_send_done"] = time.time() * 1000
        
        if res and res.get('retcode') == mt5.TRADE_RETCODE_DONE:
            order_ticket = res.get('order')
            deal_ticket = res.get('deal')
            
            def _get_pos_id():
                if deal_ticket:
                    deals = mt5.history_deals_get(ticket=deal_ticket)
                    if deals and len(deals) > 0:
                        return deals[0].position_id
                return order_ticket
                
            ticket = await asyncio.to_thread(_get_pos_id)
            
            async with AsyncSessionLocal() as db:
                t = Trade(signal_id=sig.id, ticket=ticket, symbol=resolved, direction=bias,
                         lot=lot, entry_price=res.get('price'), sl=sig.sl, tp=sig.tp,
                         opened_at=datetime.now(pytz.utc))
                
                if is_dca and dca_data:
                    t.parent_trade_id = dca_data.get('parent_ticket')
                    t.dca_index = dca_data.get('dca_index', 0)
                    t.group_id = f"grp_{t.parent_trade_id}"
                    t.note = f"DCA #{t.dca_index}"
                else:
                    t.note = "BASE"
                    t.group_id = f"grp_{ticket}"

                db.add(t)
                await db.commit()
                await db.refresh(t)
                
                if is_dca and dca_data:
                    dir_type = 0 if bias == 'bullish' else 1
                    all_pos = await mt5_client.get_positions()
                    sym_dir_pos = [p for p in all_pos if p.get('magic') == magic and p['symbol'] == resolved and p['type'] == dir_type]
                    
                    reanchor_sl = cfg.get("dca_reanchor_sl", True)
                    
                    for p in sym_dir_pos:
                        if p['ticket'] == ticket:
                            continue
                            
                        new_tp = sig.tp
                        new_sl = sig.sl if reanchor_sl else p['sl']
                        
                        if p['tp'] != new_tp or p['sl'] != new_sl:
                            req_sltp = {
                                "action": mt5.TRADE_ACTION_SLTP,
                                "position": p['ticket'],
                                "symbol": resolved,
                                "sl": new_sl,
                                "tp": new_tp,
                                "magic": magic
                            }
                            await asyncio.to_thread(mt5.order_send, req_sltp)
                            
                            db_trade_res = await db.execute(select(Trade).where(Trade.ticket == p['ticket']))
                            db_trade = db_trade_res.scalars().first()
                            if db_trade:
                                db_trade.sl = new_sl
                                db_trade.tp = new_tp
                    
                await broadcast({
                    "type": "trade.opened",
                    "trade": {
                        "ticket": ticket, "symbol": resolved, "direction": bias,
                        "lot": lot, "entry_price": t.entry_price, "sl": t.sl, "tp": t.tp,
                        "pnl": 0.0, "opened_at": t.opened_at.isoformat()
                    }
                })
                
                await db.commit()
                
                timings["order_done"] = time.time() * 1000
                if "scan_start" in timings and cfg.get("enable_latency_logs", True):
                    t_scan = timings.get("symbol_scan_start", timings["scan_start"]) - timings["scan_start"]
                    t_data = timings.get("data_fetch_done", timings["scan_start"]) - timings.get("symbol_scan_start", timings["scan_start"])
                    t_trig = timings.get("trigger_done", timings["scan_start"]) - timings.get("data_fetch_done", timings["scan_start"])
                    t_save = timings.get("signal_saved", timings["scan_start"]) - timings.get("trigger_done", timings["scan_start"])
                    t_ocheck = timings.get("order_check_done", timings["scan_start"]) - timings.get("signal_saved", timings["scan_start"])
                    t_osend = timings.get("order_send_called", timings["scan_start"]) - timings.get("order_check_done", timings["scan_start"])
                    t_mt5 = timings.get("order_send_done", timings["scan_start"]) - timings.get("order_send_called", timings["scan_start"])
                    t_odone = timings["order_done"] - timings.get("order_send_done", timings["scan_start"])
                    total = timings["order_done"] - timings["scan_start"]
                    
                    t_msg = f"Latency [Sig {sig.id} - {resolved}]: ScanWait={t_scan:.0f}ms | Data={t_data:.0f}ms | Trig={t_trig:.0f}ms | DB_Save={t_save:.0f}ms | OrderCheck={t_ocheck:.0f}ms | Prep={t_osend:.0f}ms | MT5_Send={t_mt5:.0f}ms | Finalize={t_odone:.0f}ms || TOTAL={total:.0f}ms"
                    
                    e = Event(level="INFO", component="latency", message=t_msg)
                    db.add(e)
                    await db.commit()
                    await broadcast({"type": "log.event", "level": "INFO", "component": "latency", "message": t_msg, "created_at": datetime.now(pytz.utc).isoformat()})
        else:
            async with AsyncSessionLocal() as db:
                err_msg = f"Order rejected (Retcode {res.get('retcode')}): {res.get('comment', 'Unknown')}"
                e = Event(level="ERROR", component="order_manager", message=err_msg)
                db.add(e)
                await db.commit()
                await broadcast({
                    "type": "log.event", "level": "ERROR", "component": "order_manager", "message": err_msg, "created_at": datetime.now(pytz.utc).isoformat()
                })
    except Exception as e:
        print("Order manager error:", e)
        err_msg = f"Order exception: {str(e)}"
        try:
            async with AsyncSessionLocal() as db:
                ev = Event(level="ERROR", component="order_manager", message=err_msg)
                db.add(ev)
                await db.commit()
                await broadcast({
                    "type": "log.event", "level": "ERROR", "component": "order_manager", "message": err_msg, "created_at": datetime.now(pytz.utc).isoformat()
                })
        except:
            pass
