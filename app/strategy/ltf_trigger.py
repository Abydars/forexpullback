import pandas as pd

def calculate_ltf_trigger(df: pd.DataFrame, zone_high: float, zone_low: float, direction: str, point: float, reward_ratio: float) -> tuple[float, float, float, str, int] | None:
    """
    LTF (5M) Strategy:
    - Price inside the 15M zone
    - Fire on CHoCH (5M micro-swing broken) OR engulfing rejection of the zone
    - Entry = trigger candle close
    - SL = wick + 3 pips (use point * 30, adjust for digits)
    - TP = Entry +/- (|Entry - SL|) * R
    - Return (entry, sl, tp, trigger_type, strength: int 0-100) | None
    """
    if len(df) < 5: return None
    
    current = df.iloc[-1]
    prev = df.iloc[-2]
    
    # Check if inside zone
    in_zone = zone_low <= current['close'] <= zone_high
    if not in_zone: return None
    
    # Engulfing rejection
    engulfing = False
    if direction == 'bullish':
        engulfing = prev['close'] < prev['open'] and current['close'] > current['open'] and current['close'] > prev['open'] and current['open'] < prev['close']
    else:
        engulfing = prev['close'] > prev['open'] and current['close'] < current['open'] and current['close'] < prev['open'] and current['open'] > prev['close']
        
    if not engulfing: return None
    
    entry = current['close']
    pip_adj = point * 30 # 3 pips
    
    if direction == 'bullish':
        sl = min(current['low'], prev['low']) - pip_adj
        risk = entry - sl
        tp = entry + risk * reward_ratio
    else:
        sl = max(current['high'], prev['high']) + pip_adj
        risk = sl - entry
        tp = entry - risk * reward_ratio
        
    return entry, sl, tp, 'engulfing', 85
