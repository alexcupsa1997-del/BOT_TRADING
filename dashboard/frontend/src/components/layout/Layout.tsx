import { Outlet } from 'react-router-dom';
import { useCallback } from 'react';
import Sidebar from './Sidebar';
import Header from './Header';
import { useWebSocket } from '../../hooks/useWebSocket';
import { useSystemStore } from '../../store/systemStore';
import { useTradingStore } from '../../store/tradingStore';
import type { SystemStatus, TradingData } from '../../api/types';

export default function Layout() {
  const setStatus = useSystemStore((s) => s.setStatus);
  const setSysWs = useSystemStore((s) => s.setWsConnected);
  const setTradingData = useTradingStore((s) => s.setTradingData);
  const setTradeWs = useTradingStore((s) => s.setWsConnected);

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

  return (
    <div className="min-h-screen bg-[var(--bg-primary)]">
      <Sidebar />
      <Header />
      <main className="ml-56 pt-4 px-6 pb-8">
        <Outlet />
      </main>
    </div>
  );
}
