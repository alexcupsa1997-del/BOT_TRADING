import { useState, useRef, useEffect, useCallback } from 'react';
import {
    Activity, TrendingUp, BarChart3, Layers, LineChart,
    ChevronDown, ChevronRight, Circle, Gauge, Waves, Target, Zap,
    Settings,
} from 'lucide-react';

/* ─── Types ──────────────────────────────────────────────────────── */

export interface IndicatorConfig {
    id: string;
    label: string;
    icon: typeof Activity;
    active: boolean;
    color: string;
    lineWidth: 1 | 2 | 3 | 4;
    group: 'ma' | 'bands' | 'volume' | 'momentum' | 'volatility' | 'trend';
    description?: string;
    params: Record<string, number>;
}

/** Which params each indicator exposes (label → key in params) */
export const INDICATOR_PARAM_DEFS: Record<string, { label: string; key: string; min: number; max: number; step: number }[]> = {
    sma20:      [{ label: 'Period', key: 'period', min: 2, max: 500, step: 1 }],
    sma50:      [{ label: 'Period', key: 'period', min: 2, max: 500, step: 1 }],
    sma200:     [{ label: 'Period', key: 'period', min: 2, max: 500, step: 1 }],
    ema9:       [{ label: 'Period', key: 'period', min: 2, max: 500, step: 1 }],
    ema21:      [{ label: 'Period', key: 'period', min: 2, max: 500, step: 1 }],
    ema50:      [{ label: 'Period', key: 'period', min: 2, max: 500, step: 1 }],
    ema200:     [{ label: 'Period', key: 'period', min: 2, max: 500, step: 1 }],
    bb:         [{ label: 'Period', key: 'period', min: 5, max: 100, step: 1 }, { label: 'Std Dev', key: 'stdDev', min: 0.5, max: 4, step: 0.1 }],
    keltner:    [{ label: 'EMA Period', key: 'emaPeriod', min: 5, max: 100, step: 1 }, { label: 'ATR Period', key: 'atrPeriod', min: 5, max: 50, step: 1 }, { label: 'Multiplier', key: 'multiplier', min: 0.5, max: 4, step: 0.1 }],
    ichimoku:   [{ label: 'Tenkan', key: 'tenkan', min: 5, max: 50, step: 1 }, { label: 'Kijun', key: 'kijun', min: 10, max: 100, step: 1 }, { label: 'Senkou B', key: 'senkouB', min: 20, max: 200, step: 1 }],
    rsi:        [{ label: 'Period', key: 'period', min: 2, max: 100, step: 1 }],
    macd:       [{ label: 'Fast', key: 'fast', min: 2, max: 100, step: 1 }, { label: 'Slow', key: 'slow', min: 2, max: 100, step: 1 }, { label: 'Signal', key: 'signal', min: 2, max: 50, step: 1 }],
    stochastic: [{ label: '%K Period', key: 'kPeriod', min: 2, max: 50, step: 1 }, { label: '%D Period', key: 'dPeriod', min: 2, max: 20, step: 1 }],
    cci:        [{ label: 'Period', key: 'period', min: 5, max: 100, step: 1 }],
    williamsR:  [{ label: 'Period', key: 'period', min: 2, max: 100, step: 1 }],
    atr:        [{ label: 'Period', key: 'period', min: 2, max: 100, step: 1 }],
    psar:       [{ label: 'Step', key: 'step', min: 0.005, max: 0.1, step: 0.005 }, { label: 'Max', key: 'max', min: 0.05, max: 0.5, step: 0.01 }],
    adx:        [{ label: 'Period', key: 'period', min: 2, max: 100, step: 1 }],
};

/* ─── Groups ─────────────────────────────────────────────────────── */

export const INDICATOR_GROUPS = {
    ma: { label: 'Medie Mobili', icon: TrendingUp },
    bands: { label: 'Bande & Canali', icon: Layers },
    volume: { label: 'Volume', icon: BarChart3 },
    momentum: { label: 'Momentum', icon: Zap },
    volatility: { label: 'Volatilità', icon: Waves },
    trend: { label: 'Trend', icon: Target },
} as const;

/* ─── Default Indicators ─────────────────────────────────────────── */

