function isResolvedSignal(s) {
  return s.result === 'TP HIT' || s.result === 'SL HIT' || s.result === 'SMART TP HIT';
}

function isTpResult(res) {
  return res === 'TP HIT' || res === 'SMART TP HIT';
}

function isSlResult(res) {
  return res === 'SL HIT';
}

function isSkippedSignal(s) {
  return s.status === 'SKIPPED' || s.status === 'DCA_SKIPPED' || s.status === 'SIGNAL_ONLY';
}

function getSignalResult(s) {
  return s.result;
}

function getSignalScore(s) {
  return s.score || 0;
}

function getSignalSymbol(s) {
  return s.symbol || 'UNKNOWN';
}

function getSignalDirection(s) {
  return (s.direction || 'UNKNOWN').toUpperCase();
}

function getTriggerLabel(s) {
  return s.reason?.trigger?.trigger_type || "Unknown";
}

function getZoneLabel(s) {
  return s.reason?.zone?.reason?.type || "Unknown";
}

function getSkipReason(s) {
  return s.skip_reason || s.reason?.skip_reason || "Unknown";
}

function formatPercent(value) {
  return value.toFixed(1) + "%";
}

function getFilteredSignalsForAnalytics() {
  // Use the globally available displaySignals array from app.js
  return window.displaySignals || [];
}

function buildGroupStats(signals, groupFn) {
  const groups = {};
  signals.forEach(s => {
    const key = groupFn(s);
    if (!key) return;
    
    if (!groups[key]) {
      groups[key] = {
        total: 0, fired: 0, skipped: 0,
        wins: 0, losses: 0,
        missedWins: 0, missedLosses: 0,
        scoreSum: 0, signals: []
      };
    }
    
    const g = groups[key];
    g.total++;
    g.scoreSum += getSignalScore(s);
    g.signals.push(s);
    
    const isFired = s.status === 'FIRED' || s.status === 'DCA_FIRED';
    const isSkipped = isSkippedSignal(s);
    const win = isTpResult(s.result);
    const loss = isSlResult(s.result);
    
    if (isFired) {
      g.fired++;
      if (win) g.wins++;
      if (loss) g.losses++;
    } else if (isSkipped) {
      g.skipped++;
      if (win) g.missedWins++;
      if (loss) g.missedLosses++;
    }
  });
  
  for (const k in groups) {
    const g = groups[k];
    g.resolved = g.wins + g.losses;
    g.winRate = g.resolved > 0 ? (g.wins / g.resolved) * 100 : 0;
    g.missedResolved = g.missedWins + g.missedLosses;
    g.missedRate = g.missedResolved > 0 ? (g.missedWins / g.missedResolved) * 100 : 0;
    g.avgScore = g.total > 0 ? g.scoreSum / g.total : 0;
  }
  
  return groups;
}

function gradeWinRate(winRate, sample, minSample) {
  if (sample < minSample) return { grade: "LOW DATA", action: "Need more data", color: "text-slate-500" };
  if (winRate >= 60) return { grade: "A", action: "Keep", color: "text-emerald-400" };
  if (winRate >= 52) return { grade: "B", action: "Keep / Monitor", color: "text-emerald-300" };
  if (winRate >= 45) return { grade: "C", action: "Needs filter", color: "text-amber-400" };
  return { grade: "D", action: "Avoid / Disable", color: "text-rose-400" };
}

