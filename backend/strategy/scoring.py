def calculate_score(htf_strength: float, zone_quality: float, rsi_alignment: float, ltf_strength: float, session_weight: float) -> float:
    score = (htf_strength * 0.30) + \
            (zone_quality * 0.25) + \
            (rsi_alignment * 0.15) + \
            (ltf_strength * 0.20) + \
            (session_weight * 0.10)
    return score
