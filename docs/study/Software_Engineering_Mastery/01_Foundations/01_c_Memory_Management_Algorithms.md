# Module 1.1.c: Memory Management Algorithms Deep Dive

**Date:** 2026-02-06
**Status:** Completed

## 1. Kernel Space Allocators (Physical Memory)

The kernel manages physical RAM. It must satisfy requests for contiguous page frames (e.g., for DMA) and small objects (e.g., `task_struct`).

### 1.1 The Buddy System (Page Allocator)
The **Buddy System** solves the problem of External Fragmentation for large, contiguous blocks.
*   **The Algorithm:**
    *   Memory is managed in lists of **Orders** (0 to 11). Order $N$ represents $2^N$ pages.
    *   **Allocation:** Request for size $S$.
        1.  Calculate minimal Order $K$ such that $2^K 	imes PageSize \ge S$.
        2.  Check list for Order $K$.
        3.  If empty, go to Order $K+1$.
        4.  **Split:** Take block of $K+1$, split into two buddies of Order $K$. Use one, add other to Order $K$ list. Recursive until found.
    *   **Deallocation (Coalescing):**
        1.  Free block $B$.
        2.  Check address of "Buddy" ($Address \oplus Size$).
        3.  If Buddy is also free, **Merge** into block of Order $K+1$.
        4.  Repeat.

### 1.2 The SLAB/SLUB/SLOB Allocators (Object Allocator)
The Buddy System is too coarse (4KB min). We need small objects (32 bytes, 128 bytes).
*   **SLAB (Legacy):**
    *   Uses caching heavily. Each object type (inode, dentry) has a specific cache.
    *   Complex metadata. Good for older hardware, bad for high-core-count scaling.
*   **SLUB (Unqueued - Default):**
    *   **Design:** Simplifies metadata. Most metadata is stored in the `struct page` of the physical frame itself, not in separate headers.
    *   **Performance:** Better CPU cache locality. Merges slabs of similar size classes.
*   **SLOB (Simple - Embedded):**
    *   Just a linked list of blocks. High fragmentation, but tiny code footprint. (Removed in Linux 6.4).

## 2. User Space Allocators (`malloc` Internals)

How does `glibc` or `dlmalloc` manage the heap provided by `brk`/`mmap`?

### 2.1 The Chunk Structure & Boundary Tags
*   **Memory Layout:**
    ```
    [ Header: Size | Flags ]
    [      User Data       ]
    [ Footer: Size         ] (Only if free, usually)
    ```
*   **Boundary Tags (Knuth's Algorithm):**
    *   **Problem:** When freeing pointer `P`, is `P - 1` free? How do we find the start of the previous block?
    *   **Solution:** The **Footer** of the *previous* block sits right before the **Header** of the *current* block.
    *   **Coalescing:**
        1.  Check `(P - 4 bytes)`. It's the previous block's footer. Get size $S_{prev}$.
        2.  Go to `P - S_{prev}` to find the previous header.
        3.  Check previous header's "Free" bit. If free, merge.
        4.  Check next block's header. If free, merge.

### 2.2 Binning Strategies
*   **Fastbins (LIFO):**
    *   Small chunks (16-80 bytes).
    *   Stored in singly-linked lists.
    *   **No Coalescing:** Speed optimization. "If I freed a 32-byte chunk, I'll likely need a 32-byte chunk soon."
*   **Smallbins (FIFO):**
    *   Chunks < 512 bytes.
    *   Doubly-linked lists.
    *   Coalescing enabled.
*   **Unsorted Bin:**
    *   The "Cache" of free chunks.
    *   When a chunk is freed, it goes here first.
    *   If `malloc` doesn't find a chunk in Fast/Small bins, it scans Unsorted. If a chunk here fits, take it. If not, move it to the correct Small/Large bin.
*   **Largebins (Sorted):**
    *   > 512 bytes.
    *   Sorted by size (Skip list or Tree) to support "Best Fit" allocation.

### 2.3 `brk` vs `mmap`
*   **`brk`:** Moves the "program break" (end of heap) up. Fast, but memory must be contiguous. Can't return memory to OS easily if "middle" is still used.
*   **`mmap`:** Allocates distinct anonymous pages. Slower syscall, but can be freed individually. Used for large allocations (> 128KB).
