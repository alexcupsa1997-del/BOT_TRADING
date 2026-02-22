import { useEffect, useState } from 'react';
import { useBacktestStore } from '../store/backtestStore';
import { api } from '../api/client';
import type { ApiResponse, DataFile, BacktestRequest } from '../api/types';
import StatusBadge from '../components/common/StatusBadge';
import LoadingSpinner from '../components/common/LoadingSpinner';
import EquityCurveChart from '../components/dashboard/EquityCurveChart';
import { FlaskConical, Play, FileBarChart, TrendingUp, TrendingDown } from 'lucide-react';

export default function BacktestPage() {
  const { runs, results, isRunning, error, fetchRuns, startBacktest, fetchResults } = useBacktestStore();
  const [dataFiles, setDataFiles] = useState<DataFile[]>([]);
  const [selectedRun, setSelectedRun] = useState<string | null>(null);

  const [form, setForm] = useState<BacktestRequest>({
    data_file: '',
    symbol: 'BTCUSD',
    initial_cash: '100000',
    strategy: 'breakout',
  });

  useEffect(() => {
    fetchRuns();
    api.get<ApiResponse<DataFile[]>>('/market/files')
      .then((res) => setDataFiles(res.data))
      .catch(() => {});
  }, [fetchRuns]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.data_file) return;
    try {
      const runId = await startBacktest(form);
      const poll = setInterval(async () => {
        const res = await api.get<ApiResponse<{ status: string }>>(`/backtest/status/${runId}`);
        if (res.data.status !== 'running') {
          clearInterval(poll);
          await fetchResults(runId);
          await fetchRuns();
        }
      }, 2000);
    } catch {
      // error handled in store
    }
  };

  const viewResult = async (runId: string) => {
    setSelectedRun(runId);
    if (!results[runId]) {
      await fetchResults(runId);
    }
  };

  const activeResult = selectedRun ? results[selectedRun] : null;

  // Transform equity curve for chart
  const equityData = activeResult?.equity_curve?.map((point) => ({
    time: point.timestamp || point.date || '',
    value: parseFloat(point.total_equity || point.equity || '0'),
  })).filter((p) => p.time && !isNaN(p.value)) || [];

  const metrics = activeResult?.metrics;
  const totalReturn = metrics ? parseFloat(metrics.total_return_pct) : 0;

  return (
    <div className="space-y-6 stagger-children">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Backtest Manager</h1>
        <p className="text-sm text-[var(--text-secondary)] mt-0.5">Run and analyze strategy backtests</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Form */}
        <div className="glass-card p-5">
          <div className="flex items-center gap-2 mb-4">
            <FlaskConical size={16} className="text-[var(--accent-blue)]" />
            <h3 className="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider">New Backtest</h3>
          </div>
          <form onSubmit={handleSubmit} className="space-y-3">
            <div>
              <label className="block text-[10px] text-[var(--text-muted)] uppercase tracking-wider mb-1">Data File</label>
              <select className="input-field text-sm w-full"
                value={form.data_file} onChange={(e) => setForm({ ...form, data_file: e.target.value })}>
                <option value="">Select file...</option>
                {dataFiles.map((f) => (
                  <option key={f.path} value={f.path}>{f.name} ({f.size_mb}MB)</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-[10px] text-[var(--text-muted)] uppercase tracking-wider mb-1">Symbol</label>
              <input className="input-field text-sm w-full" value={form.symbol}
                onChange={(e) => setForm({ ...form, symbol: e.target.value })} />
            </div>
            <div>
              <label className="block text-[10px] text-[var(--text-muted)] uppercase tracking-wider mb-1">Initial Cash</label>
              <input className="input-field text-sm w-full" value={form.initial_cash}
                onChange={(e) => setForm({ ...form, initial_cash: e.target.value })} />
            </div>
            <div>
              <label className="block text-[10px] text-[var(--text-muted)] uppercase tracking-wider mb-1">Strategy</label>
              <input className="input-field text-sm w-full" value={form.strategy}
                onChange={(e) => setForm({ ...form, strategy: e.target.value })} />
            </div>
            <button type="submit" disabled={isRunning || !form.data_file} className="btn-primary w-full flex items-center justify-center gap-2">
              {isRunning ? <LoadingSpinner size={16} /> : <Play size={14} />}
              {isRunning ? 'Running...' : 'Run Backtest'}
            </button>
            {error && <p className="text-xs text-[var(--accent-red)]">{error}</p>}
          </form>
        </div>

        {/* Runs List */}
        <div className="glass-card p-5">
          <div className="flex items-center gap-2 mb-4">
            <FileBarChart size={16} className="text-[var(--accent-blue)]" />
            <h3 className="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider">History</h3>
            <span className="ml-auto text-xs text-[var(--text-muted)] font-mono">{runs.length}</span>
          </div>
          <div className="space-y-2 max-h-[400px] overflow-y-auto">
            {runs.length === 0 && <p className="text-sm text-[var(--text-muted)] text-center py-8">No backtests yet</p>}
            {runs.map((run) => (
              <button key={run.run_id} onClick={() => viewResult(run.run_id)}
                className={`w-full text-left p-3 rounded-lg border transition-all ${
                  selectedRun === run.run_id
                    ? 'border-[var(--accent-blue)]/50 bg-[var(--accent-blue-dim)] shadow-[0_0_8px_rgba(59,130,246,0.1)]'
                    : 'border-[var(--border-color)]/50 hover:border-[var(--accent-blue)]/30 hover:bg-[var(--bg-card-hover)]'
                }`}>
                <div className="flex items-center justify-between">
                  <span className="text-xs font-mono text-[var(--text-muted)]">{run.run_id}</span>
                  <StatusBadge status={run.status} />
                </div>
                <div className="text-[10px] text-[var(--text-muted)] mt-1.5">
                  {run.symbol} | {run.strategy} | {new Date(run.created_at).toLocaleString()}
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Results */}
        <div className="glass-card p-5">
          <h3 className="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-4">Results</h3>
          {!activeResult ? (
            <p className="text-sm text-[var(--text-muted)] text-center py-12">Select a backtest to view results</p>
          ) : activeResult.status === 'failed' ? (
            <div className="text-[var(--accent-red)] text-sm">
              <p className="font-medium">Backtest Failed</p>
              <p className="mt-2 text-xs">{activeResult.error}</p>
            </div>
          ) : metrics ? (
            <div className="space-y-3">
              {/* Return highlight */}
              <div className="p-3 rounded-lg bg-[var(--bg-elevated)]/50 flex items-center gap-3">
                {totalReturn >= 0
                  ? <TrendingUp size={20} className="text-[var(--accent-green)]" />
                  : <TrendingDown size={20} className="text-[var(--accent-red)]" />
                }
                <div>
                  <div className={`text-xl font-bold ${totalReturn >= 0 ? 'text-[var(--accent-green)]' : 'text-[var(--accent-red)]'}`}>
                    {totalReturn >= 0 ? '+' : ''}{totalReturn.toFixed(2)}%
                  </div>
                  <div className="text-[10px] text-[var(--text-muted)]">Total Return</div>
                </div>
              </div>

              {Object.entries(metrics).map(([key, value]) => (
                <div key={key} className="flex justify-between items-center py-1.5 border-b border-[var(--border-color)]/30 last:border-0">
                  <span className="text-xs text-[var(--text-muted)] capitalize">{key.replace(/_/g, ' ')}</span>
                  <span className="text-xs font-mono font-medium">
                    {key.includes('pct') || key.includes('ratio')
                      ? `${parseFloat(value).toFixed(2)}${key.includes('pct') ? '%' : ''}`
                      : `$${parseFloat(value).toLocaleString()}`
                    }
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <div className="flex justify-center py-8"><LoadingSpinner /></div>
          )}
        </div>
      </div>

      {/* Equity Curve for selected backtest */}
      {equityData.length > 0 && (
        <div className="glass-card p-5">
          <h3 className="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-3">Backtest Equity Curve</h3>
          <EquityCurveChart data={equityData} />
        </div>
      )}
    </div>
  );
}
