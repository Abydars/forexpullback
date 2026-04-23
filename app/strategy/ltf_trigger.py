import pandas as pd

def find_ltf_trigger(df: pd.DataFrame, zone: dict, bias: str, point: float, reward_ratio: float = 2.0) -> dict | None:
    if len(df) < 5: return None
    
    last = df.iloc[-2]
    
    in_zone = (last['low'] <= zone['zone_high']) and (last['high'] >= zone['zone_low'])
    if not in_zone:
        return None
        
    if bias == 'bullish' and last['close'] > last['open']:
        entry = float(last['close'])
        sl = float(last['low'] - (point * 30))
        tp = entry + (entry - sl) * reward_ratio
        return {"entry": entry, "sl": sl, "tp": tp, "trigger_type": "engulfing", "strength": 80}
        
    if bias == 'bearish' and last['close'] < last['open']:
        entry = float(last['close'])
        sl = float(last['high'] + (point * 30))
        tp = entry - (sl - entry) * reward_ratio
        return {"entry": entry, "sl": sl, "tp": tp, "trigger_type": "engulfing", "strength": 80}
        
    return None
