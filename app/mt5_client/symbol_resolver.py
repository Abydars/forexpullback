import asyncio
import MetaTrader5 as mt5

class SymbolResolver:
    KNOWN_SUFFIXES = ["", "m", "c", "z", ".r", "_raw", ".m", ".c", "-pro", ".pro", "pro", ".ecn", ".cash", "-cash"]
    
    ALIASES = {
        "US500": ["US500", "SPX500", "SP500", "SPX"],
        "USTEC": ["USTEC", "NAS100", "NDX100", "US100"],
        "US30": ["US30", "WS30", "DJI30", "DOW"],
        "DE40": ["DE40", "GER40", "DAX40", "DAX"],
        "UK100": ["UK100", "UKX", "FTSE"],
        "XAUUSD": ["XAUUSD", "GOLD"],
        "XAGUSD": ["XAGUSD", "SILVER"],
        "USOIL": ["USOIL", "WTI", "CRUDE"],
        "UKOIL": ["UKOIL", "BRENT"],
        "BTCUSD": ["BTCUSD", "BITCOIN"]
    }

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

        search_terms = [generic]
        if generic.upper() in self.ALIASES:
            search_terms.extend(self.ALIASES[generic.upper()])

        # 1. Exact match (case-insensitive)
        for term in search_terms:
            if term in self._all_symbols:
                self._cache[generic] = term
                return term
            for sym in self._all_symbols:
                if sym.upper() == term.upper():
                    self._cache[generic] = sym
                    return sym

        # 2. Known Suffixes match
        for term in search_terms:
            for suffix in self.KNOWN_SUFFIXES:
                if not suffix: continue
                candidate = term + suffix
                if candidate in self._all_symbols:
                    self._cache[generic] = candidate
                    return candidate
                for sym in self._all_symbols:
                    if sym.upper() == candidate.upper():
                        self._cache[generic] = sym
                        return sym

        # 3. Startswith match
        for term in search_terms:
            for sym in self._all_symbols:
                if sym.upper().startswith(term.upper()):
                    self._cache[generic] = sym
                    return sym
                    
        # 4. Contains match
        for term in search_terms:
            for sym in self._all_symbols:
                if term.upper() in sym.upper():
                    self._cache[generic] = sym
                    return sym
                
        return None

    def resolve_many(self, generics: list[str]) -> dict[str, str | None]:
        return {g: self.resolve(g) for g in generics}
