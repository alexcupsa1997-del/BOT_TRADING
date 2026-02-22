import { useEffect, useState } from 'react';
import { api } from '../api/client';
import { useUIStore } from '../store/uiStore';
import type { ApiResponse, TradingConfig } from '../api/types';
import { Settings, Save, RotateCcw, Download, Upload } from 'lucide-react';

type Tab = 'general' | 'strategy' | 'execution' | 'logging';

export default function ConfigPage() {
  const [config, setConfig] = useState<TradingConfig | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>('general');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const addToast = useUIStore((s) => s.addToast);

  useEffect(() => {
    api.get<ApiResponse<TradingConfig>>('/config')
      .then((res) => setConfig(res.data))
      .catch((e) => setError(e.message));
  }, []);

  const handleSave = async () => {
    if (!config) return;
    setSaving(true);
    setError('');
    try {
      await api.put<ApiResponse<TradingConfig>>('/config', config);
      addToast({ type: 'success', title: 'Configuration saved', message: 'Changes applied successfully' });
    } catch (e) {
      setError((e as Error).message);
      addToast({ type: 'error', title: 'Save failed', message: (e as Error).message });
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    api.get<ApiResponse<TradingConfig>>('/config')
      .then((res) => { setConfig(res.data); addToast({ type: 'info', title: 'Configuration reset' }); })
      .catch((e) => setError(e.message));
  };

  const handleExport = () => {
    if (!config) return;
    const blob = new Blob([JSON.stringify(config, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'goliath-config.json';
    a.click();
    URL.revokeObjectURL(url);
    addToast({ type: 'success', title: 'Config exported' });
  };

  const handleImport = () => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.json';
    input.onchange = (e) => {
      const file = (e.target as HTMLInputElement).files?.[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = (ev) => {
        try {
          const parsed = JSON.parse(ev.target?.result as string);
          setConfig(parsed);
          addToast({ type: 'success', title: 'Config imported', message: 'Review and save to apply' });
        } catch {
          addToast({ type: 'error', title: 'Import failed', message: 'Invalid JSON file' });
        }
      };
      reader.readAsText(file);
    };
    input.click();
  };

  if (!config) {
    return <div className="text-[var(--text-muted)]">Loading configuration...</div>;
  }

  const tabs: { id: Tab; label: string }[] = [
    { id: 'general', label: 'General' },
    { id: 'strategy', label: 'Strategy' },
    { id: 'execution', label: 'Risk & Execution' },
    { id: 'logging', label: 'Logging' },
  ];

  return (
    <div className="space-y-6 stagger-children">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Configuration</h1>
          <p className="text-sm text-[var(--text-secondary)] mt-0.5">Manage trading parameters and settings</p>
        </div>
        <div className="flex gap-2">
          <button onClick={handleImport} className="btn-ghost flex items-center gap-1.5 text-xs">
            <Upload size={13} /> Import
          </button>
          <button onClick={handleExport} className="btn-ghost flex items-center gap-1.5 text-xs">
            <Download size={13} /> Export
          </button>
          <button onClick={handleReset} className="btn-ghost flex items-center gap-1.5 text-xs">
            <RotateCcw size={13} /> Reset
          </button>
          <button onClick={handleSave} disabled={saving} className="btn-primary flex items-center gap-1.5 text-xs">
            <Save size={13} /> {saving ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>

      {error && (
        <div className="glass-card p-3 border-l-2" style={{ borderLeftColor: 'var(--accent-red)' }}>
          <p className="text-xs text-[var(--accent-red)]">{error}</p>
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-0.5 bg-[var(--bg-elevated)] rounded-lg p-0.5">
        {tabs.map((tab) => (
          <button key={tab.id} onClick={() => setActiveTab(tab.id)}
            className={`flex-1 py-2 text-xs font-medium rounded-md transition-all ${
              activeTab === tab.id ? 'bg-[var(--accent-blue)] text-white shadow-sm' : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
            }`}>
            {tab.label}
          </button>
        ))}
      </div>

      <div className="glass-card p-6">
        {activeTab === 'general' && (
          <div className="space-y-4">
            <div className="flex items-center gap-2 mb-2">
              <Settings size={16} className="text-[var(--accent-blue)]" />
              <h3 className="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider">General Settings</h3>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-[10px] text-[var(--text-muted)] uppercase tracking-wider mb-1">Mode</label>
                <select className="input-field text-sm w-full" value={config.mode}
                  onChange={(e) => setConfig({ ...config, mode: e.target.value })}>
                  <option value="paper">Paper</option>
                  <option value="live">Live</option>
                </select>
              </div>
              <div>
                <label className="block text-[10px] text-[var(--text-muted)] uppercase tracking-wider mb-1">Timeframe</label>
                <select className="input-field text-sm w-full" value={config.timeframe}
                  onChange={(e) => setConfig({ ...config, timeframe: e.target.value })}>
                  {['1m', '5m', '15m', '1h', '4h', '1d'].map((tf) => <option key={tf} value={tf}>{tf}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-[10px] text-[var(--text-muted)] uppercase tracking-wider mb-1">Balance</label>
                <input className="input-field text-sm w-full" type="number"
                  value={config.balance} onChange={(e) => setConfig({ ...config, balance: parseFloat(e.target.value) || 0 })} />
              </div>
              <div>
                <label className="block text-[10px] text-[var(--text-muted)] uppercase tracking-wider mb-1">Symbols (comma separated)</label>
                <input className="input-field text-sm w-full" value={config.symbols.join(', ')}
                  onChange={(e) => setConfig({ ...config, symbols: e.target.value.split(',').map((s) => s.trim()).filter(Boolean) })} />
              </div>
            </div>
          </div>
        )}

        {activeTab === 'strategy' && (
          <div className="space-y-4">
            <h3 className="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider">Strategy Configuration</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-[10px] text-[var(--text-muted)] uppercase tracking-wider mb-1">Strategy Name</label>
                <input className="input-field text-sm w-full" value={config.strategy.name}
                  onChange={(e) => setConfig({ ...config, strategy: { ...config.strategy, name: e.target.value } })} />
              </div>
              <div>
                <label className="block text-[10px] text-[var(--text-muted)] uppercase tracking-wider mb-1">Model Path</label>
                <input className="input-field text-sm w-full" value={config.strategy.model_path}
                  onChange={(e) => setConfig({ ...config, strategy: { ...config.strategy, model_path: e.target.value } })} />
              </div>
              <div>
                <label className="block text-[10px] text-[var(--text-muted)] uppercase tracking-wider mb-1">Confidence Threshold</label>
                <input className="input-field text-sm w-full" type="number" step="0.01" min="0" max="1"
                  value={config.strategy.confidence_threshold}
                  onChange={(e) => setConfig({ ...config, strategy: { ...config.strategy, confidence_threshold: parseFloat(e.target.value) || 0 } })} />
              </div>
            </div>
          </div>
        )}

        {activeTab === 'execution' && (
          <div className="space-y-4">
            <h3 className="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider">Risk & Execution</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-[10px] text-[var(--text-muted)] uppercase tracking-wider mb-1">Gateway URL</label>
                <input className="input-field text-sm w-full" value={config.execution.gateway_url}
                  onChange={(e) => setConfig({ ...config, execution: { ...config.execution, gateway_url: e.target.value } })} />
              </div>
              <div>
                <label className="block text-[10px] text-[var(--text-muted)] uppercase tracking-wider mb-1">Risk Limit Per Trade</label>
                <input className="input-field text-sm w-full" type="number" step="0.001" min="0" max="1"
                  value={config.execution.risk_limit_per_trade}
                  onChange={(e) => setConfig({ ...config, execution: { ...config.execution, risk_limit_per_trade: parseFloat(e.target.value) || 0 } })} />
              </div>
              <div>
                <label className="block text-[10px] text-[var(--text-muted)] uppercase tracking-wider mb-1">Max Open Trades</label>
                <input className="input-field text-sm w-full" type="number" min="1" max="50"
                  value={config.execution.max_open_trades}
                  onChange={(e) => setConfig({ ...config, execution: { ...config.execution, max_open_trades: parseInt(e.target.value) || 1 } })} />
              </div>
            </div>
          </div>
        )}

        {activeTab === 'logging' && (
          <div className="space-y-4">
            <h3 className="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider">Logging</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-[10px] text-[var(--text-muted)] uppercase tracking-wider mb-1">Log Level</label>
                <select className="input-field text-sm w-full" value={config.logging.level}
                  onChange={(e) => setConfig({ ...config, logging: { ...config.logging, level: e.target.value } })}>
                  {['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'].map((l) => <option key={l} value={l}>{l}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-[10px] text-[var(--text-muted)] uppercase tracking-wider mb-1">Log File</label>
                <input className="input-field text-sm w-full" value={config.logging.file}
                  onChange={(e) => setConfig({ ...config, logging: { ...config.logging, file: e.target.value } })} />
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
