import re
from typing import Dict, List, Optional
from mt5_client.client import MT5Client, mt5_client

class SymbolResolver:
    def __init__(self, client: MT5Client):
        self.client = client
        self.broker_symbols = []
        self.cache: Dict[str, str] = {}
        
    def refresh(self):
        if not self.client.is_connected(): return
        syms = self.client.symbols_get()
        if syms:
            self.broker_symbols = [s.name for s in syms]
            self.cache.clear()

    def resolve(self, generic: str) -> Optional[str]:
        if generic in self.cache:
            return self.cache[generic]
            
        if not self.broker_symbols:
            self.refresh()
            
        # Exact match
        if generic in self.broker_symbols:
            self.cache[generic] = generic
            return generic
            
        # Suffix matching
        suffixes = ["m", "c", ".r", "pro", ""]
        for s in suffixes:
            guess = f"{generic}{s}"
            if guess in self.broker_symbols:
                self.cache[generic] = guess
                return guess
                
        return None

    def resolve_many(self, generics: List[str]) -> Dict[str, Optional[str]]:
        return {g: self.resolve(g) for g in generics}

symbol_resolver = SymbolResolver(mt5_client)
