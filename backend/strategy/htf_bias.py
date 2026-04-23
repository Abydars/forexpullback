import pandas as pd
import numpy as np

def calculate_ema(prices: pd.Series, period: int) -> pd.Series:
    return prices.ewm(span=period, adjust=False).mean()

def calculate_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()

def calculate_rsi(prices: pd.Series, period: int) -> pd.Series:
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def run_htf_bias(df_4h: pd.DataFrame):
    if len(df_4h) < 200:
        return "neutral", 0.0, {"reason": "Not enough 4H bars"}
        
    close = df_4h['close']
    ema50 = calculate_ema(close, 50)
    ema200 = calculate_ema(close, 200)
    
    curr_close = close.iloc[-1]
    curr_ema50 = ema50.iloc[-1]
    prev10_ema50 = ema50.iloc[-11]
    curr_ema200 = ema200.iloc[-1]
    
    bias = "neutral"
    strength = 0.0
    reason = {}
    
    if curr_close > curr_ema200 and curr_ema50 > prev10_ema50:
        bias = "bullish"
        strength = min(100.0, ((curr_ema50 - prev10_ema50) / curr_ema50) * 100000)
        reason = {"ema200": "above", "ema50_slope": "positive"}
    elif curr_close < curr_ema200 and curr_ema50 < prev10_ema50:
        bias = "bearish"
        strength = min(100.0, ((prev10_ema50 - curr_ema50) / curr_ema50) * 100000)
        reason = {"ema200": "below", "ema50_slope": "negative"}
        
    return bias, strength, reason
