import pytest
from datetime import time, datetime
import pytz
import pandas as pd
import numpy as np

from app.binance_client.symbol_resolver import SymbolResolver
from app.core.sessions import Session, active_sessions
from app.strategy.htf_bias import calculate_htf_bias
from app.strategy.scoring import calculate_score

class MockBinance:
    pass

@pytest.mark.asyncio
async def test_symbol_resolver():
    resolver = SymbolResolver(MockBinance())
    assert resolver.resolve("btcUsdt") == "BTCUSDT"
    assert resolver.resolve("ethusdt") == "ETHUSDT"
    assert resolver.resolve("xrpusdt") == "XRPUSDT"

def test_active_sessions():
    s1 = Session(id=1, name="Normal", start_time=time(8, 0), end_time=time(16, 0), timezone="UTC", days_mask=127, enabled=True)
    s2 = Session(id=2, name="Midnight", start_time=time(22, 0), end_time=time(2, 0), timezone="UTC", days_mask=127, enabled=True)
    
    now1 = datetime(2023, 1, 1, 10, 0, tzinfo=pytz.utc)
    active1 = active_sessions([s1, s2], now1)
    assert len(active1) == 1 and active1[0].name == "Normal"
    
    now2 = datetime(2023, 1, 1, 23, 0, tzinfo=pytz.utc)
    active2 = active_sessions([s1, s2], now2)
    assert len(active2) == 1 and active2[0].name == "Midnight"
    
def test_htf_bias():
    df_4h = pd.DataFrame({'close': [1,2,3]})
    df_1h = pd.DataFrame({'close': [1,2,3]})
    assert calculate_htf_bias(df_4h, df_1h)['bias'] == 'neutral'
    
    df_4h = pd.DataFrame({'close': np.linspace(100, 200, 250), 'high': np.linspace(101, 201, 250), 'low': np.linspace(99, 199, 250)})
    df_1h = pd.DataFrame({'close': np.linspace(100, 200, 250), 'high': np.linspace(101, 201, 250), 'low': np.linspace(99, 199, 250)})
    assert calculate_htf_bias(df_4h, df_1h)['bias'] == 'bullish'
    
    df_4h = pd.DataFrame({'close': np.linspace(200, 100, 250), 'high': np.linspace(201, 101, 250), 'low': np.linspace(199, 99, 250)})
    df_1h = pd.DataFrame({'close': np.linspace(200, 100, 250), 'high': np.linspace(201, 101, 250), 'low': np.linspace(199, 99, 250)})
    assert calculate_htf_bias(df_4h, df_1h)['bias'] == 'bearish'

def test_scoring():
    score = calculate_score(100, 100, 100, True)
    assert score == int(100*0.3 + 100*0.25 + 100*0.15 + 100*0.20 + 100*0.10)
    
    score_inactive = calculate_score(100, 100, 100, False)
    assert score_inactive == int(100*0.3 + 100*0.25 + 100*0.15 + 100*0.20 + 0)

def test_order_sizing():
    balance = 10000
    risk_pct = 1.0
    sl_points = 500
    tick_value = 1.0
    min_vol = 0.01
    max_vol = 100.0
    step = 0.01
    
    lot = (balance * risk_pct / 100) / (sl_points * tick_value)
    lot = max(min_vol, min(max_vol, round(lot / step) * step))
    assert lot == 0.2
