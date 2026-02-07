# Module 4.2: Cryptography Engineering

**Date:** 2026-02-06
**Status:** Completed

## 1. Symmetric Encryption: AES-GCM

AES (Advanced Encryption Standard) is the standard. But the **Mode** matters.

### 1.1 The Dangers of ECB
*   **ECB (Electronic Codebook):** Encrypts each 16-byte block independently.
    *   *Flaw:* Identical plaintext blocks produce identical ciphertext blocks.
    *   *Result:* Patterns remain visible (The "Penguin" image).

### 1.2 Authenticated Encryption (AEAD)
We need Confidentiality AND Integrity.
*   **AES-GCM (Galois/Counter Mode):**
    *   **Encryption:** Uses CTR mode (Stream cipher).
    *   **Authentication:** Uses GMAC (Galois Message Authentication Code) to produce a "Tag".
    *   *Mechanism:*
        1.  Sender encrypts Data -> Ciphertext.
        2.  Sender computes Tag over (Ciphertext + Metadata).
        3.  Receiver decrypts ONLY if Tag matches.
*   **The IV (Initialization Vector) Rule:**
    *   **NEVER reuse a Nonce/IV** with the same key.
    *   *Catastrophe:* If IV is reused, attacker can recover the XOR of two plaintexts and eventually the Authentication Key.

## 2. Password Hashing (KDFs)

Speed is the enemy.

### 2.1 The GPU Threat
*   A GPU can calculate 10 billion SHA-256 hashes per second.
*   If you store passwords as `SHA256(pass)`, they will be cracked in minutes.

### 2.2 Argon2 (The Winner)
*   **Memory Hardness:** Designed to fill RAM.
    *   GPUs have massive compute but limited high-speed memory per core.
    *   Argon2 forces the attacker to buy expensive RAM, not just GPUs.
*   **Variants:**
    *   `Argon2d`: Data-dependent (Fast, side-channel risk). Good for crypto-currencies.
    *   `Argon2id`: Hybrid. Resists side-channels AND GPU cracking. **Use this for passwords.**

## 3. Asymmetric Encryption: ECC vs RSA

### 3.1 The Math
*   **RSA:** Security depends on **Integer Factorization** ($N = p 	imes q$).
    *   *Key Size:* 2048-bit or 4096-bit required. Slow key gen.
*   **ECC (Elliptic Curve):** Security depends on **Discrete Logarithm Problem**.
    *   "Given point $P$ and $Q = kP$, find $k$".
    *   *Key Size:* 256-bit ECC $\approx$ 3072-bit RSA.

### 3.2 Why ECC wins?
*   **Performance:** Faster handshakes (smaller keys to transmit).
*   **Energy:** Less CPU usage (Critical for mobile/IoT).
*   **Standard Curve:** `X25519` (Curve25519) is the modern standard for Key Exchange (TLS 1.3).
