import { useEffect, useRef, useCallback, useState, useMemo } from 'react';
import { api } from '../api/client';
import {
    useDemoTradingStore,
    type DemoSymbol,
    type CandleData,
} from '../store/demoTradingStore';
import {
    createChart,
    type IChartApi,
    type ISeriesApi,
    CandlestickSeries,
    HistogramSeries,
    LineSeries,
} from 'lightweight-charts';
import TradePanel from '../components/demo-trading/TradePanel';
import PositionsPanel from '../components/demo-trading/PositionsPanel';
import TradeHistoryTable from '../components/demo-trading/TradeHistoryTable';
import IndicatorToolbar, {
    DEFAULT_INDICATORS,
    type IndicatorConfig,
    type PriceScaleMode,
} from '../components/demo-trading/IndicatorToolbar';
import {
    calcEMA,
    calcSMA,
    calcBollingerBands,
    calcRSI,
    calcMACD,
    calcVWAP,
    calcStochastic,
    calcCCI,
    calcWilliamsR,
    calcOBV,
    calcKeltnerChannel,
    calcIchimoku,
    calcParabolicSAR,
    calcATR,
    calcADX,
} from '../utils/indicators';
import {
    Wifi, WifiOff, RefreshCw, RotateCcw,
    DollarSign, TrendingUp, Award, BarChart3,
} from 'lucide-react';

const TIMEFRAMES = ['1m', '5m', '15m', '1h', '4h', '1d'];

