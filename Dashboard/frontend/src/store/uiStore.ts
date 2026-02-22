import { create } from 'zustand';

export interface Toast {
  id: string;
  type: 'success' | 'error' | 'warning' | 'info';
  title: string;
  message?: string;
  duration?: number;
}

interface UIState {
  sidebarCollapsed: boolean;
  theme: 'dark' | 'light';
  toasts: Toast[];
  paletteOpen: boolean;
  toggleSidebar: () => void;
  setSidebarCollapsed: (v: boolean) => void;
  toggleTheme: () => void;
  addToast: (toast: Omit<Toast, 'id'>) => void;
  removeToast: (id: string) => void;
  setPaletteOpen: (v: boolean) => void;
}

let toastCounter = 0;

export const useUIStore = create<UIState>((set, get) => ({
  sidebarCollapsed: false,
  theme: 'dark',
  toasts: [],
  paletteOpen: false,

  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
  setSidebarCollapsed: (v) => set({ sidebarCollapsed: v }),

  toggleTheme: () => {
    const next = get().theme === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    set({ theme: next });
  },

  addToast: (toast) => {
    const id = `toast-${++toastCounter}`;
    const duration = toast.duration ?? 4000;
    set((s) => ({ toasts: [...s.toasts, { ...toast, id }] }));
    if (duration > 0) {
      setTimeout(() => get().removeToast(id), duration);
    }
  },

  removeToast: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
  setPaletteOpen: (v) => set({ paletteOpen: v }),
}));
