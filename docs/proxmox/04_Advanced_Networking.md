# MODULE 04: ADVANCED NETWORKING & SOFTWARE DEFINED SWITCHING

> **Document Status:** Active (Revision 1 - Deep Dive)
> **Engineering Level:** L4 (Network Architect)
> **Word Count Target:** >3000 Words
> **Scope:** Bridges, Bonds, VLANs, and the Physics of Packet Switching.

---

# 1. The Virtual Switch Paradigm

In a hypervisor, the "Network Cable" is a lie. It is a memory pointer copy operation.
The Proxmox Host acts as a massive, programmable Layer 2 Switch. We have two primary engines to drive this: **Linux Bridge** and **Open vSwitch (OVS)**.

## 1.1 Linux Bridge (`vmbr`) vs Open vSwitch (`vmbr`)
Systems Architects often default to OVS because "it sounds enterprise". This is a mistake for 90% of deployments.

| Feature | Linux Bridge | Open vSwitch (OVS) |
| :--- | :--- | :--- |
| **Kernel Space** | Yes (Native) | Yes (Module) |
| **Complexity** | Low (Text Files) | High (Database Driven) |
| **Performance** | **Higher Throughput** (Simpler Code Path) | Slightly Lower (More Overhead) |
| **Features** | Basic L2 Switching, VLANs | VXLAN, GRE, RSTP, SDN Controllers |
| **Stability** | Rock Solid (20+ years) | Complex Failure Modes |

**Goliath Verdict:**
*   **Use Linux Bridge** for 99% of nodes. It is faster, simpler, and less prone to breaking during kernel updates.
*   **Use OVS** only if you strictly require **RSTP** (Rapid Spanning Tree Protocol) to prevent loops in a mesh topology, or if you are building a massive multi-tenant cloud with VXLAN overlays (BGP-EVPN).

---

# 2. Link Aggregation (Bonding): The Bandwidth Myth

We addressed this briefly in Module 02. Now we solve the configuration.

## 2.1 The Hash Policy (xmit_hash_policy)
Bonding 2x 10GbE links does not give you a 20GbE pipe. It gives you a 2-lane highway. One car (TCP Stream) can only use one lane.

*   **Layer 2 (Mac Address):** Default.
    *   *Logic:* Hashes Source MAC and Dest MAC.
    *   *Problem:* All traffic from the Gateway (Router) has the *same* Dest MAC. Result: **Zero balancing.** All ingress traffic hits one wire.
*   **Layer 2+3 (IP Address):**
    *   *Logic:* Hashes IP Addresses. Better.
*   **Layer 3+4 (IP + Port):** **Mandatory for AI.**
    *   *Logic:* Hashes IP + TCP/UDP Port.
    *   *Result:* A single DB connection (Port 5432) uses Link A. A backup stream (Port 443) uses Link B.
    *   *Requirement:* `bond-xmit-hash-policy: layer3+4`.

## 2.2 The Configuration (`/etc/network/interfaces`)
Do not use the GUI for this. The GUI hides the critical `hash-policy` settings.

**Scenario: Dual 10GbE LACP Bond (eno1 + eno2)**

```auto
auto lo
iface lo inet loopback

iface eno1 inet manual
iface eno2 inet manual

auto bond0
iface bond0 inet manual
    bond-slaves eno1 eno2
    bond-miimon 100
    bond-mode 802.3ad
    bond-xmit-hash-policy layer3+4

auto vmbr0
iface vmbr0 inet static
    address 192.168.1.10/24
    gateway 192.168.1.1
    bridge-ports bond0
    bridge-stp off
    bridge-fd 0
    bridge-vlan-aware yes
```
*   **bond-miimon 100:** Checks link status every 100ms.
*   **bridge-vlan-aware yes:** Transforms the bridge into a managed switch that understands 802.1Q tags.

---

# 3. VLANs (802.1Q): Segmentation is Security

