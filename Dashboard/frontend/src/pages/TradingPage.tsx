import { useMemo } from 'react';
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

  // Compute risk metrics from real position data
  const riskMetrics = useMemo(() => {
    let totalExposure = 0;
    positions.forEach((pos) => {
      const qty = parseFloat(pos.quantity);
      const price = parseFloat(pos.current_price);
      if (!isNaN(qty) && !isNaN(price)) totalExposure += qty * price;
    });

    const equity = 100000 + dailyPnl;
    const marginUsed = equity > 0 ? (totalExposure / equity) * 100 : 0;
    const leverage = equity > 0 ? totalExposure / equity : 0;
    const maxDrawdown = Math.abs(Math.min(dailyPnl, 0) / 1000);

    return { exposure: totalExposure, leverage, marginUsed: Math.min(marginUsed, 100), maxDrawdown };
  }, [positions, dailyPnl]);

  // Total unrealized PnL from positions
  const totalUnrealizedPnl = useMemo(() =>
    positions.reduce((sum, pos) => {
      const pnl = parseFloat(pos.unrealized_pnl);
      return sum + (isNaN(pnl) ? 0 : pnl);
    }, 0),
    [positions]
  );

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
        {totalUnrealizedPnl !== 0 && (
          <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg ${
            totalUnrealizedPnl >= 0 ? 'bg-[var(--accent-green-dim)]' : 'bg-[var(--accent-red-dim)]'
          }`}>
            {totalUnrealizedPnl >= 0
              ? <TrendingUp size={14} className="text-[var(--accent-green)]" />
              : <TrendingDown size={14} className="text-[var(--accent-red)]" />
            }
            <span className={`text-sm font-bold ${
              totalUnrealizedPnl >= 0 ? 'text-[var(--accent-green)]' : 'text-[var(--accent-red)]'
            }`}>
              {totalUnrealizedPnl >= 0 ? '+' : ''}${totalUnrealizedPnl.toFixed(2)} unrealized
            </span>
          </div>
        )}
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
          textValue={activeStrategy}
        />
      </div>

      {/* Main Grid: Tables + Side Panels */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Left: Orders + Positions (2 cols) */}
        <div className="lg:col-span-2 space-y-4">
          {/* Active Orders */}
          <div className="glass-card overflow-hidden">
            <div className="flex items-center gap-2 px-5 py-3 border-b border-[var(--border-color)]">
              <ArrowUpDown size={16} className="text-[var(--accent-blue)]" />
              <h3 className="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider">Active Orders</h3>
              <span className="ml-auto text-xs text-[var(--text-muted)] font-mono tabular-nums">{orders.length}</span>
            </div>
            {orders.length === 0 ? (
              <div className="text-center py-10">
                <ArrowUpDown size={20} className="mx-auto text-[var(--text-muted)] mb-2 opacity-30" />
                <p className="text-xs text-[var(--text-muted)]">No active orders</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-[var(--text-muted)] text-[10px] uppercase tracking-wider bg-[var(--bg-elevated)]/30">
                      <th className="text-left py-2.5 px-5 font-medium">ID</th>
                      <th className="text-left py-2.5 px-3 font-medium">Symbol</th>
                      <th className="text-left py-2.5 px-3 font-medium">Side</th>
                      <th className="text-right py-2.5 px-3 font-medium">Price</th>
                      <th className="text-right py-2.5 px-5 font-medium">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {orders.map((order) => (
                      <tr key={order.id} className="border-t border-[var(--border-color)]/20 hover:bg-[var(--bg-card-hover)] transition-colors">
                        <td className="py-3 px-5 font-mono text-xs text-[var(--text-muted)]">{order.id}</td>
                        <td className="py-3 px-3 font-medium">{order.symbol}</td>
                        <td className="py-3 px-3">
                          <span className={`flex items-center gap-1 text-xs font-bold ${
                            order.side === 'BUY' ? 'text-[var(--accent-green)]' : 'text-[var(--accent-red)]'
                          }`}>
                            {order.side === 'BUY' ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
                            {order.side}
                          </span>
                        </td>
                        <td className="py-3 px-3 text-right font-mono text-xs tabular-nums">
                          ${parseFloat(String(order.price)).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                        </td>
                        <td className="py-3 px-5 text-right">
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
          <div className="glass-card overflow-hidden">
            <div className="flex items-center gap-2 px-5 py-3 border-b border-[var(--border-color)]">
              <Layers size={16} className="text-[var(--accent-green)]" />
              <h3 className="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider">Open Positions</h3>
              <span className="ml-auto text-xs text-[var(--text-muted)] font-mono tabular-nums">{positions.length}</span>
            </div>
            {positions.length === 0 ? (
              <div className="text-center py-10">
                <Layers size={20} className="mx-auto text-[var(--text-muted)] mb-2 opacity-30" />
                <p className="text-xs text-[var(--text-muted)]">No open positions</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-[var(--text-muted)] text-[10px] uppercase tracking-wider bg-[var(--bg-elevated)]/30">
                      <th className="text-left py-2.5 px-5 font-medium">Symbol</th>
                      <th className="text-left py-2.5 px-3 font-medium">Side</th>
                      <th className="text-right py-2.5 px-3 font-medium">Qty</th>
                      <th className="text-right py-2.5 px-3 font-medium">Avg Price</th>
                      <th className="text-right py-2.5 px-3 font-medium">Current</th>
                      <th className="text-right py-2.5 px-5 font-medium">PnL</th>
                    </tr>
                  </thead>
                  <tbody>
                    {positions.map((pos, i) => {
                      const pnl = parseFloat(pos.unrealized_pnl);
                      return (
                        <tr key={i} className="border-t border-[var(--border-color)]/20 hover:bg-[var(--bg-card-hover)] transition-colors">
                          <td className="py-3 px-5 font-medium">{pos.symbol}</td>
                          <td className="py-3 px-3">
                            <span className={`text-xs font-bold px-1.5 py-0.5 rounded ${
                              pos.side === 'LONG'
                                ? 'bg-[var(--accent-green-dim)] text-[var(--accent-green)]'
                                : 'bg-[var(--accent-red-dim)] text-[var(--accent-red)]'
                            }`}>
                              {pos.side}
                            </span>
                          </td>
                          <td className="py-3 px-3 text-right font-mono text-xs tabular-nums">{pos.quantity}</td>
                          <td className="py-3 px-3 text-right font-mono text-xs tabular-nums">${pos.avg_price}</td>
                          <td className="py-3 px-3 text-right font-mono text-xs tabular-nums">${pos.current_price}</td>
                          <td className={`py-3 px-5 text-right font-mono text-xs font-bold tabular-nums ${
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

        {/* Right Sidebar */}
        <div className="space-y-4">
          <RiskPanel
            exposure={riskMetrics.exposure}
            leverage={riskMetrics.leverage}
            marginUsed={riskMetrics.marginUsed}
            maxDrawdown={riskMetrics.maxDrawdown}
          />
          <SignalPanel />
          <KillSwitch />
          <TradeTimeline />
        </div>
      </div>
    </div>
  );
}
