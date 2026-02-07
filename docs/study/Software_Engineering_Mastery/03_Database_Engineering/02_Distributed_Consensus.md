# Module 3.2: Distributed Consensus & Replication

**Date:** 2026-02-06
**Status:** Completed

## 1. Consensus Algorithms: Agreement in a Hostile World

How do 5 nodes agree on "Who is leader?" or "Value X is 5" when the network is dropping packets?

### 1.1 Paxos (The Foundation)
*   **Roles:** Proposers, Acceptors, Learners.
*   **Mechanism:** Two phases.
    1.  **Prepare:** Proposer asks majority: "Will you promise to ignore requests with ID < N?".
    2.  **Accept:** If majority says yes, Proposer says: "Okay, accept value V with ID N".
*   **Multi-Paxos:** Optimization to skip Phase 1 when the Leader is stable.
*   **Problem:** Extremely hard to implement correctly (many edge cases).

### 1.2 Raft (The Standard)
Designed for understandability. Used in Etcd, Consul, CockroachDB.
*   **Components:** Leader Election, Log Replication, Safety.
*   **Term:** A logical clock. Monotonically increasing.
*   **Leader Election Safety:**
    *   *Rule:* A candidate is only valid if its log is *at least as up-to-date* as the majority.
    *   *Mechanism:* RequestVote RPC contains `lastLogTerm` and `lastLogIndex`.
    *   *Result:* A node with missing committed entries can **never** become leader. Data loss impossible.
*   **Log Matching Property:**
    *   If two logs have an entry with the same Index and Term, they are identical in all preceding entries.

## 2. Replication Models

### 2.1 Sync vs Async
*   **Synchronous:** Write to Leader -> Leader writes to Replica -> Replica ACKs -> Leader ACKs to Client.
    *   *Pros:* Zero data loss.
    *   *Cons:* Latency = Max(Replica Latency). One slow node kills performance.
*   **Asynchronous:** Write to Leader -> Leader ACKs to Client. Background replication.
    *   *Pros:* Fast.
    *   *Cons:* Leader crash = Data loss.
*   **Semi-Sync:** Write to Leader + 1 Replica (out of N).
    *   *Pros:* Balance between durability and speed.

## 3. Leaderless Replication (DynamoDB / Cassandra)

No leader. Any node can accept writes.

### 3.1 Quorum Math
*   **N:** Replication Factor (e.g., 3).
*   **W:** Write Quorum (e.g., 2).
*   **R:** Read Quorum (e.g., 2).
*   **Rule:** $R + W > N$.
    *   *Why?* The read set and write set must overlap by at least one node.

### 3.2 Failure Handling
*   **Sloppy Quorum:**
    *   If Node A is down, write to Node D (who is not usually a replica for this key).
    *   *Goal:* High Availability (Availability over Consistency).
*   **Hinted Handoff:**
    *   Node D keeps the data in a separate "Hinted Handoff" buffer.
    *   When Node A comes back, D pushes the data to A.
*   **Read Repair:**
    *   Client reads from A, B, C. A=5, B=5, C=4.
    *   Client returns 5. Background process updates C to 5.
