import { useEffect, useState, useRef, useCallback } from 'react';
import { api } from '../api/client';
import { useWebSocket } from '../hooks/useWebSocket';
import { useUIStore } from '../store/uiStore';
import type { ApiResponse, LogFile } from '../api/types';
import { ScrollText, Search, Trash2, Download } from 'lucide-react';

export default function LogsPage() {
  const [criticalLogs, setCriticalLogs] = useState<string[]>([]);
  const [engineLogs, setEngineLogs] = useState<string[]>([]);
  const [logFiles, setLogFiles] = useState<LogFile[]>([]);
  const [selectedFile, setSelectedFile] = useState<string>('');
  const [filter, setFilter] = useState('');
  const [autoScroll, setAutoScroll] = useState(true);
  const [activeTab, setActiveTab] = useState<'critical' | 'engine'>('critical');
  const logEndRef = useRef<HTMLDivElement>(null);
  const addToast = useUIStore((s) => s.addToast);

  const handleWsLogs = useCallback((data: { logs: string[] }) => {
    setCriticalLogs(data.logs);
  }, []);

  useWebSocket('/ws/logs', handleWsLogs);

  useEffect(() => {
    api.get<ApiResponse<LogFile[]>>('/logs/files')
      .then((res) => setLogFiles(res.data))
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (activeTab === 'engine') {
      const params = selectedFile ? `?filename=${selectedFile}&lines=200` : '?lines=200';
      api.get<ApiResponse<string[]>>(`/logs/engine${params}`)
        .then((res) => setEngineLogs(res.data))
        .catch(() => setEngineLogs([]));
    }
  }, [activeTab, selectedFile]);

  useEffect(() => {
    if (autoScroll) logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [criticalLogs, engineLogs, autoScroll]);

  const logs = activeTab === 'critical' ? criticalLogs : engineLogs;
  const filteredLogs = filter
    ? logs.filter((l) => l.toLowerCase().includes(filter.toLowerCase()))
    : logs;

  const getLogColor = (log: string) => {
    const lower = log.toLowerCase();
    if (lower.includes('[error]') || lower.includes('[critical]')) return 'text-[var(--accent-red)]';
    if (lower.includes('[warn')) return 'text-[var(--accent-yellow)]';
    if (lower.includes('[info]')) return 'text-[var(--accent-blue)]';
    if (lower.includes('[debug]')) return 'text-[var(--text-muted)]';
    return 'text-[var(--text-primary)]';
  };

  const handleDownload = () => {
    const content = filteredLogs.join('\n');
    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `goliath-logs-${activeTab}-${new Date().toISOString().slice(0, 10)}.txt`;
    a.click();
    URL.revokeObjectURL(url);
    addToast({ type: 'success', title: 'Logs downloaded' });
  };

  return (
    <div className="space-y-6 stagger-children">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Log Viewer</h1>
        <p className="text-sm text-[var(--text-secondary)] mt-0.5">Real-time log monitoring and analysis</p>
      </div>

      {/* Controls */}
      <div className="glass-card p-4">
        <div className="flex items-center gap-3 flex-wrap">
          <div className="flex gap-0.5 bg-[var(--bg-elevated)] rounded-lg p-0.5">
            <button onClick={() => setActiveTab('critical')}
              className={`px-3 py-1.5 text-xs rounded-md font-medium transition-all ${
                activeTab === 'critical' ? 'bg-[var(--accent-red)] text-white shadow-sm' : 'text-[var(--text-secondary)]'
              }`}>
              Critical
            </button>
            <button onClick={() => setActiveTab('engine')}
              className={`px-3 py-1.5 text-xs rounded-md font-medium transition-all ${
                activeTab === 'engine' ? 'bg-[var(--accent-blue)] text-white shadow-sm' : 'text-[var(--text-secondary)]'
              }`}>
              Engine
            </button>
          </div>

          {activeTab === 'engine' && (
            <select className="input-field text-xs py-1.5"
              value={selectedFile} onChange={(e) => setSelectedFile(e.target.value)}>
              <option value="">Latest log file</option>
              {logFiles.map((f) => <option key={f.name} value={f.name}>{f.name} ({f.size_kb}KB)</option>)}
            </select>
          )}

          <div className="flex-1 relative min-w-48">
            <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" />
            <input className="input-field w-full pl-8 pr-3 py-1.5 text-xs"
              placeholder="Filter logs..." value={filter} onChange={(e) => setFilter(e.target.value)} />
          </div>

          <label className="flex items-center gap-1.5 text-xs text-[var(--text-muted)] cursor-pointer">
            <input type="checkbox" checked={autoScroll} onChange={(e) => setAutoScroll(e.target.checked)}
              className="rounded border-[var(--border-color)] w-3.5 h-3.5" />
            Auto-scroll
          </label>

          <div className="h-5 w-px bg-[var(--border-color)]" />

          <button onClick={handleDownload} className="btn-ghost flex items-center gap-1 text-xs py-1.5">
            <Download size={12} /> Download
          </button>
          <button onClick={() => { setCriticalLogs([]); setEngineLogs([]); }}
            className="btn-ghost flex items-center gap-1 text-xs py-1.5 text-[var(--accent-red)]">
            <Trash2 size={12} /> Clear
          </button>
        </div>
      </div>

      {/* Log Stream */}
      <div className="glass-card overflow-hidden">
        <div className="flex items-center justify-between px-4 py-2.5 border-b border-[var(--border-color)]">
          <div className="flex items-center gap-2">
            <ScrollText size={13} className="text-[var(--text-muted)]" />
            <span className="text-[10px] text-[var(--text-muted)] font-mono tabular-nums">{filteredLogs.length} entries</span>
          </div>
          {activeTab === 'critical' && (
            <div className="flex items-center gap-1.5">
              <div className="w-1.5 h-1.5 rounded-full bg-[var(--accent-green)] status-dot" />
              <span className="text-[10px] text-[var(--text-muted)]">Live</span>
            </div>
          )}
        </div>
        <div className="h-[500px] overflow-y-auto p-4 font-mono text-[11px] space-y-px bg-[var(--bg-primary)]/50">
          {filteredLogs.length === 0 ? (
            <p className="text-[var(--text-muted)] text-center py-12 text-xs">No logs available</p>
          ) : (
            filteredLogs.map((log, i) => (
              <div key={i} className={`py-0.5 px-1 rounded hover:bg-[var(--bg-elevated)]/50 ${getLogColor(log)}`}>
                {log}
              </div>
            ))
          )}
          <div ref={logEndRef} />
        </div>
      </div>
    </div>
  );
}
