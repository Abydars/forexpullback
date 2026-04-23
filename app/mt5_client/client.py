import asyncio
import MetaTrader5 as mt5
import pandas as pd
import logging

logger = logging.getLogger("mt5_client")

class MT5Client:
    def __init__(self):
        self._connected = False
        self._last_error = None

    async def connect(self, server: str, login: int, password: str, path: str | None = None) -> dict:
        kwargs = {
            "server": server,
            "login": login,
            "password": password
        }
        if path:
            kwargs["path"] = path

        success = await asyncio.to_thread(mt5.initialize, **kwargs)
        if not success:
            err = mt5.last_error()
            self._last_error = err
            logger.error(f"MT5 initialize failed: {err}")
            raise Exception(f"MT5 initialize failed: {err}")
        
        success = await asyncio.to_thread(mt5.login, **kwargs)
        if not success:
            err = mt5.last_error()
            self._last_error = err
            logger.error(f"MT5 login failed: {err}")
            raise Exception(f"MT5 login failed: {err}")
            
        self._connected = True
        return await self.account_info()

    async def disconnect(self) -> None:
        await asyncio.to_thread(mt5.shutdown)
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    async def account_info(self) -> dict:
        info = await asyncio.to_thread(mt5.account_info)
        if info is None:
            raise Exception(f"Failed to get account info: {mt5.last_error()}")
        return info._asdict()

    async def get_rates(self, symbol: str, timeframe: int, count: int) -> pd.DataFrame:
        rates = await asyncio.to_thread(mt5.copy_rates_from_pos, symbol, timeframe, 0, count)
        if rates is None or len(rates) == 0:
            return pd.DataFrame()
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        return df

    async def get_positions(self, symbol: str | None = None) -> list[dict]:
        if symbol:
            positions = await asyncio.to_thread(mt5.positions_get, symbol=symbol)
        else:
            positions = await asyncio.to_thread(mt5.positions_get)
            
        if positions is None:
            return []
        return [p._asdict() for p in positions]

    async def order_send(self, request: dict) -> dict:
        result = await asyncio.to_thread(mt5.order_send, request)
        if result is None:
            raise Exception(f"Order send failed: {mt5.last_error()}")
        return result._asdict()

    async def position_close(self, ticket: int) -> dict:
        # Closing is an order_send with opposite type
        positions = await asyncio.to_thread(mt5.positions_get, ticket=ticket)
        if not positions:
            raise Exception("Position not found")
        position = positions[0]
        
        tick = await asyncio.to_thread(mt5.symbol_info_tick, position.symbol)
        type_dict = {mt5.ORDER_TYPE_BUY: mt5.ORDER_TYPE_SELL, mt5.ORDER_TYPE_SELL: mt5.ORDER_TYPE_BUY}
        price_dict = {mt5.ORDER_TYPE_BUY: tick.bid, mt5.ORDER_TYPE_SELL: tick.ask}
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "position": ticket,
            "symbol": position.symbol,
            "volume": position.volume,
            "type": type_dict[position.type],
            "price": price_dict[position.type],
            "deviation": 20,
            "magic": position.magic,
            "comment": "Close via Bot",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        return await self.order_send(request)

mt5_client = MT5Client()
