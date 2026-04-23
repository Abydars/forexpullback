from dataclasses import dataclass, field

@dataclass
class AppState:
    mt5_connected: bool = False
    account: dict | None = None           # balance, equity, currency, leverage, server
    open_positions: list[dict] = field(default_factory=list)
    recent_signals: list[dict] = field(default_factory=list)  # cap at 50
    recent_trades: list[dict] = field(default_factory=list)   # cap at 200
    equity_series: list[tuple[float, float]] = field(default_factory=list)
    today_pnl: float = 0.0
    engine_running: bool = False
    active_sessions: list[str] = field(default_factory=list)
    last_error: str | None = None

state = AppState()
