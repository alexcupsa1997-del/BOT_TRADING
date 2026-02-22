import { create } from 'zustand';
import type { Order, Position, TradingData } from '../api/types';

interface TradingState {
  dailyPnl: number;
  pnlPercent: number;
  activeStrategy: string;
  openPositions: number;
  tradesCount: number;
  orders: Order[];
  positions: Position[];
  equityCurve: Record<string, string>[];
  wsConnected: boolean;
  setTradingData: (data: TradingData) => void;
  setWsConnected: (c: boolean) => void;
}

export const useTradingStore = create<TradingState>((set) => ({
  dailyPnl: 0,
  pnlPercent: 0,
  activeStrategy: 'N/A',
  openPositions: 0,
  tradesCount: 0,
  orders: [],
  positions: [],
  equityCurve: [],
  wsConnected: false,
  setTradingData: (data) =>
    set({
      dailyPnl: data.daily_pnl,
      pnlPercent: data.pnl_percent,
      activeStrategy: data.active_strategy,
      openPositions: data.open_positions,
      tradesCount: data.trades_count,
      orders: data.orders,
      positions: data.positions,
      equityCurve: data.equity_curve as unknown as Record<string, string>[],
    }),
  setWsConnected: (wsConnected) => set({ wsConnected }),
}));
