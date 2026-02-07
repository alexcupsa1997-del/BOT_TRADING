# Module 1.1: Operating Systems Internals - Process & Memory Management

**Date:** 2026-02-06
**Status:** Completed

## 1. Process Scheduling: The Linux CFS (Completely Fair Scheduler)

The kernel's job is to illusion of "simultaneous" execution on limited hardware. The **Completely Fair Scheduler (CFS)** is the default Linux scheduler (since 2.6.23) for normal tasks (`SCHED_NORMAL`).

### 1.1 Core Concept: Ideal Multi-Tasking
CFS aims to model an "ideal, precise multi-tasking CPU". On such hardware, if 2 processes run, each gets exactly 50% power instantly. On real hardware, we must time-slice.

### 1.2 The Implementation Details
*   **Virtual Runtime (`vruntime`):**
    *   Instead of fixed time slices, CFS tracks how long a task *has run*.
    *   `vruntime` is weighted by priority (`nice` value).
    *   **Formula:** `vruntime += delta_exec * (NICE_0_LOAD / task_load_weight)`
    *   Lower priority tasks (high `nice`) gain `vruntime` faster, so they get pushed to the back of the line sooner.
    *   Higher priority tasks (low `nice`) gain `vruntime` slower, allowing them to run longer before catching up to others.

*   **Data Structure: Red-Black Tree:**
    *   Run-queue is not a queue; it's a **time-ordered Red-Black Tree**.
    *   **Key:** `vruntime`.
    *   **Leftmost Node:** The task with the lowest `vruntime`. This is *always* the next task to run.
    *   **Complexity:** Insert/Delete/Search is **O(log N)**.

*   **Granularity & Latency:**
    *   `sched_latency_ns`: The period in which all runnable tasks should get at least one turn (default ~6ms - 24ms).
    *   `min_granularity_ns`: Minimum time a task runs before preemption (prevents thrashing).

## 2. Context Switching Internals

When the scheduler picks a new task, a **Context Switch** occurs. This is pure overhead, so it must be fast.

### 2.1 The Sequence
1.  **Interrupt/Trap:** Timer interrupt or System Call triggers kernel mode.
2.  **Save State:**
    *   **General Purpose Registers:** `RAX`, `RBX`, `RCX`... saved to the current Process Control Block (PCB) or Kernel Stack.
    *   **Instruction Pointer (`RIP`):** Where were we?
    *   **Stack Pointer (`RSP`):** Where was the stack?
3.  **Switch Memory Space (Expensive):**
    *   Update `CR3` Control Register to point to the new process's **Page Global Directory (PGD)** / **PML4**.
    *   **Consequence:** This invalidates the **TLB (Translation Lookaside Buffer)** (unless PCID feature is used), causing immediate performance dips as the CPU relearns memory mappings.
4.  **Restore State:** Load registers from the new PCB.
5.  **Execution:** `IRET` (Interrupt Return) jumps to the new `RIP`.

## 3. Virtual Memory & Paging (x86_64)

Processes see a flat, continuous virtual memory space. The CPU (MMU) translates this to fragmented physical RAM.

### 3.1 4-Level Paging Walk (Standard x86_64)
A virtual address is 48 bits effective (canonical form).
1.  **PML4 (Page Map Level 4):** Bits 47-39 index into this table. Points to PDPT.
2.  **PDPT (Page Directory Pointer Table):** Bits 38-30. Points to Page Directory.
3.  **PD (Page Directory):** Bits 29-21. Points to Page Table.
4.  **PT (Page Table):** Bits 20-12. Points to Physical Page Frame (4KB).
5.  **Offset:** Bits 11-0. Exact byte in the 4KB page.

**Hardware Cache:** **TLB (Translation Lookaside Buffer)** stores the result of this walk. A "TLB Miss" is expensive (requires 4 memory reads to find the address).

## 4. User-Space Memory Allocators: `malloc` Wars

The kernel gives large blocks (via `mmap` or `sbrk`). User-space allocators manage the sub-division.

### 4.1 glibc `malloc` (ptmalloc)
*   **Structure:** Chunk-based. Each block has a header with size.
*   **Bins:** Free chunks are kept in linked lists ("bins") based on size (Fastbins, Smallbins, Largebins, Unsorted bin).
*   **Concurrency:** Uses **Arenas** (one per core/thread typically) to reduce lock contention.
*   **Pros:** Standard, general-purpose.
*   **Cons:** Can suffer from fragmentation; "best-fit" logic can be slow.

### 4.2 jemalloc (Facebook, Firefox, Rust default)
*   **Philosophy:** Focus on **Fragmentation Avoidance** and **Concurrency**.
*   **Design:**
    *   **Small Objects:** Grouped into **Runs**. A run contains many objects of the same **Size Class**.
    *   **Bitmap:** Uses bitmaps to track used/free slots (fast).
    *   **Thread Caches:** Aggressive caching per-thread to avoid locks entirely for common ops.
*   **Win:** Highly predictable memory footprint.

### 4.3 tcmalloc (Google)
*   **Philosophy:** Speed above all.
*   **Design:**
    *   **Thread-Local Cache:** Satisfies most allocations instantly (0 locks).
    *   **Central Free List:** When thread cache is empty, fetch a batch of objects here.
    *   **Page Heap:** Manages large memory spans.
