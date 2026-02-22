import { useEffect, useState } from 'react';
import { useSystemStore } from '../store/systemStore';
import { useTradingStore } from '../store/tradingStore';
import { api } from '../api/client';
import type { ApiResponse, ServiceHealth } from '../api/types';
import KPICard from '../components/common/KPICard';
import GaugeChart from '../components/common/GaugeChart';
import StatusBadge from '../components/common/StatusBadge';
import EquityCurveChart from '../components/dashboard/EquityCurveChart';
import PerformanceHeatmap from '../components/dashboard/PerformanceHeatmap';
import PnLDistribution from '../components/dashboard/PnLDistribution';
import WinRateDonut from '../components/dashboard/WinRateDonut';
import { AreaChart, Area, XAxis, YAxis, ResponsiveContainer, Tooltip } from 'recharts';
import {
  TrendingUp, Layers, Activity, Zap, Clock, Server,
} from 'lucide-react';

export default function DashboardPage() {
  const status = useSystemStore((s) => s.status);
  const [services, setServices] = useState<ServiceHealth[]>([]);
  const dailyPnl = useTradingStore((s) => s.dailyPnl);
  const pnlPercent = useTradingStore((s) => s.pnlPercent);
  const activeStrategy = useTradingStore((s) => s.activeStrategy);
  const openPositions = useTradingStore((s) => s.openPositions);
  const tradesCount = useTradingStore((s) => s.tradesCount);
  const equityCurve = useTradingStore((s) => s.equityCurve);

  useEffect(() => {
    const fetchServices = () => {
      api.get<ApiResponse<ServiceHealth[]>>('/system/services')
        .then((res) => setServices(res.data))
        .catch(() => {});
    };
    fetchServices();
    const interval = setInterval(fetchServices, 10000);
    return () => clearInterval(interval);
  }, []);

  const latencyData = (status?.redis_latency_history || []).map(([t, v]) => ({
    time: new Date(t * 1000).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' }),
    latency: v,
  }));

  // Transform equity curve for lightweight-charts
  const equityChartData = equityCurve.map((point) => ({
    time: point.timestamp || '',
    value: parseFloat(point.total_equity || '0'),
  })).filter((p) => p.time && !isNaN(p.value));

  const uptimeHours = Math.floor((status?.uptime_seconds || 0) / 3600);
  const uptimeMinutes = Math.floor(((status?.uptime_seconds || 0) % 3600) / 60);

  return (
    <div className="space-y-6 stagger-children">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Dashboard Overview</h1>
          <p className="text-sm text-[var(--text-secondary)] mt-0.5">Real-time trading system monitoring</p>
        </div>
        <div className="flex items-center gap-2 text-xs text-[var(--text-muted)]">
          <Clock size={13} />
          <span>Uptime: {uptimeHours}h {uptimeMinutes}m</span>
        </div>
      </div>

      {/* KPI Row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KPICard
          label="Daily PnL"
          value={dailyPnl}
          prefix="$"
          decimals={2}
          delta={pnlPercent}
          icon={<TrendingUp size={16} />}
          colorize
          glowColor={dailyPnl >= 0 ? 'green' : 'red'}
          delay={0}
          sparkline={Array.from({ length: 12 }, () => dailyPnl + Math.random() * 40 - 20)}
        />
        <KPICard
          label="Open Positions"
          value={openPositions}
          decimals={0}
          suffix=""
          icon={<Layers size={16} />}
          glowColor="blue"
          delay={50}
        />
        <KPICard
          label="Trades Today"
          value={tradesCount}
          decimals={0}
          suffix=""
          icon={<Activity size={16} />}
          delay={100}
          sparkline={Array.from({ length: 12 }, (_, i) => Math.max(0, tradesCount - 12 + i + Math.floor(Math.random() * 3)))}
        />
        <KPICard
          label="Strategy"
          value={0}
          decimals={0}
          icon={<Zap size={16} />}
          delay={150}
          textValue={activeStrategy}
        />
      </div>

      {/* Gauges + Equity Curve */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* System Gauges */}
        <div className="glass-card p-5">
          <h3 className="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-4">System Resources</h3>
          <div className="grid grid-cols-3 gap-2">
            <GaugeChart value={status?.cpu_percent || 0} label="CPU" color="#3b82f6" />
            <GaugeChart value={status?.ram_percent || 0} label="RAM" color="#8b5cf6" />
            <GaugeChart value={status?.disk_usage || 0} label="Disk" color="#eab308" />
          </div>
          <div className="grid grid-cols-2 gap-3 mt-4 pt-3 border-t border-[var(--border-color)]">
            <div className="text-xs">
              <span className="text-[var(--text-muted)]">RAM </span>
              <span className="font-medium">{status?.ram_mb || 0} MB</span>
            </div>
            <div className="text-xs">
              <span className="text-[var(--text-muted)]">PG Conn </span>
              <span className="font-medium">{status?.pg_connections || 0}/{status?.pg_max_connections || 100}</span>
            </div>
          </div>
        </div>

        {/* Equity Curve */}
        <div className="glass-card p-5 lg:col-span-2">
          <h3 className="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-3">Equity Curve</h3>
          {equityChartData.length > 0 ? (
            <EquityCurveChart data={equityChartData} />
          ) : (
            <div className="flex items-center justify-center h-[260px] text-sm text-[var(--text-muted)]">
              No equity data available
            </div>
          )}
        </div>
      </div>

      {/* Services + Latency */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Service Status */}
        <div className="glass-card p-5">
          <div className="flex items-center gap-2 mb-4">
            <Server size={14} className="text-[var(--text-muted)]" />
            <h3 className="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider">Services Health</h3>
          </div>
          <div className="space-y-2.5">
            {services.length === 0 && (
              <p className="text-sm text-[var(--text-muted)]">Loading services...</p>
            )}
            {services.map((svc) => (
              <div key={svc.name} className="flex items-center justify-between py-1.5 border-b border-[var(--border-color)] last:border-0">
                <span className="text-sm font-medium capitalize">{svc.name}</span>
                <div className="flex items-center gap-3">
                  {svc.latency_ms != null && (
                    <span className="text-xs text-[var(--text-muted)] font-mono tabular-nums">
                      {svc.latency_ms.toFixed(1)}ms
                    </span>
                  )}
                  <StatusBadge status={svc.status} />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Redis Latency Chart */}
        <div className="glass-card p-5">
          <h3 className="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-3">Redis Latency</h3>
          {latencyData.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <AreaChart data={latencyData}>
                <defs>
                  <linearGradient id="latencyGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="var(--accent-blue)" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="var(--accent-blue)" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis
                  dataKey="time"
                  tick={{ fontSize: 10, fill: 'var(--text-muted)' }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fontSize: 10, fill: 'var(--text-muted)' }}
                  axisLine={false}
                  tickLine={false}
                  width={35}
                />
                <Tooltip
                  contentStyle={{
                    background: 'var(--bg-secondary)',
                    border: '1px solid var(--border-color)',
                    borderRadius: '8px',
                    fontSize: '12px',
                  }}
                  labelStyle={{ color: 'var(--text-secondary)' }}
                />
                <Area
                  type="monotone"
                  dataKey="latency"
                  stroke="var(--accent-blue)"
                  strokeWidth={2}
                  fill="url(#latencyGrad)"
                />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex items-center justify-center h-[200px] text-sm text-[var(--text-muted)]">
              No latency data
            </div>
          )}
        </div>
      </div>

      {/* Analytics Row: Heatmap + Distribution + Win Rate */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Performance Heatmap */}
        <div className="glass-card p-5">
          <h3 className="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-3">Performance Heatmap</h3>
          <PerformanceHeatmap />
        </div>

        {/* PnL Distribution */}
        <div className="glass-card p-5">
          <h3 className="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-3">PnL Distribution</h3>
          <PnLDistribution />
        </div>

        {/* Win Rate + Profit Factor */}
        <div className="glass-card p-5">
          <h3 className="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-4">Performance Metrics</h3>
          <div className="flex items-center justify-around">
            <WinRateDonut winRate={62} label="Win Rate" />
            <WinRateDonut winRate={71} label="Profit Factor" />
          </div>
          <div className="grid grid-cols-2 gap-3 mt-4 pt-3 border-t border-[var(--border-color)]">
            <div className="text-center">
              <div className="text-lg font-bold text-[var(--accent-green)]">1.85</div>
              <div className="text-[10px] text-[var(--text-muted)] uppercase">Profit Factor</div>
            </div>
            <div className="text-center">
              <div className="text-lg font-bold text-[var(--accent-blue)]">1.42</div>
              <div className="text-[10px] text-[var(--text-muted)] uppercase">Sharpe Ratio</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
