from sqlalchemy import Column, Integer, String, Float, Boolean, JSON, DateTime, ForeignKey, Text
from sqlalchemy.orm import declarative_base
import datetime

Base = declarative_base()

class ConfigRecord(Base):
    __tablename__ = 'config'
    key = Column(String, primary_key=True)
    value = Column(JSON)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow)
    version = Column(Integer, default=1)

class MT5Account(Base):
    __tablename__ = 'mt5_accounts'
    id = Column(Integer, primary_key=True, autoincrement=True)
    server = Column(String, nullable=False)
    login = Column(Integer, nullable=False)
    password_enc = Column(String, nullable=False)
    path = Column(String, nullable=True)
    is_active = Column(Boolean, default=False)
    last_connected_at = Column(DateTime, nullable=True)

class SymbolCache(Base):
    __tablename__ = 'symbols_cache'
    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey('mt5_accounts.id'))
    generic = Column(String, nullable=False)
    resolved = Column(String, nullable=False)
    digits = Column(Integer)
    point = Column(Float)
    contract_size = Column(Float)
    min_lot = Column(Float)
    max_lot = Column(Float)
    lot_step = Column(Float)
    cached_at = Column(DateTime, default=datetime.datetime.utcnow)

class SessionRecord(Base):
    __tablename__ = 'sessions'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    start_time = Column(String, nullable=False) # Store as HH:MM
    end_time = Column(String, nullable=False)   # Store as HH:MM
    tz = Column(String, nullable=False)
    days_mask = Column(Integer, nullable=False)
    enabled = Column(Boolean, default=True)

class SignalRecord(Base):
    __tablename__ = 'signals'
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String, nullable=False)
    direction = Column(String, nullable=False)
    score = Column(Float, nullable=False)
    htf_bias = Column(String, nullable=False)
    entry = Column(Float, nullable=False)
    sl = Column(Float, nullable=False)
    tp = Column(Float, nullable=False)
    reason = Column(JSON)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    status = Column(String, default='pending') # pending, executed, failed

class TradeRecord(Base):
    __tablename__ = 'trades'
    id = Column(Integer, primary_key=True, autoincrement=True)
    signal_id = Column(Integer, ForeignKey('signals.id'), nullable=True)
    ticket = Column(Integer, unique=True, nullable=False)
    symbol = Column(String, nullable=False)
    direction = Column(String, nullable=False)
    lot = Column(Float, nullable=False)
    entry_price = Column(Float, nullable=False)
    sl = Column(Float, nullable=False)
    tp = Column(Float, nullable=False)
    opened_at = Column(DateTime, nullable=False)
    closed_at = Column(DateTime, nullable=True)
    exit_price = Column(Float, nullable=True)
    pnl = Column(Float, nullable=True)
    commission = Column(Float, nullable=True)
    swap = Column(Float, nullable=True)
    comment = Column(String, nullable=True)

class EventRecord(Base):
    __tablename__ = 'events'
    id = Column(Integer, primary_key=True, autoincrement=True)
    level = Column(String, nullable=False)
    component = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    data = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
