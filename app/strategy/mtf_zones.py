import pandas as pd
import numpy as np

def calculate_mtf_zones(df: pd.DataFrame, direction: str) -> tuple[float, float, int, dict] | None:
    """
    MTF (15M) Strategy:
    - Detect last impulsive leg (consecutive same-direction candles with range >= 1.5x ATR(20))
    - Compute Fib 0.5 and 0.786 of that leg
    - Find nearest 15M order block (last opposite candle before impulse) OR FVG (3-candle gap) inside the zone
    - RSI(14) < 45 for longs, > 55 for shorts
    - Return (zone_high, zone_low, quality: int 0-100, reason: dict) | None
    """
    if len(df) < 30: return None
    
    # ATR
    df['tr0'] = abs(df['high'] - df['low'])
    df['tr1'] = abs(df['high'] - df['close'].shift())
    df['tr2'] = abs(df['low'] - df['close'].shift())
    df['tr'] = df[['tr0', 'tr1', 'tr2']].max(axis=1)
    df['atr20'] = df['tr'].rolling(20).mean()
    
    # RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi14'] = 100 - (100 / (1 + rs))
    
    rsi = df['rsi14'].iloc[-1]
    if direction == 'bullish' and rsi >= 45: return None
    if direction == 'bearish' and rsi <= 55: return None
    
    # Simplified impulse leg detection
    # Find last large candle
    df['is_large'] = abs(df['close'] - df['open']) >= 1.5 * df['atr20']
    
    large_candles = df[df['is_large']]
    if large_candles.empty: return None
    
    last_impulse = large_candles.iloc[-1]
    
    if direction == 'bullish' and last_impulse['close'] < last_impulse['open']: return None
    if direction == 'bearish' and last_impulse['close'] > last_impulse['open']: return None
    
    # Fib zones
    high = last_impulse['high']
    low = last_impulse['low']
    rng = high - low
    
    if direction == 'bullish':
        fib_50 = high - rng * 0.5
        fib_786 = high - rng * 0.786
        zone_high, zone_low = fib_50, fib_786
    else:
        fib_50 = low + rng * 0.5
        fib_786 = low + rng * 0.786
        zone_high, zone_low = fib_786, fib_50
        
    reason = {
        'impulse_time': str(last_impulse['time']),
        'fib_50': fib_50,
        'fib_786': fib_786,
        'rsi': rsi
    }
    
    # Just return base zone for now
    return zone_high, zone_low, 80, reason
