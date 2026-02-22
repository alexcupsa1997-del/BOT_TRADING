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
}: KPICardProps) {
  const glowClass =
    glowColor === 'green' ? 'glow-green'
    : glowColor === 'red' ? 'glow-red'
    : glowColor === 'blue' ? 'glow-blue'
    : '';

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
      <div className="text-2xl font-bold tracking-tight">
        <AnimatedNumber
          value={value}
          prefix={prefix}
          suffix={suffix}
          decimals={decimals}
          colorize={colorize}
        />
      </div>
      {delta !== undefined && (
        <div className={`text-xs mt-1 font-medium ${delta >= 0 ? 'text-[var(--accent-green)]' : 'text-[var(--accent-red)]'}`}>
          {delta >= 0 ? '+' : ''}{delta.toFixed(2)}{deltaSuffix}
        </div>
      )}
    </div>
  );
}
