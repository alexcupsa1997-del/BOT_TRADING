import { useMemo } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Tooltip, Cell,
} from 'recharts';

interface PnLDistributionProps {
  trades?: number[];
}

// Recharts does NOT resolve CSS custom properties - must use hex values
const COLORS = {
  green: '#10b981',
  red: '#ef4444',
  textMuted: '#64748b',
  bgSecondary: '#1a1f2e',
  border: '#2a3040',
};

function generateSampleTrades(): number[] {
  const trades: number[] = [];
  for (let i = 0; i < 100; i++) {
    trades.push(parseFloat((Math.random() * 400 - 150).toFixed(2)));
  }
  return trades;
}

function buildHistogram(trades: number[], bins = 12): { range: string; count: number; isPositive: boolean }[] {
  if (trades.length === 0) return [];
  const min = Math.min(...trades);
  const max = Math.max(...trades);
  const binWidth = (max - min) / bins;

  const histogram = Array.from({ length: bins }, (_, i) => {
    const lo = min + i * binWidth;
    const hi = lo + binWidth;
    return {
      range: `${lo.toFixed(0)}`,
      count: trades.filter((t) => t >= lo && (i === bins - 1 ? t <= hi : t < hi)).length,
      isPositive: lo + binWidth / 2 >= 0,
    };
  });
  return histogram;
}

export default function PnLDistribution({ trades }: PnLDistributionProps) {
  const data = useMemo(() => buildHistogram(trades || generateSampleTrades()), [trades]);

  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={data} barCategoryGap="10%">
        <XAxis
          dataKey="range"
          tick={{ fontSize: 9, fill: COLORS.textMuted }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          tick={{ fontSize: 10, fill: COLORS.textMuted }}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip
          contentStyle={{
            background: COLORS.bgSecondary,
            border: `1px solid ${COLORS.border}`,
            borderRadius: '8px',
            fontSize: '12px',
            color: '#e2e8f0',
          }}
          labelFormatter={(v) => `PnL: $${v}`}
        />
        <Bar dataKey="count" radius={[3, 3, 0, 0]}>
          {data.map((entry, i) => (
            <Cell
              key={i}
              fill={entry.isPositive ? COLORS.green : COLORS.red}
              fillOpacity={0.7}
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
