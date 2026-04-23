def calculate_score(htf_strength: float, mtf_strength: float, ltf_strength: float, rsi_score: float, session_score: float) -> float:
    # Weights: HTF 30%, MTF 25%, LTF 20%, RSI 15%, Session 10%
    score = (
        (htf_strength * 0.30) +
        (mtf_strength * 0.25) +
        (ltf_strength * 0.20) +
        (rsi_score * 0.15) +
        (session_score * 0.10)
    )
    return float(score)
