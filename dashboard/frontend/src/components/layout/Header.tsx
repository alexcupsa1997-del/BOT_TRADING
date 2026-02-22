import { useSystemStore } from '../../store/systemStore';
import { useTradingStore } from '../../store/tradingStore';
import { Wifi, WifiOff } from 'lucide-react';

export default function Header() {
  const wsConnected = useSystemStore((s) => s.wsConnected);
  const status = useSystemStore((s) => s.status);
  const dailyPnl = useTradingStore((s) => s.dailyPnl);
  const pnlPercent = useTradingStore((s) => s.pnlPercent);

  return (
    <header className="h-16 bg-[var(--bg-secondary)] border-b border-[var(--border-color)] flex items-center justify-between px-6 ml-56">
      {/* Left: Quick stats */}
      <div className="flex items-center gap-6">
        {status && (
          <>
            <div className="text-sm">
              <span className="text-[var(--text-secondary)]">CPU </span>
              <span className={status.cpu_percent > 80 ? 'text-[var(--accent-red)]' : 'text-[var(--text-primary)]'}>
                {status.cpu_percent.toFixed(1)}%
              </span>
            </div>
            <div className="text-sm">
              <span className="text-[var(--text-secondary)]">RAM </span>
              <span className={status.ram_percent > 80 ? 'text-[var(--accent-red)]' : 'text-[var(--text-primary)]'}>
                {status.ram_percent.toFixed(1)}%
              </span>
            </div>
          </>
        )}
        <div className="text-sm">
          <span className="text-[var(--text-secondary)]">PnL </span>
          <span className={dailyPnl >= 0 ? 'text-[var(--accent-green)]' : 'text-[var(--accent-red)]'}>
            ${dailyPnl.toFixed(2)} ({pnlPercent.toFixed(2)}%)
          </span>
        </div>
      </div>

      {/* Right: Connection status */}
      <div className="flex items-center gap-2">
        {wsConnected ? (
          <div className="flex items-center gap-1.5 text-[var(--accent-green)] text-sm">
            <Wifi size={14} />
            <span>Live</span>
          </div>
        ) : (
          <div className="flex items-center gap-1.5 text-[var(--accent-red)] text-sm">
            <WifiOff size={14} />
            <span>Disconnected</span>
          </div>
        )}
      </div>
    </header>
  );
}
