# Module 5.3: Site Reliability Engineering (SRE)

**Date:** 2026-02-06
**Status:** Completed

## 1. Metrics & Monitoring Internals

### 1.1 Prometheus: The Pull Model
*   **Architecture:** Prometheus server scrapes `/metrics` endpoints.
*   **Storage (TSDB):**
    *   **Timestamps:** Delta-of-Delta compression (Gorilla). If scrape interval is stable (30s), delta-of-delta is 0. 1 bit per timestamp.
    *   **Values:** XOR compression for float64. Small changes compress well.
*   **Pushgateway:** Only for batch jobs that die before scrape.

### 1.2 Distributed Tracing
*   **Goal:** Follow `Request A` through `LB -> Service A -> Service B -> DB`.
*   **W3C Trace Context (`traceparent`):**
    *   `version-traceid-parentid-flags`
    *   `00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01`
    *   **Propagation:** Service A generates `traceid`. Passes it to B in HTTP header. Service B logs it.

## 2. Reliability Math: SLOs & Error Budgets

### 2.1 The Terms
*   **SLI (Indicator):** "HTTP 500 rate". (The reality).
*   **SLO (Objective):** "99.9% success". (The goal).
*   **SLA (Agreement):** "If < 99.5%, refund 10%". (The contract).

### 2.2 Error Budget Calculation
*   **Period:** 30 Days.
*   **Availability:** 99.9%.
*   **Budget:** 0.1% downtime $\approx$ 43 minutes.
*   *Philosophy:* If you have budget left, release fast. If budget is empty, **FREEZE releases**.

### 2.3 Alerting: Burn Rate
Don't alert on "1 error". Alert on "Burning budget too fast".
*   **Burn Rate 1:** Consuming budget linearly (exhausts in 30 days).
*   **Burn Rate 14.4:** Consuming budget in 2 days. (Page the human).
*   **Formula:** $BurnRate = \frac{ErrorRate}{1 - SLO}$
*   *Alert Rule:* `burn_rate > 14.4` AND `error_rate > threshold`.
