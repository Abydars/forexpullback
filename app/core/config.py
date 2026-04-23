import json
from app.db.session import SessionLocal
from app.db.models import ConfigRecord

class Config:
    def __init__(self):
        self._cache = {}
        self.version = 0
        self.load()

    def load(self):
        db = SessionLocal()
        records = db.query(ConfigRecord).all()
        for r in records:
            self._cache[r.key] = r.value
        
        # default version
        ver_record = db.query(ConfigRecord).filter_by(key='_version').first()
        self.version = ver_record.value if ver_record else 1
        db.close()

    def get(self, key, default=None):
        return self._cache.get(key, default)

    def set(self, key, value):
        db = SessionLocal()
        record = db.query(ConfigRecord).filter_by(key=key).first()
        if not record:
            record = ConfigRecord(key=key, value=value)
            db.add(record)
        else:
            record.value = value
            record.version += 1
        
        ver_record = db.query(ConfigRecord).filter_by(key='_version').first()
        if not ver_record:
            ver_record = ConfigRecord(key='_version', value=1)
            db.add(ver_record)
        else:
            ver_record.value = int(ver_record.value) + 1
        
        db.commit()
        self._cache[key] = value
        self.version = ver_record.value
        db.close()

    @property
    def max_open_positions(self): return self.get('max_open_positions', 3)
    
    @property
    def signal_threshold(self): return self.get('signal_threshold', 65)

    @property
    def risk_percent(self): return self.get('risk_percent', 1.0)
    
    @property
    def scan_interval_seconds(self): return self.get('scan_interval_seconds', 10)

    @property
    def symbols(self): return self.get('symbols', ['XAUUSD', 'EURUSD'])

cfg = Config()
