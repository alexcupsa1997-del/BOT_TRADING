# Module 3.1: Relational Database Internals

**Date:** 2026-02-06
**Status:** Completed

## 1. Storage & Indexing: The B+ Tree

Why is it the standard?
*   **Structure:**
    *   **Internal Nodes:** Contain only keys and pointers. (High Fan-out).
    *   **Leaf Nodes:** Contain keys and **Record Pointers** (or the data itself in Clustered Index).
    *   **Linked Leaves:** Leaf nodes are a doubly-linked list.
*   **Performance:**
    *   **Point Lookup:** $O(\log_B N)$. With fan-out $B=100$, tree height is usually 3-4.
    *   **Range Scan:** Find start key ($O(\log N)$), then traverse linked list ($O(K)$). Very cache-friendly.

## 2. Transaction Isolation: The Anomalies

SQL Standard defines levels, but implementations vary.

### 2.1 The Anomalies
1.  **Dirty Read:** Reading uncommitted data. (Transaction A writes, B reads, A aborts).
2.  **Non-Repeatable Read:** Reading the same row twice gives different values. (Row modified by B).
3.  **Phantom Read:** Executing the same **Range Query** twice gives different set of rows. (Row inserted/deleted by B).

### 2.2 Isolation Levels
| Level | Dirty Read | Non-Repeatable | Phantom |
| :--- | :--- | :--- | :--- |
| **Read Committed** | No | Yes | Yes |
| **Repeatable Read** | No | No | Yes (Usually) |
| **Serializable** | No | No | No |

## 3. Concurrency Control: MVCC (Postgres/MySQL)

How to achieve "Readers don't block Writers"? **Multi-Version Concurrency Control**.

### 3.1 Postgres Implementation (`xmin` / `xmax`)
*   **Tuple Structure:** Every row has `xmin` (Created by TxID) and `xmax` (Deleted by TxID).
*   **UPDATE:** It is actually `DELETE` + `INSERT`.
    *   Old Row: `xmax` set to Current TxID.
    *   New Row: `xmin` set to Current TxID.
*   **Visibility Rules:**
    *   Transaction $T$ sees row $R$ if:
        1.  `R.xmin` is committed and < $T$.
        2.  `R.xmax` is NULL or (uncommitted) or > $T$.
*   **Vacuuming:** The process of removing "Dead Tuples" (where `xmax` is visible to all active transactions).

## 4. Durability & Recovery: ARIES & WAL

How to survive a power plug pull?

### 4.1 Write-Ahead Logging (WAL)
*   **The Golden Rule:** Log record must hit disk **before** the data page touches disk.
*   **Log Sequence Number (LSN):** Every log entry has an ID. Every Data Page stores the `PageLSN` of the last update.

### 4.2 ARIES Algorithm
1.  **Analysis:** Scan WAL from last Checkpoint. Determine "Winner" (Committed) and "Loser" (In-flight) transactions. Determine Dirty Pages.
2.  **Redo:** Replay history. Re-apply all updates (even for Losers) to bring memory to state at crash.
    *   *Idempotency:* If `PageLSN` >= `LogLSN`, don't apply.
3.  **Undo:** Scan WAL backwards. Revert changes of "Loser" transactions.
