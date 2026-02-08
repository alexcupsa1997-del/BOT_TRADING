# MODULE 08: LXC CONTAINERS (THE SPEED LAYER)

> **Document Status:** Active (Revision 1 - Deep Dive)
> **Engineering Level:** L4 (DevOps Engineer)
> **Word Count Target:** >3000 Words
> **Scope:** Metal-speed virtualization. Unprivileged security protocols, User ID Mapping, and the "Docker-in-LXC" paradox.

---

# 1. The Kernel Namespace

KVM (Module 07) simulates a motherboard. LXC (Linux Containers) simulates an **OS Environment**.
*   **The Physics:** LXC processes run *directly* on the Host Kernel. There is no instruction translation. There is no memory ballooning.
*   **The Benefit:** **Zero latency penalty.** An LXC container is exactly as fast as a native process.
*   **The Risk:** If you crash the kernel in the container, you crash the Host.

## 1.1 Unprivileged vs Privileged
This is the single most misunderstood concept in Proxmox.

### Privileged Containers (`root` = `root`)
*   **Concept:** The `root` user (UID 0) inside the container is mapped directly to `root` (UID 0) on the Proxmox Host.
*   **The Danger:** If a hacker breaks out of the container (Container Escape vulnerability), they are **Root on your server**. They can format the ZFS pool.
*   **Goliath Rule:** **Strictly Forbidden** for any service exposed to the internet.

### Unprivileged Containers (`root` = `nobody`)
*   **Concept:** The `root` user (UID 0) inside the container is mapped to an unprivileged user (UID 100000) on the Host.
*   **The Security:** If a hacker escapes, they find themselves as UID 100000 on the host. They cannot read `/etc/shadow`. They cannot mount drives.
*   **The Friction:** "Permission Denied" errors when mounting ZFS datasets or network shares. (Solved in Section 2).

---

# 2. Storage Mapping: Bind Mounts

In KVM, we use Virtual Disks (`.qcow2` or Zvol). In LXC, we can pass a **directory** from the host directly to the guest.

## 2.1 The "Zero Overhead" Database
*   **Scenario:** Postgres Database.
*   **KVM Way:** ZFS (Host) -> Zvol (Block) -> EXT4 (Guest) -> PostgreSQL. (Double Filesystem Overhead).
*   **LXC Bind Mount Way:** ZFS (Host) -> PostgreSQL. (Zero Overhead).

## 2.2 Configuration (`/etc/pve/lxc/100.conf`)
You cannot do this easily in the GUI. You must edit the config.

```bash
# Host Path: /rpool/data/postgres-data
# Guest Path: /var/lib/postgresql/data
mp0: /rpool/data/postgres-data,mp=/var/lib/postgresql/data
```

## 2.3 The "Unprivileged" Ownership Problem
*   *Issue:* The Host folder is owned by `root:root` (0:0).
*   *Container:* The Container `root` is actually Host user `100000`.
*   *Result:* The container cannot write to the bind mount.

### The Fix: ID Mapping (The Math)
We must change the ownership of the *Host* directory to match the *Mapped* ID.
1.  **Chown (Host Side):** `chown -R 100000:100000 /rpool/data/postgres-data`
2.  **Result:**
    *   Host sees: Owned by `100000`.
    *   Container sees: Owned by `root` (0).
    *   **Success.**

---

# 3. Docker Inside LXC (The Inception Layer)

Why run Docker in LXC? Why not just a VM?
*   **Density:** You can run 50 LXC containers on a node that supports 5 VMs.
*   **Speed:** No VM overhead.

## 3.1 The Storage Driver Conflict
Docker wants to use `overlay2` (OverlayFS).
*   **Problem:** Standard ZFS does not support OverlayFS on top of it easily in unprivileged containers.
*   **Symptom:** Docker fails to start with "Storage Driver" errors.

## 3.2 The Solution: Fuse-OverlayFS
We must enable the FUSE (Filesystem in User Space) module options.

**(Step 1) Container Options (GUI):**
*   **Features:** Check `Nesting` and `keyctl`.
    *   *Nesting:* Allows mounting `proc` and `sys` filesystems inside the container (Required for Docker).

**(Step 2) Install Fuse Overlay (Inside Container):**
```bash
apt install fuse-overlayfs
```

**(Step 3) Docker Config (`/etc/docker/daemon.json`):**
Force Docker to use the Fuse driver.
```json
{
  "storage-driver": "fuse-overlayfs"
}
```

