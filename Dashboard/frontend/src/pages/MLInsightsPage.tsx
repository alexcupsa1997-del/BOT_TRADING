import { useEffect, useState } from 'react';
import { api } from '../api/client';
import type { ApiResponse, ModelInfo } from '../api/types';
import { LineChart, Line, XAxis, YAxis, ResponsiveContainer, Tooltip, ReferenceLine } from 'recharts';
import { Brain, Cpu, HardDrive, Layers, TrendingUp, Activity } from 'lucide-react';

interface Prediction {
  symbol: string;
  direction: string;
  confidence: number;
  tp_multiplier: number;
  sl_multiplier: number;
  timestamp: string;
}

// Generate sample confidence history
function generateConfidenceHistory() {
  const points = [];
  for (let i = 0; i < 50; i++) {
    points.push({
      idx: i,
      confidence: parseFloat((40 + Math.random() * 50).toFixed(1)),
      threshold: 70,
    });
  }
  return points;
}

// Sample predictions
const samplePredictions: Prediction[] = [
  { symbol: 'XAUUSD', direction: 'BUY', confidence: 0.82, tp_multiplier: 2.1, sl_multiplier: 1.3, timestamp: '14:30:00' },
  { symbol: 'BTCUSD', direction: 'SELL', confidence: 0.65, tp_multiplier: 1.8, sl_multiplier: 1.5, timestamp: '14:15:00' },
  { symbol: 'EURUSD', direction: 'HOLD', confidence: 0.43, tp_multiplier: 0, sl_multiplier: 0, timestamp: '14:00:00' },
  { symbol: 'XAUUSD', direction: 'BUY', confidence: 0.91, tp_multiplier: 3.2, sl_multiplier: 1.1, timestamp: '13:45:00' },
];

