# MODULE 03: CLUSTER PHYSICS & KERNEL TUNING

> **Document Status:** Active (Revision 2 - Deep Dive)
> **Engineering Level:** L4 (Systems Architect)
> **Word Count Target:** >3000 Words
> **Scope:** The Cluster Stack. Corosync, Watchdogs, and Kernel Network Tuning.

---

# 1. The Totem Ring Protocol (Corosync Internals)

Proxmox Clustering (`pvecm`) is built on top of **Corosync**, which implements the **Totem Single-Ring Ordering Protocol**. Understanding this is mandatory for GOLIATH stability.

## 1.1 The Token Rotation Physics
In a Proxmox cluster, nodes do not "talk" randomly. They pass a "Token" in a strictly ordered ring (Node 1 -> Node 2 -> Node 3 -> Node 1).
*   **The Rule:** A node can only multicast messages (e.g., "I started VM 100") when it holds the Token.
*   **Token Timeout (`token`):** Default = 1000ms.
*   **Consensus:** If a node does not receive the token within 1000ms, it declares the ring broken.

### The Problem: High Latency & Packet Loss
*   *Scenario:* You saturate your 10GbE link with a backup job (Ceph Rebalance).
*   *Result:* The Token packet is queued behind 9KB Jumbo Frames of data. Latency spikes to 1500ms.
*   *Catastrophe:* Node 2 declares Node 1 dead. It initiates a **Fencing** event (Power Cycle via IPMI). The cluster reboots itself in a loop.

**Goliath Strategy:**
1.  **Dedicated Cluster Network:** Corosync traffic **MUST** be on a physically separate 1GbE/10GbE link from Data traffic.
2.  **QoS (Quality of Service):** If shared, tag Corosync packets with DSCP 46 (Expedited Forwarding) at the switch level.

## 1.2 The Quorum Vote (Paxos)
Proxmox uses a simple majority vote.
*   *Total Votes:* $N$.
*   *Quorum:* $(N/2) + 1$.
*   *3 Nodes:* Quorum = 2. You can lose 1 node.
*   *2 Nodes:* Quorum = 2. You can lose 0 nodes. (The "Split Brain" problem).
*   *The QDevice:* For 2-node clusters, we install a `qdevice` (Quorum Device) on a Raspberry Pi or Cloud VPS to act as a tie-breaker.

---

# 2. Watchdog Timers: The Dead Man's Switch

When the Kernel freezes (Soft Lockup) or Corosync crashes, the node enters an "Unknown" state. This is dangerous for HA (High Availability). We need a mechanism to **Shoot usage in the head**.

## 2.1 Software Watchdog (`softdog`)
*   *Mechanism:* A kernel module that expects a "pet" (write to `/dev/watchdog`) every 10 seconds.
*   *Failure:* If the userspace (Corosync) freezes, no pet. The kernel panics and reboots.
*   *Risk:* What if the kernel itself hangs in an interrupt loop? The softdog also hangs.

## 2.2 Hardware Watchdog (`ipmi_watchdog`)
*   *Mechanism:* The IPMI BMC (Baseboard Management Controller) - a separate computer on the motherboard - expects the OS to ping it.
*   *Failure:* If the *entire* CPU locks up, the BMC (which runs on its own ARM CPU) notices the silence. It cuts power to the main CPU and restarts it.
*   *GOLIATH Mandate:* **Use IPMI Watchdogs.**

**Configuration:**
```bash
# /etc/default/pve-ha-manager
WATCHDOG_MODULE="ipmi_watchdog"
```
*   *Note:* You must enable the correct kernel module for your board (e.g., `ipmi_si`).

---

# 3. Kernel Tuning for 10GbE AI Workloads

Linux defaults are tuned for 1990s 100Mbps Ethernet. They will throttle 10GbE/25GbE AI flows.

## 3.1 Receiver Side Scaling (RSS)
A 25GbE stream generates millions of interrupts per second. One CPU core cannot handle them.
*   *RSS:* Hashes incoming packets (Tuple: IP/Port) to distribute interrupts across multiple CPU cores.
*   *Configuration:* Ensure your NIC driver (`ixgbe`/`mlx5_core`) has RSS enabled with queues equal to valid CPU cores.
    ```bash
    ethtool -l eno1
    # Combined: 64 (Good).
    ```

## 3.2 TCP Buffer Sizing (`rmem`/`wmem`)
The "Bandwidth-Delay Product" (BDP) determines how much data can be "in flight" before an ACK is required.
*   *The Default:* ~200KB buffers.
*   *The Physics:* On a 10GbE link with 0.1ms latency, this is fine. But for cross-region replication (100ms latency), 200KB limits throughput to ~20Mbps.