export const DEFAULT_INDICATORS: IndicatorConfig[] = [
    // Medie Mobili
    { id: 'sma20', label: 'SMA 20', icon: TrendingUp, active: false, color: '#06b6d4', lineWidth: 1, group: 'ma', description: 'Simple Moving Average', params: { period: 20 } },
    { id: 'sma50', label: 'SMA 50', icon: TrendingUp, active: false, color: '#0ea5e9', lineWidth: 1, group: 'ma', description: 'Simple Moving Average', params: { period: 50 } },
    { id: 'sma200', label: 'SMA 200', icon: TrendingUp, active: false, color: '#0284c7', lineWidth: 2, group: 'ma', description: 'Simple Moving Average', params: { period: 200 } },
    { id: 'ema9', label: 'EMA 9', icon: TrendingUp, active: true, color: '#f59e0b', lineWidth: 1, group: 'ma', description: 'Exponential Moving Average', params: { period: 9 } },
    { id: 'ema21', label: 'EMA 21', icon: TrendingUp, active: true, color: '#3b82f6', lineWidth: 1, group: 'ma', description: 'Exponential Moving Average', params: { period: 21 } },
    { id: 'ema50', label: 'EMA 50', icon: TrendingUp, active: false, color: '#a855f7', lineWidth: 2, group: 'ma', description: 'Exponential Moving Average', params: { period: 50 } },
    { id: 'ema200', label: 'EMA 200', icon: TrendingUp, active: false, color: '#ef4444', lineWidth: 2, group: 'ma', description: 'Exponential Moving Average', params: { period: 200 } },

    // Bande & Canali
    { id: 'bb', label: 'Bollinger', icon: Layers, active: true, color: '#6366f1', lineWidth: 1, group: 'bands', description: 'Bollinger Bands', params: { period: 20, stdDev: 2 } },
    { id: 'keltner', label: 'Keltner', icon: Layers, active: false, color: '#ec4899', lineWidth: 1, group: 'bands', description: 'Keltner Channel', params: { emaPeriod: 20, atrPeriod: 10, multiplier: 1.5 } },
    { id: 'ichimoku', label: 'Ichimoku', icon: Layers, active: false, color: '#f97316', lineWidth: 1, group: 'bands', description: 'Ichimoku Cloud', params: { tenkan: 9, kijun: 26, senkouB: 52 } },

    // Volume
    { id: 'volume', label: 'Volume', icon: BarChart3, active: true, color: '#64748b', lineWidth: 1, group: 'volume', description: 'Volume histogram', params: {} },
    { id: 'vwap', label: 'VWAP', icon: LineChart, active: false, color: '#14b8a6', lineWidth: 2, group: 'volume', description: 'Volume Weighted Avg Price', params: {} },
    { id: 'obv', label: 'OBV', icon: BarChart3, active: false, color: '#22d3ee', lineWidth: 2, group: 'volume', description: 'On Balance Volume', params: {} },

    // Momentum
    { id: 'rsi', label: 'RSI', icon: Activity, active: true, color: '#f97316', lineWidth: 2, group: 'momentum', description: 'Relative Strength Index', params: { period: 14 } },
    { id: 'macd', label: 'MACD', icon: Activity, active: false, color: '#8b5cf6', lineWidth: 2, group: 'momentum', description: 'MACD', params: { fast: 12, slow: 26, signal: 9 } },
    { id: 'stochastic', label: 'Stochastic', icon: Gauge, active: false, color: '#10b981', lineWidth: 2, group: 'momentum', description: 'Stochastic Oscillator', params: { kPeriod: 14, dPeriod: 3 } },
    { id: 'cci', label: 'CCI', icon: Activity, active: false, color: '#eab308', lineWidth: 2, group: 'momentum', description: 'Commodity Channel Index', params: { period: 20 } },
    { id: 'williamsR', label: 'Will %R', icon: Activity, active: false, color: '#f43f5e', lineWidth: 2, group: 'momentum', description: 'Williams Percent Range', params: { period: 14 } },

    // Volatilità
    { id: 'atr', label: 'ATR', icon: Waves, active: false, color: '#84cc16', lineWidth: 2, group: 'volatility', description: 'Average True Range', params: { period: 14 } },

    // Trend
    { id: 'psar', label: 'P. SAR', icon: Circle, active: false, color: '#fbbf24', lineWidth: 1, group: 'trend', description: 'Parabolic Stop & Reverse', params: { step: 0.02, max: 0.2 } },
    { id: 'adx', label: 'ADX', icon: Target, active: false, color: '#2dd4bf', lineWidth: 2, group: 'trend', description: 'Average Directional Index', params: { period: 14 } },
];

/* ─── Settings Popover ───────────────────────────────────────────── */

