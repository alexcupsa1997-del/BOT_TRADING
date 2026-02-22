import { create } from 'zustand';
import type { SystemStatus, ServiceHealth } from '../api/types';

interface SystemState {
  status: SystemStatus | null;
  services: ServiceHealth[];
  wsConnected: boolean;
  setStatus: (s: SystemStatus) => void;
  setServices: (s: ServiceHealth[]) => void;
  setWsConnected: (c: boolean) => void;
}

export const useSystemStore = create<SystemState>((set) => ({
  status: null,
  services: [],
  wsConnected: false,
  setStatus: (status) => set({ status }),
  setServices: (services) => set({ services }),
  setWsConnected: (wsConnected) => set({ wsConnected }),
}));