**Sysctl Tunning (`/etc/sysctl.d/99-goliath.conf`):**
```ini
# Max Receive Buffer: 16MB
net.core.rmem_max = 16777216
# Max Send Buffer: 16MB
net.core.wmem_max = 16777216
# TCP Autotuning: Min / Default / Max
net.ipv4.tcp_rmem = 4096 87380 16777216
net.ipv4.tcp_wmem = 4096 65536 16777216
# Congestion Control: BBR (Google's Algo)
net.core.default_qdisc = fq
net.ipv4.tcp_congestion_control = bbr
```

## 3.3 Jumbo Frames (MTU 9000)
Standard Ethernet MTU is 1500 bytes.
*   *Overhead:* 60 bytes of header per packet. ~4% overhead.
*   *Interrupt Rate:* 10Gbps @ 1500 bytes = 800,000 packets/sec.
*   *Jumbo Frames:* 9000 bytes.
    *   *Result:* 130,000 packets/sec. (6x reduction in CPU Interrupts).
*   *GOLIATH Rule:* Enable MTU 9000 on the **Storage Network** (Ceph/NFS). Keep MTU 1500 on the **Management Network** to avoid fragmentation issues with WAN routers.

---

# 4. Journaling & Logging: Preventing SSD Death

Proxmox logs *everything*. We must tame `systemd-journald`.

## 4.1 Storage: `volatile` vs `persistent`
By default, logs are written to `/var/log/journal`.
*   *The Wear:* Constant syncs kill consumer SSDs.
*   *The Fix:* Use `Storage=volatile` (RAM) or limit the size.

**/etc/systemd/journald.conf:**
```ini
[Journal]
Storage=persistent
SystemMaxUse=1G
SystemKeepFree=10G
SyncIntervalSec=5m
```
*   *SyncIntervalSec:* Default is 5s? Increase to 5m. We accept losing 5 minutes of logs on a crash to save 1TBW of SSD life per year.

---

# 5. APT Pinning: The Stability Shield

You never want `apt upgrade` to accidentally install a new Kernel 6.8 when your NVIDIA driver only supports 6.5.

## 5.1 Kernel Pinning
*   *List Kernels:* `proxmox-boot-tool kernel list`.
*   *Pin:* `proxmox-boot-tool kernel pin 6.5.11-8-pve`.
*   *Why:* Ensures that a reboot (manual or watchdog) always brings up the **Known Good State**.

## 5.2 Package Hold
If you compile a custom version of `ffmpeg` or `zfs-dkms`:
```bash
apt-mark hold zfs-dkms
```
This prevents apt from overwriting your custom build with the upstream repository version.

---

# 6. Quorum Protocol Mechanics

How does Proxmox decide who survives a network partition?

## 6.1 The 51% Attack (Split Brain)
Imagine a 2-node cluster (Node A, Node B) with a broken cable.
*   Node A thinks Node B is dead.
*   Node B thinks Node A is dead.
*   If both try to start "VM 100", you get **filesystem corruption**.
*   *Corosync logic:* A node checks "Do I see > 50% of the votes?".
    *   Node A sees 1 vote (itself). Total = 2. 1 <= 1. **Loss of Quorum.**
    *   **Action:** Node A locks the filesystem (Read-Only) and reboots itself.

## 6.2 The QDevice Solution
We introduce a 3rd voter (Raspberry Pi/External Server).
*   **Topology:** Node A (1 Vote), Node B (1 Vote), QDevice (1 Vote). Total = 3.
*   **Cable Break:**
    *   Node A sees itself + QDevice. (2/3). **Quorum!** It stays up.
    *   Node B sees itself + (nothing). (1/3). **Fenced.** It reboots.
*   **Result:** Deterministic failover.

---

# 7. Final Security Audit (Day 0)

1.  **SSH Hardening:**
    *   Disable Password Auth.
    *   AllowedUsers `root admin`.
    *   ListenAddress `192.168.1.10` (Management LAN only).

2.  **Fail2Ban:**
    *   Install: `apt install fail2ban`.
    *   Jail: `[proxmox]`.
    *   Port: `8006`.
    *   BanTime: `1h`.

3.  **AppArmor Profiles:**
    *   Ensure all LXC containers are running with `apparmor: unconfined` ONLY if absolutely necessary (e.g., Docker-in-LXC). Default profile protects the host kernel from container breakout.

*(End of Module 03)*
