const state = {
  binance_connected: false,
  engine_running: false,
  account: null,
  today_pnl: 0,
  open_positions: [],
  closed_trades: [],
  recent_signals: [],
  all_signals: [],
  events: [],
  equity_series: [],
  config: {},
  sessions: [],
  symbols: [],
  scanner_status: {},
};

// ---- WS ----
let ws;
function connectWS() {
  ws = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws`);
  ws.onopen = () => { setInterval(() => ws.readyState === 1 && ws.send('{"type":"ping"}'), 20000); };
  ws.onmessage = (e) => handleEvent(JSON.parse(e.data));
  ws.onclose = (e) => {
      if (e.code === 1008) window.location.href = '/login';
      else setTimeout(connectWS, 2000);
  };
}

function handleEvent(msg) {
  switch (msg.type) {
    case 'binance.connection':  state.binance_connected = msg.state === 'connected'; renderTopbar(); break;
    case 'account.tick':    state.account = msg; renderTopbar(); renderStats(); break;
    case 'scan.update':     updateScanStatus(msg.data); break;
    case 'signal.new':      state.recent_signals.unshift(msg.signal); state.all_signals.unshift(msg.signal); renderSignals(); break;
    case 'trade.opened':    renderStats(); break;
    case 'trade.closed':    moveToClosed(msg.trade); renderTrades(); renderStats(); break;
    case 'positions.update':
        state.open_positions = msg.positions.map(p => ({
            ticket: p.ticket,
            symbol: p.symbol,
            direction: p.type === 0 ? 'buy' : 'sell',
            quantity: p.volume,
            entry_price: p.price_open,
            current_price: p.price_current,
            pnl: p.profit,
            sl: p.sl,
            tp: p.tp
        }));
        if (msg.basket_state) {
            const badge = document.getElementById('s-basket-badge');
            if (badge) {
                if (msg.basket_state.active) {
                    badge.classList.remove('hidden');
                    badge.innerText = `TRAIL: $${msg.basket_state.peak_pnl.toFixed(2)}`;
                } else {
                    badge.classList.add('hidden');
                }
            }
        }
        renderPositions();
        renderStats();
        break;
    case 'log.event':       state.events.unshift(msg); renderLogs(); break;
    case 'engine.status':   state.engine_running = msg.state === 'active'; renderEngineBtn(); break;
    case 'symbols.dynamic_update': renderDynamicSymbols(msg.data); break;
  }
}

function renderDynamicSymbols(data) {
  const { symbols, source_mode, updated_at, metadata } = data;
  document.getElementById('scan-universe-meta').innerText = `Mode: ${source_mode.toUpperCase()} (Refreshed ${new Date(updated_at).toLocaleTimeString()})`;
  document.getElementById('scan-universe-chips').innerHTML = symbols.map(s => {
    let html = `<span class="px-2 py-1 bg-black/20 border border-border_strong rounded flex items-center gap-2">`;
    html += `<span class="font-bold text-slate-200">${s}</span>`;
    const m = metadata && metadata[s];
    if (m) {
        if (m.reason === 'manual_include') {
           html += `<span class="text-[8px] text-cyan-500 uppercase">INCLUDED</span>`;
        } else {
           const dir = m.priceChangePercent >= 0 ? 'text-emerald-400' : 'text-rose-400';
           html += `<span class="${dir}">${m.priceChangePercent > 0 ? '+' : ''}${m.priceChangePercent.toFixed(1)}%</span>`;
        }
    }
    html += `</span>`;
    return html;
  }).join('');
}

function replaceTrade(trade) {
  // Deprecated
}

function moveToClosed(trade) {
  state.closed_trades.unshift(trade);
  state.today_pnl += trade.pnl || 0;
}

// ---- REST helpers ----
async function api(method, path, body) {
  const res = await fetch(path, {
    method,
    headers: body ? {'Content-Type': 'application/json'} : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    if (res.status === 401) window.location.href = '/login';
    throw new Error(await res.text());
  }
  return res.json();
}

// ---- Tabs ----
document.querySelectorAll('.tab').forEach(t => t.onclick = () => {
  document.querySelectorAll('.tab').forEach(x => {
    x.classList.remove('text-white', 'border-cyan-400');
    x.classList.add('text-slate-400', 'border-transparent');
  });
  document.querySelectorAll('.tab-panel').forEach(x => x.classList.remove('active'));
  t.classList.remove('text-slate-400', 'border-transparent');
  t.classList.add('text-white', 'border-cyan-400');
  document.querySelector(`.tab-panel[data-panel="${t.dataset.tab}"]`).classList.add('active');
});

document.querySelectorAll('.m-tab').forEach(t => t.onclick = () => {
  document.querySelectorAll('.m-tab').forEach(x => {
    x.classList.remove('bg-cyan-500/10', 'text-cyan-400', 'border-cyan-500/20', 'shadow-sm');
    x.classList.add('text-slate-400', 'border-transparent');
  });
  document.querySelectorAll('.m-panel').forEach(x => x.classList.remove('active'));
  t.classList.remove('text-slate-400', 'border-transparent');
  t.classList.add('bg-cyan-500/10', 'text-cyan-400', 'border-cyan-500/20', 'shadow-sm');
  document.querySelector(`.m-panel[data-mpanel="${t.dataset.mtab}"]`).classList.add('active');
});

document.querySelectorAll('.sub-tab').forEach(t => t.onclick = () => {
  document.querySelectorAll('.sub-tab').forEach(x => {
    x.classList.remove('text-cyan-400', 'border-cyan-400', 'active');
    x.classList.add('text-slate-500', 'border-transparent');
  });
  t.classList.remove('text-slate-500', 'border-transparent');
  t.classList.add('text-cyan-400', 'border-cyan-400', 'active');
  renderTrades();
});


// ---- Renderers (each idempotent, rebuild target) ----
function renderTopbar() {
  document.getElementById('binance-dot').className = `w-2 h-2 rounded-full inline-block ${state.binance_connected ? "bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.8)]" : "bg-rose-500"}`;
  document.getElementById('binance-info').innerText = state.binance_connected ? (state.account?.testnet ? 'Connected (Testnet)' : 'Connected (Live)') : 'Not connected';
  document.getElementById('active-sessions').innerText = state.sessions.filter(s => s.enabled).length;
  document.getElementById('today-pnl').innerText = `${state.today_pnl < 0 ? '-' : ''}$${Math.abs(state.today_pnl).toFixed(2)}`;
  document.getElementById('today-pnl').className = state.today_pnl >= 0 ? 'text-emerald-400 font-bold' : 'text-rose-400 font-bold';
}

function renderEngineBtn() {
  const btn = document.getElementById('engine-toggle');
  btn.innerText = state.engine_running ? 'STOP' : 'START';
  btn.className = state.engine_running ? 'px-4 py-1.5 rounded bg-cyan-500 text-black font-bold text-[11px] uppercase tracking-widest shadow-[0_0_15px_rgba(6,182,212,0.4)]' : 'px-4 py-1.5 rounded border border-slate-700 text-slate-300 hover:bg-white/5 text-[11px] uppercase tracking-widest';
}

function renderStats() {
  document.getElementById('s-balance').innerText = state.account ? `$${state.account.balance.toFixed(2)}` : '—';
  document.getElementById('s-equity').innerText = state.account ? `$${state.account.equity.toFixed(2)}` : '—';
  
  const unrealized = state.open_positions.reduce((sum, t) => sum + (t.pnl || 0), 0);
  const unEl = document.getElementById('s-unrealized');
  if (unEl) {
      unEl.innerText = `${unrealized < 0 ? '-' : ''}$${Math.abs(unrealized).toFixed(2)}`;
      unEl.className = `text-2xl ${unrealized > 0 ? 'text-emerald-400' : unrealized < 0 ? 'text-rose-400' : 'text-slate-100'}`;
  }
  
  const sToday = document.getElementById('s-today');
  if (sToday) {
      sToday.innerText = `${state.today_pnl < 0 ? '-' : ''}$${Math.abs(state.today_pnl).toFixed(2)}`;
  }
  document.getElementById('s-open').innerText = state.open_positions.length;
}

function renderPositions() {
  const tbody = document.getElementById('open-pos-body');
  if (!state.open_positions.length) {
    tbody.innerHTML = '<tr><td colspan="9" class="text-center text-slate-500 py-10 uppercase tracking-widest text-xs">NO OPEN POSITIONS</td></tr>';
    return;
  }
  
  const groups = {};
  const sortedPos = [...state.open_positions].sort((a,b) => (a.ticket || 0) - (b.ticket || 0));
  
  sortedPos.forEach(t => {
    const key = `${t.symbol}_${t.direction}`;
    if (!groups[key]) {
      groups[key] = {
        symbol: t.symbol, direction: t.direction, total_lot: 0, total_pnl: 0,
        avg_entry: 0, count: 0, sl: t.sl, tp: t.tp, current_price: t.current_price,
        positions: []
      };
    }
    const g = groups[key];
    g.total_lot += t.quantity;
    g.total_pnl += (t.pnl || 0);
    g.avg_entry += (t.entry_price * t.quantity);
    g.count += 1;
    g.sl = t.sl || g.sl;
    g.tp = t.tp || g.tp;
    g.current_price = t.current_price || g.current_price;
    g.positions.push(t);
  });

  const html = [];
  Object.values(groups).forEach(g => {
    g.avg_entry = g.avg_entry / g.total_lot;
    const gKey = `${g.symbol}_${g.direction}`;
    
    html.push(`
      <tr class="group-row cursor-pointer hover:bg-white/[0.02] transition-colors group" onclick="document.querySelectorAll('.sub-${gKey}').forEach(e => e.classList.toggle('hidden'))">
        <td class="px-5 py-3 flex items-center gap-2">
          ${g.count > 1 ? `<span class="text-slate-500 group-hover:text-cyan-400 transition-colors text-[10px]">▶</span>` : ''}
          <span class="font-bold text-slate-200">${g.symbol}</span>
          ${g.count > 1 ? `<span class="px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-400 text-[9px] font-bold tracking-widest border border-cyan-500/20">GROUP (${g.count})</span>` : ''}
        </td>
        <td class="px-5 py-3"><span class="px-2 py-0.5 rounded text-[10px] font-bold tracking-widest uppercase ${g.direction === 'buy' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'}">${g.direction}</span></td>
        <td class="px-5 py-3 text-right font-mono">${g.total_lot.toFixed(2)}</td>
        <td class="px-5 py-3 text-right font-mono text-slate-400">${g.avg_entry.toFixed(5)}</td>
        <td class="px-5 py-3 text-right font-mono text-slate-400">${g.current_price || '-'}</td>
        <td class="px-5 py-3 text-right font-mono font-bold ${g.total_pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}">${g.total_pnl >= 0 ? '+' : '-'}$${Math.abs(g.total_pnl).toFixed(2)}</td>
        <td class="px-5 py-3 text-right font-mono text-slate-400">${g.sl || '-'}</td>
        <td class="px-5 py-3 text-right font-mono text-slate-400">${g.tp || '-'}</td>
        <td class="px-5 py-3 text-right">
          <button class="px-3 py-1.5 border border-border_strong text-slate-300 text-[10px] font-bold tracking-widest uppercase hover:bg-rose-500/10 hover:text-rose-400 hover:border-rose-500/30 transition-all rounded" onclick="event.stopPropagation(); closeGroup('${g.symbol}', '${g.direction}')">CLOSE ${g.count > 1 ? 'ALL' : ''}</button>
        </td>
      </tr>
    `);
    
    if (g.count > 1) {
      g.positions.forEach((p, idx) => {
        const badge = idx === 0 ? 'BASE' : `DCA ${idx}`;
        const badgeColor = idx === 0 ? 'text-amber-400 bg-amber-500/10 border-amber-500/20' : 'text-purple-400 bg-purple-500/10 border-purple-500/20';
        html.push(`
          <tr class="sub-${gKey} hidden bg-black/20 hover:bg-black/40 transition-colors text-[11px] border-b border-border_light/50">
            <td class="px-5 py-2 pl-10 flex items-center gap-2">
               <span class="px-1.5 py-0.5 rounded text-[8px] font-bold tracking-widest uppercase border ${badgeColor}">${badge}</span>
               <span class="text-slate-500 font-mono">#${p.ticket}</span>
            </td>
            <td class="px-5 py-2"></td>
            <td class="px-5 py-2 text-right font-mono text-slate-400">${p.quantity.toFixed(3)}</td>
            <td class="px-5 py-2 text-right font-mono text-slate-500">${p.entry_price.toFixed(5)}</td>
            <td class="px-5 py-2"></td>
            <td class="px-5 py-2 text-right font-mono ${p.pnl >= 0 ? 'text-emerald-500/70' : 'text-rose-500/70'}">${p.pnl >= 0 ? '+' : '-'}$${Math.abs(p.pnl).toFixed(2)}</td>
            <td class="px-5 py-2 text-right font-mono text-slate-500">${p.sl || '-'}</td>
            <td class="px-5 py-2 text-right font-mono text-slate-500">${p.tp || '-'}</td>
            <td class="px-5 py-2 text-right"></td>
          </tr>
        `);
      });
    }
  });

  tbody.innerHTML = html.join('');
}

function renderTrades() {
  const tbody = document.getElementById('trades-body');
  const activeSub = document.querySelector('.sub-tab.active').dataset.sub;
  const list = activeSub === 'open' ? state.open_positions : state.closed_trades;
  
  if (!list.length) {
    tbody.innerHTML = `<tr><td colspan="11" class="text-center text-slate-500 py-8 uppercase tracking-widest text-xs">NO ${activeSub.toUpperCase()} TRADES</td></tr>`;
    return;
  }
  
  if (activeSub === 'open') {
      const groups = {};
      list.forEach(t => {
        const key = `${t.symbol}_${t.direction}`;
        if (!groups[key]) {
          groups[key] = {
            symbol: t.symbol, direction: t.direction, total_lot: 0, total_pnl: 0,
            avg_entry: 0, count: 0, sl: t.sl, tp: t.tp, current_price: t.current_price, note: t.note
          };
        }
        const g = groups[key];
        g.total_lot += t.quantity;
        g.total_pnl += (t.pnl || 0);
        g.avg_entry += (t.entry_price * t.quantity);
        g.count += 1;
        g.sl = t.sl || g.sl;
        g.tp = t.tp || g.tp;
        if (g.count > 1) g.note = 'DCA GROUP';
      });

      const html = [];
      Object.values(groups).forEach(g => {
        g.avg_entry = g.avg_entry / g.total_lot;
        const gKey = `${g.symbol}_${g.direction}_trades`;
        
        html.push(`
          <tr class="group-row cursor-pointer hover:bg-white/[0.02] transition-colors group" onclick="document.querySelectorAll('.sub-${gKey}').forEach(e => e.classList.toggle('hidden'))">
            <td class="px-5 py-3 font-mono text-slate-500">-</td>
            <td class="px-5 py-3 flex items-center gap-2">
              ${g.count > 1 ? `<span class="text-slate-500 group-hover:text-cyan-400 transition-colors text-[10px]">▶</span>` : ''}
              <span class="font-bold text-slate-200">${g.symbol}</span>
              ${g.count > 1 ? `<span class="px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-400 text-[9px] font-bold tracking-widest border border-cyan-500/20">GROUP (${g.count})</span>` : ''}
            </td>
            <td class="px-5 py-3"><span class="px-2 py-0.5 rounded text-[10px] font-bold tracking-widest uppercase ${g.direction === 'buy' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'}">${g.direction}</span></td>
            <td class="px-5 py-3 text-right font-mono">${g.total_lot.toFixed(2)}</td>
            <td class="px-5 py-3 text-right font-mono text-slate-400">${g.avg_entry.toFixed(5)}</td>
            <td class="px-5 py-3 text-right font-mono text-slate-400">${g.sl || '-'}</td>
            <td class="px-5 py-3 text-right font-mono text-slate-400">${g.tp || '-'}</td>
            <td class="px-5 py-3 text-right font-mono text-slate-500">-</td>
            <td class="px-5 py-3 text-right font-mono font-bold ${g.total_pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}">${g.total_pnl >= 0 ? '+' : '-'}$${Math.abs(g.total_pnl).toFixed(2)}</td>
            <td class="px-5 py-3 text-slate-400">${g.note || '-'}</td>
            <td class="px-5 py-3 text-right"><button class="px-3 py-1.5 border border-border_strong text-slate-300 text-[10px] font-bold tracking-widest uppercase hover:bg-rose-500/10 hover:text-rose-400 hover:border-rose-500/30 transition-all rounded" onclick="event.stopPropagation(); closeGroup('${g.symbol}', '${g.direction}')">CLOSE ${g.count > 1 ? 'ALL' : ''}</button></td>
          </tr>
        `);
      });
      tbody.innerHTML = html.join('');
  } else {
      tbody.innerHTML = list.map(t => `
        <tr class="hover:bg-white/[0.02] transition-colors">
          <td class="px-5 py-3 font-mono text-slate-500 whitespace-nowrap">${new Date(t.opened_at || Date.now()).toLocaleTimeString()}</td>
          <td class="px-5 py-3 font-bold text-slate-200">${t.symbol}</td>
          <td class="px-5 py-3"><span class="px-2 py-0.5 rounded text-[10px] font-bold tracking-widest uppercase ${t.direction === 'buy' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'}">${t.direction}</span></td>
          <td class="px-5 py-3 text-right font-mono">${t.quantity}</td>
          <td class="px-5 py-3 text-right font-mono text-slate-400">${t.entry_price}</td>
          <td class="px-5 py-3 text-right font-mono text-slate-400">${t.sl || '-'}</td>
          <td class="px-5 py-3 text-right font-mono text-slate-400">${t.tp || '-'}</td>
          <td class="px-5 py-3 text-right font-mono text-slate-300">${t.exit_price || '-'}</td>
          <td class="px-5 py-3 text-right font-mono font-bold ${t.pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}" title="Commission: $${(t.commission || 0).toFixed(4)}">${t.pnl >= 0 ? '+' : '-'}$${Math.abs(t.pnl || 0).toFixed(2)}</td>
          <td class="px-5 py-3 text-slate-400">${t.note || '-'}</td>
          <td class="px-5 py-3 text-right"></td>
        </tr>
      `).join('');
  }
}

function renderSignals() {
  const tbody = document.getElementById('signals-body');
  if (!state.all_signals.length) {
    tbody.innerHTML = '<tr><td colspan="6" class="text-center text-slate-500 py-8 uppercase tracking-widest text-xs">NO SIGNALS</td></tr>';
    return;
  }
  const getStatusBadge = (status) => {
    let color = 'bg-white/5 text-slate-400 border-white/10';
    if (status === 'FIRED') color = 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30';
    else if (status === 'DCA_FIRED') color = 'bg-purple-500/20 text-purple-400 border-purple-500/30';
    else if (status === 'WATCHING') color = 'bg-amber-500/20 text-amber-400 border-amber-500/30';
    else if (status === 'SKIPPED' || status === 'DCA_SKIPPED') color = 'bg-blue-500/10 text-blue-400 border-blue-500/20';
    return `<span class="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-widest whitespace-nowrap border ${color}">${status}</span>`;
  };

  tbody.innerHTML = state.all_signals.map(s => {
    const isHighlight = s.status === 'FIRED' || s.status === 'DCA_FIRED';
    return `
      <tr class="${isHighlight ? 'bg-emerald-500/5 hover:bg-emerald-500/10' : 'hover:bg-white/[0.02]'} transition-colors">
        <td class="px-5 py-3 font-mono text-slate-500 whitespace-nowrap">${new Date(s.created_at || Date.now()).toLocaleTimeString()}</td>
        <td class="px-5 py-3 font-bold text-slate-200">${s.symbol}</td>
        <td class="px-5 py-3"><span class="px-2 py-0.5 rounded text-[10px] font-bold tracking-widest uppercase ${s.direction === 'buy' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'}">${s.direction}</span></td>
        <td class="px-5 py-3 text-right font-mono ${s.score > 0 ? 'text-cyan-400 font-bold' : 'text-slate-500'}">${s.score}</td>
        <td class="px-5 py-3">${getStatusBadge(s.status)}</td>
        <td class="px-5 py-3 text-slate-300 w-full">${JSON.stringify(s.reason)}</td>
      </tr>
    `;
  }).join('');
}

function renderLogs() {
  const tbody = document.getElementById('logs-body');
  if (!state.events.length) {
    tbody.innerHTML = '<tr><td colspan="4" class="text-center text-slate-500 py-8 uppercase tracking-widest text-xs">NO LOGS</td></tr>';
    return;
  }
  tbody.innerHTML = state.events.map(e => `
    <tr class="hover:bg-white/[0.02] transition-colors">
      <td class="px-5 py-3 font-mono text-slate-500 whitespace-nowrap">${new Date(e.created_at || Date.now()).toLocaleTimeString()}</td>
      <td class="px-5 py-3 font-bold ${e.level === 'ERROR' ? 'text-rose-400' : e.level === 'WARN' ? 'text-amber-400' : 'text-cyan-400'}">${e.level}</td>
      <td class="px-5 py-3 text-slate-300">${e.component}</td>
      <td class="px-5 py-3 text-slate-400 w-full">${e.message}</td>
    </tr>
  `).join('');
}

function updateScanStatus(data) {
  state.scanner_status[data.symbol] = data;
  renderScannerStatus();
}

function renderScannerStatus() {
  const tbody = document.getElementById('scan-status-body');
  const items = Object.values(state.scanner_status);
  
  // Sort items: FIRED > DCA_FIRED > WATCHING > SKIPPED > REJECTED > COOLDOWN
  const statusWeight = { 'FIRED': 6, 'DCA_FIRED': 5, 'WATCHING': 4, 'SKIPPED': 3, 'DCA_SKIPPED': 3, 'REJECTED': 2, 'COOLDOWN': 1 };
  items.sort((a, b) => (statusWeight[b.status] || 0) - (statusWeight[a.status] || 0));
  
  if (!items.length) {
    tbody.innerHTML = '<tr><td colspan="6" class="text-center text-slate-500 py-10 uppercase tracking-widest text-xs">WAITING FOR SCAN...</td></tr>';
    return;
  }
  
  const esc = (str) => String(str).replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  
  const getStatusBadge = (status) => {
    let color = 'bg-white/5 text-slate-400 border-white/10'; // Default muted (REJECTED, COOLDOWN, SKIPPED, DCA_SKIPPED)
    if (status === 'FIRED') color = 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30';
    else if (status === 'DCA_FIRED') color = 'bg-purple-500/20 text-purple-400 border-purple-500/30';
    else if (status === 'WATCHING') color = 'bg-amber-500/20 text-amber-400 border-amber-500/30';
    else if (status === 'SKIPPED' || status === 'DCA_SKIPPED') color = 'bg-blue-500/10 text-blue-400 border-blue-500/20';
    
    return `<span class="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-widest whitespace-nowrap border ${color}">${status}</span>`;
  };
  
  tbody.innerHTML = items.map(s => {
    let reasonText = s.reason.msg || '';
    if (s.status === 'FIRED' || s.status === 'DCA_FIRED') reasonText = 'Signal Triggered!';
    
    const rawReason = esc(JSON.stringify(s.reason));
    const isHighlight = s.status === 'FIRED' || s.status === 'DCA_FIRED';
    
    return `
    <tr class="${isHighlight ? 'bg-emerald-500/5 hover:bg-emerald-500/10' : 'hover:bg-white/[0.02]'} transition-colors">
      <td class="px-5 py-3 flex items-center gap-2">
        <span class="font-bold text-slate-200">${s.symbol}</span> 
        <span class="text-slate-500 font-mono text-[9px] border border-border_strong px-1 rounded">${s.resolved}</span>
      </td>
      <td class="px-5 py-3"><span class="px-2 py-0.5 rounded text-[10px] font-bold tracking-widest uppercase ${s.bias === 'bullish' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : s.bias === 'bearish' ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20' : 'bg-white/5 text-slate-400 border border-white/10'}">${s.bias || 'NONE'}</span></td>
      <td class="px-5 py-3 text-right font-mono ${s.score > 0 ? 'text-cyan-400 font-bold' : 'text-slate-500'}">${s.score}</td>
      <td class="px-5 py-3">${getStatusBadge(s.status)}</td>
      <td class="px-5 py-3 text-slate-300" style="max-width: 300px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="${rawReason}">
        ${esc(reasonText)}
      </td>
      <td class="px-5 py-3 font-mono text-slate-500 text-right w-24 shrink-0">${new Date(s.updated_at).toLocaleTimeString()}</td>
    </tr>
    `;
  }).join('');
}

// ---- Actions ----
async function toggleEngine() {
  try {
    if (state.engine_running) {
      await api('POST', '/api/engine/stop');
    } else {
      await api('POST', '/api/engine/start');
    }
    const status = await api('GET', '/api/status');
    state.engine_running = status.engine_running;
    renderEngineBtn();
  } catch (err) {
    console.error(err);
  }
}

async function closeTrade(ticket) {
  if (confirm(`Close trade ${ticket}?`)) {
    try {
      await api('POST', `/api/trades/${ticket}/close`);
    } catch (err) {
      console.error(err);
    }
  }
}

async function closeGroup(symbol, direction) {
  const groupTrades = state.open_positions.filter(t => t.symbol === symbol && t.direction === direction);
  if (!groupTrades.length) return;
  
  const msg = groupTrades.length > 1 
    ? `Close ALL ${groupTrades.length} grouped positions for ${symbol}?` 
    : `Close position for ${symbol}?`;
    
  if (confirm(msg)) {
    for (const t of groupTrades) {
      try {
        await api('POST', `/api/trades/${t.ticket}/close`);
      } catch (e) {
        console.error("Error closing", t.ticket, e);
      }
    }
  }
}

async function closeAllPositions() {
  if (state.open_positions.length === 0) return;
  if (confirm(`Close all ${state.open_positions.length} open positions?`)) {
    for (const t of state.open_positions) {
      try {
        await api('POST', `/api/trades/${t.ticket}/close`);
      } catch (e) {
        console.error("Error closing", t.ticket, e);
      }
    }
  }
}

// ---- Modals ----
function openBinanceModal() { document.getElementById('binance-modal').showModal(); }
function closeBinanceModal() { document.getElementById('binance-modal').close(); }

async function saveBinance() {
  document.getElementById('m-status').innerText = 'Connecting...';
  document.getElementById('m-status').className = '';
  try {
    const res = await api('POST', '/api/binance/link', {
      api_key: document.getElementById('m-api-key').value,
      api_secret: document.getElementById('m-api-secret').value,
      testnet: document.getElementById('m-testnet').checked
    });
    document.getElementById('m-status').innerText = 'Success!';
    document.getElementById('m-status').className = 'text-emerald-500';
    setTimeout(() => {
        closeBinanceModal();
        api('GET', '/api/status').then(status => {
            Object.assign(state, status);
            renderTopbar(); renderStats();
        });
    }, 1000);
  } catch (err) {
    document.getElementById('m-status').innerText = err.message;
    document.getElementById('m-status').className = 'text-rose-500';
  }
}

async function loadConfig() {
  try {
    const cfg = await api('GET', '/api/config');
    state.config = cfg;
    document.getElementById('c-max_open_positions').value = cfg.max_open_positions || 5;
    document.getElementById('c-max_signals_per_scan').value = cfg.max_signals_per_scan || 1;
    document.getElementById('c-max_per_symbol').value = cfg.max_per_symbol || 1;
    document.getElementById('c-max_per_direction').value = cfg.max_per_direction || 3;
    document.getElementById('c-max_spread_pct').value = cfg.max_spread_pct || 20.0;
    document.getElementById('c-signal_threshold').value = cfg.signal_threshold || 65;
    document.getElementById('c-risk_percent').value = cfg.risk_percent || 1.0;
    document.getElementById('c-scan_interval_seconds').value = cfg.scan_interval_seconds || 10;
    document.getElementById('c-signal_cooldown_minutes').value = cfg.signal_cooldown_minutes || 30;
    document.getElementById('c-reward_ratio').value = cfg.reward_ratio || 2.0;
    document.getElementById('c-dashboard_password').value = cfg.dashboard_password || 'admin';
    
    document.getElementById('c-default_leverage').value = cfg.default_leverage || 10;
    document.getElementById('c-margin_type').value = cfg.margin_type || 'ISOLATED';

    document.getElementById('c-atr_buffer_multiplier').value = cfg.atr_buffer_multiplier || 0.2;
    document.getElementById('c-use_liquidity_tp').checked = cfg.use_liquidity_tp !== false;
    document.getElementById('c-breakeven_trigger_r').value = cfg.breakeven_trigger_r || 1.0;
    document.getElementById('c-trailing').checked = cfg.trailing !== false;
    
    document.getElementById('c-enable_dca').checked = cfg.enable_dca === true;
    document.getElementById('c-max_dca_entries').value = cfg.max_dca_entries || 1;
    document.getElementById('c-max_dca_per_scan').value = cfg.max_dca_per_scan || 2;
    document.getElementById('c-dca_trigger_sl_progress').value = cfg.dca_trigger_sl_progress || 0.5;
    document.getElementById('c-dca_lot_multiplier').value = cfg.dca_lot_multiplier || 0.7;
    document.getElementById('c-dca_max_total_risk_r').value = cfg.dca_max_total_risk_r || 2.0;
    document.getElementById('c-dca_reanchor_sl').checked = cfg.dca_reanchor_sl !== false;
    
    document.getElementById('c-enable_basket_trailing').checked = cfg.enable_basket_trailing === true;
    document.getElementById('c-basket_trailing_start_usd').value = cfg.basket_trailing_start_usd || 5.0;
    document.getElementById('c-basket_trailing_drawdown_usd').value = cfg.basket_trailing_drawdown_usd || 1.5;
    document.getElementById('c-basket_trailing_min_close_usd').value = cfg.basket_trailing_min_close_usd || 5.0;
    
    document.getElementById('c-symbol_source_mode').value = cfg.symbol_source_mode || 'manual';
    document.getElementById('c-manual_symbols').value = (cfg.manual_symbols || ['BTCUSDT', 'ETHUSDT']).join(', ');
    document.getElementById('c-dynamic_symbol_limit').value = cfg.dynamic_symbol_limit || 10;
    document.getElementById('c-min_24h_quote_volume_usdt').value = cfg.min_24h_quote_volume_usdt || 50000000;
    document.getElementById('c-exclude_symbols').value = (cfg.exclude_symbols || []).join(', ');
    document.getElementById('c-include_symbols').value = (cfg.include_symbols || []).join(', ');
    document.getElementById('c-use_only_usdt_perpetuals').checked = cfg.use_only_usdt_perpetuals !== false;
    document.getElementById('c-refresh_dynamic_symbols_minutes').value = cfg.refresh_dynamic_symbols_minutes || 15;
    
    const combined = cfg.combined_sources || ["top_movers_24h", "top_volume_24h"];
    document.querySelectorAll('.c-combined_sources').forEach(cb => {
      cb.checked = combined.includes(cb.value);
    });
    
    toggleSymbolMode();
    
    const sessions = await api('GET', '/api/sessions');
    state.sessions = sessions;
    document.getElementById('sessions-list').innerHTML = '';
    sessions.forEach(s => addSessionRow(s));
  } catch (err) { console.error(err); }
}

function openConfigModal() { loadConfig(); document.getElementById('config-modal').showModal(); }
function closeConfigModal() { document.getElementById('config-modal').close(); }

function toggleSymbolMode() {
  const mode = document.getElementById('c-symbol_source_mode').value;
  document.getElementById('manual_symbols_container').style.display = (mode === 'manual') ? 'block' : 'none';
  document.getElementById('combined_sources_container').style.display = (mode === 'combined') ? 'block' : 'none';
}

async function previewSymbols() {
  const cfg = collectConfigInputs();
  const res = document.getElementById('preview_symbols_result');
  res.innerHTML = '<div class="text-[10px] text-slate-400">Loading...</div>';
  try {
    const data = await api('POST', '/api/symbols/preview', cfg);
    res.innerHTML = `
      <table class="w-full text-left text-[10px] font-mono mt-2">
        <thead class="text-cyan_neon uppercase border-b border-border_strong">
          <tr><th>Symbol</th><th>24h %</th><th>Vol (USDT)</th><th>Range %</th><th>Score</th><th>Reason</th></tr>
        </thead>
        <tbody class="divide-y divide-border_strong/50 text-slate-300">
          ${data.map(t => `
            <tr>
              <td class="py-1">${t.symbol}</td>
              <td class="py-1 ${t.priceChangePercent > 0 ? 'text-emerald-400' : 'text-rose-400'}">${t.priceChangePercent.toFixed(2)}%</td>
              <td class="py-1">${(t.quoteVolume / 1000000).toFixed(1)}M</td>
              <td class="py-1">${t.range_pct.toFixed(2)}%</td>
              <td class="py-1">${t.rank_score.toFixed(1)}</td>
              <td class="py-1 text-slate-500">${t.reason || ''}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    `;
  } catch (err) {
    res.innerHTML = '<div class="text-[10px] text-rose-500">Error loading preview</div>';
  }
}

// Sessions repeater
const IANA_ZONES = ['UTC','Europe/London','America/New_York','Asia/Tokyo','Asia/Dubai','Asia/Karachi','Asia/Singapore','Australia/Sydney'];
function addSessionRow(session) {
  const id = session?.id ?? ('new-' + Date.now());
  const html = `
    <div class="session-row flex flex-col md:flex-row gap-4 items-start md:items-center p-4 border border-border_light bg-white/[0.02] rounded hover:bg-white/[0.04] transition-colors" data-id="${id}">
      <div class="w-full md:w-32 shrink-0 flex flex-col gap-1.5">
         <span class="text-[9px] uppercase tracking-widest text-slate-500 font-bold hidden md:block">Name</span>
         <input placeholder="SESSION NAME" class="s-name bg-black/20 border border-border_strong text-slate-200 text-xs px-3 py-2 rounded outline-none focus:border-cyan_neon w-full" value="${session?.name ?? ''}">
      </div>
      <div class="w-full md:w-24 shrink-0 flex flex-col gap-1.5">
         <span class="text-[9px] uppercase tracking-widest text-slate-500 font-bold hidden md:block">Start (UTC)</span>
         <input type="time" class="s-start bg-black/20 border border-border_strong text-slate-200 text-xs px-3 py-2 rounded outline-none focus:border-cyan_neon w-full" value="${session?.start_time ?? '08:00'}">
      </div>
      <div class="w-full md:w-24 shrink-0 flex flex-col gap-1.5">
         <span class="text-[9px] uppercase tracking-widest text-slate-500 font-bold hidden md:block">End (UTC)</span>
         <input type="time" class="s-end bg-black/20 border border-border_strong text-slate-200 text-xs px-3 py-2 rounded outline-none focus:border-cyan_neon w-full" value="${session?.end_time ?? '12:00'}">
      </div>
      <div class="w-full md:w-32 shrink-0 flex flex-col gap-1.5">
         <span class="text-[9px] uppercase tracking-widest text-slate-500 font-bold hidden md:block">Timezone</span>
         <select class="s-tz bg-black/20 border border-border_strong text-slate-200 text-[10px] px-2 py-2 rounded outline-none focus:border-cyan_neon w-full">${IANA_ZONES.map(z => `<option ${z === (session?.timezone ?? 'UTC') ? 'selected' : ''}>${z}</option>`).join('')}</select>
      </div>
      <div class="flex-1 flex flex-col gap-1.5 min-w-[120px]">
         <span class="text-[9px] uppercase tracking-widest text-slate-500 font-bold hidden md:block">Days</span>
         <div class="day-checks flex gap-1 justify-between bg-black/10 border border-border_strong p-1 rounded">${['M','T','W','T','F','S','S'].map((d,i) => `
           <label class="flex flex-col items-center gap-1 text-[9px] text-slate-500 cursor-pointer hover:text-slate-300 w-full text-center"><input type="checkbox" data-day="${i}" class="w-3 h-3 accent-cyan_neon cursor-pointer" ${!session || (session?.days_mask & (1<<i)) ? 'checked' : ''}>${d}</label>
         `).join('')}</div>
      </div>
      <div class="shrink-0 flex items-center justify-between md:flex-col md:items-end gap-2 w-full md:w-auto mt-2 md:mt-0">
        <label class="flex items-center gap-2 text-[10px] font-bold text-slate-300 uppercase shrink-0 cursor-pointer group"><input type="checkbox" class="s-on w-4 h-4 accent-cyan_neon cursor-pointer bg-black/20 border-border_strong group-hover:border-cyan_neon" ${session?.enabled !== false ? 'checked' : ''}> ENABLED</label>
        <button type="button" class="px-2 py-1 text-slate-500 hover:text-rose-400 hover:bg-rose-500/10 border border-transparent hover:border-rose-500/30 rounded text-[10px] font-bold tracking-widest uppercase transition-all shrink-0" onclick="this.closest('.session-row').remove()">DELETE</button>
      </div>
    </div>`;
  document.getElementById('sessions-list').insertAdjacentHTML('beforeend', html);
}

function collectConfigInputs() {
  return {
    max_open_positions: parseInt(document.getElementById('c-max_open_positions').value),
    max_signals_per_scan: parseInt(document.getElementById('c-max_signals_per_scan').value),
    max_per_symbol: parseInt(document.getElementById('c-max_per_symbol').value),
    max_per_direction: parseInt(document.getElementById('c-max_per_direction').value),
    max_spread_pct: parseFloat(document.getElementById('c-max_spread_pct').value),
    signal_threshold: parseInt(document.getElementById('c-signal_threshold').value),
    risk_percent: parseFloat(document.getElementById('c-risk_percent').value),
    scan_interval_seconds: parseInt(document.getElementById('c-scan_interval_seconds').value),
    signal_cooldown_minutes: parseInt(document.getElementById('c-signal_cooldown_minutes').value),
    reward_ratio: parseFloat(document.getElementById('c-reward_ratio').value),
    dashboard_password: document.getElementById('c-dashboard_password').value,
    default_leverage: parseInt(document.getElementById('c-default_leverage').value),
    margin_type: document.getElementById('c-margin_type').value,
    atr_buffer_multiplier: parseFloat(document.getElementById('c-atr_buffer_multiplier').value),
    use_liquidity_tp: document.getElementById('c-use_liquidity_tp').checked,
    breakeven_trigger_r: parseFloat(document.getElementById('c-breakeven_trigger_r').value),
    trailing: document.getElementById('c-trailing').checked,
    enable_dca: document.getElementById('c-enable_dca').checked,
    max_dca_entries: parseInt(document.getElementById('c-max_dca_entries').value),
    max_dca_per_scan: parseInt(document.getElementById('c-max_dca_per_scan').value),
    dca_trigger_sl_progress: parseFloat(document.getElementById('c-dca_trigger_sl_progress').value),
    dca_lot_multiplier: parseFloat(document.getElementById('c-dca_lot_multiplier').value),
    dca_max_total_risk_r: parseFloat(document.getElementById('c-dca_max_total_risk_r').value),
    dca_reanchor_sl: document.getElementById('c-dca_reanchor_sl').checked,
    enable_basket_trailing: document.getElementById('c-enable_basket_trailing').checked,
    basket_trailing_start_usd: parseFloat(document.getElementById('c-basket_trailing_start_usd').value),
    basket_trailing_drawdown_usd: parseFloat(document.getElementById('c-basket_trailing_drawdown_usd').value),
    basket_trailing_min_close_usd: parseFloat(document.getElementById('c-basket_trailing_min_close_usd').value),
    
    symbol_source_mode: document.getElementById('c-symbol_source_mode').value,
    manual_symbols: document.getElementById('c-manual_symbols').value.split(',').map(s=>s.trim()).filter(Boolean),
    dynamic_symbol_limit: parseInt(document.getElementById('c-dynamic_symbol_limit').value),
    min_24h_quote_volume_usdt: parseFloat(document.getElementById('c-min_24h_quote_volume_usdt').value),
    exclude_symbols: document.getElementById('c-exclude_symbols').value.split(',').map(s=>s.trim()).filter(Boolean),
    include_symbols: document.getElementById('c-include_symbols').value.split(',').map(s=>s.trim()).filter(Boolean),
    use_only_usdt_perpetuals: document.getElementById('c-use_only_usdt_perpetuals').checked,
    refresh_dynamic_symbols_minutes: parseInt(document.getElementById('c-refresh_dynamic_symbols_minutes').value),
    combined_sources: Array.from(document.querySelectorAll('.c-combined_sources:checked')).map(cb => cb.value),
  };
}

async function syncSessions() {
  const rows = document.querySelectorAll('.session-row');
  const payload = Array.from(rows).map(row => {
    let days_mask = 0;
    row.querySelectorAll('.day-checks input:checked').forEach(cb => {
      days_mask |= (1 << parseInt(cb.dataset.day));
    });
    const id = row.dataset.id.startsWith('new-') ? null : parseInt(row.dataset.id);
    return {
      id,
      name: row.querySelector('.s-name').value,
      start_time: row.querySelector('.s-start').value,
      end_time: row.querySelector('.s-end').value,
      timezone: row.querySelector('.s-tz').value,
      days_mask,
      enabled: row.querySelector('.s-on').checked
    };
  });
  
  await api('PUT', '/api/sessions', payload);
}

async function saveConfig() {
  await api('PATCH', '/api/config', collectConfigInputs());
  await syncSessions();
  closeConfigModal();
}

// ---- Init ----
async function init() {
  connectWS();
  try {
    const [status, initData] = await Promise.all([
      api('GET', '/api/status'),
      api('GET', '/api/initial_data').catch(() => null)
    ]);
    Object.assign(state, status);
    
    if (initData) {
      state.open_positions = initData.trades.filter(t => !t.closed_at);
      state.closed_trades = initData.trades.filter(t => t.closed_at);
      state.all_signals = initData.signals;
      state.recent_signals = initData.signals.slice(0, 5);
      state.events = initData.events;
      
      const todayStr = new Date().toISOString().split('T')[0];
      state.today_pnl = state.closed_trades
        .filter(t => t.closed_at && t.closed_at.startsWith(todayStr))
        .reduce((sum, t) => sum + (t.pnl || 0), 0);
        
      if (initData.current_universe && initData.current_universe.symbols && initData.current_universe.symbols.length > 0) {
        renderDynamicSymbols(initData.current_universe);
      }
    }
  } catch (err) { console.error("Init Error:", err); }
  
  renderTopbar(); renderStats(); renderEngineBtn();
  renderPositions(); renderTrades(); renderSignals(); renderLogs();
}
init();

function promptImportJSON() {
  document.getElementById("json-input").value = "";
  document.getElementById("json-modal").showModal();
}

function applyImportedJSON() {
  const jsonStr = document.getElementById("json-input").value;
  if (!jsonStr.trim()) return;
  try {
    const data = JSON.parse(jsonStr);
    for (const [key, value] of Object.entries(data)) {
      const el = document.getElementById("c-" + key);
      if (el) {
        if (el.type === "checkbox") {
          el.checked = (value === true || value === "true" || value === "True");
        } else {
          el.value = value;
        }
      }
    }
    document.getElementById("json-modal").close();
    // Re-render UI elements to show the updated values
    const mpanels = document.querySelectorAll('.m-panel');
    mpanels.forEach(p => {
       const inputs = p.querySelectorAll('input');
       inputs.forEach(inp => {
          const ev = new Event('input', { bubbles: true });
          inp.dispatchEvent(ev);
       });
    });
  } catch (e) {
    alert("Invalid JSON format:\n" + e.message);
  }
}