function renderPanelHtml(title, tableHeaderHtml, tableBodyHtml, summaryHtml = '') {
  return `
    <div class="bg-panel border border-border_light rounded p-3 mb-4 overflow-hidden flex flex-col gap-2">
      <div class="text-[11px] font-bold tracking-widest text-slate-300 uppercase border-b border-border_strong pb-1">${title}</div>
      ${summaryHtml ? `<div class="text-[10px] text-slate-400 mb-1">${summaryHtml}</div>` : ''}
      <div class="overflow-x-auto">
        <table class="w-full text-left whitespace-nowrap">
          <thead>
            <tr class="text-[9px] tracking-widest text-slate-500 uppercase border-b border-border_light">
              ${tableHeaderHtml}
            </tr>
          </thead>
          <tbody class="divide-y divide-white/5">
            ${tableBodyHtml}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function renderSmartRecommendations(signals, minSample) {
  const recs = [];
  
  const bySymDir = buildGroupStats(signals, s => `${getSignalSymbol(s)} ${getSignalDirection(s)}`);
  for (const [key, g] of Object.entries(bySymDir)) {
    if (g.resolved >= minSample) {
      if (g.winRate < 45) recs.push({ text: `Avoid ${key} — ${g.resolved} resolved, ${g.winRate.toFixed(0)}% win rate.`, type: "AVOID", score: 100 - g.winRate });
      if (g.winRate >= 58) recs.push({ text: `Keep ${key} — ${g.resolved} resolved, ${g.winRate.toFixed(0)}% win rate.`, type: "GOOD", score: g.winRate });
    }
  }

  const byTriggerZone = buildGroupStats(signals, s => `${getTriggerLabel(s)} + ${getZoneLabel(s)}`);
  for (const [key, g] of Object.entries(byTriggerZone)) {
    if (g.resolved >= minSample) {
      if (g.winRate >= 60) recs.push({ text: `${key} is strongest setup — ${g.resolved} resolved, ${g.winRate.toFixed(0)}% WR.`, type: "GOOD", score: g.winRate });
    }
  }
  
  const bySkip = buildGroupStats(signals, s => getSkipReason(s));
  for (const [key, g] of Object.entries(bySkip)) {
    if (key !== "Unknown" && g.missedResolved >= minSample && g.missedRate >= 55) {
      recs.push({ text: `Cooldown/Filter '${key}' may be too strict — ${g.missedWins} missed wins (${g.missedRate.toFixed(0)}% WR).`, type: "TUNE", score: g.missedRate });
    }
  }

  recs.sort((a, b) => b.score - a.score);
  
  if (recs.length === 0) {
    recs.push({ text: "Need more data for smart recommendations.", type: "WATCH", score: 0 });
  }

  const getTypeBadge = (type) => {
    const colors = {
      GOOD: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
      WATCH: "bg-amber-500/20 text-amber-400 border-amber-500/30",
      AVOID: "bg-rose-500/20 text-rose-400 border-rose-500/30",
      TUNE: "bg-cyan-500/20 text-cyan-400 border-cyan-500/30",
    };
    return `<span class="px-1.5 py-0.5 rounded text-[8px] font-bold uppercase border ${colors[type]}">${type}</span>`;
  };

  const rows = recs.slice(0, 5).map(r => `
    <tr>
      <td class="px-2 py-2">${getTypeBadge(r.type)}</td>
      <td class="px-2 py-2 text-[10px] text-slate-300">${r.text}</td>
    </tr>
  `).join('');

  return renderPanelHtml("SMART RECOMMENDATIONS", `<th class="px-2 py-1 font-normal w-16">Type</th><th class="px-2 py-1 font-normal">Insight</th>`, rows);
}

function renderSymbolDirectionMatrix(signals, minSample) {
  const stats = buildGroupStats(signals, s => `${getSignalSymbol(s)}_${getSignalDirection(s)}`);
  
  let rows = Object.values(stats).map(g => {
    const sym = getSignalSymbol(g.signals[0]);
    const dir = getSignalDirection(g.signals[0]);
    const grade = gradeWinRate(g.winRate, g.resolved, minSample);
    
    return `
      <tr class="hover:bg-white/5 transition-colors">
        <td class="px-2 py-1.5 text-[10px] font-bold text-slate-200">${sym}</td>
        <td class="px-2 py-1.5 text-[10px] ${dir === 'BUY' ? 'text-emerald-400' : 'text-rose-400'}">${dir}</td>
        <td class="px-2 py-1.5 text-[10px] font-mono text-slate-400 text-right">${g.resolved}</td>
        <td class="px-2 py-1.5 text-[10px] font-mono text-emerald-400 text-right">${g.wins}</td>
        <td class="px-2 py-1.5 text-[10px] font-mono text-rose-400 text-right">${g.losses}</td>
        <td class="px-2 py-1.5 text-[10px] font-mono font-bold ${grade.color} text-right">${formatPercent(g.winRate)}</td>
        <td class="px-2 py-1.5 text-[10px] font-mono ${grade.color} text-center">${grade.grade}</td>
        <td class="px-2 py-1.5 text-[10px] text-slate-400 text-right">${grade.action}</td>
      </tr>
    `;
  }).join('');

  if (!rows) rows = `<tr><td colspan="8" class="text-center text-[10px] text-slate-500 py-4">No data</td></tr>`;

  return renderPanelHtml(
    "SYMBOL / DIRECTION PERFORMANCE",
    `
      <th class="px-2 py-1 font-normal">Symbol</th>
      <th class="px-2 py-1 font-normal">Dir</th>
      <th class="px-2 py-1 font-normal text-right">Res</th>
      <th class="px-2 py-1 font-normal text-right">TP</th>
      <th class="px-2 py-1 font-normal text-right">SL</th>
      <th class="px-2 py-1 font-normal text-right">WR</th>
      <th class="px-2 py-1 font-normal text-center">Grade</th>
      <th class="px-2 py-1 font-normal text-right">Action</th>
    `,
    rows
  );
}

function renderScoreThresholdOptimizer(signals, minSample) {
  const buckets = { "0-49": [], "50-59": [], "60-69": [], "70-79": [], "80-89": [], "90-100": [] };
  const isFired = s => s.status === 'FIRED' || s.status === 'DCA_FIRED' || s.status === 'SIGNAL_ONLY';
  
  signals.forEach(s => {
    if (!isResolvedSignal(s) || !isFired(s)) return;
    const sc = getSignalScore(s);
    if (sc < 50) buckets["0-49"].push(s);
    else if (sc < 60) buckets["50-59"].push(s);
    else if (sc < 70) buckets["60-69"].push(s);
    else if (sc < 80) buckets["70-79"].push(s);
    else if (sc < 90) buckets["80-89"].push(s);
    else buckets["90-100"].push(s);
  });
  
  let rowsHtml = '';
  for (const [range, list] of Object.entries(buckets)) {
    const total = list.length;
    const wins = list.filter(s => isTpResult(s.result)).length;
    const losses = list.filter(s => isSlResult(s.result)).length;
    const wr = total > 0 ? (wins / total) * 100 : 0;
    
    let action = "Monitor";
    let color = "text-slate-400";
    if (total < minSample) { action = "Low data"; color = "text-slate-500"; }
    else if (wr >= 58) { action = "Good"; color = "text-emerald-400"; }
    else if (wr < 45) { action = "Avoid below this area"; color = "text-rose-400"; }
    
    rowsHtml += `
      <tr class="hover:bg-white/5 transition-colors">
        <td class="px-2 py-1.5 text-[10px] text-slate-300">${range}</td>
        <td class="px-2 py-1.5 text-[10px] font-mono text-slate-400 text-right">${total}</td>
        <td class="px-2 py-1.5 text-[10px] font-mono text-emerald-400 text-right">${wins}</td>
        <td class="px-2 py-1.5 text-[10px] font-mono text-rose-400 text-right">${losses}</td>
        <td class="px-2 py-1.5 text-[10px] font-mono font-bold ${color} text-right">${formatPercent(wr)}</td>
        <td class="px-2 py-1.5 text-[10px] ${color} text-right">${action}</td>
      </tr>
    `;
  }
  
  // Optimizer logic
  const thresholds = [50, 55, 60, 65, 70, 75, 80];
  let bestT = null;
  let bestWR = 0;
  let bestSample = 0;
  
  const firedRes = signals.filter(s => isFired(s) && isResolvedSignal(s));
  
  for (const t of thresholds) {
    const above = firedRes.filter(s => getSignalScore(s) >= t);
    const w = above.filter(s => isTpResult(s.result)).length;
    const tot = above.length;
    if (tot >= minSample) {
      const wr = (w / tot) * 100;
      if (!bestT || (wr >= 55 && bestT.wr < 55) || (wr > bestWR && bestT.wr >= 55 === wr >= 55)) {
         if(!bestT || (wr >= 55 && bestT === null)) {
            bestT = t;
            bestWR = wr;
            bestSample = tot;
         }
      }
    }
  }
  
  let summary = "Suggested min score: ";
  if (bestT) {
    summary += `<span class="text-emerald-400 font-bold">${bestT}</span> — ${bestWR.toFixed(1)}% WR over ${bestSample} resolved signals.`;
  } else {
    summary += `<span class="text-slate-500">Needs more validation.</span>`;
  }

  return renderPanelHtml(
    "SCORE THRESHOLD OPTIMIZER",
    `
      <th class="px-2 py-1 font-normal">Score Range</th>
      <th class="px-2 py-1 font-normal text-right">Res</th>
      <th class="px-2 py-1 font-normal text-right">TP</th>
      <th class="px-2 py-1 font-normal text-right">SL</th>
      <th class="px-2 py-1 font-normal text-right">WR</th>
      <th class="px-2 py-1 font-normal text-right">Recommendation</th>
    `,
    rowsHtml,
    summary
  );
}

function renderTriggerZoneAnalysis(signals, minSample) {
  const stats = buildGroupStats(signals, s => `${getTriggerLabel(s)}|||${getZoneLabel(s)}`);
  
  let arr = Object.values(stats);
  arr.sort((a, b) => {
    if (a.resolved < minSample && b.resolved >= minSample) return 1;
    if (b.resolved < minSample && a.resolved >= minSample) return -1;
    return b.winRate - a.winRate;
  });
  
  let rows = arr.slice(0, 12).map(g => {
    const [trig, zone] = g.signals[0] ? `${getTriggerLabel(g.signals[0])}|||${getZoneLabel(g.signals[0])}`.split('|||') : ['-', '-'];
    const grade = gradeWinRate(g.winRate, g.resolved, minSample);
    
    return `
      <tr class="hover:bg-white/5 transition-colors">
        <td class="px-2 py-1.5 text-[10px] text-cyan-400 truncate max-w-[120px]" title="${trig}">${trig}</td>
        <td class="px-2 py-1.5 text-[10px] text-purple-400 truncate max-w-[120px]" title="${zone}">${zone}</td>
        <td class="px-2 py-1.5 text-[10px] font-mono text-slate-400 text-right">${g.resolved}</td>
        <td class="px-2 py-1.5 text-[10px] font-mono text-emerald-400 text-right">${g.wins}</td>
        <td class="px-2 py-1.5 text-[10px] font-mono text-rose-400 text-right">${g.losses}</td>
        <td class="px-2 py-1.5 text-[10px] font-mono font-bold ${grade.color} text-right">${formatPercent(g.winRate)}</td>
        <td class="px-2 py-1.5 text-[10px] font-mono ${grade.color} text-center">${grade.grade}</td>
        <td class="px-2 py-1.5 text-[10px] text-slate-400 text-right">${grade.action}</td>
      </tr>
    `;
  }).join('');

  if (!rows) rows = `<tr><td colspan="8" class="text-center text-[10px] text-slate-500 py-4">No data</td></tr>`;

  return renderPanelHtml(
    "TRIGGER + ZONE SETUP ANALYSIS",
    `
      <th class="px-2 py-1 font-normal">Trigger</th>
      <th class="px-2 py-1 font-normal">Zone</th>
      <th class="px-2 py-1 font-normal text-right">Res</th>
      <th class="px-2 py-1 font-normal text-right">TP</th>
      <th class="px-2 py-1 font-normal text-right">SL</th>
      <th class="px-2 py-1 font-normal text-right">WR</th>
      <th class="px-2 py-1 font-normal text-center">Grade</th>
      <th class="px-2 py-1 font-normal text-right">Action</th>
    `,
    rows
  );
}

function renderTimeOfDayPerformance(signals, minSample) {
  const tz = document.getElementById('signal-timezone')?.value || 'UTC';
  
  const getBlock = (s) => {
    if (!s.created_at) return null;
    try {
      const d = new Date(s.created_at + "Z");
      const hStr = new Intl.DateTimeFormat('en-US', { hour: 'numeric', hour12: false, timeZone: tz }).format(d);
      const h = parseInt(hStr, 10);
      if (isNaN(h)) return null;
      const start = Math.floor(h / 2) * 2;
      const end = (start + 2) % 24;
      const pad = n => n.toString().padStart(2, '0');
      return `${pad(start)}:00-${pad(end)}:00`;
    } catch(e) { return null; }
  };
  
  const stats = buildGroupStats(signals, getBlock);
  let arr = Object.keys(stats).map(k => ({ timeBlock: k, ...stats[k] }));
  arr.sort((a, b) => a.timeBlock.localeCompare(b.timeBlock));
  
  let best = null, worst = null;
  arr.forEach(g => {
    if (g.resolved >= minSample) {
      if (!best || g.winRate > best.winRate) best = g;
      if (!worst || g.winRate < worst.winRate) worst = g;
    }
  });
  
  let rows = arr.map(g => {
    let action = "Monitor", color = "text-slate-400";
    if (g.resolved < minSample) { action = "Low data"; color = "text-slate-500"; }
    else if (g.winRate >= 58) { action = "Good window"; color = "text-emerald-400"; }
    else if (g.winRate < 45) { action = "Avoid window"; color = "text-rose-400"; }
    
    return `
      <tr class="hover:bg-white/5 transition-colors">
        <td class="px-2 py-1.5 text-[10px] text-slate-300 font-mono">${g.timeBlock}</td>
        <td class="px-2 py-1.5 text-[10px] font-mono text-slate-400 text-right">${g.resolved}</td>
        <td class="px-2 py-1.5 text-[10px] font-mono text-emerald-400 text-right">${g.wins}</td>
        <td class="px-2 py-1.5 text-[10px] font-mono text-rose-400 text-right">${g.losses}</td>
        <td class="px-2 py-1.5 text-[10px] font-mono font-bold ${color} text-right">${formatPercent(g.winRate)}</td>
        <td class="px-2 py-1.5 text-[10px] ${color} text-right">${action}</td>
      </tr>
    `;
  }).join('');
  
  let summary = "";
  if (best) summary += `Best: <span class="text-emerald-400">${best.timeBlock}</span> `;
  if (worst) summary += `| Worst: <span class="text-rose-400">${worst.timeBlock}</span>`;

  if (!rows) rows = `<tr><td colspan="6" class="text-center text-[10px] text-slate-500 py-4">No data</td></tr>`;

  return renderPanelHtml(
    "TIME OF DAY PERFORMANCE",
    `
      <th class="px-2 py-1 font-normal">Time Block</th>
      <th class="px-2 py-1 font-normal text-right">Res</th>
      <th class="px-2 py-1 font-normal text-right">TP</th>
      <th class="px-2 py-1 font-normal text-right">SL</th>
      <th class="px-2 py-1 font-normal text-right">WR</th>
      <th class="px-2 py-1 font-normal text-right">Action</th>
    `,
    rows,
    summary
  );
}

function renderSkippedMissedWinAnalysis(signals, minSample) {
  const stats = buildGroupStats(signals, s => getSkipReason(s));
  
  let rows = Object.entries(stats).map(([reason, g]) => {
    if (reason === "Unknown" || g.skipped === 0) return '';
    
    let action = "Monitor", color = "text-slate-400";
    if (g.missedResolved < minSample) { action = "Low data"; color = "text-slate-500"; }
    else if (g.missedRate >= 55) { action = "May be too strict"; color = "text-amber-400"; }
    else if (g.missedRate < 35) { action = "Good block"; color = "text-emerald-400"; }
    
    return `
      <tr class="hover:bg-white/5 transition-colors">
        <td class="px-2 py-1.5 text-[10px] text-slate-300">${reason}</td>
        <td class="px-2 py-1.5 text-[10px] font-mono text-slate-400 text-right">${g.skipped}</td>
        <td class="px-2 py-1.5 text-[10px] font-mono text-emerald-400 text-right">${g.missedWins}</td>
        <td class="px-2 py-1.5 text-[10px] font-mono text-rose-400 text-right">${g.missedLosses}</td>
        <td class="px-2 py-1.5 text-[10px] font-mono font-bold ${color} text-right">${formatPercent(g.missedRate)}</td>
        <td class="px-2 py-1.5 text-[10px] ${color} text-right">${action}</td>
      </tr>
    `;
  }).filter(Boolean).join('');
  
  if (!rows) rows = `<tr><td colspan="6" class="text-center text-[10px] text-slate-500 py-4">No skipped data</td></tr>`;

  return renderPanelHtml(
    "SKIPPED SIGNAL / MISSED WIN ANALYSIS",
    `
      <th class="px-2 py-1 font-normal">Skip Reason</th>
      <th class="px-2 py-1 font-normal text-right">Skipped</th>
      <th class="px-2 py-1 font-normal text-right">M. Wins</th>
      <th class="px-2 py-1 font-normal text-right">M. Losses</th>
      <th class="px-2 py-1 font-normal text-right">M. WR</th>
      <th class="px-2 py-1 font-normal text-right">Action</th>
    `,
    rows
  );
}

function renderSlBufferAnalysisPlaceholder() {
  return renderPanelHtml(
    "SL EFFICIENCY / BUFFER SIMULATION",
    `<th></th>`,
    `<tr><td class="px-2 py-6 text-center text-[10px] text-slate-500">
      <div class="mb-2">Click below to fetch backend candle replays and run SL simulation.</div>
      <button onclick="fetchSlBufferAnalysis()" class="bg-blue-600 hover:bg-blue-500 text-white px-3 py-1.5 rounded transition-colors uppercase tracking-widest font-bold">Run Simulation</button>
      <div id="sl-sim-loading" class="hidden mt-2 text-blue-400 animate-pulse">Running simulation (this may take a while)...</div>
    </td></tr>`
  );
}

async function fetchSlBufferAnalysis() {
  const loading = document.getElementById('sl-sim-loading');
  if(loading) loading.classList.remove('hidden');
  
  try {
    const res = await fetch('/api/signals/sl-buffer-analysis');
    const data = await res.json();
    window.slBufferAnalysisData = data.data;
    renderSignalAnalytics(window.displaySignals); // Re-render to show actual data
  } catch(e) {
    alert("Simulation failed: " + e.message);
    if(loading) loading.classList.add('hidden');
  }
}

function renderSlBufferAnalysisActual(analysisData, minSample) {
  // Aggregate data by Symbol_Direction
  const groups = {};
  analysisData.forEach(d => {
    const k = `${d.symbol}_${d.direction.toUpperCase()}`;
    if(!groups[k]) groups[k] = { total: 0, w: { '0.0': 0, '0.25': 0, '0.5': 0, '0.75': 0, '1.0': 0 } };
    groups[k].total++;
    for(const buf in d.scenarios) {
      if(isTpResult(d.scenarios[buf])) groups[k].w[buf]++;
    }
  });
  
  let rows = Object.entries(groups).map(([key, g]) => {
    const wr = (buf) => g.total > 0 ? (g.w[buf] / g.total) * 100 : 0;
    const baseWR = wr('0.0');
    const wr25 = wr('0.25');
    const wr50 = wr('0.5');
    
    let note = "Monitor";
    let color = "text-slate-400";
    if (g.total < minSample) { note = "Need more data"; color = "text-slate-500"; }
    else if (wr50 >= baseWR + 8 || wr25 >= baseWR + 8) { note = "SL likely too tight"; color = "text-amber-400"; }
    else if (wr50 < baseWR + 3) { note = "No SL benefit"; color = "text-slate-400"; }
    else { note = "WR improves but risk increases"; color = "text-cyan-400"; }
    
    const saved = g.w['0.5'] - g.w['0.0'];
    
    const wrFmt = (val) => `<span class="${val >= baseWR && val > 0 ? 'text-emerald-400 font-bold' : ''}">${val.toFixed(1)}%</span>`;
    
    return `
      <tr class="hover:bg-white/5 transition-colors">
        <td class="px-2 py-1.5 text-[10px] text-slate-200 font-bold">${key.replace('_', ' ')}</td>
        <td class="px-2 py-1.5 text-[10px] font-mono text-slate-400 text-right">${g.total}</td>
        <td class="px-2 py-1.5 text-[10px] font-mono text-slate-300 text-right">${baseWR.toFixed(1)}%</td>
        <td class="px-2 py-1.5 text-[10px] font-mono text-right">${wrFmt(wr('0.25'))}</td>
        <td class="px-2 py-1.5 text-[10px] font-mono text-right">${wrFmt(wr('0.5'))}</td>
        <td class="px-2 py-1.5 text-[10px] font-mono text-right">${wrFmt(wr('0.75'))}</td>
        <td class="px-2 py-1.5 text-[10px] font-mono text-right">${wrFmt(wr('1.0'))}</td>
        <td class="px-2 py-1.5 text-[10px] font-mono text-emerald-400 text-right">${saved > 0 ? '+'+saved : saved}</td>
        <td class="px-2 py-1.5 text-[10px] ${color} text-right">${note}</td>
      </tr>
    `;
  }).join('');
  
  return renderPanelHtml(
    "SL EFFICIENCY / BUFFER SIMULATION",
    `
      <th class="px-2 py-1 font-normal">Group</th>
      <th class="px-2 py-1 font-normal text-right">Res</th>
      <th class="px-2 py-1 font-normal text-right">0R WR</th>
      <th class="px-2 py-1 font-normal text-right">+0.25R</th>
      <th class="px-2 py-1 font-normal text-right">+0.5R</th>
      <th class="px-2 py-1 font-normal text-right">+0.75R</th>
      <th class="px-2 py-1 font-normal text-right">+1.0R</th>
      <th class="px-2 py-1 font-normal text-right">Saved</th>
      <th class="px-2 py-1 font-normal text-right">Note</th>
    `,
    rows,
    "Warning: Widening SL increases risk. This is a naive simulation and actual R:R will decrease."
  );
}

// Override the global renderSignalAnalytics
window.renderSignalAnalytics = function(signals) {
  const el = document.getElementById("analytics-panels");
  if (!el) return;

  const minSample = Number(document.getElementById("signal-min-sample")?.value || 5);

  const html = [
    renderSmartRecommendations(signals, minSample),
    renderSymbolDirectionMatrix(signals, minSample),
    renderScoreThresholdOptimizer(signals, minSample),
    renderTriggerZoneAnalysis(signals, minSample),
    renderTimeOfDayPerformance(signals, minSample),
    renderSkippedMissedWinAnalysis(signals, minSample),
    window.slBufferAnalysisData 
      ? renderSlBufferAnalysisActual(window.slBufferAnalysisData, minSample) 
      : renderSlBufferAnalysisPlaceholder()
  ].join('');

  // We can render this vertically since the user allowed it and it matches the "analytics-panels" div.
  // Make the container grid 1 or 2 columns based on screen width.
  el.className = "grid grid-cols-1 xl:grid-cols-2 gap-4 mt-4";
  el.innerHTML = html;
};
