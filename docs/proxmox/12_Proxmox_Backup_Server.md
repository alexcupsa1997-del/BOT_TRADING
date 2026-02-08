# MODULE 12: PROXMOX BACKUP SERVER (THE COMPANION)

> **Document Status:** Active (Revision 1 - Deep Dive)
> **Engineering Level:** L4 (Storage Engineer)
> **Word Count Target:** >3000 Words
> **Scope:** Deduplication Physics, Garbage Collection, and the "Remote Sync" architecture.

---

# 1. The Architecture of Deduplication

Standard `vzdump` (Module 11) is dumb. If you backup a 100GB VM today, it stores 100GB. If you backup it tomorrow (with 1MB change), it stores another 100GB.
**PBS (Proxmox Backup Server)** is smart. It ignores files names and disk positions. It looks at **Content**.

## 1.1 Content-Addressable Storage (CAS)
*   **The Chunk:** PBS splits a 100GB disk into fixed-size "Chunks" (e.g., 4MB).
*   **The Hash:** It calculates the SHA-256 hash of that chunk.
*   **The Storage:** It saves the chunk on disk using the Hash as the filename (`/chunks/ab/abcdef...`).
*   **The Magic:**
    *   *Day 1:* You send 100GB. PBS stores 25,000 chunks.
    *   *Day 2:* You change 1MB. PBS calculates hashes for the new state. It finds that 24,999 chunks **already exist** on the server. It only uploads the 1 new chunk.
    *   *Result:* **Incremental-Forever Backups.** Bandwidth Usage: 1MB. Storage Usage: 100GB + 4MB.

## 1.2 The "Fast Index"
PBS stores an `.fidx` (Fixed Index) file for each backup. This file is just a list of Hashes: "Chunk 1 is Hash A, Chunk 2 is Hash B...".
*   *Restore Speed:* To restore, PBS reads the index, grabs the chunks referenced, and assembles the stream. It is as fast as a linear read.

---

# 2. Installation & Topology

PBS is a separate software stack.
*   **Scenario A (Converged):** Install `proxmox-backup-server` *directly* on the Proxmox VE Host.
    *   *Pros:* Saves hardware.
    *   *Cons:* If the Host burns, you lose the Backup Server (and the Restore UI).
    *   *Goliath Verdict:* **Forbidden.**
*   **Scenario B (Dedicated):** A separate physical machine (or VM on a *different* cluster).
    *   *Pros:* Fault isolation.
    *   *Goliath Verdict:* **Mandatory.**

## 2.1 The Datastore
The Datastore is where chunks live.
*   **Filesystem:** **ZFS is Mandatory.**
    *   *Why?* PBS trusts the disk. It assumes if it reads a chunk, the data is valid. ZFS ensures bit-rot protection.
*   **Structure:**
    *   `.chunks/`: The billions of binary blobs.
    *   `ct/`, `vm/`: The manifest files (metadata).

---

# 3. Client-Side Encryption: The AES-256 GCM

PBS supports encryption where the **Proxmox VE Host** encrypts the chunks *before* sending them.
*   **The Key:** The "Encryption Key" lives on the PVE Host (in `/etc/pve/priv/`).
*   **The Backup Server:** Sees only encrypted blobs.
*   **The Implication:** The PBS Admin creates the storage, but **cannot read the backups**.
*   **Goliath Requirement:** Essential for off-site backups to untrusted targets (e.g., Cloud, Friend's house).

**Setup:**
1.  PVE GUI -> Storage -> Add PBS.
2.  Encryption -> **Auto-Generate Key**.
3.  **PRINT THE RECOVERY KEY.** If you lose PVE and the Key, the backups are cryptographic noise.

---

# 4. Namespaces: Multi-Tenancy

You have one Datastore (`/mnt/datastore/backup-hdd`). You have 3 Clusters (Dev, Prod, AI).
*   **Legacy:** Creating 3 separate Datastores is inefficient (deduplication doesn't work across datastores).
*   **Namespaces:** Folders inside a Datastore.
    *   `ns/prod`
    *   `ns/dev`
    *   `ns/ai`
    *   *Benefit:* Deduplication works **across** namespaces. If "Ubuntu 22.04 Base" is in Prod and Dev, it is stored once.
    *   *Permission:* You can give `Dev-User` access only to `ns/dev`.

---

# 5. Garbage Collection & Pruning

In `vzdump`, when you delete a backup, you delete the file.
In PBS, when you "Prune" (delete) a backup snapshot, you only delete the **Index File**. The Chunks remain.

## 5.1 The Garbage Collection (GC) Job
This is the heavy lifter.
1.  **Phase 1 (Mark):** Iterates through *every single index file* of all remaining snapshots. Marks referenced chunks as "Alive".
2.  **Phase 2 (Sweep):** Scans the entire `.chunks` directory. Any chunk *not* marked Alive is deleted.
*   *Performance:* Logic requires reading millions of metadata entries.
*   *Schedule:* Run **Weekly**. Running daily causes unnecessary I/O stress.

## 5.2 The Prune Schedule
Same GFS logic as Module 11 (7 daily, 4 weekly...).
*   *Note:* Pruning is instant. It just deletes small `.fidx` text files. Space is recycled only after GC runs.

---

# 6. Verify Jobs: Trust but Verify

Bit rot happens.
*   **The Job:** PBS reads the chunk from disk, calculates the SHA-256 hash, and compares it to the filename.
*   **Mismatch:** The chunk is corrupt.
*   **The Fix:** If you have a Remote Sync (see Section 7), you can "heal" the local datastore by pulling the good chunk from the remote.
*   **Schedule:** **Monthly**. Re-verify all data.

---

# 7. Remote Sync: The Off-Site Strategy

The "3-2-1 Backup Rule" requires one copy off-site.

## 7.1 The Pull Mechanism
PBS Sync is **Pull-based**.
*   **Site A:** Primary PBS.
*   **Site B:** Remote PBS (at your parents' house / Cloud).
*   **Action:** Site B connects to Site A. It asks " What snapshots do you have?". It downloads the missing chunks.
*   **Efficient:** It creates an incremental backup of the backup store.

## 7.2 The Architecture
1.  **Primary PVE** --(Backup)--> **Primary PBS**.
2.  **Remote PBS** --(Sync)--> **Primary PBS**.
    *   *Bandwidth:* Only sends new deduplicated chunks. Highly efficient over WAN.
    *   *Encryption:* If Client-Side Encryption is used (Section 3), Site B stores encrypted blobs. Site B admin cannot read your data.

---

# 8. Hosting the PBS

PBS is lightweight.
*   **CPU:** 2-4 Cores (For hashing/compression).
*   **RAM:** 4GB (Mainly for ZFS ARC).
*   **Disk:**
    *   **OS:** Small SSD (32GB).
    *   **Datastore:** Large HDD Array (RAIDZ2). SSD not required for storage, but **highly recommended** for the "Special Device" (Metadata) if using ZFS.
    *   *Special Device:* Adding a small NVMe mirror to a HDD pool to store only Metadata makes GC 100x faster.

*(End of Module 12)*
