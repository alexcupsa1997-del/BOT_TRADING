import { type ReactNode } from 'react';
import AnimatedNumber from './AnimatedNumber';

interface KPICardProps {
  label: string;
  value: number;
  prefix?: string;
  suffix?: string;
  decimals?: number;
  delta?: number;
  deltaSuffix?: string;
  icon: ReactNode;
  colorize?: boolean;
  glowColor?: 'green' | 'red' | 'blue' | 'none';
  delay?: number;
  sparkline?: number[];
  textValue?: string;
}

function Sparkline({ data, color = 'var(--accent-blue)' }: { data: number[]; color?: string }) {
  if (data.length < 2) return null;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const w = 80;
  const h = 24;
  const points = data.map((v, i) =>
    `${(i / (data.length - 1)) * w},${h - ((v - min) / range) * h}`
  ).join(' ');

  return (
    <svg width={w} height={h} className="mt-1 opacity-60">
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export default function KPICard({
  label,
  value,
  prefix = '',
  suffix = '',
  decimals = 2,
  delta,
  deltaSuffix = '%',
  icon,
  colorize = false,
  glowColor = 'none',
  delay = 0,
  sparkline,
  textValue,
}: KPICardProps) {
  const glowClass =
    glowColor === 'green' ? 'glow-green'
    : glowColor === 'red' ? 'glow-red'
    : glowColor === 'blue' ? 'glow-blue'
    : '';

  const sparkColor =
    glowColor === 'green' ? 'var(--accent-green)'
    : glowColor === 'red' ? 'var(--accent-red)'
    : 'var(--accent-blue)';

  return (
    <div
      className={`glass-card p-4 ${glowClass}`}
      style={{ animationDelay: `${delay}ms` }}
    >
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-medium text-[var(--text-secondary)] uppercase tracking-wider">
          {label}
        </span>
        <div className="w-8 h-8 rounded-lg bg-[var(--bg-elevated)] flex items-center justify-center text-[var(--text-secondary)]">
          {icon}
        </div>
      </div>

      {textValue ? (
        <div className="text-lg font-bold tracking-tight truncate">{textValue}</div>
      ) : (
        <div className="text-2xl font-bold tracking-tight">
          <AnimatedNumber
            value={value}
            prefix={prefix}
            suffix={suffix}
            decimals={decimals}
            colorize={colorize}
          />
        </div>
      )}

      <div className="flex items-end justify-between">
        {delta !== undefined ? (
          <div className={`text-xs mt-1 font-medium ${delta >= 0 ? 'text-[var(--accent-green)]' : 'text-[var(--accent-red)]'}`}>
            {delta >= 0 ? '+' : ''}{delta.toFixed(2)}{deltaSuffix}
          </div>
        ) : (
          <div />
        )}
        {sparkline && <Sparkline data={sparkline} color={sparkColor} />}
      </div>
    </div>
  );
}
