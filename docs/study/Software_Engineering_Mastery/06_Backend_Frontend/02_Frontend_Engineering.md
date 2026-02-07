# Module 6.2: Frontend Engineering

**Date:** 2026-02-06
**Status:** Completed

## 1. Rendering Patterns & Hydration

### 1.1 The "Uncanny Valley" of Hydration
*   **Process:** Server sends HTML (fast). Browser paints it. JS downloads. React "hydrates" (attaches listeners).
*   **The Mismatch Error:** If Server HTML $
eq$ Client Expected HTML (e.g., `<div>{Math.random()}</div>`), React throws a warning and might **discard the entire server tree** and re-render from scratch. Performance disaster.
*   **Fix:** Ensure deterministic rendering. Use `useEffect` for browser-specific data (`window.width`).

### 1.2 The Critical Rendering Path (CRP)
*   **Steps:**
    1.  HTML -> DOM.
    2.  CSS -> CSSOM.
    3.  DOM + CSSOM -> **Render Tree** (Visible elements only).
    4.  **Layout** (Geometry/Reflow): Calculate X,Y, Width, Height.
    5.  **Paint:** Fill pixels.
    6.  **Composite:** Layering (z-index, transforms).
*   **Optimization:**
    *   **Render Blocking Resources:** CSS is render-blocking. JS is render-blocking (unless `defer`/`async`).
    *   **CSS Triggers:** Changing `width` triggers Layout (Expensive). Changing `transform` (GPU) triggers Composite only (Cheap).

## 2. Micro-Frontends: Module Federation

How to let Team A deploy Header independently of Team B's Footer?

### 2.1 Webpack Module Federation
*   **Architecture:**
    *   **Host:** The main app shell.
    *   **Remote:** A separately built app (e.g., `checkout`).
*   **Mechanism:**
    *   Remote builds a `remoteEntry.js` (Manifest).
    *   Host loads `remoteEntry.js` at runtime.
    *   Host imports `checkout/Button`.
*   **Shared Dependencies:**
    *   If Host has React v18 and Remote needs React v18, Webpack **shares** the single instance. No double download.
    *   If versions differ incompatible, it downloads both (Safety).

## 3. State Management

*   **Redux:** Single Immutable State Tree. Great for debugging (Time Travel). Boilerplate heavy.
*   **Context API:** Built-in. Good for low-frequency updates (Theme, User). **Bad for high-frequency** (Text input) -> Triggers re-render of all consumers.
*   **Atomic (Recoil/Jotai):** Fine-grained updates. Only components subscribed to `atomX` re-render.
