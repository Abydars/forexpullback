import pytest
from datetime import time, datetime, timezone
import pytz
from app.core.sessions import Session, any_active, active_sessions

def test_active_sessions():
    # Session 10:00 to 14:00 UTC, Mon-Fri
    s1 = Session(id=1, name="London", start_time=time(10,0), end_time=time(14,0), timezone="UTC", days_mask=0b0011111, enabled=True)
    
    # Session 22:00 to 02:00 UTC, Mon-Fri (Midnight crossing)
    s2 = Session(id=2, name="Asia", start_time=time(22,0), end_time=time(2,0), timezone="UTC", days_mask=0b0011111, enabled=True)
    
    now_london = datetime(2023, 1, 2, 12, 0, tzinfo=timezone.utc) # Monday 12:00
    active = active_sessions([s1, s2], now_london)
    assert len(active) == 1
    assert active[0].name == "London"
    
    now_asia = datetime(2023, 1, 2, 23, 0, tzinfo=timezone.utc) # Monday 23:00
    active = active_sessions([s1, s2], now_asia)
    assert len(active) == 1
    assert active[0].name == "Asia"
    
    now_asia2 = datetime(2023, 1, 3, 1, 0, tzinfo=timezone.utc) # Tuesday 01:00
    active = active_sessions([s1, s2], now_asia2)
    assert len(active) == 1
    assert active[0].name == "Asia"
    
    now_none = datetime(2023, 1, 2, 16, 0, tzinfo=timezone.utc) # Monday 16:00
    active = active_sessions([s1, s2], now_none)
    assert len(active) == 0
