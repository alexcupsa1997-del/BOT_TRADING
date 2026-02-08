# MODULE 14: SDN & FIREWALLING (MICRO-SEGMENTATION)

> **Document Status:** Active (Revision 1 - Deep Dive)
> **Engineering Level:** L4 (Network Security Architect)
> **Word Count Target:** >3000 Words
> **Scope:** The Distributed Firewall. Moving security from the Edge (Router) to the NIC (Hypervisor). Zero Trust Architecture.

---

# 1. The Death of the Edge Firewall

In the 2000s, we had a "Hard Shell, Soft Center".
*   **The Paradigm:** A big Cisco ASA at the door. Inside, everything talks to everything.
*   **The Failure:** If a hacker breaches the Web Server, they can SSH into the Database because they are on the same "Trusted LAN".
*   **The Goliath Fix:** **Micro-Segmentation**. Every VM has its own Firewall.

## 1.1 The Proxmox Distributed Firewall
Proxmox does not use a "Firewall VM". It uses the Linux Kernel (`netfilter`).
*   **Physics:** It inserts `iptables` / `nftables` rules directly on the `tap100i0` interface (the virtual cable connecting the VM to the Bridge).
*   **The Benefit:** The packet is dropped **before** it enters the Virtual Switch.
*   **Performance:** Line-rate. It handles 10Gbps easily because it tracks connections in kernel memory (Conntrack).

---

# 2. Architecture: Datacenter vs Node vs VM

The Firewall is hierarchical.

## 2.1 Datacenter Level (Global)
*   **Scope:** Policies that apply to the *entire cluster*.
*   **Critical Setting:** `Input Policy: DROP`.
    *   *Meaning:* By default, no traffic enters the Proxmox Host management interface (Port 8006/22) unless explicitly allowed.
*   **The "Lockout" Risk:** If you set Input DROP without allowing your PC's IP, you lock yourself out.
    *   *Recovery:* Login via physical console (IPMI) and run `pve-firewall stop`.

## 2.2 VM Level (Local)
*   **Scope:** The specific VM.
*   **Logic:**
    *   `Enable`: Yes.
    *   `Input Policy`: DROP.
    *   `Output Policy`: ACCEPT (Usually safe to let VMs talk outbound, but for High Security AI, we drop this too).

---

# 3. IPSet: The Alias System

Engineers do not memorize IP addresses. We use Aliases.
**IPSet** is a list of IP/CIDR blocks stored in kernel memory for O(1) matching speed.

## 3.1 Creating IPSets
Located in: Datacenter -> Firewall -> IPSet.
*   **Name:** `management_stations`
    *   `192.168.1.50` (Admin PC)
    *   `10.0.0.5` (VPN Gateway)
*   **Name:** `monitoring_servers`
    *   `192.168.1.99` (Prometheus)

## 3.2 Using IPSets
Rule: `ACCEPT TCP from +management_stations to ANY port 22`.
*   *Benefit:* If you hire a new Admin, you add their IP to the IPSet. You do **not** touch the 500 Firewall Rules.

---

# 4. Security Groups: The Policy Abstraction

You have 50 Web Servers. You do not write 50 sets of rules.
You create a **Security Group**.

## 4.1 Definition
*   **Group Name:** `web-server-public`
*   **Rules:**
    *   ACCEPT TCP Source: `Any` Dest: `80, 443`.
    *   ACCEPT TCP Source: `+management_stations` Dest: `22`.
    *   ACCEPT TCP Source: `+monitoring_servers` Dest: `9100` (Node Exporter).

## 4.2 Application
1.  Go to VM 100 (Web-01).
2.  Firewall -> Insert: `group web-server-public`.
3.  Go to VM 101 (Web-02).
4.  Firewall -> Insert: `group web-server-public`.
*   *Result:* Changing the Group updates all 50 VMs instantly.

---

# 5. SDN (Software Defined Network): The New Era

Before Proxmox 8.1, we used "VLAN Aware Bridges" (Module 04).
Now, we have the **SDN Controller**.

## 5.1 Zones
A Zone is a logical network type.

### Simple Zone (Isolated)
*   **Physics:** Creates a bridge `vnetX` that is disconnected from the world.
*   **Use Case:** A "Malware Sandbox" or "CI/CD Build Environment" that needs to act like a LAN but never touch the physical uplink.

### VLAN Zone (The Standard)
*   **Physics:** Wraps the classic 802.1Q tagging.
*   **Benefit:** In the GUI, you select "Network: My-VLAN-10" instead of typing "Tag: 10". It prevents typos.

### VXLAN Zone (The Overlay)
*   **Physics:** Encapsulates L2 Frames inside UDP Packets (Port 4789).
*   **Magic:** You can span a Layer 2 Network across a Layer 3 WAN.
*   **Scenario:** Node A is in New York. Node B is in London. They are routed via IP.
    *   VM A (NY) sends an ARP request.
    *   Proxmox wraps it in UDP, sends it to London.
    *   Proxmox (London) unwraps it.
    *   VM B (London) sees the ARP.
    *   *Result:* **Geo-Stretched L2 Cluster.** (Use with caution due to latency).

---

# 6. Conntrack: The HFT Killer

The Firewall is "Stateful". It remembers "IP A connected to IP B on Port 443".
*   **The Table:** `/proc/net/nf_conntrack`.
*   **The Limit:** RAM.
*   **The Crash:** If you have a DDoS or a High-Frequency Algo opening 100,000 connections/sec, the table fills up.
*   **Symptom:** `nf_conntrack: table full, dropping packet`.

## 6.1 Tuning for HFT
For the "Neural Trader" VM, we bypass connection tracking for the Data Feed.
*   **Raw Table:** use `NOTRACK` targets in `iptables`.
*   **Proxmox Config:**
    In `/etc/pve/nodes/pve1/host.fw`:
    ```
    [OPTIONS]
    nf_conntrack_max: 1000000
    nf_conntrack_tcp_timeout_established: 600
    ```
    *   *Logic:* Increase the max table size. Decrease the timeout (kill dead connections faster).

---

# 7. Suricata Integration (IDS/IPS)

Proxmox Firewall is L3/L4 (IP + Port). It does not see "Malicious HTTP Payload".
For that, we mirror traffic to **Suricata**.
*   **Port Mirroring:**
    *   Network Device -> Advanced -> **Open vSwitch** (Required for Port Mirroring. Linux Bridge mirroring is harder).
    *   Mirror Packets from `tap100i0` to `tap105i0` (The IDS VM).

*(End of Module 14)*
