import pandas as pd

def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def find_ltf_trigger(df: pd.DataFrame, zone: dict, bias: str, point: float, reward_ratio: float = 2.0) -> dict | None:
    if len(df) < 20: return None
    
    df = df.copy()
    df['rsi'] = calculate_rsi(df['close'], 14)
    
    last = df.iloc[-2]
    prev = df.iloc[-3]
    prev2 = df.iloc[-4]
    
    # Soft zone requirement: Price should have touched the zone within the last 3 candles
    in_zone = False
    for i in range(-2, -5, -1):
        c = df.iloc[i]
        if (c['low'] <= zone['zone_high']) and (c['high'] >= zone['zone_low']):
            in_zone = True
            break
            
    if not in_zone:
        return None
        
    strength = 0
    trigger_name = ""
    entry = float(last['close'])
    sl = 0.0
    
    if bias == 'bullish':
        # Engulfing
        is_engulfing = (prev['close'] < prev['open']) and (last['close'] > last['open']) and \
                       (last['close'] > prev['open']) and (last['open'] < prev['close'])
        # Pinbar
        body_size = abs(last['close'] - last['open'])
        lower_wick = min(last['open'], last['close']) - last['low']
        upper_wick = last['high'] - max(last['open'], last['close'])
        is_pinbar = (lower_wick > body_size * 2) and (upper_wick < body_size)
        # Break of previous high (Requires strong body > 35% of candle range)
        candle_range = last['high'] - last['low']
        is_break = (last['close'] > prev['high']) and (body_size > candle_range * 0.35)
        # Liquidity Sweep
        is_sweep = last['low'] < prev['low'] and last['close'] > prev['low']
        
        if is_engulfing:
            strength = 85; trigger_name = "Bullish Engulfing"
        elif is_sweep:
            strength = 80; trigger_name = "Liquidity Sweep"
        elif is_pinbar:
            strength = 75; trigger_name = "Bullish Pinbar"
        elif is_break:
            strength = 65; trigger_name = "Break of High"
            
        if strength > 0:
            # RSI Reclaim bonus
            if last['rsi'] > 45 and prev['rsi'] <= 45:
                strength += 15
                trigger_name += " + RSI Reclaim"
            sl = float(min(last['low'], prev['low'], zone['zone_low']) - (point * 15))
            tp = entry + (entry - sl) * reward_ratio
            return {"entry": entry, "sl": sl, "tp": tp, "trigger_type": trigger_name, "strength": min(100, strength)}
            
    elif bias == 'bearish':
        # Engulfing
        is_engulfing = (prev['close'] > prev['open']) and (last['close'] < last['open']) and \
                       (last['close'] < prev['open']) and (last['open'] > prev['close'])
        # Pinbar
        body_size = abs(last['close'] - last['open'])
        lower_wick = min(last['open'], last['close']) - last['low']
        upper_wick = last['high'] - max(last['open'], last['close'])
        is_pinbar = (upper_wick > body_size * 2) and (lower_wick < body_size)
        # Break of previous low (Requires strong body > 35% of candle range)
        candle_range = last['high'] - last['low']
        is_break = (last['close'] < prev['low']) and (body_size > candle_range * 0.35)
        # Liquidity Sweep
        is_sweep = last['high'] > prev['high'] and last['close'] < prev['high']
        
        if is_engulfing:
            strength = 85; trigger_name = "Bearish Engulfing"
        elif is_sweep:
            strength = 80; trigger_name = "Liquidity Sweep"
        elif is_pinbar:
            strength = 75; trigger_name = "Bearish Pinbar"
        elif is_break:
            strength = 65; trigger_name = "Break of Low"
            
        if strength > 0:
            # RSI Reclaim bonus
            if last['rsi'] < 55 and prev['rsi'] >= 55:
                strength += 15
                trigger_name += " + RSI Reclaim"
            sl = float(max(last['high'], prev['high'], zone['zone_high']) + (point * 15))
            tp = entry - (sl - entry) * reward_ratio
            return {"entry": entry, "sl": sl, "tp": tp, "trigger_type": trigger_name, "strength": min(100, strength)}
            
    return None