We do not run Storage traffic, Management traffic, and Public Internet traffic on the same subnet. That is suicide.

## 3.1 The "VLAN Aware" Bridge Strategy
Instead of creating `vmbr0.10`, `vmbr0.20` (Legacy Mode), we use a single `vmbr0` and tag packets at the port level.

### Physical Switch Config (Sample: Ubiquiti/Cisco)
The port connecting to the Proxmox Host must be a **Trunk Port**.
*   **Native VLAN (Untagged):** VLAN 1 (Management). Host IP lives here.
*   **Tagged VLANs:** 10 (Public), 20 (Storage), 30 (Corosync).

### Virtual Machine Config
In Proxmox GUI (or `100.conf`):
*   **Network Device:** `vmbr0`.
*   **VLAN Tag:** `10`.
*   *Result:* Proxmox tags the packet as it leaves the VM tap interface. It enters the bridge tagged. It leaves the physical `bond0` tagged. The physical switch reads tag 10 and routes it.

## 3.2 OVS Intra-Host Routing (The Kernel Bypass)
If VM A (Web) talks to VM B (DB) on the *same host*, the packet never touches the physical NIC.
*   **Speed:** It is a memory copy. Bandwidth is limited only by CPU/RAM speed (200Gbps+).
*   **Latency:** < 10us.
*   **Optimization:** Ensure both VMs are on the same `vmbr` to utilize this. If they are on different bridges, the packet might be routed via the physical gateway (Hairpin NAT), adding 200us latency.

---

# 4. Jumbo Frames (MTU 9000): The Efficiency King

Standard MTU (1500) kills CPU performance on 10GbE+ links.

## 4.1 The Overhead Math
*   **Frame:** 1500 bytes.
*   **Header:** 14 bytes (Eth) + 20 bytes (IP) + 20 bytes (TCP) = 54 bytes.
*   **Payload:** 1446 bytes. Efficiency: 96%.
*   **Interrupts:** 820k packets/sec for 10Gbps.

*   **Jumbo:** 9000 bytes.
*   **Header:** 54 bytes.
*   **Payload:** 8946 bytes. Efficiency: 99%.
*   **Interrupts:** 138k packets/sec. (**6x Reduction** in CPU Load).

## 4.2 The "End-to-End" Trap
Jumbo Frames must be enabled on **EVERY** device in the chain.
1.  **VM Config:** `virtio` MTU = 9000.
2.  **Host Bond:** `mtu 9000`.
3.  **Physical Switch:** MTU 9000 (usually 9216 on Cisco).
4.  **NAS/Storage:** MTU 9000.

**Failure Mode:** If *one* device (e.g., the Switch) stays at 1500, it effectively "blackholes" large packets. The connection works for Ping (small), but hangs for SSH/HTTPS (large). This is the "Path MTU Discovery" (PMTUD) failure.

---

# 5. Kernel Tuning: The Physics of 25GbE

Linux Defaults are tuned for 1990s 100Mbps Ethernet. They will throttle 10GbE/25GbE flows in GOLIATH.

## 5.1 The BBR Congestion Control
TCP uses an algorithm to decide "How fast can I send before I drop packets?".
*   **CUBIC (Default):** Reactive. It sends until it sees packet loss, then cuts speed in half. Unsuitable for high-latency WAN or lossy high-speed LAN.
*   **BBR (Bottleneck Bandwidth and Round-trip propagation time):** Proactive. Developed by Google. It models the *pipe* capacity and sends *exactly* that amount.
*   *Result:* Massive throughput stability on 10GbE WAN links.

**Enable BBR:**
```bash
echo "net.core.default_qdisc=fq" >> /etc/sysctl.conf
echo "net.ipv4.tcp_congestion_control=bbr" >> /etc/sysctl.conf
sysctl -p
```
*   *Note:* BBR requires the "Fair Queueing" (`fq`) scheduler. It does not work with `fq_codel`.

