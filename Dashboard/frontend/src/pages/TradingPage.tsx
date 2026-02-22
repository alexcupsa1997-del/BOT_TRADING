import { useTradingStore } from '../store/tradingStore';
import StatusBadge from '../components/common/StatusBadge';
import { TrendingUp, TrendingDown, ArrowUpDown } from 'lucide-react';

export default function TradingPage() {
  const {
    dailyPnl,
    pnlPercent,
    activeStrategy,
    openPositions,
    tradesCount,
    orders,
    positions,
  } = useTradingStore();

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Live Trading</h1>

      {/* PnL Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <div className="bg-[var(--bg-card)] rounded-xl p-4 border border-[var(--border-color)]">
          <div className="text-sm text-[var(--text-secondary)] mb-1">Daily PnL</div>
          <div className={`text-2xl font-bold ${dailyPnl >= 0 ? 'text-[var(--accent-green)]' : 'text-[var(--accent-red)]'}`}>
            ${dailyPnl.toFixed(2)}
          </div>
        </div>
        <div className="bg-[var(--bg-card)] rounded-xl p-4 border border-[var(--border-color)]">
          <div className="text-sm text-[var(--text-secondary)] mb-1">PnL %</div>
          <div className={`text-2xl font-bold ${pnlPercent >= 0 ? 'text-[var(--accent-green)]' : 'text-[var(--accent-red)]'}`}>
            {pnlPercent >= 0 ? '+' : ''}{pnlPercent.toFixed(2)}%
          </div>
        </div>
        <div className="bg-[var(--bg-card)] rounded-xl p-4 border border-[var(--border-color)]">
          <div className="text-sm text-[var(--text-secondary)] mb-1">Strategy</div>
          <div className="text-lg font-bold truncate">{activeStrategy}</div>
        </div>
        <div className="bg-[var(--bg-card)] rounded-xl p-4 border border-[var(--border-color)]">
          <div className="text-sm text-[var(--text-secondary)] mb-1">Open Positions</div>
          <div className="text-2xl font-bold">{openPositions}</div>
        </div>
        <div className="bg-[var(--bg-card)] rounded-xl p-4 border border-[var(--border-color)]">
          <div className="text-sm text-[var(--text-secondary)] mb-1">Trades Today</div>
          <div className="text-2xl font-bold">{tradesCount}</div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Active Orders */}
        <div className="bg-[var(--bg-card)] rounded-xl p-5 border border-[var(--border-color)]">
          <div className="flex items-center gap-2 mb-4">
            <ArrowUpDown size={18} className="text-[var(--accent-blue)]" />
            <h3 className="text-sm font-semibold text-[var(--text-secondary)]">Active Orders</h3>
            <span className="ml-auto text-xs text-[var(--text-secondary)]">{orders.length} orders</span>
          </div>
          {orders.length === 0 ? (
            <p className="text-sm text-[var(--text-secondary)] text-center py-8">No active orders</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-[var(--text-secondary)] border-b border-[var(--border-color)]">
                    <th className="text-left py-2 font-medium">ID</th>
                    <th className="text-left py-2 font-medium">Symbol</th>
                    <th className="text-left py-2 font-medium">Side</th>
                    <th className="text-right py-2 font-medium">Price</th>
                    <th className="text-right py-2 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {orders.map((order) => (
                    <tr key={order.id} className="border-b border-[var(--border-color)]/50">
                      <td className="py-2 font-mono text-xs">{order.id}</td>
                      <td className="py-2">{order.symbol}</td>
                      <td className="py-2">
                        <span className={`flex items-center gap-1 ${order.side === 'BUY' ? 'text-[var(--accent-green)]' : 'text-[var(--accent-red)]'}`}>
                          {order.side === 'BUY' ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
                          {order.side}
                        </span>
                      </td>
                      <td className="py-2 text-right font-mono">
                        ${parseFloat(String(order.price)).toFixed(2)}
                      </td>
                      <td className="py-2 text-right">
                        <StatusBadge status={order.status.toLowerCase() === 'open' ? 'ok' : 'error'} label={order.status} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Open Positions */}
        <div className="bg-[var(--bg-card)] rounded-xl p-5 border border-[var(--border-color)]">
          <div className="flex items-center gap-2 mb-4">
            <TrendingUp size={18} className="text-[var(--accent-green)]" />
            <h3 className="text-sm font-semibold text-[var(--text-secondary)]">Open Positions</h3>
            <span className="ml-auto text-xs text-[var(--text-secondary)]">{positions.length} positions</span>
          </div>
          {positions.length === 0 ? (
            <p className="text-sm text-[var(--text-secondary)] text-center py-8">No open positions</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-[var(--text-secondary)] border-b border-[var(--border-color)]">
                    <th className="text-left py-2 font-medium">Symbol</th>
                    <th className="text-left py-2 font-medium">Side</th>
                    <th className="text-right py-2 font-medium">Qty</th>
                    <th className="text-right py-2 font-medium">Avg Price</th>
                    <th className="text-right py-2 font-medium">PnL</th>
                  </tr>
                </thead>
                <tbody>
                  {positions.map((pos, i) => (
                    <tr key={i} className="border-b border-[var(--border-color)]/50">
                      <td className="py-2 font-medium">{pos.symbol}</td>
                      <td className={`py-2 ${pos.side === 'LONG' ? 'text-[var(--accent-green)]' : 'text-[var(--accent-red)]'}`}>
                        {pos.side}
                      </td>
                      <td className="py-2 text-right font-mono">{pos.quantity}</td>
                      <td className="py-2 text-right font-mono">${pos.avg_price}</td>
                      <td className={`py-2 text-right font-mono ${parseFloat(pos.unrealized_pnl) >= 0 ? 'text-[var(--accent-green)]' : 'text-[var(--accent-red)]'}`}>
                        ${pos.unrealized_pnl}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
