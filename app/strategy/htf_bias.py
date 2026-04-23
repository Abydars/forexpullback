import pandas as pd
import numpy as np

def calculate_htf_bias(df: pd.DataFrame) -> dict:
    if len(df) < 200:
        return {"bias": "neutral", "strength": 0, "reason": {"msg": "not enough data"}}
        
    df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['ema200'] = df['close'].ewm(span=200, adjust=False).mean()
    
    # Use iloc[-2] to rely on the last completely closed 4H candle and prevent repainting
    close = df['close'].iloc[-2]
    ema200 = df['ema200'].iloc[-2]
    ema50_now = df['ema50'].iloc[-2]
    ema50_past = df['ema50'].iloc[-11]
    
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
