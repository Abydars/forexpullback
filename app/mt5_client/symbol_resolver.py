import asyncio
import MetaTrader5 as mt5

class SymbolResolver:
    KNOWN_SUFFIXES = ["", "m", "c", "z", ".r", "_raw", ".m", ".c", "-pro", ".pro", "pro", ".ecn", ".cash", "-cash"]
    
    ALIASES = {
        "US500": ["US500", "SPX500", "SP500", "SPX", "US500.cash", "SP500.cash"],
        "USTEC": ["USTEC", "NAS100", "NDX100", "US100", "USTEC.cash", "NAS100.cash"],
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

    def _find_matches(self, generic: str) -> list[str]:
        search_terms = [generic]
        if generic.upper() in self.ALIASES:
            search_terms.extend(self.ALIASES[generic.upper()])

        matches = []
        
        # 1. Exact match (case-insensitive)
        for term in search_terms:
            if term in self._all_symbols and term not in matches:
                matches.append(term)
            for sym in self._all_symbols:
                if sym.upper() == term.upper() and sym not in matches:
                    matches.append(sym)

        # 2. Known Suffixes match
        for term in search_terms:
            for suffix in self.KNOWN_SUFFIXES:
                if not suffix: continue
                candidate = term + suffix
                if candidate in self._all_symbols and candidate not in matches:
                    matches.append(candidate)
                for sym in self._all_symbols:
                    if sym.upper() == candidate.upper() and sym not in matches:
                        matches.append(sym)

        # 3. Contains match logic (extended)
        contains_terms = []
        if generic.upper() == "US500": contains_terms = ["500"]
        elif generic.upper() == "USTEC": contains_terms = ["TEC", "NAS", "100"]
        
        for term in search_terms + contains_terms:
            for sym in self._all_symbols:
                if term.upper() in sym.upper() and sym not in matches:
                    matches.append(sym)
                    
        return matches

    def resolve(self, generic: str) -> str | None:
        if generic in self._cache:
            return self._cache[generic]

        matches = self._find_matches(generic)
        for match in matches:
            if mt5.symbol_select(match, True):
                info = mt5.symbol_info(match)
                if info is not None:
                    self._cache[generic] = match
                    return match
        return None

    def resolve_detailed(self, generic: str) -> dict:
        if generic in self._cache:
            sym = self._cache[generic]
            info = mt5.symbol_info(sym)
            return {
                "generic": generic,
                "resolved": sym,
                "exists": True,
                "selected": True,
                "trade_mode": info.trade_mode if info else None,
                "visible": info.visible if info else None,
                "error": None
            }
            
        matches = self._find_matches(generic)
        for match in matches:
            selected = mt5.symbol_select(match, True)
            info = mt5.symbol_info(match)
            if selected and info is not None:
                self._cache[generic] = match
                return {
                    "generic": generic,
                    "resolved": match,
                    "exists": True,
                    "selected": True,
                    "trade_mode": info.trade_mode,
                    "visible": info.visible,
                    "error": None
                }
                
        error_reason = f"No valid symbol found. Checked: {matches[:5]}" if matches else "No matches found"
        return {
            "generic": generic,
            "resolved": None,
            "exists": False,
            "selected": False,
            "trade_mode": None,
            "visible": False,
            "error": error_reason
        }

    def resolve_many(self, generics: list[str]) -> dict:
        return {g: self.resolve_detailed(g) for g in generics}
