import { RadialBarChart, RadialBar, ResponsiveContainer } from 'recharts';

interface GaugeChartProps {
  value: number;
  max?: number;
  label: string;
  color?: string;
  warningThreshold?: number;
}

export default function GaugeChart({
  value,
  max = 100,
  label,
  color = 'var(--accent-blue)',
  warningThreshold = 80,
}: GaugeChartProps) {
  const pct = Math.min((value / max) * 100, 100);
  const fillColor = pct > warningThreshold ? 'var(--accent-red)' : color;

  const data = [{ value: pct, fill: fillColor }];

  return (
    <div className="flex flex-col items-center">
      <div className="w-32 h-20 relative">
        <ResponsiveContainer width="100%" height="100%">
          <RadialBarChart
            cx="50%"
            cy="100%"
            innerRadius="70%"
            outerRadius="100%"
            startAngle={180}
            endAngle={0}
            data={data}
            barSize={10}
          >
            <RadialBar dataKey="value" background={{ fill: 'var(--border-color)' }} cornerRadius={5} />
          </RadialBarChart>
        </ResponsiveContainer>
        <div className="absolute bottom-0 left-0 right-0 text-center">
          <span className="text-xl font-bold" style={{ color: fillColor }}>
            {value.toFixed(1)}%
          </span>
        </div>
      </div>
      <span className="text-xs text-[var(--text-secondary)] mt-1">{label}</span>
    </div>
  );
}
