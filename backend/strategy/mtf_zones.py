import pandas as pd
from backend.strategy.htf_bias import calculate_atr, calculate_rsi

def run_mtf_zones(df_15m: pd.DataFrame, bias: str):
    if len(df_15m) < 50:
        return None
        
    atr = calculate_atr(df_15m['high'], df_15m['low'], df_15m['close'], 20)
    curr_atr = atr.iloc[-1]
    
    rsi = calculate_rsi(df_15m['close'], 14)
    curr_rsi = rsi.iloc[-1]
    
    if bias == "bullish" and curr_rsi >= 45:
        return None
    if bias == "bearish" and curr_rsi <= 55:
        return None
        
    # Find last impulse leg. Simplified logic for the sake of the exercise
    highs = df_15m['high'].values
    lows = df_15m['low'].values
    closes = df_15m['close'].values
    
    # Just find recent highest/lowest over last 20 bars
    last_20 = df_15m.iloc[-20:]
    highest = last_20['high'].max()
    lowest = last_20['low'].min()
    
    impulse_range = highest - lowest
    if impulse_range < 1.5 * curr_atr:
        return None # not impulsive enough
        
    if bias == "bullish":
        fib_05 = highest - (impulse_range * 0.5)
        fib_786 = highest - (impulse_range * 0.786)
        zone_high = fib_05
        zone_low = fib_786
    else:
        fib_05 = lowest + (impulse_range * 0.5)
        fib_786 = lowest + (impulse_range * 0.786)
        zone_high = fib_786
        zone_low = fib_05
        
    # Check if current price is in zone
    curr_close = closes[-1]
    if zone_low <= curr_close <= zone_high:
        quality = 80.0 # Mock quality based on FVG/OB presence
        return (zone_high, zone_low, quality, {"rsi": curr_rsi, "fib": True})
        
    return None
