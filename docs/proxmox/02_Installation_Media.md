# MODULE 02: BOOTLOADER MECHANICS & ZFS GEOMETRY

> **Document Status:** Active (Revision 2 - Deep Dive)
> **Engineering Level:** L4 (Systems Architect)
> **Word Count Target:** >3000 Words
> **Scope:** The sub-OS layer. Bootloaders, UEFI Memory Maps, and ZFS On-Disk Structure.

---

# 1. The Boot Sequence: A Fork in the Road

Most tutorials gloss over the bootloader. In Proxmox, this is the #1 cause of "I stuck a GPU in and now it won't boot."

## 1.1 The Proxmox Boot Tool (`proxmox-boot-tool`)
Unlike standard Debian which strictly uses GRUB, Proxmox VE has a dual-personality disorder depending on your filesystem choice.

### The ZFS Bifurcation
*   **Legacy / EXT4:** Uses **GRUB**.
    *   *Config:* `/etc/default/grub`.
    *   *Update:* `update-grub`.
*   **UEFI / ZFS Root:** Uses **systemd-boot** (formerly Gummiboot).
    *   *Config:* It **IGNORES** `/etc/default/grub`.
    *   *The Trap:* 99% of "I added `intel_iommu=on` and it didn't work" posts are because the user edited the GRUB file on a ZFS system.
    *   *Real Config:* `/etc/kernel/cmdline`.
    *   *Mechanism:* The `proxmox-boot-tool` script syncs the kernel command line to the EFI System Partition (ESP) on all mirrored drives.

**Command Mastery:**
```bash
# Check which bootloader is active
proxmox-boot-tool status
# Logic: If it returns "u-boot" or "systemd-boot", you are in ZFS land.

# Correct way to change kernel parameters (IOMMU) on ZFS:
nano /etc/kernel/cmdline
# Add: quiet intel_iommu=on
proxmox-boot-tool refresh
```

## 1.2 The UEFI Memory Map (`e820`)
When you pass through a PCI device, the host kernel must reserve the exact memory addresses required by that device's BARs (Base Address Registers).

### The "Out of Resources" Error
If you see `DMAR: [Firmware Bug]: Your BIOS is broken`, it means the BIOS did not report the RMRR (Reserved Memory Region Reporting) correctly to the kernel.

**The Fix (The "Nuclear Option"):**
You must manually override the kernel's memory map using `initcall_blacklist=sysfb_init`.
*   *Why:* The System Framebuffer (`sysfb`) claims the GPU memory range during boot to show the splash screen. When the VFIO driver tries to grab it later, it's "busy".
*   *Solution:* We kill the splash screen to free the range.
    ```bash
    video=efifb:off video=vesafb:off
    ```

---

# 2. Bios Configuration: The IOMMU Architecture

Virtualization is not software; it is hardware features exposed by the CPU.

## 2.1 The VT-d / AMD-Vi Translation Table
The **IOMMU** is a physical component on the die that translates "Guest Physical Addresses" (what the VM sees) to "Host Physical Addresses" (Real RAM).

### IOMMU Groups & ACS
The **Access Control Services (ACS)** capability determines if a PCIe Transaction Layer Packet (TLP) can be routed directly between devices (P2P) or must go up to the Root Complex.
*   *Without ACS:* The Root Complex cannot trust who sent the packet. Result: It forces all devices into one "Group".
*   *With ACS:* The Root Complex can verify the Source ID. Result: Granular groups.

**The "Downstream" Patch Risk:**
Many tutorials suggest `pcie_acs_override=downstream`.
*   *What it does:* It tells the kernel to **LIE** about the isolation. It forces separate groups even if the hardware cannot guarantee isolation.
*   *The Risk:* VM A writes to GPU A. The packet "leaks" into the memory space of VM B's NIC.
*   *GOLIATH Policy:* **Strictly Forbidden.** If your hardware doesn't support proper grouping, replace the motherboard. Do not patch the kernel to ignore physics.

## 2.2 Re-Size BAR (Base Address Register)
Modern GPUs have large VRAM (24GB+).
*   *32-bit BAR:* Can only map 256MB chunks. The CPU must "page" through the VRAM window. Slow.
*   *64-bit BAR:* Can map the entire 24GB at once.
*   *Proxmox:* If "Above 4G Deployment" is disabled in BIOS, KVM cannot map the BAR. The VM will fail with `Code 43` (NVIDIA Driver Error).

---

# 3. ZFS Install Geometry: The Database Killer

The default Proxmox installer settings are **wrong** for high-performance databases (Postgres/TickDB).

## 3.1 `ashift`: The Sector Alignment
SSDs lie. They tell the OS they have 512-byte sectors (Logical) but actually write to 4096-byte or 8192-byte pages (Physical).
*   *The Mismatch:* If you write a 512-byte chunk, the SSD must read the 4k page, modify 512 bytes, and rewrite the 4k page (Read-Modify-Write). This is **Write Amplification**.
*   *The Fix:* Force `ashift=12` (2^12 = 4096 bytes) during install.
*   *Note:* Some Samsung Enterprise drives prefer `ashift=13` (8k). Check the datasheet.

