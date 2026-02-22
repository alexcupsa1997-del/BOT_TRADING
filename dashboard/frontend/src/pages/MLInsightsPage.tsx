import { useEffect, useState } from 'react';
import { api } from '../api/client';
import type { ApiResponse, ModelInfo } from '../api/types';
import { Brain, Cpu, HardDrive, Layers } from 'lucide-react';

export default function MLInsightsPage() {
  const [modelInfo, setModelInfo] = useState<ModelInfo | null>(null);

  useEffect(() => {
    api.get<ApiResponse<ModelInfo>>('/ml/model-info')
      .then((res) => setModelInfo(res.data))
      .catch(() => {});
  }, []);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">ML Insights</h1>

      {/* Model Info */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-[var(--bg-card)] rounded-xl p-5 border border-[var(--border-color)]">
          <div className="flex items-center gap-2 mb-4">
            <Brain size={18} className="text-[var(--accent-purple)]" />
            <h3 className="font-semibold">Model Architecture</h3>
          </div>
          {modelInfo ? (
            <div className="space-y-3 text-sm">
              <div className="flex justify-between">
                <span className="text-[var(--text-secondary)]">Model Type</span>
                <span className="font-mono font-medium">{modelInfo.model_type}</span>
              </div>
              {Object.entries(modelInfo.architecture).map(([key, value]) => (
                <div key={key} className="flex justify-between">
                  <span className="text-[var(--text-secondary)] capitalize">{key.replace(/_/g, ' ')}</span>
                  <span className="font-mono text-xs">
                    {Array.isArray(value) ? value.join(', ') : String(value)}
                  </span>
                </div>
              ))}
              <div className="flex justify-between">
                <span className="text-[var(--text-secondary)]">Device</span>
                <span className="font-mono">{modelInfo.device}</span>
              </div>
            </div>
          ) : (
            <p className="text-sm text-[var(--text-secondary)]">Loading model info...</p>
          )}
        </div>

        <div className="bg-[var(--bg-card)] rounded-xl p-5 border border-[var(--border-color)]">
          <div className="flex items-center gap-2 mb-4">
            <HardDrive size={18} className="text-[var(--accent-blue)]" />
            <h3 className="font-semibold">Available Models</h3>
          </div>
          <div className="space-y-2">
            {modelInfo?.available_models && modelInfo.available_models.length > 0 ? (
              modelInfo.available_models.map((m) => (
                <div key={m.name} className="flex items-center justify-between p-3 bg-[var(--bg-primary)] rounded-lg border border-[var(--border-color)]">
                  <div>
                    <div className="text-sm font-medium">{m.name}</div>
                    <div className="text-xs text-[var(--text-secondary)]">{m.path}</div>
                  </div>
                  <span className="text-xs text-[var(--text-secondary)]">{m.size_mb} MB</span>
                </div>
              ))
            ) : (
              <p className="text-sm text-[var(--text-secondary)]">No model checkpoints found</p>
            )}
          </div>
        </div>
      </div>

      {/* Output Heads Description */}
      <div className="bg-[var(--bg-card)] rounded-xl p-5 border border-[var(--border-color)]">
        <div className="flex items-center gap-2 mb-4">
          <Layers size={18} className="text-[var(--accent-green)]" />
          <h3 className="font-semibold">Model Output Heads</h3>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="p-4 bg-[var(--bg-primary)] rounded-lg border border-[var(--border-color)]">
            <div className="text-sm font-medium text-[var(--accent-green)] mb-2">Direction Head</div>
            <p className="text-xs text-[var(--text-secondary)]">
              3-class classification: BUY (2), HOLD (1), SELL (0). Uses softmax probabilities for confidence weighting.
            </p>
          </div>
          <div className="p-4 bg-[var(--bg-primary)] rounded-lg border border-[var(--border-color)]">
            <div className="text-sm font-medium text-[var(--accent-blue)] mb-2">TP/SL Head</div>
            <p className="text-xs text-[var(--text-secondary)]">
              2-value regression: Take Profit and Stop Loss multipliers (1-5x ATR). Dynamic risk management based on market conditions.
            </p>
          </div>
          <div className="p-4 bg-[var(--bg-primary)] rounded-lg border border-[var(--border-color)]">
            <div className="text-sm font-medium text-[var(--accent-purple)] mb-2">Confidence Head</div>
            <p className="text-xs text-[var(--text-secondary)]">
              Sigmoid output (0-1). Only signals above threshold (default 0.7) trigger trades. High-confidence "sniper" entries.
            </p>
          </div>
        </div>
      </div>

      {/* Note */}
      <div className="bg-[var(--accent-yellow)]/10 border border-[var(--accent-yellow)]/30 rounded-xl p-4">
        <div className="flex items-center gap-2 mb-1">
          <Cpu size={16} className="text-[var(--accent-yellow)]" />
          <span className="text-sm font-medium text-[var(--accent-yellow)]">ML Training Note</span>
        </div>
        <p className="text-xs text-[var(--text-secondary)]">
          {modelInfo?.note || 'ML training is performed on a separate machine with dedicated GPU. This dashboard loads and uses trained checkpoints only.'}
        </p>
      </div>
    </div>
  );
}
