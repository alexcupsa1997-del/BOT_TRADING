# GOLIATH TRADING SYSTEM: THE MONOLITH (TECHNICAL ARCHITECTURAL BIBLE)
**Version:** 4.0.0 (The Monolith)
**Date:** February 7, 2026
**Confidentiality Level:** EYES ONLY / HIGHEST CLASSIFICATION
**Authoring Agent:** Antigravity

---

## PREFACE: THE ARCHITECTURAL VISION

This document is not a summary. It is a **Dissection**.
It serves as the sole source of truth for the GOLIATH Trading System. It details every protocol, every algorithm, every data structure, and every design decision down to the bit-level.

The GOLIATH system is an **Event-Driven, Polyglot, High-Frequency** trading ecosystem. It is designed to survive where others fail: in the chaotic, high-latency, error-prone environment of real-world crypto and forex markets.

---

## PART I: THE META-ARCHITECTURE

### 1.1 The Tri-Language Topology
The system rejects the "Silver Bullet" hypothesis. No single language can solve all problems.
*   **Go (Golang):** The **Spinal Cord**. Handles I/O, Networking, and Data Ingestion.
    *   *Why?* Goroutines allow handling 10,000 concurrent sockets with 4KB stack overhead each.
    *   *Role:* Gateway & Aggregator.
*   **Rust:** The **Muscle**. Handles Risk, Execution, and State.
    *   *Why?* Affine Types (Ownership) prevent Double-Free and Use-After-Free errors at compile time.
    *   *Role:* Execution Engine & Risk Manager.
*   **Python:** The **Brain**. Handles Pattern Recognition and Strategy.
    *   *Why?* NumPy/PyTorch libraries are unrivaled for tensor calculus.
    *   *Role:* Data Analysis & Signal Generation.

### 1.2 The "Crash-Only" Philosophy
GOLIATH is designed to be killed at any moment (power failure, kernel panic) without data corruption.
*   **Append-Only Storage:** `.sbe` and `.parquet` files are only ever appended to.
*   **Idempotent Replay:** The system state is a function of the log history. $S_t = f(Log_{0...t})$. Restarting the system simply re-runs $f$.

---

## PART II: THE GATEWAY & INGESTION (Go/MQL5)

### 2.1 The MQL5 Expert Advisor (`SignalTrader.mq5`)
The "Edge" of the system lives inside the MetaTrader 5 terminal.

#### 2.1.1 The Event Loop (`OnTick`)
The EA is not a passive data forwarder. It implements a **Pre-Filtering** logic to reduce bandwidth.
```cpp
void OnTick() {
   // 1. Time Filter
   if(InpUseTimeFilter && !IsWithinTradingHours()) return;
   
   // 2. Trailing Stop Logic (Local Execution)
   if(InpUseTrailing) ManageTrailingStops();
   
   // 3. Indicator Collection
   UpdateIndicators(); // Copies buffers from MT5 kernel
}
```
*Critical Finding:* The Trailing Stop is managed *locally* by the EA (`ManageTrailingStops`). This is a **Failsafe**. If the Gateway disconnects, the EA will still protect open positions by moving the SL.

#### 2.1.2 The Indicator Buffers
The EA uses `CopyBuffer` to extract raw arrays from MT5's optimized C++ kernel.
*   `handleRSI`: RSI Buffer.
*   `handleBB`: 3 Buffers (Upper, Middle, Lower).
This data is usually forwarded to the Gateway, but in `SignalTrader.mq5`, there is also *embedded logic* to trade autonomously if needed (Hybrid Model).

### 2.2 The Gateway Listener (`listener.go`)

#### 2.2.1 The Wire Protocol (SBE)
The communication channel (TCP :5555) uses **Simple Binary Encoding**.

**Frame Structure:**
```
[Length: uint32][BlockLength: uint16][TemplateID: uint16][SchemaID: uint16][Version: uint16][Payload...]
```

