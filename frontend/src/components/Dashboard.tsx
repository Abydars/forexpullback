import React from 'react';
import { useStore } from '../store/useStore';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import { Play, Square, Activity, DollarSign, Briefcase } from 'lucide-react';

const Dashboard = () => {
  const { balance, equity, todayPnl, openPositions, signals, equityHistory, engineRunning, startEngine, stopEngine } = useStore();

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold">Dashboard</h2>
        <button
          onClick={engineRunning ? stopEngine : startEngine}
          className={`flex items-center gap-2 px-4 py-2 rounded font-bold ${engineRunning ? 'bg-danger/20 text-danger' : 'bg-success/20 text-success'}`}
        >
          {engineRunning ? <Square size={16} fill="currentColor" /> : <Play size={16} fill="currentColor" />}
          {engineRunning ? 'STOP ENGINE' : 'START ENGINE'}
        </button>
      </div>

      <div className="grid grid-cols-4 gap-4">
        <div className="bg-[#121826] border border-[#1e2a3f] p-4 rounded flex flex-col justify-center">
          <div className="text-muted flex items-center gap-2"><DollarSign size={16}/> Balance</div>
          <div className="text-2xl font-bold tabular-nums">${balance.toFixed(2)}</div>
        </div>
        <div className="bg-[#121826] border border-[#1e2a3f] p-4 rounded flex flex-col justify-center">
          <div className="text-muted flex items-center gap-2"><Activity size={16}/> Equity</div>
          <div className="text-2xl font-bold tabular-nums">${equity.toFixed(2)}</div>
        </div>
        <div className="bg-[#121826] border border-[#1e2a3f] p-4 rounded flex flex-col justify-center">
          <div className="text-muted flex items-center gap-2"><DollarSign size={16}/> Today PnL</div>
          <div className={`text-2xl font-bold tabular-nums ${todayPnl >= 0 ? 'text-success' : 'text-danger'}`}>
            ${todayPnl.toFixed(2)}
          </div>
        </div>
        <div className="bg-[#121826] border border-[#1e2a3f] p-4 rounded flex flex-col justify-center">
          <div className="text-muted flex items-center gap-2"><Briefcase size={16}/> Open Positions</div>
          <div className="text-2xl font-bold tabular-nums">{openPositions.length}</div>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-6">
        <div className="col-span-2 space-y-6">
          <div className="bg-[#121826] border border-[#1e2a3f] p-4 rounded h-[300px]">
            <h3 className="text-lg font-bold mb-4">Equity Curve</h3>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={equityHistory}>
                <XAxis dataKey="time" stroke="#64748b" fontSize={12} />
                <YAxis domain={['auto', 'auto']} stroke="#64748b" fontSize={12} width={60} />
                <Tooltip contentStyle={{backgroundColor: '#0a0e1a', borderColor: '#1e2a3f'}} />
                <Line type="monotone" dataKey="equity" stroke="#3b82f6" strokeWidth={2} dot={false} isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="bg-[#121826] border border-[#1e2a3f] rounded">
            <div className="p-4 border-b border-[#1e2a3f]">
              <h3 className="text-lg font-bold">Open Positions</h3>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-[#1e2a3f] text-sm text-muted">
                    <th className="p-4 font-normal">Ticket</th>
                    <th className="p-4 font-normal">Symbol</th>
                    <th className="p-4 font-normal">Dir</th>
                    <th className="p-4 font-normal">Lot</th>
                    <th className="p-4 font-normal">Entry</th>
                    <th className="p-4 font-normal">SL</th>
                    <th className="p-4 font-normal">TP</th>
                  </tr>
                </thead>
                <tbody className="text-sm">
                  {openPositions.map(p => (
                    <tr key={p.id} className="border-b border-[#1e2a3f]/50">
                      <td className="p-4">{p.ticket}</td>
                      <td className="p-4 font-bold">{p.symbol}</td>
                      <td className={`p-4 font-bold ${p.direction === 'bullish' ? 'text-success' : 'text-danger'}`}>
                        {p.direction.toUpperCase()}
                      </td>
                      <td className="p-4">{p.lot}</td>
                      <td className="p-4 tabular-nums">{p.entry_price}</td>
                      <td className="p-4 tabular-nums">{p.sl}</td>
                      <td className="p-4 tabular-nums">{p.tp}</td>
                    </tr>
                  ))}
                  {openPositions.length === 0 && (
                    <tr><td colSpan={7} className="p-4 text-center text-muted">No open positions</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <div className="bg-[#121826] border border-[#1e2a3f] rounded flex flex-col h-[calc(100vh-250px)]">
          <div className="p-4 border-b border-[#1e2a3f]">
            <h3 className="text-lg font-bold">Live Signals</h3>
          </div>
          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {signals.map(s => (
              <div key={s.id} className="bg-[#0a0e1a] border border-[#1e2a3f] p-3 rounded text-sm">
                <div className="flex justify-between items-center mb-2">
                  <span className="font-bold">{s.symbol}</span>
                  <span className={`px-2 py-0.5 rounded text-xs font-bold ${s.direction === 'bullish' ? 'bg-success/20 text-success' : 'bg-danger/20 text-danger'}`}>
                    {s.direction.toUpperCase()}
                  </span>
                </div>
                <div className="flex justify-between text-muted text-xs mb-2">
                  <span>Score: <span className="text-white">{s.score.toFixed(1)}</span></span>
                  <span>{new Date(s.created_at).toLocaleTimeString()}</span>
                </div>
                <div className="grid grid-cols-2 gap-1 text-xs">
                  <div className="flex justify-between"><span>Entry:</span> <span className="tabular-nums text-white">{s.entry}</span></div>
                  <div className="flex justify-between"><span>SL:</span> <span className="tabular-nums text-white">{s.sl}</span></div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
