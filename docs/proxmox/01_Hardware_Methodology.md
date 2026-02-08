# MODULE 01: ARCHITECTURAL PHYSICS & HARDWARE SELECTION

> **Document Status:** Active (Revision 2 - Deep Dive)
> **Engineering Level:** L4 (Systems Architect)
> **Word Count Target:** >3000 Words
> **Scope:** The rigorous physics of compute, storage, and I/O for AI/HFT workloads.

---

# 1. The Silicon Topology: A Physics-First Approach

In the realm of high-performance virtualization, "Hardware Selection" is a misnomer. We are not selecting logical components; we are engineering a physical substrate capable of sustaining specific thermal, electrical, and data-flow loads. The GOLIATH engine demands a zero-compromise approach to **determinism**. To achieve this, we must first understand the enemy: **Latency Jitter**.

## 1.1 The NUMA Cliff & Interconnect Latency
The single most critical concept for scaling AI and HFT workloads on Proxmox is **Non-Uniform Memory Access (NUMA)**.

### The Myth of "Cores"
A 64-core CPU is not a single computing unit. It is a distributed system on a package.
*   **AMD EPYC (Zen 3/4):** Composed of **CCX (Core Complex)** units. 8 cores share a customized L3 cache.
*   **The Infinity Fabric (IF):** Connects these CCX units.
    *   *Local Access:* A core accessing L3 cache within its own CCX takes **~10-12ns**.
    *   *Remote Access (Different CCX):* A core accessing L3 cache in a neighboring CCX (via IF) takes **~40-60ns**.
    *   *Remote Socket:* A core accessing RAM attached to the second CPU socket takes **~100ns-140ns**.

**The GOLIATH Consequence:**
If your Python inference engine (running on Core 0) tries to access Tensor data stored in RAM lines controlled by Core 32 (on a different die), you incur a **4x-10x latency penalty** on every memory fetch.
*   *For HFT:* This means the difference between filling an order at the top of the book vs. getting slippage.
*   *For AI:* In an LLM generating 50 tokens/sec, this "NUMA Thrashing" can drop throughput to 15 tokens/sec as the memory controller stalls waiting for IF routing.

**Proxmox Mitigation Strategy:**
We do not just "assign cores". We **pin** them.
*   *Topology Aware Scheduling:* We must map VM vCPUs to physical CCX boundaries.
*   *Command:* `numactl --hardware` identifies the distance between nodes.
*   *Implementation:* In the VM config (`/etc/pve/qemu-server/100.conf`), we will eventually use `numa: 1` and strictly define `affinity`.

## 1.2 PCIe Root Complexes & The Lane Starvation Problem
The "Consumer" vs "Enterprise" debate is mathematically settled by one metric: **PCIe Root Port Saturation**.

### The I/O Math
Let's model the bandwidth requirements of a fully loaded GOLIATH node:
1.  **Network Ingress (Market Data):** Dual 25GbE NICs = 50 Gbps.
    *   *Requirement:* PCIe Gen3 x8 or PCIe Gen4 x4.
2.  **Storage Throughput (Model Loading):** 4x NVMe Gen4 RAID10 = ~28 GB/s sequential read.
    *   *Requirement:* 16 Lanes (4 drives * 4 lanes).
    *   *Note:* A single Gen4 NVMe hits 7 GB/s. Four of them strictly require 16 dedicated CPU lanes.
3.  **Compute Offload (GPU):** 1x NVIDIA RTX 4090 = 32 GB/s bidirectional.
    *   *Requirement:* 16 Lanes (Full Width).

**Total Dedicated Lanes Required:** 8 + 16 + 16 = **40 Lanes**.

### The Consumer Trap (LGA 1700 / AM5)
*   **Available Lanes:** Intel Core i9-14900K provides **20 Lanes** total.
    *   x16 for GPU.
    *   x4 for boot drive.
*   **The Deficit:** We need 40. We have 20.
*   **The "Hack" (PCH Bottleneck):** The motherboard chipset (Z790) acts as a switch. It takes 8 virtual lanes from the devices and funnels them through a generic **DMI Link** (x8 equivalent) to the CPU.
*   **Result:** When the GPU is training (saturating memory) and the NIC is ingesting market data (saturating network), they **collide** at the DMI bottleneck. The NIC buffers fill up, packets are dropped.
    *   *Packet Loss in TCP:* Retransmission latency (200ms+).
    *   *Packet Loss in UDP (Market Data):* **Data is lost forever.** The bot trades on stale prices.

