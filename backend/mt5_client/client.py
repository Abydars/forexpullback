import pandas as pd
from typing import Optional, List, Dict, Any
import logging
import asyncio

try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False
    logging.warning("MetaTrader5 package not found (likely on Mac/Linux). Using mocked MT5 client.")

class AccountInfo:
    def __init__(self, login, server, balance, equity, margin, currency, leverage):
        self.login = login
        self.server = server
        self.balance = balance
        self.equity = equity
        self.margin = margin
        self.currency = currency
        self.leverage = leverage

class MT5Client:
    def __init__(self):
        self._connected = False
        self._account_info = None

    async def connect(self, server: str, login: int, password: str, path: Optional[str] = None) -> AccountInfo:
        if not MT5_AVAILABLE:
            await asyncio.sleep(0.5)
            self._connected = True
            self._account_info = AccountInfo(login, server, 10000.0, 10000.0, 0.0, "USD", 500)
            return self._account_info
            
        kwargs = {"login": login, "server": server, "password": password}
        if path:
            kwargs["path"] = path
            
        # mt5 functions are blocking, wrap in executor if needed, but for simplicity here:
        if not mt5.initialize(**kwargs):
            raise Exception(f"initialize() failed, error code: {mt5.last_error()}")
            
        if not mt5.login(login, password=password, server=server):
            raise Exception(f"login() failed, error code: {mt5.last_error()}")
            
        account = mt5.account_info()
        if not account:
            raise Exception(f"account_info() failed, error code: {mt5.last_error()}")
            
        self._connected = True
        self._account_info = AccountInfo(
            account.login, account.server, account.balance, account.equity,
            account.margin, account.currency, account.leverage
        )
        return self._account_info

    async def disconnect(self) -> None:
        self._connected = False
        if MT5_AVAILABLE:
            mt5.shutdown()

    def is_connected(self) -> bool:
        return self._connected

    def account_info(self) -> Optional[AccountInfo]:
        if not self._connected:
            return None
        if not MT5_AVAILABLE:
            return self._account_info
            
        account = mt5.account_info()
        if account:
            self._account_info = AccountInfo(
                account.login, account.server, account.balance, account.equity,
                account.margin, account.currency, account.leverage
            )
        return self._account_info

    def symbols_get(self) -> List[Any]:
        if not MT5_AVAILABLE:
            # Return mocked Exness-like symbols
            class MockSymbol:
                def __init__(self, name):
                    self.name = name
                    self.digits = 3 if "JPY" in name else 5
                    self.point = 0.001 if "JPY" in name else 0.00001
                    self.trade_contract_size = 100000.0
                    self.volume_min = 0.01
                    self.volume_max = 100.0
                    self.volume_step = 0.01
            return [
                MockSymbol("XAUUSDm"), MockSymbol("EURUSDm"), MockSymbol("GBPJPYm"),
                MockSymbol("XAUUSDc"), MockSymbol("BTCUSDm")
            ]
        
        # mt5 requires terminal connection
        if not self._connected:
            return []
            
        symbols = mt5.symbols_get()
        return symbols if symbols else []

    def get_rates(self, symbol: str, timeframe: int, count: int) -> pd.DataFrame:
        if not MT5_AVAILABLE:
            # Return mocked dataframe
            dates = pd.date_range(end=pd.Timestamp.now(), periods=count, freq='5min')
            df = pd.DataFrame({
                'time': dates.astype(int) // 10**9,
                'open': [1.0] * count,
                'high': [1.0] * count,
                'low': [1.0] * count,
                'close': [1.0] * count,
                'tick_volume': [100] * count,
                'spread': [1] * count,
                'real_volume': [0] * count
            })
            return df

        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
        if rates is None or len(rates) == 0:
            return pd.DataFrame()
            
        df = pd.DataFrame(rates)
        return df

    def get_positions(self, symbol: Optional[str] = None) -> list:
        if not MT5_AVAILABLE:
            return []
        if symbol:
            return mt5.positions_get(symbol=symbol) or []
        return mt5.positions_get() or []

    def order_send(self, request: dict) -> Any:
        if not MT5_AVAILABLE:
            class MockResult:
                def __init__(self):
                    self.retcode = 10009 # mt5.TRADE_RETCODE_DONE
                    self.order = 123456
                    self.comment = "Mock order"
            return MockResult()
        return mt5.order_send(request)

    def position_close(self, ticket: int) -> Any:
        if not MT5_AVAILABLE:
            class MockResult:
                def __init__(self):
                    self.retcode = 10009
            return MockResult()
        # simplified close logic...
        return None

mt5_client = MT5Client()
