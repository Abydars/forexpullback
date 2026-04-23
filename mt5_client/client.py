import asyncio
import logging
from typing import Optional, List, Dict, Any
from core.state import engine_state

try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False
    logging.warning("MetaTrader5 package not found (likely on Mac/Linux). Using mocked MT5 client.")

class MT5Client:
    def __init__(self):
        self._connected = False
        self._mock_positions = []
        self._mock_orders = []

    async def connect(self, server: str, login: int, password: str, path: Optional[str] = None) -> bool:
        if not MT5_AVAILABLE:
            self._connected = True
            engine_state.mt5_connected = True
            return True
            
        kwargs = {"server": server, "login": login, "password": password}
        if path: kwargs["path"] = path
        
        if not mt5.initialize(**kwargs):
            self._connected = False
            engine_state.mt5_connected = False
            raise Exception(f"MT5 initialize failed: {mt5.last_error()}")
            
        self._connected = True
        engine_state.mt5_connected = True
        return True

    async def disconnect(self):
        if MT5_AVAILABLE:
            mt5.shutdown()
        self._connected = False
        engine_state.mt5_connected = False

    def is_connected(self) -> bool:
        return self._connected

    def account_info(self) -> Any:
        if not MT5_AVAILABLE:
            class MockAccount:
                balance = 10000.0
                equity = 10000.0
                margin = 0.0
            return MockAccount() if self._connected else None
        return mt5.account_info() if self._connected else None

    def symbols_get(self) -> List[Any]:
        if not MT5_AVAILABLE:
            class MockSymbol:
                def __init__(self, n): self.name = n
            return [MockSymbol("EURUSD"), MockSymbol("XAUUSDm")] if self._connected else []
        return mt5.symbols_get() if self._connected else []

    def copy_rates_from_pos(self, symbol: str, timeframe: int, start_pos: int, count: int) -> Any:
        if not MT5_AVAILABLE:
            return None # Mock data generator not fully implemented here
        return mt5.copy_rates_from_pos(symbol, timeframe, start_pos, count)

    def order_send(self, request: dict) -> Any:
        if not MT5_AVAILABLE:
            class MockResult:
                retcode = 10009
                order = 12345
                price = request.get("price", 1.0)
            return MockResult()
        return mt5.order_send(request)

    def get_positions(self) -> List[Any]:
        if not MT5_AVAILABLE:
            return self._mock_positions
        return mt5.positions_get() or []

    def history_deals_get(self, ticket: int) -> List[Any]:
        if not MT5_AVAILABLE:
            return []
        return mt5.history_deals_get(position=ticket)

    def position_close(self, ticket: int) -> Any:
        if not MT5_AVAILABLE:
            class MockResult:
                retcode = 10009
            return MockResult()
        
        pos = mt5.positions_get(ticket=ticket)
        if not pos: return None
        pos = pos[0]
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": pos.symbol,
            "volume": pos.volume,
            "type": mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY,
            "position": ticket,
            "magic": 123456,
            "comment": "manual_close",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        return mt5.order_send(request)

mt5_client = MT5Client()
