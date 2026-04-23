class AppState:
    def __init__(self):
        self.engine_running = False
        self.mt5_connected = False
        self.active_sessions_count = 0
        self.today_pnl = 0.0

state = AppState()
