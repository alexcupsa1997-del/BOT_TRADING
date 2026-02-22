import { useEffect, useState, useRef, useCallback } from 'react';
import { api } from '../api/client';
import type { ApiResponse, OHLCVBar, DataFile } from '../api/types';
import {
  createChart, type IChartApi, CandlestickSeries,
  HistogramSeries, LineSeries,
} from 'lightweight-charts';
import { LineChart, Line, XAxis, YAxis, ResponsiveContainer, Tooltip, ReferenceLine } from 'recharts';
import { BarChart3, TrendingUp, Layers } from 'lucide-react';

function computeEMA(closes: number[], period: number): (number | null)[] {
  const ema: (number | null)[] = [];
  const k = 2 / (period + 1);
  let prev: number | null = null;
  for (let i = 0; i < closes.length; i++) {
    if (i < period - 1) { ema.push(null); continue; }
    if (prev === null) {
      prev = closes.slice(0, period).reduce((a, b) => a + b, 0) / period;
    } else {
      prev = closes[i] * k + prev * (1 - k);
    }
    ema.push(prev);
  }
  return ema;
}

function computeRSI(closes: number[], period = 14): number[] {
  const rsi: number[] = [];
  let gainSum = 0, lossSum = 0;
  for (let i = 0; i < closes.length; i++) {
    if (i === 0) { rsi.push(50); continue; }
    const diff = closes[i] - closes[i - 1];
    if (i <= period) {
      gainSum += Math.max(diff, 0);
      lossSum += Math.abs(Math.min(diff, 0));
      if (i === period) {
        const avgGain = gainSum / period;
        const avgLoss = lossSum / period;
        rsi.push(avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss));
      } else {
        rsi.push(50);
      }
    } else {
      const gain = Math.max(diff, 0);
      const loss = Math.abs(Math.min(diff, 0));
      gainSum = (gainSum * (period - 1) + gain) / period;
      lossSum = (lossSum * (period - 1) + loss) / period;
      rsi.push(lossSum === 0 ? 100 : 100 - 100 / (1 + gainSum / lossSum));
    }
  }
  return rsi;
}

