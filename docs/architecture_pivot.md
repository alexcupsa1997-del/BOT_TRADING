# System Architecture: Signal-Based Execution (v4.0.0)

## 1. Architectural Paradigm
The GOLIATH system implements a **Signal-Based Execution Engine**.
Unlike High-Frequency Trading (HFT) systems that co-locate for microsecond tick arbitration, Goliath optimizes for **Multi-Signal Fusion** and **Risk-Managed Execution**.

### 1.1 Core Components
*   **Signal Source (External):** TradingView (Pine Script Intelligence).
*   **Ingestion Layer (Internal):** Go Gateway (Stateless, High-Throughput).
*   **Decision Layer (Internal):** Python Brain (LSTM + Macro Overlay).
*   **Execution Layer (Internal):** Rust Engine (Order Management).

---

## 2. High-Level Data Flow
```mermaid
graph TD
    TV[TradingView Servers] -->|Webhook JSON| GW[Go Gateway]
    GW -->|Redis Pub/Sub| AI[Python Brain]
    AI -->|Order Instruction| EXE[Rust Engine]
    EXE -->|FIX/REST| EX[Exchange (Binance/Bybit)]
```

### 2.1 The Data-Execution Split
| Domain | Responsibility | Technology |
| :--- | :--- | :--- |
| **Intelligence** | Market Analysis, Indicator Calculation, Signal Generation | TradingView (Pine Script v5) |
| **Execution** | Latency Arbitrage (Internal), Risk Checks, Order Routing | Rust (Tokio) |

---

## 3. Operational Constraints

### 3.1 Signal Latency
The system accepts a "Webhook Latency" budget of **1000-5000ms** (Internet Transport).
*   **Implication:** Strategies must target timeframes $\ge$ 1 Minute.
*   **Mitigation:** Use "Confirmed Bar" signals to avoid false positives (Repainting).

### 3.2 Ingestion Security
The Gateway is the only public ingress point.
*   **Authentication:** IP Whitelisting (AWS/TradingView Ranges).
*   **Validation:** HMAC Signature verification on payload.

---

## 4. Implementation Priorities
1.  **Gateway Deployment:** Must be on a static IP (VPS/Elastic IP) to allow whitelisting.
2.  **Redis Cluster:** Deploy as the central nervous system for IPC.
3.  **Strategy Migration:** Rewriting legacy Python signals into Pine Script Alerts.