### The Enterprise Solution (SP5 / LGA 4677)
*   **Available Lanes:** AMD EPYC 9004 provides **128 Lanes**.
    *   GPU: x16 (Direct to CPU).
    *   NIC: x16 (Direct to CPU).
    *   NVMe: x16 (Direct to CPU).
    *   *Remaining:* 80 Lanes free.
*   **Result:** Zero contention. Deterministic I/O. Every device has a private highway to the CPU die.

---

# 2. Memory Architecture: Bandwidth is the Metric by which we Live

For Large Language Models (LLMs), **FLOPS (Floating Point Operations)** are irrelevant. The bottleneck is strictly **Memory Bandwidth**.

## 2.1 The "Token per Second" Formula
We can mathematically predict the maximum performance of an AI model on a specific hardware config.
The formula for memory-bound inference is:

$$ T_{sec} = \frac{BW_{mem}}{M_{size}} $$

Where:
*   $T_{sec}$ = Tokens per second.
*   $BW_{mem}$ = Effective Memory Bandwidth (GB/s).
*   $M_{size}$ = Model Size (GB).

**Scenario: Llama-3-70B (Quantized to 4-bit)**
*   Size: ~40 GB.

**Consumer Hardware (Dual Channel DDR5-6000):**
*   Bandwidth: ~96 GB/s (Theoretical).
*   Real Bandwidth (Efficiency ~70%): ~67 GB/s.
*   $T_{sec} = 67 / 40 = 1.67$ Tokens/sec.
*   *Verdict:* **Unusable** for real-time chat. The user waits 1 second per word.

**Enterprise Hardware (Octa Channel DDR4-3200 - EPYC Milan):**
*   Bandwidth: ~204 GB/s (Theoretical).
*   Real Bandwidth (Efficiency ~75%): ~153 GB/s.
*   $T_{sec} = 153 / 40 = 3.8$ Tokens/sec.
*   *Improvement:* **2.2x speedup** just from memory channels, even with "slower" RAM Hz.

**HEDT Hardware (Threadripper Pro - Octa Channel DDR5-5200):**
*   Bandwidth: ~300+ GB/s.
*   $T_{sec} = 7.5+$ Tokens/sec.

**Guidance:** Do not look at RAM "Speed" (MHz). Look at **Channel Width**. An 8-Channel DDR4 server board will usually crush a 2-Channel DDR5 gaming board for LLM inference that doesn't fit in VRAM.

## 2.2 ECC: The Insurance Policy
We previously discussed ECC. Let's define the failure rate using real-world data from Google's datacenter study.
*   *Failures:* ~25,000 to 70,000 errors per Billion device hours per Mbit.
*   *Translation:* On a 128GB RAM system running 24/7, you can statistically expect **one single-bit error every 3-6 months**.
*   *The "Silent Killer":*
    *   If a bit flips in a video frame: A pixel changes color. (Harmless).
    *   If a bit flips in a ZFS pointer: The checksum fails, and the file is marked corrupt. (Annoying).
    *   If a bit flips in the Python Process Memory (Model Weights): The Neural Net outputs "Buy" instead of "Sell". **(Catastrophic).**
    *   If a bit flips in the Linux Kernel Instruction Pointer: **Kernel Panic.**
*   **Mandate:** ECC is not optional for GOLIATH.

---

# 3. Storage Physics: The Endurance Equation

Systems Engineers often ignore SSD datasheet "fine print". We will not.

## 3.1 Write Amplification Factor (WAF)
When Proxmox writes 4KB of data, the SSD completely erases a much larger 4MB "Block" and rewrites it. This ratio (Actual Flash Writes / Host Writes) is the WAF.

| Drive Type | Controller Logic | WAF (Sequential) | WAF (Random 4k) |
| :--- | :--- | :--- | :--- |
| **Consumer (Samsung 990)** | Aggressive GC for benchmarks | ~1.1 | **~4.5 - 10.0** |
| **Enterprise (Micron 7450)** | Steady-state consistency | ~1.1 | **~1.5 - 2.5** |

**The Math of Failure:**
*   Drive: 2TB Samsung 980 Pro (1200 TBW Rated).
*   Workload: 100 GB/day (Database syncs + Logs + Swap).
*   Actual Flash Burn: $100 \times 4.5 (WAF) = 450$ GB/day.
*   Life Expectancy: $1200 TB / 0.45 TB/day = 2666$ days.
*   *The Catch:* This assumes the drive stays empty. If the drive is 80% full, the controller has less space to shuffle data, and WAF spikes to **20x**.
*   **Result:** A consumer drive in a full ZFS pool can die in **6-9 months**.

