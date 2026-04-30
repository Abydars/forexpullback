import asyncio
from datetime import datetime, timedelta, timezone
import MetaTrader5 as mt5
import pandas as pd
import sys
import os

# Ensure the app context is available
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
from app.api.signals_routes import next_closed_m1_open_time, detect_signal_result

async def run_test():
    SYMBOL = "CHFJPY"
    DIRECTION = "sell"
    ENTRY = 200.335
    SL = 201.463
    TP = 198.304
    
    # 07:25:03 PM PKT = 14:25:03 UTC
    SIGNAL_TIME = datetime(2026, 4, 30, 14, 25, 3, tzinfo=timezone.utc)
    
    print(f"--- Testing {SYMBOL} {DIRECTION.upper()} ---")
    print(f"Signal Time: {SIGNAL_TIME} UTC")
    print(f"Entry: {ENTRY} | SL: {SL} | TP: {TP}")

    if not mt5.initialize():
        print("MT5 initialize failed")
        return

    # Calculate exact date range (like check_results)
    now_dt = datetime.now(timezone.utc)
    date_from = SIGNAL_TIME - timedelta(minutes=2)
    date_to = now_dt + timedelta(minutes=2)

    rates = mt5.copy_rates_range(SYMBOL, mt5.TIMEFRAME_M1, date_from, date_to)
    if rates is None or len(rates) == 0:
        print("No candles fetched.")
        mt5.shutdown()
        return

    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)
    df = df.sort_values("time").drop_duplicates("time").reset_index(drop=True)

    # Calculate replay start
    replay_start = next_closed_m1_open_time(SIGNAL_TIME)
    print(f"Replay Start Time: {replay_start} UTC")

    future_df = df[df['time'] >= pd.Timestamp(replay_start)]
    
    if future_df.empty:
        print("No future candles available for replay.")
        mt5.shutdown()
        return

    print("\nStarting Replay:")
    res = None
    
    # Defaults config values as seen in the app
    tp_buffer_mult = 1.5
    sl_buffer_mult = 0.0
    same_candle_policy = "conservative"
    
    info = mt5.symbol_info(SYMBOL)
    tick = mt5.symbol_info_tick(SYMBOL)

    for idx, row in future_df.iterrows():
        if row['time'] > now_dt:
            continue
            
        t = row['time']
        high = row['high']
        low = row['low']
        open_price = row['open']
        spread_val = row['spread']
        
        point = info.point if info else 0.00001
        spread_price = spread_val * point if spread_val else 0.0
        
        # Eff TP/SL for display logging
        if DIRECTION == "sell":
            eff_tp = TP - (spread_price * tp_buffer_mult)
            eff_sl = SL + (spread_price * sl_buffer_mult)
        else:
            eff_tp = TP + (spread_price * tp_buffer_mult)
            eff_sl = SL - (spread_price * sl_buffer_mult)
            
        print(f"[{t}] O: {open_price:.3f} | H: {high:.3f} | L: {low:.3f} | C: {row['close']:.3f} | Spread: {spread_price:.3f} (EffTP: {eff_tp:.3f}, EffSL: {eff_sl:.3f})")

        detection = detect_signal_result(
            direction=DIRECTION,
            high=high,
            low=low,
            open_price=open_price,
            entry=ENTRY,
            sl=SL,
            tp=TP,
            spread_price=spread_price,
            tp_buffer_mult=tp_buffer_mult,
            sl_buffer_mult=sl_buffer_mult,
            same_candle_policy=same_candle_policy
        )

        if detection["result"]:
            res = detection["result"]
            print(f">>> {res} DETECTED AT {t} <<<")
            if detection["both_touched"]:
                print(">>> WARNING: BOTH SL AND TP TOUCHED IN SAME CANDLE <<<")
            break

    if not res:
        print(">>> IN PROGRESS (No TP or SL Hit yet) <<<")

    mt5.shutdown()

if __name__ == "__main__":
    asyncio.run(run_test())