**Payload Map (MarketData - Template ID 3):**
*   **SymbolID (int64):** 8 bytes.
*   **Timestamp (int64):** 8 bytes (Unix Nanoseconds).
*   **Bid (int64):** 8 bytes. *Mantissa*. Implied $10^{-9}$.
*   **Ask (int64):** 8 bytes. *Mantissa*. Implied $10^{-9}$.
*   **Volume (int64):** 8 bytes. *Mantissa*. Implied $10^{-9}$.
*   **Flags (uint8):** 1 byte.
*   **Total Size:** 41 Bytes + 8 Byte Header = 49 Bytes per tick.
*   **Efficiency:** A standard JSON payload `{"symbol":"EURUSD", "bid":1.05...}` is ~150 bytes. SBE is **3x** more dense.

#### 2.2.2 The Ingestion Pipeline
1.  **Syscall:** `read(fd, buffer, 4)` (Header).
2.  **Allocation:** `buffer = pool.Get(length)`.
3.  **Syscall:** `read(fd, buffer, length)` (Body).
4.  **Dispatch:** `channel <- tick`.
5.  **Persistence:** `Recorder` writes to `ticks_YYYYMMDD.parquet`.

---

## PART III: THE EXECUTION ENGINE (Rust)

### 3.1 Memory Safety & The Borrow Checker
The Engine (`engine/src/`) guarantees memory safety without a Garbage Collector.
*   **Ownership Rules:** A `Position` struct is Owned by the `Portfolio`. The `RiskManager` only borrows it (`&Position`).
*   **Concurrency:** The Engine uses the **Actor Model** (Tokio channels). State is *never* shared. Messages are passed.

### 3.2 The Risk Management Mathematics (`margin.rs`)

#### 3.2.1 Weighted Collateral Formula
Health is calculated using LTV (Loan-To-Value) vectors.
$$
\text{Effective Collateral} = \sum_{i=0}^{N} (Amount_i \times Price_i \times LTV_i)
$$
*   **BTC LTV:** 0.75 (Risk: Med)
*   **USDT LTV:** 1.00 (Risk: Low)
*   **Effects:** A portfolio of 100% BTC is considered "Less Solvent" than a portfolio of 100% USDT, even if they have the same nominal USD value.

#### 3.2.2 The Liquidation Equation
$$
HF = \frac{\sum (Collat_i \times Threshold_i)}{\text{Total Debt}}
$$
If $HF < 1.0$, the account is Liquidatable.

### 3.3 Dutch Auction Liquidation (`liquidation.rs`)
The system refuses to use Market Orders for large liquidations, which cause slippage.
**Algorithm:**
1.  **Start:** $T_0$. Price $P = Oracle \times 1.10$.
2.  **Decay:** Linear over 60 seconds.
3.  **End:** $T_{60}$. Price $P = Oracle \times 0.90$.
4.  **Mechanic:** Liquidator bots query the `get_dutch_auction_price()`. As soon as $P(t)$ crosses their internal valuation, they trigger the buy.
This ensures the "Best Execution" price for the distressed user.

---

## PART IV: THE BRAIN & QUANTITATIVE LIBRARY (Python)

### 4.1 The Indicator Library (`indicator_library.py`)
A massive collection of 100+ functions. The key innovation is **Normalization**. All indicators return signals in $[-1, 1]$.

#### 4.1.1 Momentum: The RSI (Relative Strength Index)
$$
RS = \frac{EMA(Gain, 14)}{EMA(Loss, 14)}
$$
$$
RSI = 100 - \frac{100}{1 + RS}
$$
**Normalization Logic:**
```python
if rsi < 30: signal = (30 - rsi) / 30  # Scale 0 to 1
if rsi > 70: signal = (70 - rsi) / 30  # Scale 0 to -1
```
This transforms a raw 0-100 scalar into a "Buying Pressure" vector suitable for Neural Network ingestion.

#### 4.1.2 Volatility: Bollinger Bands
$$
Upper = SMA(20) + 2\sigma
$$
$$
\%B = \frac{Price - Lower}{Upper - Lower}
$$
**Signal:**
*   $\%B < 0.2$: Oversold (Signal $\to$ 1)
*   $\%B > 0.8$: Overbought (Signal $\to$ -1)

### 4.2 The Neural Trader (`neural_trader.py`)
The AI is not a "Black Box". It is a **Risk-Constrained Probabilistic Engine**.

