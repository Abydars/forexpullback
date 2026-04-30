import pandas as pd

def evaluate_smart_tp_from_candles(
    direction: str,
    entry: float,
    sl: float,
    tp: float,
    candles: pd.DataFrame,
    signal_age_seconds: float
) -> str | None:
    """
    Evaluates Smart TP logic based on historical candles.
    `candles` should be a DataFrame with at least 15 candles ending exactly at the candle being evaluated.
    `signal_age_seconds` is the time elapsed since the signal was created to the end of the current candle.
    Returns a reason string if Smart TP triggers, else None.
    """
    is_buy = str(direction).lower() in ["buy", "bullish"]
    
    # Needs to be in profit to use Smart TP logic
    last_close = candles.iloc[-1]['close']
    profit = (last_close - entry) if is_buy else (entry - last_close)
    if profit <= 0:
        return None
        
    # Minimum trade age (disable smart TP for first 20 mins ~ 4 candles)
    if signal_age_seconds < 20 * 60:
        return None
        
    if len(candles) < 15:
        return None
        
    # Calculate ATR for volatility filter
    df_copy = candles.copy()
    df_copy['tr'] = df_copy['high'] - df_copy['low']
    atr = df_copy['tr'].mean()
    
    # We are evaluating at the CLOSE of the last candle, so we use iloc[-1] as the latest closed candle
    # and iloc[-2] as the previous closed candle.
    last = candles.iloc[-1]
    prev = candles.iloc[-2]
    
    body_last = abs(last['close'] - last['open'])
    range_last = last['high'] - last['low']
    is_strong = body_last > (range_last * 0.4) if range_last > 0 else False
    
    if is_buy:
        if tp and tp > entry:
            tp_dist = tp - entry
            max_reached = max(last['high'], prev['high']) - entry
            
            if max_reached >= tp_dist * 0.8:
                if (last['close'] - entry) <= tp_dist * 0.6:
                    return "Smart TP: Closed below 60% after reaching 80%"
                    
        # Momentum Reversal (Bearish)
        if last['close'] < last['open'] and last['close'] < prev['low']:
            move_size = abs(entry - last['close'])
            if move_size > (0.5 * atr):
                if is_strong or (prev['close'] < prev['open']): # Strong or 2-candle confirmation
                    return "Smart TP: Strong Bearish Reversal Detected"
    else:
        if tp and tp < entry:
            tp_dist = entry - tp
            max_reached = entry - min(last['low'], prev['low'])
            
            if max_reached >= tp_dist * 0.8:
                if (entry - last['close']) <= tp_dist * 0.6:
                    return "Smart TP: Closed below 60% after reaching 80%"
                    
        # Momentum Reversal (Bullish)
        if last['close'] > last['open'] and last['close'] > prev['high']:
            move_size = abs(last['close'] - entry)
            if move_size > (0.5 * atr):
                if is_strong or (prev['close'] > prev['open']):
                    return "Smart TP: Strong Bullish Reversal Detected"
                    
    return None
