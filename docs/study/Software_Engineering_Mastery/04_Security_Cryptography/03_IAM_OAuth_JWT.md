# Module 4.3: Identity & Access Management (IAM)

**Date:** 2026-02-06
**Status:** Completed

## 1. OAuth 2.0 with PKCE (Proof Key for Code Exchange)

The "Authorization Code Flow" is the gold standard. PKCE makes it safe for public clients (SPAs, Mobile) that cannot keep secrets.

### 1.1 The Vulnerability: Authorization Code Interception
*   **Scenario:** Malicious App installed on user's phone registers the same Custom URI Scheme (`myapp://`).
*   **Attack:** User authenticates. IDP redirects to `myapp://callback?code=123`. Malicious App intercepts the code and exchanges it for a token.

### 1.2 The PKCE Fix (RFC 7636)
1.  **Client:** Generates `code_verifier` (random string).
2.  **Client:** Hashes it: `code_challenge = SHA256(code_verifier)`.
3.  **Authorization Request:** Sends `code_challenge` to IDP.
4.  **Token Request:** Client sends the **original** `code_verifier`.
5.  **Validation:** IDP hashes the received `code_verifier`. If it matches the stored `code_challenge`, the token is issued.
    *   *Result:* Malicious App might get the Code, but it doesn't have the `code_verifier`, so the exchange fails.

## 2. JSON Web Tokens (JWT) Security

### 2.1 The "None" Algorithm Attack
*   **The Flaw:** JWT Header contains `{"alg": "none"}`.
*   **The Attack:** Attacker changes payload to `{"admin": true}`, sets `alg: none`, and removes signature.
*   **The Fix:**
    *   **Explicitly Disable** "none" algorithm in your verifier.
    *   **Hardcode** the algorithm (e.g., "Always expect RS256").

### 2.2 Validation Checklist
Don't just check the signature.
1.  **`exp` (Expiration):** Is `now < exp`?
2.  **`nbf` (Not Before):** Is `now >= nbf`?
3.  **`iss` (Issuer):** Did *my* Auth Server issue this?
4.  **`aud` (Audience):** Is this token meant for *me*?

## 3. Session Management: Stateless vs Stateful

### 3.1 Stateless JWTs
*   **Pros:** Scalable (No DB lookup per request).
*   **Cons:** **Hard to Revoke.**
    *   If user's laptop is stolen, the JWT works until `exp`.
    *   *Mitigation:* Short `exp` (15 mins) + Sliding Session via Refresh Tokens.

### 3.2 Reference Tokens (Stateful)
*   **Mechanism:** Client gets a random string (Reference). The actual data is in Redis/DB.
*   **Flow:** API receives Token -> Queries Redis -> Gets Claims.
*   **Pros:** Instant Revocation (Delete key from Redis).
*   **Cons:** Latency (DB lookup on every request).

### 3.3 The Hybrid Approach (The Best of Both)
*   Use JWTs for **Access Tokens** (Short life, fast).
*   Use Reference Tokens for **Refresh Tokens** (Long life, revokable).
*   *Revocation:* If user logs out, delete the Refresh Token. Access Token dies naturally in 15 mins.
