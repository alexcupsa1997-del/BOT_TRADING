# MODULE 05: STORAGE ARCHITECTURE & ZFS PHYSICS

> **Document Status:** Active (Revision 1 - Deep Dive)
> **Engineering Level:** L4 (Storage Architect)
> **Word Count Target:** >3000 Words
> **Scope:** The math of IOPS, ARC eviction policies, and the "Copy-on-Write" time machine.

---

# 1. The Geometry of the Pool (VDEVs)

In ZFS, you do not add "Drives". You add **Virtual Devices (VDEVs)**. The pool is a stripe (RAID0) across these VDEVs.

## 1.1 The IOPS Equation (Mirror vs RAIDZ)
The single biggest mistake in Proxmox storage is using RAIDZ (Parity) for VM backing stores.

*   **The Physics of Random I/O:**
    A Virtual Machine is a random I/O generator. It reads 4k blocks from all over the disk.
    *   **Mirror VDEV (2 Drives):** Both drives can read independent data simultaneously.
        *   *Read IOPS:* $2 \times \text{Single Drive IOPS}$.
        *   *Write IOPS:* $1 \times \text{Single Drive IOPS}$ (Must write to both).
    *   **RAIDZ1 VDEV (3 Drives):** To read a 4k block, the controller must read the data and verify parity. The *entire VDEV* acts as a single mechanical unit.
        *   *Read IOPS:* $1 \times \text{Single Drive IOPS}$.
        *   *Write IOPS:* $< 1 \times \text{Single Drive IOPS}$ (Parity Calc Overhead).

### The GOLIATH Implications
*   **Scenario:** You have 6x NVMe drives (10k IOPS each).
*   **Config A (RAIDZ2 - 6 Drives):**
    *   *Capacity:* 4 Drives (66%).
    *   *Total Pool IOPS:* **10k IOPS.** (The speed of ONE drive).
*   **Config B (Striped Mirrors - RAID10 equivalent):**
    *   3x VDEVs, each containing 2 Mirrored Drives.
    *   *Capacity:* 3 Drives (50%).
    *   *Total Pool IOPS:* **30k Write / 60k Read.**
    *   *Verdict:* **600% Performance difference.**

**Rule:** Always use **Mirrors** for `rpool` (VMs/Databases). Use **RAIDZ2** only for `backup-pool` (Cold Storage) where throughput (MB/s) matters more than IOPS.

## 1.2 The Padding Overhead (RAIDZ vs Databases)
ZFS allocates data in "ashift" sectors (4k).
*   *RAIDZ Problem:* Parity must be stored. If you write a 4k block to a RAIDZ1 pool, it might actually consume 8k or 12k of space due to parity padding and alignment requirements.
*   *Database Result:* Your Postgres 1TB database might consume 2TB of physical flash on RAIDZ, doubling wear and halving performance.

---

# 2. ARC: The Memory Vampire

Adaptive Replacement Cache (ARC) is the smartest caching algorithm in existence. It is also an AI killer.

## 2.1 MFU vs LRU
*   **LRU (Least Recently Used):** "I haven't used this in a while, delete it." (Standard Linux Cache).
*   **MFU (Most Frequently Used):** "I use this often, keep it even if I haven't touched it in an hour."
*   **Ghost Lists:** ARC tracks *evicted* metadata. If a "Ghost" is requested again, ARC realizes "I should have kept that" and increases the MFU size.

## 2.2 The Conflict: LLM vs ARC
*   *Scenario:* You run Llama-3-70B. It needs 40GB VRAM (offloaded) + 30GB System RAM.
*   *ZFS Behavior:* ZFS sees free RAM and eats it. ARC grows to 50% of Host RAM (e.g., 64GB on a 128GB node).
*   *The Crash:* The LLM requests 30GB. Linux sees 0GB free. **OOM Killer triggers.** It kills the Python process because ZFS Kernel memory is "un-killable" fast enough.

## 2.3 Tuning Strategy (`zfs.conf`)
We must clamp ARC.
*   **Formula:** `Host RAM - (VM RAM + 4GB OS base)`.
*   *Goliath Node (128GB):*
    *   VMs/AI need: 90GB.
    *   OS needs: 4GB.
    *   Leftover for ARC: 34GB.

**File: `/etc/modprobe.d/zfs.conf`**
```bash
# Min: 4GB (4294967296)
# Max: 34GB (36507222016)
options zfs zfs_arc_min=4294967296
options zfs zfs_arc_max=36507222016
```
*Run `update-initramfs -u` and reboot.*

---

# 3. Datasets: Granular Tuning

Never verify just "on the pool". Verification happens at the **Dataset** level.

## 3.1 The Hierarchy
*   `rpool` (Root)
    *   `rpool/ROOT` (Proxmox OS)
    *   `rpool/data` (Parent for VMs)
        *   `rpool/data/subvol-100-disk-0` (Container Root)
        *   `rpool/data/vm-101-disk-0` (VM Disk)

## 3.2 Property Inheritance
ZFS properties flow down. We set defaults on `rpool/data` so all future VMs inherit them.

