# Phase 2: Software Architecture & Design - Syllabus

This phase moves from "how the machine works" to "how to structure complex software".

## Module 2.1: Code-Level Architecture & Principles
**Goal:** Write maintainable, testable code within a single service.
*   **SOLID Deep Dive:**
    *   **LSP (Liskov Substitution):** Covariance (Return types) and Contravariance (Argument types). Preconditions and Postconditions.
    *   **DIP (Dependency Inversion):** The boundary between high-level policy and low-level detail.
*   **Architectural Styles:**
    *   **Clean Architecture (Uncle Bob):** The Dependency Rule. Entities vs Use Cases.
    *   **Hexagonal (Ports & Adapters):** Decoupling the "Core" from "Infrastructure" (DB, Web, CLI).
    *   **Functional Core, Imperative Shell:** The functional programming approach to architecture.

## Module 2.2: Distributed System Patterns
**Goal:** Coordinate state across multiple unreliable machines.
*   **Data Consistency:**
    *   **Sagas:** Choreography (Events) vs Orchestration (Central Controller).
    *   **The Outbox Pattern:** Guaranteeing "At Least Once" delivery in dual-write scenarios (DB + Message Bus).
    *   **2PC (Two-Phase Commit):** Why it's slow and when to use it (XA Transactions).
*   **Resiliency:**
    *   **Circuit Breaker:** State machine (Closed -> Open -> Half-Open).
    *   **Bulkhead:** Isolating failure domains (Thread pools, Connection pools).
    *   **Retry Patterns:** Exponential Backoff, Jitter, and "Retry Storms".

## Module 2.3: System Design & Scalability
**Goal:** Handle high load and massive data.
*   **The CAP Theorem & PACELC:** Trade-offs between Latency and Consistency.
*   **Caching Strategies:**
    *   **Patterns:** Cache-Aside, Write-Through, Write-Back.
    *   **Eviction:** LRU, LFU, Window TinyLFU.
    *   **Problems:** Cache Stampede (Thundering Herd), Cache Penetration.
*   **Sharding & Partitioning:**
    *   **Consistent Hashing:** Virtual nodes, Ring architecture.
    *   **Hot Partitions:** Handling celebrity keys.
*   **Load Balancing:**
    *   L4 (Transport) vs L7 (Application).
    *   **Algorithms:** Round Robin, Least Connections, Power of Two Choices.

## Module 2.4: API Design & Evolution
**Goal:** Create interfaces that survive change.
*   **Styles:** REST (HATEOAS), GraphQL (N+1 Problem), gRPC (Protobuf).
*   **Evolution:** Versioning strategies (URI, Header, Content Negotiation).
*   **Idempotency:** Designing safe retries.