export default function DemoTradingPage() {
    const {
        symbols, selectedSymbol, selectedTimeframe, currentPrice,
        candles, account, wsConnected,
        setSymbols, setSelectedSymbol, setSelectedTimeframe,
        setCandles, addOrUpdateCandle, setCurrentPrice,
        setPositions, setHistory, setAccount, setWsConnected,
    } = useDemoTradingStore();

    const chartRef = useRef<HTMLDivElement>(null);
    const chartInstance = useRef<IChartApi | null>(null);
    const candleSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
    const volumeSeriesRef = useRef<ISeriesApi<'Histogram'> | null>(null);
    const wsRef = useRef<WebSocket | null>(null);
    const [loading, setLoading] = useState(false);
    const [indicators, setIndicators] = useState<IndicatorConfig[]>(DEFAULT_INDICATORS);

    // Debounced indicators for chart rendering (avoids rebuilding chart on every slider tick)
    const [chartIndicators, setChartIndicators] = useState<IndicatorConfig[]>(DEFAULT_INDICATORS);
    useEffect(() => {
        const timer = setTimeout(() => setChartIndicators(indicators), 200);
        return () => clearTimeout(timer);
    }, [indicators]);

    const toggleIndicator = useCallback((id: string) => {
        setIndicators((prev) =>
            prev.map((ind) => (ind.id === id ? { ...ind, active: !ind.active } : ind))
        );
    }, []);

    const updateIndicator = useCallback((id: string, changes: Partial<IndicatorConfig>) => {
        setIndicators((prev) =>
            prev.map((ind) => (ind.id === id ? { ...ind, ...changes } : ind))
        );
    }, []);

    // ─── Load symbols on mount ───────────────────────────────────────────
    useEffect(() => {
        api.get<{ data: DemoSymbol[] }>('/demo-trading/symbols').then((res) => {
            setSymbols(res.data || []);
        }).catch(console.error);
        api.get<{ data: any }>('/demo-trading/account').then((r) => setAccount(r.data)).catch(() => { });
        api.get<{ data: any[] }>('/demo-trading/positions').then((r) => setPositions(r.data)).catch(() => { });
        api.get<{ data: any[] }>('/demo-trading/history').then((r) => setHistory(r.data)).catch(() => { });
    }, []);

    // ─── Load historical candles ─────────────────────────────────────────
    const loadCandles = useCallback(async () => {
        setLoading(true);
        try {
            const res = await api.get<{ data: any[] }>(
                `/demo-trading/candles/${selectedSymbol}?timeframe=${selectedTimeframe}&limit=500`
            );
            const mapped: CandleData[] = (res.data || []).map((c: any) => ({
                time: c.timestamp,
                open: parseFloat(c.open),
                high: parseFloat(c.high),
                low: parseFloat(c.low),
                close: parseFloat(c.close),
                volume: parseFloat(c.volume),
            }));
            setCandles(mapped);
            if (mapped.length > 0) setCurrentPrice(mapped[mapped.length - 1].close);
        } catch (e) {
            console.error('Failed to load candles:', e);
            setCandles([]);
        } finally {
            setLoading(false);
        }
    }, [selectedSymbol, selectedTimeframe]);

    useEffect(() => { loadCandles(); }, [loadCandles]);

    // ─── WebSocket ───────────────────────────────────────────────────────
    useEffect(() => {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.host;
        const wsUrl = `${protocol}//${host}/ws/demo-trading/stream`;
        let reconnectTimer: ReturnType<typeof setTimeout>;
        let delay = 1000;

        function connect() {
            const ws = new WebSocket(wsUrl);
            ws.onopen = () => {
                setWsConnected(true);
                delay = 1000;
                ws.send(JSON.stringify({ action: 'subscribe', symbol: selectedSymbol, timeframe: selectedTimeframe }));
            };
            ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    if (data.type === 'kline') {
                        const candle: CandleData = {
                            time: data.timestamp,
                            open: parseFloat(data.open), high: parseFloat(data.high),
                            low: parseFloat(data.low), close: parseFloat(data.close),
                            volume: parseFloat(data.volume),
                        };
                        addOrUpdateCandle(candle);
                        if (candleSeriesRef.current) {
                            candleSeriesRef.current.update({
                                time: candle.time as any, open: candle.open,
                                high: candle.high, low: candle.low, close: candle.close,
                            });
                        }
                        if (volumeSeriesRef.current) {
                            volumeSeriesRef.current.update({
                                time: candle.time as any, value: candle.volume,
                                color: candle.close >= candle.open ? 'rgba(16,185,129,0.3)' : 'rgba(239,68,68,0.3)',
                            });
                        }
                    }
                    if (data.type === 'trade_closed') {
                        api.get<{ data: any[] }>('/demo-trading/positions').then((r) => setPositions(r.data)).catch(() => { });
                        api.get<{ data: any[] }>('/demo-trading/history').then((r) => setHistory(r.data)).catch(() => { });
                        api.get<{ data: any }>('/demo-trading/account').then((r) => setAccount(r.data)).catch(() => { });
                    }
                } catch { /* ignore */ }
            };
            ws.onclose = () => {
                setWsConnected(false);
                reconnectTimer = setTimeout(() => { delay = Math.min(delay * 2, 30000); connect(); }, delay);
            };
            ws.onerror = () => ws.close();
            wsRef.current = ws;
        }

        connect();
        return () => { clearTimeout(reconnectTimer); wsRef.current?.close(); };
    }, []);

    useEffect(() => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify({ action: 'subscribe', symbol: selectedSymbol, timeframe: selectedTimeframe }));
        }
    }, [selectedSymbol, selectedTimeframe]);

    // ─── Periodic position refresh ───────────────────────────────────────
    useEffect(() => {
        const interval = setInterval(() => {
            api.get<{ data: any[] }>('/demo-trading/positions').then((r) => setPositions(r.data)).catch(() => { });
            api.get<{ data: any }>('/demo-trading/account').then((r) => setAccount(r.data)).catch(() => { });
        }, 3000);
        return () => clearInterval(interval);
    }, []);

    // ─── Chart rendering with indicators ─────────────────────────────────
    useEffect(() => {
        if (!chartRef.current || candles.length === 0) return;
        if (chartInstance.current) chartInstance.current.remove();

        // Local helpers using debounced chartIndicators (avoids stale closures)
        const isActive = (id: string) => chartIndicators.find((i) => i.id === id)?.active ?? false;
        const getInd = (id: string) => chartIndicators.find((i) => i.id === id)!;

        // Count oscillator panes needed
        const hasRSI = isActive('rsi');
        const hasMACD = isActive('macd');
        const hasStoch = isActive('stochastic');
        const hasCCI = isActive('cci');
        const hasWillR = isActive('williamsR');
        const hasOBV = isActive('obv');
        const hasATR = isActive('atr');
        const hasADX = isActive('adx');
        const oscCount = [hasRSI, hasMACD, hasStoch, hasCCI, hasWillR, hasOBV, hasATR, hasADX].filter(Boolean).length;
        const chartHeight = 500 + oscCount * 130;

        const chart = createChart(chartRef.current, {
            width: chartRef.current.clientWidth,
            height: chartHeight,
            layout: {
                background: { color: 'transparent' },
                textColor: '#64748b',
                fontSize: 11,
                panes: {
                    separatorColor: 'rgba(51,65,85,0.4)',
                    separatorHoverColor: '#3b82f6',
                    enableResize: true,
                },
            },
            grid: {
                vertLines: { color: 'rgba(30,41,59,0.25)' },
                horzLines: { color: 'rgba(30,41,59,0.25)' },
            },
            crosshair: { mode: 0 },
            rightPriceScale: { borderColor: 'rgba(30,41,59,0.5)' },
            timeScale: { borderColor: 'rgba(30,41,59,0.5)', timeVisible: true, secondsVisible: false },
        });

        // ── Pane 0: Candlesticks + Overlays ────────────────────────────────
        const candleSeries = chart.addSeries(CandlestickSeries, {
            upColor: '#10b981',
            downColor: '#ef4444',
            borderUpColor: '#10b981',
            borderDownColor: '#ef4444',
            wickUpColor: '#10b981',
            wickDownColor: '#ef4444',
        }, 0);

        // Helper to convert value arrays to line data
        const toLineData = (values: (number | null)[]) =>
            candles
                .map((c, i) => ({ time: c.time as any, value: values[i] ?? undefined }))
                .filter((d) => d.value !== undefined);

        candleSeries.setData(
            candles.map((c) => ({ time: c.time as any, open: c.open, high: c.high, low: c.low, close: c.close }))
        );

        // ── Volume (overlay on pane 0) ─────────────────────────────────────
        if (isActive('volume')) {
            const volumeSeries = chart.addSeries(HistogramSeries, {
                priceFormat: { type: 'volume' },
                priceScaleId: 'volume',
            }, 0);
            chart.priceScale('volume').applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });
            volumeSeries.setData(
                candles.map((c) => ({
                    time: c.time as any,
                    value: c.volume,
                    color: c.close >= c.open ? 'rgba(16,185,129,0.3)' : 'rgba(239,68,68,0.3)',
                }))
            );
            volumeSeriesRef.current = volumeSeries as any;
        }

        // ── Helper: convert scaleMode string to lightweight-charts numeric mode
        // 0=Normal, 1=Logarithmic, 2=Percentage, 3=IndexedTo100
        const scaleModeNum = (mode: PriceScaleMode): number =>
            mode === 'log' ? 1 : mode === 'percentage' ? 2 : mode === 'indexedTo100' ? 3 : 0;

        // ── Helper: apply scaleMode via a series' priceScale API (v5 compatible)
        const applyScaleToSeries = (series: ISeriesApi<any>, ind: IndicatorConfig) => {
            const mode = scaleModeNum(ind.scaleMode);
            try { series.priceScale().applyOptions({ mode } as any); } catch { /* fallback */ }
        };

        // ── Helper: line series opts from config ─────────────────────────
        const lineOpts = (ind: IndicatorConfig, overrides?: Record<string, any>) => ({
            color: ind.color, lineWidth: ind.lineWidth, priceLineVisible: false,
            lastValueVisible: false, crosshairMarkerVisible: false, ...overrides,
        });

        // Helper: add horizontal reference line in a pane
        const addRefLine = (pane: number, val: number, color: string) => {
            const s = chart.addSeries(LineSeries, {
                color, lineWidth: 1, lineStyle: 2,
                priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
            }, pane);
            const validC = candles.filter((_, i) => i >= 10);
            s.setData(validC.map((c) => ({ time: c.time as any, value: val })));
        };

        // ── SMA Overlays ──────────────────────────────────────────────────
        for (const id of ['sma20', 'sma50', 'sma200']) {
            if (!isActive(id)) continue;
            const cfg = getInd(id);
            chart.addSeries(LineSeries, lineOpts(cfg), 0)
                .setData(toLineData(calcSMA(candles, cfg.params.period)));
        }

        // ── EMA Overlays ───────────────────────────────────────────────────
        for (const id of ['ema9', 'ema21', 'ema50', 'ema200']) {
            if (!isActive(id)) continue;
            const cfg = getInd(id);
            chart.addSeries(LineSeries, lineOpts(cfg), 0)
                .setData(toLineData(calcEMA(candles, cfg.params.period)));
        }

        // ── Bollinger Bands ────────────────────────────────────────────────
        if (isActive('bb')) {
            const cfg = getInd('bb');
            const bb = calcBollingerBands(candles, cfg.params.period, cfg.params.stdDev);
            const bandOpts = (opacity: number, style?: number) => ({
                color: cfg.color + (opacity < 1 ? '80' : '50'), lineWidth: cfg.lineWidth,
                lineStyle: style, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
            });
            chart.addSeries(LineSeries, bandOpts(0.5), 0).setData(toLineData(bb.upper));
            chart.addSeries(LineSeries, bandOpts(0.3, 2), 0).setData(toLineData(bb.middle));
            chart.addSeries(LineSeries, bandOpts(0.5), 0).setData(toLineData(bb.lower));
        }

        // ── Keltner Channel ────────────────────────────────────────────────
        if (isActive('keltner')) {
            const cfg = getInd('keltner');
            const kc = calcKeltnerChannel(candles, cfg.params.emaPeriod, cfg.params.atrPeriod, cfg.params.multiplier);
            const kcOpts = (opacity: number, style?: number) => ({
                color: cfg.color + (opacity < 1 ? '80' : '50'), lineWidth: cfg.lineWidth,
                lineStyle: style, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
            });
            chart.addSeries(LineSeries, kcOpts(0.5), 0).setData(toLineData(kc.upper));
            chart.addSeries(LineSeries, kcOpts(0.3, 2), 0).setData(toLineData(kc.middle));
            chart.addSeries(LineSeries, kcOpts(0.5), 0).setData(toLineData(kc.lower));
        }

        // ── Ichimoku Cloud ─────────────────────────────────────────────────
        if (isActive('ichimoku')) {
            const cfg = getInd('ichimoku');
            const ichi = calcIchimoku(candles, cfg.params.tenkan, cfg.params.kijun, cfg.params.senkouB);
            chart.addSeries(LineSeries, lineOpts(cfg, { color: '#2dd4bf' }), 0).setData(toLineData(ichi.tenkan));
            chart.addSeries(LineSeries, lineOpts(cfg, { color: cfg.color }), 0).setData(toLineData(ichi.kijun));
            chart.addSeries(LineSeries, lineOpts(cfg, { color: 'rgba(16,185,129,0.4)' }), 0).setData(toLineData(ichi.senkouA));
            chart.addSeries(LineSeries, lineOpts(cfg, { color: 'rgba(239,68,68,0.4)' }), 0).setData(toLineData(ichi.senkouB));
        }

        // ── Parabolic SAR ──────────────────────────────────────────────────
        if (isActive('psar')) {
            const cfg = getInd('psar');
            chart.addSeries(LineSeries, {
                color: cfg.color, lineWidth: cfg.lineWidth, lineStyle: 0, priceLineVisible: false,
                lastValueVisible: false, crosshairMarkerVisible: false,
                pointMarkersVisible: true, pointMarkersRadius: 2,
            }, 0).setData(toLineData(calcParabolicSAR(candles, cfg.params.step, cfg.params.max)));
        }

        // ── VWAP ───────────────────────────────────────────────────────────
        if (isActive('vwap')) {
            const cfg = getInd('vwap');
            chart.addSeries(LineSeries, lineOpts(cfg, { lineStyle: 2 }), 0)
                .setData(toLineData(calcVWAP(candles)));
        }

        // ── RSI Pane ───────────────────────────────────────────────────────
        let nextPaneIdx = 1;
        if (hasRSI) {
            chart.addPane();
            const cfg = getInd('rsi');
            const rsiValues = calcRSI(candles, cfg.params.period);
            const s = chart.addSeries(LineSeries, {
                color: cfg.color, lineWidth: cfg.lineWidth, priceLineVisible: false, lastValueVisible: true,
            }, nextPaneIdx);
            s.setData(toLineData(rsiValues));
            applyScaleToSeries(s, cfg);
            addRefLine(nextPaneIdx, 70, 'rgba(239,68,68,0.3)');
            addRefLine(nextPaneIdx, 30, 'rgba(16,185,129,0.3)');
            addRefLine(nextPaneIdx, 50, 'rgba(100,116,139,0.2)');
            nextPaneIdx++;
        }

        // ── MACD Pane ──────────────────────────────────────────────────────
        if (hasMACD) {
            chart.addPane();
            const cfg = getInd('macd');
            const macdResult = calcMACD(candles, cfg.params.fast, cfg.params.slow, cfg.params.signal);
            const s = chart.addSeries(LineSeries, {
                color: cfg.color, lineWidth: cfg.lineWidth, priceLineVisible: false, lastValueVisible: true,
            }, nextPaneIdx);
            s.setData(toLineData(macdResult.macd));
            applyScaleToSeries(s, cfg);
            chart.addSeries(LineSeries, {
                color: '#f97316', lineWidth: 1, priceLineVisible: false,
                lastValueVisible: false, crosshairMarkerVisible: false,
            }, nextPaneIdx).setData(toLineData(macdResult.signal));
            chart.addSeries(HistogramSeries, {
                priceLineVisible: false, lastValueVisible: false,
            }, nextPaneIdx).setData(
                candles.map((c, i) => {
                    const v = macdResult.histogram[i];
                    if (v === null) return null;
                    return { time: c.time as any, value: v, color: v >= 0 ? 'rgba(16,185,129,0.5)' : 'rgba(239,68,68,0.5)' };
                }).filter(Boolean) as any
            );
            addRefLine(nextPaneIdx, 0, 'rgba(100,116,139,0.2)');
            nextPaneIdx++;
        }

        // ── Stochastic Pane ──────────────────────────────────────────────
        if (hasStoch) {
            chart.addPane();
            const cfg = getInd('stochastic');
            const stoch = calcStochastic(candles, cfg.params.kPeriod, cfg.params.dPeriod);
            const s = chart.addSeries(LineSeries, {
                color: cfg.color, lineWidth: cfg.lineWidth, priceLineVisible: false, lastValueVisible: true,
            }, nextPaneIdx);
            s.setData(toLineData(stoch.k));
            applyScaleToSeries(s, cfg);
            chart.addSeries(LineSeries, {
                color: '#f97316', lineWidth: 1, priceLineVisible: false,
                lastValueVisible: false, crosshairMarkerVisible: false,
            }, nextPaneIdx).setData(toLineData(stoch.d));
            addRefLine(nextPaneIdx, 80, 'rgba(239,68,68,0.3)');
            addRefLine(nextPaneIdx, 20, 'rgba(16,185,129,0.3)');
            addRefLine(nextPaneIdx, 50, 'rgba(100,116,139,0.2)');
            nextPaneIdx++;
        }

        // ── CCI Pane ─────────────────────────────────────────────────────
        if (hasCCI) {
            chart.addPane();
            const cfg = getInd('cci');
            const s = chart.addSeries(LineSeries, {
                color: cfg.color, lineWidth: cfg.lineWidth, priceLineVisible: false, lastValueVisible: true,
            }, nextPaneIdx);
            s.setData(toLineData(calcCCI(candles, cfg.params.period)));
            applyScaleToSeries(s, cfg);
            addRefLine(nextPaneIdx, 100, 'rgba(239,68,68,0.3)');
            addRefLine(nextPaneIdx, -100, 'rgba(16,185,129,0.3)');
            addRefLine(nextPaneIdx, 0, 'rgba(100,116,139,0.2)');
            nextPaneIdx++;
        }

        // ── Williams %R Pane ─────────────────────────────────────────────
        if (hasWillR) {
            chart.addPane();
            const cfg = getInd('williamsR');
            const s = chart.addSeries(LineSeries, {
                color: cfg.color, lineWidth: cfg.lineWidth, priceLineVisible: false, lastValueVisible: true,
            }, nextPaneIdx);
            s.setData(toLineData(calcWilliamsR(candles, cfg.params.period)));
            applyScaleToSeries(s, cfg);
            addRefLine(nextPaneIdx, -20, 'rgba(239,68,68,0.3)');
            addRefLine(nextPaneIdx, -80, 'rgba(16,185,129,0.3)');
            addRefLine(nextPaneIdx, -50, 'rgba(100,116,139,0.2)');
            nextPaneIdx++;
        }

        // ── OBV Pane ─────────────────────────────────────────────────────
        if (hasOBV) {
            chart.addPane();
            const cfg = getInd('obv');
            const s = chart.addSeries(LineSeries, {
                color: cfg.color, lineWidth: cfg.lineWidth, priceLineVisible: false, lastValueVisible: true,
            }, nextPaneIdx);
            s.setData(toLineData(calcOBV(candles)));
            applyScaleToSeries(s, cfg);
            nextPaneIdx++;
        }

        // ── ATR Pane ─────────────────────────────────────────────────────
        if (hasATR) {
            chart.addPane();
            const cfg = getInd('atr');
            const s = chart.addSeries(LineSeries, {
                color: cfg.color, lineWidth: cfg.lineWidth, priceLineVisible: false, lastValueVisible: true,
            }, nextPaneIdx);
            s.setData(toLineData(calcATR(candles, cfg.params.period)));
            applyScaleToSeries(s, cfg);
            nextPaneIdx++;
        }

        // ── ADX Pane ─────────────────────────────────────────────────────
        if (hasADX) {
            chart.addPane();
            const cfg = getInd('adx');
            const adxResult = calcADX(candles, cfg.params.period);
            const adxS = chart.addSeries(LineSeries, {
                color: cfg.color, lineWidth: cfg.lineWidth, priceLineVisible: false, lastValueVisible: true,
            }, nextPaneIdx);
            adxS.setData(toLineData(adxResult.adx));
            applyScaleToSeries(adxS, cfg);
            chart.addSeries(LineSeries, {
                color: '#10b981', lineWidth: 1, priceLineVisible: false,
                lastValueVisible: false, crosshairMarkerVisible: false,
            }, nextPaneIdx).setData(toLineData(adxResult.plusDI));
            chart.addSeries(LineSeries, {
                color: '#ef4444', lineWidth: 1, priceLineVisible: false,
                lastValueVisible: false, crosshairMarkerVisible: false,
            }, nextPaneIdx).setData(toLineData(adxResult.minusDI));
            addRefLine(nextPaneIdx, 25, 'rgba(100,116,139,0.3)');
            nextPaneIdx++;
        }

        // ── Pane sizing ────────────────────────────────────────────────────
        const panes = chart.panes();
        if (panes.length > 0) panes[0].setStretchFactor(3);
        for (let i = 1; i < panes.length; i++) panes[i].setStretchFactor(1);

        chart.timeScale().fitContent();
        chartInstance.current = chart;
        candleSeriesRef.current = candleSeries as any;

        const observer = new ResizeObserver(() => {
            if (chartRef.current) chart.applyOptions({ width: chartRef.current.clientWidth });
        });
        observer.observe(chartRef.current);

        return () => {
            observer.disconnect();
            chart.remove();
            chartInstance.current = null;
            candleSeriesRef.current = null;
            volumeSeriesRef.current = null;
        };
    }, [candles.length > 0 ? candles[0].time : 0, selectedSymbol, selectedTimeframe, chartIndicators]);

    // ─── Helpers ─────────────────────────────────────────────────────────
    const groupedSymbols = useMemo(() => {
        const groups: Record<string, DemoSymbol[]> = {};
        for (const sym of symbols) {
            if (!groups[sym.category]) groups[sym.category] = [];
            groups[sym.category].push(sym);
        }
        return groups;
    }, [symbols]);

    const currentSymbolInfo = symbols.find((s) => s.id === selectedSymbol);

    const handleReset = async () => {
        if (!confirm('Reset demo account? This will close all positions and clear history.')) return;
        await api.post<{ data: any }>('/demo-trading/reset', {});
        const [accRes, posRes, histRes] = await Promise.all([
            api.get<{ data: any }>('/demo-trading/account'),
            api.get<{ data: any[] }>('/demo-trading/positions'),
            api.get<{ data: any[] }>('/demo-trading/history'),
        ]);
        setAccount(accRes.data);
        setPositions(posRes.data);
        setHistory(histRes.data);
    };

    const priceChange = candles.length >= 2
        ? candles[candles.length - 1].close - candles[candles.length - 2].close
        : 0;
    const priceChangePct = candles.length >= 2 && candles[candles.length - 2].close > 0
        ? (priceChange / candles[candles.length - 2].close) * 100
        : 0;

    const activeCount = indicators.filter((i) => i.active).length;

    return (
        <div className="space-y-4 stagger-children">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold tracking-tight flex items-center gap-3">
                        Demo Trading
                        <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-medium ${wsConnected
                                ? 'bg-emerald-500/15 text-[var(--accent-green)]'
                                : 'bg-red-500/15 text-[var(--accent-red)]'
                            }`}>
                            {wsConnected ? <Wifi size={10} /> : <WifiOff size={10} />}
                            {wsConnected ? 'LIVE' : 'DISCONNECTED'}
                        </span>
                    </h1>
                    <p className="text-sm text-[var(--text-secondary)] mt-0.5">
                        Paper trading simulator with live market data
                    </p>
                </div>
                <div className="flex items-center gap-3">
                    {currentPrice > 0 && (
                        <div className="text-right">
                            <div className="text-xl font-bold font-mono tabular-nums">
                                {currentPrice.toFixed(currentSymbolInfo?.pipSize && currentSymbolInfo.pipSize < 0.01 ? 5 : 2)}
                            </div>
                            <div className={`text-xs font-medium ${priceChange >= 0 ? 'text-[var(--accent-green)]' : 'text-[var(--accent-red)]'}`}>
                                {priceChange >= 0 ? '+' : ''}{priceChange.toFixed(2)} ({priceChangePct >= 0 ? '+' : ''}{priceChangePct.toFixed(2)}%)
                            </div>
                        </div>
                    )}
                    <button
                        onClick={handleReset}
                        className="btn-ghost flex items-center gap-1.5 text-xs py-2"
                        title="Reset Account"
                    >
                        <RotateCcw size={12} /> Reset
                    </button>
                </div>
            </div>

            {/* Account Summary */}
            {account && (
                <div className="grid grid-cols-4 gap-3">
                    <div className="glass-card p-3">
                        <div className="flex items-center gap-2 mb-1">
                            <DollarSign size={12} className="text-[var(--accent-blue)]" />
                            <span className="text-[10px] uppercase tracking-wider text-[var(--text-muted)]">Balance</span>
                        </div>
                        <div className="text-base font-bold font-mono">${parseFloat(account.balance).toLocaleString(undefined, { minimumFractionDigits: 2 })}</div>
                    </div>
                    <div className="glass-card p-3">
                        <div className="flex items-center gap-2 mb-1">
                            <TrendingUp size={12} className="text-[var(--accent-green)]" />
                            <span className="text-[10px] uppercase tracking-wider text-[var(--text-muted)]">Total PnL</span>
                        </div>
                        <div className={`text-base font-bold font-mono ${parseFloat(account.total_pnl) >= 0 ? 'text-[var(--accent-green)]' : 'text-[var(--accent-red)]'}`}>
                            {parseFloat(account.total_pnl) >= 0 ? '+' : ''}${parseFloat(account.total_pnl).toFixed(2)}
                        </div>
                    </div>
                    <div className="glass-card p-3">
                        <div className="flex items-center gap-2 mb-1">
                            <Award size={12} className="text-[var(--accent-purple)]" />
                            <span className="text-[10px] uppercase tracking-wider text-[var(--text-muted)]">Win Rate</span>
                        </div>
                        <div className="text-base font-bold font-mono">{account.win_rate}%</div>
                        <div className="text-[10px] text-[var(--text-muted)]">{account.wins}W / {account.losses}L</div>
                    </div>
                    <div className="glass-card p-3">
                        <div className="flex items-center gap-2 mb-1">
                            <BarChart3 size={12} className="text-[var(--accent-yellow)]" />
                            <span className="text-[10px] uppercase tracking-wider text-[var(--text-muted)]">Trades</span>
                        </div>
                        <div className="text-base font-bold font-mono">{account.trades_count}</div>
                        <div className="text-[10px] text-[var(--text-muted)]">{account.open_positions} open</div>
                    </div>
                </div>
            )}

            {/* Controls: Symbol + Timeframe + Indicators */}
            <div className="glass-card p-3 space-y-2.5">
                <div className="flex items-center gap-4 flex-wrap">
                    <select
                        className="input-field text-sm py-1.5 w-48"
                        value={selectedSymbol}
                        onChange={(e) => setSelectedSymbol(e.target.value)}
                    >
                        {Object.entries(groupedSymbols).map(([cat, syms]) => (
                            <optgroup key={cat} label={cat}>
                                {syms.map((s) => (
                                    <option key={s.id} value={s.id} disabled={!s.available}>
                                        {s.name} {s.available ? '' : '(offline)'}
                                    </option>
                                ))}
                            </optgroup>
                        ))}
                    </select>

                    <div className="flex gap-0.5 bg-[var(--bg-elevated)] rounded-lg p-0.5">
                        {TIMEFRAMES.map((tf) => (
                            <button
                                key={tf}
                                onClick={() => setSelectedTimeframe(tf)}
                                className={`px-3 py-1.5 text-xs rounded-md transition-all font-medium ${selectedTimeframe === tf
                                        ? 'bg-[var(--accent-blue)] text-white shadow-sm'
                                        : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
                                    }`}
                            >
                                {tf.toUpperCase()}
                            </button>
                        ))}
                    </div>

                    <div className="ml-auto flex items-center gap-3">
                        <span className="text-[10px] text-[var(--text-muted)]">
                            {activeCount} indicator{activeCount !== 1 ? 's' : ''} active
                        </span>
                        <button onClick={loadCandles} className="btn-ghost flex items-center gap-1 text-xs py-1.5">
                            <RefreshCw size={12} className={loading ? 'animate-spin' : ''} /> Refresh
                        </button>
                        <span className="text-xs text-[var(--text-muted)] font-mono tabular-nums">
                            {loading ? 'Loading...' : `${candles.length} bars`}
                        </span>
                    </div>
                </div>

                {/* Indicator Toolbar — relative z-20 so popovers stack above the chart canvas */}
                <div className="border-t border-[var(--border-color)] pt-2.5 relative z-20">
                    <IndicatorToolbar indicators={indicators} onToggle={toggleIndicator} onUpdate={updateIndicator} />
                </div>
            </div>

            {/* Main Layout: Chart + Trade Panel */}
            <div className="grid grid-cols-1 lg:grid-cols-[1fr_240px] gap-3">
                <div className="glass-card overflow-hidden p-1">
                    {loading ? (
                        <div className="h-[500px] flex items-center justify-center">
                            <div className="flex flex-col items-center gap-2">
                                <RefreshCw size={20} className="animate-spin text-[var(--accent-blue)]" />
                                <span className="text-xs text-[var(--text-muted)]">Loading chart data...</span>
                            </div>
                        </div>
                    ) : candles.length === 0 ? (
                        <div className="h-[500px] flex items-center justify-center">
                            <div className="text-center">
                                <BarChart3 size={32} className="mx-auto text-[var(--text-muted)] mb-3 opacity-30" />
                                <p className="text-sm text-[var(--text-muted)]">
                                    {currentSymbolInfo?.available === false
                                        ? `${currentSymbolInfo.name} is not available — only crypto pairs are supported via Binance`
                                        : `No data available for ${selectedSymbol}`}
                                </p>
                            </div>
                        </div>
                    ) : (
                        <div ref={chartRef} className="w-full" />
                    )}
                </div>

                <div className="space-y-2">
                    <TradePanel />
                    <PositionsPanel />
                </div>
            </div>

            <TradeHistoryTable />
        </div>
    );
}
