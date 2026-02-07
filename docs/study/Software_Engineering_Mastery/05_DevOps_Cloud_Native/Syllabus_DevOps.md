# Phase 5: DevOps, SRE & Cloud Native - Syllabus

"It works on my machine" is not a valid excuse.

## Module 5.1: Container Internals (Linux Plumbing)
**Goal:** Understand that "Containers" don't exist; they are just isolated processes.
*   **Namespaces (Isolation):**
    *   PID (Process ID), NET (Networking), MNT (Filesystem), UTS (Hostname), IPC (Inter-Process Comm), USER (UID mapping).
*   **Cgroups (Limits):**
    *   Controlling CPU, Memory, I/O.
    *   OOM Killer interaction.
*   **Filesystems:**
    *   **OverlayFS:** Union mounting (Image Layers). Copy-on-Write (CoW).

## Module 5.2: Kubernetes Architecture
**Goal:** Orchestrate containers at scale.
*   **The Control Plane:**
    *   **API Server:** The front door. RESTful, stateless.
    *   **Etcd:** The brain (Consistent KV store).
    *   **Scheduler:** Assigns Pods to Nodes (Bin packing).
    *   **Controller Manager:** The reconciliation loops (State A -> State B).
*   **The Worker Node:**
    *   **Kubelet:** Talks to the Container Runtime (CRI).
    *   **Kube-Proxy:** Manages `iptables` / `IPVS` for Service discovery.
*   **Networking:**
    *   CNI (Container Network Interface).
    *   The "Pause" container (Holding the network namespace).

## Module 5.3: Site Reliability Engineering (SRE)
**Goal:** Treat operations as a software problem.
*   **The Metrics:**
    *   **SLI (Indicator):** "Latency is 200ms".
    *   **SLO (Objective):** "99% of requests < 300ms".
    *   **SLA (Agreement):** "If we fail SLO, we pay you money".
*   **Observability:**
    *   **Metrics (Prometheus):** Aggregatable data (Counters, Gauges, Histograms).
    *   **Tracing (OpenTelemetry):** Request flow across services.
    *   **Logging:** Events in time.
*   **Error Budgets:** The balance between Innovation and Stability.
