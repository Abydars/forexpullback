import re

def update_app_js():
    with open('app/static/app.js', 'r') as f:
        content = f.read()
    
    # Update tabs
    content = content.replace("document.querySelectorAll('.tab').forEach(x => x.classList.remove('active'));",
                              "document.querySelectorAll('.tab').forEach(x => { x.classList.remove('text-white', 'border-cyan-400'); x.classList.add('text-slate-400', 'border-transparent'); });")
    content = content.replace("t.classList.add('active');",
                              "t.classList.remove('text-slate-400', 'border-transparent'); t.classList.add('text-white', 'border-cyan-400');")
                              
    # Update m-tabs
    content = content.replace("document.querySelectorAll('.m-tab').forEach(x => x.classList.remove('active'));",
                              "document.querySelectorAll('.m-tab').forEach(x => { x.classList.remove('bg-cyan-500/10', 'text-cyan-400', 'border-cyan-500/20', 'shadow-sm'); x.classList.add('text-slate-400', 'border-transparent'); });")
    content = content.replace("t.classList.add('active');",
                              "t.classList.remove('text-slate-400', 'border-transparent'); t.classList.add('bg-cyan-500/10', 'text-cyan-400', 'border-cyan-500/20', 'shadow-sm');")

    # Colors
    content = content.replace("'g' : 'r'", "'text-emerald-400' : 'text-rose-400'")
    content = content.replace("? 'g' : s.bias === 'bearish' ? 'r' : ''", "? 'bg-emerald-500/20 text-emerald-400' : s.bias === 'bearish' ? 'bg-rose-500/20 text-rose-400' : ''")
    content = content.replace("=== 'ERROR' ? 'r' : e.level === 'WARN' ? 'amber' : 'c'", "=== 'ERROR' ? 'text-rose-400' : e.level === 'WARN' ? 'text-amber-400' : 'text-cyan-400'")
    content = content.replace("=== 'FIRED' ? 'g' : 'amber'", "=== 'FIRED' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-amber-500/20 text-amber-400'")
    
    # Pills
    content = re.sub(r'class="pill \$\{([^}]+)\}"', r'class="px-2 py-0.5 rounded-sm text-[10px] font-bold uppercase tracking-widest ${\1}"', content)
    content = re.sub(r'class="pill"', r'class="px-2 py-0.5 rounded-sm text-[10px] font-bold uppercase tracking-widest"', content)
    
    # Engine btn
    content = content.replace("btn.className = `btn ${state.engine_running ? 'primary' : ''}`;",
                              "btn.className = state.engine_running ? 'px-4 py-1.5 rounded bg-cyan-500 text-black font-bold text-[11px] uppercase tracking-widest shadow-[0_0_15px_rgba(6,182,212,0.4)]' : 'px-4 py-1.5 rounded border border-slate-700 text-slate-300 hover:bg-white/5 text-[11px] uppercase tracking-widest';")

    # Empty rows
    content = content.replace('class="empty"', 'class="text-center text-slate-500 py-8 uppercase tracking-widest text-xs"')
    
    # Dot
    content = content.replace('className = `dot ${state.mt5_connected ? \'on\' : \'\'}`', 
                              'className = `w-2 h-2 rounded-full inline-block ${state.mt5_connected ? "bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.8)]" : "bg-rose-500"}`')
                              
    with open('app/static/app.js', 'w') as f:
        f.write(content)
        
update_app_js()
