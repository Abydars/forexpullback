import asyncio
import MetaTrader5 as mt5

class SymbolResolver:
    KNOWN_SUFFIXES = ["", "m", "c", "z", ".r", "_raw", ".m", ".c", "-pro", ".pro", "pro", ".ecn"]

    def __init__(self, mt5_client):
        self._client = mt5_client
        self._cache: dict[str, str] = {}
        self._all_symbols: set[str] = set()

    async def refresh(self) -> None:
        def _get():
            syms = mt5.symbols_get()
            if syms is None:
                return []
            return [s.name for s in syms]
        
        all_syms = await asyncio.to_thread(_get)
        self._all_symbols = set(all_syms)
        self._cache.clear()

    def resolve(self, generic: str) -> str | None:
        if generic in self._cache:
            return self._cache[generic]

        if generic in self._all_symbols:
            self._cache[generic] = generic
            return generic

        for suffix in self.KNOWN_SUFFIXES:
            if not suffix: continue
            candidate = generic + suffix
            if candidate in self._all_symbols:
                self._cache[generic] = candidate
                return candidate
                
        return None

    def resolve_many(self, generics: list[str]) -> dict[str, str | None]:
        return {g: self.resolve(g) for g in generics}
