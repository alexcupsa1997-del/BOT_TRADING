import { useEffect, useState, useCallback } from 'react';
import { RefreshCw, Brain, Clock, Zap } from 'lucide-react';
import { api } from '../api/client';

import VerdictCard from '../components/bot-dashboard/VerdictCard';
import PipelineSteps from '../components/bot-dashboard/PipelineSteps';
import IndicatorsGrid from '../components/bot-dashboard/IndicatorsGrid';
import SignalsTable from '../components/bot-dashboard/SignalsTable';
import RegimeIndicator from '../components/bot-dashboard/RegimeIndicator';
import MLInferencePanel from '../components/bot-dashboard/MLInferencePanel';
import ConfidenceGates from '../components/bot-dashboard/ConfidenceGates';
import AnalysisLog from '../components/bot-dashboard/AnalysisLog';

/* ─── Types ─────────────────────────────────────────────── */

interface AnalysisResult {
    status: string;
    symbol: string;
    timeframe: string;
    timestamp: string;
    current_price: number;
    elapsed_ms: number;
    verdict: any;
    indicators: Record<string, any>;
    signals: any[];
    regime: any;
    ml_inference: any;
    confidence_gates: any;
    pipeline_steps: any[];
    error?: string;
}

/* ─── Constants ─────────────────────────────────────────── */

const SYMBOLS = [
    { id: 'EURUSD', label: 'EUR/USD', icon: '€' },
    { id: 'USDJPY', label: 'USD/JPY', icon: '¥' },
    { id: 'GBPUSD', label: 'GBP/USD', icon: '£' },
    { id: 'USDCHF', label: 'USD/CHF', icon: 'Fr' },
    { id: 'AUDUSD', label: 'AUD/USD', icon: 'A$' },
    { id: 'USDCAD', label: 'USD/CAD', icon: 'C$' },
    { id: 'EURJPY', label: 'EUR/JPY', icon: '€¥' },
    { id: 'EURGBP', label: 'EUR/GBP', icon: '€£' },
    { id: 'NZDUSD', label: 'NZD/USD', icon: 'NZ' },
    { id: 'GBPJPY', label: 'GBP/JPY', icon: '£¥' },
    { id: 'BTCUSD', label: 'BTC/USD', icon: '₿' },
    { id: 'XAUUSD', label: 'XAU/USD', icon: 'Au' },
    { id: 'ETHUSD', label: 'ETH/USD', icon: 'Ξ' },
];

const TIMEFRAMES = ['1m', '5m', '15m', '1h', '4h', '1d'];

/* ─── Component ─────────────────────────────────────────── */

