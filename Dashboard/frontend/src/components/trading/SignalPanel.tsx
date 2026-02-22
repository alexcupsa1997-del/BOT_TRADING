import { useEffect, useState } from 'react';

interface Signal {
  symbol: string;
  direction: 'LONG' | 'SHORT' | 'HOLD';
  confidence: number;
  model: string;
}

interface SignalPanelProps {
  signals?: Signal[];
}

function ConfidenceGauge({ value, direction }: { value: number; direction: string }) {
  const [animated, setAnimated] = useState(0);
  useEffect(() => {
    const start = performance.now();
    const duration = 1000;
    function tick(now: number) {
      const p = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - p, 3);
      setAnimated(value * eased);
      if (p < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  }, [value]);

  const color = direction === 'LONG' ? '#10b981' : direction === 'SHORT' ? '#ef4444' : '#64748b';
  const radius = 24;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (animated / 100) * circumference;

  return (
    <div className="relative w-14 h-14 flex-shrink-0">
      <svg width="56" height="56" viewBox="0 0 56 56">
        <circle cx="28" cy="28" r={radius} fill="none" stroke="var(--border-color)" strokeWidth="4" />
        <circle
          cx="28" cy="28" r={radius} fill="none"
          stroke={color} strokeWidth="4" strokeLinecap="round"
          strokeDasharray={circumference} strokeDashoffset={offset}
          transform="rotate(-90 28 28)"
          style={{ transition: 'stroke-dashoffset 0.3s ease', filter: `drop-shadow(0 0 4px ${color}50)` }}
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        <span className="text-xs font-bold" style={{ color }}>{animated.toFixed(0)}%</span>
      </div>
    </div>
  );
}

const defaultSignals: Signal[] = [
  { symbol: 'XAUUSD', direction: 'LONG', confidence: 78, model: 'JEPA-v2' },
  { symbol: 'BTCUSD', direction: 'SHORT', confidence: 62, model: 'GNN-v1' },
  { symbol: 'EURUSD', direction: 'HOLD', confidence: 45, model: 'MLP-v3' },
];

export default function SignalPanel({ signals }: SignalPanelProps) {
  const data = signals || defaultSignals;

  return (
    <div className="glass-card p-5">
      <h3 className="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-4">ML Signals</h3>
      <div className="space-y-3">
        {data.map((s) => (
          <div key={s.symbol} className="flex items-center gap-3 p-2 rounded-lg bg-[var(--bg-elevated)]/50">
            <ConfidenceGauge value={s.confidence} direction={s.direction} />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="font-medium text-sm">{s.symbol}</span>
                <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                  s.direction === 'LONG' ? 'bg-[var(--accent-green-dim)] text-[var(--accent-green)]'
                  : s.direction === 'SHORT' ? 'bg-[var(--accent-red-dim)] text-[var(--accent-red)]'
                  : 'bg-[var(--bg-elevated)] text-[var(--text-muted)]'
                }`}>
                  {s.direction}
                </span>
              </div>
              <span className="text-[10px] text-[var(--text-muted)]">{s.model}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