export default function MLInsightsPage() {
  const [modelInfo, setModelInfo] = useState<ModelInfo | null>(null);
  const confidenceHistory = generateConfidenceHistory();

  useEffect(() => {
    api.get<ApiResponse<ModelInfo>>('/ml/model-info')
      .then((res) => setModelInfo(res.data))
      .catch(() => {});
  }, []);

  return (
    <div className="space-y-6 stagger-children">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">ML Insights</h1>
        <p className="text-sm text-[var(--text-secondary)] mt-0.5">Model architecture, predictions, and confidence tracking</p>
      </div>

      {/* Top Row: Model Info + Live Predictions */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Model Architecture */}
        <div className="glass-card p-5">
          <div className="flex items-center gap-2 mb-4">
            <Brain size={16} className="text-[var(--accent-blue)]" />
            <h3 className="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider">Model Architecture</h3>
          </div>
          {modelInfo ? (
            <div className="space-y-2.5">
              <div className="flex justify-between items-center py-1.5 border-b border-[var(--border-color)]/30">
                <span className="text-xs text-[var(--text-muted)]">Type</span>
                <span className="text-xs font-mono font-bold text-[var(--accent-blue)]">{modelInfo.model_type}</span>
              </div>
              {Object.entries(modelInfo.architecture).map(([key, value]) => (
                <div key={key} className="flex justify-between items-center py-1.5 border-b border-[var(--border-color)]/30 last:border-0">
                  <span className="text-xs text-[var(--text-muted)] capitalize">{key.replace(/_/g, ' ')}</span>
                  <span className="text-xs font-mono">
                    {Array.isArray(value) ? value.join(', ') : String(value)}
                  </span>
                </div>
              ))}
              <div className="flex justify-between items-center py-1.5">
                <span className="text-xs text-[var(--text-muted)]">Device</span>
                <span className={`text-xs font-mono font-bold ${modelInfo.device.includes('cuda') ? 'text-[var(--accent-green)]' : 'text-[var(--accent-yellow)]'}`}>
                  {modelInfo.device}
                </span>
              </div>
            </div>
          ) : (
            <p className="text-sm text-[var(--text-muted)]">Loading model info...</p>
          )}
        </div>

        {/* Live Predictions */}
        <div className="glass-card p-5">
          <div className="flex items-center gap-2 mb-4">
            <Activity size={16} className="text-[var(--accent-green)]" />
            <h3 className="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider">Recent Predictions</h3>
          </div>
          <div className="space-y-2">
            {samplePredictions.map((pred, i) => (
              <div key={i} className="flex items-center gap-3 p-2.5 rounded-lg bg-[var(--bg-elevated)]/50 hover:bg-[var(--bg-elevated)] transition-colors">
                <div className="flex-shrink-0">
                  <div className={`w-10 h-10 rounded-lg flex items-center justify-center text-xs font-bold ${
                    pred.direction === 'BUY' ? 'bg-[var(--accent-green-dim)] text-[var(--accent-green)]'
                    : pred.direction === 'SELL' ? 'bg-[var(--accent-red-dim)] text-[var(--accent-red)]'
                    : 'bg-[var(--bg-elevated)] text-[var(--text-muted)]'
                  }`}>
                    {pred.direction.slice(0, 1)}
                  </div>
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium">{pred.symbol}</span>
                    <span className="text-[10px] text-[var(--text-muted)]">{pred.timestamp}</span>
                  </div>
                  <div className="flex items-center gap-3 mt-0.5">
                    <span className="text-[10px] text-[var(--text-muted)]">
                      Conf: <span className={`font-bold ${pred.confidence >= 0.7 ? 'text-[var(--accent-green)]' : 'text-[var(--accent-yellow)]'}`}>
                        {(pred.confidence * 100).toFixed(0)}%
                      </span>
                    </span>
                    {pred.tp_multiplier > 0 && (
                      <span className="text-[10px] text-[var(--text-muted)]">
                        TP: {pred.tp_multiplier.toFixed(1)}x | SL: {pred.sl_multiplier.toFixed(1)}x
                      </span>
                    )}
                  </div>
                </div>
                {/* Confidence bar */}
                <div className="w-16 h-1.5 rounded-full bg-[var(--bg-card)] overflow-hidden flex-shrink-0">
                  <div
                    className="h-full rounded-full"
                    style={{
                      width: `${pred.confidence * 100}%`,
                      background: pred.confidence >= 0.7 ? 'var(--accent-green)' : pred.confidence >= 0.5 ? 'var(--accent-yellow)' : 'var(--accent-red)',
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Confidence History Chart */}
      <div className="glass-card p-5">
        <div className="flex items-center gap-2 mb-3">
          <TrendingUp size={14} className="text-[var(--text-muted)]" />
          <h3 className="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider">Confidence History</h3>
        </div>
        <ResponsiveContainer width="100%" height={180}>
          <LineChart data={confidenceHistory}>
            <XAxis dataKey="idx" hide />
            <YAxis domain={[0, 100]} ticks={[30, 50, 70, 90]} tick={{ fontSize: 10, fill: 'var(--text-muted)' }} axisLine={false} tickLine={false} width={25} />
            <Tooltip
              contentStyle={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '8px', fontSize: '12px' }}
              formatter={(v: number) => [`${v}%`, 'Confidence']}
            />
            <ReferenceLine y={70} stroke="rgba(16,185,129,0.4)" strokeDasharray="3 3" label={{ value: 'Threshold', fill: 'var(--text-muted)', fontSize: 10 }} />
            <Line type="monotone" dataKey="confidence" stroke="#3b82f6" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Available Models */}
      <div className="glass-card p-5">
        <div className="flex items-center gap-2 mb-4">
          <HardDrive size={14} className="text-[var(--text-muted)]" />
          <h3 className="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider">Available Models</h3>
        </div>
        <div className="space-y-2">
          {modelInfo?.available_models && modelInfo.available_models.length > 0 ? (
            modelInfo.available_models.map((m) => (
              <div key={m.name} className="flex items-center justify-between p-3 bg-[var(--bg-elevated)]/50 rounded-lg border border-[var(--border-color)]/30 hover:border-[var(--accent-blue)]/20 transition-colors">
                <div>
                  <div className="text-sm font-medium">{m.name}</div>
                  <div className="text-[10px] text-[var(--text-muted)] font-mono">{m.path}</div>
                </div>
                <span className="text-xs text-[var(--text-muted)] font-mono">{m.size_mb} MB</span>
              </div>
            ))
          ) : (
            <p className="text-sm text-[var(--text-muted)]">No model checkpoints found</p>
          )}
        </div>
      </div>

      {/* Output Heads */}
      <div className="glass-card p-5">
        <div className="flex items-center gap-2 mb-4">
          <Layers size={14} className="text-[var(--text-muted)]" />
          <h3 className="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider">Model Output Heads</h3>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {[
            { name: 'Direction', color: 'var(--accent-green)', desc: '3-class: BUY / HOLD / SELL. Softmax probabilities for confidence weighting.' },
            { name: 'TP/SL', color: 'var(--accent-blue)', desc: '2-value regression: Take Profit and Stop Loss multipliers (1-5x ATR).' },
            { name: 'Confidence', color: '#8b5cf6', desc: 'Sigmoid (0-1). Only above threshold (0.7) triggers trades. Sniper entries.' },
          ].map((head) => (
            <div key={head.name} className="p-4 rounded-lg bg-[var(--bg-elevated)]/50 border border-[var(--border-color)]/30">
              <div className="text-xs font-bold mb-2" style={{ color: head.color }}>{head.name} Head</div>
              <p className="text-[10px] text-[var(--text-muted)] leading-relaxed">{head.desc}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Note */}
      <div className="glass-card p-4 border-l-2" style={{ borderLeftColor: 'var(--accent-yellow)' }}>
        <div className="flex items-center gap-2 mb-1">
          <Cpu size={14} className="text-[var(--accent-yellow)]" />
          <span className="text-xs font-bold text-[var(--accent-yellow)]">ML Training Note</span>
        </div>
        <p className="text-[11px] text-[var(--text-muted)]">
          {modelInfo?.note || 'ML training is performed on a separate machine with dedicated GPU. This dashboard loads and uses trained checkpoints only.'}
        </p>
      </div>
    </div>
  );
}
