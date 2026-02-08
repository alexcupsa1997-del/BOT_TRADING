# PROXMOX VE: MASTER CURRICULUM
> **Status:** Active Study
> **Target:** 20 Modules / 50,000+ Words Total
> **Focus:** Zero Assumptions, Total Mastery.

---

## LEVEL 1: THE FOUNDATION (HARDWARE & INSTALLATION)
*   **[01_Hardware_Methodology.md](./01_Hardware_Methodology.md)**
    *   *Scope:* Selecting the "Metal". Server vs Consumer hardware. CPU/RAM calc for AI.
*   **[02_Installation_Media.md](./02_Installation_Media.md)**
    *   *Scope:* Creating the precise Bootable USB. Ventoy vs Etcher. BIOS/UEFI flags.
*   **[03_System_Initialization.md](./03_System_Initialization.md)**
    *   *Scope:* The "First Boot". Repository management (No-Sub vs Enterprise).

## LEVEL 2: CORE ARCHITECTURE (NET & STORE)
*   **[04_Network_Architecture.md](./04_Network_Architecture.md)**
    *   *Scope:* The Nervous System. Linux Bridges, Bonds, VLANs, and NIC Offloading.
*   **[05_Storage_ZFS_DeepDive.md](./05_Storage_ZFS_DeepDive.md)**
    *   *Scope:* The Brain. ZFS Pools, RAID-Z levels, ARC caching, Integrity checks.
*   **[06_Storage_LVM_Directory.md](./06_Storage_LVM_Directory.md)**
    *   *Scope:* Alternatives. LVM-Thin for snapshots. Directory storage.

## LEVEL 3: COMPUTE UNITS (VMs & LXC)
*   **[07_Virtual_Machines_KVM.md](./07_Virtual_Machines_KVM.md)**
    *   *Scope:* The Heavy Weights. QEMU/KVM internals. VirtIO drivers. BIOS vs UEFI.
*   **[08_LXC_Containers.md](./08_LXC_Containers.md)**
    *   *Scope:* The Speed. OS-level virtualization. Unprivileged mapping. Nesting Docker.

## LEVEL 4: OPERATION & SECURITY
*   **[09_Resource_Management.md](./09_Resource_Management.md)**
    *   *Scope:* CPU Units, RAM Ballooning, KSM (Deduplication).
*   **[10_User_ACL_Security.md](./10_User_ACL_Security.md)**
    *   *Scope:* Users, Groups, API Tokens, 2FA, Realms.
*   **[11_Backup_Restore.md](./11_Backup_Restore.md)**
    *   *Scope:* `vzdump` Strategies. Snapshot vs Stop. Retention Policies.
*   **[12_Proxmox_Backup_Server.md](./12_Proxmox_Backup_Server.md)**
    *   *Scope:* The Companion. Deduplication servers. Pruning.

## LEVEL 5: ADVANCED ENGINEERING
*   **[13_Firewall_Security.md](./13_Firewall_Security.md)**
    *   *Scope:* The Shield. `pve-firewall`. Distributed Firewalling. ipsets.
*   **[14_High_Availability.md](./14_High_Availability.md)**
    *   *Scope:* Uptime. HA Manager, Watchdogs, Fencing Devices.
*   **[15_Clustering_Concepts.md](./15_Clustering_Concepts.md)**
    *   *Scope:* Multi-Node. Corosync. Quorum votes. Split-brain.

## LEVEL 6: SPECIALIZATION & PROJECT GOLIATH
*   **[16_PCI_Passthrough_AI.md](./16_PCI_Passthrough_AI.md)**
    *   *Scope:* GPU for AI. IOMMU groups. VFIO modules.
*   **[17_Monitoring_Metrics.md](./17_Monitoring_Metrics.md)**
    *   *Scope:* Observability. InfluxDB export. Grafana dashboards.
*   **[18_Automation_IaC.md](./18_Automation_IaC.md)**
    *   *Scope:* Infrastructure as Code. Cloud-Init templates. Terraform.
*   **[19_Goliath_Architecture.md](./19_Goliath_Architecture.md)**
    *   *Scope:* Hosting the Trading Bot. Order Engine Latency on VM vs LXC.
*   **[20_Disaster_Recovery.md](./20_Disaster_Recovery.md)**
    *   *Scope:* Total failure protocols. Rebuilding from scratch.
