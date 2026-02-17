# Implementation Task Plan: AI Brain Architecture & ML Pipeline

> **Minimum document depth: 4000 words (non-negotiable)**
> **Approach: Super slow, methodical, small steps, never rush if confidence < 100%**
> **Source blueprint: `stateful-inventing-pebble.md`**

---

## 1. Current State Assessment

A thorough audit of the codebase against the plan in `stateful-inventing-pebble.md` reveals the following completion snapshot:

**Phase 1 — Foundation & P0 Fixes:**
- **1.1 PositionalEncoding (TD-010):** COMPLETED. `analysis/src/ml/models/goliath_transformer.py` contains a fully functional `PositionalEncoding` class using sinusoidal sin/cos interleaving (Vaswani et al. 2017). The buffer shape `(max_len, 1, d_model)` correctly broadcasts over the batch dimension in the seq-first permute/unpermute flow (lines 110-112). No work needed.
- **1.2 Python Test Suite (TD-006):** FILES WRITTEN, NOT VERIFIED. The test directory exists: `analysis/tests/conftest.py` (2 fixtures: `ohlcv_df` with 200 rows of synthetic Gold data at seed 42, and `price_series`), `test_indicators.py` (16 tests across 10 classes), `test_signal_processor.py` (8 tests across 5 classes), `test_models.py` (11 tests across 3 classes). Total: 35 tests. However, these have never been run — no evidence of `pytest` execution output exists. Dependencies (`pytest`, `numpy`, `pandas`, `torch`, `loguru`, `scipy`) are listed in `requirements.txt` but installation status inside the venv is unknown.
- **1.3 Feature Registry:** NOT STARTED. `analysis/src/quant/feature_registry.py` does not exist. `neural_decision.py:assemble_feature_vector()` still uses the ad-hoc `indicator_cols` list at line 106 with no registry validation. The `__init__.py` has no `FeatureRegistry` export.

**Phase 2 — Core AI Architecture:**
- **2.1 TradingBrain Model:** NOT STARTED. `analysis/src/ml/models/trading_brain.py` does not exist. The `analysis/src/ml/` directory has no `__init__.py`, no subdirectories beyond `models/`. The existing `lit.py` (LSTM+Transformer hybrid, 100 LOC) and `goliath_transformer.py` (6-layer vanilla Transformer, 152 LOC) provide reusable skeletons.
- **2.2 JEPA Pre-Training:** NOT STARTED. `analysis/src/ml/training/` directory does not exist.
- **2.3 Maturity Gating:** NOT STARTED. `analysis/src/ml/confidence/` directory does not exist.

**Phase 3 — Reasoning Intelligence:**
- **3.1 COPER Bank:** NOT STARTED. `analysis/src/ml/memory/` directory does not exist.
- **3.2 Drift Detector:** NOT STARTED.
- **3.3 Silence Rule:** NOT STARTED.
- **3.4 Momentum + Blind Spots:** NOT STARTED. `analysis/src/ml/reasoning/` directory does not exist.

**Phase 4 — Integration:**
- **4.1 Fallback Engine:** NOT STARTED. `analysis/src/ml/decision/` directory does not exist.
- **4.2 gRPC Bridge:** NOT STARTED. `analysis/proto/` directory does not exist.
- **4.3 Orchestrator:** NOT STARTED.

**Infrastructure gaps identified:**
- No `__init__.py` in `analysis/src/ml/` — Python cannot resolve imports from `src.ml.models` without it.
- No `__init__.py` in `analysis/src/ml/models/` — same import issue.
- Six new subdirectories required under `analysis/src/ml/`: `training/`, `confidence/`, `memory/`, `reasoning/`, `decision/`, each needing `__init__.py`.
- `requirements.txt` is missing `grpcio`, `grpcio-tools`, `protobuf` (needed for Phase 4.2).

**Summary: 2 of 15 steps partially/fully complete. 13 steps remain.**

---

## 2. Task Sequencing Rules

Every task in this plan follows these hard constraints:

1. **Dependency ordering.** No task begins until all its prerequisites produce passing tests. The critical path is: T01 → T02 → T03 → T04 → T05 → T06 → T07 → T08 → T09 → T10 → T11 → T12 → T13.
2. **Single-file focus.** Each task creates or modifies at most 2 files (one implementation, one test). This keeps diffs reviewable and rollbacks surgical.
3. **Test-first exit criterion.** A task is marked DONE only when its tests pass via `pytest analysis/tests/<test_file> -v` with 0 failures.
4. **No forward references.** Implementation code never imports from modules created in later tasks. If a component needs a future dependency, it accepts it as a constructor parameter with a `None` default and `Optional` type.
5. **No existing breakage.** Every task ends with a full `pytest analysis/tests/ -v` run confirming zero regressions against the 35 existing tests.

---

## 3. Task List

### T01 — Verify & Fix Test Suite (Phase 1.2 completion)

**Goal:** Ensure all 35 existing tests pass in the current environment. This is the absolute prerequisite — no ML work proceeds until the foundation is provably solid.

