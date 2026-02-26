import { useState } from 'react';
import {
    Activity, TrendingUp, BarChart3, Layers, LineChart,
    ChevronDown, ChevronRight, Circle, Gauge, Waves, Target, Zap,
} from 'lucide-react';

export interface IndicatorConfig {
    id: string;
    label: string;
    icon: typeof Activity;
    active: boolean;
    color?: string;
    group: 'ma' | 'bands' | 'volume' | 'momentum' | 'volatility' | 'trend';
    description?: string;
}

export const INDICATOR_GROUPS = {
    ma: { label: 'Medie Mobili', icon: TrendingUp },
    bands: { label: 'Bande & Canali', icon: Layers },
    volume: { label: 'Volume', icon: BarChart3 },
    momentum: { label: 'Momentum', icon: Zap },
    volatility: { label: 'Volatilità', icon: Waves },
    trend: { label: 'Trend', icon: Target },
} as const;

export const DEFAULT_INDICATORS: IndicatorConfig[] = [
    // ── Medie Mobili ──
    { id: 'sma20', label: 'SMA 20', icon: TrendingUp, active: false, color: '#06b6d4', group: 'ma', description: 'Simple Moving Average 20' },
    { id: 'sma50', label: 'SMA 50', icon: TrendingUp, active: false, color: '#0ea5e9', group: 'ma', description: 'Simple Moving Average 50' },
    { id: 'sma200', label: 'SMA 200', icon: TrendingUp, active: false, color: '#0284c7', group: 'ma', description: 'Simple Moving Average 200' },
    { id: 'ema9', label: 'EMA 9', icon: TrendingUp, active: true, color: '#f59e0b', group: 'ma', description: 'Exponential Moving Average 9' },
    { id: 'ema21', label: 'EMA 21', icon: TrendingUp, active: true, color: '#3b82f6', group: 'ma', description: 'Exponential Moving Average 21' },
    { id: 'ema50', label: 'EMA 50', icon: TrendingUp, active: false, color: '#a855f7', group: 'ma', description: 'Exponential Moving Average 50' },
    { id: 'ema200', label: 'EMA 200', icon: TrendingUp, active: false, color: '#ef4444', group: 'ma', description: 'Exponential Moving Average 200' },

    // ── Bande & Canali ──
    { id: 'bb', label: 'Bollinger Bands', icon: Layers, active: true, color: '#6366f1', group: 'bands', description: 'Bollinger Bands (20, 2)' },
    { id: 'keltner', label: 'Keltner Channel', icon: Layers, active: false, color: '#ec4899', group: 'bands', description: 'Keltner Channel (20, 1.5 ATR)' },
    { id: 'ichimoku', label: 'Ichimoku Cloud', icon: Layers, active: false, color: '#f97316', group: 'bands', description: 'Ichimoku Kinko Hyo (9/26/52)' },

    // ── Volume ──
    { id: 'volume', label: 'Volume', icon: BarChart3, active: true, color: '#64748b', group: 'volume', description: 'Volume histogram' },
    { id: 'vwap', label: 'VWAP', icon: LineChart, active: false, color: '#14b8a6', group: 'volume', description: 'Volume Weighted Average Price' },
    { id: 'obv', label: 'OBV', icon: BarChart3, active: false, color: '#22d3ee', group: 'volume', description: 'On Balance Volume' },

    // ── Momentum ──
    { id: 'rsi', label: 'RSI 14', icon: Activity, active: true, color: '#f97316', group: 'momentum', description: 'Relative Strength Index (14)' },
    { id: 'macd', label: 'MACD', icon: Activity, active: false, color: '#8b5cf6', group: 'momentum', description: 'MACD (12, 26, 9)' },
    { id: 'stochastic', label: 'Stochastic', icon: Gauge, active: false, color: '#10b981', group: 'momentum', description: 'Stochastic Oscillator (14, 3)' },
    { id: 'cci', label: 'CCI 20', icon: Activity, active: false, color: '#eab308', group: 'momentum', description: 'Commodity Channel Index (20)' },
    { id: 'williamsR', label: 'Williams %R', icon: Activity, active: false, color: '#f43f5e', group: 'momentum', description: 'Williams Percent Range (14)' },

    // ── Volatilità ──
    { id: 'atr', label: 'ATR 14', icon: Waves, active: false, color: '#84cc16', group: 'volatility', description: 'Average True Range (14)' },

    // ── Trend ──
    { id: 'psar', label: 'Parabolic SAR', icon: Circle, active: false, color: '#fbbf24', group: 'trend', description: 'Parabolic Stop & Reverse' },
    { id: 'adx', label: 'ADX 14', icon: Target, active: false, color: '#2dd4bf', group: 'trend', description: 'Average Directional Index (14)' },
];

interface Props {
    indicators: IndicatorConfig[];
    onToggle: (id: string) => void;
}

export default function IndicatorToolbar({ indicators, onToggle }: Props) {
    const [expandedGroups, setExpandedGroups] = useState<Set<string>>(
        new Set(['ma', 'bands', 'momentum'])
    );

    const toggleGroup = (group: string) => {
        setExpandedGroups((prev) => {
            const next = new Set(prev);
            if (next.has(group)) next.delete(group);
            else next.add(group);
            return next;
        });
    };

    const groupKeys = Object.keys(INDICATOR_GROUPS) as (keyof typeof INDICATOR_GROUPS)[];

    return (
        <div className="flex flex-col gap-1.5">
            {/* Compact row of group chips */}
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
                        className="flex items-center gap-1 flex-wrap pl-1 py-0.5 border-l-2 border-[var(--border-color)] ml-1 animate-in fade-in duration-200"
                    >
                        {groupInds.map((ind) => {
                            const Icon = ind.icon;
                            return (
                                <button
                                    key={ind.id}
                                    onClick={() => onToggle(ind.id)}
                                    title={ind.description}
                                    className={`flex items-center gap-1 px-2 py-1 rounded-md text-[10px] font-medium transition-all border ${
                                        ind.active
                                            ? 'border-opacity-30 bg-opacity-15 text-white'
                                            : 'border-transparent bg-[var(--bg-elevated)] text-[var(--text-muted)] hover:text-[var(--text-secondary)]'
                                    }`}
                                    style={
                                        ind.active
                                            ? {
                                                borderColor: ind.color + '50',
                                                backgroundColor: ind.color + '20',
                                                color: ind.color,
                                            }
                                            : undefined
                                    }
                                >
                                    <Icon size={9} />
                                    {ind.label}
                                </button>
                            );
                        })}
                    </div>
                );
            })}
        </div>
    );
}
