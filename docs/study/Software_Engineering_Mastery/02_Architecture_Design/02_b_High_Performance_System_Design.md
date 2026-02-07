# Module 2.3: High-Performance System Design

**Date:** 2026-02-06
**Status:** Completed

## 1. Caching Strategies & Algorithms

Caching is the art of storing expensive data in cheap-to-access memory.

### 1.1 Implementation Patterns
*   **Cache-Aside (Lazy Loading):** App checks Cache. If miss, App reads DB, App updates Cache.
    *   *Pros:* Resilient to cache failure.
    *   *Cons:* Stale data potential. Thundering Herd risk on cold start.
*   **Read-Through:** App asks Cache. If miss, Cache asks DB. App never touches DB.
*   **Write-Through:** App writes to Cache. Cache writes to DB synchronously.
    *   *Pros:* Data consistency.
    *   *Cons:* Higher write latency.
*   **Write-Back (Write-Behind):** App writes to Cache. Cache acknowledges immediately. Cache writes to DB asynchronously (queue).
    *   *Pros:* Lowest write latency.
    *   *Cons:* Data loss if Cache crashes before flush.

### 1.2 The "Thundering Herd" Problem
*   **Scenario:** Cache key `product_123` expires. 1000 requests arrive simultaneously.
*   **Result:** All 1000 requests see "Miss". All 1000 requests query the DB. DB dies.
*   **Solution:** **Probabilistic Early Expiration** (X-Fetch).
    *   If `TTL - Now < gap`, a single request recomputes the value while others serve the "stale" but valid data.

### 1.3 Modern Eviction: TinyLFU (Window TinyLFU)
Used in Caffeine (Java) and Ristretto (Go). Superior to LRU.
*   **The Problem with LRU:** A one-time scan of a large database flushes "hot" items from the cache.
*   **TinyLFU Architecture:**
    1.  **Admission Policy (Doorkeeper):** Uses a **Bloom Filter**.
        *   New item comes. Is it in Bloom Filter?
        *   No: Add to Bloom Filter. Drop it (Don't cache).
        *   Yes: It's seen twice. Consider caching.
    2.  **Frequency Sketch (Count-Min Sketch):**
        *   Tracks frequency of *all* items (even those not in cache) using probabilistic counters (4-bit).
    3.  **Eviction:**
        *   Compare `Frequency(Candidate)` vs `Frequency(Victim)`.
        *   If Candidate is "hotter", evict Victim.
*   **Result:** "Scan Resistant". A million one-time reads won't evict the heavy hitters.

## 2. Horizontal Scaling & Sharding

### 2.1 Consistent Hashing
How to distribute 1TB data across 4 nodes? `Hash(key) % 4`.
*   **Problem:** Add Node 5. `Hash(key) % 5` changes *almost every* mapping. 80% of data must move.
*   **Consistent Hashing:**
    *   Map Nodes to a **Ring** (0 to $2^{32}$).
    *   Map Keys to the Ring.
    *   Key belongs to the first Node found moving clockwise.
    *   **Add Node:** Only keys between `NewNode` and `PrevNode` move. (Minimal movement).
*   **Virtual Nodes (V-Nodes):**
    *   *Problem:* Uneven distribution. Node A might get a "large" arc of the ring.
    *   *Solution:* Node A maps to 100 random points (A1..A100). Node B maps to B1..B100.
    *   *Result:* Statistically uniform load distribution.

## 3. Distributed Theory: CAP vs PACELC

CAP is too simple for 2026.
*   **CAP:** "In a Partition (P), choose Availability (A) or Consistency (C)."
    *   *Reality:* Partitions are rare. What about the other 99.9% of the time?
*   **PACELC:**
    *   **if P (Partition):** Choose **A** or **C**.
    *   **E (Else/Normal):** Choose **L** (Latency) or **C** (Consistency).
    *   *Example (DynamoDB/Cassandra):* **PA/EL**.
        *   Partition? Available.
        *   Normal? Low Latency (Eventual Consistency).
    *   *Example (BigTable/HBase):* **PC/EC**.
        *   Partition? Stop serving (Consistent).
        *   Normal? Strong Consistency (Higher Latency).
