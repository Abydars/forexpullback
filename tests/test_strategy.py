import pytest
import pandas as pd
from datetime import datetime, time
import pytz
from core.sessions import Session, active_sessions
from strategy.htf_bias import run_htf_bias
from strategy.scoring import calculate_score

def test_active_sessions():
    now_utc = datetime(2023, 1, 2, 10, 0, 0, tzinfo=pytz.utc) # Monday 10:00 UTC
    
    # Session: 08:00 - 12:00 UTC, Mon-Fri (mask=31)
    s1 = Session(1, "London", time(8, 0), time(12, 0), "UTC", 31, True)
    assert s1 in active_sessions([s1], now_utc)
    
    # Session: 11:00 - 15:00 UTC
    s2 = Session(2, "NY", time(11, 0), time(15, 0), "UTC", 31, True)
    assert s2 not in active_sessions([s2], now_utc)
    
    # Session: midnight crossing 22:00 - 02:00 UTC
    s3 = Session(3, "Asia", time(22, 0), time(2, 0), "UTC", 31, True)
    assert s3 not in active_sessions([s3], now_utc)
    
    now_midnight = datetime(2023, 1, 2, 23, 0, 0, tzinfo=pytz.utc)
    assert s3 in active_sessions([s3], now_midnight)

def test_scoring():
    score = calculate_score(100.0, 100.0, 100.0, 100.0, 100.0)
    assert score == 100.0
    
    score2 = calculate_score(50.0, 50.0, 50.0, 50.0, 50.0)
    assert score2 == 50.0

def test_htf_bias_bullish():
    dates = pd.date_range(end=pd.Timestamp.now(), periods=250, freq='4h')
    df = pd.DataFrame({
        'time': dates.astype(int) // 10**9,
        'open': [1.0] * 250,
        'high': [1.0] * 250,
        'low': [1.0] * 250,
        'close': [1.0 + (i*0.01) for i in range(250)], # upward trend
        'tick_volume': [100] * 250,
        'spread': [1] * 250,
        'real_volume': [0] * 250
    })
    
    bias, strength, reason = run_htf_bias(df)
    assert bias == "bullish"
    assert strength > 0

def test_htf_bias_bearish():
    dates = pd.date_range(end=pd.Timestamp.now(), periods=250, freq='4h')
    df = pd.DataFrame({
        'time': dates.astype(int) // 10**9,
        'open': [1.0] * 250,
        'high': [1.0] * 250,
        'low': [1.0] * 250,
        'close': [10.0 - (i*0.01) for i in range(250)], # downward trend
        'tick_volume': [100] * 250,
        'spread': [1] * 250,
        'real_volume': [0] * 250
    })
    
    bias, strength, reason = run_htf_bias(df)
    assert bias == "bearish"
    assert strength > 0
    
def test_htf_bias_neutral():
    dates = pd.date_range(end=pd.Timestamp.now(), periods=250, freq='4h')
    df = pd.DataFrame({
        'time': dates.astype(int) // 10**9,
        'open': [1.0] * 250,
        'high': [1.0] * 250,
        'low': [1.0] * 250,
        'close': [1.0] * 250, # flat
        'tick_volume': [100] * 250,
        'spread': [1] * 250,
        'real_volume': [0] * 250
    })
    
    bias, strength, reason = run_htf_bias(df)
    assert bias == "neutral"
