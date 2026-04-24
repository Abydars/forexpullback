import math

class SymbolResolver:
    def __init__(self, client):
        self.client = client
        self.cache = {}

    async def refresh(self):
        if not self.client.symbols_cache:
            await self.client._fetch_exchange_info()
            
    def resolve(self, generic: str) -> str:
        g = generic.upper().strip()
        if self.client.symbols_cache and g not in self.client.symbols_cache:
            return None
        return g
        
    def resolve_many(self, generics: list) -> dict:
        return {g: self.resolve(g) for g in generics}
        
    def round_price(self, symbol: str, price: float) -> float:
        info = self.client.symbol_info(symbol)
        if not info:
            return round(price, 2)
            
        tick_size = float(next(f['tickSize'] for f in info['filters'] if f['filterType'] == 'PRICE_FILTER'))
        precision = int(round(-math.log10(tick_size), 0))
        # Binance requires rounding down/up to tick size appropriately or just rounding to precision
        return round(price, precision)

    def round_qty(self, symbol: str, qty: float) -> float:
        info = self.client.symbol_info(symbol)
        if not info:
            return round(qty, 3)
            
        lot_size_filter = next(f for f in info['filters'] if f['filterType'] == 'LOT_SIZE')
        step_size = float(lot_size_filter['stepSize'])
        min_qty = float(lot_size_filter['minQty'])
        max_qty = float(lot_size_filter['maxQty'])
        
        # Round quantity to step size
        qty = math.floor(qty / step_size) * step_size
        
        if qty < min_qty:
            return min_qty
        if qty > max_qty:
            return max_qty
            
        precision = int(round(-math.log10(step_size), 0))
        return round(qty, precision)
