import pandas as pd
import numpy as np

def calculate_htf_bias(df_4h: pd.DataFrame, df_1h: pd.DataFrame) -> dict:
    if len(df_4h) < 200 or len(df_1h) < 200:
        return {"bias": "neutral", "strength": 0, "reason": {"msg": "not enough data"}}
        
    df_4h['ema50'] = df_4h['close'].ewm(span=50, adjust=False).mean()
    df_4h['ema200'] = df_4h['close'].ewm(span=200, adjust=False).mean()
    
    df_1h['ema50'] = df_1h['close'].ewm(span=50, adjust=False).mean()
    df_1h['ema200'] = df_1h['close'].ewm(span=200, adjust=False).mean()
    
    # 4H Logic
    c_4h = df_4h['close'].iloc[-2]
    e200_4h = df_4h['ema200'].iloc[-2]
    e50_4h_now = df_4h['ema50'].iloc[-2]
    e50_4h_past = df_4h['ema50'].iloc[-11]
    
    # 1H Logic
    c_1h = df_1h['close'].iloc[-2]
    e200_1h = df_1h['ema200'].iloc[-2]
    e50_1h_now = df_1h['ema50'].iloc[-2]
    e50_1h_past = df_1h['ema50'].iloc[-6]
    
    bias_4h = "neutral"
    if c_4h > e200_4h and e50_4h_now > e50_4h_past: bias_4h = "bullish"
    elif c_4h < e200_4h and e50_4h_now < e50_4h_past: bias_4h = "bearish"
    
    bias_1h = "neutral"
    if c_1h > e200_1h and e50_1h_now > e50_1h_past: bias_1h = "bullish"
    elif c_1h < e200_1h and e50_1h_now < e50_1h_past: bias_1h = "bearish"
    
    bias = bias_4h
    strength = 0
    reason = {"4h": bias_4h, "1h": bias_1h}
    
    if bias_4h == "bullish":
        strength = 80 if bias_1h == "bullish" else 60
    elif bias_4h == "bearish":
        strength = 80 if bias_1h == "bearish" else 60
    
    return {"bias": bias, "strength": strength, "reason": reason}
