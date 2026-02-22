import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useUIStore } from '../../store/uiStore';
import {
  LayoutDashboard, TrendingUp, FlaskConical, Settings,
  ScrollText, BarChart3, Brain, Search,
} from 'lucide-react';

const commands = [
  { label: 'Dashboard', path: '/', icon: LayoutDashboard, keywords: 'home overview' },
  { label: 'Trading', path: '/trading', icon: TrendingUp, keywords: 'orders positions pnl' },
  { label: 'Backtest', path: '/backtest', icon: FlaskConical, keywords: 'test strategy simulate' },
  { label: 'Configuration', path: '/config', icon: Settings, keywords: 'settings symbols risk' },
  { label: 'Logs', path: '/logs', icon: ScrollText, keywords: 'errors warnings debug' },
  { label: 'Market Data', path: '/market', icon: BarChart3, keywords: 'charts candles price' },
  { label: 'ML Insights', path: '/ml', icon: Brain, keywords: 'model predictions ai' },
];

export default function CommandPalette() {
  const open = useUIStore((s) => s.paletteOpen);
  const setPaletteOpen = useUIStore((s) => s.setPaletteOpen);
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  const filtered = commands.filter((c) =>
    `${c.label} ${c.keywords}`.toLowerCase().includes(query.toLowerCase())
  );

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setPaletteOpen(!open);
      }
      if (e.key === 'Escape') setPaletteOpen(false);
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, setPaletteOpen]);

  useEffect(() => {
    if (open) {
      setQuery('');
      setSelected(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [open]);

  const exec = (path: string) => {
    navigate(path);
    setPaletteOpen(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (filtered.length === 0) return;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelected((s) => Math.min(s + 1, filtered.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelected((s) => Math.max(s - 1, 0));
    } else if (e.key === 'Enter' && filtered[selected]) {
      exec(filtered[selected].path);
    }
  };

  if (!open) return null;

  return (
    <div className="palette-overlay animate-fade-in" onClick={() => setPaletteOpen(false)}>
      <div
        className="glass-card w-full max-w-lg overflow-hidden animate-fade-in-up"
        style={{ maxHeight: '400px' }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-3 px-4 py-3 border-b border-[var(--border-color)]">
          <Search size={18} className="text-[var(--text-muted)]" />
          <input
            ref={inputRef}
            className="flex-1 bg-transparent outline-none text-sm text-[var(--text-primary)] placeholder:text-[var(--text-muted)]"
            placeholder="Type a command or search..."
            value={query}
            onChange={(e) => { setQuery(e.target.value); setSelected(0); }}
            onKeyDown={handleKeyDown}
          />
          <kbd className="text-[10px] text-[var(--text-muted)] bg-[var(--bg-elevated)] px-1.5 py-0.5 rounded">ESC</kbd>
        </div>
        <div className="py-2 max-h-72 overflow-y-auto">
          {filtered.map((cmd, i) => (
            <button
              key={cmd.path}
              onClick={() => exec(cmd.path)}
              className={`w-full flex items-center gap-3 px-4 py-2.5 text-sm transition-colors ${
                i === selected ? 'bg-[var(--accent-blue-dim)] text-[var(--accent-blue)]' : 'text-[var(--text-secondary)] hover:bg-[var(--bg-card-hover)]'
              }`}
            >
              <cmd.icon size={16} />
              <span className="font-medium">{cmd.label}</span>
              <span className="ml-auto text-xs text-[var(--text-muted)]">{cmd.path}</span>
            </button>
          ))}
          {filtered.length === 0 && (
            <p className="px-4 py-6 text-sm text-[var(--text-muted)] text-center">No results found</p>
          )}
        </div>
      </div>
    </div>
  );
}