function IndicatorSettingsPopover({
    indicator,
    onUpdate,
    onClose,
}: {
    indicator: IndicatorConfig;
    onUpdate: (id: string, changes: Partial<IndicatorConfig>) => void;
    onClose: () => void;
}) {
    const ref = useRef<HTMLDivElement>(null);
    const paramDefs = INDICATOR_PARAM_DEFS[indicator.id] || [];

    useEffect(() => {
        const handleClick = (e: MouseEvent) => {
            if (ref.current && !ref.current.contains(e.target as Node)) onClose();
        };
        const handleKey = (e: KeyboardEvent) => {
            if (e.key === 'Escape') onClose();
        };
        document.addEventListener('mousedown', handleClick);
        document.addEventListener('keydown', handleKey);
        return () => {
            document.removeEventListener('mousedown', handleClick);
            document.removeEventListener('keydown', handleKey);
        };
    }, [onClose]);

    return (
        <div
            ref={ref}
            className="absolute top-full left-0 mt-1 z-50 min-w-[200px] rounded-lg border border-[var(--border-color)] bg-[var(--bg-card)] shadow-xl shadow-black/30 p-2.5 space-y-2"
            style={{ animation: 'fadeInUp 0.15s ease-out' }}
            onClick={(e) => e.stopPropagation()}
        >
            <div className="text-[10px] font-semibold text-[var(--text-primary)] uppercase tracking-wider mb-1">
                {indicator.label} Settings
            </div>

            {/* Color */}
            <div className="flex items-center justify-between">
                <span className="text-[10px] text-[var(--text-muted)]">Colore</span>
                <div className="flex items-center gap-1.5">
                    <div
                        className="w-5 h-5 rounded border border-[var(--border-color)]"
                        style={{ backgroundColor: indicator.color }}
                    />
                    <input
                        type="color"
                        value={indicator.color}
                        onChange={(e) => onUpdate(indicator.id, { color: e.target.value })}
                        className="w-6 h-6 cursor-pointer bg-transparent border-0 p-0"
                    />
                </div>
            </div>

            {/* Line Width */}
            <div>
                <span className="text-[10px] text-[var(--text-muted)]">Spessore</span>
                <div className="flex gap-1 mt-0.5">
                    {([1, 2, 3, 4] as const).map((w) => (
                        <button
                            key={w}
                            onClick={() => onUpdate(indicator.id, { lineWidth: w })}
                            className={`flex-1 py-1 rounded text-[10px] font-medium transition-all ${
                                indicator.lineWidth === w
                                    ? 'text-white'
                                    : 'bg-[var(--bg-elevated)] text-[var(--text-muted)] hover:text-[var(--text-secondary)]'
                            }`}
                            style={indicator.lineWidth === w ? { backgroundColor: indicator.color } : undefined}
                        >
                            {w}px
                        </button>
                    ))}
                </div>
            </div>

            {/* Params */}
            {paramDefs.map((def) => (
                <div key={def.key}>
                    <div className="flex items-center justify-between">
                        <span className="text-[10px] text-[var(--text-muted)]">{def.label}</span>
                        <span className="text-[10px] font-mono text-[var(--text-secondary)]">
                            {def.step < 1
                                ? (indicator.params[def.key] ?? 0).toFixed(String(def.step).split('.')[1]?.length || 2)
                                : indicator.params[def.key] ?? 0}
                        </span>
                    </div>
                    <input
                        type="range"
                        min={def.min}
                        max={def.max}
                        step={def.step}
                        value={indicator.params[def.key] ?? 0}
                        onChange={(e) => {
                            const val = parseFloat(e.target.value);
                            onUpdate(indicator.id, {
                                params: { ...indicator.params, [def.key]: val },
                            });
                        }}
                        className="w-full h-1 mt-0.5 accent-[var(--accent-blue)]"
                    />
                </div>
            ))}
        </div>
    );
}

/* ─── Props ───────────────────────────────────────────────────────── */

interface Props {
    indicators: IndicatorConfig[];
    onToggle: (id: string) => void;
    onUpdate: (id: string, changes: Partial<IndicatorConfig>) => void;
}

/* ─── Component ───────────────────────────────────────────────────── */

