const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'];
const HOURS = ['00', '04', '08', '12', '16', '20'];

interface PerformanceHeatmapProps {
  data?: number[][];
}

function getColor(value: number): string {
  if (value > 2) return 'rgba(16,185,129,0.8)';
  if (value > 1) return 'rgba(16,185,129,0.5)';
  if (value > 0) return 'rgba(16,185,129,0.25)';
  if (value === 0) return 'rgba(30,41,59,0.3)';
  if (value > -1) return 'rgba(239,68,68,0.25)';
  if (value > -2) return 'rgba(239,68,68,0.5)';
  return 'rgba(239,68,68,0.8)';
}

// Generate sample data if none provided
function generateSampleData(): number[][] {
  return DAYS.map(() =>
    HOURS.map(() => parseFloat((Math.random() * 6 - 2).toFixed(2)))
  );
}

export default function PerformanceHeatmap({ data }: PerformanceHeatmapProps) {
  const matrix = data || generateSampleData();

  return (
    <div className="space-y-1">
      {/* Hour labels */}
      <div className="flex ml-10 gap-1">
        {HOURS.map((h) => (
          <div key={h} className="flex-1 text-center text-[10px] text-[var(--text-muted)]">
            {h}:00
          </div>
        ))}
      </div>

      {/* Grid */}
      {matrix.map((row, dayIdx) => (
        <div key={DAYS[dayIdx]} className="flex items-center gap-1">
          <span className="w-8 text-right text-[10px] text-[var(--text-muted)] mr-1">
            {DAYS[dayIdx]}
          </span>
          {row.map((val, hourIdx) => (
            <div
              key={hourIdx}
              className="flex-1 h-7 rounded-sm transition-all hover:scale-110 cursor-default"
              style={{ backgroundColor: getColor(val) }}
              title={`${DAYS[dayIdx]} ${HOURS[hourIdx]}:00 → ${val > 0 ? '+' : ''}${val.toFixed(2)}%`}
            />
          ))}
        </div>
      ))}

      {/* Legend */}
      <div className="flex items-center justify-center gap-2 mt-2">
        <span className="text-[10px] text-[var(--text-muted)]">Loss</span>
        {[-2, -1, 0, 1, 2, 3].map((v) => (
          <div
            key={v}
            className="w-3 h-3 rounded-sm"
            style={{ backgroundColor: getColor(v) }}
          />
        ))}
        <span className="text-[10px] text-[var(--text-muted)]">Profit</span>
      </div>
    </div>
  );
}
