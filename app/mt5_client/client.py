import asyncio
import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime

class MT5Client:
    async def connect(self, server, login, password, path=None) -> dict:
        def _connect():
            if path:
                if not mt5.initialize(path=path, login=login, password=password, server=server):
                    return False
            else:
                if not mt5.initialize(login=login, password=password, server=server):
                    return False
            return mt5.login(login=login, password=password, server=server)
        
        success = await asyncio.to_thread(_connect)
        if not success:
            error = mt5.last_error()
            raise Exception(f"MT5 Connect failed: {error}")
        return await self.account_info()

    async def disconnect(self) -> None:
        await asyncio.to_thread(mt5.shutdown)

    def is_connected(self) -> bool:
        try:
            return mt5.terminal_info() is not None
        except:
            return False

    async def account_info(self) -> dict:
        def _info():
            acc = mt5.account_info()
            if acc is None:
                return None
            return acc._asdict()
        acc = await asyncio.to_thread(_info)
        if not acc:
            raise Exception("Failed to get account info")
        return acc

    async def get_rates(self, symbol, timeframe, count) -> pd.DataFrame:
        def _rates():
            rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
            if rates is None:
                return pd.DataFrame()
            df = pd.DataFrame(rates)
            df['time'] = pd.to_datetime(df['time'], unit='s')
            return df
        return await asyncio.to_thread(_rates)

    async def get_positions(self, symbol=None) -> list[dict]:
        def _pos():
            if symbol:
                pos = mt5.positions_get(symbol=symbol)
            else:
                pos = mt5.positions_get()
            if pos is None:
                return []
            return [p._asdict() for p in pos]
        return await asyncio.to_thread(_pos)

    async def order_send(self, request: dict) -> dict:
        def _send():
            return mt5.order_send(request)
        res = await asyncio.to_thread(_send)
        if res is None:
            raise Exception(f"Order send failed: {mt5.last_error()}")
        return res._asdict()

    async def position_close(self, ticket: int) -> dict:
        def _close():
            pos = mt5.positions_get(ticket=ticket)
            if pos is None or len(pos) == 0:
                return None
            p = pos[0]
            action = mt5.TRADE_ACTION_DEAL
            type = mt5.ORDER_TYPE_SELL if p.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
            price = mt5.symbol_info_tick(p.symbol).bid if type == mt5.ORDER_TYPE_SELL else mt5.symbol_info_tick(p.symbol).ask
            info = mt5.symbol_info(p.symbol)
            filling_type = mt5.ORDER_FILLING_IOC
            if info:
                if info.filling_mode & 1:
                    filling_type = mt5.ORDER_FILLING_FOK
                elif info.filling_mode & 2:
                    filling_type = mt5.ORDER_FILLING_IOC
                else:
                    filling_type = mt5.ORDER_FILLING_RETURN
                    
            request = {
                "action": action,
                "symbol": p.symbol,
                "volume": p.volume,
                "type": type,
                "position": ticket,
                "price": price,
                "deviation": 20,
                "magic": p.magic,
                "comment": "Close position",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": filling_type,
            }
            return mt5.order_send(request)
        res = await asyncio.to_thread(_close)
        if res is None:
            raise Exception(f"Position close failed: {mt5.last_error()}")
        return res._asdict()
        
mt5_client = MT5Client()