export default function MarketDataPage() {
  const [dataFiles, setDataFiles] = useState<DataFile[]>([]);
  const [symbol, setSymbol] = useState('BTCUSDT');
  const [timeframe, setTimeframe] = useState('1h');
  const [bars, setBars] = useState<OHLCVBar[]>([]);
  const [loading, setLoading] = useState(false);
  const [showEMA, setShowEMA] = useState(true);
  const [showBB, setShowBB] = useState(false);
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<IChartApi | null>(null);

  useEffect(() => {
    api.get<ApiResponse<DataFile[]>>('/market/files')
      .then((res) => setDataFiles(res.data))
      .catch(() => {});
  }, []);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get<ApiResponse<OHLCVBar[]>>(`/market/data/${symbol}?timeframe=${timeframe}&limit=500`);
      setBars(res.data);
    } catch {
      setBars([]);
    } finally {
      setLoading(false);
    }
  }, [symbol, timeframe]);

  useEffect(() => { loadData(); }, [loadData]);

  // Chart rendering
  useEffect(() => {
    if (!chartRef.current || bars.length === 0) return;
    if (chartInstance.current) chartInstance.current.remove();

    const chart = createChart(chartRef.current, {
      width: chartRef.current.clientWidth,
      height: 420,
      layout: {
        background: { color: 'transparent' },
        textColor: '#64748b',
        fontSize: 11,
      },
      grid: {
        vertLines: { color: 'rgba(30,41,59,0.4)' },
        horzLines: { color: 'rgba(30,41,59,0.4)' },
      },
      crosshair: { mode: 0 },
      rightPriceScale: { borderColor: 'rgba(30,41,59,0.5)' },
      timeScale: { borderColor: 'rgba(30,41,59,0.5)', timeVisible: true },
    });

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#10b981', downColor: '#ef4444',
      borderUpColor: '#10b981', borderDownColor: '#ef4444',
      wickUpColor: '#10b981', wickDownColor: '#ef4444',
    });

    const volumeSeries = chart.addSeries(HistogramSeries, {
      priceFormat: { type: 'volume' },
      priceScaleId: 'volume',
    });
    chart.priceScale('volume').applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });

    const toTs = (ts: string) => isNaN(Number(ts))
      ? Math.floor(new Date(ts).getTime() / 1000)
      : Math.floor(Number(ts));

    const closes = bars.map((b) => parseFloat(b.close));
    const timestamps = bars.map((b) => toTs(b.timestamp));

    const candleData = bars.map((bar, i) => ({
      time: timestamps[i] as any,
      open: parseFloat(bar.open), high: parseFloat(bar.high),
      low: parseFloat(bar.low), close: parseFloat(bar.close),
    }));
    const volumeData = bars.map((bar, i) => ({
      time: timestamps[i] as any,
      value: parseFloat(bar.volume),
      color: parseFloat(bar.close) >= parseFloat(bar.open) ? 'rgba(16,185,129,0.25)' : 'rgba(239,68,68,0.25)',
    }));

    candleSeries.setData(candleData);
    volumeSeries.setData(volumeData);

    // EMA overlays
    if (showEMA) {
      const ema9 = computeEMA(closes, 9);
      const ema21 = computeEMA(closes, 21);
      const ema50 = computeEMA(closes, 50);

      const addEmaLine = (values: (number | null)[], color: string) => {
        const series = chart.addSeries(LineSeries, {
          color, lineWidth: 1, priceLineVisible: false, lastValueVisible: false,
        });
        series.setData(values.map((v, i) => v !== null ? { time: timestamps[i] as any, value: v } : null).filter(Boolean) as any);
      };
      addEmaLine(ema9, '#3b82f6');
      addEmaLine(ema21, '#f59e0b');
      addEmaLine(ema50, '#8b5cf6');
    }

    // Bollinger Bands
    if (showBB) {
      const period = 20;
      const upper: (number | null)[] = [];
      const lower: (number | null)[] = [];
      for (let i = 0; i < closes.length; i++) {
        if (i < period - 1) { upper.push(null); lower.push(null); continue; }
        const slice = closes.slice(i - period + 1, i + 1);
        const mean = slice.reduce((a, b) => a + b, 0) / period;
        const std = Math.sqrt(slice.reduce((a, b) => a + (b - mean) ** 2, 0) / period);
        upper.push(mean + 2 * std);
        lower.push(mean - 2 * std);
      }
      const addBBLine = (values: (number | null)[], color: string) => {
        const series = chart.addSeries(LineSeries, {
          color, lineWidth: 1, lineStyle: 2, priceLineVisible: false, lastValueVisible: false,
        });
        series.setData(values.map((v, i) => v !== null ? { time: timestamps[i] as any, value: v } : null).filter(Boolean) as any);
      };
      addBBLine(upper, 'rgba(139,92,246,0.5)');
      addBBLine(lower, 'rgba(139,92,246,0.5)');
    }

    chart.timeScale().fitContent();
    chartInstance.current = chart;

    const observer = new ResizeObserver(() => {
      if (chartRef.current) chart.applyOptions({ width: chartRef.current.clientWidth });
    });
    observer.observe(chartRef.current);
    return () => { observer.disconnect(); chart.remove(); };
  }, [bars, showEMA, showBB]);

  // RSI data
  const closes = bars.map((b) => parseFloat(b.close));
  const rsiValues = computeRSI(closes);
  const rsiData = rsiValues.slice(-60).map((v, i) => ({ idx: i, rsi: parseFloat(v.toFixed(1)) }));

  return (
    <div className="space-y-6 stagger-children">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Market Data</h1>
        <p className="text-sm text-[var(--text-secondary)] mt-0.5">Candlestick charts with technical indicators</p>
      </div>

      {/* Controls */}
      <div className="glass-card p-4">
        <div className="flex items-center gap-4 flex-wrap">
          <div className="flex items-center gap-2">
            <BarChart3 size={16} className="text-[var(--accent-blue)]" />
            <select className="input-field text-sm py-1.5 w-36"
              value={symbol} onChange={(e) => setSymbol(e.target.value)}>
              <option value="BTCUSDT">BTC/USDT</option>
              <option value="ETHUSDT">ETH/USDT</option>
              <option value="XAUUSD">XAU/USD</option>
              {dataFiles.filter((f) => !['BTCUSDT', 'ETHUSDT', 'XAUUSD'].some((s) => f.name.toLowerCase().includes(s.toLowerCase()))).map((f) => (
                <option key={f.name} value={f.name.split('_')[1] || f.name}>{f.name}</option>
              ))}
            </select>
          </div>

          <div className="flex gap-0.5 bg-[var(--bg-elevated)] rounded-lg p-0.5">
            {['1m', '5m', '15m', '1h', '4h', '1d'].map((tf) => (
              <button key={tf} onClick={() => setTimeframe(tf)}
                className={`px-3 py-1.5 text-xs rounded-md transition-all font-medium ${
                  timeframe === tf ? 'bg-[var(--accent-blue)] text-white shadow-sm' : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
                }`}>
                {tf.toUpperCase()}
              </button>
            ))}
          </div>

          <div className="h-5 w-px bg-[var(--border-color)]" />

          {/* Indicator toggles */}
          <div className="flex items-center gap-2">
            <TrendingUp size={13} className="text-[var(--text-muted)]" />
            <button onClick={() => setShowEMA(!showEMA)}
              className={`px-2.5 py-1 text-xs rounded-md transition-all ${showEMA ? 'bg-[var(--accent-blue-dim)] text-[var(--accent-blue)]' : 'text-[var(--text-muted)]'}`}>
              EMA 9/21/50
            </button>
            <button onClick={() => setShowBB(!showBB)}
              className={`px-2.5 py-1 text-xs rounded-md transition-all ${showBB ? 'bg-[var(--accent-blue-dim)] text-[var(--accent-blue)]' : 'text-[var(--text-muted)]'}`}>
              Bollinger
            </button>
          </div>

          <span className="ml-auto text-xs text-[var(--text-muted)] font-mono tabular-nums">
            {loading ? 'Loading...' : `${bars.length} bars`}
          </span>
        </div>
      </div>

      {/* Chart */}
      <div className="glass-card overflow-hidden p-1">
        {bars.length === 0 && !loading ? (
          <div className="h-[420px] flex items-center justify-center text-sm text-[var(--text-muted)]">
            No data available for {symbol} {timeframe}
          </div>
        ) : (
          <div ref={chartRef} className="w-full" />
        )}
      </div>

      {/* RSI Panel */}
      {rsiData.length > 0 && (
        <div className="glass-card p-5">
          <h3 className="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-3">RSI (14)</h3>
          <ResponsiveContainer width="100%" height={120}>
            <LineChart data={rsiData}>
              <XAxis dataKey="idx" hide />
              <YAxis domain={[0, 100]} ticks={[30, 50, 70]} tick={{ fontSize: 10, fill: 'var(--text-muted)' }} axisLine={false} tickLine={false} width={25} />
              <Tooltip
                contentStyle={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '8px', fontSize: '12px' }}
                formatter={(v: number) => [v.toFixed(1), 'RSI']}
              />
              <ReferenceLine y={70} stroke="rgba(239,68,68,0.3)" strokeDasharray="3 3" />
              <ReferenceLine y={30} stroke="rgba(16,185,129,0.3)" strokeDasharray="3 3" />
              <Line type="monotone" dataKey="rsi" stroke="#8b5cf6" strokeWidth={1.5} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Available Files */}
      <div className="glass-card p-5">
        <div className="flex items-center gap-2 mb-3">
          <Layers size={14} className="text-[var(--text-muted)]" />
          <h3 className="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider">Available Data Files</h3>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
          {dataFiles.map((f) => (
            <div key={f.name} className="text-xs bg-[var(--bg-elevated)] rounded-lg px-3 py-2.5 border border-[var(--border-color)]/50 hover:border-[var(--accent-blue)]/30 transition-colors cursor-pointer">
              <div className="font-medium truncate">{f.name}</div>
              <div className="text-[var(--text-muted)] mt-0.5">{f.size_mb} MB</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
