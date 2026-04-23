import React, { useState, useEffect } from 'react';
import { api } from '../api';
import { X } from 'lucide-react';

const ConfigModal = ({ onClose }: { onClose: () => void }) => {
  const [activeTab, setActiveTab] = useState('General');
  const [config, setConfig] = useState<any>({});
  const [symbolsInput, setSymbolsInput] = useState('');
  const [sessions, setSessions] = useState<any[]>([]);
  
  useEffect(() => {
    api.get('/config').then(res => {
      setConfig(res.config);
      setSymbolsInput(res.config.symbols?.join(', ') || '');
    });
    api.get('/sessions').then(res => setSessions(res));
  }, []);

  const handleSave = async () => {
    try {
      const syms = symbolsInput.split(',').map(s => s.trim()).filter(Boolean);
      await api.patch('/config', { ...config, symbols: syms });
      onClose();
    } catch (e) {
      console.error(e);
    }
  };

  const handleAddSession = async () => {
    const newSession = {
      name: 'New Session',
      start_time: '08:00',
      end_time: '12:00',
      tz: 'UTC',
      days_mask: 62, // Mon-Fri
      enabled: true
    };
    const res = await api.post('/sessions', newSession);
    setSessions([...sessions, res]);
  };

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50">
      <div className="bg-[#121826] border border-[#1e2a3f] rounded-lg w-full max-w-4xl h-[80vh] flex flex-col">
        <div className="flex justify-between items-center p-4 border-b border-[#1e2a3f]">
          <h2 className="text-xl font-bold">Configuration</h2>
          <button onClick={onClose} className="text-muted hover:text-white"><X size={20}/></button>
        </div>
        
        <div className="flex flex-1 overflow-hidden">
          {/* Tabs */}
          <div className="w-48 border-r border-[#1e2a3f] p-4 space-y-1">
            {['General', 'Symbols', 'Sessions', 'Risk'].map(tab => (
              <button 
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`w-full text-left px-3 py-2 rounded text-sm font-medium transition-colors ${activeTab === tab ? 'bg-accent/20 text-accent' : 'text-muted hover:text-white hover:bg-[#1e2a3f]'}`}
              >
                {tab}
              </button>
            ))}
          </div>
          
          {/* Content */}
          <div className="flex-1 p-6 overflow-y-auto">
            {activeTab === 'General' && (
              <div className="space-y-4 max-w-md">
                <div>
                  <label className="block text-sm text-muted mb-1">Max Open Positions</label>
                  <input type="number" className="w-full bg-[#0a0e1a] border border-[#1e2a3f] rounded p-2 text-white" 
                    value={config.max_open_positions || 3} onChange={e => setConfig({...config, max_open_positions: parseInt(e.target.value)})} />
                </div>
                <div>
                  <label className="block text-sm text-muted mb-1">Max Per Symbol</label>
                  <input type="number" className="w-full bg-[#0a0e1a] border border-[#1e2a3f] rounded p-2 text-white" 
                    value={config.max_per_symbol || 1} onChange={e => setConfig({...config, max_per_symbol: parseInt(e.target.value)})} />
                </div>
                <div>
                  <label className="block text-sm text-muted mb-1">Signal Threshold (0-100)</label>
                  <input type="number" className="w-full bg-[#0a0e1a] border border-[#1e2a3f] rounded p-2 text-white" 
                    value={config.signal_threshold || 65} onChange={e => setConfig({...config, signal_threshold: parseFloat(e.target.value)})} />
                </div>
              </div>
            )}
            
            {activeTab === 'Symbols' && (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm text-muted mb-1">Symbols (comma separated)</label>
                  <textarea 
                    className="w-full bg-[#0a0e1a] border border-[#1e2a3f] rounded p-2 text-white h-32" 
                    placeholder="XAUUSD, EURUSD"
                    value={symbolsInput} onChange={e => setSymbolsInput(e.target.value)} 
                  />
                </div>
                {/* Advanced: Add chip resolution UI here */}
              </div>
            )}
            
            {activeTab === 'Sessions' && (
              <div className="space-y-4">
                {sessions.map(s => (
                  <div key={s.id} className="flex gap-4 items-center bg-[#0a0e1a] p-3 rounded border border-[#1e2a3f]">
                    <input className="bg-transparent border-b border-accent outline-none w-32" value={s.name} readOnly />
                    <input type="time" className="bg-[#121826] p-1 rounded border border-[#1e2a3f]" value={s.start_time} readOnly />
                    <span>to</span>
                    <input type="time" className="bg-[#121826] p-1 rounded border border-[#1e2a3f]" value={s.end_time} readOnly />
                    <input className="bg-transparent border-b border-accent outline-none w-24" value={s.tz} readOnly />
                    {/* Add checkboxes and delete handlers */}
                  </div>
                ))}
                <button onClick={handleAddSession} className="px-4 py-2 border border-accent text-accent rounded hover:bg-accent/10">
                  + Add Session
                </button>
              </div>
            )}

            {activeTab === 'Risk' && (
              <div className="space-y-4 max-w-md">
                <div>
                  <label className="block text-sm text-muted mb-1">Risk per Trade (%)</label>
                  <input type="number" step="0.1" className="w-full bg-[#0a0e1a] border border-[#1e2a3f] rounded p-2 text-white" 
                    value={config.risk_percent || 1.0} onChange={e => setConfig({...config, risk_percent: parseFloat(e.target.value)})} />
                </div>
                <div>
                  <label className="block text-sm text-muted mb-1">Reward Ratio (R)</label>
                  <input type="number" step="0.1" className="w-full bg-[#0a0e1a] border border-[#1e2a3f] rounded p-2 text-white" 
                    value={config.reward_ratio || 2.0} onChange={e => setConfig({...config, reward_ratio: parseFloat(e.target.value)})} />
                </div>
              </div>
            )}
          </div>
        </div>
        
        <div className="p-4 border-t border-[#1e2a3f] flex justify-end gap-3">
          <button onClick={onClose} className="px-4 py-2 rounded text-muted hover:text-white">Cancel</button>
          <button onClick={handleSave} className="bg-accent text-white px-6 py-2 rounded font-medium hover:bg-accent/90">
            Save Config
          </button>
        </div>
      </div>
    </div>
  );
};

export default ConfigModal;
