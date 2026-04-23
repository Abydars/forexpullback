import pandas as pd
import numpy as np

def calculate_htf_bias(df: pd.DataFrame) -> dict:
    if len(df) < 200:
        return {"bias": "neutral", "strength": 0, "reason": {"msg": "not enough data"}}
        
    df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['ema200'] = df['close'].ewm(span=200, adjust=False).mean()
    
    close = df['close'].iloc[-1]
    ema200 = df['ema200'].iloc[-1]
    ema50_now = df['ema50'].iloc[-1]
    ema50_past = df['ema50'].iloc[-10]
    
    bias = "neutral"
    strength = 0
    reason = {}
    
    if close > ema200 and ema50_now > ema50_past:
        bias = "bullish"
        strength = 70
        reason = {"trend": "bullish", "ema_slope": "up"}
    elif close < ema200 and ema50_now < ema50_past:
        bias = "bearish"
        strength = 70
        reason = {"trend": "bearish", "ema_slope": "down"}
        
    return {"bias": bias, "strength": strength, "reason": reason}
