def calculate_score(htf_strength: int, zone_quality: int, rsi_alignment: int, ltf_strength: int, session_weight: int) -> int:
    score = (
        htf_strength * 0.30 +
        zone_quality * 0.25 +
        rsi_alignment * 0.15 +
        ltf_strength * 0.20 +
        session_weight * 0.10
    )
    return int(score)