### Compression (`lz4` vs `zstd`)
*   **LZ4:** Extremely fast. Zero CPU overhead on modern CPUs. **Default.**
*   **ZSTD:** Higher compression, higher CPU usage.
    *   *SBE Data / Market Logs:* Use `zstd-3`. Text/JSON compresses 10:1.
    *   *Postgres/VM Disks:* Use `lz4`. We need latency < 0.1ms. Zstd adds latency.

### Access Time (`atime`)
*   *Default:* `on`. Every time you *read* a file, ZFS writes a new "Last Accessed" timestamp.
*   *Result:* Reading a database generates Write IOPS.
*   *Verdict:* **Turn it OFF.** `zfs set atime=off rpool/data`.

### Sync Write (`sync`)
*   **Standard:** `standard`. ZFS decides.
*   **Always:** `always`. Every write goes to ZIL. (Safe but slow).
*   **Disabled:** `disabled`. Writes are acked in RAM.
    *   *Risk:* Power loss = 5 seconds of data loss.
    *   *Benefit:* **10x Performance on Consumer SSDs.**
    *   *Goliath Policy:* **Strictly Forbidden** on Database datasets. Acceptable on "Temp/Cache" datasets for compilation.

---

# 4. Replication: The Time Machine (ZFS Send/Recv)

Traditional backups (rsync/tar) are file-based. They are slow because they must scan millions of files to find changes.
**ZFS Send/Recv** is block-based. It streams the *changed binary blocks*.

## 4.1 The Snapshot Mechanism
A ZFS Snapshot is an immutable point-in-time reference. It takes **0 seconds** and consumes **0 bytes** (initially). space is only consumed as the live filesystem diverges from the snapshot (Copy-on-Write).

## 4.2 `pve-zsync`: Continuous Data Protection
Proxmox includes a wrapper tool `pve-zsync` to automate this.

**Scenario:** Replicate "Database VM" (ID 100) from Node A to Node B every 15 minutes.
```bash
pve-zsync create --source 100 --dest 192.168.1.11:rpool/replication --maxsnap 96 --name VM100-DR --method ssh
```
*   *Initial Sync:* Sends full 100GB.
*   *Subsequent Syncs:* Sends only the 50MB of changed blocks. Takes 2 seconds.
*   *RPO (Recovery Point Objective):* 15 minutes.
*   *DTO (Disaster Recovery):* If Node A burns down, you just turn on the replicated disk on Node B. No "Restore" process needed.

---

# 5. Encryption: Native vs LUKS

We deal with financial data. Encryption involves a penalty.

## 5.1 ZFS Native Encryption
*   *Layer:* Happens at the Dataset/Zvol layer.
*   *Key Location:* Loaded into RAM when the dataset is mounted.
*   *Benefit:* Replication (`zfs send -w`) sends the **Encrypted Raw Stream**.
    *   *Implication:* The backup server (Node B) *does not need the key*. It stores the encrypted blob. If Node B is stolen, the data is safe.
    *   *LZ4 Compression:* Worked **before** encryption. (Data is compressed, then encrypted).

## 5.2 LUKS (Linux Unified Key Setup)
*   *Layer:* Block Device layer (below ZFS).
*   *Problem:* ZFS sees random noise. Compression (LZ4) drops to 1.00x ratio because you cannot compress encrypted noise.
*   *Verdict:* **Use ZFS Native Encryption.**

**Command:**
```bash
zfs create -o encryption=on -o keyformat=passphrase rpool/data/secure-wallet
```

---

# 6. Data Integrity: The Scrub

Silence is the enemy. Bit rot (flipped bits on disk) happens naturally due to cosmic rays and magnetic degradation.

## 6.1 The Scrubbing Process
`zpool scrub` reads **every single block** of data on the drive and compares its checksum against the metadata.
*   *Match:* Good.
*   *Mismatch (Mirror):* ZFS notices the bad hash. It reads the copy from Drive B. If Drive B is good, it **automatically repairs** Drive A.
*   *Mismatch (No Redundancy):* ZFS tells you the exact file path that is corrupt.

## 6.2 Schedule Requirement
Consumer drives are less reliable. We must scrub often.
*   *Enterprise:* Monthly.
*   *Consumer (GOLIATH):* **Weekly.**

**Systemd Timer (`/usr/lib/zfs-linux/zfs-scrub-monthly`):**
Override to weekly in `/etc/cron.d/zfsutils-linux`.

---

# 7. Monitoring: Arcstat and Zpool Status

Do not fly blind.

## 7.1 `arcstat`
Shows cache hit rates.
```bash
arcstat 1
# Look for "hits" > 90%.
# If "miss" is high, and "size" = "c" (max), you need more RAM or L2ARC.
```

## 7.2 `zpool status -v`
Shows the health of VDEVs.
*   *Read/Write/Cksum:* Should be 0.
*   *Action:* If you see a number > 0 in Cksum column, that cable or drive is dying. Replace immediately.

*(End of Module 05)*
