import { Outlet } from 'react-router-dom';
import { useCallback, useEffect, useState } from 'react';
import Sidebar from './Sidebar';
import Header from './Header';
import ToastContainer from '../common/Toast';
import CommandPalette from '../common/CommandPalette';
import { useWebSocket } from '../../hooks/useWebSocket';
import { useSystemStore } from '../../store/systemStore';
import { useTradingStore } from '../../store/tradingStore';
import { useUIStore } from '../../store/uiStore';
import type { SystemStatus, TradingData } from '../../api/types';

export default function Layout() {
  const setStatus = useSystemStore((s) => s.setStatus);
  const setSysWs = useSystemStore((s) => s.setWsConnected);
  const setTradingData = useTradingStore((s) => s.setTradingData);
  const setTradeWs = useTradingStore((s) => s.setWsConnected);
  const collapsed = useUIStore((s) => s.sidebarCollapsed);
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia('(max-width: 768px)');
    setIsMobile(mq.matches);
    const handler = (e: MediaQueryListEvent) => setIsMobile(e.matches);
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, []);

  const handleStatus = useCallback(
    (data: SystemStatus) => setStatus(data),
    [setStatus]
  );

  const handleTrading = useCallback(
    (data: TradingData) => setTradingData(data),
    [setTradingData]
  );

  const { connected: statusWs } = useWebSocket<SystemStatus>(
    '/ws/status',
    handleStatus
  );
  const { connected: tradingWs } = useWebSocket<TradingData>(
    '/ws/trading',
    handleTrading
  );

  // Sync connection state to stores
  if (statusWs !== useSystemStore.getState().wsConnected) setSysWs(statusWs);
  if (tradingWs !== useTradingStore.getState().wsConnected) setTradeWs(tradingWs);

  // On mobile, sidebar slides over content (no margin needed)
  const sidebarWidth = isMobile ? '0px' : (collapsed ? '64px' : '220px');

  return (
    <div className="min-h-screen bg-[var(--bg-primary)] text-[var(--text-primary)]">
      <Sidebar />
      <Header />

      <main
        className="pt-[72px] px-4 md:px-6 pb-8 transition-all duration-300"
        style={{ marginLeft: sidebarWidth }}
      >
        <Outlet />
      </main>

      {/* Global overlays */}
      <ToastContainer />
      <CommandPalette />
    </div>
  );
}
