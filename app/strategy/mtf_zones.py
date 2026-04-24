import pandas as pd

def find_mtf_zone(df: pd.DataFrame, bias: str) -> dict | None:
    if len(df) < 35: return None
    
    df_copy = df.copy()
    df_copy['ema20'] = df_copy['close'].ewm(span=20, adjust=False).mean()
    df_copy['ema50'] = df_copy['close'].ewm(span=50, adjust=False).mean()
    
    last_closed = df_copy.iloc[-2]
    
    zone_high = 0.0
    zone_low = 0.0
    quality = 0
    zone_type = "None"
    
    if bias == 'bullish' and last_closed['ema20'] > last_closed['ema50']:
        zone_high = float(last_closed['ema20'])
        zone_low = float(last_closed['ema50'])
        quality = 70
        zone_type = "EMA Pullback Zone"
    elif bias == 'bearish' and last_closed['ema20'] < last_closed['ema50']:
        zone_high = float(last_closed['ema50'])
        zone_low = float(last_closed['ema20'])
        quality = 70
        zone_type = "EMA Pullback Zone"
    else:
        return None
        
    # Check for FVG bonus in the last 30 candles
    fvg_bonus = False
    for i in range(len(df)-3, len(df)-30, -1):
        c1 = df.iloc[i-2]
        c2 = df.iloc[i-1]
        c3 = df.iloc[i]
        
        if bias == 'bullish' and c1['high'] < c3['low'] and c2['close'] > c2['open']:
            fvg_low = c1['high']
            subsequent = df.iloc[i+1:]
            if subsequent.empty or subsequent['low'].min() > fvg_low:
                fvg_bonus = True
                break
                
        elif bias == 'bearish' and c1['low'] > c3['high'] and c2['close'] < c2['open']:
            fvg_high = c1['low']
            subsequent = df.iloc[i+1:]
            if subsequent.empty or subsequent['high'].max() < fvg_high:
                fvg_bonus = True
                break

    if fvg_bonus:
        quality += 20
        zone_type += " + Unmitigated FVG"
        
    return {
        "zone_high": zone_high,
        "zone_low": zone_low,
        "quality": quality,
        "reason": {"type": zone_type, "fvg_bonus": fvg_bonus}
    }
