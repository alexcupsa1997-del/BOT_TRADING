# Module 2.1: Code-Level Architecture & Principles

**Date:** 2026-02-06
**Status:** Completed

## 1. SOLID Deep Dive: The Tricky Parts

### 1.1 Liskov Substitution Principle (LSP)
Most people know "Subtypes must be substitutable". The hard part is **Variance**.
*   **Covariance (Return Types):**
    *   *Definition:* If `Dog` is a subtype of `Animal`, then `Producer<Dog>` is a subtype of `Producer<Animal>`.
    *   *Rule:* Overridden methods can return a *more specific* type.
    *   *Example:* `AnimalFactory.create()` returns `Animal`. `DogFactory.create()` returns `Dog`. Safe because caller expects `Animal` and gets `Dog`.
*   **Contravariance (Argument Types):**
    *   *Definition:* If `Dog` is a subtype of `Animal`, then `Consumer<Animal>` is a subtype of `Consumer<Dog>`.
    *   *Rule:* Overridden methods can accept a *more general* type.
    *   *Example:* `DogHandler.handle(Dog d)` can be replaced by `AnimalHandler.handle(Animal a)`. Safe because `AnimalHandler` can handle any animal, including a dog.

### 1.2 Dependency Inversion Principle (DIP)
*   **The Rule:** High-level modules (Business Rules) should not depend on low-level modules (DB, UI). Both should depend on abstractions.
*   **The "Inversion":**
    *   *Traditional:* Controller -> Service -> Repository (Implementation). Flow of control and source code dependency point in the same direction.
    *   *Inverted:* Controller -> Service -> Repository (Interface) <- Repository (Implementation). Flow of control is the same, but source dependency is **inverted** against the flow.

## 2. Architectural Styles

### 2.1 Clean Architecture (The Layered Onion)
*   **Structure:**
    1.  **Entities (Core):** Enterprise-wide business rules. No dependencies.
    2.  **Use Cases (Application):** Application-specific rules. Orchestrates entities.
    3.  **Interface Adapters:** Convert data from Use Cases to Format X (SQL, HTML).
    4.  **Frameworks & Drivers:** The DB, the Web Framework.
*   **The Key Rule:** Source code dependencies *always* point inward.

### 2.2 Hexagonal Architecture (Ports & Adapters)
*   **Philosophy:** Application is a hexagon.
    *   **Inside:** The Application Core.
    *   **The Edge:** Ports (Interfaces).
    *   **Outside:** Adapters (Implementations).
*   **Types of Adapters:**
    *   **Driving (Primary):** Kickstart the app (Web Controller, CLI Command, Test Runner).
    *   **Driven (Secondary):** React to the app (SQL Adapter, Email Adapter).
*   **Benefit:** You can swap "Web Controller" for "Test Runner" and run the *exact same* business logic.

## 3. Dependency Injection (DI) Internals

How does the "Magic Container" work?

### 3.1 Reflection-Based (Spring, Guice)
*   **Mechanism:** At startup, scan classpath. Find classes with `@Inject`. Use `Class.forName()` and `Constructor.newInstance()`.
*   **Pros:** Easy to use, very dynamic.
*   **Cons:** Slow startup (scanning), runtime errors (missing dependency found only when app runs).

### 3.2 Code Generation-Based (Dagger, Wire)
*   **Mechanism:** Annotation Processor runs *during compilation*. It writes a new Java/Go class that looks like: `new Service(new Repository())`.
*   **Pros:** Zero reflection overhead, compile-time safety (build fails if dependency missing), fast startup.
*   **Cons:** Boilerplate setup, harder to understand generated code.
