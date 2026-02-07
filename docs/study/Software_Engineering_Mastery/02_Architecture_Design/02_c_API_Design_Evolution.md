# Module 2.4: API Design & Evolution

**Date:** 2026-02-06
**Status:** Completed

## 1. GraphQL Performance Deep Dive

GraphQL offers "Exact Fetching" (no over/under fetching), but introduces the **N+1 Problem**.

### 1.1 The N+1 Problem
*   **Scenario:** Query `authors { name, books { title } }`.
*   **Execution:**
    1.  `SELECT * FROM authors` (Returns 10 authors).
    2.  For Author 1: `SELECT * FROM books WHERE author_id = 1`.
    3.  ...
    4.  For Author 10: `SELECT * FROM books WHERE author_id = 10`.
*   **Total Queries:** $1 + N = 11$. If N is 1000, DB dies.

### 1.2 The Solution: DataLoader Pattern
*   **Mechanism:** Batching & Caching within a single request tick (Event Loop).
*   **Algorithm:**
    1.  Resolver for Author 1 calls `loader.load(1)`. Promise returns (Pending).
    2.  Resolver for Author 2 calls `loader.load(2)`. Promise returns (Pending).
    3.  ...
    4.  **End of Tick:** DataLoader sees 10 pending IDs.
    5.  **Batch Execution:** `SELECT * FROM books WHERE author_id IN (1, 2, ... 10)`.
    6.  **Distribution:** DataLoader maps results back to the promises.
*   **Result:** 2 Queries Total (O(1)).

## 2. gRPC & Protocol Buffers (Protobuf)

REST (JSON) is text-based, verbose, and untyped. gRPC is binary, strict, and fast.

### 2.1 Why Protobuf is Faster?
*   **Binary Encoding:** JSON `{"id": 123}` is 10 bytes. Protobuf is 2-3 bytes.
*   **Field Numbers (The Secret Sauce):**
    *   Proto definition: `int32 id = 1;`
    *   On the wire, it sends `08 7B` (Field 1, Varint type, Value 123).
    *   **No Field Names:** It doesn't send the string "id". Bandwidth saved.
*   **Schema Evolution:**
    *   **Backward Compatibility:** If you rename `id` to `user_id`, the wire format (`Field 1`) stays the same. Old clients still work.
    *   **Rule:** NEVER change a Field Number.

## 3. Idempotency (Safety in Retries)

If a client sends `POST /payment`, and the network drops the response:
*   Client retries.
*   Server charges user twice.

### 3.1 The "Idempotency-Key" Pattern (Stripe Style)
1.  **Client:** Generates UUID `key_123`. Sends header `Idempotency-Key: key_123`.
2.  **Server:**
    *   **Check:** `GET key_123` from Redis/DB.
    *   **Hit:** Return stored response (200 OK). Do NOT execute logic.
    *   **Miss:**
        1.  **Lock:** `SETNX key_123 "IN_PROGRESS"`.
        2.  **Execute:** Charge credit card.
        3.  **Save:** Update `key_123` with Response Body.
        4.  **Return:** 200 OK.
3.  **Concurrency:** If two requests with `key_123` arrive at once, the second one hits the "IN_PROGRESS" lock and waits.
