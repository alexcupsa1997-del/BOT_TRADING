import { useState, useEffect, useRef } from 'react';
import { useSystemStore } from '../../store/systemStore';
import { useTradingStore } from '../../store/tradingStore';
import { useUIStore } from '../../store/uiStore';
import type { Notification } from '../../store/uiStore';
import ThemeToggle from '../common/ThemeToggle';
import {
  Wifi, WifiOff, Search, Bell, Activity,
  CheckCheck, Trash2, AlertTriangle, Info, CheckCircle2, XCircle,
} from 'lucide-react';

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

const notifIcons: Record<Notification['type'], typeof Info> = {
  info: Info,
  success: CheckCircle2,
  warning: AlertTriangle,
  error: XCircle,
};

const notifColors: Record<Notification['type'], string> = {
  info: 'text-[var(--accent-blue)]',
  success: 'text-[var(--accent-green)]',
  warning: 'text-[var(--accent-yellow)]',
  error: 'text-[var(--accent-red)]',
};

function timeAgo(ts: number): string {
  const diff = Math.floor((Date.now() - ts) / 1000);
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  return `${Math.floor(diff / 3600)}h ago`;
}

function NotificationPanel({ onClose }: { onClose: () => void }) {
  const notifications = useUIStore((s) => s.notifications);
  const unreadCount = useUIStore((s) => s.unreadCount);
  const markAllRead = useUIStore((s) => s.markAllRead);
  const clearNotifications = useUIStore((s) => s.clearNotifications);
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        onClose();
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [onClose]);

  return (
    <div
      ref={panelRef}
      className="absolute right-0 top-full mt-2 w-80 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl shadow-2xl overflow-hidden animate-fade-in-up z-50"
      style={{ animationDuration: '0.15s' }}
    >
      <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--border-color)]">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-[var(--text-primary)]">Notifications</span>
          {unreadCount > 0 && (
            <span className="text-[10px] bg-[var(--accent-blue)] text-white px-1.5 py-0.5 rounded-full font-medium">
              {unreadCount}
            </span>
          )}
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={markAllRead}
            className="p-1.5 rounded-md text-[var(--text-muted)] hover:text-[var(--accent-blue)] hover:bg-[var(--bg-elevated)] transition-all"
            title="Mark all read"
          >
            <CheckCheck size={14} />
          </button>
          <button
            onClick={clearNotifications}
            className="p-1.5 rounded-md text-[var(--text-muted)] hover:text-[var(--accent-red)] hover:bg-[var(--bg-elevated)] transition-all"
            title="Clear all"
          >
            <Trash2 size={14} />
          </button>
        </div>
      </div>
      <div className="max-h-72 overflow-y-auto">
        {notifications.length === 0 ? (
          <div className="py-8 text-center">
            <Bell size={20} className="mx-auto text-[var(--text-muted)] mb-2 opacity-40" />
            <p className="text-xs text-[var(--text-muted)]">No notifications yet</p>
          </div>
        ) : (
          notifications.map((n) => {
            const Icon = notifIcons[n.type];
            return (
              <div
                key={n.id}
                className="flex items-start gap-3 px-4 py-3 hover:bg-[var(--bg-elevated)]/50 transition-colors border-b border-[var(--border-color)]/50 last:border-0"
              >
                <Icon size={15} className={`mt-0.5 flex-shrink-0 ${notifColors[n.type]}`} />
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-medium text-[var(--text-primary)] truncate">{n.title}</p>
                  {n.message && (
                    <p className="text-[10px] text-[var(--text-muted)] truncate mt-0.5">{n.message}</p>
                  )}
                  <p className="text-[10px] text-[var(--text-muted)] mt-1">{timeAgo(n.timestamp)}</p>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}

export default function Header() {
  const wsConnected = useSystemStore((s) => s.wsConnected);
  const status = useSystemStore((s) => s.status);
  const dailyPnl = useTradingStore((s) => s.dailyPnl);
  const pnlPercent = useTradingStore((s) => s.pnlPercent);
  const collapsed = useUIStore((s) => s.sidebarCollapsed);
  const setPaletteOpen = useUIStore((s) => s.setPaletteOpen);
  const unreadCount = useUIStore((s) => s.unreadCount);
  const [notifOpen, setNotifOpen] = useState(false);
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia('(max-width: 768px)');
    setIsMobile(mq.matches);
    const handler = (e: MediaQueryListEvent) => setIsMobile(e.matches);
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, []);

  const sidebarWidth = isMobile ? '0px' : (collapsed ? '64px' : '220px');

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
          <span className="hidden sm:inline">Search...</span>
          <kbd className="ml-3 text-[10px] bg-[var(--bg-card)] px-1.5 py-0.5 rounded border border-[var(--border-color)] hidden sm:inline">
            Ctrl+K
          </kbd>
        </button>
        <LiveClock />
      </div>

      {/* Center: Quick Metrics */}
      <div className="hidden lg:flex items-center gap-5">
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
          <span className="hidden sm:inline">{wsConnected ? 'Live' : 'Offline'}</span>
          {wsConnected && <div className="w-1.5 h-1.5 rounded-full bg-[var(--accent-green)] status-dot" />}
        </div>

        <div className="h-5 w-px bg-[var(--border-color)]" />

        {/* Notifications */}
        <div className="relative">
          <button
            onClick={() => setNotifOpen(!notifOpen)}
            className="relative w-8 h-8 rounded-lg flex items-center justify-center text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-elevated)] transition-all"
          >
            <Bell size={16} />
            {unreadCount > 0 && (
              <span className="absolute -top-0.5 -right-0.5 min-w-[16px] h-4 flex items-center justify-center text-[9px] font-bold text-white bg-[var(--accent-red)] rounded-full px-1 animate-fade-in">
                {unreadCount > 99 ? '99+' : unreadCount}
              </span>
            )}
          </button>
          {notifOpen && <NotificationPanel onClose={() => setNotifOpen(false)} />}
        </div>

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
