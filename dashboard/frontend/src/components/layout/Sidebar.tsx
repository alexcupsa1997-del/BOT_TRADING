import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  TrendingUp,
  FlaskConical,
  Settings,
  ScrollText,
  BarChart3,
  Brain,
} from 'lucide-react';

const navItems = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/trading', icon: TrendingUp, label: 'Trading' },
  { to: '/backtest', icon: FlaskConical, label: 'Backtest' },
  { to: '/config', icon: Settings, label: 'Config' },
  { to: '/logs', icon: ScrollText, label: 'Logs' },
  { to: '/market', icon: BarChart3, label: 'Market Data' },
  { to: '/ml', icon: Brain, label: 'ML Insights' },
];

export default function Sidebar() {
  return (
    <aside className="fixed left-0 top-0 h-screen w-56 bg-[var(--bg-secondary)] border-r border-[var(--border-color)] flex flex-col z-40">
      {/* Logo */}
      <div className="h-16 flex items-center px-5 border-b border-[var(--border-color)]">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-[var(--accent-blue)] flex items-center justify-center text-white font-bold text-sm">
            G
          </div>
          <span className="font-bold text-lg tracking-tight">GOLIATH</span>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-4 px-3 space-y-1">
        {navItems.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-[var(--accent-blue)]/15 text-[var(--accent-blue)]'
                  : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-white/5'
              }`
            }
          >
            <Icon size={18} />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="p-4 border-t border-[var(--border-color)]">
        <p className="text-xs text-[var(--text-secondary)]">GOLIATH v1.0</p>
        <p className="text-xs text-[var(--text-secondary)]">Trading Dashboard</p>
      </div>
    </aside>
  );
}
