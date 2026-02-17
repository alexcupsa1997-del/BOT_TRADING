# Plan: AI Brain Architecture & ML Pipeline Enhancement

> **Minimum document depth: 4000 words (non-negotiable)**
> **Approach: Super slow, methodical, small steps, never rush if confidence < 100%**

---

## 1. Context & Motivation

The BOT_TRADING project (maturity 5.25/10 per `biopsy.md`) has three services — a Go Gateway, a Rust matching Engine, and a Python Analysis brain — communicating via SBE/Parquet. The quantitative infrastructure is substantial: 150+ technical indicators (`analysis/src/quant/indicators.py`), a signal aggregation pipeline (`signal_processor.py`), candlestick and channel pattern detectors, fractional differencing for stationarity, triple-barrier labeling, and a risk management system with Kelly Criterion sizing.

However, the ML/AI brain is rudimentary:

- **GoliathTransformer** (`analysis/src/ml/models/goliath_transformer.py`): A vanilla 6-layer Transformer encoder (d_model=256, nhead=8, dim_feedforward=1024). It uses only the last timestep `output[:, -1, :]` for classification into 3 classes (Up/Down/Neutral). Prior to our fix, it was missing PositionalEncoding entirely — making training impossible.
- **GoliathTransformerV2** (`analysis/goliath_trainer_v2.py`): Adds a triple-head (direction + TP/SL + confidence) with a learnable positional encoding (`nn.Parameter`), but lives in a standalone trainer script rather than as a reusable model module.
- **LiT Model** (`analysis/src/ml/models/lit.py`): A clean LSTM+Transformer hybrid (parallel branches fused via concatenation), but with no attention to regularization, confidence gating, or multi-expert reasoning.
- **NeuralTrader** (`analysis/src/quant/neural_trader.py`): A NumPy-only approximation of what should be a PyTorch model. Uses `IndicatorScaler` with hardcoded per-indicator bounds and a `sigmoid` approximation via NumPy. Cannot actually learn.

The **AI_BIOPSY documents** dissect a production CS2 coaching AI (10,000+ LOC, 45+ files) with battle-tested patterns that directly address every weakness above: adaptive learning with maturity gating, episodic memory (COPER), multi-expert reasoning (MoE with SuperpositionLayer), drift detection, confidence-gated output, JEPA self-supervised pre-training, and a silence rule that prevents bad outputs. The **solutions.md** document proposes complementary upgrades: T-Mamba (Mamba SSM hybrid), TFT multi-horizon forecasting, DRL ensemble, Feature Registry, BacktestEngine v2, and gRPC signal bridge.

This plan transfers the most impactful architectural patterns from both documents into the trading domain. We prioritize patterns that yield the largest quality gains with the least risk, and we explicitly sequence work so that each phase produces a testable, self-contained improvement before the next phase begins.

