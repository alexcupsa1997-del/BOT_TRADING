import { PieChart, Pie, Cell, ResponsiveContainer } from 'recharts';

interface WinRateDonutProps {
  winRate: number;
  label?: string;
}

export default function WinRateDonut({ winRate, label = 'Win Rate' }: WinRateDonutProps) {
  const data = [
    { name: 'Win', value: winRate },
    { name: 'Loss', value: 100 - winRate },
  ];

  return (
    <div className="flex flex-col items-center">
      <div className="relative w-28 h-28">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              cx="50%"
              cy="50%"
              innerRadius={32}
              outerRadius={48}
              startAngle={90}
              endAngle={-270}
              dataKey="value"
              stroke="none"
            >
              <Cell fill="var(--accent-green)" />
              <Cell fill="rgba(30,41,59,0.5)" />
            </Pie>
          </PieChart>
        </ResponsiveContainer>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-lg font-bold text-[var(--text-primary)]">
            {winRate.toFixed(0)}%
          </span>
        </div>
      </div>
      <span className="text-xs text-[var(--text-secondary)] mt-1">{label}</span>
    </div>
  );
}
