# Module 5.2: Kubernetes Architecture Deep Dive

**Date:** 2026-02-06
**Status:** Completed

## 1. The Control Plane Brain: Etcd

Kubernetes is just a CRUD app over Etcd.
*   **Data Model:** Key-Value store. Consistent (CP).
*   **MVCC (Multi-Version Concurrency Control):**
    *   Etcd does NOT overwrite keys. It appends new revisions.
    *   `Key="pod1" Rev=1` -> `Key="pod1" Rev=2`.
*   **The Watch Mechanism:**
    *   Controllers do not Poll. They **Watch**.
    *   API Server sends `Watch(Rev=100)`. Etcd streams all events > Rev 100.
    *   *Reliability:* If connection breaks, client reconnects with `LastRevision`. Etcd replays history from that point (Time Travel).

## 2. The Controller Pattern (SharedInformer)

How does `DeploymentController` manage 1000 pods without killing the API Server?

### 2.1 The Components
1.  **Reflector:** Performs `List()` (Initial state) and `Watch()` (Updates). Pushes objects to a DeltaFIFO queue.
2.  **Informer:** Popps from DeltaFIFO. Updates the **Local Cache** (Thread-safe Store).
3.  **Indexer:** Allows looking up objects by field (e.g., "Find all Pods on Node X").
4.  **WorkQueue:** If an object changes, its **Key** (namespace/name) is pushed here.
5.  **Worker:** Pops Key. Gets *latest* state from Cache. Reconciles.

### 2.2 Why is this brilliant?
*   **Edge Triggered:** You get notified on change.
*   **Level Driven Logic:** The Worker always looks at the *current* state in Cache, not the specific event. If you missed 5 updates, you just see the final result. (Self-healing).

## 3. Pod Networking (The "Flat" Network)

**Rule:** Every Pod gets an IP. No NAT between Pods.

### 3.1 The Plumbing (CNI)
1.  **Pod Creation:** Kubelet calls CNI Plugin (e.g., Calico/Flannel).
2.  **veth Pair:** CNI creates a virtual cable.
    *   `eth0` (Inside Pod Namespace).
    *   `vethXXXX` (Host Namespace).
3.  **Bridge:** CNI attaches `vethXXXX` to a Linux Bridge (`cni0`).
4.  **Routing:**
    *   **Same Node:** `Pod A -> cni0 -> Pod B`. (L2 Switching).
    *   **Cross Node:** `Pod A -> cni0 -> Host Routing Table -> VXLAN/BGP -> Dest Node`.

### 3.2 The Pause Container
*   *Observation:* In `docker ps`, you see `k8s_POD_...` containers.
*   *Purpose:* It holds the **Network Namespace**.
*   *Why?* If the Application Container crashes and restarts, it joins the *existing* Pause container's namespace. Result: **IP Address stays the same** across restarts.
