import { useState, useEffect } from 'react';
import { useSystemStore } from '../../store/systemStore';
import { useTradingStore } from '../../store/tradingStore';
import { useUIStore } from '../../store/uiStore';
import ThemeToggle from '../common/ThemeToggle';
import { Wifi, WifiOff, Search, Bell, Activity } from 'lucide-react';

function LiveClock() {
  const [time, setTime] = useState(new Date());
  useEffect(() => {
    const id = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(id);
  }, []);
  return (
    <span className="text-xs font-mono text-[var(--text-secondary)] tabular-nums">
      {time.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
      <span className="text-[var(--text-muted)] ml-1">UTC</span>
    </span>
  );
}

export default function Header() {
  const wsConnected = useSystemStore((s) => s.wsConnected);
  const status = useSystemStore((s) => s.status);
  const dailyPnl = useTradingStore((s) => s.dailyPnl);
  const pnlPercent = useTradingStore((s) => s.pnlPercent);
  const collapsed = useUIStore((s) => s.sidebarCollapsed);
  const setPaletteOpen = useUIStore((s) => s.setPaletteOpen);

  const sidebarWidth = collapsed ? '64px' : '220px';

  return (
    <header
      className="h-14 bg-[var(--bg-secondary)]/80 backdrop-blur-md border-b border-[var(--border-color)] flex items-center justify-between px-5 transition-all duration-300 fixed top-0 right-0 z-30"
      style={{ left: sidebarWidth }}
    >
      {/* Left: Search + Clock */}
      <div className="flex items-center gap-4">
        <button
          onClick={() => setPaletteOpen(true)}
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[var(--bg-elevated)] border border-[var(--border-color)] text-[var(--text-muted)] hover:text-[var(--text-secondary)] hover:border-[var(--accent-blue)]/30 transition-all text-xs"
        >
          <Search size={13} />
          <span>Search...</span>
          <kbd className="ml-3 text-[10px] bg-[var(--bg-card)] px-1.5 py-0.5 rounded border border-[var(--border-color)]">
            Ctrl+K
          </kbd>
        </button>
        <LiveClock />
      </div>

      {/* Center: Quick Metrics */}
      <div className="flex items-center gap-5">
        {status && (
          <>
            <div className="flex items-center gap-1.5">
              <Activity size={12} className="text-[var(--text-muted)]" />
              <span className="text-xs text-[var(--text-secondary)]">CPU</span>
              <span className={`text-xs font-medium tabular-nums ${
                status.cpu_percent > 80 ? 'text-[var(--accent-red)]'
                : status.cpu_percent > 50 ? 'text-[var(--accent-yellow)]'
                : 'text-[var(--text-primary)]'
              }`}>
                {status.cpu_percent.toFixed(0)}%
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="text-xs text-[var(--text-secondary)]">RAM</span>
              <span className={`text-xs font-medium tabular-nums ${
                status.ram_percent > 80 ? 'text-[var(--accent-red)]'
                : status.ram_percent > 60 ? 'text-[var(--accent-yellow)]'
                : 'text-[var(--text-primary)]'
              }`}>
                {status.ram_percent.toFixed(0)}%
              </span>
            </div>
          </>
        )}
        <div className="h-4 w-px bg-[var(--border-color)]" />
        <div className="flex items-center gap-1.5">
          <span className="text-xs text-[var(--text-secondary)]">PnL</span>
          <span className={`text-xs font-bold tabular-nums ${
            dailyPnl >= 0 ? 'text-[var(--accent-green)]' : 'text-[var(--accent-red)]'
          }`}>
            {dailyPnl >= 0 ? '+' : ''}${dailyPnl.toFixed(2)}
          </span>
          <span className={`text-[10px] tabular-nums ${
            pnlPercent >= 0 ? 'text-[var(--accent-green)]' : 'text-[var(--accent-red)]'
          }`}>
            ({pnlPercent >= 0 ? '+' : ''}{pnlPercent.toFixed(2)}%)
          </span>
        </div>
      </div>

      {/* Right: Actions */}
      <div className="flex items-center gap-2">
        {/* WS Status */}
        <div className={`flex items-center gap-1.5 px-2 py-1 rounded-md text-xs font-medium ${
          wsConnected
            ? 'text-[var(--accent-green)] bg-[var(--accent-green-dim)]'
            : 'text-[var(--accent-red)] bg-[var(--accent-red-dim)]'
        }`}>
          {wsConnected ? <Wifi size={12} /> : <WifiOff size={12} />}
          <span>{wsConnected ? 'Live' : 'Offline'}</span>
          {wsConnected && <div className="w-1.5 h-1.5 rounded-full bg-[var(--accent-green)] status-dot" />}
        </div>

        <div className="h-5 w-px bg-[var(--border-color)]" />

        {/* Notifications */}
        <button className="relative w-8 h-8 rounded-lg flex items-center justify-center text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-elevated)] transition-all">
          <Bell size={16} />
        </button>

        {/* Theme Toggle */}
        <ThemeToggle />

        {/* Account Badge */}
        <div className="w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold text-white flex-shrink-0"
             style={{ background: 'linear-gradient(135deg, var(--accent-blue), #6366f1)' }}>
          A
        </div>
      </div>
    </header>
  );
}
