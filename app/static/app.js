function formatLocalTime(dateStr) {
  if (!dateStr) return new Date().toLocaleTimeString();
  let str = String(dateStr);
  if (!str.endsWith('Z') && !str.match(/(\+|-)\d{2}:\d{2}$/)) {
    str += 'Z';
  }
  const date = new Date(str);
  return date.toLocaleString([], {
    month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit', second: '2-digit'
  });
}

const state = {
  mt5_connected: false,
  engine_running: false,
  account: null,
  today_pnl: 0,
  open_positions: [],
  closed_trades: [],
  recent_signals: [],
  all_signals: [],
  signal_live_results: {},
  selected_signal_ids: new Set(),
  events: [],
  equity_series: [],
  config: {},
  sessions: [],
  symbols: [],
  scanner_status: {},
  exit_advice: {},
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
    case 'mt5.connection': state.mt5_connected = msg.state === 'connected'; renderTopbar(); break;
    case 'account.tick': state.account = msg; renderTopbar(); renderStats(); break;
    case 'scan.update': updateScanStatus(msg.data); break;
    case 'signal.new': state.recent_signals.unshift(msg.signal); state.all_signals.unshift(msg.signal); renderSignals(); break;
    case 'trade.opened': renderStats(); break;
    case 'trade.closed': moveToClosed(msg.trade); renderTrades(); renderStats(); break;
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
      if (msg.exit_advice) state.exit_advice = msg.exit_advice;
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
    case 'log.event': state.events.unshift(msg); renderLogs(); break;
    case 'engine.status': state.engine_running = msg.state === 'active'; renderEngineBtn(); renderNotice(); break;
    case 'session.status': state.active_sessions_count = msg.active_count; renderTopbar(); renderNotice(); break;
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
    headers: body ? { 'Content-Type': 'application/json' } : {},
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
  document.getElementById('active-sessions').innerText = state.active_sessions_count !== undefined ? state.active_sessions_count : state.sessions.filter(s => s.enabled).length;
  document.getElementById('today-pnl').innerText = `${state.today_pnl < 0 ? '-' : ''}$${Math.abs(state.today_pnl).toFixed(2)}`;
  document.getElementById('today-pnl').className = state.today_pnl >= 0 ? 'text-emerald-400 font-bold' : 'text-rose-400 font-bold';
}

function renderNotice() {
  const notice = document.getElementById('session-notice');
  if (notice) {
    if (state.active_sessions_count === 0 && state.engine_running) {
      notice.classList.remove('hidden');
    } else {
      notice.classList.add('hidden');
    }
  }
}

function renderEngineBtn() {
  const btn = document.getElementById('engine-toggle');
  btn.innerText = state.engine_running ? 'STOP' : 'START';
  btn.className = state.engine_running ? 'px-4 py-1.5 rounded bg-cyan-500 text-black font-bold text-[11px] uppercase tracking-widest shadow-[0_0_15px_rgba(6,182,212,0.4)]' : 'px-4 py-1.5 rounded border border-slate-700 text-slate-300 hover:bg-white/5 text-[11px] uppercase tracking-widest';
}

function renderStats() {
  const sBalance = document.getElementById('s-balance');
  if (sBalance) sBalance.innerText = state.account ? `$${state.account.balance.toFixed(2)}` : '—';

  const sEquity = document.getElementById('s-equity');
  if (sEquity) sEquity.innerText = state.account ? `$${state.account.equity.toFixed(2)}` : '—';

  const unrealized = state.open_positions.reduce((sum, t) => sum + (t.pnl || 0), 0);
  const unEl = document.getElementById('s-unrealized');
  if (unEl) {
    let pctStr = '';
    if (state.account && state.account.balance > 0) {
      const pct = (unrealized / state.account.balance) * 100;
      pctStr = ` <span class="text-[14px] opacity-60 font-normal tracking-wider">(${pct > 0 ? '+' : ''}${pct.toFixed(2)}%)</span>`;
    }
    unEl.innerHTML = `${unrealized < 0 ? '-' : ''}$${Math.abs(unrealized).toFixed(2)}${pctStr}`;
    unEl.className = `text-2xl font-bold font-mono ${unrealized > 0 ? 'text-emerald-400' : unrealized < 0 ? 'text-rose-400' : 'text-slate-100'}`;
  }

  const sToday = document.getElementById('s-today');
  if (sToday) {
    sToday.innerText = `${state.today_pnl < 0 ? '-' : ''}$${Math.abs(state.today_pnl).toFixed(2)}`;
  }

  const sOpen = document.getElementById('s-open');
  if (sOpen) sOpen.innerText = state.open_positions.length;
}

