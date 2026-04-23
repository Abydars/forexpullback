from dataclasses import dataclass
from datetime import time, datetime
import pytz

@dataclass
class Session:
    id: int
    name: str
    start_time: time
    end_time: time
    timezone: str       # IANA, e.g. "Europe/London"
    days_mask: int      # bit 0 = Mon ... bit 6 = Sun
    enabled: bool

def any_active(sessions: list[Session], now_utc: datetime) -> bool:
    return len(active_sessions(sessions, now_utc)) > 0

def active_sessions(sessions: list[Session], now_utc: datetime) -> list[Session]:
    active = []
    for s in sessions:
        if not s.enabled:
            continue
            
        tz = pytz.timezone(s.timezone)
        now_local = now_utc.astimezone(tz)
        current_time = now_local.time()
        current_day = now_local.weekday() # 0 = Mon, 6 = Sun
        
        # Check day mask
        if not (s.days_mask & (1 << current_day)):
            continue
            
        # Check time window (handles midnight crossing)
        if s.start_time <= s.end_time:
            if s.start_time <= current_time <= s.end_time:
                active.append(s)
        else:
            # Midnight crossing
            if current_time >= s.start_time or current_time <= s.end_time:
                active.append(s)
                
    return active
