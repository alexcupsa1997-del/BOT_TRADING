# Module 1.1.a: The CPU & The Kernel Boundary Deep Dive

**Date:** 2026-02-06
**Status:** Completed

## 1. Hardware Privilege: Protection Rings (x86_64)

The CPU enforces security through **Protection Rings** (Domains). Although x86 supports 4 rings (0-3), Linux only uses two: **Ring 0 (Kernel Mode)** and **Ring 3 (User Mode)**.

### 1.1 The Mechanics of Privilege
*   **CPL (Current Privilege Level):** Stored in the bottom 2 bits of the `CS` (Code Segment) register.
    *   `00` = Ring 0 (Kernel).
    *   `11` = Ring 3 (User).
*   **DPL (Descriptor Privilege Level):** Stored in the GDT/IDT entry. It defines "How privileged do you need to be to access this?".
*   **RPL (Requester Privilege Level):** Stored in the Selector (e.g., when you push a segment to DS/SS). It ensures a kernel process acting on behalf of a user cannot accidentally access kernel data (The "Confused Deputy" problem).
*   **The Rule:** Access is granted if `MAX(CPL, RPL) <= DPL`.
    *   *Interpretation:* "Your current rank (CPL) AND the rank of the person asking you (RPL) must both be higher (numerically lower) than the rank of the target data (DPL)."

## 2. Crossing the Boundary: System Calls

How does a User (Ring 3) talk to the Kernel (Ring 0)?

### 2.1 The Legacy Way: `int 0x80`
*   **Mechanism:** Software Interrupt.
*   **Steps:**
    1.  User loads `EAX` with Syscall ID (e.g., `1` for `exit`).
    2.  User executes `int 0x80`.
    3.  CPU looks up vector `0x80` in the **IDT** (Interrupt Descriptor Table).
    4.  CPU checks DPL of the gate (must be Ring 3 accessible).
    5.  CPU saves `CS`, `EIP`, `EFLAGS`, `SS`, `ESP` to the **Kernel Stack**.
    6.  CPU switches to Ring 0 and jumps to the handler.
*   **Performance:** Slow. Requires memory lookups (IDT, GDT) and complex permission checks.

### 2.2 The Modern Way: `syscall` (x86_64) / `sysenter` (Intel 32-bit)
*   **Mechanism:** Specialized Hardware Instruction (Opcode `0F 05`).
*   **Steps:**
    1.  User loads `RAX` with Syscall ID.
    2.  User executes `syscall`.
    3.  **Hardware Magic:**
        *   Saves `RIP` to `RCX`.
        *   Saves `RFLAGS` to `R11`.
        *   Loads `RIP` from **MSR_LSTAR** (Long System Target Address Register) - A dedicated CPU register pre-loaded by Linux at boot time.
        *   Loads `CS` and `SS` from **MSR_STAR**.
        *   Forces CPL to Ring 0.
        *   **NO STACK SWITCH:** It does *not* automatically switch the stack pointer (`RSP`). The kernel entry point *must* immediately switch to a kernel stack (usually found in `GS` segment per-cpu data) before doing *anything* else.
*   **Performance:** Extremely fast. Bypass IDT/GDT lookups entirely.

## 3. Interrupt Handling & The IDT

When hardware needs attention (Keyboard, Network Card, Timer), it fires an interrupt.

### 3.1 The IDT (Interrupt Descriptor Table)
*   An array of 256 **Gate Descriptors** (16 bytes each in 64-bit mode).
*   **Location:** Pointed to by the **IDTR** (IDT Register).
*   **Layout:**
    *   **0-31:** Exceptions (Faults, Traps, Aborts). E.g., `#PF` (Page Fault - Vector 14), `#GP` (General Protection Fault - Vector 13).
    *   **32-255:** User Defined / Hardware Interrupts (IRQs).

### 3.2 The Interrupt Sequence
1.  **Assert:** Hardware line (APIC) signals CPU.
2.  **Vector:** CPU reads vector number (e.g., 32 for Timer).
3.  **Lookup:** CPU reads `IDT[Vector]`.
4.  **Gate:**
    *   **Interrupt Gate:** Clears `IF` (Interrupt Flag) in `RFLAGS` (Disables other interrupts).
    *   **Trap Gate:** Leaves `IF` alone (Allows nesting).
5.  **IST Switch (Critical):**
    *   If the IDT entry has a non-zero **IST (Interrupt Stack Table)** index, the CPU forcibly switches `RSP` to a known good stack defined in the **TSS**.
    *   *Why?* If we double-fault because the kernel stack corrupted, we need a fresh stack to handle the panic.
6.  **Stack Frame:** CPU pushes `SS`, `RSP`, `RFLAGS`, `CS`, `RIP`, `Error Code` (optional).
7.  **Handler:** Jumps to ISR (Interrupt Service Routine).

## 4. The TSS (Task State Segment) in x86_64

In 32-bit, TSS was used for hardware Context Switching. In 64-bit, that's gone. What is it used for now?

1.  **RSP0:** The location of the Ring 0 Stack. When a privilege change happens (Ring 3 -> Ring 0), the CPU *must* know where the kernel stack is. It reads `TSS.RSP0`.
2.  **IST (Interrupt Stack Table):** 7 pointers to "Emergency Stacks" (Double Faults, NMIs, Machine Checks).
3.  **I/O Bitmap:** Permission bits for `in` / `out` instructions.

*Linux has one TSS per CPU.*
