import { useEffect, useState, useRef, useCallback } from 'react';
import { api } from '../api/client';
import { useWebSocket } from '../hooks/useWebSocket';
import type { ApiResponse, LogFile } from '../api/types';
import { ScrollText, Search, Trash2 } from 'lucide-react';

export default function LogsPage() {
  const [criticalLogs, setCriticalLogs] = useState<string[]>([]);
  const [engineLogs, setEngineLogs] = useState<string[]>([]);
  const [logFiles, setLogFiles] = useState<LogFile[]>([]);
  const [selectedFile, setSelectedFile] = useState<string>('');
  const [filter, setFilter] = useState('');
  const [autoScroll, setAutoScroll] = useState(true);
  const [activeTab, setActiveTab] = useState<'critical' | 'engine'>('critical');
  const logEndRef = useRef<HTMLDivElement>(null);

  // Real-time critical logs via WebSocket
  const handleWsLogs = useCallback((data: { logs: string[] }) => {
    setCriticalLogs(data.logs);
  }, []);

  useWebSocket('/ws/logs', handleWsLogs);

  // Load engine logs and file list
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

  // Auto-scroll
  useEffect(() => {
    if (autoScroll) {
      logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [criticalLogs, engineLogs, autoScroll]);

  const logs = activeTab === 'critical' ? criticalLogs : engineLogs;
  const filteredLogs = filter
    ? logs.filter((l) => l.toLowerCase().includes(filter.toLowerCase()))
    : logs;

  const getLogColor = (log: string) => {
    const lower = log.toLowerCase();
    if (lower.includes('[error]') || lower.includes('[critical]')) return 'text-[var(--accent-red)]';
    if (lower.includes('[warn]')) return 'text-[var(--accent-yellow)]';
    if (lower.includes('[info]')) return 'text-[var(--accent-blue)]';
    return 'text-[var(--text-primary)]';
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Log Viewer</h1>

      {/* Controls */}
      <div className="flex items-center gap-4 flex-wrap">
        <div className="flex gap-1 bg-[var(--bg-secondary)] rounded-lg p-1 border border-[var(--border-color)]">
          <button onClick={() => setActiveTab('critical')}
            className={`px-3 py-1.5 text-sm rounded-md transition-colors ${activeTab === 'critical' ? 'bg-[var(--accent-red)]/15 text-[var(--accent-red)]' : 'text-[var(--text-secondary)]'}`}>
            Critical Logs
          </button>
          <button onClick={() => setActiveTab('engine')}
            className={`px-3 py-1.5 text-sm rounded-md transition-colors ${activeTab === 'engine' ? 'bg-[var(--accent-blue)]/15 text-[var(--accent-blue)]' : 'text-[var(--text-secondary)]'}`}>
            Engine Logs
          </button>
        </div>

        {activeTab === 'engine' && (
          <select className="bg-[var(--bg-primary)] border border-[var(--border-color)] rounded-lg px-3 py-1.5 text-sm"
            value={selectedFile} onChange={(e) => setSelectedFile(e.target.value)}>
            <option value="">Latest log file</option>
            {logFiles.map((f) => <option key={f.name} value={f.name}>{f.name} ({f.size_kb}KB)</option>)}
          </select>
        )}

        <div className="flex-1 relative">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-secondary)]" />
          <input className="w-full bg-[var(--bg-primary)] border border-[var(--border-color)] rounded-lg pl-9 pr-3 py-1.5 text-sm"
            placeholder="Filter logs..." value={filter} onChange={(e) => setFilter(e.target.value)} />
        </div>

        <label className="flex items-center gap-2 text-sm text-[var(--text-secondary)]">
          <input type="checkbox" checked={autoScroll} onChange={(e) => setAutoScroll(e.target.checked)}
            className="rounded border-[var(--border-color)]" />
          Auto-scroll
        </label>

        <button onClick={() => { setCriticalLogs([]); setEngineLogs([]); }}
          className="flex items-center gap-1 px-3 py-1.5 rounded-lg border border-[var(--border-color)] text-sm hover:bg-white/5">
          <Trash2 size={14} /> Clear
        </button>
      </div>

      {/* Log Stream */}
      <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border-color)] overflow-hidden">
        <div className="flex items-center justify-between px-4 py-2 border-b border-[var(--border-color)]">
          <div className="flex items-center gap-2">
            <ScrollText size={14} className="text-[var(--text-secondary)]" />
            <span className="text-xs text-[var(--text-secondary)]">{filteredLogs.length} entries</span>
          </div>
          <div className="w-2 h-2 rounded-full bg-[var(--accent-green)] animate-pulse" />
        </div>
        <div className="h-[500px] overflow-y-auto p-4 font-mono text-xs space-y-0.5">
          {filteredLogs.length === 0 ? (
            <p className="text-[var(--text-secondary)] text-center py-8">No logs available</p>
          ) : (
            filteredLogs.map((log, i) => (
              <div key={i} className={`py-0.5 ${getLogColor(log)}`}>{log}</div>
            ))
          )}
          <div ref={logEndRef} />
        </div>
      </div>
    </div>
  );
}
