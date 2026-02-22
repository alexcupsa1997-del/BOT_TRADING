import {
  BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Tooltip, Cell,
} from 'recharts';

interface PnLDistributionProps {
  trades?: number[];
}

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
  const data = buildHistogram(trades || generateSampleTrades());

  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={data} barCategoryGap="10%">
        <XAxis
          dataKey="range"
          tick={{ fontSize: 9, fill: 'var(--text-muted)' }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          tick={{ fontSize: 10, fill: 'var(--text-muted)' }}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip
          contentStyle={{
            background: 'var(--bg-secondary)',
            border: '1px solid var(--border-color)',
            borderRadius: '8px',
            fontSize: '12px',
          }}
          labelFormatter={(v) => `PnL: $${v}`}
        />
        <Bar dataKey="count" radius={[3, 3, 0, 0]}>
          {data.map((entry, i) => (
            <Cell
              key={i}
              fill={entry.isPositive ? 'var(--accent-green)' : 'var(--accent-red)'}
              fillOpacity={0.7}
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
