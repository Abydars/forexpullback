import pandas as pd

def find_ltf_trigger(df: pd.DataFrame, zone: dict, bias: str, point: float, reward_ratio: float = 2.0) -> dict | None:
    if len(df) < 5: return None
    
    last = df.iloc[-2]
    prev = df.iloc[-3]
    
    # Ensure price is mitigating the MTF zone
    in_zone = (last['low'] <= zone['zone_high']) and (last['high'] >= zone['zone_low'])
    if not in_zone:
        return None
        
    # Bullish Triggers
    if bias == 'bullish':
        # Bullish Engulfing: Prev red, Last green, Last body engulfs Prev body
        is_engulfing = (prev['close'] < prev['open']) and (last['close'] > last['open']) and \
                       (last['close'] > prev['open']) and (last['open'] < prev['close'])
                       
        # Bullish Pinbar: Long lower wick, small body at the top
        body_size = abs(last['close'] - last['open'])
        lower_wick = min(last['open'], last['close']) - last['low']
        upper_wick = last['high'] - max(last['open'], last['close'])
        is_pinbar = (lower_wick > body_size * 2) and (upper_wick < body_size)
        
        if is_engulfing or is_pinbar:
            entry = float(last['close'])
            # Place SL below the lowest point of the trigger or zone
            sl = float(min(last['low'], prev['low'], zone['zone_low']) - (point * 15))
            tp = entry + (entry - sl) * reward_ratio
            trigger_name = "Bullish Engulfing" if is_engulfing else "Bullish Pinbar"
            return {"entry": entry, "sl": sl, "tp": tp, "trigger_type": trigger_name, "strength": 85}
            
    # Bearish Triggers
    elif bias == 'bearish':
        # Bearish Engulfing: Prev green, Last red, Last body engulfs Prev body
        is_engulfing = (prev['close'] > prev['open']) and (last['close'] < last['open']) and \
                       (last['close'] < prev['open']) and (last['open'] > prev['close'])
                       
        # Bearish Pinbar: Long upper wick, small body at the bottom
        body_size = abs(last['close'] - last['open'])
        lower_wick = min(last['open'], last['close']) - last['low']
        upper_wick = last['high'] - max(last['open'], last['close'])
        is_pinbar = (upper_wick > body_size * 2) and (lower_wick < body_size)
        
        if is_engulfing or is_pinbar:
            entry = float(last['close'])
            sl = float(max(last['high'], prev['high'], zone['zone_high']) + (point * 15))
            tp = entry - (sl - entry) * reward_ratio
            trigger_name = "Bearish Engulfing" if is_engulfing else "Bearish Pinbar"
            return {"entry": entry, "sl": sl, "tp": tp, "trigger_type": trigger_name, "strength": 85}
            
    return None
