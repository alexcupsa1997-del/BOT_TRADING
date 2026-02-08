# Gateway Drivers: High-Frequency Ingestion

**Target:** `gateway/internal/ingestion`
**Protocol:** SBE Template ID 3 (MarketData)

## Mandate
These drivers enable the **Fast Path**. They connect to external WebSockets (e.g., Kingfisher), normalize the data into the internal SBE format, and push it to the internal UDP/TCP bus.

## Priorities
1.  **Kingfisher.io (Liquidations):**
    -   Input: WebSocket JSON Alerts.
    -   Transformation: Map "Liquidation Intensity" to Volume/Price impact.
    -   Output: SBE Tick.

2.  **Bitcoin Live:**
    -   Input: Expert Signals.
    -   Output: SBE Tick (with proprietary Flags).
