import asyncio
import MetaTrader5 as mt5
from datetime import datetime, timedelta
import pytz

mt5.initialize()
# Try fetching from 2 hours ago
utc_dt = datetime.now(pytz.utc) - timedelta(hours=2)
rates = mt5.copy_rates_from("EURUSD", mt5.TIMEFRAME_M5, utc_dt, 10)
print("Using UTC datetime:", len(rates) if rates is not None else None)

# Try fetching using POSIX timestamp
rates2 = mt5.copy_rates_from("EURUSD", mt5.TIMEFRAME_M5, int(utc_dt.timestamp()), 10)
print("Using POSIX timestamp:", len(rates2) if rates2 is not None else None)

mt5.shutdown()
