import { create } from 'zustand';
import type { BacktestRun, BacktestResult, BacktestRequest, ApiResponse } from '../api/types';
import { api } from '../api/client';

interface BacktestState {
  runs: BacktestRun[];
  activeRunId: string | null;
  results: Record<string, BacktestResult>;
  isRunning: boolean;
  error: string | null;
  fetchRuns: () => Promise<void>;
  startBacktest: (config: BacktestRequest) => Promise<string>;
  fetchResults: (runId: string) => Promise<void>;
}

export const useBacktestStore = create<BacktestState>((set, get) => ({
  runs: [],
  activeRunId: null,
  results: {},
  isRunning: false,
  error: null,

  fetchRuns: async () => {
    try {
      const res = await api.get<ApiResponse<BacktestRun[]>>('/backtest/list');
      set({ runs: res.data });
    } catch (e) {
      set({ error: (e as Error).message });
    }
  },

  startBacktest: async (config) => {
    set({ isRunning: true, error: null });
    try {
      const res = await api.post<ApiResponse<{ run_id: string }>>('/backtest/run', config);
      const runId = res.data.run_id;
      set({ activeRunId: runId });
      // Refresh runs list
      await get().fetchRuns();
      return runId;
    } catch (e) {
      set({ error: (e as Error).message, isRunning: false });
      throw e;
    }
  },

  fetchResults: async (runId) => {
    try {
      const res = await api.get<ApiResponse<BacktestResult>>(`/backtest/results/${runId}`);
      set((state) => ({
        results: { ...state.results, [runId]: res.data },
        isRunning: false,
      }));
    } catch (e) {
      set({ error: (e as Error).message });
    }
  },
}));
