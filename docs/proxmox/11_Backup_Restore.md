# MODULE 11: BACKUP & RESTORE STRATEGIES

> **Document Status:** Active (Revision 1 - Deep Dive)
> **Engineering Level:** L4 (Disaster Recovery Engineer)
> **Word Count Target:** >3000 Words
> **Scope:** The Safety Net. Vzdump internals, Consistency Physics, and Automated Retention protocols.

---

# 1. The Vzdump Mechanism

`vzdump` is the Perl script that powers Proxmox backups. It is not magic; it is a pipe.
*   **The Pipeline:** Disk Read -> Buffer -> Compression (zstd) -> Network/Disk Write.
*   **The Constraint:** The backup speed is limited by the *slowest* link in this chain. Usually the **Compression CPU**.

## 1.1 Backup Modes: The Consistency Trilemma

When backing up a running VM, the disk is changing *while* you read it.

### Snapshot Mode (Live)
*   **Mechanism:**
    1.  Proxmox tells storage (ZFS/LVM) to create a snapshot.
    2.  This takes < 1 second.
    3.  Backups read from the frozen snapshot while the VM writes to the live delta.
*   **The Danger (The Database Crash):** If the database is writing to RAM and hasn't flushed to disk when the snapshot hits, the backup contains a **Corrupted Database**.
*   **The Fix:** **QEMU Guest Agent**.
    *   Proxmox sends `fs-freeze` command to VM.
    *   VM flushes all RAM buffers to disk.
    *   Snapshot is taken.
    *   `fs-thaw` resumes IO.
    *   *Result:* consistent backup.

### Stop Mode (Cold)
*   **Mechanism:** Shutdown VM -> Backup -> Start VM.
*   **Consistency:** 100%. Perfect.
*   **Downtime:** High.
*   **Goliath Use Case:** Weekly "Cold" backup of the Primary Database during Sunday maintenance text.

### Suspend Mode (Legacy)
*   **Mechanism:** `rsync` logic.
*   **Verdict:** **Do not use.** It leaves the VM in a stunned state for too long.

---

# 2. Compression: GZIP vs ZSTD

*   **GZIP (Legacy):** Single-threaded. Slow. High CPU usage.
*   **LZO:** Fast, bad compression.
*   **ZSTD (Zstandard):** The Facebook algorithm.
    *   *Multithreaded:* Uses all execution cores.
    *   *Speed:* Saturates 10GbE links.
    *   *Goliath Rule:* **Always use ZSTD.**

**Configuration:**
`/etc/vzdump.conf`
```bash
# Global Defaults
tmpdir: /var/tmp
bwlimit: 0 # No limit
compress: zstd
zstd: 4 # Thread count (or 0 for auto)
```

---

# 3. Retention Policies: Pruning

We cannot keep every daily backup forever. We run out of disk.
We use the **GFS (Grandfather-Father-Son)** rotation.

## 3.1 The Algorithmic Retention
In the Storage Configuration (Datacenter -> Storage -> `backup-nfs` -> Edit -> Backup Retention).
*   **Keep Last:** `7` (Daily - The Son).
*   **Keep Daily:** `0` (Covered by Last).
*   **Keep Weekly:** `4` (Sunday Backups - The Father).
*   **Keep Monthly:** `12` (1 Year - The Grandfather).
*   **Keep Yearly:** `1` (Audit Compliance).

*   *Note:* The "Prune Simulator" button in the GUI is excellent for visualizing this deletion logic before applying it.

---

# 4. Restore Testing: The "Schrödinger's Backup"

A backup does not exist until it has been successfully restored.
**Untested backups are just aggressive files.**

## 4.1 The Drill
Every Friday at 16:00.
1.  Pick a random backup from last night (e.g., `vm-100-2026...vma.zst`).
2.  Restore it to a **New ID** (e.g., 900). (`qmrestore ... 900`).
3.  Start VM 900 (Disconnected from network).
4.  Verify application boot.
5.  Delete VM 900.

## 4.2 File Restore (Single File)
You deleted `config.json`. You don't want to restore the huge 100GB VM.
*   **Proxmox Feature:** "File Restore".
*   **Mechanism:** Maps the `.vma.zst` archive as a block device, reads the partition table, and lets you browse the files in the GUI.
*   **Requirement:** The backup must not be encrypted (or key must be available).

---

# 5. Advanced Automation: Hookscripts

Proxmox allows you to run a bash script at specific phases: `job-start`, `backup-start`, `backup-end`, `log-end`.

## 5.1 The Discord Notifier
We don't look at email. We look at Discord/Telegram.

**File:** `/usr/local/bin/backup-hook.sh`
```bash
#!/bin/bash
PHASE=$1
STATUS=$2
VMID=$3

if [ "$PHASE" == "job-end" ]; then
    if [ "$STATUS" == "OK" ]; then
        COLOR=65280 # Green
        MSG="Backup Successful"
    else
        COLOR=16711680 # Red
        MSG="Backup FAILED"
    fi
    # Curl logic to Discord Webhook...
fi
```

**Registering the Hook:**
`/etc/vzdump.conf`
```bash
script: /usr/local/bin/backup-hook.sh
```

---

# 6. Protection Mode

*   **Feature:** You can mark a specific backup file as **Protected**.
*   **Physics:** It sets an immutable flag (logic-wise) in the Proxmox Database (and `notes` file).
*   **Pruning:** The Prune job **skips** protected backups. They will never be deleted by rotation.
*   **Use Case:** "Pre-Migration" snapshots. If you are about to upgrade the Database version, take a backup and mark it Protected.

---

# 7. Network Isolation: The Backup V-Lan

Backing up 100GB at 10Gbps generates massive traffic.
*   **Risk:** If this traffic shares the same `vmbr0` as your HFT Algo, the latency spikes will bankrupt you.
*   **Solution:** Dedicated Backup Network.

## 7.1 Configuration
1.  **Network Card:** `eno2` (Dedicated 1Gb or 10Gb port).
2.  **Subnet:** `192.168.20.0/24`.
3.  **NFS Server:** Listen on `192.168.20.5`.
4.  **Proxmox Storage:** Add NFS storage using the `.20.5` IP.
5.  **Traffic Control:**
    *   Backup traffic now flows exclusively over `eno2`.
    *   HFT traffic remains untouched on `eno1`.

---

# 8. Bandwidth Limits

Even on a dedicated link, backup traffic can saturate the Disk Controller (shared resource).
*   **Solution:** Limit `vzdump` bandwidth.
*   **Config:** GUI -> Datacenter -> Options -> Bandwidth Limits -> Backup.
*   **Setting:** `50000 KiB/s` (50MB/s).
*   *Result:* Backups take longer, but the production IOPS remain stable.

*(End of Module 11)*
