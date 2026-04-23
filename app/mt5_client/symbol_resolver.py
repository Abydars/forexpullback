import asyncio
import MetaTrader5 as mt5

class SymbolResolver:
    KNOWN_SUFFIXES = ["", "m", "c", "z", ".r", "_raw", ".m", ".c", "-pro", ".pro", "pro", ".ecn"]

    def __init__(self, mt5_client):
        self._client = mt5_client
        self._cache: dict[str, str] = {}
        self._all_symbols: set[str] = set()

    async def refresh(self) -> None:
        """Pull all broker symbols via mt5.symbols_get() and rebuild the index."""
        if not self._client.is_connected():
            return
            
        symbols = await asyncio.to_thread(mt5.symbols_get)
        if symbols:
            self._all_symbols = {s.name for s in symbols}
            self._cache.clear()

    async def resolve(self, generic: str) -> str | None:
        """
        Resolution priority:
          1. Exact match
          2. generic + known suffix (try each in order)
          3. Longest prefix match where remainder in KNOWN_SUFFIXES
        Never match if the base portion differs (EURUSD != EURUSDT).
        Cache result. Return None if not found.
        """
        if not self._all_symbols:
            await self.refresh()
            
        if generic in self._cache:
            return self._cache[generic]

        # 1. Exact match
        if generic in self._all_symbols:
            self._cache[generic] = generic
            return generic
            
        # 2. generic + known suffix
        for suffix in self.KNOWN_SUFFIXES:
            if not suffix: continue
            candidate = f"{generic}{suffix}"
            if candidate in self._all_symbols:
                self._cache[generic] = candidate
                return candidate
                
        # 3. If there are other strange prefixes, we can iterate, but let's stick to spec.
        # Check if generic is prefix to something that only differs by KNOWN_SUFFIXES
        for sym in self._all_symbols:
            if sym.startswith(generic):
                remainder = sym[len(generic):]
                if remainder in self.KNOWN_SUFFIXES:
                    self._cache[generic] = sym
                    return sym
                    
        return None

    async def resolve_many(self, generics: list[str]) -> dict[str, str | None]:
        results = {}
        for g in generics:
            results[g] = await self.resolve(g)
        return results
