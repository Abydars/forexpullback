import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta

SYMBOL = "USDCHF"

ENTRY = 0.79087
SL = 0.7902134409752182
TP = 0.7920518062446071

START_TIME = datetime(2026, 4, 30, 7, 50)

# connect MT5
mt5.initialize()

# fetch enough candles (important!)
rates = mt5.copy_rates_from(
    SYMBOL,
    mt5.TIMEFRAME_M1,
    START_TIME,
    300  # ~5 hours
)

df = pd.DataFrame(rates)
df['time'] = pd.to_datetime(df['time'], unit='s')

# filter only AFTER signal
df = df[df['time'] >= START_TIME]

result = None

for _, row in df.iterrows():
    high = row['high']
    low = row['low']
    t = row['time']

    print(f"{t} | H:{high} L:{low}")

    # BUY logic
    if low <= SL and high >= TP:
        print(f"AMBIGUOUS @ {t} | High: {high} >= TP: {TP} AND Low: {low} <= SL: {SL}")
        result = "SL HIT (conservative)"
        break
    elif low <= SL:
        print(f"SL HIT @ {t} | Low: {low} <= SL: {SL}")
        result = "SL HIT"
        break
    elif high >= TP:
        print(f"TP HIT @ {t} | High: {high} >= TP: {TP}")
        result = "TP HIT"
        break

print("\nFINAL RESULT:", result)