**Guiding principles:**
- Super slow, methodical approach (user's explicit request)
- Each phase produces testable, self-contained improvements
- No existing working functionality is broken
- We fix P0 blockers as prerequisites, not as separate work
- Read in small batches, write in small batches, never rush

---

## 2. Source Document Cross-Reference

Every architectural decision below traces to specific source material. This section maps CS2 patterns to trading equivalents:

| CS2 Pattern (AI_BIOPSY) | Source Location | Trading Equivalent | Rationale |
|---|---|---|---|
| RAP 6-Layer Architecture | AI_BIOPSY.md §6.3 | 4-Layer TradingBrain | Drop Position/Communication (no spatial/coaching in trading) |
| JEPA Pre-Training (InfoNCE) | AI_BIOPSY.md §6.4 | Market structure pre-training | We have far more unlabeled bars than labeled trades |
| 3-Tier Maturity Gate | AI_BIOPSY.md §8.1 | Identical (50%/80%/100% ceilings) | A model that says "I don't know" beats random guessing |
| COPER Experience Bank | AI_BIOPSY.md §8.2 | Trade experience episodic memory | Retrieve past trades in similar market conditions |
| 4-Tier Fallback | AI_BIOPSY.md §8.2 | COPER→ML→Signals→Conservative | Never return nothing; degrade gracefully |
| MoE + SuperpositionLayer | AI_BIOPSY.md §6.3.3 | 4 market-regime experts | Trend/MeanReversion/Breakout/Range specialization |
| Meta-Drift Surveillance | AI_BIOPSY_PART2.md §3.7 | Feature distribution drift | Markets change regime; stale models are dangerous |
| Silence Rule (4 conditions) | AI_BIOPSY_PART2.md §3.8 | Identical transfer | "Prefer no trade over bad trade" |
| Momentum Tracker | AI_BIOPSY_PART2.md §3.4 | Position sizing by streak | Hot/cold streaks adjust risk appetite |
| Blind Spot Detector | AI_BIOPSY_PART2.md §3.5 | Recurring mistake detection | Identify systematic errors for retraining |
| 19-dim Feature Contract | AI_BIOPSY.md §6.1 | Feature Registry pattern | Prevent silent feature parity drift |
| T-Mamba (SSM Hybrid) | solutions.md §3.1 | Deferred to Phase 5+ | O(n) complexity, but needs CUDA; GRU fallback |
| DRL Ensemble | solutions.md §3.3 | Deferred to Phase 5+ | PPO/SAC/A2C regime-switching; complex dependency |

---

## 3. Phase 1: Foundation & P0 Fixes (Prerequisite)

All downstream ML work depends on these fixes. Each is small, self-contained, and independently testable.

### 3.1 Fix GoliathTransformer PositionalEncoding (TD-010)

**Status:** ALREADY COMPLETED in prior session.

**What was done:** Added sinusoidal `PositionalEncoding` class to `analysis/src/ml/models/goliath_transformer.py`. The implementation uses standard sin/cos interleaving from "Attention Is All You Need" (Vaswani et al. 2017). The positional encoding tensor is registered as a buffer (not a parameter) so it persists across `model.state_dict()` saves but does not receive gradients.

**Exact implementation (already in file):**
```python
class PositionalEncoding(nn.Module):
    def __init__(self, d_model: int, max_len: int = 5000, dropout: float = 0.1):
        super().__init__()
        self.dropout = nn.Dropout(p=dropout)
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(
            torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model)
        )
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        pe = pe.unsqueeze(1)  # (max_len, 1, d_model) for seq-first format
        self.register_buffer('pe', pe)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = x + self.pe[:x.size(0)]
        return self.dropout(x)
```

**Why seq-first format:** GoliathTransformer permutes input to `(Seq, Batch, d_model)` before positional encoding (line 110: `x = x.permute(1, 0, 2)`), then permutes back. The PE buffer shape `(max_len, 1, d_model)` broadcasts correctly over the batch dimension.

**Verification:** `pytest analysis/tests/test_models.py::TestPositionalEncoding` — 3 tests (shape, different positions get different encodings, deterministic without dropout). Forward pass sanity: `GoliathTransformer(GoliathConfig(input_dim=10))(torch.randn(2, 64, 10))` → shape `(2, 3)`.

---

### 3.2 Python Test Suite Bootstrap (TD-006)

**Status:** PARTIALLY COMPLETED. Test files written, dependencies not yet installed.

**Files created:**
- `analysis/tests/__init__.py` — empty module marker
- `analysis/tests/conftest.py` — shared fixtures
- `analysis/tests/test_indicators.py` — 16 tests across 10 test classes
- `analysis/tests/test_signal_processor.py` — 8 tests across 5 test classes
- `analysis/tests/test_models.py` — 11 tests across 3 test classes

**Fixture design** (`conftest.py`): The `ohlcv_df` fixture generates 200 rows of synthetic Gold-like data (base price ~1800, hourly frequency, log-normal volume). 200 rows is enough for the largest rolling window (SMA_200 needs exactly 200 bars). The `price_series` fixture extracts just the close prices. Random seed is fixed at 42 for reproducibility.

**Test coverage strategy:** These are smoke tests, not exhaustive. They verify:
1. **Indicators** — output lengths match input, NaN behavior after warmup, value bounds (RSI 0-100, ADX 0-100), MACD histogram = line - signal, Bollinger upper >= lower, ATR non-negative, SMA middle band identity
2. **Features** — FFD weight[0] == 1.0, d=0 is identity transform, triple-barrier labels in {-1, 0, 1}
3. **Patterns** — returns DataFrame, pattern columns are boolean
4. **Signal Processor** — Signal/AggregatedSignal dataclass creation, extract_indicator_signals returns list of Signal objects, aggregate_signals on empty list returns NEUTRAL/0.0, single bullish signal correctly counted, round-trip pipeline OHLCV→Indicators→Signals→Aggregation
5. **Models** — PositionalEncoding shape/determinism, GoliathTransformer output shape/NaN-free/gradient flow/batch-size-1/context-dim, LiTModel output shape/NaN-free/multi-class/gradient flow

**Remaining work:** Install dependencies (`pip install pytest numpy pandas torch loguru scipy` inside the project venv), then run `pytest analysis/tests/ -v`. Fix any import errors or assertion failures before proceeding to Phase 1.3.

---

### 3.3 Feature Registry Pattern

**Why this matters (from AI_BIOPSY.md §6.1):** The CS2 system enforces a strict 19-dimensional feature vector contract (`METADATA_DIM = 19`) between all components. Every feature has a defined name, position, dtype, and valid range. When any component adds or removes a feature, the contract breaks loudly at import time — not silently at inference time.

Our system has no such contract. Features are assembled ad-hoc in `neural_decision.py:assemble_feature_vector()` (lines 82-166). The function manually iterates over `indicator_cols = ['rsi', 'stoch_k', 'stoch_d', 'cci', 'adx', 'atr', 'bb_position']`, then appends MACD features, pattern features (8 binary flags), channel features (4 values), and S/R proximity features (2 values). This produces a variable-length feature vector depending on which columns exist in the DataFrame. If any indicator name changes upstream in `indicators.py`, the feature vector silently drops that feature with no error.

**Existing code to formalize (in `neural_decision.py`):**
- `indicator_cols` list at line 106 — 7 indicators
- `normalize_value()` at line 169 — per-indicator min/max ranges
- `pattern_list` at line 128 — 8 patterns
- Channel encoding at lines 138-153 — 4 features
- S/R proximity at lines 156-158 — 2 features
- **Total: ~23 features**, but the exact count varies at runtime

**New file:** `analysis/src/quant/feature_registry.py`

**Architecture (inspired by CS2's METADATA_DIM contract + solutions.md §2.1):**

```python
@dataclass(frozen=True)
class FeatureSpec:
    name: str                     # e.g., "ind_rsi"
    dtype: str                    # "float32" | "bool"
    valid_range: Tuple[float, float]  # (min, max) for validation
    category: str                 # "indicator" | "pattern" | "channel" | "sr" | "macro"
    required: bool = True         # If True, missing = ValueError
    default: float = 0.0          # Fallback value if not required

class FeatureRegistry:
    _instance: Optional['FeatureRegistry'] = None  # Singleton

    @classmethod
    def get_instance(cls) -> 'FeatureRegistry':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self._schema: Dict[str, FeatureSpec] = {}
        self._register_defaults()

    def _register_defaults(self):
        # Indicator features (from neural_decision.py indicator_cols)
        for name, (lo, hi) in [
            ("ind_rsi", (0, 100)), ("ind_stoch_k", (0, 100)),
            ("ind_stoch_d", (0, 100)), ("ind_cci", (0, 100)),
            ("ind_adx", (0, 100)), ("ind_atr", (0, 100)),
            ("ind_bb_position", (0, 100)), ("ind_macd_diff", (0, 100)),
            ("ind_macd_momentum", (0, 100)),
        ]:
            self.register(FeatureSpec(name, "float32", (lo, hi), "indicator"))

        # Pattern features (from neural_decision.py pattern_list)
        for pat in ["doji", "hammer", "engulfing_bullish", "engulfing_bearish",
                     "morning_star", "evening_star", "double_top", "double_bottom"]:
            self.register(FeatureSpec(f"pat_{pat}", "bool", (0, 100), "pattern"))

        # Channel features
        for ch in ["chan_ascending", "chan_descending", "chan_horizontal"]:
            self.register(FeatureSpec(ch, "bool", (0, 100), "channel"))
        self.register(FeatureSpec("chan_position", "float32", (0, 100), "channel"))

        # S/R features
        self.register(FeatureSpec("sr_support_dist", "float32", (0, 100), "sr"))
        self.register(FeatureSpec("sr_resistance_dist", "float32", (0, 100), "sr"))

    def register(self, spec: FeatureSpec):
        self._schema[spec.name] = spec

    def validate_parity(self, feature_names: List[str]) -> bool:
        required = {n for n, s in self._schema.items() if s.required}
        provided = set(feature_names)
        missing = required - provided
        if missing:
            raise ValueError(f"Feature Parity VIOLATION: missing {missing}")
        return True

    def validate_values(self, feature_dict: Dict[str, float]) -> Dict[str, float]:
        validated = {}
        for name, value in feature_dict.items():
            spec = self._schema.get(name)
            if spec:
                lo, hi = spec.valid_range
                validated[name] = max(lo, min(hi, value))
            else:
                validated[name] = value  # pass through unknown features
        return validated

    @property
    def expected_dim(self) -> int:
        return len(self._schema)

    def get_ordered_names(self) -> List[str]:
        return list(self._schema.keys())
```

**Integration point:** The existing `assemble_feature_vector()` in `neural_decision.py` will be updated to use `FeatureRegistry.get_instance()` for validation, but the actual computation logic stays in place. The registry is a contract layer, not a replacement for computation.

**Tests:** `test_feature_registry.py` — registry singleton, validate_parity raises on missing required feature, validate_values clamps out-of-range, expected_dim matches default count (23 features), register custom feature extends schema.

---

## 4. Phase 2: Core AI Architecture (The Brain)

This phase builds the new multi-layer model architecture, self-supervised pre-training, and maturity gating. Each component is independently testable and doesn't break existing models.

### 4.1 Multi-Layer TradingBrain Model (inspired by RAP 6-Layer)

**Why:** The CS2 RAP Coach uses 6 specialized processing layers: Perception (3-stream CNN: View ResNet[3,4,6,3]→64-dim, Map ResNet[2,2]→32-dim, Motion Conv→32-dim → total 128-dim), Memory (LTC AutoNCP 288 units + Hopfield 4-head 256-dim + Belief Head 256→SiLU→64), Strategy (4 MoE experts with SuperpositionLayer(256→128, context_dim=18)→ReLU→Linear(128→10) + Gate Linear(256→4)→Softmax), Pedagogy (Value Critic Linear(256→64→1) + CausalAttributor 5-dim), Position (Linear(256→3)), Communication (template selector).

Our trading brain should have analogous specialized stages rather than one monolithic transformer. We drop Position and Communication (no spatial movement or user-facing text in trading), keeping 4 layers.

**New file:** `analysis/src/ml/models/trading_brain.py`

**Detailed architecture:**

```
Layer 1 — Perception (Multi-Stream Input Encoding)
├── Price Stream:
│   - Input: raw OHLCV (batch, seq, 5)
│   - 1D Conv1d(5, 64, kernel=3, padding=1) → BatchNorm1d → GELU
│   - 1D Conv1d(64, 64, kernel=3, padding=1) → BatchNorm1d → GELU
│   - Output: (batch, seq, 64)
│   - Analogy: CS2 View CNN (ResNet processing visual frames)
│
├── Indicator Stream:
│   - Input: computed indicators (batch, seq, n_indicators)
│   - Linear(n_indicators, 96) → LayerNorm → GELU → Dropout(0.1)
│   - Output: (batch, seq, 96)
│   - Analogy: CS2 Map embedding (structured spatial data)
│
├── Volume/Volatility Stream:
│   - Input: volume + ATR + BB_bandwidth + returns (batch, seq, 4)
│   - Linear(4, 32) → LayerNorm → GELU
│   - Output: (batch, seq, 32)
│   - Analogy: CS2 Motion encoding (dynamic state changes)
│
└── Concatenation + Projection:
    - Cat: (batch, seq, 64+96+32) = (batch, seq, 192)
    - Linear(192, 256) → LayerNorm
    - Output: (batch, seq, 256)
    - Note: CS2 uses 128-dim total; we use 256-dim because
      financial features have higher dimensionality than game frames.

Layer 2 — Memory (Temporal + Associative Pattern Recall)
├── Sequential Memory (LSTM):
│   - LSTM(input_size=256, hidden_size=128, num_layers=2,
│          batch_first=True, dropout=0.2)
│   - Takes full sequence, outputs (batch, seq, 128)
│   - Analogy: CS2 LTC AutoNCP 288 units (sequential state tracking)
│   - Reuse: LiTModel (lit.py) already has an LSTM branch with
│     similar structure — we match its pattern
│
├── Associative Memory (Self-Attention):
│   - MultiheadAttention(embed_dim=128, num_heads=4, dropout=0.1,
│                         batch_first=True)
│   - Input: LSTM output (batch, seq, 128)
│   - Query=Key=Value=LSTM_output (self-attention for pattern recall)
│   - Output: (batch, seq, 128)
│   - Analogy: CS2 Hopfield network (4 heads, 256-dim).
│     Modern Hopfield networks are equivalent to attention with
│     specific energy functions. Self-attention here serves the
│     same role: recalling similar past patterns from the sequence.
│
├── Fusion:
│   - Cat(LSTM_out, Attention_out) → (batch, seq, 256)
│   - Linear(256, 256) → LayerNorm → GELU
│   - Residual: output = output + perception_output
│   - Output: (batch, seq, 256)
│   - Note: CS2 Memory layer also includes a Belief Head (256→SiLU→64)
│     for estimating hidden enemy state. We don't have "hidden state"
│     in markets, but drift detection (Phase 3) serves a similar role.

Layer 3 — Strategy (Mixture of Experts with Context Gating)
├── Expert Networks (4 specialists):
│   - Expert_Trend:         Linear(256,128)→LayerNorm→ReLU→Linear(128,64)
│   - Expert_MeanReversion: Linear(256,128)→LayerNorm→ReLU→Linear(128,64)
│   - Expert_Breakout:      Linear(256,128)→LayerNorm→ReLU→Linear(128,64)
│   - Expert_Range:         Linear(256,128)→LayerNorm→ReLU→Linear(128,64)
│   - Each expert outputs (batch, 64) from the last timestep
│   - Analogy: CS2 MoE has 3 experts: Linear(128→128)→LayerNorm→ReLU→
│     Linear(128→output_dim), gated by softmax. We use 4 experts
│     matching the 4 market regimes from solutions.md §3.3.
│
├── Gating Network:
│   - Input: memory_output[:, -1, :] → (batch, 256)
│   - Gate: Linear(256, 4) → Softmax  →  (batch, 4)
│   - Analogy: CS2 gate_network = Linear(256, 4) → Softmax
│   - The gate learns to route to the expert best suited for
│     the current market regime. During trending markets, the
│     Trend expert gets the highest gate weight.
│
├── SuperpositionLayer (Context-Gated Masking):
│   - From AI_BIOPSY.md §6.3.3: "output = F.linear(x, weight, bias)
│     * sigmoid(context_gate(context))"
│   - context_gate: Linear(context_dim, 256) where context_dim = number
│     of macro/regime features (e.g., ADX, ATR_ratio, VIX, DXY if available)
│   - The sigmoid gate selectively masks strategy dimensions based on
│     current market context. This is the key innovation: it allows the
│     model to "silence" certain strategy aspects when context says
│     they're irrelevant (e.g., suppress breakout features during
│     low-volatility range-bound markets).
│   - L1 sparsity loss on gate weights (lambda=1e-4) encourages
│     the gate to be selective, not always-on.
│
├── Expert Aggregation:
│   - stacked_experts: (batch, 4, 64)
│   - gate_weights:     (batch, 4, 1)
│   - weighted_sum = (stacked_experts * gate_weights).sum(dim=1) → (batch, 64)
│   - Project: Linear(64, 256) → LayerNorm
│   - Apply SuperpositionLayer mask
│   - Output: (batch, 256)

Layer 4 — Decision (Value + Direction + Confidence)
├── Value Critic:
│   - Linear(256, 64) → ReLU → Linear(64, 1)
│   - Estimates expected return (regression)
│   - Analogy: CS2 Pedagogy layer Value Critic
│     (Linear(256→64)→ReLU→Linear(64→1))
│   - Output: (batch, 1)
│
├── Direction Head:
│   - Linear(256, 64) → ReLU → Linear(64, 3)
│   - 3-class classification: Long / Hold / Short
│   - Output: (batch, 3) — raw logits, softmax applied in loss
│   - Analogy: CS2 output_dim=3 position recommendations
│
├── Confidence Head:
│   - Linear(256, 64) → ReLU → Linear(64, 1) → Sigmoid
│   - Outputs [0, 1] confidence score
│   - This is the raw confidence BEFORE maturity gating (Phase 2.3)
│   - Analogy: Not explicitly in CS2, but the maturity gate system
│     effectively creates a confidence ceiling. Having an explicit
│     learned confidence head is stronger because the model can learn
│     when its own predictions are unreliable.
│   - Output: (batch, 1)
│
└── Combined Output:
    - TradingBrainOutput(direction=(batch,3), value=(batch,1),
                          confidence=(batch,1))
    - Composite Loss (from AI_BIOPSY.md §7):
      L_total = L_direction(CrossEntropy with label_smoothing=0.1)
              + 0.5 × L_value(MSE)
              + 0.3 × L_confidence(BCE vs actual outcome correctness)
              + 1e-4 × L_sparsity(L1 on MoE gate weights)
```

**Reuse from existing code:**
- `lit.py` LiTModel: Its parallel LSTM+Transformer fusion pattern directly maps to our Memory layer. We can extract its `input_proj → LSTM branch → Transformer branch → fusion` skeleton.
- `goliath_transformer.py` GoliathTransformer: Its `input_projection → pos_encoder → transformer_encoder → decoder` flow is preserved in the Perception+Decision layers, but with multi-stream inputs rather than a single linear projection.
- `goliath_trainer_v2.py` GoliathTransformerV2: Its triple-head pattern (direction + TP/SL + confidence) maps to our Decision layer, though we add a value critic.

**Parameter count estimate:** ~2.4M parameters at d_model=256, which is reasonable for the amount of data we'll have after JEPA pre-training.

---

### 4.2 JEPA Self-Supervised Pre-Training

**Why this is the highest-impact transfer:** The CS2 system's JEPA (Joint Embedding Predictive Architecture) module in AI_BIOPSY.md §6.4 is arguably its most powerful training innovation. It allows the model to learn meaningful representations from unlabeled data using InfoNCE contrastive loss. In trading, we have vastly more unlabeled market data (years of tick/bar data) than labeled trade outcomes. JEPA lets us pre-train the Perception and Memory layers on raw market sequences before fine-tuning on labeled triple-barrier data.

**CS2 exact architecture (from AI_BIOPSY.md):**
- Online Encoder: `Linear(input, 512) → LayerNorm → GELU → Dropout(0.1) → Linear(512, 256) → LayerNorm`
- Target Encoder: Deep copy of online encoder, updated via EMA (τ=0.996)
- Predictor: `Linear(256, 512) → LayerNorm → GELU → Dropout(0.1) → Linear(512, 256)`
- Loss: InfoNCE with temperature τ=0.07
- Selective Decoding: Skip processing when cosine_distance < 0.05 (already-well-represented states)
- Retrain trigger: drift > 2.5σ

**New file:** `analysis/src/ml/training/jepa.py`

**Trading adaptation:**

```python
class JEPAPreTrainer(nn.Module):
    def __init__(self, perception_layer, d_model=256, tau=0.996, temperature=0.07):
        # Online encoder: perception_layer (reusing Layer 1 of TradingBrain)
        # + projection: Linear(d_model, 512) → LayerNorm → GELU → Dropout(0.1)
        #              → Linear(512, 256) → LayerNorm
        # Target encoder: deepcopy(online_encoder), EMA-updated
        # Predictor: Linear(256, 512) → LayerNorm → GELU → Dropout(0.1)
        #           → Linear(512, 256)

    @torch.no_grad()
    def update_target(self):
        # EMA update: for each parameter pair (online, target):
        #   target.data = tau * target.data + (1 - tau) * online.data
        # tau=0.996 means target moves slowly, providing a stable
        # learning signal. This is identical to BYOL/MoCo momentum.

    def info_nce_loss(self, online_proj, target_proj, temperature=0.07):
        # Normalize: online_norm = F.normalize(online_proj, dim=-1)
        #            target_norm = F.normalize(target_proj, dim=-1)
        # Similarity matrix: sim = online_norm @ target_norm.T / temperature
        # Labels: diagonal (positive pairs = same market state at t and t+1)
        # Loss: F.cross_entropy(sim, labels)
        # This pushes adjacent market windows together in embedding space
        # and pushes random windows apart.

    def selective_decode(self, online_repr, target_repr):
        # cosine_dist = 1 - F.cosine_similarity(online, target)
        # if cosine_dist < 0.05: skip (already well-represented)
        # This saves compute on "boring" market states (e.g., flat
        # overnight sessions) and focuses learning on informative
        # transitions (breakouts, reversals, volatility spikes).

    def pretrain_step(self, x_t, x_t1):
        # x_t, x_t1: adjacent market windows (positive pair)
        # 1. online_repr = online_encoder(x_t)
        # 2. predicted = predictor(online_repr)
        # 3. with torch.no_grad(): target_repr = target_encoder(x_t1)
        # 4. if selective_decode says skip: return 0 loss
        # 5. loss = info_nce_loss(predicted, target_repr)
        # 6. update_target()
        # 7. return loss
```

**Data source:** `etl_pipeline.py:create_sequences()` (line 173) already produces sliding-window sequences with default features `['close_fracdiff', 'returns', 'volatility', 'rsi', 'macd', ...]`. JEPA will consume these sequences in adjacent pairs: `(seq[i], seq[i+1])` as positive pairs, random sequences as negatives.

**Pre-training protocol:**
1. Load all available Parquet data via `etl_pipeline.py:load_parquet_files()`
2. Process through `compute_all_indicators()` and `create_sequences()`
3. JEPA pre-trains for 50-100 epochs on unlabeled sequences
4. Monitor: loss should decrease; cosine similarity of adjacent windows should increase
5. After pre-training, freeze Perception layer weights and fine-tune Memory+Strategy+Decision on labeled triple-barrier data

**Verification:** Pre-training loss decreases monotonically over 100 steps on synthetic data. Cosine similarity between adjacent windows increases from ~0 to >0.5.

---

### 4.3 Maturity Gating System (3-Tier)

**Why:** From AI_BIOPSY.md §8.1: the CS2 system never outputs full-confidence predictions until it has accumulated enough demonstration data. The exact thresholds are: CALIBRATING (0-49 samples, max 50% confidence), LEARNING (50-199, max 80%), MATURE (200+, 100%). There is also a "10/10 prerequisite rule" — the system must have processed at least 10 demonstrations before any inference.

In trading, this pattern is critical. A newly deployed model should not make full-size trades until it has proven itself on sufficient live data. The maturity gate sits between the model's raw confidence output and the decision engine.

**New file:** `analysis/src/ml/confidence/maturity.py`

**Detailed specification:**

```python
class MaturityTier(Enum):
    CALIBRATING = "calibrating"  # 0-49 samples seen
    LEARNING = "learning"        # 50-199 samples seen
    MATURE = "mature"            # 200+ samples seen

TIER_CEILINGS = {
    MaturityTier.CALIBRATING: 0.50,  # Max 50% confidence passthrough
    MaturityTier.LEARNING: 0.80,     # Max 80% confidence passthrough
    MaturityTier.MATURE: 1.00,       # Full confidence passthrough
}

TIER_THRESHOLDS = {
    MaturityTier.CALIBRATING: 0,
    MaturityTier.LEARNING: 50,
    MaturityTier.MATURE: 200,
}

class MaturityGate:
    def __init__(self):
        self.samples_seen: int = 0
        self.tier: MaturityTier = MaturityTier.CALIBRATING
        self._retrain_counter: int = 0

    def record_sample(self):
        self.samples_seen += 1
        self._retrain_counter += 1
        self._update_tier()
        # 10/10 rule: trigger retrain every 10 samples until mature
        if self.tier != MaturityTier.MATURE and self._retrain_counter >= 10:
            self._retrain_counter = 0
            return True  # Signal: retrain needed
        return False

    def gate(self, raw_confidence: float) -> float:
        ceiling = TIER_CEILINGS[self.tier]
        return min(raw_confidence, ceiling)

    def _update_tier(self):
        if self.samples_seen >= TIER_THRESHOLDS[MaturityTier.MATURE]:
            self.tier = MaturityTier.MATURE
        elif self.samples_seen >= TIER_THRESHOLDS[MaturityTier.LEARNING]:
            self.tier = MaturityTier.LEARNING
```

**Integration point:** The maturity gate sits between `TradingBrain.confidence_head` output and `neural_decision.py:CONFIDENCE_THRESHOLDS`. The raw model confidence (0-1) is gated by `maturity_gate.gate()`, then compared against the action thresholds (85% for STRONG_BUY, 70% for BUY, etc.).

**Reuse:** `neural_decision.py` already has `CONFIDENCE_THRESHOLDS = {STRONG_BUY: 85, BUY: 70, ...}` at line 62. The maturity gate does not replace these thresholds — it caps the input to them.

---

## 5. Phase 3: Reasoning Intelligence

These components add meta-cognition: the system reasons about its own performance, detects when its models are stale, and knows when to stay silent.

### 5.1 COPER Experience Bank (Episodic Memory)

**Source:** AI_BIOPSY.md §8.2 describes COPER (Context-Oriented Personalized Experience Retrieval) with SHA256[:16] context hashing, 4 retrieval strategies, EMA effectiveness feedback (0.7 × old + 0.3 × new), and 90-day stale decay.

**New file:** `analysis/src/ml/memory/coper.py`

**Data model:**
```python
@dataclass
class TradeExperience:
    id: str                        # UUID
    context_hash: str              # SHA256[:16] of market state vector
    market_state: Dict[str, float] # regime, volatility, trend, key indicators
    decision: str                  # "LONG" | "SHORT" | "HOLD"
    entry_price: float
    exit_price: float
    pnl: float                     # Realized PnL
    effectiveness: float           # EMA-smoothed score, starts at 0.5
    timestamp: datetime
    symbol: str
    timeframe: str
```

**Context hashing (from AI_BIOPSY.md):** Hash the market state vector (regime label + top-5 indicator z-scores + volatility percentile + trend slope) using SHA256, truncate to 16 hex chars. Two market states with the same hash are considered "similar enough" for exact retrieval.

**4 retrieval strategies:**
1. **Semantic (cosine similarity):** Compute cosine similarity between current market state vector and all stored experience vectors. Return top-k by similarity. Weight: 0.6 in hybrid mode.
2. **Context Hash (exact match):** Look up experiences with identical SHA256[:16] hash. Fast O(1) lookup via dict. Weight: 0.4 in hybrid mode.
3. **Hybrid:** Combine semantic + hash scores: `0.6 × cosine_sim + 0.4 × hash_match`. This is the default strategy.
4. **Pattern (temporal):** Retrieve experiences from similar time patterns (same day-of-week, same session — Asian/London/NY). Useful for detecting intraday seasonality.

**Stale decay:** Experiences older than 90 days get their effectiveness multiplied by `exp(-0.01 × days_since)`. This ensures recent market conditions are weighted more heavily.

**Effectiveness feedback (EMA):** After each trade closes, update the originating experience's effectiveness: `new_eff = 0.7 × old_eff + 0.3 × outcome_score` where outcome_score = 1.0 for profitable trade, 0.0 for loss, 0.5 for break-even.

**Storage:** JSON file on disk (simple, no database dependency). Max 10,000 experiences; oldest get pruned when limit is reached.

**Reuse:** `signal_processor.py:AggregatedSignal` (line 49) provides the market state snapshot for context hashing. Its fields `direction`, `confidence`, `bullish_count`, `bearish_count`, `dominant_timeframe` directly feed into the market state vector.

---

### 5.2 Meta-Drift Surveillance

**Source:** AI_BIOPSY_PART2.md §3.7 — MetaDriftSurveillance with `stat_drift = |recent - historical| / historical / 0.20` (20% shift = max drift), `spatial_drift` (mapped to feature distribution drift in trading), `combined = 0.4 × stat + 0.6 × distribution`, `confidence_adjustment = 1.0 - (drift × 0.5)`, floor at 50%.

**New file:** `analysis/src/ml/confidence/drift.py`

**Architecture:**

```python
class DriftDetector:
    def __init__(self, window_size: int = 100):
        self.stat_window: deque = deque(maxlen=window_size)
        self.baseline_stats: Dict[str, float] = {}  # Set during training
        self.feature_distributions: Dict[str, np.ndarray] = {}  # Training-time histograms

    def set_baseline(self, training_predictions: np.ndarray,
                     training_features: pd.DataFrame):
        # Compute baseline stats: mean, std of predictions
        # Compute feature distribution histograms (50 bins per feature)
        # Store for comparison during inference

    def detect_stat_drift(self, recent_predictions: np.ndarray) -> float:
        # Compare recent prediction mean/std to baseline
        # stat_drift = |recent_mean - baseline_mean| / baseline_mean / 0.20
        # Clamped to [0, 1]. A 20% shift = max drift (1.0).

    def detect_distribution_drift(self, recent_features: pd.DataFrame) -> float:
        # For each feature: compute KL divergence between recent histogram
        # and training histogram
        # Average KL divergence across all features, normalized to [0, 1]
        # This catches regime shifts that stat drift might miss
        # (e.g., all predictions center around 0.5 but feature distributions
        # have completely changed)

    def combined_drift(self) -> float:
        stat = self.detect_stat_drift(np.array(self.stat_window))
        dist = self.detect_distribution_drift(self.recent_features)
        return 0.4 * stat + 0.6 * dist

    def adjust_confidence(self, raw_confidence: float) -> float:
        drift = self.combined_drift()
        adjustment = 1.0 - (drift * 0.5)
        return raw_confidence * max(adjustment, 0.5)  # Floor at 50%

    def should_retrain(self) -> bool:
        # Compute rolling z-score of drift values
        # If drift > 2.5σ above the historical mean drift: retrain
        return self.combined_drift() > self._retrain_threshold
```

**Reuse:** `features.py:compute_rolling_volatility()` provides volatility regime data. `indicators.py:adx()` indicates trend strength. Both feed into drift detection.

---

### 5.3 Silence Rule (4 Conditions)

**Source:** AI_BIOPSY_PART2.md §3.8 — "Prefer no output over bad output." Four conditions trigger silence.

**New file:** `analysis/src/ml/confidence/silence.py`

```python
class SilenceRule:
    def should_stay_silent(self,
                           maturity_gate: MaturityGate,
                           gated_confidence: float,
                           aggregated_signal: AggregatedSignal,
                           feature_z_scores: Dict[str, float]
                           ) -> Tuple[bool, str]:
        # Condition 1: Cold Start
        # If maturity_gate.tier == CALIBRATING AND samples_seen < 10:
        #   return (True, "cold_start: insufficient training data")

        # Condition 2: Low Confidence
        # If gated_confidence < 0.40:
        #   return (True, "low_confidence: gated confidence below 40%")

        # Condition 3: Neutral Deviation
        # If ALL feature z-scores have |z| < 1.0:
        #   return (True, "neutral_deviation: no indicator strongly deviates")
        # Z-score: (current_value - rolling_mean) / max(rolling_std, 0.01)
        # This is the trading equivalent of CS2's "no significant
        # deviation from expected behavior" check. If RSI is at 50,
        # MACD is near zero, ADX is middling — there's no signal.

        # Condition 4: Conflicting Signals
        # If |bullish_count - bearish_count| <= 1 AND both > 0:
        #   return (True, "conflicting_signals: bull/bear signals nearly equal")
        # From AggregatedSignal.bullish_count and .bearish_count

        return (False, "")
```

**Z-score computation (from AI_BIOPSY_PART2.md §3.1):** For each indicator, compute `z = (current_value - rolling_mean_50) / max(rolling_std_50, 0.01)`. If `|z| > 1.0`, the indicator has a "significant deviation" worth acting on. The logistic CDF approximation `1/(1+exp(-1.702×z))` converts this to a percentile, though for the silence rule we only need the raw z-score magnitude check.

**Reuse:** `signal_processor.py:AggregatedSignal` already tracks `bullish_count` and `bearish_count` — these feed directly into Condition 4.

---

### 5.4 Momentum Tracker + Blind Spot Detector

**Source:** AI_BIOPSY_PART2.md §3.4 (Momentum) and §3.5 (Blind Spots).

**New files:**
- `analysis/src/ml/reasoning/momentum.py`
- `analysis/src/ml/reasoning/blind_spots.py`

**Momentum Tracker specification:**
```python
class MomentumTracker:
    def __init__(self):
        self.momentum: float = 1.0     # Neutral starting point
        self.last_trade_time: datetime = None
        self.trade_history: List[Tuple[datetime, bool]] = []  # (time, is_win)

    def record_trade(self, is_win: bool, timestamp: datetime):
        # Time decay: if last_trade_time exists:
        #   gap_hours = (timestamp - last_trade_time).total_seconds() / 3600
        #   self.momentum *= exp(-0.15 * gap_hours)
        # Win: self.momentum += 0.05
        # Loss: self.momentum -= 0.04
        # Clamp: self.momentum = max(0.7, min(1.4, self.momentum))
        # Asymmetry: wins add +0.05, losses subtract -0.04
        # This means you need ~4 wins to recover from 3 losses.

    @property
    def is_tilted(self) -> bool:
        return self.momentum < 0.85  # Cold streak → reduce sizing

    @property
    def is_hot(self) -> bool:
        return self.momentum > 1.2   # Hot streak → allow larger (capped)

    def adjust_position_size(self, base_size: float) -> float:
        if self.is_tilted:
            return base_size * 0.5   # Halve position during cold streak
        if self.is_hot:
            return base_size * 1.25  # 25% larger during hot streak (capped)
        return base_size * self.momentum  # Linear scaling in middle zone
```

**Blind Spot Detector specification:**
```python
@dataclass
class BlindSpot:
    pattern: str        # e.g., "late_breakout_entry", "ignores_divergence"
    frequency: int      # How many times this mistake occurred
    avg_impact: float   # Average PnL impact of this mistake
    priority: float     # frequency × avg_impact (absolute)
    examples: List[str] # Last 5 trade IDs where this occurred

class BlindSpotDetector:
    def __init__(self):
        self.blind_spots: Dict[str, BlindSpot] = {}

    def analyze_trade(self, trade_result, optimal_result):
        # Compare actual trade outcome vs what the optimal decision
        # would have been (computed via hindsight backtesting).
        # Detect patterns:
        # - "late_entry": entry was >3 bars after signal triggered
        # - "ignored_divergence": RSI/price divergence present but ignored
        # - "counter_trend": traded against dominant trend (ADX > 25)
        # - "oversize_on_tilt": position too large during momentum < 0.85
        # Each detected pattern gets its frequency incremented and
        # impact averaged.

    def get_top_blind_spots(self, k: int = 3) -> List[BlindSpot]:
        sorted_spots = sorted(self.blind_spots.values(),
                              key=lambda b: b.priority, reverse=True)
        return sorted_spots[:k]
```

---

## 6. Phase 4: Integration & Production Hardening

### 6.1 4-Tier Decision Fallback

**Source:** AI_BIOPSY.md §8.2 — "COPER → Hybrid ML+RAG → RAG Basic → Template." The system guarantees it never returns nothing. Each tier degrades gracefully.

**New file:** `analysis/src/ml/decision/fallback.py`

```python
class FallbackTier(Enum):
    COPER = 1       # Best: episodic memory retrieval
    ML_MODEL = 2    # Good: neural network prediction
    SIGNALS = 3     # Decent: weighted signal aggregation
    CONSERVATIVE = 4  # Safe: minimal exposure, widened stops

class FallbackDecisionEngine:
    def __init__(self, coper: COPERBank, brain: TradingBrain,
                 maturity: MaturityGate, silence: SilenceRule,
                 drift: DriftDetector, momentum: MomentumTracker):
        self.coper = coper
        self.brain = brain
        self.maturity = maturity
        self.silence = silence
        self.drift = drift
        self.momentum = momentum

    def decide(self, market_state, features_tensor, agg_signal) -> TradeDecision:
        # Tier 1: COPER (retrieve similar past experience)
        similar = self.coper.retrieve(market_state, k=5)
        best = max(similar, key=lambda e: e.effectiveness, default=None)
        if best and best.effectiveness > 0.7:
            return self._decision_from_experience(best, tier=FallbackTier.COPER)

        # Tier 2: ML Model (TradingBrain forward pass)
        output = self.brain(features_tensor)
        raw_conf = output.confidence.item()
        gated_conf = self.maturity.gate(raw_conf)
        drift_adjusted = self.drift.adjust_confidence(gated_conf)

        silent, reason = self.silence.should_stay_silent(
            self.maturity, drift_adjusted, agg_signal, ...)
        if not silent and drift_adjusted > 0.5:
            return self._decision_from_model(output, drift_adjusted,
                                              tier=FallbackTier.ML_MODEL)

        # Tier 3: Signal Aggregation (existing pipeline)
        if agg_signal.confidence > 40 and not silent:
            return self._decision_from_signals(agg_signal,
                                               tier=FallbackTier.SIGNALS)

        # Tier 4: Conservative Default (always returns something)
        return self._conservative_default(market_state,
                                           tier=FallbackTier.CONSERVATIVE)
```

**Reuse:** `neural_decision.py:generate_decision()` becomes the implementation backbone for Tier 3. `signal_processor.py:aggregate_signals()` feeds into it.

---

### 6.2 gRPC Signal Bridge (TD-003/TD-012)

**Source:** solutions.md §1.3 — Protobuf schema with SignalService, ModelVote, Direction enum.

**New files:**
- `analysis/proto/signal.proto`
- `analysis/src/integration/grpc_server.py`

**Proto schema (from solutions.md, adapted):**
```protobuf
syntax = "proto3";
package signal;

service SignalService {
    rpc GetSignal(SignalRequest) returns (SignalResponse);
    rpc StreamSignals(SignalRequest) returns (stream SignalResponse);
}

message SignalRequest {
    string symbol = 1;
    string timeframe = 2;
    int64 timestamp_ns = 3;
}

message SignalResponse {
    Direction direction = 1;
    double confidence = 2;
    string model_name = 3;
    int32 source_tier = 4;     // 1=COPER, 2=ML, 3=Signals, 4=Conservative
    double entry_price = 5;
    double stop_loss = 6;
    double take_profit = 7;
    double position_size_pct = 8;
}

enum Direction {
    HOLD = 0;
    LONG = 1;
    SHORT = 2;
}
```

**Python gRPC server:** Wraps the `FallbackDecisionEngine.decide()` method behind a gRPC interface. The Go Gateway (out of scope for code changes) would use the `SignalClient` from solutions.md §1.3 to connect.

**Note:** Gateway-side Go changes are out of scope for this plan (Python-side only).

---

### 6.3 Orchestrator (Tying It All Together)

**Source:** Inspired by CS2's AnalysisOrchestrator that runs 6 parallel analysis engines.

**New file:** `analysis/src/orchestrator.py`

```python
class TradingOrchestrator:
    """
    Central orchestration of the full analysis pipeline.
    Coordinates all components in the correct dependency order.
    """
    def __init__(self, config: OrchestratorConfig):
        self.feature_registry = FeatureRegistry.get_instance()
        self.brain = TradingBrain(config.brain_config)
        self.maturity = MaturityGate()
        self.drift = DriftDetector(window_size=100)
        self.silence = SilenceRule()
        self.momentum = MomentumTracker()
        self.coper = COPERBank(max_size=10000)
        self.blind_spots = BlindSpotDetector()
        self.fallback = FallbackDecisionEngine(
            self.coper, self.brain, self.maturity,
            self.silence, self.drift, self.momentum
        )

    def analyze(self, symbol: str, timeframe: str,
                ohlcv_df: pd.DataFrame) -> TradeDecision:
        # Step 1: Compute indicators
        df = compute_all_indicators(ohlcv_df)

        # Step 2: Detect patterns
        patterns = detect_all_patterns(ohlcv_df)

        # Step 3: Extract and aggregate signals
        signals = extract_indicator_signals(df, symbol, timeframe)
        pattern_signals = extract_pattern_signals(patterns, symbol, timeframe)
        agg = aggregate_signals(signals + pattern_signals, symbol=symbol)

        # Step 4: Assemble feature vector (via registry)
        features = assemble_feature_vector(df, patterns, {}, {}, symbol)
        self.feature_registry.validate_parity(features.feature_names)

        # Step 5: Create tensor for model
        sequences = create_sequences(df)
        features_tensor = torch.tensor(sequences[0][-1:], dtype=torch.float32)

        # Step 6: Check drift
        drift_level = self.drift.combined_drift()

        # Step 7: Run fallback decision engine
        decision = self.fallback.decide(
            market_state=self._build_market_state(df, agg),
            features_tensor=features_tensor,
            agg_signal=agg,
        )

        # Step 8: Adjust sizing by momentum
        decision.position_size_pct = self.momentum.adjust_position_size(
            decision.position_size_pct
        )

        # Step 9: Store experience for future COPER retrieval
        self.coper.store(self._build_experience(decision, agg))

        # Step 10: Log for blind spot analysis
        self.blind_spots.analyze_trade(decision, None)  # optimal computed later

        return decision
```

---

## 7. Implementation Order & Dependencies

```
Phase 1 (Foundation)         Phase 2 (Brain)              Phase 3 (Reasoning)         Phase 4 (Integration)

1.1 Fix PE [DONE]            2.1 TradingBrain model  -->  3.1 COPER Bank         -->  4.1 Fallback Engine
        |                        |                             |                          |
1.2 Test Suite [PARTIAL] --> 2.2 JEPA Pre-Training         3.2 Drift Detector     -->  4.2 gRPC Bridge
        |                        |                             |                          |
1.3 Feature Registry    -->  2.3 Maturity Gating      -->  3.3 Silence Rule       -->  4.3 Orchestrator
                                                               |
                                                           3.4 Momentum + Blind Spots
```

**Critical path:** 1.2 (finish tests) → 1.3 → 2.1 → 2.2 → 2.3 → 3.2 → 3.3 → 4.1 → 4.3

**Estimated step count:** ~15 implementation steps, each producing testable output.

---

## 8. Verification Plan

### Phase 1 Verification:
- `pytest analysis/tests/ -v` — all 35 tests pass
- GoliathTransformer forward pass: `model(torch.randn(2, 64, input_dim))` → shape `(2, 3)`, no NaNs
- Feature Registry: `registry.validate_parity(correct_names)` returns True; `validate_parity(missing_one)` raises ValueError; `registry.expected_dim == 23`

### Phase 2 Verification:
- TradingBrain forward pass: input `(batch=4, seq=50, features=23)` → output `TradingBrainOutput(direction=(4,3), value=(4,1), confidence=(4,1))`
- All outputs NaN-free; gradients flow to all named parameters
- JEPA pre-training: loss decreases over 100 steps on synthetic data; cosine similarity of adjacent windows increases from ~0 to >0.5
- Maturity gate: `MaturityGate(samples_seen=10).gate(0.95)` returns `0.50`; `MaturityGate(samples_seen=100).gate(0.95)` returns `0.80`; `MaturityGate(samples_seen=300).gate(0.95)` returns `0.95`

### Phase 3 Verification:
- COPER: store 10 experiences with varied market states; retrieve top-5 by cosine similarity; verify ordering is correct (most similar first); verify stale decay reduces effectiveness for 90+ day old experiences
- Drift: inject artificial distribution shift (multiply all features by 2.0); verify `combined_drift()` increases; verify `adjust_confidence()` reduces raw confidence
- Silence: verify all 4 conditions trigger independently: cold start (samples < 10), low confidence (<0.4), neutral deviation (all |z| < 1.0), conflicting signals (bull=bear=3)
- Momentum: simulate 5 consecutive wins → momentum should be ~1.25; simulate 5 consecutive losses → momentum should be ~0.80; verify `is_tilted` and `is_hot` flags

### Phase 4 Verification:
- Fallback: mock COPER with no experiences → falls to Tier 2; mock brain with low confidence → falls to Tier 3; mock signals with no signal → falls to Tier 4; verify each tier labels its source correctly
- gRPC: start Python server, use `grpcurl` to call `GetSignal("XAUUSD")`, verify response has all fields populated and direction is valid enum
- Orchestrator: end-to-end `analyze("XAUUSD", "H1", synthetic_ohlcv)` returns `TradeDecision` with all fields non-null and `source_tier` labeled

---

## 9. Composite Loss Function (Detailed)

The TradingBrain uses a composite loss inspired by CS2's `L_total = L_strategy + 0.5 × L_value + L_sparsity + L_position`:

```python
class TradingBrainLoss(nn.Module):
    def __init__(self, label_smoothing=0.1, value_weight=0.5,
                 confidence_weight=0.3, sparsity_weight=1e-4):
        super().__init__()
        self.direction_loss = nn.CrossEntropyLoss(label_smoothing=label_smoothing)
        self.value_loss = nn.MSELoss()
        self.confidence_loss = nn.BCELoss()
        self.value_weight = value_weight
        self.confidence_weight = confidence_weight
        self.sparsity_weight = sparsity_weight

    def forward(self, output, targets, gate_weights):
        # output: TradingBrainOutput(direction, value, confidence)
        # targets: (direction_label, return_value, was_correct)
        # gate_weights: (batch, 4) MoE gate weights

        L_direction = self.direction_loss(output.direction, targets.direction_label)
        L_value = self.value_loss(output.value.squeeze(), targets.return_value)
        L_confidence = self.confidence_loss(output.confidence.squeeze(),
                                             targets.was_correct.float())
        L_sparsity = gate_weights.abs().mean()  # L1 on MoE gate weights

        L_total = (L_direction
                   + self.value_weight * L_value
                   + self.confidence_weight * L_confidence
                   + self.sparsity_weight * L_sparsity)

        return L_total
```

**Why each term:**
- `L_direction` (CrossEntropy): Primary task — classify market direction. Label smoothing at 0.1 prevents overconfident predictions (a common failure mode in financial classification).
- `L_value` (MSE, weight=0.5): Auxiliary regression task — predict expected return magnitude. This grounds the model in actual PnL rather than just direction.
- `L_confidence` (BCE, weight=0.3): Calibration — train the confidence head to predict whether the direction prediction will be correct. This is trained against hindsight labels (was_correct = 1.0 if predicted direction matches actual, 0.0 otherwise).
- `L_sparsity` (L1, weight=1e-4): Regularization on MoE gate weights — encourages the model to specialize experts rather than blending them uniformly. From AI_BIOPSY.md §7: sparsity loss prevents "expert collapse" where all experts learn the same thing.

---

## 10. What We Are NOT Doing (Scope Exclusions)

These items are explicitly out of scope for this plan. Some are deferred to future iterations, others are inapplicable:

- **Game Tree / Expectiminimax (AI_BIOPSY_PART2.md §2.3):** 3-level game tree with 1000-node budget, 4 actions, opponent modeling. Too CS2-specific — markets don't have a discrete opponent making observable moves.
- **Causal Attribution 5-axis (AI_BIOPSY.md §6.3.4):** Mechanics/Positioning/Utility/Timing/Decision axes. Interesting but premature — need baseline model performance first.
- **Communication/Template layers (AI_BIOPSY.md §6.3.6):** Template-based text output for coaching. Not applicable to trading signals.
- **Frontend (AI_BIOPSY_FRONTEND.md):** Kivy desktop app for CS2. Entirely irrelevant.
- **Go gateway changes:** Python-side only for now. The Go `SignalClient` from solutions.md exists but modifying it is a separate scope.
- **Rust engine changes:** Out of scope for ML pipeline work.
- **DRL Ensemble (PPO/SAC/A2C, solutions.md §3.3):** Regime-aware RL ensemble. High potential but requires stable-baselines3 dependency, proper reward function design, and extensive hyperparameter tuning. Deferred to Phase 5+.
- **T-Mamba (solutions.md §3.1):** Mamba SSM hybrid with O(n) complexity. Requires `mamba-ssm` package which needs CUDA. GRU fallback exists but reduces the value proposition. Deferred to Phase 5+.
- **TFT Multi-Horizon (solutions.md §3.2):** Temporal Fusion Transformer with quantile loss. Requires `pytorch-forecasting` dependency. Deferred to Phase 5+.
- **LLM Sentiment Pipeline (solutions.md §3.4):** Requires external API (OpenRouter). Deferred.
- **Deception Index (AI_BIOPSY_PART2.md §2.5):** Fake flash + rotation feint + sound deception. CS2-specific, no trading equivalent.
- **Entropy Analyzer (AI_BIOPSY_PART2.md §3.3):** Shannon entropy on 32×32 grid for spatial analysis. Could be adapted to heatmap-style order flow analysis, but premature.
- **Win Probability NN (AI_BIOPSY_PART2.md §2.6):** 12-feature → Linear(64)→ReLU→Dropout→Linear(32)→ReLU→Linear(1)→Sigmoid. Could be useful for trade outcome prediction, but our TradingBrain value critic already serves this purpose.
- **7-Layer Learning Stack (AI_BIOPSY_PART2.md §3.9):** Hardcoded→CSV→Database→Map→COPER→RAG→Neural. We implement a simplified 4-tier version (COPER→ML→Signals→Conservative) which captures the key idea without the game-specific layers.

---

## 11. File Summary

**New files to create (12 total):**
| File | Phase | Purpose |
|---|---|---|
| `analysis/src/quant/feature_registry.py` | 1.3 | Feature contract singleton |
| `analysis/tests/test_feature_registry.py` | 1.3 | Registry tests |
| `analysis/src/ml/models/trading_brain.py` | 2.1 | 4-layer model |
| `analysis/src/ml/training/jepa.py` | 2.2 | JEPA pre-training |
| `analysis/src/ml/confidence/maturity.py` | 2.3 | 3-tier maturity gating |
| `analysis/src/ml/memory/coper.py` | 3.1 | Episodic memory bank |
| `analysis/src/ml/confidence/drift.py` | 3.2 | Distribution drift detection |
| `analysis/src/ml/confidence/silence.py` | 3.3 | 4-condition silence rule |
| `analysis/src/ml/reasoning/momentum.py` | 3.4 | Win/loss momentum tracker |
| `analysis/src/ml/reasoning/blind_spots.py` | 3.4 | Recurring mistake detection |
| `analysis/src/ml/decision/fallback.py` | 4.1 | 4-tier fallback engine |
| `analysis/src/orchestrator.py` | 4.3 | Central pipeline orchestrator |

**Existing files to modify (3 total):**
| File | Phase | Change |
|---|---|---|
| `analysis/src/ml/models/goliath_transformer.py` | 1.1 | Add PositionalEncoding [DONE] |
| `analysis/src/quant/neural_decision.py` | 1.3 | Use FeatureRegistry for validation |
| `analysis/src/quant/__init__.py` | 1.3 | Export FeatureRegistry |

**Proto files (1):**
| File | Phase | Purpose |
|---|---|---|
| `analysis/proto/signal.proto` | 4.2 | gRPC service definition |
