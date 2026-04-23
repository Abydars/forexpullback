import pytest
from backend.mt5_client.client import MT5Client
from backend.mt5_client.symbol_resolver import SymbolResolver

class MockSymbol:
    def __init__(self, name):
        self.name = name
        self.digits = 5
        self.point = 0.00001
        self.trade_contract_size = 100000.0
        self.volume_min = 0.01
        self.volume_max = 100.0
        self.volume_step = 0.01

class MockMT5Client(MT5Client):
    def is_connected(self): return True
    def symbols_get(self):
        return [
            MockSymbol("XAUUSDm"),
            MockSymbol("EURUSDc"),
            MockSymbol("GBPJPY.r"),
            MockSymbol("BTCUSD"),
        ]

def test_symbol_resolver():
    client = MockMT5Client()
    resolver = SymbolResolver(client)
    resolver.refresh()
    
    assert resolver.resolve("XAUUSD") == "XAUUSDm"
    assert resolver.resolve("EURUSD") == "EURUSDc"
    assert resolver.resolve("GBPJPY") == "GBPJPY.r"
    assert resolver.resolve("BTCUSD") == "BTCUSD"
    assert resolver.resolve("UNKNOWN") is None
