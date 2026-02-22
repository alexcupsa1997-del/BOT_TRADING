import { useEffect, useRef, useState } from 'react';

interface AnimatedNumberProps {
  value: number;
  prefix?: string;
  suffix?: string;
  decimals?: number;
  duration?: number;
  className?: string;
  colorize?: boolean; // green if positive, red if negative
}

export default function AnimatedNumber({
  value,
  prefix = '',
  suffix = '',
  decimals = 2,
  duration = 600,
  className = '',
  colorize = false,
}: AnimatedNumberProps) {
  const [display, setDisplay] = useState(value);
  const prevRef = useRef(value);
  const frameRef = useRef<number>(0);

  useEffect(() => {
    const from = prevRef.current;
    const to = value;
    const diff = to - from;
    if (Math.abs(diff) < 0.001) {
      setDisplay(to);
      prevRef.current = to;
      return;
    }

    const start = performance.now();
    const animate = (now: number) => {
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      // easeOutExpo
      const eased = progress === 1 ? 1 : 1 - Math.pow(2, -10 * progress);
      setDisplay(from + diff * eased);
      if (progress < 1) {
        frameRef.current = requestAnimationFrame(animate);
      } else {
        prevRef.current = to;
      }
    };

    frameRef.current = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(frameRef.current);
  }, [value, duration]);

  const colorClass = colorize
    ? display >= 0
      ? 'text-[var(--accent-green)]'
      : 'text-[var(--accent-red)]'
    : '';

  return (
    <span className={`tabular-nums ${colorClass} ${className}`}>
      {prefix}{display.toFixed(decimals)}{suffix}
    </span>
  );
}