#### 4.2.1 Architecture (LSTM)
1.  **Input:** $(Batch, 60, 100)$. 60 time steps (1 minute), 100 normalized features.
2.  **Hidden:** LSTM(128). Captures temporal dependencies (e.g., "RSI is high AND was low 5 minutes ago").
3.  **Dense Heads:**
    *   **Direction:** Softmax(Buy, Sell, Hold).
    *   **SL/TP:** ReLU (Positive distance in pips).

#### 4.2.2 The Hubris Loss Function
$$
L = MSE(Price) + \lambda \cdot (Confidence - Accuracy)^2
$$
The model is penalized if it outputs `Confidence=0.99` but gets the direction wrong. This forces "Calibrated Uncertainty".

---

## PART V: THE USER INTERFACE (Dashboard)

### 5.1 TUI Rendering Engine (`dashboard.py`)
The dashboard is a Terminal User Interface built with `rich`.

#### 5.1.1 Layout Management
```python
layout.split(
    Layout(name="header", size=3),
    Layout(name="main"),
    Layout(name="footer")
)
```
This responsive grid adapts to terminal size.

#### 5.1.2 The "Mock Data" Finding
**CRITICAL AUDIT ITEM:** The current `generate_active_orders()` function uses synthetic data:
```python
table.add_row("ORD-001", "[green]BUY[/]", ...)
```
*   **Risk:** The dashboard displays *simulated* profit/loss, not real engine state.
*   **Remediation:** Phase 4 must connect `dashboard.py` to the Redis/ZMQ state channel to read real positions.

### 5.2 Threading Model
The dashboard runs a background daemon `fetch_live_price` that polls Binance API every 5 seconds.
*   **Conflict:** The main thread renders UI at 4 FPS.
*   **Safety:** Python's GIL ensures the UI thread reads atomic variable updates (`CURRENT_PRICE`) safely, though logic is eventually consistent.

---

## PART VI: TESTING & SIMULATION

### 6.1 The Test Harness (`test_bot.py`)
The system validates itself using `test_complete_simulation`.

#### 6.1.1 Synthetic Data Generation
```python
returns = np.random.randn(n_candles) * 0.0005
close = base_price + np.cumsum(returns)
```
It generates a Random Walk (Brownian Motion).
*   **Purpose:** If the strategy loses money on a Random Walk (expected), but loses *less* than spread costs, it's neutral. If it makes money, it's "Overfitting".
*   **Validation:** Real validation requires historical tick data replay, not just random walks.

---

## PART VII: INFRASTRUCTURE & CRITICAL AUDIT

### 7.1 Docker Isolation
*   **Gateway:** Alpine Linux (Minimal Attack Surface).
*   **Brain:** Debian + CUDA/ROCm (Heavy Compute).
*   **Network:** Internal Bridge. Example: Gateway at `172.18.0.2`, Engine at `172.18.0.3`.

### 7.2 Safety Interlocks (The Red Buttons)
1.  **Max Drawdown Killswitch:** If `Balance < StartBalance * 0.90`, the EA acts as a Circuit Breaker and creates a file `STOP_TRADING`.
2.  **Spiral Guard:** Rust Engine throttles orders if Volume > MarketDepth.

### 7.3 Final Compliance Checklist
*   [x] **Memory Safety:** Enforced by Rust.
*   [x] **Audit Trail:** Enforced by Blockchain Log (`audit.rs`).
*   [x] **Stop Loss:** Enforced locally by EA (`ManageTrailingStops`).
*   [!] **Dashboard:** **WARNING**. Visuals are currently decoupled from Reality.
*   [!] **Simulation:** Relies on Synthetic Random Walks. Needs Historic Data Backtest.

---

## APPENDIX A: MATHEMATICAL FORMULARY

**A.1 Exponential Moving Average (EMA)**
$$
EMA_t = (P_t \times \alpha) + (EMA_{t-1} \times (1 - \alpha))
$$
Where $\alpha = \frac{2}{N+1}$.

**A.2 Order Book Imbalance (OBI)**
$$
\rho = \frac{V_b - V_a}{V_b + V_a}
$$
Range: $[-1, 1]$.

**A.3 Parabolic SAR**
$$
SAR_{t+1} = SAR_t + \alpha (EP - SAR_t)
$$
Where $EP$ is the Extreme Point reached in the trend.

---

**END OF DOCUMENT**
*GOLIATH SYSTEM ARCHITECT - ANTIGRAVITY*
