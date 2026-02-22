import { useState } from 'react';
import { useUIStore } from '../../store/uiStore';
import { OctagonX } from 'lucide-react';

export default function KillSwitch() {
  const [confirming, setConfirming] = useState(false);
  const addToast = useUIStore((s) => s.addToast);

  const handleKill = () => {
    if (!confirming) {
      setConfirming(true);
      setTimeout(() => setConfirming(false), 3000);
      return;
    }
    // Would call API to stop all trading
    addToast({
      type: 'warning',
      title: 'Kill Switch Activated',
      message: 'All trading operations halted. Close all positions manually.',
      duration: 10000,
    });
    setConfirming(false);
  };

  return (
    <button
      onClick={handleKill}
      className={`w-full flex items-center justify-center gap-2 py-3 rounded-xl font-bold text-sm transition-all duration-300 ${
        confirming
          ? 'bg-[var(--accent-red)] text-white shadow-[0_0_20px_rgba(239,68,68,0.4)] animate-pulse'
          : 'bg-[var(--accent-red-dim)] text-[var(--accent-red)] hover:bg-[var(--accent-red)] hover:text-white hover:shadow-[0_0_15px_rgba(239,68,68,0.3)]'
      }`}
    >
      <OctagonX size={18} />
      {confirming ? 'CONFIRM KILL' : 'EMERGENCY STOP'}
    </button>
  );
}
