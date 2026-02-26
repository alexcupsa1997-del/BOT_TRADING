import { useState, useEffect, useMemo } from 'react';
import { api } from '../../api/client';
import { useDemoTradingStore } from '../../store/demoTradingStore';
import { TrendingUp, TrendingDown, Target, Shield } from 'lucide-react';

const LOT_PRESETS = [0.01, 0.1, 0.5, 1.0, 5.0];
const RR_PRESETS = [
    { label: '1:1', value: 1 },
    { label: '1:2', value: 2 },
    { label: '1:3', value: 3 },
    { label: '1:4', value: 4 },
];

export default function TradePanel() {
    const { selectedSymbol, currentPrice, symbols } = useDemoTradingStore();

    const [direction, setDirection] = useState<'LONG' | 'SHORT'>('LONG');
    const [lotSize, setLotSize] = useState(0.1);
    const [rrRatio, setRrRatio] = useState(2);
    const [slPips, setSlPips] = useState(50);
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState('');
    const [success, setSuccess] = useState('');

    const pipSize = useMemo(() => {
        const sym = symbols.find((s) => s.id === selectedSymbol);
        return sym?.pipSize ?? 0.01;
    }, [symbols, selectedSymbol]);

    const sl = useMemo(() => {
        if (!currentPrice) return 0;
        const distance = slPips * pipSize;
        return direction === 'LONG' ? currentPrice - distance : currentPrice + distance;
    }, [currentPrice, slPips, pipSize, direction]);

    const tp = useMemo(() => {
        if (!currentPrice) return 0;
        const distance = slPips * pipSize * rrRatio;
        return direction === 'LONG' ? currentPrice + distance : currentPrice - distance;
    }, [currentPrice, slPips, pipSize, rrRatio, direction]);

    const riskAmount = useMemo(() => Math.abs(currentPrice - sl) * lotSize, [currentPrice, sl, lotSize]);
    const rewardAmount = useMemo(() => Math.abs(tp - currentPrice) * lotSize, [tp, currentPrice, lotSize]);

    useEffect(() => { setError(''); setSuccess(''); }, [selectedSymbol]);

    const handleSubmit = async () => {
        if (!currentPrice || currentPrice <= 0) { setError('Waiting for price...'); return; }
        setSubmitting(true); setError(''); setSuccess('');
        try {
            await api.post<{ data: unknown }>('/demo-trading/trade', {
                symbol: selectedSymbol, direction, entry_price: currentPrice,
                lot_size: lotSize, stop_loss: parseFloat(sl.toFixed(5)),
                take_profit: parseFloat(tp.toFixed(5)),
            });
            setSuccess(`${direction} @ ${currentPrice.toFixed(2)}`);
            const [posRes, accRes] = await Promise.all([
                api.get<{ data: unknown[] }>('/demo-trading/positions'),
                api.get<{ data: unknown }>('/demo-trading/account'),
            ]);
            useDemoTradingStore.getState().setPositions(posRes.data as any);
            useDemoTradingStore.getState().setAccount(accRes.data as any);
            setTimeout(() => setSuccess(''), 3000);
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Failed');
        } finally { setSubmitting(false); }
    };

    const fmt = (v: number) => v > 0 ? v.toFixed(pipSize < 0.01 ? 5 : 2) : '—';

    return (
        <div className="glass-card p-2.5 space-y-2">
            {/* Direction buttons */}
            <div className="grid grid-cols-2 gap-1.5">
                <button
                    onClick={() => setDirection('LONG')}
                    className={`flex items-center justify-center gap-1.5 py-2 rounded-lg font-bold text-xs transition-all ${
                        direction === 'LONG'
                            ? 'bg-[var(--accent-green)] text-white shadow-lg shadow-emerald-500/20'
                            : 'bg-[var(--bg-elevated)] text-[var(--text-muted)] hover:text-[var(--accent-green)]'
                    }`}
                >
                    <TrendingUp size={13} /> LONG
                </button>
                <button
                    onClick={() => setDirection('SHORT')}
                    className={`flex items-center justify-center gap-1.5 py-2 rounded-lg font-bold text-xs transition-all ${
                        direction === 'SHORT'
                            ? 'bg-[var(--accent-red)] text-white shadow-lg shadow-red-500/20'
                            : 'bg-[var(--bg-elevated)] text-[var(--text-muted)] hover:text-[var(--accent-red)]'
                    }`}
                >
                    <TrendingDown size={13} /> SHORT
                </button>
            </div>

            {/* Lot + R:R inline */}
            <div className="grid grid-cols-2 gap-1.5">
                <div>
                    <label className="text-[9px] uppercase tracking-wider text-[var(--text-muted)] font-medium">Lot</label>
                    <div className="flex gap-0.5 mt-0.5">
                        {LOT_PRESETS.map((l) => (
                            <button
                                key={l}
                                onClick={() => setLotSize(l)}
                                className={`flex-1 py-1 text-[10px] rounded transition-all ${
                                    lotSize === l
                                        ? 'bg-[var(--accent-blue)] text-white'
                                        : 'bg-[var(--bg-elevated)] text-[var(--text-muted)]'
                                }`}
                            >
                                {l}
                            </button>
                        ))}
                    </div>
                </div>
                <div>
                    <label className="text-[9px] uppercase tracking-wider text-[var(--text-muted)] font-medium">R:R</label>
                    <div className="flex gap-0.5 mt-0.5">
                        {RR_PRESETS.map((rr) => (
                            <button
                                key={rr.value}
                                onClick={() => setRrRatio(rr.value)}
                                className={`flex-1 py-1 text-[10px] rounded transition-all ${
                                    rrRatio === rr.value
                                        ? 'bg-[var(--accent-purple)] text-white'
                                        : 'bg-[var(--bg-elevated)] text-[var(--text-muted)]'
                                }`}
                            >
                                {rr.label}
                            </button>
                        ))}
                    </div>
                </div>
            </div>

            {/* SL slider compact */}
            <div>
                <div className="flex justify-between">
                    <label className="text-[9px] uppercase tracking-wider text-[var(--text-muted)] font-medium">SL Distance</label>
                    <span className="text-[10px] font-mono text-[var(--text-secondary)]">{slPips} pips</span>
                </div>
                <input
                    type="range" min={5} max={500} value={slPips}
                    onChange={(e) => setSlPips(parseInt(e.target.value))}
                    className="w-full h-1 mt-0.5 accent-[var(--accent-red)]"
                />
            </div>

            {/* SL/TP + Entry compact row */}
            <div className="grid grid-cols-3 gap-1 text-[10px]">
                <div className="bg-[var(--bg-elevated)] rounded-md p-1.5 border border-red-500/20">
                    <div className="flex items-center gap-0.5 text-[var(--accent-red)]">
                        <Shield size={8} /> SL
                    </div>
                    <div className="font-mono font-bold text-[var(--text-primary)] text-[11px]">{fmt(sl)}</div>
                    <div className="text-[var(--accent-red)] text-[9px]">-${riskAmount.toFixed(2)}</div>
                </div>
                <div className="bg-[var(--bg-elevated)] rounded-md p-1.5 text-center">
                    <div className="text-[var(--text-muted)]">Entry</div>
                    <div className="font-mono font-bold text-[var(--text-primary)] text-[11px]">
                        {currentPrice > 0 ? fmt(currentPrice) : '...'}
                    </div>
                </div>
                <div className="bg-[var(--bg-elevated)] rounded-md p-1.5 border border-emerald-500/20 text-right">
                    <div className="flex items-center justify-end gap-0.5 text-[var(--accent-green)]">
                        <Target size={8} /> TP
                    </div>
                    <div className="font-mono font-bold text-[var(--text-primary)] text-[11px]">{fmt(tp)}</div>
                    <div className="text-[var(--accent-green)] text-[9px]">+${rewardAmount.toFixed(2)}</div>
                </div>
            </div>

            {/* Messages */}
            {error && <div className="text-[10px] text-[var(--accent-red)] bg-red-500/10 rounded px-2 py-1">{error}</div>}
            {success && <div className="text-[10px] text-[var(--accent-green)] bg-emerald-500/10 rounded px-2 py-1">{success}</div>}

            {/* Execute */}
            <button
                onClick={handleSubmit}
                disabled={submitting || currentPrice <= 0}
                className={`w-full py-2 rounded-lg font-bold text-xs transition-all ${
                    direction === 'LONG'
                        ? 'bg-gradient-to-r from-emerald-600 to-emerald-500 hover:from-emerald-500 hover:to-emerald-400 text-white shadow-lg shadow-emerald-500/20'
                        : 'bg-gradient-to-r from-red-600 to-red-500 hover:from-red-500 hover:to-red-400 text-white shadow-lg shadow-red-500/20'
                } disabled:opacity-50 disabled:cursor-not-allowed`}
            >
                {submitting ? '...' : `Execute ${direction}`}
            </button>
        </div>
    );
}
