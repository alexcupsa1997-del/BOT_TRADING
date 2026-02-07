# Phase 1: Computer Science & Systems Engineering Foundations - Syllabus

This phase focuses on the low-level machinery that powers all software. A deep understanding here distinguishes a "coder" from a "software engineer".

## Module 1.1: Operating Systems Internals
**Goal:** Understand how software interacts with hardware.
*   **Kernel Architecture:** Monolithic vs. Microkernels, User Space vs. Kernel Space, System Calls.
*   **Process Management:** Processes vs. Threads, PCB (Process Control Block), Context Switching, CPU Scheduling Algorithms (CFS, Round Robin).
*   **Concurrency & Synchronization:** Race Conditions, Critical Sections, Mutexes, Semaphores, Monitors, Deadlocks (Prevention & Avoidance), Atomics.
*   **Memory Management:** Virtual Memory, Paging & Segmentation, TLB (Translation Lookaside Buffer), Page Faults, Swapping, Heap vs. Stack allocation, Memory Allocators (malloc/free implementations).
*   **I/O Systems:** Interrupts, DMA (Direct Memory Access), Buffered I/O, File Descriptors, Async I/O (epoll, kqueue, IOCP).
*   **File Systems:** Inodes, Journaling, VFS (Virtual File System), Hard Links vs. Soft Links.

## Module 1.2: Networking Deep Dive
**Goal:** Understand how systems communicate.
*   **The Physical to Application Layer:** OSI Model Deep Dive.
*   **Transport Layer (Layer 4):** TCP internals (Three-way handshake, Window Scaling, Congestion Control: Reno/Cubic/BBR, Head-of-line blocking), UDP (Use cases, QUIC).
*   **Network Layer (Layer 3):** IP addressing, Subnetting, BGP, Routing Tables, NAT.
*   **Application Layer (Layer 7):** HTTP/1.1 vs HTTP/2 (Multiplexing, Header Compression) vs HTTP/3 (QUIC), DNS (Records, Recursion), TLS/SSL (Handshake, Certificates, SNI), WebSockets.

## Module 1.3: Compilers, Interpreters & Runtimes
**Goal:** Understand how code becomes execution.
*   **Compilation Pipeline:** Lexing, Parsing, Semantic Analysis, IR (Intermediate Representation), Code Generation.
*   **Runtime Environments:** Stack Frames, Calling Conventions, ABI (Application Binary Interface).
*   **Memory Safety:** Manual management (C/C++) vs. Garbage Collection (Tracing, Mark-and-Sweep, Generational GC).
*   **JIT Compilation:** How V8 or JVM optimizes code at runtime (Hot spots, de-optimization).

## Module 1.4: Advanced Data Structures & Algorithms
**Goal:** Optimize for performance and scale.
*   **Probabilistic Data Structures:** Bloom Filters, Count-Min Sketch, HyperLogLog.
*   **Advanced Trees:** B-Trees & B+ Trees (Database indexing), LSM Trees (Log-Structured Merge-trees), Red-Black Trees.
*   **Graph Algorithms:** Dijkstra, A*, Max Flow/Min Cut, Topological Sort.
*   **Distributed Algorithms:** Consistent Hashing, Merkle Trees.
