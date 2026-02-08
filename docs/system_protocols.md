# System Protocol Definitions (v4.0.0)

## 1. Inter-Process Communication (IPC)

### 1.1 Simple Binary Encoding (SBE)
**Transport:** ZeroMQ (PUB/SUB) / UDP Multicast
**Endianness:** Little Endian
**Schema Path:** `schemas/sbe/market_data.xml`

#### Message Header (8 Bytes)
| Offset | Field | Type | Description |
| :--- | :--- | :--- | :--- |
| 0 | `blockLength` | `uint16` | Root block size (e.g., 42 bytes) |
| 2 | `templateId` | `uint16` | Message Type ID (e.g., 1=Tick, 2=Trade) |
| 4 | `schemaId` | `uint16` | Protocol Version ID |
| 6 | `version` | `uint16` | Schema Version |

#### Payload: Market Tick (Template ID: 1)
| Offset | Field | Type | SBE Type | Description |
| :--- | :--- | :--- | :--- | :--- |
| 0 | `timestamp` | `int64` | `u64` | Unix Nanoseconds (UTC) |
| 8 | `symbol_id` | `int32` | `i32` | Mapped Integer ID |
| 12 | `bid_price` | `int64` | `i64` | Price * 1e9 |
| 20 | `ask_price` | `int64` | `i64` | Price * 1e9 |
| 28 | `bid_sz` | `int64` | `i64` | Quantity * 1e9 |
| 36 | `ask_sz` | `int64` | `i64` | Quantity * 1e9 |
| 44 | `flags` | `uint8` | `u8` | Bitmask (0x1=Realtime, 0x2=Replay) |

---

## 2. Historical Data Storage

### 2.1 Apache Parquet Schema
**Compression:** ZSTD (Level 3)
**Row Group Size:** 128MB
**Partitioning:** `date={YYYY-MM-DD}/symbol={SYMBOL}`

#### Column Definitions
```protobuf
message MarketTick {
  required int64 timestamp (TIMESTAMP_NANOS);
  required int64 bid (DECIMAL, precision=18, scale=9);
  required int64 ask (DECIMAL, precision=18, scale=9);
  required int64 volume (INT64);
  optional binary flags (BYTE_ARRAY);
}
```

### 2.2 Write Path (Go -> Disk)
*   **Buffer:** 64KB Ring Buffer in RAM.
*   **Flush Policy:** Every 1s OR when buffer > 75% full.
*   **Sync:** `fdatasync()` called only on flush to minimize I/O wait.

---

## 3. Kernel Isolation Protocols

### 3.1 Cgroups v2 Configuration
Resource limits are enforced via `systemd` slice units.

**Gateway Slice (`goliath-gateway.slice`)**
```ini
[Slice]
CPUQuota=200%             # Max 2 Cores
MemoryMax=4G              # Hard Limit
MemorySwapMax=0           # Disable Swap
TasksMax=10000            # Goroutine limit
```

**Engine Slice (`goliath-engine.slice`)**
```ini
[Slice]
AllowedCPUs=2,3           # CPU Pinning (Isolation)
MemoryHigh=8G             # Soft Limit
OOMScoreAdjust=-1000      # Prevent Kill (Critical)
```

### 3.2 System Calls (Seccomp BPF)
Whitelist of allowed syscalls for the Gateway process:
*   `epoll_wait`, `epoll_ctl` (Networking)
*   `read`, `write`, `close` (I/O)
*   `futex` (Go Runtime)
*   *Blocked:* `fork`, `execve` (Prevents RCE escalation)

---

## 4. Cryptographic Standards

### 4.1 HMAC Signing (Inbound)
*   **Algorithm:** HMAC-SHA256
*   **Header:** `X-TradingView-Signature`
*   **Verification:** Constant-time comparison `hmac.Equal()` to prevent timing attacks.

### 4.2 Key Management
*   **Internal Keys:** Ed25519 (High speed signing).
*   **Storage:** AWS KMS / HashiCorp Vault (Production) or `tmpfs` (Dev RAM disk). Keys never touch the persistent disk.
