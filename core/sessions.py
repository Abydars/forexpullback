from datetime import datetime, time
import pytz
from dataclasses import dataclass

@dataclass
class Session:
    id: int
    name: str
    start_time: time
    end_time: time
    timezone: str
    days_mask: int
    enabled: bool

def is_session_active(session: Session, now_utc: datetime) -> bool:
    if not session.enabled:
        return False
        
    try:
        tz = pytz.timezone(session.timezone)
    except pytz.UnknownTimeZoneError:
        return False
        
    now_local = now_utc.astimezone(tz)
    weekday = now_local.weekday()
    
    # Check days mask (0=Mon, 6=Sun)
    if not (session.days_mask & (1 << weekday)):
        return False
        
    current_time = now_local.time()
    if session.start_time <= session.end_time:
        return session.start_time <= current_time <= session.end_time
    else:
        # Crosses midnight
        return current_time >= session.start_time or current_time <= session.end_time

def active_sessions(sessions: list[Session], now_utc: datetime) -> list[Session]:
    return [s for s in sessions if is_session_active(s, now_utc)]

def any_active(sessions: list[Session], now_utc: datetime) -> bool:
    return len(active_sessions(sessions, now_utc)) > 0
