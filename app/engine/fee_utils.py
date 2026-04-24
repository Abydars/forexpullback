def get_active_fee_rate(cfg: dict) -> float:
    use_taker = cfg.get("use_taker_fee_for_planning", True)
    if use_taker:
        return float(cfg.get("taker_fee_rate", 0.0004))
    return float(cfg.get("maker_fee_rate", 0.0002))

def estimate_fee(notional: float, fee_rate: float) -> float:
    return abs(notional) * fee_rate

def estimate_round_trip_fee(entry_price: float, exit_price: float, qty: float, fee_rate: float) -> float:
    entry_fee = entry_price * qty * fee_rate
    exit_fee = exit_price * qty * fee_rate
    return entry_fee + exit_fee

def estimate_position_entry_fee(entry_price: float, qty: float, fee_rate: float) -> float:
    return entry_price * qty * fee_rate

def estimate_net_pnl(direction: str, entry_price: float, exit_price: float, qty: float, fee_rate: float) -> float:
    if direction == 'bullish':
        gross = (exit_price - entry_price) * qty
    else:
        gross = (entry_price - exit_price) * qty
    fees = estimate_round_trip_fee(entry_price, exit_price, qty, fee_rate)
    return gross - fees
