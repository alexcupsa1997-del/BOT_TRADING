# Module 3.3: Storage Engines & NoSQL

**Date:** 2026-02-06
**Status:** Completed

## 1. The Write-Optimized Engine: LSM Trees

**Log-Structured Merge-Trees** solve the problem of random write I/O.
Used by: Cassandra, RocksDB, LevelDB, ScyllaDB.

### 1.1 Architecture
1.  **MemTable (Memory):** Incoming writes go here (SkipList or RB-Tree). Fast ($O(\log N)$).
2.  **WAL (Disk):** Sequential append for durability (crash recovery).
3.  **SSTable (Disk):** When MemTable is full, it is **flushed** to disk as an Immutable Sorted String Table.
4.  **Compaction:** Merge background SSTables to remove deleted/overwritten data.

### 1.2 Compaction Strategies
*   **Leveled (RocksDB):**
    *   L0: Overlapping SSTables.
    *   L1..LN: Non-overlapping.
    *   *Trade-off:* **High Write Amplification** (Data moved many times), but **Low Read Amplification** (Few files to check). Good for Reads.
*   **Tiered (Cassandra/Size-Tiered):**
    *   Flush to Tier 1. When 4 files exist, merge to Tier 2.
    *   *Trade-off:* **Low Write Amplification**, but **High Read Amplification** (Key might be in any file). Good for heavy Writes.

### 1.3 Bloom Filters
*   *Problem:* Reading a key requires checking potentially many SSTables.
*   *Solution:* Each SSTable has a **Bloom Filter** in its header.
*   *Result:* "Is key X in file Y?" -> No (Definite) / Maybe (Check index). Saves 99% of disk lookups.

## 2. The Scan-Optimized Engine: Columnar Storage

Used by: Snowflake, ClickHouse, Redshift, Parquet.

### 2.1 Row vs Column
*   **Row-Oriented (Postgres):** `[ID, Name, Age], [ID, Name, Age]`.
    *   Good for: Fetching one user.
    *   Bad for: `SELECT AVG(Age)`. Must read Name/ID from disk too (wasted I/O).
*   **Column-Oriented:** `[ID, ID], [Name, Name], [Age, Age]`.
    *   Good for: Analytics. Read only the `Age` block.

### 2.2 Compression Techniques
Column values are often repetitive.
*   **Run-Length Encoding (RLE):**
    *   Data: `USA, USA, USA, UK, UK`.
    *   Stored: `(USA, 3), (UK, 2)`.
*   **Delta Encoding:**
    *   Data (Timestamps): `1000, 1005, 1012`.
    *   Stored: `1000, +5, +7`. Small integers compress better.

### 2.3 Vectorized Execution (SIMD)
*   **Concept:** Instead of `for i in rows: sum += row.age` (Scalar)...
*   **SIMD (Single Instruction Multiple Data):** Load 16 integers into an AVX-512 register. Execute `VPADD` (Vector Parallel Add).
*   *Result:* 10x-50x speedup for aggregation queries.
