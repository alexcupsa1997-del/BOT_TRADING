# Module 1.2.b: Modern Application Protocols (HTTP/2, HTTP/3, TLS)

**Date:** 2026-02-06
**Status:** Completed

## 1. The Head-of-Line (HOL) Blocking Problem

The history of HTTP is a history of fighting HOL Blocking.
*   **HTTP/1.0:** New TCP connection for every file. (Slow, high RTT overhead).
*   **HTTP/1.1:**
    *   **Keep-Alive:** Reuse TCP connection.
    *   **Pipelining:** Send `Req1, Req2` without waiting.
    *   **The HOL Problem:** Server must send `Resp1` before `Resp2`. If `Req1` needs a DB Query (2s) and `Req2` is a static image (1ms), the image is blocked for 2s.
*   **HTTP/2 (RFC 7540):**
    *   **Multiplexing:** Split messages into binary **Frames** with Stream IDs.
    *   **Interleaving:** `Stream 1` and `Stream 2` frames are mixed on the wire.
    *   **App-Layer HOL Solved:** Fast static assets are not blocked by slow DB queries.
    *   **The *New* HOL Problem (TCP Level):** TCP guarantees order. If Packet 10 is lost, Packet 11 (even if it belongs to a different, independent stream) sits in the kernel buffer waiting for Packet 10. **Result:** On lossy networks, HTTP/2 is *slower* than HTTP/1.1.

## 2. HTTP/3 & QUIC (RFC 9000)

Google (gQUIC) -> IETF (QUIC). The move to UDP.

### 2.1 The Architecture
*   **Transport:** UDP (User Datagram Protocol). No kernel handshake.
*   **Reliability:** Implemented in User Space (on top of UDP).
*   **Streams:** QUIC streams are independent. Loss of a packet in Stream A *does not* block Stream B.

### 2.2 Key Features
1.  **Connection Migration:**
    *   TCP uses 4-tuple (SrcIP, SrcPort, DstIP, DstPort). Switching from WiFi to LTE changes SrcIP -> Connection breaks.
    *   QUIC uses **CID (Connection ID)**. A 64-bit ID persists across IP changes. Seamless handover.
2.  **QPACK:**
    *   HTTP/2 used **HPACK**. It relied on a global stateful table. If a packet updating the table is lost, all future header decoding stalls.
    *   HTTP/3 uses **QPACK**. It separates the "Compression Context" stream from the "Data" stream. Allowed out-of-order delivery without breaking compression context.

## 3. TLS 1.3 Deep Dive (RFC 8446)

Encryption is no longer a layer *on top*; in QUIC, it's baked in.

### 3.1 Handshake Latency
*   **TLS 1.2:** 2-RTT (ClientHello -> ServerHello -> KeyExchange -> Finished).
*   **TLS 1.3:** 1-RTT.
    *   Client guesses the Key Share (usually Elliptic Curve Diffie-Hellman - X25519) and sends it in the *first* packet (ClientHello).
    *   If Server accepts, it sends ServerHello + Finished. Immediate encryption.

### 3.2 0-RTT Resumption (Early Data)
*   **Mechanism:** If Client has talked to Server before, they share a **PSK (Pre-Shared Key)** or Session Ticket.
*   **Action:** Client sends encrypted HTTP Request *inside* the very first packet (ClientHello).
*   **The Risk: Replay Attacks.**
    *   Attacker captures the 0-RTT packet.
    *   Attacker resends it 10 times.
    *   If the request was `POST /pay-money`, user pays 10 times.
*   **Mitigation:**
    *   Server must implement **Anti-Replay** (Time windows, Nonce cache).
    *   **Idempotency:** Browsers/Apps should ONLY use 0-RTT for Safe Methods (`GET`, `HEAD`).

## 4. Summary: The Stack Evolution

| Layer | Old Stack | New Stack (HTTP/3) |
| :--- | :--- | :--- |
| **App** | HTTP/1.1 or HTTP/2 | HTTP/3 |
| **Security** | TLS 1.2 | TLS 1.3 (Integrated) |
| **Transport** | TCP | QUIC |
| **Network** | IP | IP |
| **Link** | UDP | UDP |
