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
  ws.onclose = () => setTimeout(connectWS, 2000);
}

function handleEvent(msg) {
  switch (msg.type) {
    case 'mt5.connection':  state.mt5_connected = msg.state === 'connected'; renderTopbar(); break;
    case 'account.tick':    state.account = msg; renderTopbar(); renderStats(); break;
    case 'scan.update':     updateScanStatus(msg.data); break;
    case 'signal.new':      state.recent_signals.unshift(msg.signal); state.all_signals.unshift(msg.signal); renderSignals(); break;
    case 'trade.opened':    state.open_positions.push(msg.trade); renderPositions(); renderStats(); break;
    case 'trade.updated':   replaceTrade(msg.trade); renderPositions(); break;
    case 'trade.closed':    moveToClosed(msg.trade); renderPositions(); renderTrades(); renderStats(); break;
    case 'log.event':       state.events.unshift(msg); renderLogs(); break;
    case 'engine.status':   state.engine_running = msg.state === 'active'; renderEngineBtn(); break;
  }
}

function replaceTrade(trade) {
  const i = state.open_positions.findIndex(t => t.ticket === trade.ticket);
  if (i > -1) state.open_positions[i] = trade;
  else state.open_positions.push(trade);
}

function moveToClosed(trade) {
  state.open_positions = state.open_positions.filter(t => t.ticket !== trade.ticket);
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
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// ---- Tabs ----
document.querySelectorAll('.tab').forEach(t => t.onclick = () => {
  document.querySelectorAll('.tab').forEach(x => x.classList.remove('active'));
  document.querySelectorAll('.tab-panel').forEach(x => x.classList.remove('active'));
  t.classList.add('active');
  document.querySelector(`.tab-panel[data-panel="${t.dataset.tab}"]`).classList.add('active');
});

document.querySelectorAll('.m-tab').forEach(t => t.onclick = () => {
  document.querySelectorAll('.m-tab').forEach(x => x.classList.remove('active'));
  document.querySelectorAll('.m-panel').forEach(x => x.classList.remove('active'));
  t.classList.add('active');
  document.querySelector(`.m-panel[data-mpanel="${t.dataset.mtab}"]`).classList.add('active');
});

document.querySelectorAll('.sub-tab').forEach(t => t.onclick = () => {
  document.querySelectorAll('.sub-tab').forEach(x => x.classList.remove('active'));
  t.classList.add('active');
  renderTrades();
});


// ---- Renderers (each idempotent, rebuild target) ----
function renderTopbar() {
  document.getElementById('mt5-dot').className = `dot ${state.mt5_connected ? 'on' : ''}`;
  document.getElementById('mt5-info').innerText = state.mt5_connected ? (state.account?.server || 'Connected') : 'Not connected';
  document.getElementById('active-sessions').innerText = state.sessions.filter(s => s.enabled).length;
  document.getElementById('today-pnl').innerText = `$${state.today_pnl.toFixed(2)}`;
  document.getElementById('today-pnl').className = state.today_pnl >= 0 ? 'g' : 'r';
}

function renderEngineBtn() {
  const btn = document.getElementById('engine-toggle');
  btn.innerText = state.engine_running ? 'STOP' : 'START';
  btn.className = `btn ${state.engine_running ? 'primary' : ''}`;
}

function renderStats() {
  document.getElementById('s-balance').innerText = state.account ? `$${state.account.balance.toFixed(2)}` : '—';
  document.getElementById('s-equity').innerText = state.account ? `$${state.account.equity.toFixed(2)}` : '—';
  
  const unrealized = state.open_positions.reduce((sum, t) => sum + (t.pnl || 0), 0);
  const unEl = document.getElementById('s-unrealized');
  if (unEl) {
      unEl.innerText = `$${unrealized.toFixed(2)}`;
      unEl.className = `stat-value ${unrealized >= 0 ? 'g' : 'r'}`;
  }
  
  document.getElementById('s-today').innerText = `$${state.today_pnl.toFixed(2)}`;
  document.getElementById('s-open').innerText = state.open_positions.length;
}

function renderPositions() {
  const tbody = document.getElementById('open-pos-body');
  if (!state.open_positions.length) {
    tbody.innerHTML = '<tr><td colspan="9" class="empty">NO OPEN POSITIONS</td></tr>';
    return;
  }
  tbody.innerHTML = state.open_positions.map(t => `
    <tr>
      <td>${t.symbol}</td>
      <td><span class="pill ${t.direction === 'buy' ? 'g' : 'r'}">${t.direction}</span></td>
      <td>${t.lot}</td>
      <td>${t.entry_price}</td>
      <td>${t.current_price || '-'}</td>
      <td class="${t.pnl >= 0 ? 'g' : 'r'}">${t.pnl?.toFixed(2) || '0.00'}</td>
      <td>${t.sl || '-'}</td>
      <td>${t.tp || '-'}</td>
      <td><button class="btn" style="padding:2px 8px; font-size:10px;" onclick="closeTrade(${t.ticket})">CLOSE</button></td>
    </tr>
  `).join('');
}

function renderTrades() {
  const tbody = document.getElementById('trades-body');
  const activeSub = document.querySelector('.sub-tab.active').dataset.sub;
  const list = activeSub === 'open' ? state.open_positions : state.closed_trades;
  
  if (!list.length) {
    tbody.innerHTML = `<tr><td colspan="11" class="empty">NO ${activeSub.toUpperCase()} TRADES</td></tr>`;
    return;
  }
  
  tbody.innerHTML = list.map(t => `
    <tr>
      <td>${new Date(t.opened_at || Date.now()).toLocaleTimeString()}</td>
      <td>${t.symbol}</td>
      <td><span class="pill ${t.direction === 'buy' ? 'g' : 'r'}">${t.direction}</span></td>
      <td>${t.lot}</td>
      <td>${t.entry_price}</td>
      <td>${t.sl || '-'}</td>
      <td>${t.tp || '-'}</td>
      <td>${t.exit_price || '-'}</td>
      <td class="${t.pnl >= 0 ? 'g' : 'r'}">${t.pnl?.toFixed(2) || '-'}</td>
      <td>${t.note || '-'}</td>
      <td>${activeSub === 'open' ? `<button class="btn" onclick="closeTrade(${t.ticket})">CLOSE</button>` : ''}</td>
    </tr>
  `).join('');
}

function renderSignals() {
  const tbody = document.getElementById('signals-body');
  if (!state.all_signals.length) {
    tbody.innerHTML = '<tr><td colspan="6" class="empty">NO SIGNALS</td></tr>';
    return;
  }
  tbody.innerHTML = state.all_signals.map(s => `
    <tr>
      <td>${new Date(s.created_at || Date.now()).toLocaleTimeString()}</td>
      <td>${s.symbol}</td>
      <td><span class="pill ${s.direction === 'buy' ? 'g' : 'r'}">${s.direction}</span></td>
      <td>${s.score}</td>
      <td><span class="pill ${s.status === 'FIRED' ? 'g' : 'amber'}">${s.status}</span></td>
      <td>${JSON.stringify(s.reason)}</td>
    </tr>
  `).join('');
}

function renderLogs() {
  const tbody = document.getElementById('logs-body');
  if (!state.events.length) {
    tbody.innerHTML = '<tr><td colspan="4" class="empty">NO LOGS</td></tr>';
    return;
  }
  tbody.innerHTML = state.events.map(e => `
    <tr>
      <td>${new Date(e.created_at || Date.now()).toLocaleTimeString()}</td>
      <td class="${e.level === 'ERROR' ? 'r' : e.level === 'WARN' ? 'amber' : 'c'}">${e.level}</td>
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
    tbody.innerHTML = '<tr><td colspan="6" class="empty">WAITING FOR SCAN...</td></tr>';
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
      <td><span class="pill ${s.bias === 'bullish' ? 'g' : s.bias === 'bearish' ? 'r' : ''}">${s.bias}</span></td>
      <td>${s.score}</td>
      <td><span class="pill ${s.status === 'FIRED' ? 'g' : 'amber'}">${s.status}</span></td>
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
    document.getElementById('c-max_per_symbol').value = cfg.max_per_symbol || 1;
    document.getElementById('c-max_per_direction').value = cfg.max_per_direction || 3;
    document.getElementById('c-max_spread_pct').value = cfg.max_spread_pct || 20.0;
    document.getElementById('c-signal_threshold').value = cfg.signal_threshold || 65;
    document.getElementById('c-risk_percent').value = cfg.risk_percent || 1.0;
    document.getElementById('c-scan_interval_seconds').value = cfg.scan_interval_seconds || 10;
    document.getElementById('c-reward_ratio').value = cfg.reward_ratio || 2.0;

    document.getElementById('c-sl_mode').value = cfg.sl_mode || 'structural';
    document.getElementById('c-atr_multiplier').value = cfg.atr_multiplier || 1.5;
    document.getElementById('c-tp_mode').value = cfg.tp_mode || 'r_multiple';
    document.getElementById('c-breakeven_trigger_r').value = cfg.breakeven_trigger_r || 1.0;
    document.getElementById('c-trailing').checked = cfg.trailing !== false;
    document.getElementById('c-trailing_distance_pips').value = cfg.trailing_distance_pips || 15.0;
    
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
    <span class="chip ${s.status}">
      ${s.generic}${s.resolved ? ' → ' + s.resolved + ' ✓' : ' ✗'}
      <span class="x" onclick="removeSymbol('${s.generic}')">×</span>
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
    <div class="session-row" data-id="${id}">
      <input placeholder="NAME" class="s-name" value="${session?.name ?? ''}">
      <input type="time" class="s-start" value="${session?.start_time ?? '08:00'}">
      <input type="time" class="s-end" value="${session?.end_time ?? '12:00'}">
      <select class="s-tz">${IANA_ZONES.map(z => `<option ${z === (session?.timezone ?? 'UTC') ? 'selected' : ''}>${z}</option>`).join('')}</select>
      <div class="day-checks">${['M','T','W','T','F','S','S'].map((d,i) => `
        <label><input type="checkbox" data-day="${i}" ${!session || (session?.days_mask & (1<<i)) ? 'checked' : ''}>${d}</label>
      `).join('')}</div>
      <label><input type="checkbox" class="s-on" ${session?.enabled !== false ? 'checked' : ''}>ON</label>
      <button type="button" class="btn" onclick="this.closest('.session-row').remove()">×</button>
    </div>`;
  document.getElementById('sessions-list').insertAdjacentHTML('beforeend', html);
}

function collectConfigInputs() {
  return {
    max_open_positions: parseInt(document.getElementById('c-max_open_positions').value),
    max_per_symbol: parseInt(document.getElementById('c-max_per_symbol').value),
    max_per_direction: parseInt(document.getElementById('c-max_per_direction').value),
    max_spread_pct: parseFloat(document.getElementById('c-max_spread_pct').value),
    signal_threshold: parseInt(document.getElementById('c-signal_threshold').value),
    risk_percent: parseFloat(document.getElementById('c-risk_percent').value),
    scan_interval_seconds: parseInt(document.getElementById('c-scan_interval_seconds').value),
    reward_ratio: parseFloat(document.getElementById('c-reward_ratio').value),
    sl_mode: document.getElementById('c-sl_mode').value,
    atr_multiplier: parseFloat(document.getElementById('c-atr_multiplier').value),
    tp_mode: document.getElementById('c-tp_mode').value,
    breakeven_trigger_r: parseFloat(document.getElementById('c-breakeven_trigger_r').value),
    trailing: document.getElementById('c-trailing').checked,
    trailing_distance_pips: parseFloat(document.getElementById('c-trailing_distance_pips').value),
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
