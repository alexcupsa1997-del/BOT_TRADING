# Phase 3: Advanced Database Engineering - Syllabus

This phase dives into how data is stored, protected, and distributed.

## Module 3.1: Relational Internals (The Single Node)
**Goal:** Understand what happens when you type `COMMIT`.
*   **Storage Structures:**
    *   **B+ Trees:** The default index. High fan-out, cache-friendly.
    *   **Heap Files:** Unordered storage.
*   **Transaction Management (ACID):**
    *   **Atomicity & Durability:** The WAL (Write-Ahead Log) and Checkpoints.
    *   **Isolation:** The 4 levels. Dirty Read, Non-repeatable Read, Phantom Read.
    *   **MVCC (Multi-Version Concurrency Control):** How Postgres/MySQL allow "Readers don't block Writers".
*   **Concurrency Control:**
    *   **2PL (Two-Phase Locking):** Shared vs Exclusive locks. Deadlocks.
    *   **Snapshot Isolation:** The MVCC implementation.

## Module 3.2: Distributed Systems & Consensus
**Goal:** Agree on "Truth" across unreliable networks.
*   **Consensus Algorithms:**
    *   **Raft:** Leader Election, Log Replication, Safety Properties.
    *   **Paxos:** The mathematical foundation.
*   **Replication Patterns:**
    *   **Leader-Follower:** Sync vs Async. Failover issues (Split Brain).
    *   **Multi-Leader:** Conflict Resolution (LWW - Last Write Wins, Vector Clocks).
    *   **Leaderless (Dynamo-style):** Quorum Reads/Writes (R + W > N). Read Repair.

## Module 3.3: Storage Engines & NoSQL
**Goal:** Optimize for specific access patterns (Write-heavy vs Scan-heavy).
*   **LSM Trees (Log-Structured Merge-Trees):**
    *   **Components:** MemTable, WAL, SSTables.
    *   **Compaction:** Leveled vs Tiered. Write Amplification vs Read Amplification.
    *   *Use Cases:* Cassandra, RocksDB, LevelDB.
*   **Columnar Storage:**
    *   **Compression:** Run-Length Encoding (RLE), Delta Encoding.
    *   **Execution:** Vectorized processing (SIMD).
    *   *Use Cases:* Snowflake, ClickHouse, Redshift.
