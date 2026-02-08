# MODULE 09: RESOURCE MANAGEMENT PHYSICS

> **Document Status:** Active (Revision 1 - Deep Dive)
> **Engineering Level:** L4 (Kernel Performance Engineer)
> **Word Count Target:** >3000 Words
> **Scope:** The Scheduler. CPU Units vs Cores, Memory Ballooning, and KSM Deduplication.

---

# 1. The CPU Scheduler (CFS)

When you assign "4 Cores" to a VM, you are not giving it 4 physical silicon cores. You are giving it **4 Threads of execution time** on the Host CPU.
The Linux Kernel (Hypervisor) uses the **CFS (Completely Fair Scheduler)** to decide which thread runs on which physical core, slice by nanosecond.

## 1.1 The "Steal Time" Metric (%st)
*   **Definition:** The time a VM *wanted* to run but the Hypervisor said "Wait, someone else is using the CPU".
*   **Threshold:**
    *   `< 1%:` Healthy.
    *   `> 5%:` Performance Degradation.
    *   `> 20%:` The VM is effectively frozen 20% of the time. HFT algos fail.
*   **Goliath Goal:** **0.0% Steal Time** for the Neural Trader.

---

# 2. CPU Units: The Political Currency

If you have 64 Cores, and you assign 64 Cores to VM A and 64 Cores to VM B, what happens when both hit 100% load?
They fight.

## 2.1 CPU Shares (Units)
Proxmox uses a proportional weight system.
*   **Default:** `1024`.
*   **The Math:**
    *   VM A (Units: 1024)
    *   VM B (Units: 1024)
    *   *Result:* Each gets 50% of the CPU time.
*   **The Adjustment:**
    *   VM A (Neural Trader): `4096`
    *   VM B (Database): `2048`
    *   VM C (Log Server): `1024`
    *   *Result:* VM A gets 4x more slices than C.

## 2.2 CPU Limits (The Hard Ceiling)
You can artificially cap a VM.
*   **Limit:** `1` = 1 Core worth of performance.
*   **Use Case:** Preventing a compromised/buggy container (e.g., infinite loop in a scraper) from overheating the server.
*   **Goliath Rule:** Never limit the Neural Trader. Limit the *Microservices*.

---

# 3. Memory Management: The Balloon Trap

Memory is finite. Disk is slow.

## 3.1 VirtIO Ballooning
*   **Mechanism:** The Host tells the VM driver: "I need 2GB back." The Driver inside the VM allocates 2GB of "junk" RAM (inflates the balloon) and tells the Host "I'm holding this 2GB, you can take the physical pages backing it."
*   **The Usage:** Overcommitting RAM. (Running 150GB of VMs on 128GB Server).
*   **The Danger (AI Workloads):**
    1.  VM A (PyTorch) loads a model. RAM usage spikes.
    2.  Host sees pressure. Inflates balloon in VM A.
    3.  VM A Kernel runs out of RAM. **OOM Killer** shoots the PyTorch process.
*   **Verdict:** **Strictly Disabled** for critical nodes. Check "Fixed Size Memory".

## 3.2 KSM (Kernel Samepage Merging)
*   **Mechanism:** A background daemon scans RAM looking for identical pages. If found, it merges them into a single read-only page.
*   **Efficiency:**
    *   *Windows VDI:* 100x Windows 10 VMs = 80% RAM savings (Identical OS DLLs).
    *   *Linux/AI:* < 1% Savings. Every Linux VM has diverse binaries, and AI weights are high-entropy noise.
*   **The Cost:** CPU usage (ksmd) limits peak performance.
*   **Goliath Configuration:** Disable KSM on AI Nodes.
    ```bash
    systemctl stop ksmtuned
    systemctl disable ksmtuned
    echo 2 > /sys/kernel/mm/ksm/run # (2 = unmerge and stop)
    ```

---

# 4. Swap: The Latency Cliff

What happens when RAM is full and Ballooning is disabled?

## 4.1 Host Swap vs Guest Swap
*   **Guest Swap:** The VM swaps to its virtual disk (Zvol).
    *   *Speed:* Fast-ish (NVMe). High IOPS.
*   **Host Swap:** The Proxmox Host swaps the **entire VM memory space** to its drive.
    *   *Speed:* Catastrophic. The VM stops executing for seconds at a time ("Stunned").

## 4.2 Swappiness Tuning
Linux defaults to `vm.swappiness=60`. This means it starts swapping when 40% of RAM is occupied by filesystem cache.
*   **Goliath Tuning:** `/etc/sysctl.conf`
    ```bash
    vm.swappiness=1
    ```
    *   *Logic:* Only swap if OOM is imminent. Preserves latency at all costs.

---

# 5. Advanced Tuning: NUMA Balancing

Linux has an automated system called "Auto NUMA Balancing".
*   **Mechanism:** It periodically unmaps pages to trigger "Page Faults". It uses these faults to detect if a thread is accessing remote memory. If so, it moves the memory to the local node.
*   **The HFT Problem:** Triggering page faults intentionally causes **Latency Spikes**.
*   **The Goliath Fix:** Since we manually pinned the VM (Module 07), we do not need the kernel guessing.
    ```bash
    echo 0 > /proc/sys/kernel/numa_balancing
    ```
    *   *Result:* Deterministic performance.

---

# 6. IRQ Affinity: Interrupt Steering

When a network packet hits the NIC, it fires an Interrupt request (IRQ) to the CPU.
*   **Default:** The IRQ hits Core 0.
*   **Problem:** If receiving 10Gbps of traffic, Core 0 hits 100% usage (SoftIRQ) while Core 1-15 sleep.
*   **Solution: `irqbalance` vs static mapping.**
    *   **Proxmox Host:** Uses `irqbalance` daemon to spread generic load.
    *   **High Performance VM:** We want the NIC queues (VirtIO Multiqueue) to map 1:1 with vCPUs.
    *   *Config:* This is handled by the `ethtool -L` command inside the Guest (Module 07).

---

# 7. Resource Policy Matrix

| Metric | **Neural Trader (Priority 1)** | **Database (Priority 2)** | **Monitor/Log (Priority 3)** |
| :--- | :--- | :--- | :--- |
| **CPU Units** | 4096 | 2048 | 1024 |
| **CPU Limit** | Unlimited | Unlimited | 0.5 (Half Core) |
| **NUMA Pinning** | Strict (Socket 0) | Strict (Socket 1) | Auto |
| **Ballooning** | **Disabled** (Static 64GB) | Enabled (Min 4GB) | Enabled |
| **KSM** | Ignored | Ignored | Shared |
| **Hugepages** | 1GB Pages | 2MB Pages | 4KB (Standard) |

*   **Note:** The Database uses 2MB pages because Postgres hugepage support is easier with 2MB chunks. The AI Engine uses 1GB pages (if possible) for massive matrix efficiency.

*(End of Module 09)*
