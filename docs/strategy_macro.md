# Macro-Economic Signal Overlay (v4.0.0)

## 1. Algorithmic Implementation
The system does not trade "Megatrends" directly. Instead, it uses a **Macro Overlay** to adjust the position sizing of high-frequency technical signals.

### 1.1 Trend Vector Definition
Each tracked asset class is assigned a scalar `TrendVector` ($V_T$) updated daily via the Newswires MCP.

$$ V_T \in [-1.0, 1.0] $$

*   $V_T > 0.5$: Structural Bull (e.g., AI/Semi)
*   $V_T < -0.5$: Structural Bear (e.g., Fossil Fuels)
*   $V_T \approx 0$: Neutral (e.g., Forex Majors)

### 1.2 Signal Fusion Logic
When a Technical Signal ($S_{tech}$) is received from TradingView, the Execution Engine calculates the final Position Size ($Q_{final}$).

$$ Q_{final} = Q_{base} \times (1 + \alpha \cdot V_T \cdot \text{sign}(S_{tech})) $$

Where:
*   $\alpha$: Sensitivity Coefficient (Default: 0.5)
*   $\text{sign}(S_{tech})$: Direction of trade (+1 Long, -1 Short)

**Logic Table:**
| Tech Signal | Macro Trend ($V_T$) | Multiplier | Action |
| :--- | :--- | :--- | :--- |
| LONG (+1) | Bullish (+0.8) | $1 + (0.5 \cdot 0.8) = 1.4x$ | **Aggressive Long** |
| LONG (+1) | Bearish (-0.8) | $1 + (0.5 \cdot -0.8) = 0.6x$ | **Conservative Long** (Counter-Trend) |
| SHORT (-1) | Bullish (+0.8) | $1 + (0.5 \cdot -0.8) = 0.6x$ | **Conservative Short** (Counter-Trend) |

---

## 2. Data Sources & Parsing

### 2.1 Inputs (Newswires MCP)
The Python Brain queries the `newswires` tool every 4 hours for specific keywords.

**Query Map:**
```json
{
  "semiconductors": ["tsmc", "nvidia", "wafer capacity", "chip shortage"],
  "energy": ["opec", "crude inventory", "renewable mandate", "solar efficiency"],
  "biotech": ["fda approval", "clinical trial phase 3", "patent expiry"]
}
```

### 2.2 Sentiment Scoring (NLP)
Raw text is scored using a fine-tuned BERT model (or equivalent LLM call).
*   **Output:** `SentimentScore` (`float`).
*   **Aggregation:** Exponential Moving Average (EMA) of last 7 days' scores forms the $V_T$.

---

## 3. Portfolio Allocation Constraints

### 3.1 Sector Limits
To prevent over-exposure to a single "Hype" trend, the Risk Engine enforces:

```rust
struct SectorLimit {
    max_exposure: f64, // e.g., 0.20 (20% of Equity)
    correlation_threshold: f64, // e.g., 0.70
}
```
If `Correlation(Crypto, Tech) > 0.8`, the effective limit for `Crypto + Tech` is capped at 30% combined.

### 3.2 Dynamic Rebalancing
*   **Frequency:** Weekly (Friday Close).
*   **Logic:** If $V_T$ flips from Bull to Bear (Zero-Crossing), the system closes all "Aggressive" portions of open positions immediately.
