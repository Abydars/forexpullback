from dataclasses import dataclass
from datetime import time, datetime
import pytz

@dataclass
class Session:
    id: int
    name: str
    start_time: time
    end_time: time
    timezone: str
    days_mask: int
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
        day_bit = 1 << now_local.weekday()
        t = now_local.time()
        
        if s.start_time <= s.end_time:
            in_window = s.start_time <= t <= s.end_time
            if in_window and (s.days_mask & day_bit):
                active.append(s)
        else:
            if t >= s.start_time:
                if (s.days_mask & day_bit):
                    active.append(s)
            elif t <= s.end_time:
                prev_day_bit = 1 << ((now_local.weekday() - 1) % 7)
                if (s.days_mask & prev_day_bit):
                    active.append(s)
                    
    return active
