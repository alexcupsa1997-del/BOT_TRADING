import { useEffect, useState } from 'react';
import { useBacktestStore } from '../store/backtestStore';
import { api } from '../api/client';
import type { ApiResponse, DataFile, BacktestRequest } from '../api/types';
import StatusBadge from '../components/common/StatusBadge';
import LoadingSpinner from '../components/common/LoadingSpinner';
import { FlaskConical, Play, FileBarChart } from 'lucide-react';

export default function BacktestPage() {
  const { runs, results, isRunning, error, fetchRuns, startBacktest, fetchResults } = useBacktestStore();
  const [dataFiles, setDataFiles] = useState<DataFile[]>([]);
  const [selectedRun, setSelectedRun] = useState<string | null>(null);

  // Form state
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
      // Poll for completion
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

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Backtest Manager</h1>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Form */}
        <div className="bg-[var(--bg-card)] rounded-xl p-5 border border-[var(--border-color)]">
          <div className="flex items-center gap-2 mb-4">
            <FlaskConical size={18} className="text-[var(--accent-purple)]" />
            <h3 className="text-sm font-semibold">New Backtest</h3>
          </div>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs text-[var(--text-secondary)] mb-1">Data File</label>
              <select
                className="w-full bg-[var(--bg-primary)] border border-[var(--border-color)] rounded-lg px-3 py-2 text-sm"
                value={form.data_file}
                onChange={(e) => setForm({ ...form, data_file: e.target.value })}
              >
                <option value="">Select file...</option>
                {dataFiles.map((f) => (
                  <option key={f.path} value={f.path}>{f.name} ({f.size_mb}MB)</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs text-[var(--text-secondary)] mb-1">Symbol</label>
              <input
                className="w-full bg-[var(--bg-primary)] border border-[var(--border-color)] rounded-lg px-3 py-2 text-sm"
                value={form.symbol}
                onChange={(e) => setForm({ ...form, symbol: e.target.value })}
              />
            </div>
            <div>
              <label className="block text-xs text-[var(--text-secondary)] mb-1">Initial Cash</label>
              <input
                className="w-full bg-[var(--bg-primary)] border border-[var(--border-color)] rounded-lg px-3 py-2 text-sm"
                value={form.initial_cash}
                onChange={(e) => setForm({ ...form, initial_cash: e.target.value })}
              />
            </div>
            <div>
              <label className="block text-xs text-[var(--text-secondary)] mb-1">Strategy</label>
              <input
                className="w-full bg-[var(--bg-primary)] border border-[var(--border-color)] rounded-lg px-3 py-2 text-sm"
                value={form.strategy}
                onChange={(e) => setForm({ ...form, strategy: e.target.value })}
              />
            </div>
            <button
              type="submit"
              disabled={isRunning || !form.data_file}
              className="w-full flex items-center justify-center gap-2 bg-[var(--accent-blue)] hover:bg-[var(--accent-blue)]/80 disabled:opacity-50 text-white rounded-lg px-4 py-2.5 text-sm font-medium transition-colors"
            >
              {isRunning ? <LoadingSpinner size={16} /> : <Play size={16} />}
              {isRunning ? 'Running...' : 'Run Backtest'}
            </button>
            {error && <p className="text-xs text-[var(--accent-red)]">{error}</p>}
          </form>
        </div>

        {/* Runs List */}
        <div className="bg-[var(--bg-card)] rounded-xl p-5 border border-[var(--border-color)]">
          <div className="flex items-center gap-2 mb-4">
            <FileBarChart size={18} className="text-[var(--accent-blue)]" />
            <h3 className="text-sm font-semibold">Backtest History</h3>
            <span className="ml-auto text-xs text-[var(--text-secondary)]">{runs.length} runs</span>
          </div>
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {runs.length === 0 && <p className="text-sm text-[var(--text-secondary)] text-center py-4">No backtests yet</p>}
            {runs.map((run) => (
              <button
                key={run.run_id}
                onClick={() => viewResult(run.run_id)}
                className={`w-full text-left p-3 rounded-lg border transition-colors ${
                  selectedRun === run.run_id
                    ? 'border-[var(--accent-blue)] bg-[var(--accent-blue)]/10'
                    : 'border-[var(--border-color)] hover:border-[var(--accent-blue)]/50'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-mono">{run.run_id}</span>
                  <StatusBadge status={run.status} />
                </div>
                <div className="text-xs text-[var(--text-secondary)] mt-1">
                  {run.symbol} | {run.strategy} | {new Date(run.created_at).toLocaleString()}
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Results View */}
        <div className="bg-[var(--bg-card)] rounded-xl p-5 border border-[var(--border-color)]">
          <h3 className="text-sm font-semibold text-[var(--text-secondary)] mb-4">Results</h3>
          {!activeResult ? (
            <p className="text-sm text-[var(--text-secondary)] text-center py-8">Select a backtest to view results</p>
          ) : activeResult.status === 'failed' ? (
            <div className="text-[var(--accent-red)] text-sm">
              <p className="font-medium">Backtest Failed</p>
              <p className="mt-2">{activeResult.error}</p>
            </div>
          ) : activeResult.metrics ? (
            <div className="space-y-3">
              {Object.entries(activeResult.metrics).map(([key, value]) => (
                <div key={key} className="flex justify-between text-sm">
                  <span className="text-[var(--text-secondary)] capitalize">{key.replace(/_/g, ' ')}</span>
                  <span className="font-mono font-medium">
                    {key.includes('pct') || key.includes('ratio') ? `${parseFloat(value).toFixed(2)}${key.includes('pct') ? '%' : ''}` : `$${parseFloat(value).toFixed(2)}`}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <LoadingSpinner />
          )}
        </div>
      </div>
    </div>
  );
}
