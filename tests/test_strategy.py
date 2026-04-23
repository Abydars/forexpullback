import pytest
from app.strategy.scoring import calculate_score

def test_calculate_score():
    score = calculate_score(100, 100, 100, 100, 100)
    assert score == 100
    
    score = calculate_score(50, 50, 50, 50, 50)
    assert score == 50
    
    score = calculate_score(100, 0, 0, 0, 0)
    assert score == 30
