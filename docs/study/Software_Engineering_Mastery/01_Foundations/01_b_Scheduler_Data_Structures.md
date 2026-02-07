# Module 1.1.b: Scheduler Data Structures Deep Dive

**Date:** 2026-02-06
**Status:** Completed

## 1. The Red-Black Tree (rbtree) in CFS

The **Completely Fair Scheduler (CFS)** abandoned the O(1) scheduler's array-of-queues in favor of a tree structure.

### 1.1 Why not AVL?
Both are Self-Balancing Binary Search Trees (BSTs).
*   **AVL Trees:** Strictly balanced (Height difference $\le 1$). Lookups are faster ($1.44 \log N$), but Insertion/Deletion requires more rotations to rebalance.
*   **Red-Black Trees:** Relaxed balancing (Longest path $\le 2 	imes$ Shortest path). Lookups are slightly slower ($2 \log N$), but Insertion/Deletion is much cheaper (O(1) amortized rebalancing).
*   **The Kernel's Choice:** Schedulers mutate the tree constantly (every task wake-up, sleep, or tick). High churn favors the cheaper write cost of RB-Trees.

### 1.2 Kernel Implementation Details (`lib/rbtree.c`)
*   **Intrusive Data Structure:** The `rb_node` is embedded *inside* the `task_struct` (via `sched_entity`). This avoids `malloc` overhead.
*   **The "Leftmost" Cache:**
    *   Finding the node with the smallest `vruntime` (the next task to run) is $O(\log N)$ in a standard BST.
    *   **Optimization:** CFS caches the pointer to the `rb_leftmost` node.
    *   **Result:** `pick_next_task` is effectively **O(1)**. The tree is only traversed when adding/removing tasks.

## 2. Per-CPU Variables & Locking

Scalability kills. If all CPUs fought over one global Runqueue, the locking overhead would destroy performance on 64-core systems.

### 2.1 The Per-CPU Paradigm
*   **Concept:** Each CPU has its own private memory area. CPU 0 writes to `var_cpu0`, CPU 1 writes to `var_cpu1`. No locks needed for local access.
*   **Hardware Implementation (x86_64):**
    *   The `GS` segment register holds the base address of the per-cpu area.
    *   **Access:** `mov rax, gs:[offset]`.
    *   **Context Switch Safety:** `swapgs` instruction swaps the user-space GS base with the kernel-space GS base upon entry (syscall/interrupt).

### 2.2 The Runqueue (`rq`)
*   Every CPU has its own `struct rq`.
*   **Locking:** `rq->lock`.
    *   Local scheduler operations (picking next task) only acquire the *local* lock.
    *   **Result:** Near-perfect linear scalability for CPU-bound workloads.

## 3. Load Balancing & Work Stealing

If CPU 0 has 10 tasks and CPU 1 has 0, we must balance. But locking remote runqueues is expensive.

### 3.1 Hierarchical Scheduling Domains
*   CPUs are grouped into **Scheduling Domains** (based on topology: SMT threads -> Cores -> Sockets -> NUMA nodes).
*   Balancing happens more frequently at the bottom (cheap) and less frequently at the top (expensive).

### 3.2 The Mechanisms
1.  **Periodic Load Balance:**
    *   Triggered by timer (`scheduler_tick`).
    *   Calculates "Load" (Combination of task weight + CPU utilization).
    *   If imbalance > Threshold, it locks the remote queue and pulls tasks.
2.  **Idle Balance (Work Stealing):**
    *   Triggered when a CPU is about to go `idle` (`schedule()` finds no tasks).
    *   It aggressively searches other CPUs' runqueues to "steal" work.
    *   **Order:** Check sibling threads first (L1 cache warm), then same socket (L3 warm), then remote NUMA nodes.

### 3.3 The "Misfit" Task
*   In **Heterogeneous Systems** (ARM big.LITTLE / Intel Hybrid), a "heavy" task might be stuck on a "LITTLE" (efficient) core.
*   CFS detects this "Misfit" and actively pushes the task to a "big" (performance) core, even if the load numbers technically look balanced.
