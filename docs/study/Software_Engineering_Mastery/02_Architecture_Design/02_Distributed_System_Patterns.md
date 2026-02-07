# Module 2.2: Distributed System Patterns

**Date:** 2026-02-06
**Status:** Completed

## 1. Data Consistency in Microservices

The ACID guarantee of a single database is gone. We have **BASE** (Basically Available, Soft state, Eventual consistency).

### 1.1 The Saga Pattern
When a business process spans multiple services (e.g., `Order` -> `Payment` -> `Inventory`), we use a Saga.
*   **Choreography:**
    *   *Service A* emits `OrderCreated`.
    *   *Service B* listens, deducts stock, emits `StockReserved`.
    *   *Pros:* Decoupled, simple start.
    *   *Cons:* "Cyclic dependencies", hard to visualize flow.
*   **Orchestration:**
    *   *Saga Coordinator* (State Machine) tells A: "Create Order". Tells B: "Deduct Stock".
    *   *Pros:* Centralized logic, easy error handling.
    *   *Cons:* Coordinator is a single point of failure (conceptually).

### 1.2 Failure Handling: The "Zombie Saga"
What if the **Compensation** fails?
*   *Scenario:* Money deducted. Stock reservation failed. We try to refund money, but `PaymentService` is down.
*   *Result:* User has no stock and less money. Inconsistent state.
*   *Solution:* **Idempotent Retry**. The Compensation transaction *must* be retried until it succeeds. It cannot be allowed to fail permanently. Manual intervention queues are the last resort.

### 1.3 The Transactional Outbox Pattern
**Problem:** You save `Order` to DB, but the `EventBus` crashes before you publish `OrderCreated`. Now DB has data, but downstream knows nothing.
**Solution:**
1.  **Begin Transaction.**
2.  `INSERT INTO orders ...`
3.  `INSERT INTO outbox (topic, payload) ...` (Same Tx).
4.  **Commit Transaction.** (Atomic guarantee).
5.  **Relay:**
    *   **Polling:** Background thread `SELECT * FROM outbox`. Publish. Delete. (Simple, but delays).
    *   **Log Tailing (CDC):** Debezium reads the Postgres WAL / MySQL Binlog. Publishes to Kafka. (Real-time, complex).

## 2. Resiliency Patterns

### 2.1 Circuit Breaker State Machine
Prevents cascading failures by "failing fast".
1.  **Closed (Normal):** Requests go through. Count errors.
    *   If `ErrorRate > Threshold` (e.g., 50%): Transition to **Open**.
2.  **Open (Broken):** Fail immediately (throw `CircuitOpenException`).
    *   Wait for `SleepWindow` (e.g., 5s).
    *   Transition to **Half-Open**.
3.  **Half-Open (Test):**
    *   Allow *one* (or small N) request through.
    *   **Success?** Reset counters. Transition to **Closed**.
    *   **Fail?** Transition back to **Open**. Reset timer.

### 2.2 Bulkhead Pattern
*   *Concept:* Ship compartments. If one floods, the ship floats.
*   *Impl:* Thread Pools / Connection Pools.
*   *Scenario:* `Service A` calls `Service B` (slow) and `Service C` (fast).
*   *Without Bulkhead:* All threads get stuck waiting for B. Service C calls fail because no threads are left.
*   *With Bulkhead:* Pool B has 10 threads. Pool C has 10 threads. B exhaustion does not kill C.

### 2.3 Retry with Exponential Backoff & Jitter
*   **Backoff:** Wait 1s, 2s, 4s, 8s. (Give system time to recover).
*   **Jitter:** Wait `Random(0.8, 1.2) * 2^n`.
    *   *Why?* If 1000 clients fail at once, and all retry exactly at 2.00s, they create a **Retry Storm** (DDoS). Jitter spreads them out.
