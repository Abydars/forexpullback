import MetaTrader5 as mt5
import time
from datetime import datetime

mt5.initialize()
tick = mt5.symbol_info_tick("EURUSD")
if tick:
    print(f"tick.time: {tick.time}")
    print(f"tick.time_msc: {tick.time_msc}")
    print(f"time.time(): {time.time()}")
    print(f"datetime.now().timestamp(): {datetime.now().timestamp()}")
    print(f"Diff seconds: {time.time() - tick.time}")
else:
    print("No tick for EURUSD")
mt5.shutdown()
