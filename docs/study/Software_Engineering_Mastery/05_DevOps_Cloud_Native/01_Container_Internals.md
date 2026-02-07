# Module 5.1: Container Internals (Linux Plumbing)

**Date:** 2026-02-06
**Status:** Completed

## 1. Namespaces: The Isolation Layer

Containers are not real objects. They are processes with a limited view of the world.

*   **PID Namespace:**
    *   *Inside:* Process sees itself as PID 1.
    *   *Outside:* Process has PID 4500.
    *   *Impact:* Cannot `kill` processes outside the container.
*   **NET Namespace:**
    *   Own `eth0`, IP, Routing Table, `iptables`.
    *   *Port 80* inside does not conflict with *Port 80* outside.
*   **MNT Namespace:**
    *   Own `/` root filesystem.
    *   Changing `/etc/config` inside does not touch host.
*   **USER Namespace:**
    *   *UID Mapping:* User can be `root` (UID 0) inside, but `nobody` (UID 1000) outside.
    *   *Security:* If container escapes, it has zero privileges on host.

## 2. Control Groups (Cgroups): The Limits Layer

Namespaces hide what you *see*. Cgroups limit what you *use*.

### 2.1 Cgroups v1 vs v2
*   **v1:** Hierarchies were separate. `cpu` and `memory` were different trees. Complex to manage.
*   **v2 (Unified Hierarchy):** Single tree. Better support for "Pressure Stall Information" (PSI).
    *   **CPU Shares:** Soft limit (`cpu.weight`). If idle, take 100%. If busy, share 50/50.
    *   **CPU Quota:** Hard limit (`cpu.max`). If used > 100ms in 100ms window, THROTTLE (Sleep).
    *   **Memory Limit:** Hard limit. If used > Limit, **OOM Killer** shoots the process.

## 3. The Filesystem: OverlayFS

How can 1000 containers start in 1 second? They share the disk.

### 3.1 Architecture
*   **LowerDir (Read-Only):** The Base Image (Ubuntu, Node.js).
*   **UpperDir (Read-Write):** The Container Layer. Starts empty.
*   **WorkDir:** Internal kernel scratchpad.
*   **Merged:** The view the process sees.

### 3.2 Copy-on-Write (CoW) Mechanism
*   **Read:** Application reads `/etc/app.conf`. Kernel finds it in `LowerDir`. Zero copy.
*   **Write:** Application opens `/etc/app.conf` for writing.
    1.  Kernel **pauses** write.
    2.  Copies file from `LowerDir` to `UpperDir`.
    3.  App writes to the copy in `UpperDir`.
*   **Delete:** A "Whiteout" file (character device 0:0) is created in `UpperDir` to mask the file in `LowerDir`.
