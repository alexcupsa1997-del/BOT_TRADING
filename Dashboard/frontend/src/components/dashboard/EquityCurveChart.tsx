import { useEffect, useRef } from 'react';
import { createChart, LineSeries, type IChartApi } from 'lightweight-charts';

interface EquityCurveChartProps {
  data: { time: string; value: number }[];
}

export default function EquityCurveChart({ data }: EquityCurveChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height: 260,
      layout: {
        background: { color: 'transparent' },
        textColor: '#64748b',
        fontSize: 11,
      },
      grid: {
        vertLines: { color: 'rgba(30,41,59,0.5)' },
        horzLines: { color: 'rgba(30,41,59,0.5)' },
      },
      rightPriceScale: {
        borderColor: 'rgba(30,41,59,0.5)',
      },
      timeScale: {
        borderColor: 'rgba(30,41,59,0.5)',
        timeVisible: false,
      },
      crosshair: {
        vertLine: { color: 'rgba(59,130,246,0.3)', width: 1, style: 2 },
        horzLine: { color: 'rgba(59,130,246,0.3)', width: 1, style: 2 },
      },
    });

    const lineSeries = chart.addSeries(LineSeries, {
      color: '#3b82f6',
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: true,
    });

    if (data.length > 0) {
      lineSeries.setData(data as { time: string; value: number }[]);
      chart.timeScale().fitContent();
    }

    chartRef.current = chart;

    const handleResize = () => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth });
      }
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
    };
  }, [data]);

  return <div ref={containerRef} className="w-full" />;
}
