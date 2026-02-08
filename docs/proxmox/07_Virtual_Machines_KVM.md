# MODULE 07: VIRTUAL MACHINES (KVM/QEMU DEEP DIVE)

> **Document Status:** Active (Revision 1 - Deep Dive)
> **Engineering Level:** L4 (Virtualization Engineer)
> **Word Count Target:** >3000 Words
> **Scope:** The Engine. KVM internals, QEMU mechanics, and the "Neural Trader" workload optimization.

---

# 1. The Hypervisor Anatomy

Proxmox is not "The Hypervisor". Linux is the Hypervisor (`kvm.ko`). Proxmox is the API.

## 1.1 KVM (Kernel-based Virtual Machine)
*   **The Concept:** KVM turns the Linux Kernel into a Type-1 Hypervisor.
*   **The Mechanism:** It uses Intel VT-x / AMD-V extensions to create "Guest Mode" execution.
*   **The Performance:** Since the CPU instructions run directly on the metal (mostly), CPU overhead is < 2%.

## 1.2 QEMU (Quick Emulator)
KVM provides the CPU. QEMU provides the *Motherboard*.
*   **Role:** Emulates the Chipset (i440fx/q35), the Disk Controller (VirtIO-SCSI), the Network Card (VirtIO-Net), and the RAM.
*   **The Bottleneck:** Every time the VM touches hardware (Disk/Net), the CPU must exit "Guest Mode", trap to QEMU (User Space), execute the I/O, and return. This "Context Switch" is expensive.
*   **The Goliath Fix:** **VirtIO**.

---

# 2. CPU Types: The Illusion of "Host"

When you create a VM, you select a "CPU Type". This is the most critical setting for AI and HFT.

## 2.1 `kvm64` (Default - The Trash)
*   **What it is:** A generic Pentium 4 era CPU profile.
*   **Why it exists:** Maximum compatibility for Live Migration between Intel and AMD hosts.
*   **The Cost:** It hides advanced instruction sets (AVX, AVX2, AVX-512, AES-NI) from the Guest.
*   **Result:** Python (NumPy/TensorFlow) falls back to slow math paths. **Unacceptable for Neural Trader.**

## 2.2 `host` (Passthrough)
*   **What it is:** Passes the exact CPU model and flags to the guest.
*   **Benefit:** The VM sees AVX-512. Python runs at native speed.
*   **Restriction:** You can only Live Migrate to a node with the *exact* same CPU.
*   **Verdict:** **Mandatory for Goliath AI Nodes.**

## 2.3 `x86-64-v2/v3` (The Middle Ground)
*   **Use Case:** If you have a mixed cluster (e.g., EPYC Milan and EPYC Genoa).
*   **Mechanism:** Exposes a high baseline of instructions (AVX2) but hides model-specifics.

---

# 3. Machine Type: i440fx vs q35

## 3.1 i440fx (The Legacy)
*   **Era:** 1996. PCI (Legacy) bus.
*   **Pros:** Rock solid. Works with Windows XP.
*   **Cons:** No PCIe support. No IOMMU grouping.
*   **Verdict:** Use for old Linux/Windows VMs only.

## 3.2 q35 (The Modern Standard)
*   **Era:** 2007+. PCIe native.
*   **Pros:** Supports PCIe Passthrough (GPU), Hot-plug PCIe.
*   **Verdict:** **Mandatory for PCIe Passthrough (GPU) Tasks.**

---

# 4. VirtIO: Paravirtualization Physics

To solve the "QEMU Context Switch" problem, we use drivers that *know* they are virtualized.

## 4.1 VirtIO-SCSI (Disk)
*   **Standard SATA/IDE:** The VM talks to an emulated AHCI controller. High overhead.
*   **VirtIO-SCSI:** The VM places block requests directly into a shared memory ring buffer. The Host picks them up.
*   **Single vs Multi-Queue:**
    *   *Single:* One ring buffer. Bottleneck on 1 vCPU.
    *   *Multi-Queue:* One ring buffer per vCPU.
    *   *Setting:* Check `Multi-Queue` in Disk Advanced Options. Set to number of vCPUs.

## 4.2 VirtIO-Net (Network)
*   **E1000:** Emulates an Intel 1Gb NIC. Slow.
*   **VirtIO:** 10GbE/25GbE/40GbE speed equivalent.
*   **Queues:** Like SCSI, set `Multiqueue = 8` (if you have 8 vCPUs) to spread interrupt load.

