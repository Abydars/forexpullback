import React, { useEffect, useState } from 'react';
import { useStore } from './store/useStore';
import Dashboard from './components/Dashboard';
import ConfigModal from './components/ConfigModal';
import MT5ConnectionModal from './components/MT5ConnectionModal';
import { Activity, Settings, Link as LinkIcon, Link2Off } from 'lucide-react';

function App() {
  const { fetchStatus, mt5Connected, engineRunning, connectWs } = useStore();
  const [showConfig, setShowConfig] = useState(false);
  const [showMT5, setShowMT5] = useState(false);

  useEffect(() => {
    fetchStatus();
    connectWs();
    const interval = setInterval(fetchStatus, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="min-h-screen bg-[#0a0e1a] text-[#e2e8f0]">
      {/* Header */}
      <header className="border-b border-[#1e2a3f] bg-[#121826] p-4 flex justify-between items-center">
        <div className="flex items-center gap-3">
          <Activity className="text-accent" />
          <h1 className="text-xl font-bold tracking-wider">PULLBACK SYSTEM</h1>
        </div>
        
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium">Engine:</span>
            <div className={`w-3 h-3 rounded-full ${engineRunning ? 'bg-success' : 'bg-muted'}`} />
          </div>
          
          <button 
            onClick={() => setShowMT5(true)}
            className={`flex items-center gap-2 px-3 py-1.5 rounded text-sm font-medium transition-colors ${mt5Connected ? 'bg-[#1e2a3f] text-success hover:bg-[#2d3a54]' : 'bg-danger/20 text-danger hover:bg-danger/30'}`}
          >
            {mt5Connected ? <LinkIcon size={16} /> : <Link2Off size={16} />}
            {mt5Connected ? 'MT5 Connected' : 'MT5 Disconnected'}
          </button>

          <button 
            onClick={() => setShowConfig(true)}
            className="p-2 hover:bg-[#1e2a3f] rounded transition-colors"
          >
            <Settings size={20} />
          </button>
        </div>
      </header>

      {/* Main Content */}
      <main className="p-6">
        <Dashboard />
      </main>

      {/* Modals */}
      {showConfig && <ConfigModal onClose={() => setShowConfig(false)} />}
      {showMT5 && <MT5ConnectionModal onClose={() => setShowMT5(false)} />}
    </div>
  );
}

export default App;