## 3.3 The ZFS Native Driver (Advanced)
Alternatively, we can tell Docker to use the Host's ZFS driver.
1.  Create a ZFS dataset for the container's Docker dir: `zfs create rpool/data/lxc-100-docker`
2.  Bind mount it to `/var/lib/docker`.
3.  Set Docker driver to `zfs`.
*   **Performance:** Massive. 10x faster than Fuse-Overlay.
*   **Complexity:** High. Requires careful UID mapping.

---

# 4. Resource Limiting: Cgroups

Since LXC processes share the Kernel, a run-away process can starve the host CPU (unlike KVM where the vCPU limit is hard).

## 4.1 CPU Units (Shares)
*   **Default:** 1024.
*   **Scenario:** Container A (Priority) vs Container B (Background).
*   **Config:** Set A to `2048`, Set B to `512`. A gets 4x more CPU time during contention.

## 4.2 Memory Limits (OOM)
*   **Hard Limit:** If you set 2GB, the kernel kills the process at 2001MB.
*   **Swap:** Crucial. If Swap is 0, the process dies instantly. If Swap is 512MB, it slows down (gives you time to react).


# 5. Network: vEth vs Phys

LXC networking is simpler than KVM, but has specific modes.

## 5.1 vEth (Virtual Ethernet) - Default
*   **Mechanism:** Creates a pair of pipes. One end in the Host Bridge (`fwbr100`), one end in the Container (`eth0`).
*   **Pros:** Firewall support (Proxmox Firewall). Live Migration support.
*   **Cons:** Small CPU overhead for packet switching.

## 5.2 Phys (Physical Interface Passthrough)
*   **Mechanism:** Takes a physical NIC (e.g., `enp3s0`) and **moves** it from the Host namespace to the Container namespace.
*   **Result:** The Host *loses* the network card. The Container gets direct hardware access.
*   **Use Case:** High-throughput Ingestion Node (10GbE line rate ingest).

---

# 6. Device Passthrough: USB & GPU

Containers can access hardware, but they need permission (cgroups).

## 6.1 Google Coral TPU (USB AI Accelerator)
For the "Edge" nodes running inference.

**Host Step (Find Device):**
```bash
lsusb
# Bus 002 Device 003: ID 18d1:9302 Google Inc.
```

**Container Config (`100.conf`):**
```bash
lxc.cgroup2.devices.allow: c 189:* rwm
lxc.mount.entry: /dev/bus/usb/002/003 dev/bus/usb/002/003 none bind,optional,create=file
```
*   `c 189:*`: Allows Character Device 189 (USB Bus).
*   `rwm`: Read, Write, Mknod permissions.

## 6.2 GPU Passthrough (LXC)
*   **Hard Mode:** Unlike KVM PCIe passthrough, LXC shares the **Kernel Driver**.
*   **Requirement:** You must install the NVIDIA Driver on the **Host** AND the **Container**.
*   **Version Match:** The driver versions must be *identical*.
*   **Goliath Verdict:** Too fragile. Use KVM for GPU. Use LXC for TPU/USB.

---

# 7. Decision Matrix: VM vs LXC

When to use what in the Goliath Architecture.

| Feature | **KVM (VM)** | **LXC (Container)** |
| :--- | :--- | :--- |
| **Isolation** | Complete (Kernel) | Weak (Namespace) |
| **Kernel Tuning** | Custom (Sysctl) | Shared (Host) |
| **Boot Speed** | 10-20 seconds | < 1 second |
| **Efficiency** | 95% Native | 99.9% Native |
| **Live Migration** | Yes (RAM State) | Yes (Restart) |
| **Docker** | Clean | Nested (Complex) |

## 7.1 The Goliath Strategy
*   **Neural Trader (AI):** **KVM**. We need custom kernel flags for hugepages, specific CPU pinning, and guaranteed isolation for the logic core.
*   **Databases (Postgres/Redis):** **LXC**. We need the raw disk I/O of bind mounts and the memory efficiency.
*   **Ingestion (Python Scrapers):** **LXC**. Low footprint, spin up/down instantly.
*   **Microservices (Docker Swarm):** **KVM**. Running Docker in LXC adds complexity (Fuse-Overlay). It is cleaner to run a "Docker Node" VM.

*(End of Module 08)*