## 3.2 Power Loss Protection (PLP) Capacitor Physics
Enterprise SSDs (e.g., Micron 7450 / Intel D7) have a visible row of yellow tantalum capacitors on the PCB.
*   **Function:** On power loss, they provide voltage for ~20ms.
*   **Why it matters for Speed:**
    *   *Without PLP:* The SSD Firmware *knows* it has no backup. If the OS sends a `SYNC` command (database commit), the SSD forces the data all the way to the slow NAND flash before sending "OK". **Latency: 500us.**
    *   *With PLP:* The SSD Firmware knows the DRAM cache is safe. It writes to the fast DRAM, sends "OK" immediately, and lazily writes to NAND later. **Latency: 30us.**
*   **Real World Impact:** A PostgreSQL database on a PLP drive is **10x-15x faster** on commits than on a consumer drive, even if the "Sequential Read" speed is lower.

---

# 4. CPU Architecture: The Silicon Choice

When we select a CPU for GOLIATH, we are selecting a **Memory Controller** first, and a Compute Engine second.

## 4.1 AMD EPYC (The Throughput King)
*   **Architecture:** Zen 3 (Milan) / Zen 4 (Genoa).
*   **The "Chiplet" Design:**
    *   *Pros:* Massive L3 Cache (up to 768MB per socket for Milan-X). Python execution scales linearly with L3 cache size due to reduced RAM fetches.
    *   *Cons:* Inter-Chiplet Latency. Moving data between `CCX0` and `CCX7` costs ~100ns.
*   **The Recommendation:** **EPYC 7443P (24 Cores / 48 Threads)**.
    *   *Base Clock:* 2.85 GHz.
    *   *Boost Clock:* 4.0 GHz.
    *   *L3 Cache:* 128 MB.
    *   *TDP:* 200W.
    *   *Value:* Only requires 4 memory channels populated to boot, but 8 for full bandwidth.
    *   *Use Case:* Perfect for parallelized backtesting (Python `multiprocessing`) and high-throughput ingestion.

## 4.2 Intel Xeon Scalable (The Latency King)
*   **Architecture:** Ice Lake (3rd Gen) / Sapphire Rapids (4th Gen).
*   **The "Mesh" Design:**
    *   *Pros:* Deterministic latency. Any core can access any cache slice with consistent cost.
    *   *AVX-512:* A massive accelerator for linear algebra (NumPy/Pandas). Note that standard "AVX2" operates on 256-bit registers; AVX-512 doubles this per clock cycle.
*   **The Recommendation:** **Xeon Gold 6330 (28 Cores / 56 Threads)**.
    *   *Base Clock:* 2.0 GHz.
    *   *Boost Clock:* 3.1 GHz.
    *   *L3 Cache:* 42 MB.
    *   *Use Case:* Better for HFT-style execution logic where latency consistency > raw throughput.

## 4.3 Why not Threadripper (HEDT)?
Threadripper occupies an awkward middle ground.
*   *TR 5000 WX:* Based on Milan (Zen 3).
*   *The Trap:* Many "Workstation" motherboards (WRX80) lack proper **IPMI/BMC** (Baseboard Management Controller) for remote management.
    *   *Scenario:* The kernel panics at 3 AM.
    *   *Server:* You log into the IPMI (HTML5 KV), reboot, and view the error logs.
    *   *Workstation:* You drive to the office to press the reset button.
*   *Verdict:* **Avoid.**

---

# 5. The "HCL From Hell": Motherboard VRM Analysis

The motherboard is the power delivery system. For AI training, the CPU + GPU load can pull **1500W+ continuously**.

## 5.1 VRM Phases & Transient Response
A typical 24-core EPYC idles at 50W. When a backtest starts, it dumps a 300A current demand on the VRMs in <1ms.
*   **Weak VRM (Consumer):** Voltage sags (Vdroop). The CPU crashes or throttles.
*   **Strong VRM (Server - Supermicro H12SSL-i):**
    *   *Phases:* 6+2 Digital Multi-Phase.
    *   *Capacitors:* Japanese Solid Polymer (105°C rated).
    *   *Heatsinks:* Finned copper, designed for server airflow (high static pressure).
