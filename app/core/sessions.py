from dataclasses import dataclass
from datetime import time, datetime, timedelta
import pytz

@dataclass
class Session:
    id: int
    name: str
    start_time: str
    end_time: str
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
        current_time = now_local.strftime("%H:%M")
        day_bit = 1 << now_local.weekday()
        
        start_time = s.start_time
        end_time = s.end_time
        
        if start_time <= end_time:
            in_window = start_time <= current_time <= end_time
            if in_window and (s.days_mask & day_bit):
                active.append(s)
        else:
            if current_time >= start_time:
                if (s.days_mask & day_bit):
                    active.append(s)
            elif current_time <= end_time:
                prev_day_bit = 1 << ((now_local.weekday() - 1) % 7)
                if (s.days_mask & prev_day_bit):
                    active.append(s)
                    
    return active

def get_session_start_utc(s: Session, now_utc: datetime) -> datetime:
    tz = pytz.timezone(s.timezone)
    now_local = now_utc.astimezone(tz)
    current_time = now_local.strftime("%H:%M")
    
    start_hour, start_minute = map(int, s.start_time.split(':'))
    
    if s.start_time <= s.end_time:
        start_local = now_local.replace(hour=start_hour, minute=start_minute, second=0, microsecond=0)
    else:
        if current_time >= s.start_time:
            start_local = now_local.replace(hour=start_hour, minute=start_minute, second=0, microsecond=0)
        else:
            start_local = (now_local - timedelta(days=1)).replace(hour=start_hour, minute=start_minute, second=0, microsecond=0)
            
    return start_local.astimezone(pytz.utc)
