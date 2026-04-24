import re
with open("app/engine/scanner.py", "r") as f:
    text = f.read()

# 1. Fix the top of the loop to use Binance positions and start timer:
top_replacement = """        try:
            import time
            scan_start = time.time()
            await symbol_resolver.refresh()
                
            from app.engine.symbol_universe import symbol_universe
            symbols = await symbol_universe.get_symbols(cfg)
            
            max_signals_per_scan = int(cfg.get("max_signals_per_scan", 1))
            max_open = int(cfg.get("max_open_positions", 5))
            max_symbol = int(cfg.get("max_per_symbol", 1))
            max_dir = int(cfg.get("max_per_direction", 3))
            
            raw_positions = await binance_client.get_positions()
            active_symbols_sides = set((p['symbol'], p['positionSide']) for p in raw_positions if abs(float(p['positionAmt'])) > 0)
            
            async with AsyncSessionLocal() as db:
                res_pos = await db.execute(select(Trade).where(Trade.closed_at == None))
                all_open_trades = res_pos.scalars().all()
                bot_positions = [t for t in all_open_trades if (t.symbol, t.position_side) in active_symbols_sides]
                
            candidates = []
            updates_to_broadcast = []
"""

# replace up to `bot_positions = []`
pattern = r'        try:\n.*?bot_positions = \[\]\n.*?res_pos\.scalars\(\)\.all\(\)\n.*?updates_to_broadcast = \[\]\n'
text = re.sub(pattern, top_replacement, text, flags=re.DOTALL)

# 2. Extract loop body
loop_pattern = r'            for generic in symbols:\n(.*?)            dca_candidates = '
match = re.search(loop_pattern, text, flags=re.DOTALL)
if match:
    loop_body = match.group(1)
    
    # We replace the loop body with a function
    lines = loop_body.split("\n")
    # All lines start with at least 16 spaces ("            ")
    # Inside the function we need them to be indented properly.
    # Since they are inside an async def which is at 12 spaces, 16 spaces is fine!
    
    new_loop_body = []
    for line in lines:
        if "candidates.append" in line:
            line = line.replace("candidates.append", "candidates_local.append")
        if "updates_to_broadcast.append" in line:
            if "else:" in lines[lines.index(line)-2] and "is_dca = c.get" in lines[lines.index(line)-1]:
                # Skip the one in the execute block which is AFTER the loop! Wait, the loop body ends at dca_candidates!
                pass
            line = line.replace("updates_to_broadcast.append", "updates_local.append")
        new_loop_body.append(line)
        
    func_body = "\n".join(new_loop_body)
    
    func_def = """            async def scan_symbol(generic):
                candidates_local = []
                updates_local = []
""" + func_body + """                return updates_local, candidates_local

            max_concurrent = int(cfg.get("max_concurrent_symbol_scans", 5))
            sem = asyncio.Semaphore(max_concurrent)
            
            async def bounded_scan(generic):
                async with sem:
                    try:
                        return await scan_symbol(generic)
                    except Exception as e:
                        print(f"Error scanning {generic}: {e}")
                        return [], []
                        
            scan_tasks = [bounded_scan(sym) for sym in symbols]
            results = await asyncio.gather(*scan_tasks)
            
            for upd, cand in results:
                updates_to_broadcast.extend(upd)
                candidates.extend(cand)
            
            dca_candidates = """
            
    text = text[:match.start()] + func_def + text[match.end()-17:]
    

# 3. Add latency logs to execute block and fix send_order call
exec_pattern = r'(                        from app\.engine\.order_manager import send_order\n)(.*?)(                else:)'
exec_replacement = r'''\1                        
                        order_start = time.time()
                        await send_order(sig, res, bias, c["cfg"], is_dca=is_dca, dca_data=ltf_trigger if is_dca else None, signal_detected_at=signal_detected_at)
                        order_end = time.time()
                        
                        print(f"[LATENCY] Signal found for {res} at {time.time()-scan_start:.2f}s | Order executed in {order_end-order_start:.2f}s")
\3'''
text = re.sub(exec_pattern, exec_replacement, text, flags=re.DOTALL)

# Add signal_detected_at = time.time()
text = text.replace('scanner_state[state_key] = {"time": now_utc, "status": status}', 'scanner_state[state_key] = {"time": now_utc, "status": status}\n                    signal_detected_at = time.time()')

# Add latency log for full scan cycle
text = text.replace('await asyncio.sleep(interval)', 'print(f"[LATENCY] Full scan cycle for {len(symbols)} symbols completed in {time.time()-scan_start:.2f}s")\n            await asyncio.sleep(interval)', 1)

with open("app/engine/scanner.py", "w") as f:
    f.write(text)
print("done")
