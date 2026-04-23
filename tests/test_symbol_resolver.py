import pytest
import asyncio
from app.mt5_client.symbol_resolver import SymbolResolver

class MockMT5Client:
    def is_connected(self):
        return True

@pytest.fixture
def resolver():
    res = SymbolResolver(MockMT5Client())
    res._all_symbols = {'EURUSD', 'XAUUSDm', 'GBPUSD.r', 'USDJPYc'}
    return res

@pytest.mark.asyncio
async def test_resolve_exact(resolver):
    assert await resolver.resolve('EURUSD') == 'EURUSD'

@pytest.mark.asyncio
async def test_resolve_suffix(resolver):
    assert await resolver.resolve('XAUUSD') == 'XAUUSDm'
    assert await resolver.resolve('GBPUSD') == 'GBPUSD.r'
    assert await resolver.resolve('USDJPY') == 'USDJPYc'

@pytest.mark.asyncio
async def test_resolve_not_found(resolver):
    assert await resolver.resolve('AUDUSD') is None
