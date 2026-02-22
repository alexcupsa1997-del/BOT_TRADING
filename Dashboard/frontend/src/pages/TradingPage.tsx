import { useTradingStore } from '../store/tradingStore';
import KPICard from '../components/common/KPICard';
import StatusBadge from '../components/common/StatusBadge';
import RiskPanel from '../components/trading/RiskPanel';
import SignalPanel from '../components/trading/SignalPanel';
import KillSwitch from '../components/trading/KillSwitch';
import TradeTimeline from '../components/trading/TradeTimeline';
import DrawdownChart from '../components/trading/DrawdownChart';
import {
  TrendingUp, TrendingDown, ArrowUpDown, Layers,
  Activity, Zap, DollarSign,
} from 'lucide-react';

export default function TradingPage() {
  const {
    dailyPnl, pnlPercent, activeStrategy,
    openPositions, tradesCount, orders, positions,
  } = useTradingStore();

  return (
    <div className="space-y-6 stagger-children">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Live Trading</h1>
          <p className="text-sm text-[var(--text-secondary)] mt-0.5">
            Strategy: <span className="font-medium text-[var(--text-primary)]">{activeStrategy}</span>
          </p>
        </div>
      </div>

      {/* KPI Row */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        <KPICard
          label="Daily PnL"
          value={dailyPnl}
          prefix="$"
          decimals={2}
          delta={pnlPercent}
          icon={<DollarSign size={16} />}
          colorize
          glowColor={dailyPnl >= 0 ? 'green' : 'red'}
        />
        <KPICard
          label="PnL %"
          value={pnlPercent}
          suffix="%"
          decimals={2}
          icon={<TrendingUp size={16} />}
          colorize
        />
        <KPICard
          label="Open Positions"
          value={openPositions}
          decimals={0}
          icon={<Layers size={16} />}
          glowColor="blue"
        />
        <KPICard
          label="Trades Today"
          value={tradesCount}
          decimals={0}
          icon={<Activity size={16} />}
        />
        <KPICard
          label="Strategy"
          value={0}
          decimals={0}
          icon={<Zap size={16} />}
        />
      </div>

      {/* Main Grid: Tables + Side Panels */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Left: Orders + Positions (2 cols) */}
        <div className="lg:col-span-2 space-y-4">
          {/* Active Orders */}
          <div className="glass-card p-5">
            <div className="flex items-center gap-2 mb-4">
              <ArrowUpDown size={16} className="text-[var(--accent-blue)]" />
              <h3 className="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider">Active Orders</h3>
              <span className="ml-auto text-xs text-[var(--text-muted)] font-mono">{orders.length}</span>
            </div>
            {orders.length === 0 ? (
              <p className="text-sm text-[var(--text-muted)] text-center py-8">No active orders</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-[var(--text-muted)] text-xs uppercase tracking-wider">
                      <th className="text-left py-2 font-medium">ID</th>
                      <th className="text-left py-2 font-medium">Symbol</th>
                      <th className="text-left py-2 font-medium">Side</th>
                      <th className="text-right py-2 font-medium">Price</th>
                      <th className="text-right py-2 font-medium">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {orders.map((order) => (
                      <tr key={order.id} className="border-t border-[var(--border-color)]/30 hover:bg-[var(--bg-card-hover)] transition-colors">
                        <td className="py-2.5 font-mono text-xs text-[var(--text-muted)]">{order.id}</td>
                        <td className="py-2.5 font-medium">{order.symbol}</td>
                        <td className="py-2.5">
                          <span className={`flex items-center gap-1 text-xs font-bold ${
                            order.side === 'BUY' ? 'text-[var(--accent-green)]' : 'text-[var(--accent-red)]'
                          }`}>
                            {order.side === 'BUY' ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
                            {order.side}
                          </span>
                        </td>
                        <td className="py-2.5 text-right font-mono text-xs">
                          ${parseFloat(String(order.price)).toFixed(2)}
                        </td>
                        <td className="py-2.5 text-right">
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
          <div className="glass-card p-5">
            <div className="flex items-center gap-2 mb-4">
              <Layers size={16} className="text-[var(--accent-green)]" />
              <h3 className="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider">Open Positions</h3>
              <span className="ml-auto text-xs text-[var(--text-muted)] font-mono">{positions.length}</span>
            </div>
            {positions.length === 0 ? (
              <p className="text-sm text-[var(--text-muted)] text-center py-8">No open positions</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-[var(--text-muted)] text-xs uppercase tracking-wider">
                      <th className="text-left py-2 font-medium">Symbol</th>
                      <th className="text-left py-2 font-medium">Side</th>
                      <th className="text-right py-2 font-medium">Qty</th>
                      <th className="text-right py-2 font-medium">Avg Price</th>
                      <th className="text-right py-2 font-medium">Current</th>
                      <th className="text-right py-2 font-medium">PnL</th>
                    </tr>
                  </thead>
                  <tbody>
                    {positions.map((pos, i) => {
                      const pnl = parseFloat(pos.unrealized_pnl);
                      return (
                        <tr key={i} className="border-t border-[var(--border-color)]/30 hover:bg-[var(--bg-card-hover)] transition-colors">
                          <td className="py-2.5 font-medium">{pos.symbol}</td>
                          <td className="py-2.5">
                            <span className={`text-xs font-bold ${
                              pos.side === 'LONG' ? 'text-[var(--accent-green)]' : 'text-[var(--accent-red)]'
                            }`}>
                              {pos.side}
                            </span>
                          </td>
                          <td className="py-2.5 text-right font-mono text-xs">{pos.quantity}</td>
                          <td className="py-2.5 text-right font-mono text-xs">${pos.avg_price}</td>
                          <td className="py-2.5 text-right font-mono text-xs">${pos.current_price}</td>
                          <td className={`py-2.5 text-right font-mono text-xs font-bold ${
                            pnl >= 0 ? 'text-[var(--accent-green)]' : 'text-[var(--accent-red)]'
                          }`}>
                            {pnl >= 0 ? '+' : ''}${pos.unrealized_pnl}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Drawdown Chart */}
          <DrawdownChart />
        </div>

        {/* Right Sidebar: Risk, Signals, Kill Switch, Timeline */}
        <div className="space-y-4">
          <RiskPanel
            exposure={dailyPnl * 10 + 5000}
            leverage={1.5}
            marginUsed={35}
            maxDrawdown={4.2}
          />
          <SignalPanel />
          <KillSwitch />
          <TradeTimeline />
        </div>
      </div>
    </div>
  );
}