## 4.3 VirtIO-Balloon (RAM)
*   **Concept:** The Host can "inflate" a balloon inside the VM to reclaim RAM.
*   **Risk:** If the Guest OS is under memory pressure (e.g., loading a large Pandas DataFrame) and the Balloon inflates, the OOM Killer strikes.
*   **Goliath Rule:** **Disable Ballooning** on all HFT/AI nodes. RAM allocation must be static and guaranteed.

---

# 5. BIOS vs UEFI

## 5.1 SeaBIOS (Legacy)
*   **Boot:** MBR.
*   **Limit:** 2TB boot drives. Slow boot.
*   **Use Case:** Legacy compatibility.

## 5.2 OVMF (UEFI)
*   **Boot:** GPT.
*   **Feature:** Secure Boot. PCIe Passthrough (often requires UEFI).
*   **The "EFI Disk":** Proxmox creates a small separate disk for EFI variables.
*   **Verdict:** **Default for all new Goliath VMs.**

---

# 6. The "Neural Trader" Spec (VM 100)

Based on the Consensus Engine requirements (100+ Indicators, Real-time Aggregation):

**Profile: `goliath-aggregator`**
*   **CPU Type:** `host` (Access to AVX-512 for NumPy).
*   **Cores:** 16 (NUMA Pinned - See Module 09).
*   **RAM:** 64GB (Static - No Balloon).
*   **Machine:** `q35`.
*   **BIOS:** `OVMF`.
*   **Disk:**
    *   `scsi0`: VirtIO-SCSI Single, `iothread=1`, `discard=on`, `aio=io_uring`.
    *   *Why IO Thread?* Offloads disk I/O from the vCPU execution thread to a dedicated thread. Essential for HFT to prevent "micro-stutters" in Python loops during DB writes.
*   **Network:**
    *   `net0`: VirtIO, `multiqueue=8`.

---

# 7. NUMA Topology: The Silent Killer

For the "Consensus Engine" (aggregating 100+ signals), memory latency is everything.
*   **The Physics:** Dual Socket servers (or AMD EPYC Chiplets) have Non-Uniform Memory Access.
*   **The Trap:** If a VM's vCPU is on Socket 0, but its RAM is on Socket 1, every memory access must cross the UPI/Infinity Fabric link.
*   **Latency Penalty:** ~20ns -> ~120ns (600% increase).
*   **Result:** Python loops run slower. The "Neural Trader" misses the tick.

## 7.1 Configuration (Strict Enforcement)
We must pin the VM to a specific NUMA node.

**Command Line (QM):**
```bash
qm set 100 --numa 1
# This tells QEMU to expose NUMA topology to the guest.
```

**CPU Pinning (Hookscripts):**
Proxmox does not have a GUI for CPU Pinning (yet). We use `taskset` via hookscripts or systemd slices.
*   *Manual Test:* `taskset -c 0-15 qm start 100` (Runs VM 100 only on cores 0-15).

---

# 8. Hugepages: Reducing TLB Misses

*   **Standard Page:** 4KB.
*   **The Problem:** For 64GB RAM, the CPU needs millions of entries in the Translation Lookaside Buffer (TLB) to map Virtual Address -> Physical Address.
*   **The Miss:** When the TLB fills up, the CPU must walk the page table in RAM. Slow.
*   **Hugepage:** 2MB or 1GB.
*   **Result:** 500x fewer entries. 99% TLB Hit Rate.

**Implementation:**
1.  **Host Kernel:** `hugepages=32000` (Allocates 64GB of 2MB pages).
2.  **VM Config:**
    ```bash
    qm set 100 --hugepages 2
    ```
    *   `2`: Use 2MB pages. (1GB pages are harder to allocate without fragmentation).

---

# 9. The "Neural Trader" VM Deployment (Step-by-Step)

This is the exact spec for the primary AI node.

1.  **Create VM:**
    *   OS: Linux (Debian 12 Bookworm).
    *   System: q35, OVMF, SCSI Controller (VirtIO SCSI Single).
    *   Disk: 100GB, SSD Emulation, Discard, IO Thread.
    *   CPU: 16 Cores, Type `host`, NUMA enabled.
    *   Memory: 64GB, Balloon=0.
    *   Network: VirtIO, Multiqueue=8.

2.  **Post-Install Optimization (Inside Guest):**
    *   *Kernel:* Install `linux-image-cloud-amd64` (Optimization for virtualized environments).
    *   *Systemd:* Mask unnecessary services (`systemctl mask sleep.target suspend.target hibernation.target`).
    *   *Network:* Enable Multi-queue in guest (`ethtool -L enp18s0 combined 8`).

3.  **Python Optimization:**
    *   Compile NumPy/PyTorch against **Intel MKL** or **OpenBLAS** to utilize the AVX-512 instructions passed through by the `host` CPU type.

*(End of Module 07)*
