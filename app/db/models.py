from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Boolean, Float, DateTime, JSON, ForeignKey, func
from datetime import datetime

class Base(DeclarativeBase):
    pass

class Config(Base):
    __tablename__ = "config"
    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[dict] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())
    version: Mapped[int] = mapped_column(Integer, default=1)

class BinanceAccount(Base):
    __tablename__ = "binance_accounts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    api_key_enc: Mapped[str] = mapped_column(String)
    api_secret_enc: Mapped[str] = mapped_column(String)
    testnet: Mapped[bool] = mapped_column(Boolean, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    last_connected_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

class SymbolCache(Base):
    __tablename__ = "symbols_cache"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("binance_accounts.id"))
    generic: Mapped[str] = mapped_column(String)
    resolved: Mapped[str] = mapped_column(String)
    tick_size: Mapped[float] = mapped_column(Float)
    step_size: Mapped[float] = mapped_column(Float)
    min_qty: Mapped[float] = mapped_column(Float)
    max_qty: Mapped[float] = mapped_column(Float)
    min_notional: Mapped[float] = mapped_column(Float)
    cached_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

class Session(Base):
    __tablename__ = "sessions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    start_time: Mapped[str] = mapped_column(String)
    end_time: Mapped[str] = mapped_column(String)
    tz: Mapped[str] = mapped_column(String)
    days_mask: Mapped[int] = mapped_column(Integer)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

class Signal(Base):
    __tablename__ = "signals"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String)
    direction: Mapped[str] = mapped_column(String)
    score: Mapped[int] = mapped_column(Integer)
    htf_bias: Mapped[str] = mapped_column(String)
    entry: Mapped[float] = mapped_column(Float)
    sl: Mapped[float] = mapped_column(Float)
    tp: Mapped[float] = mapped_column(Float)
    reason: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

class Trade(Base):
    __tablename__ = "trades"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    signal_id: Mapped[int | None] = mapped_column(ForeignKey("signals.id"), nullable=True)
    exchange: Mapped[str] = mapped_column(String, default="binance")
    order_id: Mapped[str | None] = mapped_column(String, nullable=True)
    client_order_id: Mapped[str | None] = mapped_column(String, nullable=True)
    position_side: Mapped[str | None] = mapped_column(String, nullable=True)
    symbol: Mapped[str] = mapped_column(String)
    direction: Mapped[str] = mapped_column(String)
    quantity: Mapped[float] = mapped_column(Float)
    entry_price: Mapped[float] = mapped_column(Float)
    sl: Mapped[float] = mapped_column(Float)
    tp: Mapped[float] = mapped_column(Float)
    opened_at: Mapped[datetime] = mapped_column(DateTime)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    exit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    pnl: Mapped[float | None] = mapped_column(Float, nullable=True)
    commission: Mapped[float | None] = mapped_column(Float, nullable=True)
    swap: Mapped[float | None] = mapped_column(Float, nullable=True)
    note: Mapped[str | None] = mapped_column(String, nullable=True)
    parent_trade_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dca_index: Mapped[int] = mapped_column(Integer, default=0)
    group_id: Mapped[str | None] = mapped_column(String, nullable=True)
    sl_order_id: Mapped[str | None] = mapped_column(String, nullable=True)
    tp_order_id: Mapped[str | None] = mapped_column(String, nullable=True)

class Event(Base):
    __tablename__ = "events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    level: Mapped[str] = mapped_column(String)
    component: Mapped[str] = mapped_column(String)
    message: Mapped[str] = mapped_column(String)
    data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
