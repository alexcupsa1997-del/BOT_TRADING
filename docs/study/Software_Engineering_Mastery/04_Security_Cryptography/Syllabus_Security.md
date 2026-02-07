# Phase 4: Security & Cryptography - Syllabus

Security is not a feature; it's a constraint.

## Module 4.1: Application Security (AppSec)
**Goal:** Prevent bad actors from exploiting logical vulnerabilities.
*   **Injection Attacks:**
    *   **SQLi:** Prepared Statements & Parameterized Queries.
    *   **Command Injection:** Avoiding `exec()`.
*   **Browser Security:**
    *   **XSS (Cross-Site Scripting):** Reflected, Stored, DOM.
    *   **CSP (Content Security Policy):** The `script-src` directive and Nonces.
    *   **CSRF (Cross-Site Request Forgery):** Anti-CSRF Tokens and `SameSite` cookies.
    *   **CORS (Cross-Origin Resource Sharing):** Preflight requests (`OPTIONS`).

## Module 4.2: Cryptography Engineering
**Goal:** Protect data at rest and in transit.
*   **Symmetric Encryption:**
    *   **AES-GCM:** Authenticated Encryption (Confidentiality + Integrity).
    *   **Modes:** Why `ECB` is insecure (Pattern leak).
*   **Asymmetric Encryption:**
    *   **RSA:** Integer factorization. Large keys (2048+ bits).
    *   **ECC (Elliptic Curve):** Discrete Logarithm. Small keys (256 bits), high performance (X25519).
*   **Hashing & KDFs:**
    *   **Cryptographic Hash:** SHA-256 (Collision resistance).
    *   **Password Hashing (KDF):** Argon2, bcrypt, scrypt. (Work factors, Salt, Memory Hardness).

## Module 4.3: Identity & Access (IAM)
**Goal:** Authentication (Who are you?) and Authorization (What can you do?).
*   **OAuth 2.0:**
    *   **Flows:** Authorization Code with PKCE (for SPAs/Mobile). Client Credentials (Machine-to-Machine).
    *   **Scopes:** Granular permission.
*   **OIDC (OpenID Connect):**
    *   The Identity Layer on top of OAuth. The `ID Token`.
*   **JWT (JSON Web Token):**
    *   **Structure:** Header.Payload.Signature.
    *   **Security:** `alg: none` attack. Key rotation (JWKS).
*   **Session Management:**
    *   JWT (Stateless) vs Reference Tokens (Stateful/Revocable).
