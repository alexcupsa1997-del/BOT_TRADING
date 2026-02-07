# Module 1.1.d: File Systems & Storage Deep Dive

**Date:** 2026-02-06
**Status:** Completed

## 1. The VFS (Virtual File System)
VFS is the abstraction layer that allows Linux to handle `ext4`, `NTFS`, and `/proc` transparently.

### 1.1 The Big Four Objects
1.  **Superblock:** Represents a mounted filesystem (e.g., `/dev/sda1` on `/`).
    *   Stores: Block size, Magic Number, Inode/Block usage bitmaps.
    *   *Kernel Op:* `alloc_super()`.
2.  **Inode (Index Node):** Represents a specific object (file/directory).
    *   Stores: Permissions, UID, GID, Size, Time, **Pointers to Data Blocks**.
    *   *Key:* Unique ID Number. Does **NOT** store the filename.
3.  **Dentry (Directory Entry):** Represents a path component.
    *   Links "Filename" -> "Inode".
    *   Example: Path `/home/user` has three dentries: `/`, `home`, `user`.
    *   **Dentry Cache (dcache):** Huge hash table (`d_lookup`) to speed up path resolution.
4.  **File:** Represents an open file instance (File Descriptor).
    *   Stores: Current Offset (`f_pos`), Mode (Read/Write).
    *   *Note:* Two processes can have two `File` objects pointing to the same `Inode`.

## 2. Ext4 Internals: The Standard

### 2.1 Inode Structure & Data Addressing
*   **Legacy (Ext2/3):** Block Pointers.
    *   12 Direct Pointers.
    *   1 Indirect (Points to a block of pointers).
    *   1 Doubly Indirect.
    *   1 Triply Indirect.
    *   *Problem:* Huge metadata overhead for large contiguous files.
*   **Modern (Ext4):** **Extents**.
    *   Instead of listing every block, it says: "Start at Block 5000, Length 100".
    *   Stored in a **Tree** structure inside the inode (`i_block` array).
    *   *Benefit:* CPU/Disk efficient for large files.

### 2.2 Journaling (Write-Ahead Logging)
Protects metadata integrity during crashes.
*   **Mode: `data=ordered` (Default):**
    1.  Write **Data** to main disk.
    2.  Write **Metadata** to Journal.
    3.  **Commit** Journal.
    4.  Checkpoint (Move metadata to final location).
    *   *Safety:* File content is guaranteed to be "new" or "old", never garbage.
*   **Mode: `data=writeback`:**
    *   Metadata is journaled, Data is not ordered.
    *   *Risk:* After crash, file might contain old garbage data from deleted files.
*   **Mode: `data=journal`:**
    *   Write **Data AND Metadata** to journal first.
    *   *Safety:* Maximum.
    *   *Cost:* Writes everything twice. Slow.

## 3. High-Performance I/O: `io_uring` vs `epoll`

### 3.1 The "Ready" Model: `epoll`
*   **Mechanism:** "Tell me when I can read."
*   **Flow:**
    1.  `epoll_wait()` (Sleep until ready).
    2.  Wake up.
    3.  `read()` (Syscall).
    4.  Kernel copies data to user buffer.
    5.  Return.
*   **Overhead:** Syscall per operation + Data Copy.

### 3.2 The "Completion" Model: `io_uring` (Linux 5.1+)
*   **Mechanism:** "Here is a buffer. Fill it and wake me when done."
*   **Architecture:** Two Shared Ring Buffers (mapped in User & Kernel space).
    *   **Submission Queue (SQ):** User pushes requests.
    *   **Completion Queue (CQ):** Kernel pushes results.
*   **Zero-Syscall Mode:**
    *   If `IORING_SETUP_SQPOLL` is set, a kernel thread polls the SQ.
    *   User just pushes to ring. Kernel picks it up. **Zero syscalls.**
*   **Performance:** Can reach millions of IOPS per core. Used by modern DBs (Postgres/MySQL) and Web Servers.
