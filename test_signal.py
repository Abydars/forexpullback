import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta

SYMBOL = "USDCHF"

ENTRY = 0.79087
SL = 0.7902134409752182
TP = 0.7920518062446071

CREATED_AT = datetime(2026, 4, 30, 7, 50)

# 🔥 IMPORTANT FIX
REPLAY_START = CREATED_AT + timedelta(minutes=1)

mt5.initialize()

rates = mt5.copy_rates_from(
    SYMBOL,
    mt5.TIMEFRAME_M1,
    CREATED_AT - timedelta(minutes=2),  # small buffer
    300
)

df = pd.DataFrame(rates)
df['time'] = pd.to_datetime(df['time'], unit='s')

# DEBUG: show first few candles
print("\n--- RAW DATA ---")
print(df.head(5))

# 🔥 IMPORTANT FILTER
df = df[df['time'] >= REPLAY_START]

print(f"\nReplay starting from: {REPLAY_START}\n")

result = None

for _, row in df.iterrows():
    high = row['high']
    low = row['low']
    t = row['time']

    print(f"{t} | H:{high:.5f} L:{low:.5f}")

    # BUY logic
    if low <= SL and high >= TP:
        print(f"AMBIGUOUS @ {t}")
        result = "SL HIT (conservative)"
        break
    elif low <= SL:
        print(f"SL HIT @ {t}")
        result = "SL HIT"
        break
    elif high >= TP:
        print(f"TP HIT @ {t}")
        result = "TP HIT"
        break

print("\nFINAL RESULT:", result)