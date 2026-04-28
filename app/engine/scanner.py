import time
import asyncio
import MetaTrader5 as mt5
from datetime import datetime, timedelta
import pytz
import pandas as pd
from app.mt5_client.client import mt5_client
from app.mt5_client.symbol_resolver import SymbolResolver
from app.strategy.htf_bias import calculate_htf_bias
from app.strategy.mtf_zones import find_mtf_zone
from app.strategy.ltf_trigger import find_ltf_trigger
from app.strategy.scoring import calculate_score
from app.core.config import get_config
from app.db.session import AsyncSessionLocal
from app.db.models import Signal, Session as SessionModel, Trade
from app.core.sessions import active_sessions, any_active, Session
from app.ws.manager import broadcast
from sqlalchemy import select

symbol_resolver = SymbolResolver(mt5_client)

scanner_state = {}

def calc_adx(df: pd.DataFrame, period=14):
    df['up_move'] = df['high'] - df['high'].shift(1)
    df['down_move'] = df['low'].shift(1) - df['low']
    df['+dm'] = 0.0
    df['-dm'] = 0.0
    df.loc[(df['up_move'] > df['down_move']) & (df['up_move'] > 0), '+dm'] = df['up_move']
    df.loc[(df['down_move'] > df['up_move']) & (df['down_move'] > 0), '-dm'] = df['down_move']
    df['tr'] = pd.concat([df['high'] - df['low'], abs(df['high'] - df['close'].shift(1)), abs(df['low'] - df['close'].shift(1))], axis=1).max(axis=1)
    df['+di'] = 100 * (df['+dm'].ewm(alpha=1/period, adjust=False).mean() / df['tr'].ewm(alpha=1/period, adjust=False).mean())
    df['-di'] = 100 * (df['-dm'].ewm(alpha=1/period, adjust=False).mean() / df['tr'].ewm(alpha=1/period, adjust=False).mean())
    df['dx'] = 100 * abs(df['+di'] - df['-di']) / (df['+di'] + df['-di'])
    df['adx'] = df['dx'].ewm(alpha=1/period, adjust=False).mean()
    return df['adx'].iloc[-2], df['tr'].ewm(alpha=1/period, adjust=False).mean().iloc[-2]

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
            current_5m_slot = (now_utc.minute // 5) * 5
            
            # Calculate exactly how many seconds are left until the next 5-minute boundary
            seconds_in_5m = 300
            current_seconds = (now_utc.minute % 5) * 60 + now_utc.second + (now_utc.microsecond / 1_000_000)
            time_to_next = seconds_in_5m - current_seconds
            
            # Ensure we only scan exactly ONCE right after a 5-minute candle closes
            if 'last_scan_slot' not in scanner_state:
                # First run: set the slot and wait for the next close boundary
                scanner_state['last_scan_slot'] = current_5m_slot
                # Wake up 0.5s after the boundary to ensure MT5 has finalized the candle
                sleep_duration = min(float(interval), time_to_next + 0.5)
                await asyncio.sleep(sleep_duration)
                continue
                
            last_scan_slot = scanner_state['last_scan_slot']
            
            # If we haven't reached the next 5-minute boundary yet, skip
            if last_scan_slot == current_5m_slot:
                # Wake up 0.5s after the boundary to ensure MT5 has finalized the candle
                sleep_duration = min(float(interval), time_to_next + 0.5)
                await asyncio.sleep(sleep_duration)
                continue
                
            scanner_state['last_scan_slot'] = current_5m_slot
            
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
                
            scan_start_ms = time.time() * 1000
            
            symbols = cfg.get("symbols", [])
            
            # --- PRE-FETCH COOLDOWNS ---
            cooldown_mins = int(cfg.get("signal_cooldown_minutes", 30))
            cutoff = now_utc - timedelta(minutes=cooldown_mins)
            
            recent_closed_set = set()
            recent_fired_set = set()
            
            async with AsyncSessionLocal() as db:
                from app.db.models import Trade, Signal
                recent_trades = await db.execute(select(Trade.symbol, Trade.direction).where(
                    Trade.closed_at != None,
                    Trade.closed_at >= cutoff
                ))
                for sym, dr in recent_trades:
                    recent_closed_set.add((sym, dr))
                    
                recent_signals = await db.execute(select(Signal.symbol, Signal.direction).where(
                    Signal.status == "FIRED",
                    Signal.created_at >= cutoff
                ))
                for sym, dr in recent_signals:
                    recent_fired_set.add((sym, dr))
            
            # --- RANKING CONFIG & POSITIONS ---
            max_signals_per_scan = int(cfg.get("max_signals_per_scan", 1))
            max_open = int(cfg.get("max_open_positions", 5))
            max_symbol = int(cfg.get("max_per_symbol", 1))
            max_dir = int(cfg.get("max_per_direction", 3))
            magic = int(cfg.get("magic_number", 123456))
            
            bot_positions = []
            res_pos = await mt5_client.get_positions()
            if res_pos:
                bot_positions = [p for p in res_pos if p.get('magic') == magic]
                
            correlation_groups_enabled = cfg.get("correlation_groups_enabled", True)
            enabled_correlation_groups = cfg.get("enabled_correlation_groups", ["indices", "metals", "jpy", "usd_majors", "oil"])
            max_corr = int(cfg.get("max_open_per_correlation_group", 1))

            CORRELATION_GROUPS = {
                "indices": ["US30", "US500", "USTEC"],
                "metals": ["XAUUSD", "XAGUSD"],
                "oil": ["USOIL", "UKOIL"],
                "usd_majors": ["EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "USDCAD", "USDCHF"],
                "jpy_pairs": ["USDJPY", "EURJPY", "GBPJPY", "AUDJPY", "CADJPY", "CHFJPY", "NZDJPY"],
                "eur_crosses": ["EURAUD", "EURCAD", "EURGBP", "EURCHF", "EURNZD"],
                "gbp_crosses": ["GBPAUD", "GBPCAD", "GBPCHF", "GBPNZD"],
                "minor_crosses": ["AUDCAD", "AUDCHF", "AUDNZD", "CADCHF", "NZDCAD", "NZDCHF"]
            }
            
            generic_to_group = {}
            for g, syms in CORRELATION_GROUPS.items():
                for s in syms:
                    generic_to_group[s] = g
            
            group_open_counts = {g: 0 for g in CORRELATION_GROUPS}
            if correlation_groups_enabled:
                for p in bot_positions:
                    for g_sym in generic_to_group:
                        if symbol_resolver.resolve(g_sym) == p['symbol']:
                            group_open_counts[generic_to_group[g_sym]] += 1
                            break
                
            candidates = []
            updates_to_broadcast = []
            
            async def scan_symbol(generic):
                local_candidates = []
                local_updates = []
                timings = {"scan_start": scan_start_ms, "symbol_scan_start": time.time() * 1000}
                resolved = symbol_resolver.resolve(generic)
                if not resolved:
                    return [], []
                    
                reason_full = {"htf": None, "zone": None, "trigger": None, "msg": ""}
                status = "REJECTED"
                score = 0
                bias = "neutral"
                
                info = mt5.symbol_info(resolved)
                tick = mt5.symbol_info_tick(resolved)
                current_time = datetime.now().timestamp()
                
                if not info or info.trade_mode != mt5.SYMBOL_TRADE_MODE_FULL:
                    reason_full["msg"] = "Market is CLOSED (Trading Disabled)"
                elif not tick or (current_time - tick.time) > 300:
                    reason_full["msg"] = "Market is CLOSED (Stale tick data)"
                else:
                    df_4h = await mt5_client.get_rates(resolved, mt5.TIMEFRAME_H4, 200)
                    df_1h = await mt5_client.get_rates(resolved, mt5.TIMEFRAME_H1, 200)
                    df_15m = await mt5_client.get_rates(resolved, mt5.TIMEFRAME_M15, 300)
                    df_5m = await mt5_client.get_rates(resolved, mt5.TIMEFRAME_M5, 500)
                    
                    timings["data_fetch_done"] = time.time() * 1000
                    
                    if df_4h.empty or df_1h.empty or df_15m.empty or df_5m.empty: 
                        reason_full["msg"] = "Not enough data (need more bars)"
                    else:
                        # Volatility and Spread Checks
                        adx, atr = calc_adx(df_15m, 14)
                        point = info.point if info else 0.0001
                        spread_points = (tick.ask - tick.bid) / point if tick else 0
                        atr_points = atr / point if point > 0 else 1
                        
                        htf = calculate_htf_bias(df_4h, df_1h)
                        reason_full["htf"] = htf
                        bias = htf['bias']
                        
                        if bias == 'neutral':
                            reason_full["msg"] = "Neutral HTF Bias (4H EMA not aligned)"
                        else:
                            mtf_zone = find_mtf_zone(df_15m, bias)
                            reason_full["zone"] = mtf_zone
                            
                            if not mtf_zone:
                                reason_full["msg"] = "No 15M Pullback Zone (Not near EMA or FVG)"
                            else:
                                base_atr_mult = float(cfg.get("atr_buffer_multiplier", 0.2))
                                
                                # Dynamic Volatility (Spike) Factor instead of hardcoded symbols
                                recent_tr = pd.concat([
                                    df_15m['high'] - df_15m['low'],
                                    abs(df_15m['high'] - df_15m['close'].shift(1)),
                                    abs(df_15m['low'] - df_15m['close'].shift(1))
                                ], axis=1).max(axis=1).iloc[-14:]
                                
                                local_atr = recent_tr.mean()
                                max_tr = recent_tr.max()
                                
                                if local_atr > 0:
                                    spike_factor = max_tr / local_atr
                                    if spike_factor > 2.0:
                                        # Scale multiplier based on how spiky the asset is (capped at 3x)
                                        scale = min(spike_factor / 1.5, 3.0)
                                        base_atr_mult *= scale
                                        
                                ltf_trigger = find_ltf_trigger(
                                    df_5m, df_15m, atr, mtf_zone, bias, point, 
                                    float(cfg.get("reward_ratio", 2.0)),
                                    base_atr_mult,
                                    cfg.get("use_liquidity_tp", True),
                                    float(cfg.get("min_sl_atr_multiplier", 0.8))
                                )
                                timings["trigger_done"] = time.time() * 1000
                                reason_full["trigger"] = ltf_trigger
                                
                                is_strong_trigger = ltf_trigger and ltf_trigger['strength'] >= 80
                                
                                if (spread_points / atr_points) > 0.25:
                                    reason_full["msg"] = f"Spread too high relative to ATR (Spread={spread_points:.1f}, ATR={atr_points:.1f})"
                                elif adx < 15 and not is_strong_trigger:
                                    reason_full["msg"] = f"Low Volatility (ADX={adx:.1f} < 15) and no strong trigger"
                                else:
                                    # Dynamic Threshold Logic
                                    base_threshold = int(cfg.get("signal_threshold", 65))
                                    current_hour = now_utc.hour
                                    # London/NY overlap is roughly 12:00 to 16:00 UTC
                                    if 12 <= current_hour <= 16:
                                        base_threshold -= 5 # Easier threshold during overlap
                                    elif current_hour < 6 or current_hour > 20:
                                        base_threshold += 5 # Stricter during Asian session
                                        
                                    if spread_points > 15: base_threshold += 5
                                    if htf['strength'] >= 80: base_threshold -= 5
                                    
                                    if not ltf_trigger:
                                        status = "WATCHING"
                                        reason_full["msg"] = f"Zone Valid, Waiting for Trigger (Thresh: {base_threshold})"
                                        
                                        state_key = f"{resolved}_{bias}"
                                        scanner_state[state_key] = {"time": now_utc, "status": "WATCHING"}
                                    else:
                                        score = calculate_score(htf['strength'], mtf_zone['quality'], ltf_trigger['strength'], True)
                                        
                                        # Smart Cooldown Check via Pre-fetched sets
                                        has_recent_closed = (resolved, bias) in recent_closed_set
                                        has_recent_fired = (resolved, bias) in recent_fired_set
                                        
                                        state_key = f"{resolved}_{bias}"
                                        
                                        # Also check if a trade is currently open for this symbol
                                        open_positions_for_sym = [p for p in bot_positions if p['symbol'] == resolved]
                                        ord_type = mt5.ORDER_TYPE_BUY if bias == 'bullish' else mt5.ORDER_TYPE_SELL
                                        sym_count = len(open_positions_for_sym)
                                        
                                        is_dca_allowed = False
                                        is_dca_candidate = False
                                        
                                        if sym_count > 0:
                                            enable_dca = cfg.get("enable_dca", False)
                                            same_dir_positions = [p for p in open_positions_for_sym if p.get('type') == ord_type]
                                            
                                            if enable_dca and score >= base_threshold and len(same_dir_positions) > 0:
                                                max_dca_entries = int(cfg.get("max_dca_entries", 1))
                                                dca_trigger_sl_progress = float(cfg.get("dca_trigger_sl_progress", 0.5))
                                                dca_max_total_risk_r = float(cfg.get("dca_max_total_risk_r", 2.0))
                                                
                                                same_dir_positions.sort(key=lambda x: x.get('time', 0))
                                                base_trade = same_dir_positions[0]
                                                base_entry = base_trade.get('price_open')
                                                base_sl = base_trade.get('sl')
                                                
                                                if base_entry and base_sl and base_entry != base_sl:
                                                    current_price = tick.ask if bias == 'bullish' else tick.bid
                                                    
                                                    if bias == 'bullish':
                                                        progress = (base_entry - current_price) / (base_entry - base_sl)
                                                    else:
                                                        progress = (current_price - base_entry) / (base_sl - base_entry)
                                                        
                                                    dca_count = len(same_dir_positions) - 1
                                                    
                                                    if dca_count >= max_dca_entries:
                                                        status = "DCA_SKIPPED"
                                                        reason_full["msg"] = "Skipped DCA: max entries reached"
                                                    elif progress < dca_trigger_sl_progress:
                                                        status = "DCA_SKIPPED"
                                                        reason_full["msg"] = f"Skipped DCA: price not moved enough ({progress:.2f} < {dca_trigger_sl_progress})"
                                                    elif progress >= 0.85:
                                                        status = "DCA_SKIPPED"
                                                        reason_full["msg"] = "Skipped DCA: too close to SL"
                                                    else:
                                                        original_lot = base_trade.get('volume')
                                                        dca_lot_multiplier = float(cfg.get("dca_lot_multiplier", 0.7))
                                                        dca_lot = original_lot * dca_lot_multiplier
                                                        if dca_lot < info.volume_min: dca_lot = info.volume_min
                                                        if dca_lot > info.volume_max: dca_lot = info.volume_max
                                                        step = info.volume_step
                                                        dca_lot = round(dca_lot / step) * step
                                                        
                                                        dca_reanchor_sl = cfg.get("dca_reanchor_sl", True)
                                                        new_sl = ltf_trigger['sl'] if dca_reanchor_sl else base_sl
                                                        
                                                        def _calc_risk(action, symbol, vol, open_price, sl_price):
                                                            if not open_price or not sl_price or open_price == sl_price: return 0
                                                            profit = mt5.order_calc_profit(action, symbol, vol, open_price, sl_price)
                                                            return abs(profit) if profit and profit < 0 else 1.0 # Fallback
                                                        
                                                        # Base 1R risk amount (original trade's initial risk)
                                                        base_1r_risk = await asyncio.to_thread(_calc_risk, ord_type, resolved, original_lot, base_entry, base_sl)
                                                        if base_1r_risk == 0: base_1r_risk = 1.0
                                                        
                                                        total_new_risk = await asyncio.to_thread(_calc_risk, ord_type, resolved, dca_lot, current_price, new_sl)
                                                        
                                                        for p in same_dir_positions:
                                                            p_entry = p.get('price_open')
                                                            p_vol = p.get('volume')
                                                            p_risk = await asyncio.to_thread(_calc_risk, ord_type, resolved, p_vol, p_entry, new_sl)
                                                            total_new_risk += p_risk
                                                        
                                                        total_risk_r = total_new_risk / base_1r_risk
                                                        
                                                        if total_risk_r > dca_max_total_risk_r:
                                                            status = "DCA_SKIPPED"
                                                            reason_full["msg"] = f"Skipped DCA: total risk cap exceeded ({total_risk_r:.2f} > {dca_max_total_risk_r})"
                                                        else:
                                                            status = "DCA_FIRED"
                                                            reason_full["msg"] = "DCA added: fresh signal while price near SL"
                                                            is_dca_allowed = True
                                                            is_dca_candidate = True
                                                            
                                                            ltf_trigger['is_dca'] = True
                                                            ltf_trigger['dca_index'] = dca_count + 1
                                                            ltf_trigger['dca_lot'] = dca_lot
                                                            ltf_trigger['sl'] = new_sl
                                                            ltf_trigger['parent_ticket'] = base_trade.get('ticket')
                                            
                                            if not is_dca_allowed and status not in ("DCA_SKIPPED", "DCA_FIRED"):
                                                status = "COOLDOWN"
                                                reason_full["msg"] = "Skipped: position already open for this symbol"
                                                
                                        elif has_recent_closed:
                                            status = "COOLDOWN"
                                            reason_full["msg"] = f"Skipped: recent trade exit cooldown ({cooldown_mins}m)"
                                        elif has_recent_fired:
                                            status = "COOLDOWN"
                                            reason_full["msg"] = f"Fired recently, waiting {cooldown_mins}m"
                                        elif score >= base_threshold:
                                            # POSITION LIMITS CHECK BEFORE CANDIDATE SELECTION
                                            dir_count = len([p for p in bot_positions if p.get('type') == ord_type])
                                            
                                            if len(bot_positions) >= max_open or sym_count >= max_symbol or dir_count >= max_dir:
                                                status = "SKIPPED"
                                                reason_full["msg"] = "Skipped because position limit already reached"
                                            else:
                                                my_group = generic_to_group.get(generic)
                                                if correlation_groups_enabled and my_group and my_group in enabled_correlation_groups:
                                                    if group_open_counts[my_group] >= max_corr:
                                                        status = "SKIPPED"
                                                        reason_full["msg"] = f"Skipped: max open positions ({max_corr}) for group '{my_group}' reached"
                                                
                                                if status != "SKIPPED":
                                                    status = "FIRED" # Temporary status
                                                    reason_full["msg"] = f"Candidate Accepted! Score: {score} >= {base_threshold}"
                                                
                                                    local_candidates.append({
                                                        "generic": generic,
                                                        "resolved": resolved,
                                                        "bias": bias,
                                                        "score": score,
                                                        "ltf_trigger": ltf_trigger,
                                                        "reason_full": dict(reason_full),
                                                        "cfg": cfg,
                                                        "threshold": base_threshold,
                                                        "state_key": state_key,
                                                        "timings": dict(timings)
                                                    })
                                        else:
                                            status = "WATCHING"
                                            reason_full["msg"] = f"Low Score ({score} < {base_threshold})"
                                            scanner_state[state_key] = {"time": now_utc, "status": "WATCHING"}
                                            
                                        if is_dca_candidate and status != "DCA_SKIPPED":
                                            local_candidates.append({
                                                "generic": generic,
                                                "resolved": resolved,
                                                "bias": bias,
                                                "score": score,
                                                "ltf_trigger": ltf_trigger,
                                                "reason_full": dict(reason_full),
                                                "cfg": cfg,
                                                "threshold": base_threshold,
                                                "state_key": state_key,
                                                "is_dca": True,
                                                "timings": dict(timings)
                                            })

                if status not in ("FIRED", "DCA_FIRED"):
                    local_updates.append({
                        "symbol": generic,
                        "resolved": resolved,
                        "bias": bias,
                        "score": score,
                        "status": status,
                        "reason": reason_full,
                        "updated_at": datetime.now(pytz.utc).isoformat()
                    })
                    
                return local_candidates, local_updates

            scan_concurrency = int(cfg.get("scan_concurrency", 5))
            sem = asyncio.Semaphore(scan_concurrency)
            
            async def bounded_scan(generic):
                async with sem:
                    return await scan_symbol(generic)
                    
            scan_results = await asyncio.gather(*(bounded_scan(sym) for sym in symbols))
            
            candidates = []
            updates_to_broadcast = []
            for c_list, u_list in scan_results:
                candidates.extend(c_list)
                updates_to_broadcast.extend(u_list)

            # --- CANDIDATE RANKING ---
            dca_candidates = [c for c in candidates if c.get("is_dca")]
            normal_candidates = [c for c in candidates if not c.get("is_dca")]
            
            dca_candidates.sort(key=lambda x: x["score"], reverse=True)
            normal_candidates.sort(key=lambda x: x["score"], reverse=True)
            
            max_dca_per_scan = int(cfg.get("max_dca_per_scan", 2))
            
            selected_dca = dca_candidates[:max_dca_per_scan]
            
            selected_normal = []
            groups_used_this_scan = set()
            for c in normal_candidates:
                if len(selected_normal) >= max_signals_per_scan:
                    break
                my_group = generic_to_group.get(c["generic"])
                if correlation_groups_enabled and my_group and my_group in enabled_correlation_groups:
                    if my_group in groups_used_this_scan:
                        c["status"] = "SKIPPED"
                        c["reason_full"]["msg"] = f"Skipped: higher score candidate from group '{my_group}' selected"
                        continue
                    groups_used_this_scan.add(my_group)
                selected_normal.append(c)
                
            selected_candidates = selected_dca + selected_normal
            selected_symbols_dca = {c["resolved"] for c in selected_dca}
            selected_symbols_normal = {c["resolved"] for c in selected_normal}
            
            for c in candidates:
                res = c["resolved"]
                generic = c["generic"]
                bias = c["bias"]
                score = c["score"]
                ltf_trigger = c["ltf_trigger"]
                reason_full = c["reason_full"]
                state_key = c["state_key"]
                
                is_dca = c.get("is_dca", False)
                
                # Check if it was selected based on its list
                if (is_dca and res in selected_symbols_dca) or (not is_dca and res in selected_symbols_normal):
                    status = "DCA_FIRED" if is_dca else "FIRED"
                    if is_dca:
                        reason_full["msg"] = f"DCA Executed! Rank 1 (Score: {score})"
                    else:
                        reason_full["msg"] = f"Executed! Rank 1 (Score: {score})"
                    scanner_state[state_key] = {"time": now_utc, "status": status}
                    
                    updates_to_broadcast.append({
                        "symbol": generic, "resolved": res, "bias": bias, "score": score,
                        "status": status, "reason": reason_full, "updated_at": datetime.now(pytz.utc).isoformat()
                    })
                    
                    async with AsyncSessionLocal() as db:
                        sig = Signal(symbol=res, direction=bias, score=score, htf_bias=bias, 
                                    entry=ltf_trigger['entry'], sl=ltf_trigger['sl'], tp=ltf_trigger['tp'],
                                    reason=reason_full, status=status)
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
                        
                        c["timings"]["signal_saved"] = time.time() * 1000
                        from app.engine.order_manager import send_order
                        await send_order(sig, res, bias, c["cfg"], is_dca=is_dca, dca_data=ltf_trigger if is_dca else None, timings=c.get("timings"))
                else:
                    is_dca = c.get("is_dca", False)
                    status = c.get("status", "DCA_SKIPPED" if is_dca else "SKIPPED")
                    if not ("Skipped: higher score candidate from group" in c["reason_full"].get("msg", "")):
                        reason_full["msg"] = "Skipped because higher-ranked signal selected"
                    
                    updates_to_broadcast.append({
                        "symbol": generic, "resolved": res, "bias": bias, "score": score,
                        "status": status, "reason": reason_full, "updated_at": datetime.now(pytz.utc).isoformat()
                    })

            # Broadcast all states for UI
            for update in updates_to_broadcast:
                await broadcast({"type": "scan.update", "data": update})

            await asyncio.sleep(interval)
        except Exception as e:
            print("Scanner error:", e)
            await asyncio.sleep(5)
