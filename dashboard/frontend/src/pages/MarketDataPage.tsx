import { useEffect, useState, useRef } from 'react';
import { api } from '../api/client';
import type { ApiResponse, OHLCVBar, DataFile } from '../api/types';
import { createChart, type IChartApi, ColorType, CandlestickSeries, HistogramSeries } from 'lightweight-charts';
import { BarChart3 } from 'lucide-react';

export default function MarketDataPage() {
  const [dataFiles, setDataFiles] = useState<DataFile[]>([]);
  const [symbol, setSymbol] = useState('BTCUSDT');
  const [timeframe, setTimeframe] = useState('1h');
  const [bars, setBars] = useState<OHLCVBar[]>([]);
  const [loading, setLoading] = useState(false);
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<IChartApi | null>(null);

  useEffect(() => {
    api.get<ApiResponse<DataFile[]>>('/market/files')
      .then((res) => setDataFiles(res.data))
      .catch(() => {});
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const res = await api.get<ApiResponse<OHLCVBar[]>>(`/market/data/${symbol}?timeframe=${timeframe}&limit=500`);
      setBars(res.data);
    } catch {
      setBars([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (symbol) loadData();
  }, [symbol, timeframe]);

  // Chart rendering
  useEffect(() => {
    if (!chartRef.current || bars.length === 0) return;

    // Cleanup previous
    if (chartInstance.current) {
      chartInstance.current.remove();
    }

    const chart = createChart(chartRef.current, {
      width: chartRef.current.clientWidth,
      height: 450,
      layout: {
        background: { type: ColorType.Solid, color: '#1e293b' },
        textColor: '#94a3b8',
      },
      grid: {
        vertLines: { color: '#334155' },
        horzLines: { color: '#334155' },
      },
      crosshair: { mode: 0 },
      rightPriceScale: { borderColor: '#334155' },
      timeScale: { borderColor: '#334155', timeVisible: true },
    });

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#22c55e',
      downColor: '#ef4444',
      borderUpColor: '#22c55e',
      borderDownColor: '#ef4444',
      wickUpColor: '#22c55e',
      wickDownColor: '#ef4444',
    });

    const volumeSeries = chart.addSeries(HistogramSeries, {
      priceFormat: { type: 'volume' },
      priceScaleId: 'volume',
    });
    chart.priceScale('volume').applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    });

    // Map data
    const candleData = bars.map((bar) => {
      const ts = isNaN(Number(bar.timestamp))
        ? Math.floor(new Date(bar.timestamp).getTime() / 1000)
        : Math.floor(Number(bar.timestamp));
      return {
        time: ts as any,
        open: parseFloat(bar.open),
        high: parseFloat(bar.high),
        low: parseFloat(bar.low),
        close: parseFloat(bar.close),
      };
    });

    const volumeData = bars.map((bar) => {
      const ts = isNaN(Number(bar.timestamp))
        ? Math.floor(new Date(bar.timestamp).getTime() / 1000)
        : Math.floor(Number(bar.timestamp));
      const close = parseFloat(bar.close);
      const open = parseFloat(bar.open);
      return {
        time: ts as any,
        value: parseFloat(bar.volume),
        color: close >= open ? 'rgba(34, 197, 94, 0.3)' : 'rgba(239, 68, 68, 0.3)',
      };
    });

    candleSeries.setData(candleData);
    volumeSeries.setData(volumeData);
    chart.timeScale().fitContent();

    chartInstance.current = chart;

    // Resize observer
    const observer = new ResizeObserver(() => {
      if (chartRef.current) {
        chart.applyOptions({ width: chartRef.current.clientWidth });
      }
    });
    observer.observe(chartRef.current);

    return () => {
      observer.disconnect();
      chart.remove();
    };
  }, [bars]);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Market Data</h1>

      {/* Controls */}
      <div className="flex items-center gap-4 flex-wrap">
        <div className="flex items-center gap-2">
          <BarChart3 size={18} className="text-[var(--accent-blue)]" />
          <select className="bg-[var(--bg-primary)] border border-[var(--border-color)] rounded-lg px-3 py-2 text-sm"
            value={symbol} onChange={(e) => setSymbol(e.target.value)}>
            <option value="BTCUSDT">BTC/USDT</option>
            <option value="ETHUSDT">ETH/USDT</option>
            <option value="XAUUSD">XAU/USD</option>
            {dataFiles.filter((f) => !['BTCUSDT', 'ETHUSDT', 'XAUUSD'].some((s) => f.name.toLowerCase().includes(s.toLowerCase()))).map((f) => (
              <option key={f.name} value={f.name.split('_')[1] || f.name}>{f.name}</option>
            ))}
          </select>
        </div>

        <div className="flex gap-1 bg-[var(--bg-secondary)] rounded-lg p-1 border border-[var(--border-color)]">
          {['1m', '5m', '15m', '1h', '4h', '1d'].map((tf) => (
            <button key={tf} onClick={() => setTimeframe(tf)}
              className={`px-3 py-1 text-xs rounded-md transition-colors ${timeframe === tf ? 'bg-[var(--accent-blue)]/15 text-[var(--accent-blue)]' : 'text-[var(--text-secondary)]'}`}>
              {tf.toUpperCase()}
            </button>
          ))}
        </div>

        <span className="text-sm text-[var(--text-secondary)]">
          {loading ? 'Loading...' : `${bars.length} bars`}
        </span>
      </div>

      {/* Chart */}
      <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border-color)] overflow-hidden">
        {bars.length === 0 && !loading ? (
          <div className="h-[450px] flex items-center justify-center text-[var(--text-secondary)]">
            No data available for {symbol} {timeframe}
          </div>
        ) : (
          <div ref={chartRef} className="w-full" />
        )}
      </div>

      {/* Available Files */}
      <div className="bg-[var(--bg-card)] rounded-xl p-5 border border-[var(--border-color)]">
        <h3 className="text-sm font-semibold text-[var(--text-secondary)] mb-3">Available Data Files</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
          {dataFiles.map((f) => (
            <div key={f.name} className="text-xs bg-[var(--bg-primary)] rounded-lg px-3 py-2 border border-[var(--border-color)]">
              <div className="font-medium truncate">{f.name}</div>
              <div className="text-[var(--text-secondary)]">{f.size_mb} MB</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
