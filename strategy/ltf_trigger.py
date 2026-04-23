import pandas as pd

def run_ltf_trigger(df: pd.DataFrame, bias: str, zone: dict):
    if df.empty or len(df) < 5:
        return False, 0.0, 0.0, 0.0, {"reason": "Not enough data"}
        
    close = df['close'].values[-1]
    high = df['high'].values[-1]
    low = df['low'].values[-1]
    
    trigger = False
    entry = 0.0
    sl = 0.0
    strength = 0.0
    
    if bias == "bullish":
        if zone['bottom'] <= low <= zone['top']:
            trigger = True
            entry = close
            sl = zone['bottom'] - (entry * 0.0005)
            strength = 90.0
    elif bias == "bearish":
        if zone['bottom'] <= high <= zone['top']:
            trigger = True
            entry = close
            sl = zone['top'] + (entry * 0.0005)
            strength = 90.0
            
    if trigger:
        return trigger, entry, sl, strength, {"close": float(close)}
    return False, 0.0, 0.0, 0.0, {"reason": "No trigger"}
