import { useEffect, useState } from 'react';

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
  color = '#3b82f6',
  warningThreshold = 80,
}: GaugeChartProps) {
  const [animatedValue, setAnimatedValue] = useState(0);
  const pct = Math.min((value / max) * 100, 100);
  const fillColor = pct > warningThreshold ? '#ef4444' : color;

  useEffect(() => {
    const start = animatedValue;
    const end = pct;
    const duration = 800;
    const startTime = performance.now();

    function animate(now: number) {
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setAnimatedValue(start + (end - start) * eased);
      if (progress < 1) requestAnimationFrame(animate);
    }
    requestAnimationFrame(animate);
  }, [pct]);

  // SVG arc parameters
  const cx = 64, cy = 56, r = 42;
  const startAngle = Math.PI;
  const endAngle = 0;
  const totalArc = Math.PI;
  const arcLength = (animatedValue / 100) * totalArc;

  const bgX1 = cx + r * Math.cos(startAngle);
  const bgY1 = cy - r * Math.sin(startAngle);
  const bgX2 = cx + r * Math.cos(endAngle);
  const bgY2 = cy - r * Math.sin(endAngle);

  const fillEndAngle = startAngle - arcLength;
  const fX = cx + r * Math.cos(fillEndAngle);
  const fY = cy - r * Math.sin(fillEndAngle);
  const largeArc = arcLength > Math.PI ? 1 : 0;

  const bgPath = `M ${bgX1} ${bgY1} A ${r} ${r} 0 1 1 ${bgX2} ${bgY2}`;
  const fillPath = arcLength > 0
    ? `M ${bgX1} ${bgY1} A ${r} ${r} 0 ${largeArc} 1 ${fX} ${fY}`
    : '';

  const gradientId = `gauge-grad-${label.replace(/[^a-zA-Z0-9]/g, '')}`;

  return (
    <div className="flex flex-col items-center">
      <svg width="128" height="72" viewBox="0 0 128 72">
        <defs>
          <linearGradient id={gradientId} x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor={fillColor} stopOpacity={0.4} />
            <stop offset="100%" stopColor={fillColor} stopOpacity={1} />
          </linearGradient>
        </defs>
        {/* Background arc */}
        <path d={bgPath} fill="none" stroke="var(--border-color)" strokeWidth={8} strokeLinecap="round" />
        {/* Fill arc */}
        {fillPath && (
          <path
            d={fillPath}
            fill="none"
            stroke={`url(#${gradientId})`}
            strokeWidth={8}
            strokeLinecap="round"
            style={{ filter: `drop-shadow(0 0 6px ${fillColor}40)` }}
          />
        )}
        {/* Center value */}
        <text x={cx} y={cy + 2} textAnchor="middle" fill={fillColor} fontSize="18" fontWeight="bold" fontFamily="monospace">
          {animatedValue.toFixed(1)}%
        </text>
      </svg>
      <span className="text-xs text-[var(--text-secondary)] -mt-1">{label}</span>
    </div>
  );
}
