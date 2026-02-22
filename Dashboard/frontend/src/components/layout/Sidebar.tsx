import { NavLink, useLocation } from 'react-router-dom';
import { useEffect } from 'react';
import { useUIStore } from '../../store/uiStore';
import {
  LayoutDashboard, TrendingUp, FlaskConical, Settings,
  ScrollText, BarChart3, Brain, PanelLeftClose, PanelLeft, X,
} from 'lucide-react';

const navItems = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard', title: 'Dashboard' },
  { to: '/trading', icon: TrendingUp, label: 'Trading', title: 'Trading' },
  { to: '/backtest', icon: FlaskConical, label: 'Backtest', title: 'Backtest' },
  { to: '/config', icon: Settings, label: 'Config', title: 'Configuration' },
  { to: '/logs', icon: ScrollText, label: 'Logs', title: 'Logs' },
  { to: '/market', icon: BarChart3, label: 'Market Data', title: 'Market Data' },
  { to: '/ml', icon: Brain, label: 'ML Insights', title: 'ML Insights' },
];

export default function Sidebar() {
  const collapsed = useUIStore((s) => s.sidebarCollapsed);
  const toggleSidebar = useUIStore((s) => s.toggleSidebar);
  const setSidebarCollapsed = useUIStore((s) => s.setSidebarCollapsed);
  const location = useLocation();

  // Update document title based on route
  useEffect(() => {
    const item = navItems.find((n) => n.to === location.pathname);
    document.title = item ? `${item.title} | GOLIATH` : 'GOLIATH Dashboard';
  }, [location.pathname]);

  // Auto-collapse on mobile
  useEffect(() => {
    const mq = window.matchMedia('(max-width: 768px)');
    const handler = (e: MediaQueryListEvent | MediaQueryList) => {
      if (e.matches) setSidebarCollapsed(true);
    };
    handler(mq);
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, [setSidebarCollapsed]);

  // Close sidebar on mobile when navigating
  useEffect(() => {
    if (window.innerWidth < 768) setSidebarCollapsed(true);
  }, [location.pathname, setSidebarCollapsed]);

  return (
    <>
      {/* Mobile overlay backdrop */}
      {!collapsed && (
        <div
          className="fixed inset-0 bg-black/50 backdrop-blur-sm z-30 md:hidden animate-fade-in"
          onClick={() => setSidebarCollapsed(true)}
        />
      )}

      <aside
        className={`fixed left-0 top-0 h-screen flex flex-col z-40 transition-all duration-300 ease-in-out border-r border-[var(--border-color)] ${
          collapsed ? 'max-md:-translate-x-full md:translate-x-0' : ''
        }`}
        style={{
          width: collapsed ? '64px' : '220px',
          background: 'linear-gradient(180deg, var(--bg-secondary) 0%, var(--bg-primary) 100%)',
        }}
      >
        {/* Logo */}
        <div className="h-14 flex items-center justify-between px-3 border-b border-[var(--border-color)]">
          <div className="flex items-center gap-2 min-w-0">
            <div className="w-9 h-9 rounded-xl flex items-center justify-center text-white font-black text-sm flex-shrink-0"
                 style={{ background: 'linear-gradient(135deg, var(--accent-blue), #6366f1)' }}>
              G
            </div>
            {!collapsed && (
              <span className="font-bold text-base tracking-tight text-[var(--text-primary)] animate-fade-in whitespace-nowrap">
                GOLIATH
              </span>
            )}
          </div>
          <button
            onClick={toggleSidebar}
            className="w-7 h-7 rounded-md flex items-center justify-center text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-elevated)] transition-all flex-shrink-0"
          >
            {collapsed ? <PanelLeft size={15} /> : (
              <span className="hidden md:block"><PanelLeftClose size={15} /></span>
            )}
            {!collapsed && (
              <span className="md:hidden"><X size={15} /></span>
            )}
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 py-3 px-2 space-y-0.5 overflow-y-auto">
          {navItems.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              title={collapsed ? label : undefined}
              className={({ isActive }) =>
                `group relative flex items-center gap-3 rounded-lg text-sm font-medium transition-all duration-200 ${
                  collapsed ? 'justify-center px-0 py-2.5' : 'px-3 py-2.5'
                } ${
                  isActive
                    ? 'bg-[var(--accent-blue)]/15 text-[var(--accent-blue)] shadow-[0_0_12px_rgba(59,130,246,0.1)]'
                    : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-white/5'
                }`
              }
            >
              {({ isActive }) => (
                <>
                  {isActive && (
                    <div className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 rounded-r-full bg-[var(--accent-blue)]" />
                  )}
                  <Icon size={18} className="flex-shrink-0" />
                  {!collapsed && (
                    <span className="animate-fade-in whitespace-nowrap">{label}</span>
                  )}
                  {/* Tooltip when collapsed */}
                  {collapsed && (
                    <div className="absolute left-full ml-2 px-2.5 py-1.5 rounded-md bg-[var(--bg-elevated)] text-[var(--text-primary)] text-xs font-medium whitespace-nowrap opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity duration-200 shadow-lg border border-[var(--border-color)] z-50 hidden md:block">
                      {label}
                    </div>
                  )}
                </>
              )}
            </NavLink>
          ))}
        </nav>

        {/* Footer */}
        <div className="p-3 border-t border-[var(--border-color)]">
          {collapsed ? (
            <div className="flex justify-center">
              <div className="w-2 h-2 rounded-full bg-[var(--accent-green)] status-dot" />
            </div>
          ) : (
            <div className="flex items-center gap-2 animate-fade-in">
              <div className="w-2 h-2 rounded-full bg-[var(--accent-green)] status-dot" />
              <div>
                <p className="text-[10px] font-medium text-[var(--text-secondary)] uppercase tracking-widest">GOLIATH v2</p>
                <p className="text-[10px] text-[var(--text-muted)]">Trading Dashboard</p>
              </div>
            </div>
          )}
        </div>
      </aside>
    </>
  );
}
