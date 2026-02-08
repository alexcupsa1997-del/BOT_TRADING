# MODULE 06: STORAGE ALTERNATIVES: LVM-THIN & DIRECTORY

> **Document Status:** Active (Revision 1 - Deep Dive)
> **Engineering Level:** L4 (Storage Architect)
> **Word Count Target:** >3000 Words
> **Scope:** Block-level virtualization without ZFS. LVM-Thin mathematics, Directory overhead, and NAS integration.

---

# 1. The Case Against ZFS

ZFS is the gold standard, but it is not a religion. There are specific architectural scenarios where ZFS is the **wrong choice**.

## 1.1 The "Low RAM" Constraint (Edge Nodes)
*   **Scenario:** A 32GB RAM NUC acting as a Quorum Witness or Edge Inference Node.
*   **The Math:** ZFS ARC wants 16GB. The OS wants 4GB. You have 12GB left for VMs.
*   **The Alternative:** **LVM-Thin**.
    *   *RAM Usage:* ~0GB (Kernel Metadata only).
    *   *Result:* You reclaim 16GB of RAM for actual compute.

## 1.2 The "Single Drive" NVMe
*   **Scenario:** A single 2TB Consumer NVMe.
*   **The Math:** ZFS relies on redundancy to self-heal. On a single drive, `copies=2` reduces capacity by 50% and write performance by 50%.
*   **The Alternative:** **LVM-Ext4**. Native speed. No checksum overhead. (Risk: Bit rot is undetected).

---

# 2. LVM-Thin: The Block Layer

Standard LVM allocates blocks immediately. LVM-Thin allocates blocks **on write**.

## 2.1 The Architecture
*   **VG (Volume Group):** The physical disk(s).
*   **Thin Pool:** A reserved area for data + metadata.
*   **Thin Volume (LV):** The virtual disk presented to the VM.

### The Metadata Trap (The 100% Full Crash)
In LVM-Thin, there are two usage bars: **Data Usage** and **Metadata Usage**.
*   *The Limit:* Metadata space is finite (default 128MB or calculated).
*   *The Catastrophe:* If the Metadata Pool hits 100%, **the entire Pool locks up read-only**. You cannot delete files to free space because deleting a file requires *writing* a metadata update.
*   *Recovery:* Extremely difficult. Often requires `lvconvert --repair` which can result in data loss.
*   *GOLIATH Rule:* Always oversized the metadata pool.

**Configuration:**
```bash
# Check Metadata Size
lvs -a -o name,size,chunk_size,monitor,data_percent,metadata_percent
```

## 2.2 Snapshots & Copy-on-Write (CoW)
LVM-Thin snapshots function similarly to ZFS but operate at the block device mapper level.
*   *Speed:* Instant.
*   *Performance Cost:* Each snapshot adds a lookup penalty.
    *   *Chain depth 1:* Negligible.
    *   *Chain depth 10:* Significant IOPS degradation as the kernel traverses the mapping tree.
*   *Strategy:* LVM snapshots are for **Backups**, not for "Time Machine" usage. Delete them after the backup completes.

---

# 3. Directory Storage: The Filesystem Layer

Sometimes you just need a file.

## 3.1 The `.qcow2` Format (QEMU Copy On Write)
When using LVM or ZFS-Zvol, the VM sees a "Raw Block Device". When using Directory storage, the VM sees a `.qcow2` file.

**Features of QCOW2:**
1.  **Compression:** Native zlib/zstd compression *inside* the file.
2.  **Encryption:** Native AES encryption *inside* the file.
3.  **Internal Snapshots:** The file itself contains the snapshots.
    *   *Portability:* You can `scp` a single `.qcow2` file to another server, and it carries its entire snapshot history with it. **This is impossible with LVM/ZFS raw volumes.**

## 3.2 The Overhead
*   *Layering:* VM -> QCOW2 Driver -> Ext4 Filesystem -> LVM -> Disk.
*   *The Cost:* Double journaling. Ext4 journals the metadata updates of the `.qcow2` file growing. The VM journals its own internal filesystem.
*   *Verdict:* **Do not use QCOW2 for Databases.** The Write Amplification is massive. Use it for:
    *   OS Disks (Low IOPS).
    *   Templates (Golden Images).
    *   ISO Libraries.

---

# 4. External Storage: NAS Integration

Proxmox is not an island. It connects to TrueNAS/Synology.

