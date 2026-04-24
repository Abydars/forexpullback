import re

with open("app/engine/scanner.py", "r") as f:
    content = f.read()

# We need to extract from "for generic in symbols:" down to "updates_to_broadcast.append({" before "dca_candidates ="
match = re.search(r'(\s*)for generic in symbols:\n(.*?)(\s*)dca_candidates = ', content, re.DOTALL)
if not match:
    print("Could not match symbol loop")
    exit(1)

indent = match.group(1)
loop_body = match.group(2)
post_indent = match.group(3)

# The loop_body contains the logic for one symbol.
# We need to wrap it in a function.
# The body relies on variables: symbols, symbol_resolver, cfg, binance_client, bot_positions, max_open, max_symbol, max_dir, scanner_state, now_utc, max_dca_entries

# Let's write the new function:
new_func_def = """
            async def scan_symbol(generic):
                candidates_local = []
                updates_local = []
"""
# adjust indentation
adjusted_body = ""
for line in loop_body.split("\n"):
    if line.startswith(indent + "    "):
        # Replace candidates.append with candidates_local.append
        line = line.replace("candidates.append", "candidates_local.append")
        # Replace updates_to_broadcast.append with updates_local.append
        line = line.replace("updates_to_broadcast.append", "updates_local.append")
        adjusted_body += line + "\n"

adjusted_body += indent + "        return updates_local, candidates_local\n\n"

# The execution part
exec_part = """
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
"""

new_content = content[:match.start()] + new_func_def + adjusted_body + exec_part + post_indent + "dca_candidates = " + content[match.end():]

with open("app/engine/scanner.py", "w") as f:
    f.write(new_content)

print("Scanner refactored successfully.")