## 3.2 `recordsize`: The Tuning Variable
ZFS writes data in variable-sized chunks called Records.
*   *Default:* 128k. (Great for sequential movies).
*   *Database (Postgres):* Writes in 8k or 16k pages.
*   *The Conflict:* Postgres writes 16k. ZFS reads 128k, modifies 16k, writes 128k. **Write Amplification = 8x.**
*   *GOLIATH Strategy:*
    1.  Root/OS: 128k (Default).
    2.  Dataset `rpool/data/postgres`: **Set `recordsize=16k`**.
    3.  Dataset `rpool/data/parquet`: **Set `recordsize=1M`** (Maximize sequential throughput for Python Arrow).

## 3.3 Redundancy: Mirror vs RAIDZ
*   **RAIDZ (Parity):** Like RAID5.
    *   *Calculation:* Needs to calculate parity checksum on writes.
    *   *IOPS:* Limited to the speed of the *slowest single drive* for random IOPS.
*   **Mirror (RAID1/10):**
    *   *Calculation:* None. Just copy.
    *   *IOPS:* **Linear scaling** of read IOPS. 2 drives = 2x reads. 4 drives = 4x reads.
*   *Verdict:* For VM Block Storage (`zvol`), RAIDZ is terrible due to "Padding Overhead". **Always use Mirrors (RAID10) for VM backing stores.**

---

# 4. The Calculus of Caching: ARC, L2ARC, and ZIL

ZFS is a memory-first filesystem. Understanding its caching tiers is critical for "Goliath" performance.

## 4.1 ARC (Adaptive Replacement Cache)
Unlike the Linux Page Cache (which is LRU - Least Recently Used), ARC is **MFU + LRU** (Most Frequently Used + Least Recently Used). It remembers "Ghosts" (evicted pages) to predict what you might need again.
*   *The Math:* ZFS will eat 50% of your RAM by default.
*   *The Limit:* For AI nodes, we need RAM for the Model. We must cap ARC.
    ```bash
    # Limit ARC to 32GB
    echo "options zfs zfs_arc_max=34359738368" > /etc/modprobe.d/zfs.conf
    ```
*   *Strategy:* `primarycache=all` (Default) caches data and metadata.
    *   *For Backups:* Set `primarycache=metadata`. We don't need to cache the backup file itself, just the pointers to it. This prevents backups from flushing hot DB pages out of RAM.

## 4.2 ZIL (ZFS Intent Log) vs SLOG
*   *Synchronous Writes:* When Postgres says "COMMIT", ZFS *must* write to non-volatile storage before confirming.
*   *The ZIL:* By default, ZFS writes this "Intent Log" to a reserved area on the spinning disk pool. **Latency: 10ms.**
*   *The SLOG (Separate Log):* We move this log to an Optane or Enterprise NVMe. **Latency: 20us.**
*   *Verdict:* For a Trading Bot DB, a **Mirrored Optane SLOG** is the single biggest performance upgrade you can buy.

## 4.3 L2ARC (Level 2 ARC)
Reading from RAM is 50 GB/s. Reading from NVMe is 5 GB/s. Reading from HDD is 0.1 GB/s.
*   *L2ARC:* Uses a fast SSD to cache data evicted from RAM.
*   *The Trap:* L2ARC *consumes* RAM to index the SSD. (approx 1GB RAM per 50GB L2ARC).
*   *GOLIATH Rule:* **Do not use L2ARC** unless you have maxed out your motherboard's RAM slots. RAM is always better than SSD.

---

# 5. Network Bonding Physics (LACP vs Active-Backup)

We have two 10GbE ports. How do we use them?

## 5.1 The Hash Policy (LACP - 802.3ad)
*   *Myth:* "2x 10GbE = 20GbE Speed".
*   *Reality:* **No.** A single TCP stream (e.g., an SCP file transfer or a single WebSocket connection) is defined by `(SrcIP, DstIP, SrcPort, DstPort)`. The LACP hashing algorithm assigns this tuple to **Port A OR Port B**, never both.
*   *Result:* Single stream maxes at 10Gbps. Aggregate bandwidth (100 clients) maxes at 20Gbps.
*   *Requirement:* Your physical switch **MUST** support LACP (802.3ad).

## 5.2 Active-Backup (Failover)
*   *Logic:* Traffic uses Port A. If Port A link signal dies, switch to Port B.
*   *Pros:* Requires no switch configuration. Works on dumb switches.
*   *Cons:* You waste 50% of your bandwidth.

**Goliath Verdict:**
*   **Management Network:** Active-Backup (Robustness).
*   **Storage Network (Ceph/NAS):** LACP (Layer 3+4 Hashing).
*   **AI Data Ingest:** LACP. We want to ingest 10 streams of market data in parallel.

---

# 6. Post-Install Verification Checklist

Before installing the first VM, you must verify the foundation.

1.  **Verify Bootloader:**
    ```bash
    proxmox-boot-tool status
    # Expect: configured systems: uefi (x2)
    ```

2.  **Verify ZFS Alignment:**
    ```bash
    zdb -C | grep ashift
    # Expect: ashift: 12
    ```

3.  **Verify Network Offloads:**
    ```bash
    ethtool -k eno1 | grep tso
    # Expect: tcp-segmentation-offload: on
    ```
    *Note:* If TSO is OFF, your CPU is being hammered by packet fragmentation.

4.  **Verify IOMMU Groups:**
    ```bash
    pvesh get /nodes/localhost/hardware/pci --pci-class-blacklist ""
    # Look for: GPU in its OWN group number (e.g., Group 45).
    ```

*(End of Module 02)*
