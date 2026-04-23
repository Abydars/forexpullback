import { create } from 'zustand';
import { api } from '../api';

interface State {
  mt5Connected: boolean;
  engineRunning: boolean;
  activeSessions: number;
  openPositions: any[];
  signals: any[];
  balance: number;
  equity: number;
  todayPnl: number;
  equityHistory: any[];
  
  fetchStatus: () => Promise<void>;
  connectWs: () => void;
  startEngine: () => Promise<void>;
  stopEngine: () => Promise<void>;
  addSignal: (signal: any) => void;
  addTrade: (trade: any) => void;
  removeTrade: (ticket: number) => void;
  updateTick: (data: any) => void;
}

export const useStore = create<State>((set, get) => ({
  mt5Connected: false,
  engineRunning: false,
  activeSessions: 0,
  openPositions: [],
  signals: [],
  balance: 0,
  equity: 0,
  todayPnl: 0,
  equityHistory: [],

  fetchStatus: async () => {
    try {
      const { engine_state } = await api.get('/status');
      set({
        mt5Connected: engine_state.mt5_connected,
        engineRunning: engine_state.is_running,
        activeSessions: engine_state.active_sessions_count,
      });
      
      const positions = await api.get('/trades?status=open');
      set({ openPositions: positions });
      
      const recentSignals = await api.get('/signals?limit=20');
      set({ signals: recentSignals });
      
    } catch (e) {
      console.error(e);
    }
  },

  connectWs: () => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;
    const ws = new WebSocket(wsUrl);
    
    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      if (msg.type === 'signal.new') get().addSignal(msg.data);
      else if (msg.type === 'trade.opened') get().addTrade(msg.data);
      else if (msg.type === 'trade.closed') get().removeTrade(msg.data.ticket);
      else if (msg.type === 'account.tick') get().updateTick(msg.data);
    };
    
    ws.onclose = () => setTimeout(get().connectWs, 5000);
    
    setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'ping' }));
      }
    }, 20000);
  },

  startEngine: async () => {
    const res = await api.post('/engine/start');
    set({ engineRunning: res.is_running });
  },

  stopEngine: async () => {
    const res = await api.post('/engine/stop');
    set({ engineRunning: res.is_running });
  },

  addSignal: (signal) => set((state) => ({ signals: [signal, ...state.signals].slice(0, 20) })),
  addTrade: (trade) => set((state) => ({ openPositions: [trade, ...state.openPositions] })),
  removeTrade: (ticket) => set((state) => ({ openPositions: state.openPositions.filter(t => t.ticket !== ticket) })),
  updateTick: (data) => set((state) => {
    const history = [...state.equityHistory, { time: new Date().toLocaleTimeString(), equity: data.equity }];
    if (history.length > 50) history.shift();
    return { balance: data.balance, equity: data.equity, equityHistory: history };
  })
}));
