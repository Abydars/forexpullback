from backend.mt5_client.client import MT5Client
from datetime import datetime

class SymbolResolver:
    KNOWN_SUFFIXES = ["", "m", "c", "z", ".r", "_raw", ".m", ".c", "-pro", ".pro", "pro", ".ecn"]

    def __init__(self, mt5_client: MT5Client):
        self._client = mt5_client
        self._cache = {}       # generic -> resolved name
        self._cache_meta = {}  # generic -> symbol info dict
        self._all_symbols = set()
        self._symbol_infos = {}

    def refresh(self) -> None:
        """Pull all broker symbols via mt5.symbols_get() and rebuild the index."""
        if not self._client.is_connected():
            return

        symbols = self._client.symbols_get()
        self._all_symbols = set()
        self._symbol_infos = {}
        for s in symbols:
            self._all_symbols.add(s.name)
            self._symbol_infos[s.name] = s
        
        self._cache.clear()
        self._cache_meta.clear()

    def resolve(self, generic: str) -> str | None:
        if not generic:
            return None
            
        if generic in self._cache:
            return self._cache[generic]

        if not self._all_symbols:
            self.refresh()

        generic_upper = generic.upper()
        
        # 1. Exact match
        if generic_upper in self._all_symbols:
            self._cache[generic] = generic_upper
            return generic_upper
            
        # 2. generic + known suffix
        for suffix in self.KNOWN_SUFFIXES:
            variant = f"{generic_upper}{suffix}"
            if variant in self._all_symbols:
                self._cache[generic] = variant
                return variant
                
        # 3. generic + lowercase suffix
        for suffix in self.KNOWN_SUFFIXES:
            variant = f"{generic_upper}{suffix.lower()}"
            if variant in self._all_symbols:
                self._cache[generic] = variant
                return variant

        # Fallback (longest prefix match)
        # Not implementing full longest-prefix match unless needed, as above covers most Exness cases
        
        self._cache[generic] = None
        return None

    def get_info(self, generic: str):
        resolved = self.resolve(generic)
        if resolved and resolved in self._symbol_infos:
            s = self._symbol_infos[resolved]
            return {
                "generic": generic,
                "resolved": resolved,
                "digits": s.digits,
                "point": s.point,
                "contract_size": s.trade_contract_size,
                "min_lot": s.volume_min,
                "max_lot": s.volume_max,
                "lot_step": s.volume_step
            }
        return None

    def resolve_many(self, generics: list[str]) -> dict[str, str | None]:
        return {g: self.resolve(g) for g in generics}

from backend.mt5_client.client import mt5_client
symbol_resolver = SymbolResolver(mt5_client)
