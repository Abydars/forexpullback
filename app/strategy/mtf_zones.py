import pandas as pd

def find_mtf_zone(df: pd.DataFrame, bias: str) -> dict | None:
    if len(df) < 35: return None
    
    # Scan the last 30 candles for an unmitigated FVG in the direction of the bias
    for i in range(len(df)-3, len(df)-30, -1):
        c1 = df.iloc[i-2]
        c2 = df.iloc[i-1]
        c3 = df.iloc[i]
        
        if bias == 'bullish':
            # Bullish FVG: C1 High < C3 Low and impulsive C2
            if c1['high'] < c3['low'] and c2['close'] > c2['open']:
                fvg_low = c1['high']
                fvg_high = c3['low']
                
                # Check if subsequent candles have fully mitigated (filled) the FVG
                subsequent = df.iloc[i+1:]
                if not subsequent.empty and subsequent['low'].min() <= fvg_low:
                    continue # Fully filled
                    
                return {
                    "zone_high": float(fvg_high),
                    "zone_low": float(fvg_low),
                    "quality": 90,
                    "reason": {"type": "Bullish FVG", "fvg": True, "age_candles": len(df) - i}
                }
                
        elif bias == 'bearish':
            # Bearish FVG: C1 Low > C3 High and impulsive C2
            if c1['low'] > c3['high'] and c2['close'] < c2['open']:
                fvg_high = c1['low']
                fvg_low = c3['high']
                
                # Check if fully mitigated
                subsequent = df.iloc[i+1:]
                if not subsequent.empty and subsequent['high'].max() >= fvg_high:
                    continue
                    
                return {
                    "zone_high": float(fvg_high),
                    "zone_low": float(fvg_low),
                    "quality": 90,
                    "reason": {"type": "Bearish FVG", "fvg": True, "age_candles": len(df) - i}
                }
                
    # FALLBACK: If no FVG is found, we use a Dynamic EMA Pullback Zone
    # Standard pullbacks often bounce between the 20 and 50 EMA in a trending market.
    df_copy = df.copy()
    df_copy['ema20'] = df_copy['close'].ewm(span=20, adjust=False).mean()
    df_copy['ema50'] = df_copy['close'].ewm(span=50, adjust=False).mean()
    
    # Use the last closed candle to prevent repainting
    last_closed = df_copy.iloc[-2]
    
    if bias == 'bullish' and last_closed['ema20'] > last_closed['ema50']:
        return {
            "zone_high": float(last_closed['ema20']),
            "zone_low": float(last_closed['ema50']),
            "quality": 75, # Lower quality than FVG, but valid
            "reason": {"type": "EMA Dynamic Support", "fvg": False}
        }
    elif bias == 'bearish' and last_closed['ema20'] < last_closed['ema50']:
        return {
            "zone_high": float(last_closed['ema50']),
            "zone_low": float(last_closed['ema20']),
            "quality": 75,
            "reason": {"type": "EMA Dynamic Resistance", "fvg": False}
        }
                
    return None
