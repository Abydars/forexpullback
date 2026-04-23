import React, { useState } from 'react';
import { api } from '../api';
import { X } from 'lucide-react';

const MT5ConnectionModal = ({ onClose }: { onClose: () => void }) => {
  const [server, setServer] = useState('');
  const [login, setLogin] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

  const handleConnect = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    
    try {
      await api.post('/mt5/connect', { server, login: parseInt(login), password });
      setSuccess(true);
      setTimeout(onClose, 1500);
    } catch (err: any) {
      setError(err.message || 'Connection failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50">
      <div className="bg-[#121826] border border-[#1e2a3f] rounded-lg w-full max-w-md">
        <div className="flex justify-between items-center p-4 border-b border-[#1e2a3f]">
          <h2 className="text-xl font-bold">Connect MT5</h2>
          <button onClick={onClose} className="text-muted hover:text-white"><X size={20}/></button>
        </div>
        
        <form onSubmit={handleConnect} className="p-6 space-y-4">
          {error && <div className="bg-danger/20 text-danger p-3 rounded text-sm">{error}</div>}
          {success && <div className="bg-success/20 text-success p-3 rounded text-sm">Connected successfully!</div>}
          
          <div>
            <label className="block text-sm text-muted mb-1">Server</label>
            <input 
              type="text" required
              className="w-full bg-[#0a0e1a] border border-[#1e2a3f] rounded p-2 text-white focus:border-accent outline-none"
              placeholder="Exness-MT5Real"
              value={server} onChange={e => setServer(e.target.value)}
            />
          </div>
          <div>
            <label className="block text-sm text-muted mb-1">Login</label>
            <input 
              type="number" required
              className="w-full bg-[#0a0e1a] border border-[#1e2a3f] rounded p-2 text-white focus:border-accent outline-none"
              value={login} onChange={e => setLogin(e.target.value)}
            />
          </div>
          <div>
            <label className="block text-sm text-muted mb-1">Password</label>
            <input 
              type="password" required
              className="w-full bg-[#0a0e1a] border border-[#1e2a3f] rounded p-2 text-white focus:border-accent outline-none"
              value={password} onChange={e => setPassword(e.target.value)}
            />
          </div>
          
          <div className="pt-4 flex justify-end gap-3">
            <button type="button" onClick={onClose} className="px-4 py-2 rounded text-muted hover:text-white">Cancel</button>
            <button 
              type="submit" disabled={loading}
              className="bg-accent text-white px-4 py-2 rounded font-medium hover:bg-accent/90 disabled:opacity-50"
            >
              {loading ? 'Connecting...' : 'Test & Connect'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default MT5ConnectionModal;
