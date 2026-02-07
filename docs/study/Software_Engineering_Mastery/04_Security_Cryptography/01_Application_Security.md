# Module 4.1: Application Security (AppSec)

**Date:** 2026-02-06
**Status:** Completed

## 1. Cross-Site Scripting (XSS)

The ability to execute malicious JS in a victim's browser.

### 1.1 Types
1.  **Reflected:** Payload comes from the URL (`?search=<script>...`). Server echoes it back in HTML.
    *   *Defense:* Output Encoding (Context-aware).
2.  **Stored:** Payload is saved in DB (e.g., Comment). Served to every visitor.
    *   *Defense:* Output Encoding + CSP.
3.  **DOM-Based:** Payload never leaves the browser. `document.location.hash` -> `innerHTML`.
    *   *Defense:* Avoid `innerHTML`, `document.write`. Use `textContent`.

### 1.2 Content Security Policy (CSP)
*   **The Concept:** Allowlist for scripts. "Only run scripts from `mydomain.com`".
*   **The Problem:** Whitelists are hard to maintain (Google Analytics, CDNs).
*   **Modern Approach (Strict CSP):**
    *   **Nonce-based:** `<script nonce="random123">`.
    *   **`strict-dynamic`:** If a trusted script (with nonce) loads another script, trust the child too.
    *   *Header:* `Content-Security-Policy: script-src 'nonce-{random}' 'strict-dynamic';`

## 2. Cross-Site Request Forgery (CSRF)

Forcing a logged-in user to perform an action without their consent.

### 2.1 The Attack
*   User is logged into `bank.com` (Session cookie is set).
*   User visits `evil.com`.
*   `evil.com` has `<img src="https://bank.com/transfer?to=attacker&amount=1000">`.
*   Browser sends the request *with* the `bank.com` cookie (Ambient Authority).

### 2.2 The Defenses
1.  **SameSite Cookies:**
    *   **`Strict`:** Cookie never sent on cross-site requests. (Good for banks, bad for linking).
    *   **`Lax` (Default):** Sent on "Top-Level Navigations" (Clicking a link) but NOT on sub-resources (Images, POST forms).
    *   **`None`:** Sent everywhere (Must be `Secure`).
2.  **Anti-CSRF Tokens:**
    *   Server generates random token. Puts it in hidden form field.
    *   Cookie is *automatically* sent. Token is *manually* sent.
    *   Attacker cannot read the token (SOP), so cannot forge the form.

## 3. SQL Injection (SQLi)

### 3.1 The Mechanism
Code: `query = "SELECT * FROM users WHERE name = '" + userInput + "'"`
Input: `' OR '1'='1`
Result: `SELECT * FROM users WHERE name = '' OR '1'='1'` (Always True).

### 3.2 The Solution: Separation of Code & Data
*   **Prepared Statements:**
    1.  **Prepare:** Send `SELECT * FROM users WHERE name = ?` to DB. DB parses, optimizes, and caches the *Plan*.
    2.  **Execute:** Send `[' OR '1'='1']` as a raw value.
    3.  **Result:** DB looks for a user whose literal name is `' OR '1'='1`. Safe.
