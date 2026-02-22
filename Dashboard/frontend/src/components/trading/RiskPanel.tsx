import AnimatedNumber from '../common/AnimatedNumber';
import { Shield, TrendingDown, Percent, DollarSign } from 'lucide-react';

interface RiskPanelProps {
  exposure: number;
  leverage: number;
  marginUsed: number;
  maxDrawdown: number;
}

export default function RiskPanel({ exposure, leverage, marginUsed, maxDrawdown }: RiskPanelProps) {
  const metrics = [
    { label: 'Exposure', value: exposure, prefix: '$', icon: <DollarSign size={14} />, color: 'var(--accent-blue)' },
    { label: 'Leverage', value: leverage, suffix: 'x', decimals: 1, icon: <TrendingDown size={14} />, color: 'var(--accent-yellow)' },
    { label: 'Margin Used', value: marginUsed, suffix: '%', icon: <Percent size={14} />, color: marginUsed > 80 ? 'var(--accent-red)' : 'var(--accent-green)' },
    { label: 'Max Drawdown', value: maxDrawdown, suffix: '%', icon: <Shield size={14} />, color: maxDrawdown > 10 ? 'var(--accent-red)' : 'var(--accent-yellow)' },
  ];

  return (
    <div className="glass-card p-5">
      <h3 className="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-4">Risk Dashboard</h3>
      <div className="grid grid-cols-2 gap-4">
        {metrics.map((m) => (
          <div key={m.label} className="space-y-1">
            <div className="flex items-center gap-1.5 text-[var(--text-muted)]">
              {m.icon}
              <span className="text-[10px] uppercase tracking-wider">{m.label}</span>
            </div>
            <div className="text-lg font-bold" style={{ color: m.color }}>
              <AnimatedNumber
                value={m.value}
                prefix={m.prefix || ''}
                suffix={m.suffix || ''}
                decimals={m.decimals ?? 2}
              />
            </div>
            {/* Progress bar for margin */}
            {m.label === 'Margin Used' && (
              <div className="w-full h-1.5 rounded-full bg-[var(--bg-elevated)] overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-700"
                  style={{
                    width: `${Math.min(m.value, 100)}%`,
                    background: m.value > 80 ? 'var(--accent-red)' : m.value > 50 ? 'var(--accent-yellow)' : 'var(--accent-green)',
                  }}
                />
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
