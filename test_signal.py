import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta, timezone

SYMBOL = "USDCHF"

ENTRY = 0.79087
SL = 0.7902134409752182
TP = 0.7920518062446071

CREATED_AT_UTC = datetime(2026, 4, 30, 7, 50, tzinfo=timezone.utc)
REPLAY_START_UTC = CREATED_AT_UTC + timedelta(minutes=1)

# Conservative TP buffer
# USDCHF spread was around 2 points = 0.00002
SPREAD_PRICE = 0.00002
TP_BUFFER = SPREAD_PRICE * 1.5

mt5.initialize()

rates = mt5.copy_rates_range(
    SYMBOL,
    mt5.TIMEFRAME_M1,
    CREATED_AT_UTC - timedelta(minutes=5),
    CREATED_AT_UTC + timedelta(hours=5)
)

df = pd.DataFrame(rates)
df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)

df = df[df["time"] >= pd.Timestamp(REPLAY_START_UTC)]

print(f"Replay starting from: {REPLAY_START_UTC}")
print(f"Entry: {ENTRY}")
print(f"SL: {SL}")
print(f"TP: {TP}")
print(f"TP effective with buffer: {TP + TP_BUFFER}\n")

result = None

for _, row in df.iterrows():
    high = row["high"]
    low = row["low"]
    spread_points = row.get("spread", None)
    t = row["time"]

    print(f"{t} | H:{high:.5f} L:{low:.5f} Spread:{spread_points}")

    # BUY signal logic
    if low <= SL:
        result = "SL HIT"
        print(f"SL HIT @ {t}")
        break

    elif high >= (TP + TP_BUFFER):
        result = "TP HIT"
        print(f"TP HIT @ {t}")
        break

    elif high >= TP:
        print(f"TP touched but ignored due to buffer @ {t}")

print("\nFINAL RESULT:", result)