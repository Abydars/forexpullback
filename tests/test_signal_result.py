import pytest
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.api.signals_routes import detect_signal_result, next_closed_m1_open_time
import pandas as pd
from datetime import datetime, timezone

def test_next_closed_m1_open_time():
    dt = datetime(2026, 4, 30, 14, 26, 3, tzinfo=timezone.utc)
    res = next_closed_m1_open_time(dt)
    assert res.hour == 14
    assert res.minute == 27
    assert res.second == 0
    
    dt_exact = datetime(2026, 4, 30, 14, 27, 0, tzinfo=timezone.utc)
    res2 = next_closed_m1_open_time(dt_exact)
    assert res2.minute == 27
    assert res2.second == 0

def test_detect_buy_tp():
    # Buy TP only: high >= effective TP, low > effective SL => TP HIT
    res = detect_signal_result("buy", 10.0, 5.0, 4.0, 4.0, 2.0, 9.0, 0, 1.5, 0.0, "conservative")
    assert res["result"] == "TP HIT"
    assert res["both_touched"] is False

def test_detect_buy_sl():
    # Buy SL only: low <= effective SL, high < effective TP => SL HIT
    res = detect_signal_result("buy", 8.0, 1.0, 4.0, 4.0, 2.0, 9.0, 0, 1.5, 0.0, "conservative")
    assert res["result"] == "SL HIT"

def test_detect_sell_tp():
    # Sell TP only: low <= effective TP, high < effective SL => TP HIT
    res = detect_signal_result("sell", 5.0, 1.0, 6.0, 6.0, 8.0, 2.0, 0, 1.5, 0.0, "conservative")
    assert res["result"] == "TP HIT"

def test_detect_sell_sl():
    # Sell SL only: high >= effective SL, low > effective TP => SL HIT
    res = detect_signal_result("sell", 9.0, 4.0, 6.0, 6.0, 8.0, 2.0, 0, 1.5, 0.0, "conservative")
    assert res["result"] == "SL HIT"

def test_same_candle_conservative():
    # Buy, both hit
    res = detect_signal_result("buy", 10.0, 1.0, 4.0, 4.0, 2.0, 9.0, 0, 1.5, 0.0, "conservative")
    assert res["both_touched"] is True
    assert res["result"] == "SL HIT"

def test_same_candle_optimistic():
    res = detect_signal_result("buy", 10.0, 1.0, 4.0, 4.0, 2.0, 9.0, 0, 1.5, 0.0, "optimistic")
    assert res["result"] == "TP HIT"

def test_same_candle_ignore():
    res = detect_signal_result("buy", 10.0, 1.0, 4.0, 4.0, 2.0, 9.0, 0, 1.5, 0.0, "ignore")
    assert res["result"] is None

def test_same_candle_nearest_open():
    # Entry at 4.0. Open at 3.0. SL is 2.0 (dist 1.0). TP is 9.0 (dist 6.0).
    # Since open is closer to SL, it should hit SL.
    res1 = detect_signal_result("buy", 10.0, 1.0, 3.0, 4.0, 2.0, 9.0, 0, 1.5, 0.0, "nearest_open")
    assert res1["result"] == "SL HIT"
    
    # Open at 8.0. TP is 9.0 (dist 1.0). SL is 2.0 (dist 6.0). Closer to TP.
    res2 = detect_signal_result("buy", 10.0, 1.0, 8.0, 4.0, 2.0, 9.0, 0, 1.5, 0.0, "nearest_open")
    assert res2["result"] == "TP HIT"