export default function IndicatorToolbar({ indicators, onToggle, onUpdate }: Props) {
    const [expandedGroups, setExpandedGroups] = useState<Set<string>>(
        new Set(['ma', 'bands', 'momentum'])
    );
    const [openSettings, setOpenSettings] = useState<string | null>(null);

    const toggleGroup = useCallback((group: string) => {
        setExpandedGroups((prev) => {
            const next = new Set(prev);
            if (next.has(group)) next.delete(group);
            else next.add(group);
            return next;
        });
    }, []);

    const groupKeys = Object.keys(INDICATOR_GROUPS) as (keyof typeof INDICATOR_GROUPS)[];

    return (
        <div className="flex flex-col gap-1.5">
            {/* Group chips */}
            <div className="flex items-center gap-1 flex-wrap">
                {groupKeys.map((groupKey) => {
                    const groupInfo = INDICATOR_GROUPS[groupKey];
                    const GroupIcon = groupInfo.icon;
                    const groupInds = indicators.filter((i) => i.group === groupKey);
                    const activeInGroup = groupInds.filter((i) => i.active).length;
                    const isExpanded = expandedGroups.has(groupKey);

                    return (
                        <button
                            key={groupKey}
                            onClick={() => toggleGroup(groupKey)}
                            className={`flex items-center gap-1 px-2 py-1 rounded-md text-[10px] font-medium transition-all border ${
                                isExpanded
                                    ? 'border-[var(--accent-blue)]/30 bg-[var(--accent-blue)]/10 text-[var(--accent-blue)]'
                                    : 'border-transparent bg-[var(--bg-elevated)] text-[var(--text-muted)] hover:text-[var(--text-secondary)]'
                            }`}
                        >
                            <GroupIcon size={9} />
                            {groupInfo.label}
                            {activeInGroup > 0 && (
                                <span className="inline-flex items-center justify-center min-w-[14px] h-[14px] rounded-full bg-[var(--accent-blue)]/20 text-[var(--accent-blue)] text-[8px] font-bold">
                                    {activeInGroup}
                                </span>
                            )}
                            {isExpanded ? <ChevronDown size={8} /> : <ChevronRight size={8} />}
                        </button>
                    );
                })}
            </div>

            {/* Expanded indicator rows */}
            {groupKeys.map((groupKey) => {
                if (!expandedGroups.has(groupKey)) return null;
                const groupInds = indicators.filter((i) => i.group === groupKey);

                return (
                    <div
                        key={groupKey}
                        className="flex items-center gap-1 flex-wrap pl-1 py-0.5 border-l-2 border-[var(--border-color)] ml-1"
                    >
                        {groupInds.map((ind) => {
                            const Icon = ind.icon;
                            const isSettingsOpen = openSettings === ind.id;

                            return (
                                <div key={ind.id} className="relative">
                                    <div className="flex items-center">
                                        {/* Toggle button */}
                                        <button
                                            onClick={() => onToggle(ind.id)}
                                            title={ind.description}
                                            className={`flex items-center gap-1 pl-2 pr-1 py-1 rounded-l-md text-[10px] font-medium transition-all border border-r-0 ${
                                                ind.active
                                                    ? 'border-opacity-30 bg-opacity-15 text-white'
                                                    : 'border-transparent bg-[var(--bg-elevated)] text-[var(--text-muted)] hover:text-[var(--text-secondary)]'
                                            }`}
                                            style={
                                                ind.active
                                                    ? { borderColor: ind.color + '50', backgroundColor: ind.color + '20', color: ind.color }
                                                    : undefined
                                            }
                                        >
                                            <Icon size={9} />
                                            {ind.label}
                                        </button>

                                        {/* Gear button — same py-1 as toggle so heights match */}
                                        <button
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                setOpenSettings(isSettingsOpen ? null : ind.id);
                                            }}
                                            className={`flex items-center justify-center px-1 py-1 rounded-r-md border border-l-0 transition-all text-[10px] ${
                                                ind.active
                                                    ? 'border-opacity-30 bg-opacity-15'
                                                    : 'border-transparent bg-[var(--bg-elevated)]'
                                            } ${isSettingsOpen ? 'text-[var(--accent-blue)]' : 'text-[var(--text-muted)] hover:text-[var(--text-secondary)]'}`}
                                            style={
                                                ind.active
                                                    ? { borderColor: ind.color + '50', backgroundColor: ind.color + '20' }
                                                    : undefined
                                            }
                                        >
                                            <Settings size={8} />
                                        </button>
                                    </div>

                                    {/* Settings Popover */}
                                    {isSettingsOpen && (
                                        <IndicatorSettingsPopover
                                            indicator={ind}
                                            onUpdate={onUpdate}
                                            onClose={() => setOpenSettings(null)}
                                        />
                                    )}
                                </div>
                            );
                        })}
                    </div>
                );
            })}
        </div>
    );
}
