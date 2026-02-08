# TRADINGVIEW INTEGRATION PROTOCOL

> [!NOTE]
> This document overrides previous integration guides. It enforces **Mandatory Security** and **Goliath V4** Architecture standards.

## 1. System Role
TradingView (TV) acts as the **Primary Intelligence Source**.
- It visualizes the market.
- It calculates indicators (RSI, MACD, Custom).
- It generates **Signals** (Buy/Sell/Close).

The Goliath System receives these signals via **Secure Webhooks** and executes them with high precision.

---

## 2. Secure Gateway Implementation (Go)

The Gateway Service receives webhooks, validates the source, and publishes to Redis.

### 2.1 Security: IP Whitelisting (MANDATORY)
We accept traffic **ONLY** from official TradingView IPs.
*   `52.89.214.238`
*   `34.212.75.30`
*   `54.218.53.128`
*   `52.32.178.7`

### 2.2 Go Code Snippet (`gateway/main.go`)

```go
package main

import (
	"encoding/json"
	"net/http"
	"strings"
	"log"
)

// Authorized TradingView IPs
var allowedIPs = map[string]bool{
	"52.89.214.238": true,
	"34.212.75.30":  true,
	"54.218.53.128": true,
	"52.32.178.7":   true,
}

// TVPayload defines the expected JSON structure
type TVPayload struct {
	Symbol    string  `json:"symbol"`
	Price     float64 `json:"price"`
	Signal    string  `json:"signal"` // "LONG", "SHORT", "CLOSE"
	Timestamp int64   `json:"time"`
}

func webhookHandler(w http.ResponseWriter, r *http.Request) {
    // 1. Extract Client IP (Handle proxies if behind Nginx/Cloudflare)
    clientIP := r.RemoteAddr
    if forwarded := r.Header.Get("X-Forwarded-For"); forwarded != "" {
        clientIP = strings.Split(forwarded, ",")[0]
    } else {
        clientIP = strings.Split(clientIP, ":")[0]
    }

    // 2. Exact Match Whitelist Check
    if !allowedIPs[clientIP] {
        http.Error(w, "Unauthorized", http.StatusForbidden)
        log.Printf("[SECURITY] Blocked request from %s", clientIP)
        return
    }

    // 3. Parse Payload
    var payload TVPayload
    if err := json.NewDecoder(r.Body).Decode(&payload); err != nil {
        http.Error(w, "Bad JSON", http.StatusBadRequest)
        return
    }

    // 4. Publish to Redis (Fire & Forget)
    // Using Go-Redis client (pseudocode)
    // redisClient.Publish(ctx, "market_signals", payload)

    w.WriteHeader(http.StatusOK)
}
```

---

## 3. Pine Script Configuration

Strategy scripts must be configured to send the correct JSON payload.

### 3.1 Alert Payload Template
Copy this into the "Message" field of the Create Alert dialog:

```json
{
  "symbol": "{{ticker}}",
  "price": {{close}},
  "signal": "{{strategy.order.action}}",
  "time": {{time}}
}
```

### 3.2 Strategy Coding (Pine Script v5)
Ensure your strategy triggers alerts on confirmed bars to avoid "repainting" false signals.

```pinescript
//@version=5
strategy("Goliath Strategy", overlay=true)

// ... Logic ...
if longCondition
    strategy.entry("LONG", strategy.long)
    alert('{"symbol":"' + syminfo.ticker + '", "price":' + str.tostring(close) + ', "signal":"LONG", "time":' + str.tostring(time) + '}', alert.freq_once_per_bar_close)
```

## 4. Operational Pipeline
1.  **Signal:** TV triggers Alert -> Sends POST to `https://gw.goliath.bot/webhook`.
2.  **Verify:** Gateway checks IP `52.89...` -> Approved.
3.  **Transport:** Gateway pushes JSON to Redis channel `market_signals`.
4.  **Action:** Python Brain reads Redis -> Validates Risk -> Sends Order to Exchange.

---
*Verified for Goliath V4*
