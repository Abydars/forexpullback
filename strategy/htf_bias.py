import pandas as pd
import numpy as np

def run_htf_bias(df: pd.DataFrame):
    if df.empty or len(df) < 50:
        return "neutral", 0.0, {"reason": "Not enough data"}
        
    close = df['close'].values
    
    ema50 = pd.Series(close).ewm(span=50, adjust=False).mean().values
    
    curr_ema50 = ema50[-1]
    prev10_ema50 = ema50[-10]
    
    if curr_ema50 > prev10_ema50:
        bias = "bullish"
        strength = min(100.0, ((curr_ema50 - prev10_ema50) / abs(prev10_ema50)) * 100000)
    elif curr_ema50 < prev10_ema50:
        bias = "bearish"
        strength = min(100.0, ((prev10_ema50 - curr_ema50) / abs(prev10_ema50)) * 100000)
    else:
        bias = "neutral"
        strength = 0.0
        
    return bias, strength, {"ema50_diff": float(curr_ema50 - prev10_ema50)}
