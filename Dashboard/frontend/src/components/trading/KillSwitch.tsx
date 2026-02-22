import { useState } from 'react';
import { useUIStore } from '../../store/uiStore';
import { api } from '../../api/client';
import { OctagonX, ShieldAlert } from 'lucide-react';

export default function KillSwitch() {
  const [confirming, setConfirming] = useState(false);
  const [killed, setKilled] = useState(false);
  const [loading, setLoading] = useState(false);
  const addToast = useUIStore((s) => s.addToast);

  const handleKill = async () => {
    if (!confirming) {
      setConfirming(true);
      setTimeout(() => setConfirming(false), 5000);
      return;
    }

    setLoading(true);
    try {
      // Attempt to call backend kill endpoint
      await api.post('/api/trading/kill-switch', { action: 'halt_all' });
      addToast({
        type: 'warning',
        title: 'Kill Switch Activated',
        message: 'All trading operations halted. Close positions manually.',
        duration: 10000,
      });
    } catch {
      // Even if API fails, activate local kill state
      addToast({
        type: 'error',
        title: 'Kill Switch - Local Only',
        message: 'Backend unreachable. Trading halted locally. Verify engine status manually.',
        duration: 15000,
      });
    } finally {
      setKilled(true);
      setConfirming(false);
      setLoading(false);
    }
  };

  const handleReset = () => {
    setKilled(false);
    addToast({
      type: 'info',
      title: 'Kill Switch Reset',
      message: 'Trading can resume. Monitor carefully.',
      duration: 5000,
    });
  };

  return (
    <div className="glass-card p-5">
      <div className="flex items-center gap-2 mb-3">
        <ShieldAlert size={16} className="text-[var(--accent-red)]" />
        <h3 className="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider">Emergency Control</h3>
      </div>

      {killed ? (
        <div className="space-y-3">
          <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-[var(--accent-red-dim)] text-[var(--accent-red)]">
            <OctagonX size={14} />
            <span className="text-xs font-bold">TRADING HALTED</span>
          </div>
          <button
            onClick={handleReset}
            className="w-full py-2.5 rounded-xl text-xs font-semibold bg-[var(--bg-elevated)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-card-hover)] transition-all"
          >
            Reset Kill Switch
          </button>
        </div>
      ) : (
        <button
          onClick={handleKill}
          disabled={loading}
          className={`w-full flex items-center justify-center gap-2 py-3 rounded-xl font-bold text-sm transition-all duration-300 ${
            confirming
              ? 'bg-[var(--accent-red)] text-white shadow-[0_0_20px_rgba(239,68,68,0.4)] animate-pulse'
              : 'bg-[var(--accent-red-dim)] text-[var(--accent-red)] hover:bg-[var(--accent-red)] hover:text-white hover:shadow-[0_0_15px_rgba(239,68,68,0.3)]'
          } ${loading ? 'opacity-50 cursor-not-allowed' : ''}`}
        >
          <OctagonX size={18} />
          {loading ? 'STOPPING...' : confirming ? 'CLICK AGAIN TO CONFIRM' : 'EMERGENCY STOP'}
        </button>
      )}

      {confirming && !killed && (
        <p className="text-[10px] text-[var(--accent-red)] mt-2 text-center animate-pulse">
          Click again within 5s to confirm. This will halt all trading.
        </p>
      )}
    </div>
  );
}
