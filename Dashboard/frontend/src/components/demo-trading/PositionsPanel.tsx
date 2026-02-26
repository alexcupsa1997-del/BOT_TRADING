import { useDemoTradingStore, type DemoPosition } from '../../store/demoTradingStore';
import { api } from '../../api/client';
import { TrendingUp, TrendingDown, X } from 'lucide-react';

export default function PositionsPanel() {
    const { positions, setPositions, setAccount, setHistory } = useDemoTradingStore();

    const handleClose = async (tradeId: string) => {
        try {
            await api.post('/demo-trading/close-trade', { trade_id: tradeId });
            const [posRes, accRes, histRes] = await Promise.all([
                api.get<{ data: DemoPosition[] }>('/demo-trading/positions'),
                api.get<{ data: any }>('/demo-trading/account'),
                api.get<{ data: any[] }>('/demo-trading/history'),
            ]);
            setPositions(posRes.data);
            setAccount(accRes.data);
            setHistory(histRes.data);
        } catch (e) {
            console.error('Failed to close trade:', e);
        }
    };

    return (
        <div className="glass-card p-2.5">
            <div className="flex items-center justify-between mb-1.5">
                <h3 className="text-[10px] font-semibold text-[var(--text-primary)] uppercase tracking-wider">
                    Positions
                </h3>
                <span className="text-[10px] text-[var(--text-muted)] font-mono">{positions.length}</span>
            </div>

            {positions.length === 0 ? (
                <div className="text-center py-3 text-[10px] text-[var(--text-muted)]">
                    No open positions
                </div>
            ) : (
                <div className="space-y-1.5 max-h-[280px] overflow-y-auto">
                    {positions.map((pos) => {
                        const pnl = parseFloat(pos.unrealized_pnl);
                        const isProfit = pnl >= 0;
                        const current = parseFloat(pos.current_price);
                        const sl = parseFloat(pos.stop_loss);
                        const tp = parseFloat(pos.take_profit);
                        const range = Math.abs(tp - sl);
                        const progress = range > 0 ? Math.abs(current - sl) / range : 0.5;

                        return (
                            <div
                                key={pos.id}
                                className={`bg-[var(--bg-elevated)] rounded-md p-2 border-l-2 ${isProfit ? 'border-l-emerald-500' : 'border-l-red-500'}`}
                            >
                                <div className="flex items-center justify-between mb-1">
                                    <div className="flex items-center gap-1">
                                        {pos.direction === 'LONG'
                                            ? <TrendingUp size={10} className="text-[var(--accent-green)]" />
                                            : <TrendingDown size={10} className="text-[var(--accent-red)]" />
                                        }
                                        <span className="text-[10px] font-bold">{pos.symbol}</span>
                                        <span className={`text-[8px] font-medium px-1 py-0.5 rounded ${
                                            pos.direction === 'LONG'
                                                ? 'bg-emerald-500/15 text-[var(--accent-green)]'
                                                : 'bg-red-500/15 text-[var(--accent-red)]'
                                        }`}>
                                            {pos.direction}
                                        </span>
                                        <span className="text-[8px] text-[var(--text-muted)]">{pos.lot_size}</span>
                                    </div>
                                    <div className="flex items-center gap-1.5">
                                        <span className={`text-[10px] font-mono font-bold ${isProfit ? 'text-[var(--accent-green)]' : 'text-[var(--accent-red)]'}`}>
                                            {isProfit ? '+' : ''}{pnl.toFixed(2)}
                                        </span>
                                        <button
                                            onClick={() => handleClose(pos.id)}
                                            className="w-4 h-4 rounded flex items-center justify-center text-[var(--text-muted)] hover:text-[var(--accent-red)] hover:bg-red-500/10 transition-all"
                                            title="Close"
                                        >
                                            <X size={10} />
                                        </button>
                                    </div>
                                </div>

                                {/* Compact SL/TP progress */}
                                <div className="flex justify-between text-[8px] text-[var(--text-muted)] mb-0.5">
                                    <span>SL {sl.toFixed(2)}</span>
                                    <span className="font-mono">{current.toFixed(2)}</span>
                                    <span>TP {tp.toFixed(2)}</span>
                                </div>
                                <div className="w-full h-1 rounded-full bg-[var(--bg-primary)] overflow-hidden">
                                    <div
                                        className={`h-full rounded-full transition-all duration-300 ${
                                            isProfit
                                                ? 'bg-gradient-to-r from-yellow-500 to-emerald-500'
                                                : 'bg-gradient-to-r from-red-500 to-yellow-500'
                                        }`}
                                        style={{ width: `${Math.min(100, Math.max(0, progress * 100))}%` }}
                                    />
                                </div>
                            </div>
                        );
                    })}
                </div>
            )}
        </div>
    );
}
