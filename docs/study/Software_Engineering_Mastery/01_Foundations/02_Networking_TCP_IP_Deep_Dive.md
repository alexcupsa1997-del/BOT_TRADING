# Module 1.2.a: TCP/IP & Congestion Control Deep Dive

**Date:** 2026-02-06
**Status:** Completed

## 1. The TCP State Machine & Lifecycle

### 1.1 Connection Establishment (3-Way Handshake)
1.  **SYN:** Client sends `SYN`, enters `SYN_SENT`.
2.  **SYN-ACK:** Server receives `SYN`, sends `SYN-ACK`, enters `SYN_RCVD`.
3.  **ACK:** Client receives `SYN-ACK`, sends `ACK`, enters `ESTABLISHED`. Server receives `ACK`, enters `ESTABLISHED`.

### 1.2 Connection Termination (4-Way Teardown)
This is where complexity lives.
1.  **Active Close (Client):** Sends `FIN`. Enters `FIN_WAIT_1`.
2.  **Passive Close (Server):** Receives `FIN`. Sends `ACK`. Enters `CLOSE_WAIT`.
    *   *Critical:* The Server App *must* detect EOF and call `close()` explicitly. If not, the socket hangs in `CLOSE_WAIT` forever (Resource Leak).
3.  **Server Sends FIN:** Server calls `close()`, sends `FIN`. Enters `LAST_ACK`.
4.  **Client Receives FIN:** Sends `ACK`. Enters **`TIME_WAIT`**.
    *   *Purpose:* Wait 2xMSL (Max Segment Lifetime) to catch delayed packets.
    *   *Problem:* High-load servers run out of ephemeral ports if too many sockets are in `TIME_WAIT`. (Fix: `SO_REUSEADDR` or `tcp_tw_reuse`).

## 2. Window Management: Flow vs. Congestion

Transmission rate is limited by the **Minimum** of two windows:
$$Rate = \min(rwnd, cwnd)$$

### 2.1 Flow Control (`rwnd` - Receiver Window)
*   **Goal:** Don't drown the receiver.
*   **Mechanism:** Receiver advertises "I have 64KB buffer space left" in every ACK header.
*   **Window Scaling:** Original TCP limit was 64KB ($2^{16}$). RFC 1323 added "Window Scale" option to shift bits, allowing GB-sized windows (LFN - Long Fat Networks).

### 2.2 Congestion Control (`cwnd` - Congestion Window)
*   **Goal:** Don't drown the network (routers/switches).
*   **Mechanism:** Sender maintains a hidden variable `cwnd`. It starts small and grows until packet loss occurs.

## 3. Congestion Algorithms: The Evolution

### 3.1 TCP Reno (The Classic - Loss Based)
*   **Slow Start:** Double `cwnd` every RTT (Exponential).
*   **Congestion Avoidance:** Upon `ssthresh`, increase `cwnd` linearly (+1 MSS per RTT).
*   **AIMD:** Additive Increase, Multiplicative Decrease.
    *   Packet Loss? Cut `cwnd` in half.
*   **Flaw:** In high-speed networks, recovering from a 50% cut takes too long.

### 3.2 TCP CUBIC (The Standard - Loss Based)
Default in Linux since 2.6.19.
*   **Concept:** Instead of Linear increase, use a **Cubic Function** ($f(t) = Ct^3$).
*   **Mechanism:**
    *   When loss happens, remember `W_max`.
    *   Ramp up fast to regain `W_max`, slow down near the limit, then accelerate fast if no loss is found.
*   **Benefit:** Independent of RTT. Very efficient on High Bandwidth-Delay Product (BDP) links (e.g., Transatlantic Fiber).

### 3.3 TCP BBR (The Modern - Model Based)
Google's "Bottleneck Bandwidth and RTT" (2016).
*   **Paradigm Shift:** **Loss $
eq$ Congestion.**
    *   Loss can be random (WiFi noise). Reno/Cubic panic and slow down.
*   **Mechanism:**
    *   Estimates **BtlBw** (Bottleneck Bandwidth) and **RTprop** (Round Trip Propagation).
    *   **Pacing:** Sends data at exactly the BtlBw rate.
    *   Does not fill buffers (avoids Bufferbloat).
*   **Result:** High throughput even with 1-5% packet loss. Critical for modern internet.
