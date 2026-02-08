# System Technical Specifications (v4.0.0)

## 1. System Topology & Latency Budget

### 1.1 Component Architecture
The system operates as a distributed event-processing pipeline with strict separation of concerns.

| Component | Language | Role | Scale Strategy | IPC Transport |
| :--- | :--- | :--- | :--- | :--- |
| **Gateway** | Go (1.22+) | Ingestion & Auth | Horizontal (Stateless) | Redis Pub/Sub |
| **Brain** | Python (3.11+) | Signal Processing | Vertical (GPU/CUDA) | Redis Streams |
| **Engine** | Rust (2021) | Execution & Risk | Actor Model (Tokio) | ZeroMQ / IPC |

### 1.2 Latency Budgets (Internal)
*   **Ingress (Webhook -> Go):** < 500µs (Parsing + HMAC)
*   **Transport (Go -> Redis):** < 200µs
*   **Inference (Redis -> Python -> Signal):** < 50ms (Model dependent)
*   **Execution (Python -> Rust -> Exchange):** < 5ms (Internal processing)

---

## 2. Ingestion Interface (Go Gateway)

### 2.1 Webhook Payload Schema
All inbound signals MUST conform to the following JSON Schema (Draft 7).

```json
{
  "type": "object",
  "required": ["timestamp", "symbol", "signal", "price"],
  "properties": {
    "timestamp": { "type": "integer", "description": "Unix nanoseconds" },
    "symbol": { "type": "string", "pattern": "^[A-Z0-9]{3,10}$" },
    "signal": { "type": "string", "enum": ["LONG", "SHORT", "CLOSE"] },
    "price": { "type": "string", "pattern": "^\\d+(\\.\\d{1,8})?$" },
    "strategy_id": { "type": "string", "maxLength": 32 }
  }
}
```

### 2.2 Redis Key Namespace
*   **Signals:** `market:signal:{symbol}:{timestamp}` (TTL: 24h)
*   **Order Book:** `market:ob:{symbol}` (Hash)
*   **Position State:** `account:position:{symbol}` (Hash)

---

## 3. Signal Processing (Python Brain)

### 3.1 Normalization Vectors
Inputs $x$ are normalized to range $[-1, 1]$ using a standard `tanh` activation to ensure bounded inputs for the LSTM.

$$
x_{norm} = \tanh\left(\frac{x - \mu_{ROLLING}}{\sigma_{ROLLING}}\right)
$$

### 3.2 Signal Fusion Logic
The `Aggregator` class computes the final `ConfidenceScore` ($C$).

$$
C = (w_{TV} \cdot S_{TV}) + (w_{NEWS} \cdot S_{NEWS}) + (w_{CHAIN} \cdot S_{CHAIN})
$$

Where:
*   $S_{TV} \in \{-1, 0, 1\}$ (TradingView Signal)
*   $S_{NEWS} \in [-1, 1]$ (Sentiment Score from Newswires)
*   $w$ represents the configurable weight of each source.

---

## 4. Execution Engine (Rust)

### 4.1 Order Request Structure
Internal IPC message format (Zero-Copy deserialization).

```rust
#[repr(C)]
pub struct OrderRequest {
    pub timestamp: i64,      // Unix Nano
    pub symbol_id: u32,      // Mapped ID
    pub side: u8,            // 1=Buy, 2=Sell
    pub quantity: f64,       // Base Asset
    pub limit_price: f64,    // 0.0 for Market
    pub time_in_force: u8,   // 0=GTC, 1=IOC, 2=FOK
    pub signature: [u8; 64], // Ed25519 Internal Sig
}
```

### 4.2 Risk Checks (Pre-Flight)
Before any `OrderRequest` is serialized to the exchange API, it must pass:
1.  **Max Notional Check:** `Qty * Price < Max_Position_Size`
2.  **Daily Drawdown:** `Current_Equity > (Start_Equity * 0.95)`
3.  **LTV Health:** Portfolio Collateral Factor > 1.1

---

## 5. Infrastructure Constraints

### 5.1 OS Kernel Tuning (sysctl.conf)
Required for high-throughput networking.
```bash
net.core.rmem_max = 16777216
net.core.wmem_max = 16777216
net.ipv4.tcp_fastopen = 3
fs.file-max = 100000
```

### 5.2 Security Hardening
*   **Ingress:** Allow only `443/tcp` from Allowlist IPs.
*   **Process Isolation:** `systemd` slices for CPU containment.
*   **Secrets:** Injected via Environment Variables (never disk).