**What to do:**
1. Check that `pytest` is available in the current Python environment. If not, install it.
2. Run `pytest analysis/tests/ -v` from the project root.
3. Read every failure. Likely failure modes:
   - Import errors (`sys.path.insert` in test files may not resolve correctly depending on working directory)
   - Missing `scipy` dependency (used by `features.py:find_optimal_d` via `statsmodels` — but our tests don't call `find_optimal_d`, so this may be fine)
   - `triple_barrier_labels` signature mismatch (test calls `triple_barrier_labels(price_series)` with 1 arg, but the function requires `close, high, low` — 3 args). This is a known gap in `test_indicators.py:TestTripleBarrierLabels`.
4. Fix each failure minimally — patch the test to match the actual API, never patch production code to match a wrong test.
5. Re-run until 35/35 pass.

**Files touched:**
- `analysis/tests/test_indicators.py` (fix `triple_barrier_labels` call signature if needed)
- `analysis/tests/test_models.py` (verify imports resolve)
- `analysis/tests/test_signal_processor.py` (verify imports resolve)

**Exit criterion:** `pytest analysis/tests/ -v` → 35 passed, 0 failed, 0 errors.

**Estimated scope:** Small. Only test plumbing, no production code changes.

---

### T02 — Create Package __init__.py Files (Infrastructure)

**Goal:** Establish the Python package structure for all modules that will be created in subsequent tasks. Without these files, `from src.ml.confidence.maturity import MaturityGate` raises `ModuleNotFoundError`.

**What to do:**
1. Create `analysis/src/ml/__init__.py` (empty or with a module docstring).
2. Create `analysis/src/ml/models/__init__.py` (empty — the `models/` dir exists but has no `__init__.py`).
3. Create empty `__init__.py` in these new directories:
   - `analysis/src/ml/training/__init__.py`
   - `analysis/src/ml/confidence/__init__.py`
   - `analysis/src/ml/memory/__init__.py`
   - `analysis/src/ml/reasoning/__init__.py`
   - `analysis/src/ml/decision/__init__.py`
4. Create `analysis/proto/` directory (for Phase 4.2 gRPC, but the dir is needed early to avoid confusion).

**Files created:** 7 `__init__.py` files + 1 directory.

**Exit criterion:** `python -c "from analysis.src.ml.models.goliath_transformer import GoliathTransformer; print('OK')"` succeeds. All existing tests still pass.

**Estimated scope:** Tiny. Boilerplate only.

---

### T03 — Feature Registry (Phase 1.3)

**Goal:** Create the `FeatureRegistry` singleton that enforces a strict feature vector contract between the quant pipeline and ML models. This directly transfers the CS2 "19-dim METADATA_DIM" pattern (AI_BIOPSY.md §6.1) into the trading domain.

**What to do:**
1. Create `analysis/src/quant/feature_registry.py` with:
   - `FeatureSpec` frozen dataclass: `name`, `dtype`, `valid_range: Tuple[float, float]`, `category`, `required: bool = True`, `default: float = 0.0`
   - `FeatureRegistry` class (singleton via `_instance` class variable):
     - `_register_defaults()`: Register all 23 features currently assembled ad-hoc in `neural_decision.py`:
       - 9 indicator features: `ind_rsi`, `ind_stoch_k`, `ind_stoch_d`, `ind_cci`, `ind_adx`, `ind_atr`, `ind_bb_position`, `ind_macd_diff`, `ind_macd_momentum`
       - 8 pattern features: `pat_doji`, `pat_hammer`, `pat_engulfing_bullish`, `pat_engulfing_bearish`, `pat_morning_star`, `pat_evening_star`, `pat_double_top`, `pat_double_bottom`
       - 4 channel features: `chan_ascending`, `chan_descending`, `chan_horizontal`, `chan_position`
       - 2 S/R features: `sr_support_dist`, `sr_resistance_dist`
     - `register(spec: FeatureSpec)`: Add a feature to the schema
     - `validate_parity(feature_names: List[str]) -> bool`: Raise `ValueError` if any required feature is missing
     - `validate_values(feature_dict: Dict[str, float]) -> Dict[str, float]`: Clamp values to valid ranges
     - `expected_dim -> int`: Property returning `len(self._schema)`
     - `get_ordered_names() -> List[str]`: Deterministic feature order

2. Create `analysis/tests/test_feature_registry.py` with:
   - `test_singleton_identity`: Two calls to `get_instance()` return the same object
   - `test_expected_dim_is_23`: Default registry has exactly 23 features
   - `test_validate_parity_passes_with_all_features`: No exception when all 23 names provided
   - `test_validate_parity_raises_on_missing`: `ValueError` when a required feature is omitted
   - `test_validate_values_clamps_out_of_range`: Values outside `valid_range` get clamped
   - `test_register_custom_feature_extends_schema`: Adding a new feature increases `expected_dim`
   - `test_get_ordered_names_deterministic`: Two calls return identical list

3. Update `analysis/src/quant/__init__.py` to export `FeatureRegistry` and `FeatureSpec`.

4. Update `analysis/src/quant/neural_decision.py:assemble_feature_vector()` to call `FeatureRegistry.get_instance().validate_parity(names)` at the end before returning. The actual computation logic stays exactly the same — the registry is a contract layer, not a replacement.

**Files created:** `feature_registry.py`, `test_feature_registry.py`
**Files modified:** `__init__.py`, `neural_decision.py` (minimal — add 3 lines at end of `assemble_feature_vector`)

**Exit criterion:** `pytest analysis/tests/test_feature_registry.py -v` → 7 passed. Full suite still green.

---

### T04 — TradingBrain Model (Phase 2.1)

**Goal:** Create the 4-layer multi-expert neural architecture that replaces the monolithic GoliathTransformer for production inference. This is the single largest implementation task in the plan.

**What to do:**
1. Create `analysis/src/ml/models/trading_brain.py` with four layers:

   **Layer 1 — Perception (Multi-Stream Input Encoding):**
   - Price Stream: `Conv1d(5, 64, kernel=3, padding=1) → BatchNorm1d → GELU → Conv1d(64, 64, kernel=3, padding=1) → BatchNorm1d → GELU`
   - Indicator Stream: `Linear(n_indicators, 96) → LayerNorm → GELU → Dropout(0.1)`
   - Volume/Volatility Stream: `Linear(4, 32) → LayerNorm → GELU`
   - Concatenation: `Cat(64+96+32=192) → Linear(192, 256) → LayerNorm`
   - Analogy: CS2 3-stream CNN (View ResNet + Map ResNet + Motion Conv → 128-dim)

   **Layer 2 — Memory (Temporal + Associative):**
   - Sequential: `LSTM(256, 128, num_layers=2, batch_first=True, dropout=0.2)`
   - Associative: `MultiheadAttention(128, num_heads=4, dropout=0.1, batch_first=True)` — self-attention on LSTM output
   - Fusion: `Cat(128+128=256) → Linear(256, 256) → LayerNorm → GELU` + residual from Perception
   - Analogy: CS2 LTC AutoNCP + Hopfield 4-head + Belief Head

   **Layer 3 — Strategy (MoE with Context Gating):**
   - 4 Expert Networks: `Linear(256, 128) → LayerNorm → ReLU → Linear(128, 64)` — one each for Trend, MeanReversion, Breakout, Range
   - Gating Network: `Linear(256, 4) → Softmax` — routes to the regime-appropriate expert
   - SuperpositionLayer: `Linear(context_dim, 256) → Sigmoid` — context-gated masking from AI_BIOPSY §6.3.3
   - Expert Aggregation: `weighted_sum → Linear(64, 256) → LayerNorm → apply mask`
   - L1 sparsity loss on gate weights (`lambda=1e-4`) returned separately for composite loss

   **Layer 4 — Decision (Value + Direction + Confidence):**
   - Value Critic: `Linear(256, 64) → ReLU → Linear(64, 1)` — expected return regression
   - Direction Head: `Linear(256, 64) → ReLU → Linear(64, 3)` — Long/Hold/Short logits
   - Confidence Head: `Linear(256, 64) → ReLU → Linear(64, 1) → Sigmoid` — raw [0,1] confidence
   - Output: `TradingBrainOutput` named tuple with `direction`, `value`, `confidence`, `gate_weights`

   **Composite Loss (`TradingBrainLoss`):**
   - `L_direction`: `CrossEntropyLoss(label_smoothing=0.1)`
   - `L_value`: `MSELoss()` × 0.5
   - `L_confidence`: `BCELoss()` × 0.3
   - `L_sparsity`: `gate_weights.abs().mean()` × 1e-4
   - `L_total = L_direction + 0.5 × L_value + 0.3 × L_confidence + 1e-4 × L_sparsity`

2. Create `analysis/tests/test_trading_brain.py` with:
   - `test_forward_pass_shape`: Input `(4, 50, 5, 9, 4)` split across streams → output shapes correct
   - `test_output_nan_free`: No NaNs in any output head
   - `test_gradients_flow_all_params`: Every `requires_grad` parameter receives a gradient
   - `test_batch_size_one`: Single-sample forward pass succeeds
   - `test_gate_weights_sum_to_one`: MoE gate weights along dim=-1 sum to 1.0
   - `test_confidence_bounded_0_1`: Confidence head output ∈ [0, 1]
   - `test_composite_loss_scalar`: `TradingBrainLoss` returns a single scalar loss
   - `test_with_context_dim`: Model with `context_dim=4` accepts context tensor
   - `test_sparsity_loss_nonnegative`: L1 term ≥ 0

**Config dataclass:** `TradingBrainConfig(n_indicators=9, context_dim=0, d_model=256, n_experts=4, ...)`

**Estimated parameter count:** ~2.4M at d_model=256. Acceptable for the data volume expected after JEPA pre-training.

**Files created:** `trading_brain.py`, `test_trading_brain.py`
**Files modified:** None.

**Exit criterion:** `pytest analysis/tests/test_trading_brain.py -v` → 9 passed. Full suite still green.

---

### T05 — JEPA Self-Supervised Pre-Training (Phase 2.2)

**Goal:** Build the pre-training module that learns market structure representations from unlabeled OHLCV sequences using InfoNCE contrastive loss. Directly transfers the CS2 JEPA pattern (AI_BIOPSY.md §6.4).

**What to do:**
1. Create `analysis/src/ml/training/jepa.py` with:
   - `JEPAPreTrainer(nn.Module)`:
     - Online encoder: reuses TradingBrain's Perception layer + projection `Linear(d_model, 512) → LayerNorm → GELU → Dropout(0.1) → Linear(512, 256) → LayerNorm`
     - Target encoder: `deepcopy(online_encoder)`, updated via EMA (τ=0.996)
     - Predictor: `Linear(256, 512) → LayerNorm → GELU → Dropout(0.1) → Linear(512, 256)`
   - `update_target()`: EMA update — `target.data = τ × target.data + (1-τ) × online.data`
   - `info_nce_loss(online_proj, target_proj, temperature=0.07)`: Normalize, compute similarity matrix, cross-entropy with diagonal labels
   - `selective_decode(online_repr, target_repr)`: Skip if `cosine_distance < 0.05` (already well-represented states)
   - `pretrain_step(x_t, x_t1)`: Full forward pass → loss → EMA update

2. Create `analysis/tests/test_jepa.py` with:
   - `test_pretrain_step_returns_scalar_loss`: Single step produces a scalar
   - `test_loss_decreases_over_steps`: 50 steps on synthetic data → final loss < initial loss
   - `test_target_encoder_differs_from_online`: After EMA updates, parameters diverge slightly
   - `test_cosine_similarity_increases`: Adjacent windows become more similar after training
   - `test_selective_decode_skips_similar`: Identical inputs trigger skip

**Data source:** `etl_pipeline.py:create_sequences()` already produces sliding-window sequences. JEPA consumes adjacent pairs `(seq[i], seq[i+1])` as positive pairs.

**Files created:** `jepa.py`, `test_jepa.py`
**Files modified:** None.

**Exit criterion:** `pytest analysis/tests/test_jepa.py -v` → 5 passed. Full suite green.

---

### T06 — Maturity Gating System (Phase 2.3)

**Goal:** Implement the 3-tier confidence ceiling that prevents a newly deployed model from expressing full confidence. Directly transfers AI_BIOPSY.md §8.1.

**What to do:**
1. Create `analysis/src/ml/confidence/maturity.py` with:
   - `MaturityTier` enum: `CALIBRATING`, `LEARNING`, `MATURE`
   - Tier ceilings: `{CALIBRATING: 0.50, LEARNING: 0.80, MATURE: 1.00}`
   - Tier thresholds: `{CALIBRATING: 0, LEARNING: 50, MATURE: 200}`
   - `MaturityGate` class:
     - `record_sample() -> bool`: Increment `samples_seen`, update tier. Return `True` if retrain is needed (every 10 samples while not mature — the "10/10 prerequisite rule").
     - `gate(raw_confidence: float) -> float`: `min(raw_confidence, ceiling)`
     - `_update_tier()`: Promote tier based on thresholds.
     - `reset()`: Reset to CALIBRATING (for model retraining scenarios).

2. Create `analysis/tests/test_maturity.py` with:
   - `test_initial_tier_is_calibrating`: New gate starts at CALIBRATING
   - `test_gate_caps_at_50_during_calibrating`: `gate(0.95)` → `0.50`
   - `test_gate_caps_at_80_during_learning`: After 50 samples, `gate(0.95)` → `0.80`
   - `test_gate_passes_through_at_mature`: After 200 samples, `gate(0.95)` → `0.95`
   - `test_retrain_signal_every_10_samples`: `record_sample()` returns `True` on the 10th, 20th, etc.
   - `test_no_retrain_signal_when_mature`: After 200 samples, `record_sample()` always returns `False`
   - `test_reset_returns_to_calibrating`: After reset, tier is CALIBRATING and `samples_seen` is 0

**Files created:** `maturity.py`, `test_maturity.py`
**Files modified:** None.

**Exit criterion:** `pytest analysis/tests/test_maturity.py -v` → 7 passed. Full suite green.

---

### T07 — COPER Experience Bank (Phase 3.1)

**Goal:** Build the episodic memory system that stores and retrieves past trade experiences for decision-making. Transfers AI_BIOPSY.md §8.2 COPER pattern.

**What to do:**
1. Create `analysis/src/ml/memory/coper.py` with:
   - `TradeExperience` dataclass: `id`, `context_hash`, `market_state: Dict[str, float]`, `decision`, `entry_price`, `exit_price`, `pnl`, `effectiveness`, `timestamp`, `symbol`, `timeframe`
   - `COPERBank` class:
     - `_compute_context_hash(market_state) -> str`: SHA256[:16] of sorted market state values
     - `store(experience: TradeExperience)`: Add to bank, prune oldest if > `max_size` (default 10,000)
     - `retrieve(market_state, k=5, strategy='hybrid') -> List[TradeExperience]`:
       - Semantic: cosine similarity on state vectors, top-k
       - Hash: exact SHA256[:16] match, O(1) lookup
       - Hybrid: `0.6 × cosine + 0.4 × hash_match`
       - Pattern: same day-of-week / session filtering
     - `update_effectiveness(experience_id, outcome_score)`: EMA update `0.7 × old + 0.3 × new`
     - `_apply_stale_decay()`: Multiply effectiveness by `exp(-0.01 × days_since)` for experiences > 90 days old
     - `save(filepath)` / `load(filepath)`: JSON serialization
     - `__len__()`: Return bank size

2. Create `analysis/tests/test_coper.py` with:
   - `test_store_and_retrieve`: Store 1 experience, retrieve it by market state
   - `test_retrieve_ordering_by_similarity`: Store 10 varied experiences, verify top-1 is most similar
   - `test_hash_exact_match`: Identical market states produce same hash
   - `test_stale_decay_reduces_effectiveness`: 90+-day-old experience has lower effective score
   - `test_effectiveness_ema_update`: Update with score=1.0 increases effectiveness
   - `test_max_size_pruning`: Store `max_size+1` → bank size stays at `max_size`
   - `test_save_and_load_roundtrip`: Save to temp file, load back, verify all fields match
   - `test_empty_bank_returns_empty_list`: `retrieve()` on empty bank returns `[]`

**Files created:** `coper.py`, `test_coper.py`
**Files modified:** None.

**Exit criterion:** `pytest analysis/tests/test_coper.py -v` → 8 passed. Full suite green.

---

### T08 — Drift Detector (Phase 3.2)

**Goal:** Detect when feature distributions or prediction statistics shift away from training-time baselines, triggering confidence reduction or retraining. Transfers AI_BIOPSY_PART2.md §3.7 MetaDriftSurveillance.

**What to do:**
1. Create `analysis/src/ml/confidence/drift.py` with:
   - `DriftDetector` class:
     - `__init__(window_size=100)`: Initialize rolling deques and empty baselines
     - `set_baseline(training_predictions, training_features)`: Compute and store baseline mean/std of predictions, plus per-feature histograms (50 bins)
     - `detect_stat_drift(recent_predictions) -> float`: `|recent_mean - baseline_mean| / max(baseline_mean, 1e-8) / 0.20`, clamped to [0, 1]. A 20% shift = max drift.
     - `detect_distribution_drift(recent_features) -> float`: Average KL divergence across all features between recent and baseline histograms, normalized to [0, 1]
     - `combined_drift() -> float`: `0.4 × stat_drift + 0.6 × distribution_drift`
     - `adjust_confidence(raw_confidence) -> float`: `raw × max(1.0 - drift × 0.5, 0.5)` — floor at 50%
     - `should_retrain() -> bool`: `combined_drift() > 2.5σ` above historical mean drift
     - `record_prediction(prediction, features)`: Feed into rolling windows

2. Create `analysis/tests/test_drift.py` with:
   - `test_no_drift_when_distribution_unchanged`: Baseline and recent identical → drift ≈ 0
   - `test_stat_drift_detects_mean_shift`: Multiply predictions by 1.5 → stat_drift > 0.5
   - `test_distribution_drift_detects_feature_shift`: Multiply all features by 2.0 → distribution_drift > 0.5
   - `test_adjust_confidence_reduces_on_drift`: Injected drift → adjusted < raw
   - `test_adjust_confidence_floors_at_50_percent`: Even with max drift → adjusted ≥ raw × 0.5
   - `test_should_retrain_on_extreme_drift`: Large artificial shift triggers retrain signal

**Files created:** `drift.py`, `test_drift.py`
**Files modified:** None.

**Exit criterion:** `pytest analysis/tests/test_drift.py -v` → 6 passed. Full suite green.

---

### T09 — Silence Rule (Phase 3.3)

**Goal:** Implement the 4-condition silence check that prevents the system from producing signals when conditions indicate any output would be unreliable. Transfers AI_BIOPSY_PART2.md §3.8 "Prefer no trade over bad trade."

**What to do:**
1. Create `analysis/src/ml/confidence/silence.py` with:
   - `SilenceRule` class:
     - `should_stay_silent(maturity_gate, gated_confidence, aggregated_signal, feature_z_scores) -> Tuple[bool, str]`:
       - **Condition 1 — Cold Start:** `maturity_gate.tier == CALIBRATING AND samples_seen < 10` → `(True, "cold_start")`
       - **Condition 2 — Low Confidence:** `gated_confidence < 0.40` → `(True, "low_confidence")`
       - **Condition 3 — Neutral Deviation:** All `|z| < 1.0` for all features → `(True, "neutral_deviation")` — no indicator shows a strong enough move to act on
       - **Condition 4 — Conflicting Signals:** `|bullish_count - bearish_count| <= 1 AND both > 0` → `(True, "conflicting_signals")`
     - Returns `(False, "")` if no condition triggers.

   - `compute_z_scores(df, window=50) -> Dict[str, float]`: For each indicator column, compute `z = (current - rolling_mean_50) / max(rolling_std_50, 0.01)`. Helper for Condition 3.

2. Create `analysis/tests/test_silence.py` with:
   - `test_cold_start_triggers_silence`: Calibrating gate with 5 samples → silent
   - `test_low_confidence_triggers_silence`: Confidence 0.30 → silent
   - `test_neutral_deviation_triggers_silence`: All z-scores within [-0.5, 0.5] → silent
   - `test_conflicting_signals_triggers_silence`: 3 bull, 3 bear → silent
   - `test_no_silence_when_conditions_clear`: Mature gate, high confidence, significant z-scores, clear direction → not silent
   - `test_each_condition_independent`: Only one condition true → still silent (each is sufficient)

**Files created:** `silence.py`, `test_silence.py`
**Files modified:** None.

**Exit criterion:** `pytest analysis/tests/test_silence.py -v` → 6 passed. Full suite green.

---

### T10 — Momentum Tracker (Phase 3.4a)

**Goal:** Track win/loss streaks and adjust position sizing accordingly. Transfers AI_BIOPSY_PART2.md §3.4.

**What to do:**
1. Create `analysis/src/ml/reasoning/momentum.py` with:
   - `MomentumTracker` class:
     - `momentum: float = 1.0` (neutral starting point)
     - `record_trade(is_win: bool, timestamp: datetime)`:
       - Time decay: `momentum *= exp(-0.15 × gap_hours)` if previous trade exists
       - Win: `momentum += 0.05`; Loss: `momentum -= 0.04`
       - Clamp: `[0.7, 1.4]`
       - Asymmetry: ~4 wins to recover from 3 losses
     - `is_tilted -> bool`: `momentum < 0.85` (cold streak)
     - `is_hot -> bool`: `momentum > 1.2` (hot streak)
     - `adjust_position_size(base_size: float) -> float`:
       - Tilted: `base_size × 0.5`
       - Hot: `base_size × 1.25`
       - Middle: `base_size × momentum`

2. Create `analysis/tests/test_momentum.py` with:
   - `test_initial_momentum_is_neutral`: New tracker has `momentum == 1.0`
   - `test_five_wins_increases_momentum`: 5 consecutive wins → `momentum ≈ 1.25`
   - `test_five_losses_decreases_momentum`: 5 consecutive losses → `momentum ≈ 0.80`
   - `test_is_tilted_after_losses`: 4 losses → `is_tilted == True`
   - `test_is_hot_after_wins`: 5 wins → `is_hot == True`
   - `test_position_size_halved_when_tilted`: `adjust_position_size(1.0)` returns `0.5` when tilted
   - `test_time_decay_reduces_momentum`: Large time gap → momentum decays toward neutral
   - `test_clamping_prevents_extreme_values`: Many wins → momentum ≤ 1.4; many losses → momentum ≥ 0.7

**Files created:** `momentum.py`, `test_momentum.py`
**Files modified:** None.

**Exit criterion:** `pytest analysis/tests/test_momentum.py -v` → 8 passed. Full suite green.

---

### T11 — Blind Spot Detector (Phase 3.4b)

**Goal:** Identify systematic recurring mistakes in trade decisions for targeted retraining. Transfers AI_BIOPSY_PART2.md §3.5.

**What to do:**
1. Create `analysis/src/ml/reasoning/blind_spots.py` with:
   - `BlindSpot` dataclass: `pattern`, `frequency`, `avg_impact`, `priority` (frequency × |avg_impact|), `examples: List[str]` (last 5 trade IDs)
   - `BlindSpotDetector` class:
     - `analyze_trade(trade_result, market_context)`: Detect patterns:
       - `"late_entry"`: Entry > 3 bars after signal
       - `"ignored_divergence"`: RSI/price divergence present but not used
       - `"counter_trend"`: Trade against trend when ADX > 25
       - `"oversize_on_tilt"`: Position too large when momentum < 0.85
     - `get_top_blind_spots(k=3) -> List[BlindSpot]`: Sorted by priority descending
     - `get_retraining_weights() -> Dict[str, float]`: Map blind spot patterns to sample weights for retraining emphasis

2. Create `analysis/tests/test_blind_spots.py` with:
   - `test_detect_late_entry`: Feed trade with entry_delay=5 → `"late_entry"` detected
   - `test_detect_counter_trend`: Trade direction opposes ADX > 25 trend → detected
   - `test_frequency_increments`: Same pattern twice → `frequency == 2`
   - `test_priority_ordering`: Higher impact spots ranked first
   - `test_examples_capped_at_5`: Adding 10 trades of same pattern → only last 5 IDs kept

**Files created:** `blind_spots.py`, `test_blind_spots.py`
**Files modified:** None.

**Exit criterion:** `pytest analysis/tests/test_blind_spots.py -v` → 5 passed. Full suite green.

---

### T12 — 4-Tier Fallback Decision Engine (Phase 4.1)

**Goal:** Build the cascading decision engine that guarantees a response at every inference call, degrading gracefully from COPER → ML → Signals → Conservative. Transfers AI_BIOPSY.md §8.2 "never return nothing" guarantee.

**What to do:**
1. Create `analysis/src/ml/decision/fallback.py` with:
   - `FallbackTier` enum: `COPER(1)`, `ML_MODEL(2)`, `SIGNALS(3)`, `CONSERVATIVE(4)`
   - `FallbackDecisionEngine` class:
     - Constructor accepts all components as `Optional` parameters (graceful degradation if some components aren't ready yet)
     - `decide(market_state, features_tensor, agg_signal) -> TradeDecision`:
       - **Tier 1 — COPER:** Retrieve top-5 similar experiences. If best effectiveness > 0.7, use it.
       - **Tier 2 — ML Model:** Forward pass through TradingBrain. Apply maturity gate, drift adjustment. Check silence rule. If not silent and confidence > 0.5, use it.
       - **Tier 3 — Signals:** Use `AggregatedSignal` from existing pipeline. If confidence > 40 and not silent, use it.
       - **Tier 4 — Conservative:** Always returns HOLD with widened stops, minimal position size. Never fails.
     - Each decision includes `source_tier: FallbackTier` for audit trail.
   - Reuses `neural_decision.py:generate_decision()` as the Tier 3 backbone.

2. Create `analysis/tests/test_fallback.py` with:
   - `test_tier1_coper_used_when_effective`: Mock COPER with high-effectiveness experience → Tier 1 used
   - `test_tier2_ml_used_when_coper_empty`: Empty COPER, high-confidence model → Tier 2 used
   - `test_tier3_signals_used_when_model_silent`: Model silenced, good signal → Tier 3 used
   - `test_tier4_conservative_always_returns`: Everything fails → Tier 4 returns valid decision
   - `test_source_tier_labeled_correctly`: Each tier correctly sets `source_tier` field
   - `test_conservative_default_is_hold`: Tier 4 always returns HOLD action
   - `test_none_components_skip_gracefully`: Engine with `coper=None` skips to Tier 2 without error

**Files created:** `fallback.py`, `test_fallback.py`
**Files modified:** None.

**Exit criterion:** `pytest analysis/tests/test_fallback.py -v` → 7 passed. Full suite green.

---

### T13 — Orchestrator (Phase 4.3)

**Goal:** Create the central coordination point that wires all components together in the correct dependency order and provides a single `analyze()` entry point. Inspired by CS2's AnalysisOrchestrator.

**What to do:**
1. Create `analysis/src/orchestrator.py` with:
   - `OrchestratorConfig` dataclass: brain config, feature registry, max experiences, etc.
   - `TradingOrchestrator` class:
     - Constructor initializes all components: `FeatureRegistry`, `TradingBrain`, `MaturityGate`, `DriftDetector`, `SilenceRule`, `MomentumTracker`, `COPERBank`, `BlindSpotDetector`, `FallbackDecisionEngine`
     - `analyze(symbol, timeframe, ohlcv_df) -> TradeDecision`: Full pipeline:
       1. Compute indicators via `compute_all_indicators()`
       2. Detect patterns via `detect_all_patterns()`
       3. Extract and aggregate signals
       4. Assemble feature vector (validated via registry)
       5. Create tensor for model
       6. Check drift
       7. Run fallback decision engine
       8. Adjust sizing by momentum
       9. Store experience for future COPER retrieval
       10. Log for blind spot analysis
     - `record_trade_outcome(trade_id, pnl)`: Update COPER effectiveness, momentum, blind spots
     - `save_state(directory)` / `load_state(directory)`: Persist all stateful components

2. Create `analysis/tests/test_orchestrator.py` with:
   - `test_analyze_returns_trade_decision`: Synthetic OHLCV → valid `TradeDecision` with all fields non-null
   - `test_source_tier_is_labeled`: Decision includes a valid `source_tier`
   - `test_position_size_non_negative`: Result position size ≥ 0
   - `test_stop_loss_and_take_profit_set`: Both SL and TP are non-zero for actionable decisions
   - `test_orchestrator_does_not_crash_on_short_data`: 10-row OHLCV → graceful degradation, not exception

**Files created:** `orchestrator.py`, `test_orchestrator.py`
**Files modified:** None.

**Exit criterion:** `pytest analysis/tests/test_orchestrator.py -v` → 5 passed. Full suite green.

---

## 4. Deferred Work (Not in This Plan)

The following items from `stateful-inventing-pebble.md` are explicitly out of scope for this task plan and will be addressed in future iterations:

- **gRPC Signal Bridge (Phase 4.2):** Requires `grpcio`, `grpcio-tools`, `protobuf` dependencies and proto compilation infrastructure. Will be tackled after the core Python pipeline is proven. Proto schema is defined in the blueprint.
- **T-Mamba SSM Hybrid (solutions.md §3.1):** Needs CUDA and `mamba-ssm`. Deferred to Phase 5+.
- **DRL Ensemble (solutions.md §3.3):** PPO/SAC/A2C with `stable-baselines3`. Deferred.
- **TFT Multi-Horizon (solutions.md §3.2):** Requires `pytorch-forecasting`. Deferred.
- **LLM Sentiment Pipeline (solutions.md §3.4):** External API dependency. Deferred.
- **Go Gateway changes:** Out of scope — Python side only.
- **Rust Engine changes:** Out of scope — ML pipeline only.

---

## 5. Dependency Graph

```
T01 (Test Suite Fix)
 └─→ T02 (Package __init__.py)
      └─→ T03 (Feature Registry)
           └─→ T04 (TradingBrain Model)
                ├─→ T05 (JEPA Pre-Training)
                └─→ T06 (Maturity Gating)
                     ├─→ T07 (COPER Bank)
                     ├─→ T08 (Drift Detector)
                     └─→ T09 (Silence Rule)
                          ├─→ T10 (Momentum Tracker)
                          └─→ T11 (Blind Spot Detector)
                               └─→ T12 (Fallback Engine)
                                    └─→ T13 (Orchestrator)
```

**Critical path:** T01 → T02 → T03 → T04 → T06 → T09 → T12 → T13

**Parallelizable after T04:** T05, T06 are independent. T07, T08, T09 are independent after T06. T10 and T11 are independent after T09.

---

## 6. New Files Summary (26 files)

| # | File | Task | Purpose |
|---|------|------|---------|
| 1 | `analysis/src/ml/__init__.py` | T02 | Package marker |
| 2 | `analysis/src/ml/models/__init__.py` | T02 | Package marker |
| 3 | `analysis/src/ml/training/__init__.py` | T02 | Package marker |
| 4 | `analysis/src/ml/confidence/__init__.py` | T02 | Package marker |
| 5 | `analysis/src/ml/memory/__init__.py` | T02 | Package marker |
| 6 | `analysis/src/ml/reasoning/__init__.py` | T02 | Package marker |
| 7 | `analysis/src/ml/decision/__init__.py` | T02 | Package marker |
| 8 | `analysis/src/quant/feature_registry.py` | T03 | Feature contract singleton |
| 9 | `analysis/tests/test_feature_registry.py` | T03 | Registry tests (7) |
| 10 | `analysis/src/ml/models/trading_brain.py` | T04 | 4-layer model + composite loss |
| 11 | `analysis/tests/test_trading_brain.py` | T04 | Model tests (9) |
| 12 | `analysis/src/ml/training/jepa.py` | T05 | JEPA pre-trainer |
| 13 | `analysis/tests/test_jepa.py` | T05 | JEPA tests (5) |
| 14 | `analysis/src/ml/confidence/maturity.py` | T06 | 3-tier maturity gate |
| 15 | `analysis/tests/test_maturity.py` | T06 | Maturity tests (7) |
| 16 | `analysis/src/ml/memory/coper.py` | T07 | Episodic memory bank |
| 17 | `analysis/tests/test_coper.py` | T07 | COPER tests (8) |
| 18 | `analysis/src/ml/confidence/drift.py` | T08 | Distribution drift detection |
| 19 | `analysis/tests/test_drift.py` | T08 | Drift tests (6) |
| 20 | `analysis/src/ml/confidence/silence.py` | T09 | 4-condition silence rule |
| 21 | `analysis/tests/test_silence.py` | T09 | Silence tests (6) |
| 22 | `analysis/src/ml/reasoning/momentum.py` | T10 | Win/loss momentum tracker |
| 23 | `analysis/tests/test_momentum.py` | T10 | Momentum tests (8) |
| 24 | `analysis/src/ml/reasoning/blind_spots.py` | T11 | Recurring mistake detection |
| 25 | `analysis/tests/test_blind_spots.py` | T11 | Blind spot tests (5) |
| 26 | `analysis/src/ml/decision/fallback.py` | T12 | 4-tier fallback engine |
| 27 | `analysis/tests/test_fallback.py` | T12 | Fallback tests (7) |
| 28 | `analysis/src/orchestrator.py` | T13 | Central pipeline orchestrator |
| 29 | `analysis/tests/test_orchestrator.py` | T13 | Orchestrator tests (5) |

**Existing files modified (3):**
| File | Task | Change |
|------|------|--------|
| `analysis/src/quant/__init__.py` | T03 | Export `FeatureRegistry`, `FeatureSpec` |
| `analysis/src/quant/neural_decision.py` | T03 | Add registry validation to `assemble_feature_vector()` |
| `analysis/tests/test_indicators.py` | T01 | Fix `triple_barrier_labels` call signature if broken |

**Total new tests across all tasks: 88**
**Total existing tests preserved: 35**
**Grand total at completion: 123 tests**

---

## 7. Verification Protocol

After every task:
1. Run the task-specific test file: `pytest analysis/tests/test_<module>.py -v`
2. Run the full suite: `pytest analysis/tests/ -v`
3. Check for import cycles: `python -c "from analysis.src.ml.models.trading_brain import TradingBrain"` (or equivalent for the module just created)
4. Confirm no existing test was broken by the new code.

After T13 (final task):
- Full end-to-end: `TradingOrchestrator.analyze("XAUUSD", "H1", synthetic_ohlcv)` returns a `TradeDecision` with all fields populated, `source_tier` labeled, and `position_size_pct` appropriately momentum-adjusted.
- All 123 tests pass.
- No import cycles.
- No `Optional` parameters left unresolved in the Orchestrator (all components wired).
