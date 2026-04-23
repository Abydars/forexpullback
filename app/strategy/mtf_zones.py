import pandas as pd

def find_mtf_zone(df: pd.DataFrame, bias: str) -> dict | None:
    if len(df) < 50: return None
    
    df['tr'] = pd.concat([
        df['high'] - df['low'],
        (df['high'] - df['close'].shift()).abs(),
        (df['low'] - df['close'].shift()).abs()
    ], axis=1).max(axis=1)
    df['atr'] = df['tr'].rolling(20).mean()
    
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    last_rsi = df['rsi'].iloc[-1]
    
    if bias == 'bullish' and last_rsi < 45:
        return {
            "zone_high": float(df['high'].iloc[-10:].max()),
            "zone_low": float(df['low'].iloc[-10:].min()),
            "quality": 80,
            "reason": {"rsi": float(last_rsi), "fvg": True}
        }
    elif bias == 'bearish' and last_rsi > 55:
        return {
            "zone_high": float(df['high'].iloc[-10:].max()),
            "zone_low": float(df['low'].iloc[-10:].min()),
            "quality": 80,
            "reason": {"rsi": float(last_rsi), "fvg": True}
        }
        
    return None
