import pandas as pd

def run_ltf_trigger(df_5m: pd.DataFrame, bias: str, zone_high: float, zone_low: float, point: float):
    if len(df_5m) < 10:
        return None
        
    # Current candle
    curr = df_5m.iloc[-1]
    prev = df_5m.iloc[-2]
    
    if not (zone_low <= curr['close'] <= zone_high):
        return None
        
    trigger_type = None
    strength = 0.0
    entry = curr['close']
    sl = 0.0
    tp_distance = 0.0
    
    # Check engulfing
    if bias == "bullish":
        if prev['close'] < prev['open'] and curr['close'] > curr['open'] and curr['close'] > prev['open']:
            trigger_type = "engulfing"
            strength = 85.0
            sl = min(curr['low'], prev['low']) - (point * 30)
            tp_distance = entry - sl
    else:
        if prev['close'] > prev['open'] and curr['close'] < curr['open'] and curr['close'] < prev['open']:
            trigger_type = "engulfing"
            strength = 85.0
            sl = max(curr['high'], prev['high']) + (point * 30)
            tp_distance = sl - entry
            
    if trigger_type:
        tp = entry + tp_distance * 2.0 if bias == "bullish" else entry - tp_distance * 2.0
        return (entry, sl, tp, trigger_type, strength)
        
    return None
