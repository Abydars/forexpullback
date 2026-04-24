import asyncio
import httpx
import hmac
import hashlib
import time
import pandas as pd
from urllib.parse import urlencode

class BinanceClient:
    def __init__(self):
        self.api_key = None
        self.api_secret = None
        self.testnet = True
        self.client = httpx.AsyncClient()
        self.exchange_info_cache = {}
        self.symbols_cache = {}
        
    @property
    def base_url(self):
        return "https://testnet.binancefuture.com" if self.testnet else "https://fapi.binance.com"
        
    def _sign(self, params: dict) -> str:
        query_string = urlencode(params)
        return hmac.new(self.api_secret.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()
        
    async def request(self, method: str, endpoint: str, signed: bool = False, **kwargs) -> dict:
        url = f"{self.base_url}{endpoint}"
        headers = kwargs.get('headers', {})
        if self.api_key:
            headers['X-MBX-APIKEY'] = self.api_key
        kwargs['headers'] = headers
        
        if signed:
            params = kwargs.get('params', {})
            params['timestamp'] = int(time.time() * 1000)
            params['signature'] = self._sign(params)
            kwargs['params'] = params
            
        response = await self.client.request(method, url, **kwargs)
        if response.status_code != 200:
            raise Exception(f"Binance API error {response.status_code}: {response.text}")
        return response.json()

    async def connect(self, api_key: str, api_secret: str, testnet: bool = True) -> dict:
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        
        # Test connection
        acc_info = await self.account_info()
        await self._fetch_exchange_info()
        return acc_info
        
    async def _fetch_exchange_info(self):
        res = await self.request('GET', '/fapi/v1/exchangeInfo')
        self.exchange_info_cache = res
        self.symbols_cache = {s['symbol']: s for s in res['symbols']}
        
    async def disconnect(self) -> None:
        self.api_key = None
        self.api_secret = None
        await self.client.aclose()
        self.client = httpx.AsyncClient()

    def is_connected(self) -> bool:
        return self.api_key is not None

    async def account_info(self) -> dict:
        res = await self.request('GET', '/fapi/v2/account', signed=True)
        return res

    async def get_rates(self, symbol: str, timeframe: str, count: int) -> pd.DataFrame:
        tf_map = {
            'M1': '1m', 'M5': '5m', 'M15': '15m', 
            'H1': '1h', 'H4': '4h', 'D1': '1d'
        }
        interval = tf_map.get(timeframe, '15m')
        
        res = await self.request('GET', '/fapi/v1/klines', params={
            'symbol': symbol,
            'interval': interval,
            'limit': count
        })
        
        if not res:
            return pd.DataFrame()
            
        df = pd.DataFrame(res, columns=[
            'time', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_asset_volume', 'number_of_trades',
            'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
        ])
        
        df['time'] = pd.to_datetime(df['time'], unit='ms')
        df['open'] = df['open'].astype(float)
        df['high'] = df['high'].astype(float)
        df['low'] = df['low'].astype(float)
        df['close'] = df['close'].astype(float)
        df['volume'] = df['volume'].astype(float)
        
        return df[['time', 'open', 'high', 'low', 'close', 'volume']]

    async def get_positions(self, symbol: str = None) -> list[dict]:
        res = await self.request('GET', '/fapi/v2/positionRisk', signed=True)
        positions = []
        for p in res:
            if float(p['positionAmt']) != 0:
                if symbol and p['symbol'] != symbol:
                    continue
                positions.append(p)
        return positions

    def symbol_info(self, symbol: str) -> dict:
        if not self.symbols_cache:
            return None
        return self.symbols_cache.get(symbol)
        
    async def get_24hr_tickers(self) -> list[dict]:
        res = await self.request('GET', '/fapi/v1/ticker/24hr')
        return res

    async def symbol_info_tick(self, symbol: str) -> dict:
        res = await self.request('GET', '/fapi/v1/ticker/bookTicker', params={'symbol': symbol})
        if isinstance(res, dict) and 'symbol' in res:
            return {
                'ask': float(res['askPrice']),
                'bid': float(res['bidPrice']),
                'time': time.time()
            }
        return None

    async def order_send(self, params: dict) -> dict:
        res = await self.request('POST', '/fapi/v1/order', signed=True, params=params)
        return res

    async def algo_order_send(self, params: dict) -> dict:
        res = await self.request('POST', '/fapi/v1/algoOrder', signed=True, params=params)
        return res

    async def order_cancel(self, symbol: str, order_id: str = None, client_order_id: str = None) -> dict:
        params = {'symbol': symbol}
        if order_id: params['orderId'] = order_id
        if client_order_id: params['origClientOrderId'] = client_order_id
        res = await self.request('DELETE', '/fapi/v1/order', signed=True, params=params)
        return res

    async def algo_order_cancel(self, symbol: str, order_id: str = None, client_order_id: str = None) -> dict:
        params = {'symbol': symbol}
        if order_id: params['algoId'] = order_id # algo orders use algoId for cancellation
        if client_order_id: params['clientAlgoId'] = client_order_id
        res = await self.request('DELETE', '/fapi/v1/algoOrder', signed=True, params=params)
        return res
        
    async def cancel_all_orders(self, symbol: str) -> dict:
        res = await self.request('DELETE', '/fapi/v1/allOpenOrders', signed=True, params={'symbol': symbol})
        return res

    async def set_leverage(self, symbol: str, leverage: int) -> dict:
        res = await self.request('POST', '/fapi/v1/leverage', signed=True, params={'symbol': symbol, 'leverage': leverage})
        return res
        
    async def set_margin_type(self, symbol: str, margin_type: str) -> dict:
        try:
            res = await self.request('POST', '/fapi/v1/marginType', signed=True, params={'symbol': symbol, 'marginType': margin_type})
            return res
        except Exception as e:
            if "-4046" in str(e): # No need to change margin type
                return {"msg": "Margin type already set"}
            raise e

binance_client = BinanceClient()