export default function BotDashboardPage() {
    const [symbol, setSymbol] = useState('EURUSD');
    const [timeframe, setTimeframe] = useState('1h');
    const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [autoRefresh, setAutoRefresh] = useState(false);
    const [analysisLog, setAnalysisLog] = useState<any[]>([]);

    const runAnalysis = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const data = await api.get<AnalysisResult>(`/bot/analyze/${symbol}?tf=${timeframe}`);
            if (data.status === 'error') {
                setError(data.error || 'Analysis failed');
                setAnalysis(null);
            } else {
                setAnalysis(data);
                setError(null);
            }
        } catch (err: any) {
            setError(err.message || 'Failed to connect to server');
            setAnalysis(null);
        } finally {
            setLoading(false);
        }
    }, [symbol, timeframe]);

    // Fetch analysis log
    const fetchLog = useCallback(async () => {
        try {
            const res = await api.get<{ data: any[] }>('/bot/log');
            setAnalysisLog(res.data || []);
        } catch { /* silent */ }
    }, []);

    // Auto-refresh
    useEffect(() => {
        if (!autoRefresh) return;
        const interval = setInterval(() => {
            runAnalysis();
            fetchLog();
        }, 30000);
        return () => clearInterval(interval);
    }, [autoRefresh, runAnalysis, fetchLog]);

    // Fetch log on mount and after each analysis
    useEffect(() => { fetchLog(); }, [fetchLog]);
    useEffect(() => { if (analysis) fetchLog(); }, [analysis, fetchLog]);

    return (
        <div className="bot-dashboard">
            {/* ═══ Header Bar ═══ */}
            <div className="bot-header">
                <div className="bot-header-left">
                    <Brain size={24} className="bot-header-icon" />
                    <h1>Bot Dashboard</h1>
                    <span className="bot-header-subtitle">Real-time Analysis Pipeline</span>
                </div>
                <div className="bot-header-right">
                    {analysis && (
                        <span className="bot-elapsed">
                            <Clock size={14} /> {analysis.elapsed_ms}ms
                        </span>
                    )}
                    <button
                        className={`bot-auto-btn ${autoRefresh ? 'bot-auto-active' : ''}`}
                        onClick={() => setAutoRefresh(!autoRefresh)}
                        title="Auto-refresh every 30s"
                    >
                        <Zap size={14} /> Auto
                    </button>
                </div>
            </div>

            {/* ═══ Controls ═══ */}
            <div className="bot-controls">
                {/* Symbol selector */}
                <div className="bot-symbol-selector">
                    {SYMBOLS.map(s => (
                        <button
                            key={s.id}
                            className={`bot-symbol-btn ${symbol === s.id ? 'bot-symbol-active' : ''}`}
                            onClick={() => setSymbol(s.id)}
                        >
                            <span className="bot-symbol-icon">{s.icon}</span>
                            <span className="bot-symbol-label">{s.label}</span>
                        </button>
                    ))}
                </div>

                {/* Timeframe selector + Analyze button */}
                <div className="bot-tf-row">
                    <div className="bot-tf-selector">
                        {TIMEFRAMES.map(tf => (
                            <button
                                key={tf}
                                className={`bot-tf-btn ${timeframe === tf ? 'bot-tf-active' : ''}`}
                                onClick={() => setTimeframe(tf)}
                            >
                                {tf}
                            </button>
                        ))}
                    </div>

                    <button
                        className="bot-analyze-btn"
                        onClick={runAnalysis}
                        disabled={loading}
                    >
                        <RefreshCw size={16} className={loading ? 'spin' : ''} />
                        {loading ? 'Analyzing...' : 'Analyze'}
                    </button>
                </div>
            </div>

            {/* ═══ Error ═══ */}
            {error && (
                <div className="bot-error">
                    <span>⚠️ {error}</span>
                </div>
            )}

            {/* ═══ Content ═══ */}
            {(analysis || loading) && (
                <div className="bot-content">
                    {/* Verdict */}
                    <VerdictCard
                        verdict={analysis?.verdict || null}
                        currentPrice={analysis?.current_price || 0}
                        loading={loading}
                    />

                    {/* Pipeline */}
                    {analysis?.pipeline_steps && (
                        <PipelineSteps steps={analysis.pipeline_steps} />
                    )}

                    {/* Two-column: Indicators + Signals */}
                    <div className="bot-two-col">
                        <div className="bot-col-left">
                            {analysis?.indicators && (
                                <IndicatorsGrid
                                    indicators={analysis.indicators}
                                    currentPrice={analysis.current_price}
                                />
                            )}
                        </div>
                        <div className="bot-col-right">
                            {analysis?.signals && (
                                <SignalsTable signals={analysis.signals} />
                            )}
                        </div>
                    </div>

                    {/* Three-column: Regime + ML + Gates */}
                    <div className="bot-three-col">
                        <RegimeIndicator regime={analysis?.regime || null} />
                        <MLInferencePanel mlData={analysis?.ml_inference || null} />
                        <ConfidenceGates gates={analysis?.confidence_gates || null} />
                    </div>

                    {/* Analysis Log */}
                    <AnalysisLog log={analysisLog} />
                </div>
            )}

            {/* ═══ Empty State ═══ */}
            {!analysis && !loading && !error && (
                <div className="bot-empty-state">
                    <Brain size={64} />
                    <h2>Select a symbol and click Analyze</h2>
                    <p>The bot will run its full analysis pipeline and show you every step of its reasoning</p>
                </div>
            )}

            {/* ═══ Styles ═══ */}
            <style>{`
        .bot-dashboard {
          padding: 1.5rem;
          max-width: 1600px;
          margin: 0 auto;
        }

        /* ── Header ── */
        .bot-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-bottom: 1.5rem;
        }
        .bot-header-left {
          display: flex;
          align-items: center;
          gap: 0.75rem;
        }
        .bot-header-left h1 {
          font-size: 1.5rem;
          font-weight: 700;
          color: #e0e0e0;
          margin: 0;
        }
        .bot-header-icon { color: #7c4dff; }
        .bot-header-subtitle {
          font-size: 0.8rem;
          color: #666;
          padding: 0.2rem 0.6rem;
          background: rgba(124,77,255,0.1);
          border-radius: 12px;
        }
        .bot-header-right {
          display: flex;
          align-items: center;
          gap: 0.75rem;
        }
        .bot-elapsed {
          font-size: 0.78rem;
          color: #888;
          display: flex;
          align-items: center;
          gap: 0.3rem;
        }
        .bot-auto-btn {
          display: flex;
          align-items: center;
          gap: 0.3rem;
          padding: 0.4rem 0.8rem;
          border-radius: 8px;
          border: 1px solid rgba(255,255,255,0.1);
          background: rgba(255,255,255,0.04);
          color: #888;
          font-size: 0.78rem;
          cursor: pointer;
          transition: all 0.2s;
        }
        .bot-auto-btn:hover { border-color: rgba(124,77,255,0.4); color: #aaa; }
        .bot-auto-active {
          background: rgba(124,77,255,0.15);
          border-color: rgba(124,77,255,0.5);
          color: #7c4dff;
        }

        /* ── Controls ── */
        .bot-controls {
          margin-bottom: 1.5rem;
        }
        .bot-symbol-selector {
          display: flex;
          gap: 0.5rem;
          flex-wrap: wrap;
          margin-bottom: 0.75rem;
        }
        .bot-symbol-btn {
          display: flex;
          align-items: center;
          gap: 0.4rem;
          padding: 0.5rem 0.9rem;
          border-radius: 10px;
          border: 1px solid rgba(255,255,255,0.08);
          background: rgba(255,255,255,0.03);
          color: #aaa;
          font-size: 0.82rem;
          cursor: pointer;
          transition: all 0.2s;
        }
        .bot-symbol-btn:hover { border-color: rgba(255,255,255,0.2); background: rgba(255,255,255,0.06); }
        .bot-symbol-active {
          background: rgba(124,77,255,0.15);
          border-color: rgba(124,77,255,0.5);
          color: #fff;
        }
        .bot-symbol-icon { font-size: 1rem; }

        .bot-tf-row {
          display: flex;
          align-items: center;
          gap: 0.75rem;
        }
        .bot-tf-selector {
          display: flex;
          gap: 0.25rem;
          background: rgba(255,255,255,0.03);
          border-radius: 10px;
          padding: 0.2rem;
        }
        .bot-tf-btn {
          padding: 0.4rem 0.75rem;
          border-radius: 8px;
          border: none;
          background: transparent;
          color: #888;
          font-size: 0.78rem;
          cursor: pointer;
          transition: all 0.2s;
          font-weight: 500;
        }
        .bot-tf-btn:hover { color: #ccc; background: rgba(255,255,255,0.06); }
        .bot-tf-active { background: rgba(124,77,255,0.2); color: #fff; }

        .bot-analyze-btn {
          display: flex;
          align-items: center;
          gap: 0.4rem;
          padding: 0.55rem 1.5rem;
          border-radius: 10px;
          border: none;
          background: linear-gradient(135deg, #7c4dff 0%, #536dfe 100%);
          color: #fff;
          font-size: 0.85rem;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.3s;
          box-shadow: 0 4px 15px rgba(124,77,255,0.3);
        }
        .bot-analyze-btn:hover { transform: translateY(-1px); box-shadow: 0 6px 20px rgba(124,77,255,0.4); }
        .bot-analyze-btn:disabled { opacity: 0.6; cursor: not-allowed; transform: none; }
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        .spin { animation: spin 1s linear infinite; }

        /* ── Error ── */
        .bot-error {
          padding: 0.8rem 1.2rem;
          border-radius: 10px;
          background: rgba(255,23,68,0.08);
          border: 1px solid rgba(255,23,68,0.3);
          color: #ff5252;
          margin-bottom: 1.5rem;
          font-size: 0.85rem;
        }

        /* ── Content ── */
        .bot-content { display: flex; flex-direction: column; gap: 1.5rem; }

        /* ── Section titles ── */
        .section-title {
          font-size: 0.95rem;
          font-weight: 600;
          color: #ccc;
          margin: 0 0 0.75rem 0;
          display: flex;
          align-items: center;
          gap: 0.5rem;
        }

        /* ── Verdict Card ── */
        .verdict-card {
          display: grid;
          grid-template-columns: 120px 1fr 200px;
          grid-template-rows: auto auto;
          gap: 1.5rem;
          padding: 1.5rem;
          border-radius: 16px;
          background: linear-gradient(135deg, rgba(30,30,40,0.9) 0%, rgba(20,20,30,0.95) 100%);
          border: 2px solid rgba(255,255,255,0.1);
          position: relative;
          overflow: hidden;
        }
        .verdict-card::before {
          content: '';
          position: absolute;
          top: 0;
          left: 0;
          right: 0;
          height: 3px;
          background: currentColor;
          opacity: 0.5;
        }
        .verdict-ring-container {
          position: relative;
          display: flex;
          align-items: center;
          justify-content: center;
        }
        .verdict-ring-label {
          position: absolute;
          text-align: center;
          display: flex;
          flex-direction: column;
        }
        .verdict-conf-value { font-size: 1.4rem; font-weight: 700; }
        .verdict-conf-text { font-size: 0.65rem; color: #888; text-transform: uppercase; }

        .verdict-action-block {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          gap: 0.3rem;
        }
        .verdict-action-label { font-size: 1.8rem; font-weight: 800; letter-spacing: 2px; }
        .verdict-tier {
          font-size: 0.7rem;
          color: #888;
          display: flex;
          align-items: center;
          gap: 0.3rem;
          padding: 0.15rem 0.5rem;
          background: rgba(255,255,255,0.05);
          border-radius: 6px;
        }

        .verdict-levels {
          display: flex;
          flex-direction: column;
          gap: 0.5rem;
          justify-content: center;
        }
        .verdict-level-row {
          display: flex;
          justify-content: space-between;
          font-size: 0.82rem;
          padding: 0.3rem 0.6rem;
          border-radius: 6px;
          background: rgba(255,255,255,0.04);
        }
        .verdict-level-label {
          color: #888;
          display: flex;
          align-items: center;
          gap: 0.3rem;
        }
        .verdict-level-value { color: #e0e0e0; font-weight: 600; font-family: 'JetBrains Mono', monospace; }
        .verdict-sl .verdict-level-value { color: #ff5252; }
        .verdict-tp .verdict-level-value { color: #69f0ae; }

        .verdict-reasoning {
          grid-column: 1 / -1;
          padding-top: 0.75rem;
          border-top: 1px solid rgba(255,255,255,0.06);
        }
        .verdict-reasoning p { font-size: 0.82rem; color: #aaa; margin: 0 0 0.5rem 0; line-height: 1.5; }
        .verdict-weights {
          display: flex;
          gap: 1rem;
          font-size: 0.75rem;
        }

        .verdict-loading, .verdict-empty {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 0.75rem;
          padding: 2rem;
          color: #666;
          font-size: 0.9rem;
        }
        .verdict-spinner {
          width: 24px;
          height: 24px;
          border: 3px solid rgba(124,77,255,0.2);
          border-top-color: #7c4dff;
          border-radius: 50%;
          animation: spin 0.8s linear infinite;
        }

        /* ── Pipeline ── */
        .pipeline-container {
          background: rgba(255,255,255,0.02);
          border-radius: 14px;
          padding: 1.25rem;
          border: 1px solid rgba(255,255,255,0.06);
        }
        .pipeline-steps {
          display: flex;
          gap: 0;
          overflow-x: auto;
          padding: 0.5rem 0;
        }
        .pipeline-step {
          flex: 1;
          min-width: 120px;
          padding: 0.6rem 0.8rem;
          text-align: center;
          position: relative;
        }
        .pipeline-step-header {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 0.3rem;
          margin-bottom: 0.3rem;
        }
        .step-icon-ok { color: #00c853; }
        .step-icon-warn { color: #ffc107; }
        .step-icon-stub { color: #888; }
        .step-icon-error { color: #ff1744; }
        .pipeline-step-num { font-size: 0.65rem; color: #666; }
        .pipeline-step-name { font-size: 0.78rem; font-weight: 600; color: #ccc; margin-bottom: 0.2rem; }
        .pipeline-step-detail { font-size: 0.68rem; color: #888; }
        .pipeline-connector {
          position: absolute;
          right: -8px;
          top: 50%;
          width: 16px;
          height: 2px;
          background: rgba(255,255,255,0.15);
          z-index: 1;
        }

        /* ── Two column layout ── */
        .bot-two-col {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 1.5rem;
        }
        @media (max-width: 1100px) {
          .bot-two-col { grid-template-columns: 1fr; }
        }

        /* ── Three column layout ── */
        .bot-three-col {
          display: grid;
          grid-template-columns: 1fr 1fr 1fr;
          gap: 1.5rem;
        }
        @media (max-width: 1200px) {
          .bot-three-col { grid-template-columns: 1fr; }
        }

        /* ── Indicators Grid ── */
        .indicators-grid-container {
          background: rgba(255,255,255,0.02);
          border-radius: 14px;
          padding: 1.25rem;
          border: 1px solid rgba(255,255,255,0.06);
        }
        .indicators-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
          gap: 0.75rem;
        }
        .indicator-card {
          padding: 0.75rem;
          border-radius: 10px;
          background: rgba(255,255,255,0.03);
          border-left: 3px solid #888;
          transition: all 0.2s;
        }
        .indicator-card:hover { background: rgba(255,255,255,0.06); }
        .indicator-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 0.3rem;
        }
        .indicator-label { font-size: 0.72rem; color: #888; font-weight: 500; }
        .indicator-value { font-size: 1.15rem; font-weight: 700; font-family: 'JetBrains Mono', monospace; }
        .indicator-zone-tag {
          display: inline-block;
          padding: 0.1rem 0.4rem;
          border-radius: 4px;
          font-size: 0.6rem;
          color: #fff;
          text-transform: uppercase;
          margin-top: 0.3rem;
          opacity: 0.8;
        }
        .indicator-detail { font-size: 0.68rem; color: #666; margin-top: 0.2rem; }
        .indicator-bb-values {
          display: flex;
          flex-direction: column;
          gap: 0.15rem;
          font-size: 0.75rem;
          color: #aaa;
          font-family: 'JetBrains Mono', monospace;
        }

        /* ── Signals Table ── */
        .signals-container {
          background: rgba(255,255,255,0.02);
          border-radius: 14px;
          padding: 1.25rem;
          border: 1px solid rgba(255,255,255,0.06);
        }
        .signals-summary {
          font-size: 0.75rem;
          font-weight: 400;
          margin-left: 0.5rem;
        }
        .signals-table { display: flex; flex-direction: column; gap: 0.3rem; }
        .signals-header, .signals-row {
          display: grid;
          grid-template-columns: 120px 100px 140px 1fr;
          gap: 0.5rem;
          align-items: center;
          padding: 0.4rem 0.6rem;
          font-size: 0.78rem;
        }
        .signals-header {
          color: #666;
          font-weight: 600;
          font-size: 0.7rem;
          text-transform: uppercase;
          border-bottom: 1px solid rgba(255,255,255,0.06);
          padding-bottom: 0.6rem;
        }
        .signals-row {
          border-radius: 8px;
          transition: background 0.2s;
        }
        .signals-row:hover { background: rgba(255,255,255,0.04); }
        .signal-source { color: #ccc; font-weight: 500; }
        .signal-direction {
          display: flex;
          align-items: center;
          gap: 0.25rem;
          font-weight: 600;
          font-size: 0.72rem;
        }
        .signal-strength {
          display: flex;
          align-items: center;
          gap: 0.4rem;
        }
        .strength-bar-bg {
          flex: 1;
          height: 6px;
          border-radius: 3px;
          background: rgba(255,255,255,0.08);
          overflow: hidden;
        }
        .strength-bar-fill {
          height: 100%;
          border-radius: 3px;
          transition: width 0.5s ease;
        }
        .strength-value { font-size: 0.7rem; color: #888; min-width: 30px; }
        .signal-detail { font-size: 0.72rem; color: #666; }

        /* ── Regime ── */
        .regime-container {
          background: rgba(255,255,255,0.02);
          border-radius: 14px;
          padding: 1.25rem;
          border: 1px solid rgba(255,255,255,0.06);
        }
        .regime-card {
          display: flex;
          align-items: center;
          gap: 1rem;
          padding: 1rem;
          border-radius: 12px;
          border: 1px solid;
        }
        .regime-icon { font-size: 2rem; }
        .regime-info { flex: 1; }
        .regime-label { font-size: 1.1rem; font-weight: 700; }
        .regime-description { font-size: 0.78rem; color: #aaa; margin: 0.2rem 0; }
        .regime-strategy-label { font-size: 0.72rem; color: #666; }
        .regime-strategy-value { font-size: 0.78rem; color: #ccc; margin-left: 0.3rem; font-weight: 500; }
        .regime-confidence { display: flex; flex-direction: column; align-items: center; gap: 0.3rem; min-width: 60px; }
        .regime-conf-bar { width: 60px; height: 6px; border-radius: 3px; overflow: hidden; }
        .regime-conf-fill { height: 100%; border-radius: 3px; transition: width 0.5s; }
        .regime-conf-text { font-size: 0.7rem; color: #888; }

        /* ── ML Inference ── */
        .ml-container {
          background: rgba(255,255,255,0.02);
          border-radius: 14px;
          padding: 1.25rem;
          border: 1px solid rgba(255,255,255,0.06);
        }
        .ml-card { display: flex; flex-direction: column; gap: 0.75rem; }
        .ml-model-info {
          display: flex;
          align-items: center;
          gap: 0.5rem;
          font-size: 0.78rem;
          color: #888;
        }
        .ml-model-type { color: #ccc; font-weight: 500; }
        .ml-model-status {
          padding: 0.1rem 0.4rem;
          border-radius: 4px;
          font-size: 0.65rem;
          font-weight: 600;
        }
        .ml-loaded { background: rgba(0,200,83,0.15); color: #00c853; }
        .ml-stub { background: rgba(255,193,7,0.15); color: #ffc107; }
        .ml-probs-title { font-size: 0.72rem; color: #666; margin-bottom: 0.3rem; }
        .ml-prob-row {
          display: flex;
          align-items: center;
          gap: 0.5rem;
          margin-bottom: 0.3rem;
        }
        .ml-prob-label { font-size: 0.75rem; color: #aaa; min-width: 40px; font-weight: 500; }
        .ml-prob-bar-bg {
          flex: 1;
          height: 10px;
          border-radius: 5px;
          background: rgba(255,255,255,0.06);
          overflow: hidden;
        }
        .ml-prob-bar-fill {
          height: 100%;
          border-radius: 5px;
          transition: width 0.5s ease;
        }
        .ml-prob-value { font-size: 0.72rem; color: #888; min-width: 40px; text-align: right; }
        .ml-confidence {
          display: flex;
          justify-content: space-between;
          font-size: 0.78rem;
          color: #888;
          padding-top: 0.5rem;
          border-top: 1px solid rgba(255,255,255,0.06);
        }
        .ml-conf-value { color: #ccc; font-weight: 600; }
        .ml-tpsl {
          display: flex;
          gap: 1rem;
          font-size: 0.72rem;
          color: #888;
        }
        .ml-note {
          font-size: 0.68rem;
          color: #555;
          font-style: italic;
          padding: 0.5rem;
          background: rgba(255,255,255,0.02);
          border-radius: 6px;
        }

        /* ── Confidence Gates ── */
        .gates-container {
          background: rgba(255,255,255,0.02);
          border-radius: 14px;
          padding: 1.25rem;
          border: 1px solid rgba(255,255,255,0.06);
        }
        .gates-summary {
          font-size: 0.7rem;
          padding: 0.15rem 0.5rem;
          border-radius: 6px;
          font-weight: 600;
        }
        .gates-all-pass { background: rgba(0,200,83,0.15); color: #00c853; }
        .gates-warn { background: rgba(255,152,0,0.15); color: #ff9800; }
        .gates-grid { display: flex; flex-direction: column; gap: 0.5rem; }
        .gate-card {
          display: flex;
          align-items: center;
          gap: 0.75rem;
          padding: 0.75rem;
          border-radius: 10px;
          background: rgba(255,255,255,0.03);
          transition: all 0.2s;
        }
        .gate-card:hover { background: rgba(255,255,255,0.06); }
        .gate-pass { border-left: 3px solid #00c853; }
        .gate-fail { border-left: 3px solid #ff9800; }
        .gate-info { flex: 1; }
        .gate-label { font-size: 0.82rem; font-weight: 600; color: #ccc; }
        .gate-description { font-size: 0.7rem; color: #666; }
        .gate-detail { font-size: 0.72rem; color: #888; margin-top: 0.15rem; font-family: 'JetBrains Mono', monospace; }
        .gate-alert { font-size: 0.68rem; color: #00c853; margin-top: 0.15rem; }
        .gate-alert-warn { color: #ff9800; }
        .gate-badge {
          padding: 0.2rem 0.5rem;
          border-radius: 6px;
          font-size: 0.65rem;
          font-weight: 700;
        }
        .gate-badge-pass { background: rgba(0,200,83,0.15); color: #00c853; }
        .gate-badge-fail { background: rgba(255,152,0,0.15); color: #ff9800; }

        /* ── Analysis Log ── */
        .log-container {
          background: rgba(255,255,255,0.02);
          border-radius: 14px;
          padding: 1.25rem;
          border: 1px solid rgba(255,255,255,0.06);
        }
        .log-empty { color: #666; font-size: 0.85rem; text-align: center; padding: 1rem; }
        .log-list { display: flex; flex-direction: column; gap: 0.2rem; max-height: 300px; overflow-y: auto; }
        .log-entry {
          display: grid;
          grid-template-columns: 100px 80px 40px 80px 50px 50px;
          gap: 0.5rem;
          align-items: center;
          padding: 0.4rem 0.6rem;
          font-size: 0.75rem;
          border-radius: 6px;
          transition: background 0.2s;
        }
        .log-entry:hover { background: rgba(255,255,255,0.04); }
        .log-time { color: #666; display: flex; align-items: center; gap: 0.3rem; }
        .log-symbol { color: #ccc; font-weight: 500; }
        .log-tf { color: #888; }
        .log-action { display: flex; align-items: center; gap: 0.25rem; font-weight: 600; }
        .log-conf { color: #888; text-align: right; }
        .log-elapsed { color: #555; text-align: right; }

        /* ── Empty State ── */
        .bot-empty-state {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          padding: 4rem;
          color: #444;
          text-align: center;
        }
        .bot-empty-state h2 { color: #666; font-size: 1.2rem; margin: 1rem 0 0.5rem; }
        .bot-empty-state p { color: #555; font-size: 0.85rem; max-width: 400px; }
      `}</style>
        </div>
    );
}
