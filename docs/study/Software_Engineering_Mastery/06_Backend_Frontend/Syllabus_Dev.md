# Phase 6: Modern Backend & Frontend - Syllabus

Code that runs on the server vs Code that runs in the browser.

## Module 6.1: Backend Concurrency Models
**Goal:** Handle 10k concurrent connections.
*   **Node.js (Event Driven):**
    *   **Libuv:** The C library handling the thread pool.
    *   **Phases:** Timers, Pending, Poll, Check, Close.
    *   `process.nextTick()` vs `Promise.then()`.
*   **Go (CSP - Communicating Sequential Processes):**
    *   **Goroutines:** 2KB stack vs 1MB OS Thread.
    *   **M:N Scheduler:** Mapping M Goroutines to N OS Threads.
*   **Java (Project Loom):**
    *   **Virtual Threads:** Blocking code that doesn't block OS threads.

## Module 6.2: Frontend Engineering
**Goal:** 60 FPS and instant interactions.
*   **Rendering Patterns:**
    *   **CSR:** Client-Side Rendering (Empty HTML, JS fetches data).
    *   **SSR:** Server-Side Rendering (HTML generated on request).
    *   **SSG:** Static Site Generation (HTML generated at build time).
    *   **ISR:** Incremental Static Regeneration (Update static pages on-demand).
*   **The Critical Rendering Path:**
    *   DOM + CSSOM = Render Tree. Layout. Paint. Composite.
*   **State Management:**
    *   Prop Drilling vs Context vs Global Store (Redux).

## Module 6.3: WebAssembly (Wasm)
**Goal:** Near-native performance in the browser.
*   **Architecture:** Stack machine. Linear Memory.
*   **Use Cases:** Video editing (Figma), 3D Games (Unity), Cryptography.
