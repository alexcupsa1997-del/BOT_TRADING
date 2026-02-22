import { AreaChart, Area, XAxis, YAxis, ResponsiveContainer, Tooltip } from 'recharts';

interface DrawdownChartProps {
  data?: { time: string; drawdown: number }[];
}

function generateSampleDrawdown(): { time: string; drawdown: number }[] {
  const points: { time: string; drawdown: number }[] = [];
  let dd = 0;
  for (let i = 0; i < 30; i++) {
    dd = Math.min(0, dd + (Math.random() * 2 - 1.2));
    if (Math.random() > 0.7) dd = Math.min(dd + 1, 0);
    points.push({
      time: `Day ${i + 1}`,
      drawdown: parseFloat(dd.toFixed(2)),
    });
  }
  return points;
}

export default function DrawdownChart({ data }: DrawdownChartProps) {
  const chartData = data || generateSampleDrawdown();

  return (
    <div className="glass-card p-5">
      <h3 className="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-3">Drawdown</h3>
      <ResponsiveContainer width="100%" height={160}>
        <AreaChart data={chartData}>
          <defs>
            <linearGradient id="drawdownGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
            </linearGradient>
          </defs>
          <XAxis
            dataKey="time"
            tick={{ fontSize: 9, fill: 'var(--text-muted)' }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            tick={{ fontSize: 10, fill: 'var(--text-muted)' }}
            axisLine={false}
            tickLine={false}
            width={35}
            domain={['auto', 0]}
          />
          <Tooltip
            contentStyle={{
              background: 'var(--bg-secondary)',
              border: '1px solid var(--border-color)',
              borderRadius: '8px',
              fontSize: '12px',
            }}
            formatter={(v: number) => [`${v.toFixed(2)}%`, 'Drawdown']}
          />
          <Area
            type="monotone"
            dataKey="drawdown"
            stroke="#ef4444"
            strokeWidth={2}
            fill="url(#drawdownGrad)"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
