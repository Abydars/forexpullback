const state = {
  mt5_connected: false,
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
    case 'mt5.connection':  state.mt5_connected = msg.state === 'connected'; renderTopbar(); break;
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
            lot: p.volume,
            entry_price: p.price_open,
            current_price: p.price_current,
            pnl: p.profit,
            sl: p.sl,
            tp: p.tp
        }));
        renderPositions();
        renderStats();
        break;
    case 'log.event':       state.events.unshift(msg); renderLogs(); break;
    case 'engine.status':   state.engine_running = msg.state === 'active'; renderEngineBtn(); break;
  }
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
  document.getElementById('mt5-dot').className = `w-2 h-2 rounded-full inline-block ${state.mt5_connected ? "bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.8)]" : "bg-rose-500"}`;
  document.getElementById('mt5-info').innerText = state.mt5_connected ? (state.account?.server || 'Connected') : 'Not connected';
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
    tbody.innerHTML = '<tr><td colspan="9" class="text-center text-slate-500 py-8 uppercase tracking-widest text-xs">NO OPEN POSITIONS</td></tr>';
    return;
  }
  
  const groups = {};
  state.open_positions.forEach(t => {
    const key = `${t.symbol}_${t.direction}`;
    if (!groups[key]) {
      groups[key] = {
        symbol: t.symbol, direction: t.direction, total_lot: 0, total_pnl: 0,
        avg_entry: 0, count: 0, sl: t.sl, tp: t.tp, current_price: t.current_price
      };
    }
    const g = groups[key];
    g.total_lot += t.lot;
    g.total_pnl += (t.pnl || 0);
    g.avg_entry += (t.entry_price * t.lot);
    g.count += 1;
    g.sl = t.sl || g.sl;
    g.tp = t.tp || g.tp;
    g.current_price = t.current_price || g.current_price;
  });

  const groupedArray = Object.values(groups).map(g => {
    g.avg_entry = g.avg_entry / g.total_lot;
    return g;
  });

  tbody.innerHTML = groupedArray.map(g => `
    <tr>
      <td>${g.symbol} ${g.count > 1 ? `<span class="px-2 py-0.5 rounded-sm text-[10px] font-bold uppercase tracking-widest" style="margin-left:6px; background:rgba(77,208,225,0.1); color:var(--cyan);">GROUP (${g.count})</span>` : ''}</td>
      <td><span class="px-2 py-0.5 rounded-sm text-[10px] font-bold uppercase tracking-widest ${g.direction === 'buy' ? 'text-emerald-400' : 'text-rose-400'}">${g.direction}</span></td>
      <td>${g.total_lot.toFixed(2)}</td>
      <td>${g.avg_entry.toFixed(5)}</td>
      <td>${g.current_price || '-'}</td>
      <td class="${g.total_pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}">${g.total_pnl.toFixed(2)}</td>
      <td>${g.sl || '-'}</td>
      <td>${g.tp || '-'}</td>
      <td><button class="btn" style="padding:2px 8px; font-size:10px;" onclick="closeGroup('${g.symbol}', '${g.direction}')">CLOSE ${g.count > 1 ? 'ALL' : ''}</button></td>
    </tr>
  `).join('');
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
        g.total_lot += t.lot;
        g.total_pnl += (t.pnl || 0);
        g.avg_entry += (t.entry_price * t.lot);
        g.count += 1;
        g.sl = t.sl || g.sl;
        g.tp = t.tp || g.tp;
        if (g.count > 1) g.note = 'DCA GROUP';
      });

      const groupedArray = Object.values(groups).map(g => {
        g.avg_entry = g.avg_entry / g.total_lot;
        return g;
      });

      tbody.innerHTML = groupedArray.map(t => `
        <tr>
          <td>-</td>
          <td>${t.symbol} ${t.count > 1 ? `<span class="px-2 py-0.5 rounded-sm text-[10px] font-bold uppercase tracking-widest" style="margin-left:6px; background:rgba(77,208,225,0.1); color:var(--cyan);">GROUP (${t.count})</span>` : ''}</td>
          <td><span class="px-2 py-0.5 rounded-sm text-[10px] font-bold uppercase tracking-widest ${t.direction === 'buy' ? 'text-emerald-400' : 'text-rose-400'}">${t.direction}</span></td>
          <td>${t.total_lot.toFixed(2)}</td>
          <td>${t.avg_entry.toFixed(5)}</td>
          <td>${t.sl || '-'}</td>
          <td>${t.tp || '-'}</td>
          <td>-</td>
          <td class="${t.total_pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}">${t.total_pnl.toFixed(2)}</td>
          <td>${t.note || '-'}</td>
          <td><button class="btn" onclick="closeGroup('${t.symbol}', '${t.direction}')">CLOSE ${t.count > 1 ? 'ALL' : ''}</button></td>
        </tr>
      `).join('');
  } else {
      tbody.innerHTML = list.map(t => `
        <tr>
          <td>${new Date(t.opened_at || Date.now()).toLocaleTimeString()}</td>
          <td>${t.symbol}</td>
          <td><span class="px-2 py-0.5 rounded-sm text-[10px] font-bold uppercase tracking-widest ${t.direction === 'buy' ? 'text-emerald-400' : 'text-rose-400'}">${t.direction}</span></td>
          <td>${t.lot}</td>
          <td>${t.entry_price}</td>
          <td>${t.sl || '-'}</td>
          <td>${t.tp || '-'}</td>
          <td>${t.exit_price || '-'}</td>
          <td class="${t.pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}">${t.pnl?.toFixed(2) || '-'}</td>
          <td>${t.note || '-'}</td>
          <td></td>
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
  tbody.innerHTML = state.all_signals.map(s => `
    <tr>
      <td>${new Date(s.created_at || Date.now()).toLocaleTimeString()}</td>
      <td>${s.symbol}</td>
      <td><span class="px-2 py-0.5 rounded-sm text-[10px] font-bold uppercase tracking-widest ${s.direction === 'buy' ? 'text-emerald-400' : 'text-rose-400'}">${s.direction}</span></td>
      <td>${s.score}</td>
      <td><span class="px-2 py-0.5 rounded-sm text-[10px] font-bold uppercase tracking-widest ${s.status === 'FIRED' ? 'bg-emerald-500/20 text-emerald-400' : s.status === 'REJECTED' ? 'bg-white/5 text-slate-400' : 'bg-amber-500/20 text-amber-400'}">${s.status}</span></td>
      <td>${JSON.stringify(s.reason)}</td>
    </tr>
  `).join('');
}

function renderLogs() {
  const tbody = document.getElementById('logs-body');
  if (!state.events.length) {
    tbody.innerHTML = '<tr><td colspan="4" class="text-center text-slate-500 py-8 uppercase tracking-widest text-xs">NO LOGS</td></tr>';
    return;
  }
  tbody.innerHTML = state.events.map(e => `
    <tr>
      <td>${new Date(e.created_at || Date.now()).toLocaleTimeString()}</td>
      <td class="${e.level === 'ERROR' ? 'text-rose-400' : e.level === 'WARN' ? 'text-amber-400' : 'text-cyan-400'}">${e.level}</td>
      <td>${e.component}</td>
      <td>${e.message}</td>
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
  if (!items.length) {
    tbody.innerHTML = '<tr><td colspan="6" class="text-center text-slate-500 py-8 uppercase tracking-widest text-xs">WAITING FOR SCAN...</td></tr>';
    return;
  }
  
  tbody.innerHTML = items.map(s => {
    let reasonText = s.reason.msg || '';
    if (s.status === 'FIRED') reasonText = 'Signal Triggered!';
    
    // Clean up reason text safely
    const esc = (str) => String(str).replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    const rawReason = esc(JSON.stringify(s.reason));
    
    return `
    <tr>
      <td>${s.symbol} <span style="color:var(--muted); font-size:10px;">(${s.resolved})</span></td>
      <td><span class="px-2 py-0.5 rounded-sm text-[10px] font-bold uppercase tracking-widest ${s.bias === 'bullish' ? 'bg-emerald-500/20 text-emerald-400' : s.bias === 'bearish' ? 'bg-rose-500/20 text-rose-400' : ''}">${s.bias}</span></td>
      <td>${s.score}</td>
      <td><span class="px-2 py-0.5 rounded-sm text-[10px] font-bold uppercase tracking-widest ${s.status === 'FIRED' ? 'bg-emerald-500/20 text-emerald-400' : s.status === 'REJECTED' ? 'bg-white/5 text-slate-400' : 'bg-amber-500/20 text-amber-400'}">${s.status}</span></td>
      <td style="max-width: 300px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="${rawReason}">
        ${esc(reasonText)}
      </td>
      <td>${new Date(s.updated_at).toLocaleTimeString()}</td>
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
async function loadSavedAccounts() {
  try {
    const accs = await api('GET', '/api/mt5/accounts');
    document.getElementById('saved-accounts').innerHTML = accs.map(a => `
      <div style="padding: 8px; border: 1px solid var(--border); margin-bottom: 8px; display:flex; justify-content:space-between; cursor:pointer;"
           onclick="document.getElementById('m-server').value='${a.server}'; document.getElementById('m-login').value='${a.login}';">
        <span>${a.server}</span><span>${a.login}</span>
      </div>
    `).join('');
  } catch(err) { console.error(err); }
}

function openMt5Modal() { loadSavedAccounts(); document.getElementById('mt5-modal').showModal(); }
function closeMt5Modal() { document.getElementById('mt5-modal').close(); }

async function testMt5() {
  document.getElementById('m-status').innerText = 'Testing...';
  try {
    const res = await api('POST', '/api/mt5/connect', {
      server: document.getElementById('m-server').value,
      login: parseInt(document.getElementById('m-login').value),
      password: document.getElementById('m-password').value,
      path: document.getElementById('m-path').value || undefined
    });
    document.getElementById('m-status').innerText = 'Success!';
    document.getElementById('m-status').className = 'g';
    document.getElementById('m-save').disabled = false;
  } catch (err) {
    document.getElementById('m-status').innerText = err.message;
    document.getElementById('m-status').className = 'r';
  }
}
async function saveMt5() { 
  closeMt5Modal(); 
  const status = await api('GET', '/api/status');
  Object.assign(state, status);
  renderTopbar(); renderStats();
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
    document.getElementById('c-reward_ratio').value = cfg.reward_ratio || 2.0;
    document.getElementById('c-dashboard_password').value = cfg.dashboard_password || 'admin';

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
    
    state.symbols = (cfg.symbols || []).map(s => ({generic: s, resolved: null, status: 'pending'}));
    renderChips();
    resolveAllSymbols();
    
    const sessions = await api('GET', '/api/sessions');
    state.sessions = sessions;
    document.getElementById('sessions-list').innerHTML = '';
    sessions.forEach(s => addSessionRow(s));
  } catch (err) { console.error(err); }
}

function openConfigModal() { loadConfig(); document.getElementById('config-modal').showModal(); }
function closeConfigModal() { document.getElementById('config-modal').close(); }

// Symbols chips
function addSymbols() {
  const raw = document.getElementById('sym-input').value;
  const parts = raw.split(/[,\n]/).map(s => s.trim().toUpperCase()).filter(Boolean);
  parts.forEach(p => {
    if (!state.symbols.find(s => s.generic === p))
      state.symbols.push({generic: p, resolved: null, status: 'pending'});
  });
  document.getElementById('sym-input').value = '';
  renderChips();
  resolveAllSymbols();
}

async function resolveAllSymbols() {
  const generics = state.symbols.map(s => s.generic);
  if (!generics.length) return;
  try {
    const { map } = await api('POST', '/api/symbols/resolve', { generics });
    state.symbols = state.symbols.map(s => ({
      ...s, resolved: map[s.generic], status: map[s.generic] ? 'resolved' : 'unresolved'
    }));
    renderChips();
  } catch(err) { console.error(err); }
}

function renderChips() {
  document.getElementById('sym-chips').innerHTML = state.symbols.map(s => `
    <span class="flex items-center gap-2 px-3 py-1 rounded bg-panel border ${s.status === 'resolved' ? 'border-emerald-500/30 text-emerald-400' : s.status === 'pending' ? 'border-amber-500/30 text-amber-400' : 'border-rose-500/30 text-rose-400'} text-xs font-mono">
      ${s.generic}${s.resolved ? ' → ' + s.resolved + ' ✓' : ' ✗'}
      <span class="cursor-pointer text-slate-500 hover:text-white px-1" onclick="removeSymbol('${s.generic}')">×</span>
    </span>
  `).join('');
}

function removeSymbol(generic) {
  state.symbols = state.symbols.filter(s => s.generic !== generic);
  renderChips();
}

// Sessions repeater
const IANA_ZONES = ['UTC','Europe/London','America/New_York','Asia/Tokyo','Asia/Dubai','Asia/Karachi','Asia/Singapore','Australia/Sydney'];
function addSessionRow(session) {
  const id = session?.id ?? ('new-' + Date.now());
  const html = `
    <div class="session-row flex flex-col md:flex-row gap-3 items-start md:items-center p-3 border border-border_light bg-white/[0.02] rounded-sm" data-id="${id}">
      <input placeholder="NAME" class="s-name bg-bg border border-border_strong text-slate-200 text-xs px-3 py-1.5 rounded-sm outline-none focus:border-cyan_neon w-full md:w-auto flex-1" value="${session?.name ?? ''}">
      <input type="time" class="s-start bg-bg border border-border_strong text-slate-200 text-xs px-3 py-1.5 rounded-sm outline-none focus:border-cyan_neon" value="${session?.start_time ?? '08:00'}">
      <input type="time" class="s-end bg-bg border border-border_strong text-slate-200 text-xs px-3 py-1.5 rounded-sm outline-none focus:border-cyan_neon" value="${session?.end_time ?? '12:00'}">
      <select class="s-tz bg-bg border border-border_strong text-slate-200 text-[10px] px-2 py-1.5 rounded-sm outline-none focus:border-cyan_neon w-28">${IANA_ZONES.map(z => `<option ${z === (session?.timezone ?? 'UTC') ? 'selected' : ''}>${z}</option>`).join('')}</select>
      <div class="day-checks flex gap-1">${['M','T','W','T','F','S','S'].map((d,i) => `
        <label class="flex flex-col items-center gap-1 text-[9px] text-slate-500 cursor-pointer hover:text-slate-300"><input type="checkbox" data-day="${i}" class="w-3 h-3 accent-cyan_neon cursor-pointer" ${!session || (session?.days_mask & (1<<i)) ? 'checked' : ''}>${d}</label>
      `).join('')}</div>
      <label class="flex items-center gap-2 text-[10px] font-bold text-slate-300 uppercase shrink-0"><input type="checkbox" class="s-on w-4 h-4 accent-cyan_neon cursor-pointer" ${session?.enabled !== false ? 'checked' : ''}>ON</label>
      <button type="button" class="px-2 py-1 text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 rounded transition-colors shrink-0" onclick="this.closest('.session-row').remove()">×</button>
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
    reward_ratio: parseFloat(document.getElementById('c-reward_ratio').value),
    dashboard_password: document.getElementById('c-dashboard_password').value,
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
  await api('PATCH', '/api/config', { symbols: state.symbols.filter(s => s.status !== 'unresolved').map(s => s.generic) });
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
    }
  } catch (err) { console.error("Init Error:", err); }
  
  renderTopbar(); renderStats(); renderEngineBtn();
  renderPositions(); renderTrades(); renderSignals(); renderLogs();
}
init();