## 4.1 NFS (Network File System)
*   **Version:** Use NFS v4.2 if possible.
*   **The "Hang" Problem:** If the NAS reboots, Proxmox hangs because the NFS mount is "Hard Mounted" inside the kernel. `pvestatd` (the status daemon) freezes while waiting for I/O. The entire GUI becomes unresponsive.
*   **The Fix:** Use `soft` mount options? No, that risks data corruption.
*   **Goliath Strategy:** Dedicated Storage Network (Module 04). If the Storage Network is distinct, a LAN broadcast storm won't kill the storage connection.

## 4.2 SMB/CIFS
*   **Performance:** Single-threaded (mostly). Lower throughput than NFS on Linux.
*   **Use Case:** Only for **Backup Targets** that need to be read by Windows workstations.
*   **Security:** Requires saving credentials in plain text (`/etc/pve/priv/storage/`).

## 4.3 iSCSI (Block Level)
*   **Difference:** NFS presents a *File Share*. iSCSI presents a *SCSI Cable over IP*.
*   **Proxmox sees:** A local block device (`/dev/sdb`).
*   **Format:** We usually format this iSCSI LUN with **LVM-Shared**.
*   **Benefit:** Live Migration without a Cluster Filesystem. All nodes see the same block device.
*   **Constraint:** You cannot use "Thin Provisioning" easily on standard iSCSI. You allocate the full 100GB.

---

# 5. The Physics of Deletion: TRIM and Discard

When you delete a file in a VM, the OS just marks the inode as "free". It does not tell the physical SSD "this silicon cell is empty".
*   **Result:** The LVM-Thin pool stays "Full". The SSD controller thinks the drive is full (WAF increases).

## 5.1 The Discard Command
We must pass the "Delete" command all the way down.
1.  **Guest OS:** Mounts filesystem with `discard` or runs `fstrim -v /`.
2.  **VirtIO Controller:** Must have "Discard" enabled in Proxmox GUI.
3.  **LVM-Thin Layer:** `issue_discards = 1` in `lvm.conf`.
4.  **Physical SSD:** Receives the TRIM command and erases the cell.

**Diagnostic:**
If `lvs` shows your Thin Pool is 90% full, but the VM thinks it's only 50% full, your TRIM chain is broken.

---

# 6. Backup Theory: Vzdump vs PBS

How do these storage backends interact with backups?

## 6.1 Vzdump (Standard Backup)
*   **Mechanism:** It creates a momentary snapshot. It reads the entire disk size (or used size) and pipes it to `.zst` compression.
*   **LVM-Thin:** Very fast snapshotting.
*   **Directory/QCOW2:** Uses `suspend` mode if snapshotting is not supported (standard Directory), or internal QCOW2 snapshots (if verified).
*   *The Downtime:* `snapshot` mode requires the QEMU Guest Agent to "Freeze" the filesystem (fs-freeze) to ensure consistency. This causes a <1s IO pause.

## 6.2 Dirty Bitmaps (PBS)
Proxmox Backup Server is a revolution because it bypasses the filesystem search.
*   **QEMU Dirty Bitmap:** QEMU tracks in RAM exactly which SSD blocks have changed since the last backup.
*   **Speed:** A backup of a 1TB drive with 1GB of changes takes **seconds**, regardless of whether the underlying storage is ZFS, LVM, or Directory.
*   **Requirement:** The storage must support `persistence` of these bitmaps? No, QEMU manages it. But if the VM is fully stopped (stop mode), the bitmap is lost unless using specific "Safe" shutdowns.

---

# 7. Decision Matrix: Choosing the Backend

| Feature | **ZFS (Local)** | **LVM-Thin (Local)** | **Directory (Local)** | **NFS (Network)** | **iSCSI (Network)** |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Performance** | High (ARC) | Very High (Native) | Medium (Overhead) | Network Bound | Network Bound |
| **RAM Usage** | Massive | Low | Low | Low | Low |
| **Snapshots** | Instant | Instant | Slow (QCOW2) | Server Side | N/A (Standard) |
| **Replication** | Built-in (Send) | No | No | N/A | Buffer |
| **Bit Rot Protection** | **Yes** | No | No | Depends on Server | No |
| **Overprovisioning** | Safeish | **Dangerous** | Safe | Safe | No |

**GOLIATH Implementation Plan:**
1.  **Primary Node (AI):** **ZFS Mirror**. We need the checksums for Model Weights.
2.  **Edge Node (Witness):** **LVM-Thin**. We need the RAM.
3.  **Backup Target:** **NFS** to TrueNAS Core (which runs ZFS).

*(End of Module 06)*
