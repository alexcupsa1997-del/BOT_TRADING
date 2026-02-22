import { TrendingUp, TrendingDown } from 'lucide-react';

interface Trade {
  id: string;
  symbol: string;
  side: 'BUY' | 'SELL';
  price: string;
  quantity: string;
  pnl: string;
  time: string;
}

interface TradeTimelineProps {
  trades?: Trade[];
}

const sampleTrades: Trade[] = [
  { id: '1', symbol: 'XAUUSD', side: 'BUY', price: '2645.30', quantity: '0.5', pnl: '+12.50', time: '14:32' },
  { id: '2', symbol: 'BTCUSD', side: 'SELL', price: '67420.00', quantity: '0.02', pnl: '-8.20', time: '13:15' },
  { id: '3', symbol: 'EURUSD', side: 'BUY', price: '1.0842', quantity: '10000', pnl: '+5.60', time: '11:48' },
  { id: '4', symbol: 'XAUUSD', side: 'SELL', price: '2638.10', quantity: '0.3', pnl: '+22.30', time: '10:22' },
  { id: '5', symbol: 'BTCUSD', side: 'BUY', price: '67180.00', quantity: '0.01', pnl: '-3.10', time: '09:05' },
];

export default function TradeTimeline({ trades }: TradeTimelineProps) {
  const data = trades || sampleTrades;

  return (
    <div className="glass-card p-5">
      <h3 className="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-4">Recent Trades</h3>
      <div className="space-y-0">
        {data.map((trade, idx) => {
          const pnlNum = parseFloat(trade.pnl);
          const isProfit = pnlNum >= 0;
          return (
            <div
              key={trade.id}
              className="relative flex items-center gap-3 py-3 border-b border-[var(--border-color)]/50 last:border-0"
            >
              {/* Timeline dot */}
              <div className="relative flex-shrink-0">
                <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
                  trade.side === 'BUY' ? 'bg-[var(--accent-green-dim)]' : 'bg-[var(--accent-red-dim)]'
                }`}>
                  {trade.side === 'BUY'
                    ? <TrendingUp size={14} className="text-[var(--accent-green)]" />
                    : <TrendingDown size={14} className="text-[var(--accent-red)]" />
                  }
                </div>
                {/* Connector line */}
                {idx < data.length - 1 && (
                  <div className="absolute top-8 left-1/2 -translate-x-1/2 w-px h-3 bg-[var(--border-color)]" />
                )}
              </div>

              {/* Details */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-sm">{trade.symbol}</span>
                  <span className={`text-[10px] font-bold ${
                    trade.side === 'BUY' ? 'text-[var(--accent-green)]' : 'text-[var(--accent-red)]'
                  }`}>
                    {trade.side}
                  </span>
                </div>
                <div className="text-[10px] text-[var(--text-muted)]">
                  {trade.quantity} @ ${trade.price}
                </div>
              </div>

              {/* PnL + Time */}
              <div className="text-right flex-shrink-0">
                <div className={`text-sm font-bold font-mono ${
                  isProfit ? 'text-[var(--accent-green)]' : 'text-[var(--accent-red)]'
                }`}>
                  {isProfit ? '+' : ''}${trade.pnl}
                </div>
                <div className="text-[10px] text-[var(--text-muted)]">{trade.time}</div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
