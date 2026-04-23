import json
from datetime import datetime
from backend.db.session import SessionLocal
from backend.db.models import Config

DEFAULT_CONFIG = {
    "max_open_positions": 3,
    "max_per_symbol": 1,
    "max_per_direction": 1,
    "signal_threshold": 65.0,
    "risk_percent": 1.0,
    "scan_interval_seconds": 10,
    "reward_ratio": 2.0,
    "sl_mode": "structural",
    "atr_multiplier": 1.5,
    "tp_mode": "r_multiple",
    "breakeven_trigger_r": 1.0,
    "trailing_enabled": False,
    "trailing_distance_pips": 10.0,
    "symbols": []
}

class ConfigManager:
    def __init__(self):
        self.config = DEFAULT_CONFIG.copy()
        self.version = 0

    def load(self):
        with SessionLocal() as db:
            row = db.query(Config).filter(Config.key == "main").first()
            if not row:
                row = Config(
                    key="main",
                    value=self.config,
                    updated_at=datetime.utcnow(),
                    version=1
                )
                db.add(row)
                db.commit()
            
            self.config = {**DEFAULT_CONFIG, **row.value}
            self.version = row.version

    def update(self, new_values: dict):
        with SessionLocal() as db:
            row = db.query(Config).filter(Config.key == "main").first()
            if row:
                merged = {**row.value, **new_values}
                row.value = merged
                row.version += 1
                row.updated_at = datetime.utcnow()
                db.commit()
                self.config = merged
                self.version = row.version

    def get(self, key, default=None):
        return self.config.get(key, default)

config_manager = ConfigManager()
