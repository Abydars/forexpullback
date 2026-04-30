import MetaTrader5 as mt5
from datetime import datetime
import pandas as pd

mt5.initialize()
tick = mt5.symbol_info_tick("CHFJPY")
if tick:
    broker_naive = datetime.utcfromtimestamp(tick.time)
    system_naive = datetime.now()
    print("Broker Naive:", broker_naive)
    print("System Naive:", system_naive)
    
    offset = system_naive - broker_naive
    print("Offset:", offset)
    
    offset_rounded = pd.Timedelta(seconds=round(offset.total_seconds() / 3600) * 3600)
    print("Rounded Offset:", offset_rounded)

mt5.shutdown()