## 5.2 Ring Buffers (ethtool)
NICs have hardware buffers (RX/TX Rings) to store packets before the CPU processes them.
*   *Default:* often 512 or 1024 descriptors.
*   *High Load:* If the CPU is busy (100% load), the ring fills up. The NIC drops the packet *before the OS even sees it*.
*   *Fix:* Increase rings to max.

```bash
ethtool -g eno1
# Pre-set maximums:
# RX: 4096
# TX: 4096
# Current hardware settings:
# RX: 512
# TX: 512

# Command to Maximize:
ethtool -G eno1 rx 4096 tx 4096
```

---

# 6. Hardware Offloading: The Double-Edged Sword

NICs claim they can do work for the CPU. Sometimes they do it wrong.

## 6.1 TSO (TCP Segmentation Offload)
*   *Concept:* The CPU sends a 64KB "Super-Packet" to the NIC. The NIC chops it into 1500-byte Ethernet frames.
*   *Benefit:* Massive CPU savings.
*   *Risk:* If the NIC firmware is buggy (Broadcom), it corrupts the checksum.
*   *Verdict:* **Enable** for Intel/Mellanox. **Disable** for Realtek/Broadcom.

## 6.2 LRO (Large Receive Offload)
*   *Concept:* The NIC aggregates incoming small packets into one large chunk for the CPU.
*   *The Trap:* Proxmox is a *Router* (Bridge). If the NIC modifies packets (aggregates them), the destination VM sees a "fake" packet that breaks TCP sequence numbers.
*   *Verdict:* **DISABLE on Host.** Let the VM handle aggregation (GRO - Generic Receive Offload).
    ```bash
    ethtool -K eno1 lro off
    ```

---

# 7. SR-IOV: Bypassing the Bridge

For the absolute lowest latency (HFT Enclave), we skip the bridge entirely.

## 7.1 Single Root I/O Virtualization
SR-IOV allows one Physical Function (PF) - the card itself - to spawn multiple Virtual Functions (VFs).
*   *Visual:* The card appears as 64 separate PCIe devices (`03:00.1`, `03:00.2`...).
*   *Pass-through:* We pass `03:00.1` directly to the "Engine VM".
*   *Result:* The VM kernel talks directly to the NIC silicon. **Zero Host CPU Overhead.**
*   *Latency:* 10us (Network) + 1us (PCIe). **Unbeatable.**

## 7.2 Configuration (Mellanox ConnectX-4)
1.  **BIOS:** Enable `SR-IOV Global`.
2.  **Kernel:**
    ```bash
    # /etc/modprobe.d/mlx5_core.conf
    options mlx5_core num_vfs=4
    ```
3.  **Proxmox:**
    Add PCI Device -> Select `0000:03:00.1` -> Check `PCI-Express`.

---

# 8. Network Diagnostics: The Packet Whisperer

When packets die, where do they go?

## 8.1 `tcpdump` on Bridges
Capturing on `eno1` shows **Ingress** (tagged). Capturing on `vmbr0` shows **Egress** (untagged/striped).
*   *Command:*
    ```bash
    tcpdump -i vmbr0 -nn -e vlan
    ```
    *   `-nn`: No DNS resolution (Speed).
    *   `-e`: Show Ethernet Headers (MAC addresses).
    *   `vlan`: Filter for tagged traffic.

## 8.2 Bandwidth Testing (`iperf3`)
Do not test "Disk to Disk" (smb/nfs). Test network first.
*   **Server (VM A):** `iperf3 -s`
*   **Client (VM B):** `iperf3 -c <IP_A> -P 4`
    *   `-P 4`: Parallel streams. Necessary to saturate 10GbE. Single stream is CPU-bound.
    *   *Goal:* 9.4 Gbps (on 10GbE). Anything < 9Gbps indicates a bridge/MTU/CPU issue.

*(End of Module 04)*
