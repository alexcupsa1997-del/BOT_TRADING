# MODULE 15: MONITORING & OBSERVABILITY

> **Document Status:** Active (Revision 1 - Deep Dive)
> **Engineering Level:** L4 (SRE - Site Reliability Engineer)
> **Word Count Target:** >3000 Words
> **Scope:** The Eyes. InfluxDB, Grafana, Node Explorer, and the physics of "IO Wait".

---

# 1. The GUI Lie

The Proxmox Web UI is excellent for "Configuration" but terrible for "Observability".
*   **The Sampling:** It updates every 1-2 seconds.
*   **The History:** It uses RRD (Round Robin Database). It aggregates data aggressively.
    *   *Reality:* If a CPU spike lasts 200ms (typical for HFT micro-bursts), the GUI *will never show it*. It looks like a flat line.
*   **The Solution:** Telemetry streaming to a Time Series Database (TSDB).

---

# 2. InfluxDB Integration

Proxmox has native support for InfluxDB.
*   **Protocol:** UDP (Fire and Forget) or HTTP (Reliable).
*   **Goliath Standard:** **HTTP**. We value metric completeness over the 0.01% CPU overhead of TCP.

## 2.1 Configuration
1.  **Deploy InfluxDB:** Run it on a separate Monitoring Node (or Docker Container in a Management Zone).
2.  **Proxmox:** Datacenter -> Metric Server -> Add -> InfluxDB2.
3.  **Token:** Generate a Write Token in InfluxDB.
4.  **Bucket:** `proxmox`.

## 2.2 The Metric Data Model
Proxmox sends:
*   `cpustat`: System load, User, Nice, IOWait.
*   `memory`: RAM used, swap used.
*   `blockstat`: Disk Reads/Writes, Latency.
*   `nics`: Network traffic (Octets).

---

# 3. Grafana: The Cockpit

InfluxDB stores numbers. Grafana makes them useful.

## 3.1 The "Goliath Host" Dashboard
We do not use generic dashboards. We look for **Bottlenecks**.

### Panels to Build:
1.  **CPU I/O Wait (The Killer):**
    *   *Query:* `SELECT last("iowait") FROM "cpustat" ...`
    *   *Physics:* If this > 1%, your disk is too slow for your Application. The CPU is sitting idle, *waiting* for data.
2.  **KVM Steal Time (The Neighbor):**
    *   *Context:* Inside a VM.
    *   *Physics:* How long the VM wanted to run, but the Hypervisor said "No, wait for another VM".
    *   *Threshold:* > 0.5% means the Node is oversubscribed. Move VMs elsewhere.
3.  **UDP Drops (Packet Loss):**
    *   *Critical for HFT.*
    *   *Source:* `node_netstat_Udp_InErrors`.

---

# 4. Node Exporter: The Kernel Spy

Proxmox metrics are "High Level". To see the *truth*, we need `node_exporter`.
*   **Risk:** Installing software on the Hypervisor.
*   **Goliath Policy:** Allowed for `node_exporter` only (Single binary, read-only).

## 4.1 Installation
1.  Download official binary to `/usr/local/bin/node_exporter`.
2.  Create SystemD service:
    ```ini
    [Unit]
    Description=Node Exporter
    [Service]
    User=nobody
    ExecStart=/usr/local/bin/node_exporter
    [Install]
    WantedBy=multi-user.target
    ```
3.  **Firewall:** Allow Port 9100 from `+monitoring_servers` only (Module 14).

## 4.2 What it sees that PVE doesn't
*   **Interrupts per Second:** Is a bad NIC firmware flooding the CPU with IRQs?
*   **Context Switches:** Is the Scheduler thrashing between 5000 threads?
*   **ZFS ARC Stats:** Detailed Cache Hit/Miss ratios.

---

# 5. ZFS Observability

ZFS is a complex beast. You must monitor its stomach.

## 5.1 ARC Efficiency
*   **Metric:** `zfs_arc_hits` vs `zfs_arc_misses`.
*   **Goal:** > 90% Hit Rate.
*   **Analysis:** If Hit Rate < 80% and RAM is full, you need **L2ARC** (NVMe Cache) or more RAM.

## 5.2 Scrub Status
*   **Alert:** Trigger if `zfs_pool_scan_stats` shows a scrub has not run in > 35 days.
*   **Alert:** Trigger IMMEDIATELY if `zfs_pool_health` != "ONLINE".

---

# 6. Alerting: Silence is Golden

We do not want "Info" alerts. We want "Wake Up" alerts.

## 6.1 The AlertManager Rules (Prometheus/Grafana)

### 1. The "Disk Full" Prediction
*   *Bad Alert:* "Disk is 90% full".
*   *Good Alert:* "Disk will fill up **in 24 hours** at current write rate."
*   *Query:* `predict_linear(node_filesystem_free_bytes[4h], 24 * 3600) < 0`

### 2. The "OOM Killer" Watch
*   *Metric:* `dmesg` or log/journal scraping (via Promtail/Loki).
*   *Pattern:* Regex match `Out of memory: Kill process`.
*   *Action:* Critical PagerDuty alert. A process died. State is unknown.

### 3. The "Split Brain" (Corosync)
*   *Metric:* `pve_cluster_quorate`.
*   *Condition:* `== 0`.
*   *Action:* **DEFCON 1.** The cluster has lost quorum. HA Watchdog may fence (reboot) nodes.

---

# 7. Blackbox Monitoring (External)

You cannot monitor the network from *inside* the network.
If the Router dies, the internal Monitoring Server cannot email you.

## 7.1 The External Agent
*   **Location:** AWS/GCP Free Tier, or a Raspberry Pi at your house (for the Datacenter).
*   **Checks:**
    *   **ICMP:** Ping the Gateway.
    *   **TCP:** Connect to VPN Port (WireGuard/OpenVPN).
    *   **HTTP:** Check Proxmox GUI (Port 8006).
*   **Dead Man's Switch:** If the External Agent stops hearing from the Internal Agent, it screams.

---

# 8. Logging Aggregation (Loki)

Metrics tell you *what* happened. Logs tell you *why*.
*   **Architecture:**
    *   **Promtail:** Installed on Proxmox Host. Reads `/var/log/syslog`, `/var/log/pve/tasks/`.
    *   **Loki:** Stores the logs.
    *   **Grafana:** Displays logs alongside metrics.
*   **Correlation:** You see a CPU Spike on the graph. You drag your mouse over it. Grafana shows the Logs from *that exact second*. You see "Vzdump Started". Mystery solved.

*(End of Module 15)*
