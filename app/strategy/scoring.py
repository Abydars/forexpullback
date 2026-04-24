def calculate_score(htf_strength: int, zone_quality: int, ltf_strength: int, session_active: bool) -> int:
    session_weight = 100 if session_active else 0
    score = (htf_strength * 0.35) + (zone_quality * 0.30) + (ltf_strength * 0.25) + (session_weight * 0.10)
    return int(score)
