import asyncio
import time
import math
from datetime import datetime, timezone
from app.binance_client.client import binance_client
from app.engine.scanner import calculate_htf_bias
from app.ws.manager import broadcast

class SymbolUniverseBuilder:
    def __init__(self):
        self.last_refresh = 0
        self.cached_universe = []
        self.last_metadata = {}
        self.last_mode = "manual"
        
        
    async def get_symbols(self, cfg: dict) -> list[str]:
        mode = cfg.get("symbol_source_mode", "manual")
        manual_symbols = cfg.get("manual_symbols", ["BTCUSDT", "ETHUSDT"])
        
        if mode == "manual":
            return manual_symbols
            
        refresh_mins = float(cfg.get("refresh_dynamic_symbols_minutes", 15))
        if time.time() - self.last_refresh < refresh_mins * 60 and self.cached_universe:
            return self.cached_universe
            
        try:
            new_universe = await self.build_scan_symbols(cfg)
            self.cached_universe = new_universe
            self.last_refresh = time.time()
            return new_universe
        except Exception as e:
            print(f"Failed to build dynamic universe: {e}")
            return manual_symbols if not self.cached_universe else self.cached_universe

    async def build_scan_symbols(self, cfg: dict) -> list[str]:
        limit = int(cfg.get("dynamic_symbol_limit", 10))
        min_vol = float(cfg.get("min_24h_quote_volume_usdt", 50000000))
        exclude = set(cfg.get("exclude_symbols", []))
        include = set(cfg.get("include_symbols", []))
        use_only_usdt = cfg.get("use_only_usdt_perpetuals", True)
        mode = cfg.get("symbol_source_mode", "top_volume_24h")
        combined_sources = cfg.get("combined_sources", ["top_movers_24h", "top_volume_24h"])

        if not binance_client.symbols_cache:
            await binance_client._fetch_exchange_info()
            
        exchange_info = binance_client.symbols_cache
        
        valid_symbols = set()
        for sym, info in exchange_info.items():
            if info.get('status') != 'TRADING': continue
            if use_only_usdt:
                if info.get('quoteAsset') != 'USDT': continue
                if info.get('contractType') != 'PERPETUAL': continue
            if sym in exclude: continue
            valid_symbols.add(sym)
            
        tickers = await binance_client.get_24hr_tickers()
        
        filtered_tickers = []
        for t in tickers:
            sym = t['symbol']
            if sym not in valid_symbols: continue
            
            qv = float(t.get('quoteVolume', 0))
            if qv < min_vol: continue
            
            high = float(t.get('highPrice', 0))
            low = float(t.get('lowPrice', 0))
            last = float(t.get('lastPrice', 0))
            
            range_pct = 0
            if last > 0:
                range_pct = (high - low) / last * 100
                
            pc = float(t.get('priceChangePercent', 0))
                
            filtered_tickers.append({
                'symbol': sym,
                'quoteVolume': qv,
                'priceChangePercent': pc,
                'absChange': abs(pc),
                'range_pct': range_pct,
                'rank_score': 0
            })
            
        if not filtered_tickers:
            return list(include)
            
        # Modes mapping
        async def fetch_source(source_mode, tick_list):
            if source_mode == "top_gainers_24h":
                return sorted(tick_list, key=lambda x: x['priceChangePercent'], reverse=True)[:limit]
            elif source_mode == "top_losers_24h":
                return sorted(tick_list, key=lambda x: x['priceChangePercent'])[:limit]
            elif source_mode == "top_movers_24h":
                return sorted(tick_list, key=lambda x: x['absChange'], reverse=True)[:limit]
            elif source_mode == "top_volume_24h":
                return sorted(tick_list, key=lambda x: x['quoteVolume'], reverse=True)[:limit]
            elif source_mode == "high_volatility":
                return sorted(tick_list, key=lambda x: x['range_pct'], reverse=True)[:limit]
            elif source_mode in ("trending_up", "trending_down"):
                # We need to fetch candles
                vol_sorted = sorted(tick_list, key=lambda x: x['quoteVolume'], reverse=True)[:max(50, limit * 2)]
                trending = []
                for t in vol_sorted:
                    sym = t['symbol']
                    df_4h, df_1h = await asyncio.gather(
                        binance_client.get_rates(sym, 'H4', 250),
                        binance_client.get_rates(sym, 'H1', 250)
                    )
                    if df_4h.empty or df_1h.empty: continue
                    htf = calculate_htf_bias(df_4h, df_1h)
                    if source_mode == "trending_up" and htf['bias'] == 'bullish':
                        trending.append(t)
                    elif source_mode == "trending_down" and htf['bias'] == 'bearish':
                        trending.append(t)
                    if len(trending) >= limit:
                        break
                return trending
            return []
            
        if mode == "combined":
            # calculate dynamic ranking score
            filtered_tickers.sort(key=lambda x: x['quoteVolume'], reverse=True)
            for i, t in enumerate(filtered_tickers):
                t['vol_rank_score'] = max(0, 100 - i * (100 / len(filtered_tickers)))
                
            filtered_tickers.sort(key=lambda x: x['absChange'], reverse=True)
            for i, t in enumerate(filtered_tickers):
                t['change_rank_score'] = max(0, 100 - i * (100 / len(filtered_tickers)))
                
            filtered_tickers.sort(key=lambda x: x['range_pct'], reverse=True)
            for i, t in enumerate(filtered_tickers):
                t['volat_rank_score'] = max(0, 100 - i * (100 / len(filtered_tickers)))
                
                # Update total score based on weights
                t['rank_score'] = (t['change_rank_score'] * 0.4) + (t['vol_rank_score'] * 0.4) + (t['volat_rank_score'] * 0.2)
                
            combined_pool = {}
            for src in combined_sources:
                res = await fetch_source(src, filtered_tickers)
                for t in res:
                    combined_pool[t['symbol']] = t
                    
            final_list = list(combined_pool.values())
            final_list.sort(key=lambda x: x['rank_score'], reverse=True)
            selected = final_list[:limit]
        else:
            selected = await fetch_source(mode, filtered_tickers)
            
        final_symbols = [s['symbol'] for s in selected]
        
        # Always include manual inclusions
        for s in include:
            s_up = s.upper().strip()
            if s_up not in final_symbols and s_up in exchange_info:
                final_symbols.append(s_up)
                selected.append({
                    'symbol': s_up,
                    'priceChangePercent': 0,
                    'quoteVolume': 0,
                    'range_pct': 0,
                    'rank_score': 0,
                    'reason': 'manual_include'
                })
                
        # Prepare metadata for broadcast
        meta = {}
        for item in selected:
            if 'reason' not in item:
                item['reason'] = mode
            meta[item['symbol']] = item
            
        self.last_metadata = meta
        self.last_mode = mode
        
        await broadcast({
            "type": "symbols.dynamic_update",
            "data": {
                "symbols": final_symbols,
                "source_mode": mode,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "metadata": meta
            }
        })
        
        return final_symbols

symbol_universe = SymbolUniverseBuilder()
