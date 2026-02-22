import { useEffect, useState } from 'react';
import { useSystemStore } from '../store/systemStore';
import { useTradingStore } from '../store/tradingStore';
import { api } from '../api/client';
import type { ApiResponse, ServiceHealth } from '../api/types';
import GaugeChart from '../components/common/GaugeChart';
import StatusBadge from '../components/common/StatusBadge';
import { AreaChart, Area, XAxis, YAxis, ResponsiveContainer, Tooltip } from 'recharts';
import {
  Activity,
  TrendingUp,
  Layers,
  Zap,
} from 'lucide-react';

export default function DashboardPage() {
  const status = useSystemStore((s) => s.status);
  const [services, setServices] = useState<ServiceHealth[]>([]);
  const dailyPnl = useTradingStore((s) => s.dailyPnl);
  const pnlPercent = useTradingStore((s) => s.pnlPercent);
  const activeStrategy = useTradingStore((s) => s.activeStrategy);
  const openPositions = useTradingStore((s) => s.openPositions);
  const tradesCount = useTradingStore((s) => s.tradesCount);

  useEffect(() => {
    api
      .get<ApiResponse<ServiceHealth[]>>('/system/services')
      .then((res) => setServices(res.data))
      .catch(() => {});
    const interval = setInterval(() => {
      api
        .get<ApiResponse<ServiceHealth[]>>('/system/services')
        .then((res) => setServices(res.data))
        .catch(() => {});
    }, 10000);
    return () => clearInterval(interval);
  }, []);

  const latencyData = (status?.redis_latency_history || []).map(([t, v]) => ({
    time: new Date(t * 1000).toLocaleTimeString(),
    latency: v,
  }));

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Dashboard Overview</h1>

      {/* Gauges Row */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-[var(--bg-card)] rounded-xl p-5 border border-[var(--border-color)]">
          <GaugeChart value={status?.cpu_percent || 0} label="CPU Usage" color="var(--accent-blue)" />
        </div>
        <div className="bg-[var(--bg-card)] rounded-xl p-5 border border-[var(--border-color)]">
          <GaugeChart value={status?.ram_percent || 0} label="RAM Usage" color="var(--accent-purple)" />
        </div>
        <div className="bg-[var(--bg-card)] rounded-xl p-5 border border-[var(--border-color)]">
          <GaugeChart value={status?.disk_usage || 0} label="Disk Usage" color="var(--accent-yellow)" />
        </div>
      </div>

      {/* KPI Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-[var(--bg-card)] rounded-xl p-4 border border-[var(--border-color)]">
          <div className="flex items-center gap-2 text-[var(--text-secondary)] text-sm mb-2">
            <TrendingUp size={16} />
            Daily PnL
          </div>
          <div className={`text-2xl font-bold ${dailyPnl >= 0 ? 'text-[var(--accent-green)]' : 'text-[var(--accent-red)]'}`}>
            ${dailyPnl.toFixed(2)}
          </div>
          <div className={`text-sm ${pnlPercent >= 0 ? 'text-[var(--accent-green)]' : 'text-[var(--accent-red)]'}`}>
            {pnlPercent >= 0 ? '+' : ''}{pnlPercent.toFixed(2)}%
          </div>
        </div>

        <div className="bg-[var(--bg-card)] rounded-xl p-4 border border-[var(--border-color)]">
          <div className="flex items-center gap-2 text-[var(--text-secondary)] text-sm mb-2">
            <Layers size={16} />
            Open Positions
          </div>
          <div className="text-2xl font-bold">{openPositions}</div>
        </div>

        <div className="bg-[var(--bg-card)] rounded-xl p-4 border border-[var(--border-color)]">
          <div className="flex items-center gap-2 text-[var(--text-secondary)] text-sm mb-2">
            <Activity size={16} />
            Trades Today
          </div>
          <div className="text-2xl font-bold">{tradesCount}</div>
        </div>

        <div className="bg-[var(--bg-card)] rounded-xl p-4 border border-[var(--border-color)]">
          <div className="flex items-center gap-2 text-[var(--text-secondary)] text-sm mb-2">
            <Zap size={16} />
            Strategy
          </div>
          <div className="text-lg font-bold truncate">{activeStrategy}</div>
        </div>
      </div>

      {/* Services + Latency Row */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Service Status */}
        <div className="bg-[var(--bg-card)] rounded-xl p-5 border border-[var(--border-color)]">
          <h3 className="text-sm font-semibold text-[var(--text-secondary)] mb-4">Services Health</h3>
          <div className="space-y-3">
            {services.length === 0 && (
              <p className="text-sm text-[var(--text-secondary)]">Loading services...</p>
            )}
            {services.map((svc) => (
              <div key={svc.name} className="flex items-center justify-between">
                <span className="text-sm font-medium capitalize">{svc.name}</span>
                <div className="flex items-center gap-3">
                  {svc.latency_ms != null && (
                    <span className="text-xs text-[var(--text-secondary)]">{svc.latency_ms.toFixed(1)}ms</span>
                  )}
                  <StatusBadge status={svc.status} />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Redis Latency Chart */}
        <div className="bg-[var(--bg-card)] rounded-xl p-5 border border-[var(--border-color)]">
          <h3 className="text-sm font-semibold text-[var(--text-secondary)] mb-4">Redis Latency (ms)</h3>
          {latencyData.length > 0 ? (
            <ResponsiveContainer width="100%" height={160}>
              <AreaChart data={latencyData}>
                <defs>
                  <linearGradient id="latencyGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="var(--accent-blue)" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="var(--accent-blue)" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="time" tick={{ fontSize: 10, fill: 'var(--text-secondary)' }} />
                <YAxis tick={{ fontSize: 10, fill: 'var(--text-secondary)' }} />
                <Tooltip
                  contentStyle={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '8px' }}
                  labelStyle={{ color: 'var(--text-secondary)' }}
                />
                <Area type="monotone" dataKey="latency" stroke="var(--accent-blue)" fill="url(#latencyGrad)" />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-sm text-[var(--text-secondary)]">No latency data</p>
          )}
        </div>
      </div>

      {/* System Info */}
      <div className="bg-[var(--bg-card)] rounded-xl p-5 border border-[var(--border-color)]">
        <h3 className="text-sm font-semibold text-[var(--text-secondary)] mb-3">System Info</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          <div>
            <span className="text-[var(--text-secondary)]">RAM: </span>
            <span>{status?.ram_mb || 0} MB</span>
          </div>
          <div>
            <span className="text-[var(--text-secondary)]">Uptime: </span>
            <span>{Math.floor((status?.uptime_seconds || 0) / 3600)}h {Math.floor(((status?.uptime_seconds || 0) % 3600) / 60)}m</span>
          </div>
          <div>
            <span className="text-[var(--text-secondary)]">PG Connections: </span>
            <span>{status?.pg_connections || 0}/{status?.pg_max_connections || 100}</span>
          </div>
          <div>
            <span className="text-[var(--text-secondary)]">Redis Latency: </span>
            <span>{status?.redis_latency_ms?.toFixed(1) || 'N/A'} ms</span>
          </div>
        </div>
      </div>
    </div>
  );
}
