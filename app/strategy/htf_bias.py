import pandas as pd
import numpy as np

def calculate_htf_bias(df: pd.DataFrame) -> tuple[str, int, dict]:
    """
    HTF (4H) Strategy:
    - EMA50, EMA200
    - Bias = bullish if close > EMA200 and EMA50[now] > EMA50[-10]; inverse for bearish
    - Require BOS: last 5-bar pivot high broken for bullish, pivot low broken for bearish
    - Return (bias: str, strength: int 0-100, reason: dict)
    """
    if len(df) < 200:
        return 'neutral', 0, {"error": "not enough data"}
        
    df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['ema200'] = df['close'].ewm(span=200, adjust=False).mean()
    
    current = df.iloc[-1]
    past10 = df.iloc[-11]
    
    # Calculate pivots for BOS (Break of Structure)
    # simplified pivot: max/min over window of 5
    df['pivot_high'] = df['high'].rolling(window=5, center=True).max()
    df['pivot_low'] = df['low'].rolling(window=5, center=True).min()
    
    # Forward fill to get last established pivot
    df['last_pivot_high'] = df['pivot_high'].ffill()
    df['last_pivot_low'] = df['pivot_low'].ffill()
    
    last_ph = df['last_pivot_high'].iloc[-6] # use slightly lagged to ensure it's established
    last_pl = df['last_pivot_low'].iloc[-6]
    
    is_bullish = current['close'] > current['ema200'] and current['ema50'] > past10['ema50']
    is_bearish = current['close'] < current['ema200'] and current['ema50'] < past10['ema50']
    
    bos_bullish = current['close'] > last_ph
    bos_bearish = current['close'] < last_pl
    
    bias = 'neutral'
    strength = 0
    reason = {
        'close': current['close'],
        'ema50': current['ema50'],
        'ema200': current['ema200'],
        'bos_bullish': bool(bos_bullish),
        'bos_bearish': bool(bos_bearish)
    }
    
    if is_bullish and bos_bullish:
        bias = 'bullish'
        strength = min(100, int((current['close'] - current['ema200']) / current['ema200'] * 10000)) # dummy strength calc
    elif is_bearish and bos_bearish:
        bias = 'bearish'
        strength = min(100, int((current['ema200'] - current['close']) / current['ema200'] * 10000))

    return bias, strength, reason