*   **The Risk:** A consumer board (ASRock Rack Romed8U) might have excellent features but weaker VRMs. If you run AVX-512 code 24/7, the MOSFETs will overheat and fail.

## 5.2 The PCIe Slot Layout
Physical slot placement matters for airflow.
*   **Issue:** Double-width GPUs (RTX 3090/4090) cover adjacent PCIe slots.
*   **Requirement:** You need **At least 3-slot spacing** between x16 slots to fit multiple consumer GPUs.
*   **Server Chassis:** Often designed for "Passive" GPU cooling (A100). Consumer GPUs are "Active" (blowers). Ensure the chassis has massive intake fans (Noctua Industrial 3000 RPM) to feed the GPUs.

---

# 6. GPU Architectures: The AI Accelerator

## 6.1 Consumer (RTX 3090 / 4090)
*   **VRAM:** 24GB GDDR6X.
*   **Bandwidth:** ~1 TB/s.
*   **Limitations:**
    *   **No SR-IOV.** You cannot slice it.
    *   **P2P Transfer:** Peer-to-Peer DMA (GPU-to-GPU) over PCIe is often disabled or slow on consumer chipsets.
    *   **Longevity:** Not designed for 24/7 duty cycle. VRAM thermal pads often degrade after 6 months of training usage.

## 6.2 Enterprise (A6000 Ada / L40S)
*   **VRAM:** 48GB GDDR6.
*   **MIG (Multi-Instance GPU):** Hardware partitioning of compute units.
    *   *Example:* Split one A6000 into 4x 12GB slices.
        *   Slice 1: Brain VM (Inference).
        *   Slice 2: Dev VM (Jupyter Notebooks).
        *   Slice 3: CI/CD Runner (Unit Tests).
        *   Slice 4: Transcoding VM (Video).
*   **Cost Efficiency:** While expensive ($6k+), a single card replaces 4x consumer cards and saves 3 PCIe slots.

---

# 7. Network Fabric: The Nervous System

## 7.1 Latency vs Bandwidth
*   **1GbE:** ~1000us latency under load.
*   **10GbE (SFP+):** ~100us latency.
*   **25GbE (SFP28):** ~10us latency (with RDMA).

## 7.2 RDMA (Remote Direct Memory Access)
For multi-node clustering (Ceph), standard TCP/IP uses too much CPU.
*   **RoCE v2:** Allows NICs to write directly to each other's RAM.
*   *Requirement:* **Mellanox ConnectX-4 Lx** or newer.
*   *Switch Support:* Requires DCB (Data Center Bridging) and PFC (Priority Flow Control) on the switch (e.g., MikroTik CRS305).

**Recommendation:** Stick to **10GbE SFP+ (Intel X520-DA2)** for single-node setups. It is bulletproof, cheap ($30), and driverless on Linux.

---

# 8. GOLIATH Reference Build (BOM)
Based on the physics above, here is the approved Bill of Materials.

| component | Recommendation | Alternatives | Reason |
| :--- | :--- | :--- | :--- |
| **CPU** | **AMD EPYC 7443P** (24c/48t) | EPYC 7543P, Xeon Gold 6330 | Balance of High Frequency (4GHz) and Lane Count (128). |
| **Motherboard** | **Supermicro H12SSL-i** | AsRock Rack ROMED8-2T | Proven VRM reliability, standard ATX form factor. |
| **RAM** | **8x 32GB DDR4-3200 ECC RDIMM** (256GB) | Micron/Samsung | Fully populates 8 channels for max memory bandwidth (204 GB/s). |
| **HBA (Boot)** | **2x Micron 7450 PRO 960GB** (M.2) | Intel D7-P5510 | Enterprise PLP for ZFS mirror logs. |
| **Storage (Data)** | **4x Micron 9300 MAX 6.4TB** (U.2) | Intel Optane P5800X | High endurance (3DWPD) for Parquet/Tick data. |
| **GPU** | **1x NVIDIA RTX 3090** (24GB) | RTX 4090, A6000 | Best value per GB VRAM. Requires 3-slot spacing. |
| **NIC** | **Intel X520-DA2** (Dual SFP+) | Mellanox ConnectX-3 | Driver stability in Linux Kernel 6.5+. |
| **PSU** | **Seasonic Prime TX-1600** | EVGA SuperNOVA 1600 | 12 years warranty. Titanium efficiency. |

*(End of Module 01)*