function renderPositions() {
  const tbody = document.getElementById('open-pos-body');
  if (!state.open_positions.length) {
    tbody.innerHTML = '<tr><td colspan="10" class="text-center text-slate-500 py-10 uppercase tracking-widest text-xs">NO OPEN POSITIONS</td></tr>';
    return;
  }

  const groups = {};
  const sortedPos = [...state.open_positions].sort((a, b) => (a.ticket || 0) - (b.ticket || 0));

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
    g.total_lot += t.lot;
    g.total_pnl += (t.pnl || 0);
    g.avg_entry += (t.entry_price * t.lot);
    g.count += 1;
    g.sl = t.sl || g.sl;
    g.tp = t.tp || g.tp;
    g.current_price = t.current_price || g.current_price;
    g.positions.push(t);
  });

  const bal = state.account && state.account.balance > 0 ? state.account.balance : null;
  const html = [];

  const renderAdviceCell = (adviceObj, isSub = false) => {
    const py = isSub ? 'py-1.5' : 'py-2.5';
    if (!adviceObj) return `<td class="px-4 ${py} text-right font-mono text-slate-500">-</td>`;
    let color = 'bg-slate-500/10 text-slate-400 border-slate-500/20';
    if (adviceObj.advice === 'HOLD') color = 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20 text-emerald-400';
    if (adviceObj.advice === 'WATCH') color = 'bg-amber-500/10 text-amber-400 border-amber-500/20 text-amber-400';
    if (adviceObj.advice === 'CONSIDER_CLOSE') color = 'bg-orange-500/10 text-orange-400 border-orange-500/20 text-orange-400';
    if (adviceObj.advice === 'CLOSE_SIGNAL') color = 'bg-rose-500/10 text-rose-400 border-rose-500/20 text-rose-400';

    return `<td class="px-4 ${py} text-right">
        <div class="flex flex-col items-end gap-0.5">
            <span class="px-1.5 py-0.5 rounded text-[9px] font-bold tracking-widest uppercase border ${color}">
                ${adviceObj.advice.replace('_', ' ')} <span class="opacity-70 ml-1">${Math.round(adviceObj.risk_score)}%</span>
            </span>
            <span class="text-[9px] text-slate-400 truncate max-w-[130px]" title="${adviceObj.reason}">${adviceObj.reason}</span>
        </div>
    </td>`;
  };

  Object.values(groups).forEach(g => {
    g.avg_entry = g.avg_entry / g.total_lot;
    const gKey = `${g.symbol}_${g.direction}`;
    const gPctStr = bal ? ` <span class="text-[10px] opacity-60 font-normal">(${g.total_pnl > 0 ? '+' : ''}${(g.total_pnl / bal * 100).toFixed(2)}%)</span>` : '';
    const gSlPct = g.sl && g.avg_entry ? ` <span class="text-[9px] opacity-40 font-normal">(${Math.abs((g.sl - g.avg_entry) / g.avg_entry * 100).toFixed(2)}%)</span>` : '';
    const gTpPct = g.tp && g.avg_entry ? ` <span class="text-[9px] opacity-40 font-normal">(${Math.abs((g.tp - g.avg_entry) / g.avg_entry * 100).toFixed(2)}%)</span>` : '';

    let gCpPctVal = 0;
    if (g.current_price && g.avg_entry) {
      gCpPctVal = ['buy', 'bullish'].includes((g.direction || '').toLowerCase()) ? (g.current_price - g.avg_entry) / g.avg_entry * 100 : (g.avg_entry - g.current_price) / g.avg_entry * 100;
    }
    const gCpPctStr = g.current_price && g.avg_entry ? ` <br><span class="text-[9px] ${gCpPctVal >= 0 ? 'text-emerald-400/70' : 'text-rose-400/70'} font-normal">(${gCpPctVal > 0 ? '+' : ''}${gCpPctVal.toFixed(2)}%)</span>` : '';

    let groupAdvice = null;
    if (g.count === 1) {
      groupAdvice = state.exit_advice[g.positions[0].ticket];
    } else {
      const scores = g.positions.map(p => state.exit_advice[p.ticket] ? state.exit_advice[p.ticket].risk_score : 0);
      const maxScore = Math.max(...scores, 0);
      if (maxScore > 0) {
        const worstP = g.positions.find(p => state.exit_advice[p.ticket] && state.exit_advice[p.ticket].risk_score === maxScore);
        if (worstP) groupAdvice = state.exit_advice[worstP.ticket];
      }
    }

    html.push(`
      <tr class="group-row cursor-pointer hover:bg-white/[0.02] transition-colors group" onclick="document.querySelectorAll('.sub-${gKey}').forEach(e => e.classList.toggle('hidden'))">
        <td class="px-4 py-2.5 flex items-center gap-2">
          ${g.count > 1 ? `<span class="text-slate-500 group-hover:text-cyan-400 transition-colors text-[10px]">▶</span>` : ''}
          <span class="font-bold text-slate-200">${g.symbol}</span>
          ${g.count > 1 ? `<span class="px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-400 text-[9px] font-bold tracking-widest border border-cyan-500/20">GROUP (${g.count})</span>` : ''}
        </td>
        <td class="px-4 py-2.5"><span class="px-2 py-0.5 rounded text-[10px] font-bold tracking-widest uppercase ${['buy', 'bullish'].includes((g.direction || '').toLowerCase()) ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'}">${g.direction}</span></td>
        <td class="px-4 py-2.5 text-right font-mono">${g.total_lot.toFixed(2)}</td>
        <td class="px-4 py-2.5 text-right font-mono text-slate-400">${g.avg_entry.toFixed(5)}</td>
        <td class="px-4 py-2.5 text-right font-mono text-slate-400">${g.current_price ? g.current_price + gCpPctStr : '-'}</td>
        <td class="px-4 py-2.5 text-right font-mono font-bold ${g.total_pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}">${g.total_pnl >= 0 ? '+' : '-'}$${Math.abs(g.total_pnl).toFixed(2)}${gPctStr}</td>
        <td class="px-4 py-2.5 text-right font-mono text-slate-400">${g.sl ? g.sl + gSlPct : '-'}</td>
        <td class="px-4 py-2.5 text-right font-mono text-slate-400">${g.tp ? g.tp + gTpPct : '-'}</td>
        ${renderAdviceCell(groupAdvice)}
        <td class="px-4 py-2.5 text-right">
          <button class="px-3 py-1.5 border border-border_strong text-slate-300 text-[10px] font-bold tracking-widest uppercase hover:bg-rose-500/10 hover:text-rose-400 hover:border-rose-500/30 transition-all rounded" onclick="event.stopPropagation(); closeGroup('${g.symbol}', '${g.direction}')">CLOSE ${g.count > 1 ? 'ALL' : ''}</button>
        </td>
      </tr>
    `);

    if (g.count > 1) {
      g.positions.forEach((p, idx) => {
        const badge = idx === 0 ? 'BASE' : `DCA ${idx}`;
        const badgeColor = idx === 0 ? 'text-amber-400 bg-amber-500/10 border-amber-500/20' : 'text-purple-400 bg-purple-500/10 border-purple-500/20';
        const pPctStr = bal ? ` <span class="text-[9px] opacity-50 font-normal">(${p.pnl > 0 ? '+' : ''}${(p.pnl / bal * 100).toFixed(2)}%)</span>` : '';
        const pSlPct = p.sl && p.entry_price ? ` <span class="text-[8px] opacity-40 font-normal">(${Math.abs((p.sl - p.entry_price) / p.entry_price * 100).toFixed(2)}%)</span>` : '';
        const pTpPct = p.tp && p.entry_price ? ` <span class="text-[8px] opacity-40 font-normal">(${Math.abs((p.tp - p.entry_price) / p.entry_price * 100).toFixed(2)}%)</span>` : '';

        let pCpPctVal = 0;
        if (p.current_price && p.entry_price) {
          pCpPctVal = ['buy', 'bullish'].includes((p.direction || '').toLowerCase()) ? (p.current_price - p.entry_price) / p.entry_price * 100 : (p.entry_price - p.current_price) / p.entry_price * 100;
        }
        const pCpPctStr = p.current_price && p.entry_price ? ` <br><span class="text-[8px] ${pCpPctVal >= 0 ? 'text-emerald-400/60' : 'text-rose-400/60'} font-normal">(${pCpPctVal > 0 ? '+' : ''}${pCpPctVal.toFixed(2)}%)</span>` : '';

        html.push(`
          <tr class="sub-${gKey} hidden bg-black/20 hover:bg-black/40 transition-colors text-[11px] border-b border-border_light/50">
            <td class="px-4 py-1.5 pl-10 flex items-center gap-2">
               <span class="px-1.5 py-0.5 rounded text-[8px] font-bold tracking-widest uppercase border ${badgeColor}">${badge}</span>
               <span class="text-slate-500 font-mono">#${p.ticket}</span>
            </td>
            <td class="px-4 py-1.5"></td>
            <td class="px-4 py-1.5 text-right font-mono text-slate-400">${p.lot.toFixed(2)}</td>
            <td class="px-4 py-1.5 text-right font-mono text-slate-500">${p.entry_price.toFixed(5)}</td>
            <td class="px-4 py-1.5 text-right font-mono text-slate-500">${p.current_price ? p.current_price + pCpPctStr : '-'}</td>
            <td class="px-4 py-1.5 text-right font-mono ${p.pnl >= 0 ? 'text-emerald-500/70' : 'text-rose-500/70'}">${p.pnl >= 0 ? '+' : '-'}$${Math.abs(p.pnl).toFixed(2)}${pPctStr}</td>
            <td class="px-4 py-1.5 text-right font-mono text-slate-500">${p.sl ? p.sl + pSlPct : '-'}</td>
            <td class="px-4 py-1.5 text-right font-mono text-slate-500">${p.tp ? p.tp + pTpPct : '-'}</td>
            ${renderAdviceCell(state.exit_advice[p.ticket], true)}
            <td class="px-4 py-1.5 text-right"></td>
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
      g.total_lot += t.lot;
      g.total_pnl += (t.pnl || 0);
      g.avg_entry += (t.entry_price * t.lot);
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
            <td class="px-4 py-2.5 font-mono text-slate-500">-</td>
            <td class="px-4 py-2.5 flex items-center gap-2">
              ${g.count > 1 ? `<span class="text-slate-500 group-hover:text-cyan-400 transition-colors text-[10px]">▶</span>` : ''}
              <span class="font-bold text-slate-200">${g.symbol}</span>
              ${g.count > 1 ? `<span class="px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-400 text-[9px] font-bold tracking-widest border border-cyan-500/20">GROUP (${g.count})</span>` : ''}
            </td>
            <td class="px-4 py-2.5"><span class="px-2 py-0.5 rounded text-[10px] font-bold tracking-widest uppercase ${['buy', 'bullish'].includes((g.direction || '').toLowerCase()) ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'}">${g.direction}</span></td>
            <td class="px-4 py-2.5 text-right font-mono">${g.total_lot.toFixed(2)}</td>
            <td class="px-4 py-2.5 text-right font-mono text-slate-400">${g.avg_entry.toFixed(5)}</td>
            <td class="px-4 py-2.5 text-right font-mono text-slate-400">${g.sl || '-'}</td>
            <td class="px-4 py-2.5 text-right font-mono text-slate-400">${g.tp || '-'}</td>
            <td class="px-4 py-2.5 text-right font-mono text-slate-500">-</td>
            <td class="px-4 py-2.5 text-right font-mono font-bold ${g.total_pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}">${g.total_pnl >= 0 ? '+' : '-'}$${Math.abs(g.total_pnl).toFixed(2)}</td>
            <td class="px-4 py-2.5 text-slate-400">${g.note || '-'}</td>
            <td class="px-4 py-2.5 text-right"><button class="px-3 py-1 border border-border_strong text-slate-300 text-[10px] font-bold tracking-widest uppercase hover:bg-rose-500/10 hover:text-rose-400 hover:border-rose-500/30 transition-all rounded" onclick="event.stopPropagation(); closeGroup('${g.symbol}', '${g.direction}')">CLOSE ${g.count > 1 ? 'ALL' : ''}</button></td>
          </tr>
        `);
    });
    tbody.innerHTML = html.join('');
  } else {
    tbody.innerHTML = list.map(t => `
        <tr class="hover:bg-white/[0.02] transition-colors">
          <td class="px-4 py-2.5 font-mono text-slate-500 whitespace-nowrap">${formatLocalTime(t.opened_at)}</td>
          <td class="px-4 py-2.5 font-bold text-slate-200">${t.symbol}</td>
          <td class="px-4 py-2.5"><span class="px-2 py-0.5 rounded text-[10px] font-bold tracking-widest uppercase ${['buy', 'bullish'].includes((t.direction || '').toLowerCase()) ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'}">${t.direction}</span></td>
          <td class="px-4 py-2.5 text-right font-mono">${t.lot}</td>
          <td class="px-4 py-2.5 text-right font-mono text-slate-400">${t.entry_price}</td>
          <td class="px-4 py-2.5 text-right font-mono text-slate-400">${t.sl || '-'}</td>
          <td class="px-4 py-2.5 text-right font-mono text-slate-400">${t.tp || '-'}</td>
          <td class="px-4 py-2.5 text-right font-mono text-slate-300">${t.exit_price || '-'}</td>
          <td class="px-4 py-2.5 text-right font-mono font-bold ${t.pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}">${t.pnl >= 0 ? '+' : '-'}$${Math.abs(t.pnl || 0).toFixed(2)}</td>
          <td class="px-4 py-2.5 text-slate-400">${t.note || '-'}</td>
          <td class="px-4 py-2.5 text-right"></td>
        </tr>
      `).join('');
  }
}

function getSignalLocalParts(created_at, timezone) {
  try {
    const d = new Date(created_at + 'Z');
    const year = new Intl.DateTimeFormat('en-US', { timeZone: timezone, year: 'numeric' }).format(d);
    const month = new Intl.DateTimeFormat('en-US', { timeZone: timezone, month: '2-digit' }).format(d);
    const day = new Intl.DateTimeFormat('en-US', { timeZone: timezone, day: '2-digit' }).format(d);
    const time = new Intl.DateTimeFormat('en-GB', { timeZone: timezone, hour: '2-digit', minute: '2-digit', hour12: false }).format(d);
    return { date: `${year}-${month}-${day}`, time: time };
  } catch (e) {
    return null;
  }
}

function renderSignals() {
  const tbody = document.getElementById('signals-body');
  
  const dateFromStr = document.getElementById('signal-date-from')?.value;
  const dateToStr = document.getElementById('signal-date-to')?.value;
  const timeFromStr = document.getElementById('signal-time-from')?.value;
  const timeToStr = document.getElementById('signal-time-to')?.value;
  const tzStr = document.getElementById('signal-timezone')?.value || 'Asia/Karachi';
  const statusFilter = document.getElementById('signal-status-filter')?.value;

  const validSymbols = new Set();
  state.symbols.forEach(st => {
    if (st.status !== 'unresolved') {
      if (st.generic) validSymbols.add(st.generic);
      if (st.original) validSymbols.add(st.original);
      if (st.resolved) validSymbols.add(st.resolved);
    }
  });

  let displaySignals = state.all_signals;
  if (validSymbols.size > 0) {
    displaySignals = state.all_signals.filter(s => validSymbols.has(s.symbol));
  }

  if (dateFromStr || dateToStr || (timeFromStr && timeToStr)) {
    displaySignals = displaySignals.filter(s => {
      const parts = getSignalLocalParts(s.created_at, tzStr);
      if (!parts) return true; // fallback

      let passDate = true;
      if (dateFromStr && parts.date < dateFromStr) passDate = false;
      if (dateToStr && parts.date > dateToStr) passDate = false;

      let passTime = true;
      if (timeFromStr && timeToStr) {
        if (timeFromStr <= timeToStr) {
          passTime = parts.time >= timeFromStr && parts.time <= timeToStr;
        } else {
          passTime = parts.time >= timeFromStr || parts.time <= timeToStr;
        }
      }

      return passDate && passTime;
    });
  }

  if (statusFilter) {
    displaySignals = displaySignals.filter(s => {
      if (statusFilter === 'FIRED') return s.status === 'FIRED' || s.status === 'DCA_FIRED';
      if (statusFilter === 'SKIPPED') return s.status === 'SKIPPED' || s.status === 'DCA_SKIPPED';
      return true;
    });
  }

  if (!displaySignals.length) {
    tbody.innerHTML = '<tr><td colspan="8" class="text-center text-slate-500 py-8 uppercase tracking-widest text-xs">NO SIGNALS FOR SELECTED DATE/TIME RANGE</td></tr>';
    if (document.getElementById('win-rate')) document.getElementById('win-rate').textContent = '0.0';
    if (document.getElementById('live-bias-rate')) document.getElementById('live-bias-rate').textContent = '0.0';
    if (document.getElementById('stat-fired')) document.getElementById('stat-fired').textContent = '0';
    if (document.getElementById('stat-tp')) document.getElementById('stat-tp').textContent = '0';
    if (document.getElementById('stat-sl')) document.getElementById('stat-sl').textContent = '0';
    if (document.getElementById('stat-live')) document.getElementById('stat-live').textContent = '0';
    return;
  }

  const getStatusBadge = (status) => {
    let color = 'bg-white/5 text-slate-400 border-white/10';
    if (status === 'FIRED') color = 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30';
    else if (status === 'DCA_FIRED') color = 'bg-purple-500/20 text-purple-400 border-purple-500/30';
    else if (status === 'WATCHING') color = 'bg-amber-500/20 text-amber-400 border-amber-500/30';
    else if (status === 'SKIPPED' || status === 'DCA_SKIPPED') color = 'bg-slate-500/10 text-slate-400 border-slate-500/20';
    return `<span class="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-widest whitespace-nowrap border ${color}">${status}</span>`;
  };

  const getResultBadge = (s) => {
    if (s.result === 'TP HIT') return '<span class="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-widest whitespace-nowrap bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">TP HIT</span>';
    if (s.result === 'SMART TP HIT') return '<span class="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-widest whitespace-nowrap bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">SMART TP HIT</span>';
    if (s.result === 'SL HIT') return '<span class="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-widest whitespace-nowrap bg-rose-500/10 text-rose-400 border border-rose-500/20">SL HIT</span>';
    if (s.result) return `<span class="text-slate-400">${s.result}</span>`;
    
    const lr = state.signal_live_results[s.id];
    if (lr) {
      let color = 'bg-white/5 text-slate-400 border-white/10';
      if (lr.live_result_status === 'NEAR TP') color = 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40';
      else if (lr.live_result_status === 'MOVING TO TP') color = 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40';
      else if (lr.live_result_status === 'MOVING TO SL') color = 'bg-amber-500/20 text-amber-400 border-amber-500/40';
      else if (lr.live_result_status === 'NEAR SL') color = 'bg-rose-500/20 text-rose-300 border-rose-500/40';
      
      const tpProg = Math.max(0, Math.min(100, Math.round(lr.tp_progress * 100)));
      const slProg = Math.max(0, Math.min(100, Math.round(lr.sl_progress * 100)));
      const progStr = `TP: ${tpProg}% | SL: ${slProg}%`;
      return `<div class="flex flex-col gap-1 items-start"><span class="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-widest whitespace-nowrap border text-center ${color}">${lr.live_result_status}</span><span class="text-[8px] font-mono text-slate-500 text-center">${progStr}</span></div>`;
    }
    
    return '<span class="text-slate-600">-</span>';
  };

  const firedSignals = displaySignals.filter(s => s.status === 'FIRED' || s.status === 'DCA_FIRED');
  const skippedCount = displaySignals.filter(s => s.status === 'SKIPPED' || s.status === 'DCA_SKIPPED').length;

  const won = firedSignals.filter(s => s.result === 'TP HIT' || s.result === 'SMART TP HIT').length;
  const lost = firedSignals.filter(s => s.result === 'SL HIT').length;
  const winRate = (won + lost) > 0 ? ((won / (won + lost)) * 100).toFixed(1) : '0.0';
  const missedWins = displaySignals.filter(s => (s.status === 'SKIPPED' || s.status === 'DCA_SKIPPED') && (s.result === 'TP HIT' || s.result === 'SMART TP HIT')).length;
  
  let nearTp = 0, nearSl = 0, movingTp = 0, movingSl = 0, inProgress = 0;
  firedSignals.forEach(s => {
    if (!s.result && state.signal_live_results[s.id]) {
      const st = state.signal_live_results[s.id].live_result_status;
      if (st === 'NEAR TP') nearTp++;
      else if (st === 'NEAR SL') nearSl++;
      else if (st === 'MOVING TO TP') movingTp++;
      else if (st === 'MOVING TO SL') movingSl++;
      else inProgress++;
    }
  });
  
  const liveBiasTotal = won + lost + nearTp + nearSl + movingTp + movingSl;
  const liveBiasRate = liveBiasTotal > 0 ? (((won + nearTp + movingTp) / liveBiasTotal) * 100).toFixed(1) : '0.0';
  
  if (document.getElementById('win-rate')) document.getElementById('win-rate').textContent = winRate;
  if (document.getElementById('live-bias-rate')) document.getElementById('live-bias-rate').textContent = liveBiasRate;
  if (document.getElementById('stat-total')) document.getElementById('stat-total').textContent = displaySignals.length;
  if (document.getElementById('stat-fired')) document.getElementById('stat-fired').textContent = firedSignals.length;
  if (document.getElementById('stat-skipped')) document.getElementById('stat-skipped').textContent = skippedCount;
  if (document.getElementById('stat-tp')) document.getElementById('stat-tp').textContent = won;
  if (document.getElementById('stat-sl')) document.getElementById('stat-sl').textContent = lost;
  if (document.getElementById('stat-live')) document.getElementById('stat-live').textContent = nearTp + nearSl + movingTp + movingSl + inProgress;
  if (document.getElementById('stat-missed-wins')) document.getElementById('stat-missed-wins').textContent = missedWins;

  window.current_display_signal_ids = displaySignals.map(s => s.id);
  
  if (document.getElementById('signals-select-all')) {
    const allChecked = window.current_display_signal_ids.length > 0 && window.current_display_signal_ids.every(id => state.selected_signal_ids.has(id));
    document.getElementById('signals-select-all').checked = allChecked;
  }
  
  const selectedCountEl = document.getElementById('signals-selected-count');
  const deleteBtnEl = document.getElementById('btn-delete-selected');
  if (selectedCountEl && deleteBtnEl) {
    if (state.selected_signal_ids.size > 0) {
      selectedCountEl.textContent = `SELECTED: ${state.selected_signal_ids.size}`;
      selectedCountEl.style.display = 'block';
      deleteBtnEl.style.display = 'block';
    } else {
      selectedCountEl.style.display = 'none';
      deleteBtnEl.style.display = 'none';
    }
  }

  tbody.innerHTML = displaySignals.map(s => {
    const isHighlight = s.status === 'FIRED' || s.status === 'DCA_FIRED';
    const isChecked = state.selected_signal_ids.has(s.id);
    return `
      <tr class="${isHighlight ? 'bg-emerald-500/5 hover:bg-emerald-500/10' : 'hover:bg-white/[0.02]'} transition-colors">
        <td class="px-4 py-2.5"><input type="checkbox" onchange="toggleSignalSelection(${s.id}, this.checked)" ${isChecked ? 'checked' : ''} class="accent-rose-500"></td>
        <td class="px-4 py-2.5 font-mono text-slate-500 whitespace-nowrap">${formatLocalTime(s.created_at)}</td>
        <td class="px-4 py-2.5 font-bold text-slate-200">${s.symbol}</td>
        <td class="px-4 py-2.5"><span class="px-2 py-0.5 rounded text-[10px] font-bold tracking-widest uppercase ${['buy', 'bullish'].includes((s.direction || '').toLowerCase()) ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'}">${s.direction}</span></td>
        <td class="px-4 py-2.5 text-right font-mono ${s.score > 0 ? 'text-cyan-400 font-bold' : 'text-slate-500'}">${s.score}</td>
        <td class="px-4 py-2.5">${getStatusBadge(s.status)}</td>
        <td class="px-4 py-2.5">${getResultBadge(s)}</td>
        <td class="px-4 py-2.5 text-slate-300 w-full">${s.reason && s.reason.skip_reason ? `<span class="text-orange-400 font-bold uppercase tracking-widest text-[9px] border border-orange-500/30 bg-orange-500/10 px-1.5 py-0.5 rounded mr-2">${s.reason.skip_reason}</span>` : ''}${s.reason && s.reason.msg ? s.reason.msg : JSON.stringify(s.reason)}</td>
      </tr>
    `;
  }).join('');
}

function toggleSignalSelection(id, checked) {
  if (checked) state.selected_signal_ids.add(id);
  else state.selected_signal_ids.delete(id);
  renderSignals();
}

function toggleAllSignals(checked) {
  if (!window.current_display_signal_ids) return;
  if (checked) {
    window.current_display_signal_ids.forEach(id => state.selected_signal_ids.add(id));
  } else {
    window.current_display_signal_ids.forEach(id => state.selected_signal_ids.delete(id));
  }
  renderSignals();
}

async function deleteSelectedSignals() {
  if (state.selected_signal_ids.size === 0) return;
  if (!confirm(`Delete ${state.selected_signal_ids.size} selected signals? This cannot be undone.`)) return;
  
  const ids = Array.from(state.selected_signal_ids);
  const btn = document.getElementById('btn-delete-selected');
  btn.textContent = 'DELETING...';
  btn.disabled = true;
  
  try {
    const res = await api('POST', '/api/signals/delete_bulk', { ids });
    
    // Remove from frontend state
    state.all_signals = state.all_signals.filter(s => !state.selected_signal_ids.has(s.id));
    state.recent_signals = state.recent_signals.filter(s => !state.selected_signal_ids.has(s.id));
    ids.forEach(id => { delete state.signal_live_results[id]; });
    state.selected_signal_ids.clear();
    
    renderSignals();
  } catch (err) {
    alert(err.message);
  } finally {
    btn.textContent = 'DELETE SELECTED';
    btn.disabled = false;
  }
}

async function checkSignalResults() {
  const btn = document.getElementById('btn-check-results');
  btn.textContent = 'CHECKING...';
  btn.disabled = true;
  const useSmartTp = document.getElementById('use-smart-tp-sim')?.checked || false;
  try {
    const res = await api('POST', '/api/signals/check_results', { use_smart_tp: useSmartTp });
    alert(`Done! Updated ${res.updated} final signals.`);
    
    if (res.live_results) {
      state.signal_live_results = { ...state.signal_live_results, ...res.live_results };
    }
    
    const initData = await api('GET', '/api/initial_data').catch(() => null);
    if (initData && initData.signals) {
      state.all_signals = initData.signals;
    }
    
    renderSignals();
  } catch (err) {
    alert(err.message);
  } finally {
    btn.textContent = 'CHECK RESULTS';
    btn.disabled = false;
  }
}

async function clearSignalResults() {
  if (!confirm("Are you sure you want to clear all signal results?")) return;
  const btn = document.getElementById('btn-clear-results');
  btn.textContent = 'CLEARING...';
  btn.disabled = true;
  try {
    await api('POST', '/api/signals/clear_results');
    window.location.reload();
  } catch (err) {
    alert(err.message);
  } finally {
    if (btn) {
      btn.textContent = 'CLEAR RESULTS';
      btn.disabled = false;
    }
  }
}

async function clearAllSignals() {
  if (!confirm("Are you sure you want to delete ALL signals? This cannot be undone.")) return;
  try {
    await api('DELETE', '/api/signals');
    state.all_signals = [];
    state.recent_signals = [];
    renderSignals();
  } catch (err) {
    alert(err.message);
  }
}

function renderLogs() {
  const tbody = document.getElementById('logs-body');
  if (!state.events.length) {
    tbody.innerHTML = '<tr><td colspan="4" class="text-center text-slate-500 py-8 uppercase tracking-widest text-xs">NO LOGS</td></tr>';
    return;
  }
  tbody.innerHTML = state.events.map(e => `
    <tr class="hover:bg-white/[0.02] transition-colors">
      <td class="px-4 py-2.5 font-mono text-slate-500 whitespace-nowrap">${formatLocalTime(e.created_at)}</td>
      <td class="px-4 py-2.5 font-bold ${e.level === 'ERROR' ? 'text-rose-400' : e.level === 'WARN' ? 'text-amber-400' : 'text-cyan-400'}">${e.level}</td>
      <td class="px-4 py-2.5 text-slate-300">${e.component}</td>
      <td class="px-4 py-2.5 text-slate-400 w-full">${e.message}</td>
    </tr>
  `).join('');
}

function updateScanStatus(data) {
  state.scanner_status[data.symbol] = data;
  renderScannerStatus();
}

function renderScannerStatus() {
  const tbody = document.getElementById('scan-status-body');
  
  const itemsMap = { ...state.scanner_status };
  const configuredSymbols = state.config.symbols || [];
  
  configuredSymbols.forEach(sym => {
    if (!itemsMap[sym]) {
      itemsMap[sym] = {
        symbol: sym,
        resolved: 'pending',
        status: 'WAITING',
        bias: null,
        score: 0,
        reason: { msg: "Waiting for first scan..." },
        updated_at: null
      };
    }
  });

  const items = Object.values(itemsMap).filter(s => configuredSymbols.includes(s.symbol));

  // Sort items: FIRED > DCA_FIRED > WATCHING > SKIPPED > REJECTED > COOLDOWN > WAITING
  const statusWeight = { 'FIRED': 7, 'DCA_FIRED': 6, 'WATCHING': 5, 'SKIPPED': 4, 'DCA_SKIPPED': 4, 'REJECTED': 3, 'COOLDOWN': 2, 'WAITING': 1 };
  items.sort((a, b) => (statusWeight[b.status] || 0) - (statusWeight[a.status] || 0));

  if (!items.length) {
    tbody.innerHTML = '<tr><td colspan="6" class="text-center text-slate-500 py-10 uppercase tracking-widest text-xs">NO SYMBOLS CONFIGURED</td></tr>';
    return;
  }

  const esc = (str) => String(str).replace(/"/g, '&quot;').replace(/'/g, '&#39;');

  const getStatusBadge = (status) => {
    let color = 'bg-white/5 text-slate-400 border-white/10'; // Default muted
    if (status === 'FIRED') color = 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30';
    else if (status === 'DCA_FIRED') color = 'bg-purple-500/20 text-purple-400 border-purple-500/30';
    else if (status === 'WATCHING') color = 'bg-amber-500/20 text-amber-400 border-amber-500/30';
    else if (status === 'SKIPPED' || status === 'DCA_SKIPPED') color = 'bg-blue-500/10 text-blue-400 border-blue-500/20';
    else if (status === 'WAITING') color = 'bg-white/10 text-slate-300 border-white/20';

    return `<span class="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-widest whitespace-nowrap border ${color}">${status}</span>`;
  };

  tbody.innerHTML = items.map(s => {
    let reasonText = s.reason.msg || '';
    if (s.status === 'FIRED' || s.status === 'DCA_FIRED') reasonText = 'Signal Triggered!';

    const rawReason = esc(JSON.stringify(s.reason));
    const isHighlight = s.status === 'FIRED' || s.status === 'DCA_FIRED';

    return `
    <tr class="${isHighlight ? 'bg-emerald-500/5 hover:bg-emerald-500/10' : 'hover:bg-white/[0.02]'} transition-colors">
      <td class="px-4 py-2.5 flex items-center gap-2">
        <span class="font-bold text-slate-200">${s.symbol}</span> 
        <span class="text-slate-500 font-mono text-[9px] border border-border_strong px-1 rounded">${s.resolved}</span>
      </td>
      <td class="px-4 py-2.5"><span class="px-2 py-0.5 rounded text-[10px] font-bold tracking-widest uppercase ${s.bias === 'bullish' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : s.bias === 'bearish' ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20' : 'bg-white/5 text-slate-400 border border-white/10'}">${s.bias || 'NONE'}</span></td>
      <td class="px-4 py-2.5 text-right font-mono ${s.score > 0 ? 'text-cyan-400 font-bold' : 'text-slate-500'}">${s.score}</td>
      <td class="px-4 py-2.5">${getStatusBadge(s.status)}</td>
      <td class="px-4 py-2.5 text-slate-300" style="max-width: 300px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="${rawReason}">
        ${esc(reasonText)}
      </td>
      <td class="px-4 py-2.5 font-mono text-slate-500 text-right w-24 shrink-0">${formatLocalTime(s.updated_at)}</td>
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
  } catch (err) { console.error(err); }
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
    document.getElementById('c-signal_cooldown_minutes').value = cfg.signal_cooldown_minutes || 30;
    document.getElementById('c-reward_ratio').value = cfg.reward_ratio || 2.0;
    document.getElementById('c-dashboard_password').value = cfg.dashboard_password || 'admin';
    document.getElementById('c-scan_concurrency').value = cfg.scan_concurrency || 5;
    document.getElementById('c-close_all_concurrency').value = cfg.close_all_concurrency || 2;
    document.getElementById('c-enable_latency_logs').checked = cfg.enable_latency_logs !== false;
    document.getElementById('c-magic_number').value = cfg.magic_number || 123456;

    document.getElementById('c-atr_buffer_multiplier').value = cfg.atr_buffer_multiplier || 0.2;
    document.getElementById('c-use_liquidity_tp').checked = cfg.use_liquidity_tp !== false;
    document.getElementById('c-enable_smart_tp').checked = cfg.enable_smart_tp !== false;
    document.getElementById('c-min_sl_atr_multiplier').value = cfg.min_sl_atr_multiplier || 0.8;
    document.getElementById('c-breakeven_trigger_r').value = cfg.breakeven_trigger_r || 1.0;
    document.getElementById('c-trailing').checked = cfg.trailing !== false;
    document.getElementById('c-trailing_start_tp_pct').value = cfg.trailing_start_tp_pct || 0.6;
    document.getElementById('c-trailing_mode').value = cfg.trailing_mode || 'atr';
    document.getElementById('c-trailing_atr_multiplier').value = cfg.trailing_atr_multiplier || 1.5;
    document.getElementById('c-trailing_distance_pips').value = cfg.trailing_distance_pips || 15.0;

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

    document.getElementById('c-volume_filter_enabled').checked = cfg.volume_filter_enabled !== false;
    document.getElementById('c-volume_lookback').value = cfg.volume_lookback || 20;
    document.getElementById('c-min_volume_ratio').value = cfg.min_volume_ratio || 0.85;
    document.getElementById('c-strong_volume_ratio').value = cfg.strong_volume_ratio || 1.3;
    document.getElementById('c-volume_score_bonus').value = cfg.volume_score_bonus || 5;
    document.getElementById('c-volume_use_ema').checked = cfg.volume_use_ema !== false;
    document.getElementById('c-volume_low_downgrade_only').checked = cfg.volume_low_downgrade_only !== false;

    document.getElementById('c-session_warmup_enabled').checked = cfg.session_warmup_enabled !== false;
    document.getElementById('c-session_min_warmup_minutes').value = cfg.session_min_warmup_minutes || 5;
    document.getElementById('c-session_max_warmup_minutes').value = cfg.session_max_warmup_minutes || 15;
    document.getElementById('c-session_warmup_require_closed_m5').checked = cfg.session_warmup_require_closed_m5 !== false;
    document.getElementById('c-session_warmup_spread_multiplier').value = cfg.session_warmup_spread_multiplier || 1.2;
    document.getElementById('c-session_warmup_volatility_multiplier').value = cfg.session_warmup_volatility_multiplier || 1.5;

    state.symbols = (cfg.symbols || []).map(s => ({ generic: s, original: s, resolved: null, status: 'pending' }));
    document.getElementById('c-correlation_groups_enabled').checked = cfg.correlation_groups_enabled !== false;
    document.getElementById('c-max_open_per_correlation_group').value = cfg.max_open_per_correlation_group || 1;

    state.enabled_correlation_groups = cfg.enabled_correlation_groups || ["indices", "metals", "jpy", "usd_majors", "oil"];
    renderPredefinedSymbols();
    renderCorrelationGroups();
    resolveAllSymbols();

    const sessions = await api('GET', '/api/sessions');
    state.sessions = sessions;
    document.getElementById('sessions-list').innerHTML = '';
    sessions.forEach(s => addSessionRow(s));
  } catch (err) { alert(err.message + "\n" + err.stack); console.error(err); }
}

function openConfigModal() { loadConfig(); document.getElementById('config-modal').showModal(); }
function closeConfigModal() { document.getElementById('config-modal').close(); }

// Predefined Symbols and Groups
const PREDEFINED_SYMBOLS = [
  "US30", "US500", "USTEC", "XAUUSD", "XAGUSD", "USDJPY", "EURJPY", "GBPJPY",
  "EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "USDCAD", "USDCHF", "USOIL", "UKOIL",
  "EURAUD", "EURCAD", "EURGBP", "EURCHF", "EURNZD", "GBPAUD", "GBPCAD", "GBPCHF",
  "GBPNZD", "AUDCAD", "AUDCHF", "AUDJPY", "AUDNZD", "CADCHF", "CADJPY", "CHFJPY",
  "NZDCAD", "NZDCHF", "NZDJPY"
];

const CORRELATION_GROUPS = {
  "indices": ["US30", "US500", "USTEC"],
  "metals": ["XAUUSD", "XAGUSD"],
  "oil": ["USOIL", "UKOIL"],
  "usd_majors": ["EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "USDCAD", "USDCHF"],
  "jpy_pairs": ["USDJPY", "EURJPY", "GBPJPY", "AUDJPY", "CADJPY", "CHFJPY", "NZDJPY"],
  "eur_crosses": ["EURAUD", "EURCAD", "EURGBP", "EURCHF", "EURNZD"],
  "gbp_crosses": ["GBPAUD", "GBPCAD", "GBPCHF", "GBPNZD"],
  "minor_crosses": ["AUDCAD", "AUDCHF", "AUDNZD", "CADCHF", "NZDCAD", "NZDCHF"]
};

function renderPredefinedSymbols() {
  const customSyms = state.symbols.map(s => s.original || s.generic).filter(s => !PREDEFINED_SYMBOLS.includes(s));
  const displayList = [...PREDEFINED_SYMBOLS, ...customSyms];

  document.getElementById('sym-checkboxes').innerHTML = displayList.map(sym => {
    const obj = state.symbols.find(s => (s.original === sym) || (s.generic === sym));
    const isChecked = !!obj;
    
    const displayName = (obj && obj.original && obj.generic && obj.original !== obj.generic) 
      ? `${obj.original} &rarr; <span class="text-cyan-400">${obj.generic}</span>` 
      : sym;

    const statusLabel = obj && obj.status === 'resolved' 
      ? ` <span class="text-emerald-500 text-[9px] whitespace-nowrap">(✓)</span>` 
      : (obj && obj.status === 'unresolved' 
        ? ` <span class="text-rose-500 text-[9px] cursor-help" title="${obj.error_reason || 'Unknown error'}">(✗ ${obj.error_reason ? 'ERR' : 'FAIL'})</span>` 
        : '');

    return `
      <label class="flex items-center gap-2 text-[10px] font-bold tracking-[0.1em] text-slate-300 cursor-pointer p-2 border border-border_light bg-black/10 hover:bg-white/5 rounded transition-colors group">
        <input type="checkbox" value="${sym}" class="sym-cb w-4 h-4 accent-cyan_neon cursor-pointer shrink-0" ${isChecked ? 'checked' : ''} onchange="toggleSymbol('${sym}', this.checked)">
        <span class="truncate">${displayName}${statusLabel}</span>
      </label>
    `;
  }).join('');
}

function toggleSymbol(sym, isChecked) {
  if (isChecked) {
    if (!state.symbols.find(s => s.original === sym || s.generic === sym)) {
      state.symbols.push({ generic: sym, original: sym, resolved: null, status: 'pending' });
    }
  } else {
    state.symbols = state.symbols.filter(s => s.original !== sym && s.generic !== sym);
  }
  renderCorrelationGroups();
}

function renderCorrelationGroups() {
  const enabledGrp = new Set(state.enabled_correlation_groups || []);
  const enabledSet = new Set();
  state.symbols.forEach(s => {
    enabledSet.add(s.generic);
    if(s.original) enabledSet.add(s.original);
  });

  document.getElementById('corr-groups-list').innerHTML = Object.entries(CORRELATION_GROUPS).map(([group, syms]) => {
    const isChecked = enabledGrp.has(group);

    const symsHtml = syms.map(s => {
      const isActive = enabledSet.has(s) || state.symbols.some(st => st.original === s || st.generic === s);
      const colorClass = isActive ? "text-cyan_neon bg-cyan_neon/10 border border-cyan_neon/30" : "text-slate-600 bg-black/20 border border-transparent";
      return `<span class="px-1.5 py-0.5 rounded ${colorClass}">${s}</span>`;
    }).join('');

    return `
      <label class="flex flex-col gap-2 p-3 border border-border_light bg-black/10 rounded cursor-pointer group hover:bg-white/5 transition-colors">
        <div class="flex items-center gap-2 text-[10px] font-bold tracking-[0.1em] text-cyan_neon uppercase">
          <input type="checkbox" value="${group}" class="corr-cb w-4 h-4 accent-cyan_neon cursor-pointer" ${isChecked ? 'checked' : ''} onchange="toggleCorrelationGroup('${group}', this.checked)">
          ${group}
        </div>
        <div class="text-[9px] font-mono flex flex-wrap gap-1">
          ${symsHtml}
        </div>
      </label>
    `;
  }).join('');
}

function toggleCorrelationGroup(group, isChecked) {
  let enabled = new Set(state.enabled_correlation_groups || []);
  if (isChecked) enabled.add(group);
  else enabled.delete(group);
  state.enabled_correlation_groups = Array.from(enabled);
}

async function resolveAllSymbols() {
  const generics = state.symbols.map(s => s.generic);
  if (!generics.length) return renderPredefinedSymbols();
  try {
    const { map } = await api('POST', '/api/symbols/resolve', { generics });
    state.symbols = state.symbols.map(s => {
      const info = map[s.generic];
      const isResolved = info && info.exists && info.selected;
      
      const newGeneric = isResolved ? info.resolved : s.generic;
      
      return {
        ...s, 
        generic: newGeneric, 
        original: s.original || s.generic,
        resolved: isResolved ? info.resolved : null, 
        status: isResolved ? 'resolved' : 'unresolved',
        error_reason: info ? info.error : null
      };
    });
    renderPredefinedSymbols();
    renderSignals();
  } catch (err) { console.error(err); }
}

// Sessions repeater
const IANA_ZONES = ['UTC', 'Europe/London', 'America/New_York', 'Asia/Tokyo', 'Asia/Dubai', 'Asia/Karachi', 'Asia/Singapore', 'Australia/Sydney'];
function addSessionRow(session) {
  const id = session?.id ?? ('new-' + Date.now());
  const html = `
    <div class="session-row grid grid-cols-2 md:grid-cols-12 gap-x-4 gap-y-3 p-3 border border-border_light bg-white/[0.02] rounded hover:bg-white/[0.04] transition-colors" data-id="${id}">
      <div class="col-span-2 md:col-span-4 flex flex-col gap-1">
         <span class="text-[9px] uppercase tracking-widest text-slate-500 font-bold">Name</span>
         <input placeholder="NAME" class="s-name bg-black/20 border border-border_strong text-slate-200 text-[10px] px-2.5 py-1.5 rounded outline-none focus:border-cyan_neon w-full" value="${session?.name ?? ''}">
      </div>
      <div class="col-span-1 md:col-span-2 flex flex-col gap-1">
         <span class="text-[9px] uppercase tracking-widest text-slate-500 font-bold">Start</span>
         <input type="time" class="s-start bg-black/20 border border-border_strong text-slate-200 text-[10px] px-2.5 py-1.5 rounded outline-none focus:border-cyan_neon w-full" value="${session?.start_time ?? '08:00'}">
      </div>
      <div class="col-span-1 md:col-span-2 flex flex-col gap-1">
         <span class="text-[9px] uppercase tracking-widest text-slate-500 font-bold">End</span>
         <input type="time" class="s-end bg-black/20 border border-border_strong text-slate-200 text-[10px] px-2.5 py-1.5 rounded outline-none focus:border-cyan_neon w-full" value="${session?.end_time ?? '12:00'}">
      </div>
      <div class="col-span-2 md:col-span-4 flex flex-col gap-1">
         <span class="text-[9px] uppercase tracking-widest text-slate-500 font-bold">Timezone</span>
         <select class="s-tz bg-black/20 border border-border_strong text-slate-200 text-[10px] px-2 py-1.5 rounded outline-none focus:border-cyan_neon w-full truncate">${IANA_ZONES.map(z => `<option ${z === (session?.timezone ?? 'UTC') ? 'selected' : ''}>${z}</option>`).join('')}</select>
      </div>
      <div class="col-span-2 md:col-span-8 flex flex-col gap-1 mt-1">
         <span class="text-[9px] uppercase tracking-widest text-slate-500 font-bold">Days Active</span>
         <div class="day-checks flex gap-1 justify-between bg-black/10 border border-border_strong p-1 rounded">${['M', 'T', 'W', 'T', 'F', 'S', 'S'].map((d, i) => `
           <label class="flex flex-col items-center gap-1 text-[9px] font-bold text-slate-500 cursor-pointer hover:text-slate-300 w-full text-center"><input type="checkbox" data-day="${i}" class="w-3 h-3 accent-cyan_neon cursor-pointer" ${!session || (session?.days_mask & (1 << i)) ? 'checked' : ''}>${d}</label>
         `).join('')}</div>
      </div>
      <div class="col-span-2 md:col-span-4 flex items-end justify-end gap-3 mt-1 h-full pb-0.5">
        <label class="flex items-center gap-2 text-[9px] font-bold text-slate-300 uppercase cursor-pointer group"><input type="checkbox" class="s-on w-3.5 h-3.5 accent-cyan_neon cursor-pointer bg-black/20 border-border_strong group-hover:border-cyan_neon" ${session?.enabled !== false ? 'checked' : ''}> ON</label>
        <button type="button" class="px-3 py-1.5 text-rose-400 bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/20 hover:border-rose-500/40 rounded text-[9px] font-bold tracking-widest uppercase transition-colors shrink-0" onclick="this.closest('.session-row').remove()">DELETE</button>
      </div>
    </div>`;
  document.getElementById('sessions-list').insertAdjacentHTML('beforeend', html);
}

function collectConfigInputs() {
  return {
    correlation_groups_enabled: document.getElementById('c-correlation_groups_enabled').checked,
    max_open_per_correlation_group: parseInt(document.getElementById('c-max_open_per_correlation_group').value),
    enabled_correlation_groups: state.enabled_correlation_groups || [],
    max_open_positions: parseInt(document.getElementById('c-max_open_positions').value),
    max_signals_per_scan: parseInt(document.getElementById('c-max_signals_per_scan').value),
    max_per_symbol: parseInt(document.getElementById('c-max_per_symbol').value),
    max_per_direction: parseInt(document.getElementById('c-max_per_direction').value),
    max_spread_pct: parseFloat(document.getElementById('c-max_spread_pct').value),
    signal_threshold: parseInt(document.getElementById('c-signal_threshold').value),
    risk_percent: parseFloat(document.getElementById('c-risk_percent').value),
    scan_interval_seconds: parseInt(document.getElementById('c-scan_interval_seconds').value),
    scan_concurrency: parseInt(document.getElementById('c-scan_concurrency').value),
    close_all_concurrency: parseInt(document.getElementById('c-close_all_concurrency').value),
    signal_cooldown_minutes: parseInt(document.getElementById('c-signal_cooldown_minutes').value),
    reward_ratio: parseFloat(document.getElementById('c-reward_ratio').value),
    magic_number: parseInt(document.getElementById('c-magic_number').value),
    dashboard_password: document.getElementById('c-dashboard_password').value,
    enable_latency_logs: document.getElementById('c-enable_latency_logs').checked,
    atr_buffer_multiplier: parseFloat(document.getElementById('c-atr_buffer_multiplier').value),
    use_liquidity_tp: document.getElementById('c-use_liquidity_tp').checked,
    enable_smart_tp: document.getElementById('c-enable_smart_tp').checked,
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
    min_sl_atr_multiplier: parseFloat(document.getElementById('c-min_sl_atr_multiplier').value),
    trailing_start_tp_pct: parseFloat(document.getElementById('c-trailing_start_tp_pct').value),
    trailing_mode: document.getElementById('c-trailing_mode').value,
    trailing_atr_multiplier: parseFloat(document.getElementById('c-trailing_atr_multiplier').value),
    trailing_distance_pips: parseFloat(document.getElementById('c-trailing_distance_pips').value),
    volume_filter_enabled: document.getElementById('c-volume_filter_enabled').checked,
    volume_lookback: parseInt(document.getElementById('c-volume_lookback').value),
    min_volume_ratio: parseFloat(document.getElementById('c-min_volume_ratio').value),
    strong_volume_ratio: parseFloat(document.getElementById('c-strong_volume_ratio').value),
    volume_score_bonus: parseInt(document.getElementById('c-volume_score_bonus').value),
    volume_use_ema: document.getElementById('c-volume_use_ema').checked,
    volume_low_downgrade_only: document.getElementById('c-volume_low_downgrade_only').checked,
    session_warmup_enabled: document.getElementById('c-session_warmup_enabled').checked,
    session_min_warmup_minutes: parseInt(document.getElementById('c-session_min_warmup_minutes').value),
    session_max_warmup_minutes: parseInt(document.getElementById('c-session_max_warmup_minutes').value),
    session_warmup_require_closed_m5: document.getElementById('c-session_warmup_require_closed_m5').checked,
    session_warmup_spread_multiplier: parseFloat(document.getElementById('c-session_warmup_spread_multiplier').value),
    session_warmup_volatility_multiplier: parseFloat(document.getElementById('c-session_warmup_volatility_multiplier').value)
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

function applyJsonText() {
  const text = document.getElementById('c-import_json').value;
  if (!text.trim()) return;

  try {
    const data = JSON.parse(text);

    const inputs = {
      correlation_groups_enabled: 'c-correlation_groups_enabled',
      max_open_per_correlation_group: 'c-max_open_per_correlation_group',
      max_open_positions: 'c-max_open_positions',
      max_signals_per_scan: 'c-max_signals_per_scan',
      max_per_symbol: 'c-max_per_symbol',
      max_per_direction: 'c-max_per_direction',
      max_spread_pct: 'c-max_spread_pct',
      signal_threshold: 'c-signal_threshold',
      risk_percent: 'c-risk_percent',
      scan_interval_seconds: 'c-scan_interval_seconds',
      scan_concurrency: 'c-scan_concurrency',
      close_all_concurrency: 'c-close_all_concurrency',
      signal_cooldown_minutes: 'c-signal_cooldown_minutes',
      reward_ratio: 'c-reward_ratio',
      magic_number: 'c-magic_number',
      dashboard_password: 'c-dashboard_password',
      enable_latency_logs: 'c-enable_latency_logs',
      atr_buffer_multiplier: 'c-atr_buffer_multiplier',
      use_liquidity_tp: 'c-use_liquidity_tp',
      enable_smart_tp: 'c-enable_smart_tp',
      breakeven_trigger_r: 'c-breakeven_trigger_r',
      trailing: 'c-trailing',
      enable_dca: 'c-enable_dca',
      max_dca_entries: 'c-max_dca_entries',
      max_dca_per_scan: 'c-max_dca_per_scan',
      dca_trigger_sl_progress: 'c-dca_trigger_sl_progress',
      dca_lot_multiplier: 'c-dca_lot_multiplier',
      dca_max_total_risk_r: 'c-dca_max_total_risk_r',
      dca_reanchor_sl: 'c-dca_reanchor_sl',
      enable_basket_trailing: 'c-enable_basket_trailing',
      basket_trailing_start_usd: 'c-basket_trailing_start_usd',
      basket_trailing_drawdown_usd: 'c-basket_trailing_drawdown_usd',
      basket_trailing_min_close_usd: 'c-basket_trailing_min_close_usd',
      min_sl_atr_multiplier: 'c-min_sl_atr_multiplier',
      trailing_start_tp_pct: 'c-trailing_start_tp_pct',
      trailing_mode: 'c-trailing_mode',
      trailing_atr_multiplier: 'c-trailing_atr_multiplier',
      trailing_distance_pips: 'c-trailing_distance_pips',
      volume_filter_enabled: 'c-volume_filter_enabled',
      volume_lookback: 'c-volume_lookback',
      min_volume_ratio: 'c-min_volume_ratio',
      strong_volume_ratio: 'c-strong_volume_ratio',
      volume_score_bonus: 'c-volume_score_bonus',
      volume_use_ema: 'c-volume_use_ema',
      volume_low_downgrade_only: 'c-volume_low_downgrade_only',
      session_warmup_enabled: 'c-session_warmup_enabled',
      session_min_warmup_minutes: 'c-session_min_warmup_minutes',
      session_max_warmup_minutes: 'c-session_max_warmup_minutes',
      session_warmup_require_closed_m5: 'c-session_warmup_require_closed_m5',
      session_warmup_spread_multiplier: 'c-session_warmup_spread_multiplier',
      session_warmup_volatility_multiplier: 'c-session_warmup_volatility_multiplier'
    };

    for (const [key, id] of Object.entries(inputs)) {
      if (data[key] !== undefined) {
        const el = document.getElementById(id);
        if (el) {
          if (el.type === 'checkbox') el.checked = data[key];
          else el.value = data[key];
          if (el.type === 'range') el.dispatchEvent(new Event('input'));
        }
      }
    }

    if (Array.isArray(data.symbols)) {
      state.symbols = data.symbols.map(s => typeof s === 'string' ? { generic: s, resolved: null, status: 'pending' } : s);
      renderPredefinedSymbols();
      resolveAllSymbols();
    }

    if (Array.isArray(data.enabled_correlation_groups)) {
      state.enabled_correlation_groups = data.enabled_correlation_groups;
    }

    renderCorrelationGroups();

    if (Array.isArray(data.sessions)) {
      document.getElementById('sessions-list').innerHTML = '';
      data.sessions.forEach(s => {
        if (Array.isArray(s.days)) {
          const dayNames = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'];
          let mask = 0;
          s.days.forEach(d => {
            const idx = dayNames.indexOf(d.toLowerCase().trim());
            if (idx !== -1) mask |= (1 << idx);
          });
          s.days_mask = mask;
        } else if (s.days_mask === undefined) {
          s.days_mask = 31; // Default Mon-Fri
        }
        addSessionRow(s);
      });
    }

    alert("JSON applied to form. Click 'SAVE CHANGES' to submit.");
    document.getElementById('c-import_json').value = '';

    // switch to general tab to see changes
    const generalTab = document.querySelector('.m-tab[data-mtab="general"]');
    if (generalTab) generalTab.click();

  } catch (err) {
    alert("Failed to parse JSON text. Ensure it is valid JSON.");
    console.error(err);
  }
}

async function saveConfig() {
  const btn = document.getElementById('save-config-btn');
  if (btn) { btn.innerHTML = 'SAVING...'; btn.disabled = true; }
  try {
    const payload1 = collectConfigInputs();
    await api('PATCH', '/api/config', payload1);

    const payload2 = { symbols: state.symbols.filter(s => s.status !== 'unresolved').map(s => s.generic) };
    await api('PATCH', '/api/config', payload2);

    await syncSessions();

    // Update local state config
    state.config = { ...state.config, ...payload1, ...payload2 };
    state.config.enabled_correlation_groups = state.enabled_correlation_groups;

    closeConfigModal();
    renderScannerStatus(); // Refresh scanner list to show/hide symbols immediately
  } catch (err) {
    alert("Error saving config: " + err.message);
    console.error(err);
  } finally {
    if (btn) { btn.innerHTML = 'SAVE CHANGES'; btn.disabled = false; }
  }
}

function exportConfig() {
  const payload = collectConfigInputs();
  payload.symbols = state.symbols.filter(s => s.status !== 'unresolved').map(s => s.generic);
  payload.enabled_correlation_groups = state.enabled_correlation_groups;
  
  const dayNames = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'];
  const rows = document.querySelectorAll('.session-row');
  payload.sessions = Array.from(rows).map(row => {
    let days_mask = 0;
    const days = [];
    row.querySelectorAll('.day-checks input:checked').forEach(cb => {
      const idx = parseInt(cb.dataset.day);
      days_mask |= (1 << idx);
      days.push(dayNames[idx]);
    });
    const id = row.dataset.id.startsWith('new-') ? null : parseInt(row.dataset.id);
    return {
      id,
      name: row.querySelector('.s-name').value,
      start_time: row.querySelector('.s-start').value,
      end_time: row.querySelector('.s-end').value,
      timezone: row.querySelector('.s-tz').value,
      days_mask,
      days,
      enabled: row.querySelector('.s-on').checked
    };
  });
  
  const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(payload, null, 2));
  const downloadAnchorNode = document.createElement('a');
  downloadAnchorNode.setAttribute("href", dataStr);
  downloadAnchorNode.setAttribute("download", "bot_config.json");
  document.body.appendChild(downloadAnchorNode);
  downloadAnchorNode.click();
  downloadAnchorNode.remove();
}

// ---- Init ----
async function init() {
  connectWS();
  try {
    const [status, initData, cfg] = await Promise.all([
      api('GET', '/api/status'),
      api('GET', '/api/initial_data').catch(() => null),
      api('GET', '/api/config').catch(() => ({}))
    ]);
    Object.assign(state, status);
    state.config = cfg;
    if (cfg && Array.isArray(cfg.symbols)) {
      state.symbols = cfg.symbols.map(s => ({ generic: s, original: s, resolved: null, status: 'pending' }));
      resolveAllSymbols();
    }

    if (initData) {
      state.open_positions = initData.trades.filter(t => !t.closed_at);
      state.closed_trades = initData.trades.filter(t => t.closed_at);
      state.all_signals = initData.signals;
      state.recent_signals = initData.signals.slice(0, 5);
      state.events = initData.events;
      if (initData.scanner_status) {
        state.scanner_status = initData.scanner_status;
      }

      const todayStr = new Date().toISOString().split('T')[0];
      state.today_pnl = state.closed_trades
        .filter(t => t.closed_at && t.closed_at.startsWith(todayStr))
        .reduce((sum, t) => sum + (t.pnl || 0), 0);
    }
  } catch (err) { console.error("Init Error:", err); }

  renderTopbar(); renderStats(); renderEngineBtn(); renderNotice();
  renderPositions(); renderTrades(); renderSignals(); renderLogs();
  renderScannerStatus();
}
init();

// Ensure global scope exposure for inline HTML onclick handlers
window.checkSignalResults = checkSignalResults;
window.clearSignalResults = clearSignalResults;
window.clearAllSignals = clearAllSignals;
