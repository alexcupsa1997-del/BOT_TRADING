# Integrations: The GOLIATH Bridge

**Version:** 1.0.0
**Doctrine:** v2.0 (Two-Speed Architecture)

This directory bridges the gap between the Core System (Rust/Go) and the External World (MCP/Megatrends).

## Structure

### 1. `gateway_drivers/` (The Fast Path)
-   **Target:** Go Gateway (`gateway/`).
-   **Protocol:** SBE (Simple Binary Encoding).
-   **Latency:** < 1ms.
-   **Modules:** Kingfisher (Liquidations), Bitcoin Live.
-   **Rule:** NO JSON. All data must be normalized to SBE Template ID 3 before hitting the engine.

### 2. `agent_tools/` (The Slow Path)
-   **Target:** Python Brain / Agent Logic.
-   **Protocol:** JSON-RPC (MCP).
-   **Latency:** Human-speed.
-   **Modules:** Blockscout, News, Context7.
-   **Rule:** These are for *context*, not *execution*.

### 3. `universe/` (The Strategy)
-   **Target:** Strategy Configuration.
-   **Content:** The "God List" (Megatrend Selection).
-   **Rule:** Only assets defined here are tradable by the Engine.
