import pandas as pd

def run_mtf_zones(df: pd.DataFrame, bias: str):
    if df.empty or len(df) < 20:
        return None, 0.0, {"reason": "Not enough data"}
        
    close = df['close'].values
    high = df['high'].values
    low = df['low'].values
    
    atr = pd.Series(high - low).rolling(14).mean().values[-1]
    
    zone = None
    strength = 0.0
    
    if bias == "bullish":
        # Look for FVG down
        for i in range(len(df)-3, len(df)-20, -1):
            if high[i-2] < low[i]:
                zone = {"top": low[i], "bottom": high[i-2]}
                strength = 80.0
                break
    elif bias == "bearish":
        # Look for FVG up
        for i in range(len(df)-3, len(df)-20, -1):
            if low[i-2] > high[i]:
                zone = {"top": low[i-2], "bottom": high[i]}
                strength = 80.0
                break
                
    if zone:
        return zone, strength, {"fvg": zone, "atr": float(atr)}
    return None, 0.0, {"reason": "No FVG found"}
