# 🛡️ GOLIATH System Report v3.0

> **Generated:** 2026-02-07 20:30:08  
> **Platform:** Windows 10  
> **Duration:** 15.1s  
> **Health Score:** 100%

![Status](https://img.shields.io/badge/Status-ALL%20PASS-brightgreen?style=for-the-badge)

## Summary

| Component | Tests | Passed | Status |
|-----------|-------|--------|--------|
| INFRA | 3 | 3 | ✅ |
| RUST | 5 | 5 | ✅ |
| GO | 5 | 5 | ✅ |
| PYTHON | 5 | 5 | ✅ |
| SIGNALS | 5 | 5 | ✅ |

## ✅ All Systems Operational

No issues detected. System ready for trading.

## 📋 Test Details

<details><summary>✅ <b>INFRA</b>: Disk Space (0.00s)</summary>

```
469.8 GB available
```
</details>

<details><summary>✅ <b>INFRA</b>: Data Storage (0.00s)</summary>

```
8 parquet files (25.9 MB)
```
</details>

<details><summary>✅ <b>INFRA</b>: Internet (0.10s)</summary>

```
Connected
```
</details>

<details><summary>✅ <b>RUST</b>: Syntax Check (0.49s)</summary>

```

--- STDERR ---
    Checking engine v0.1.0 (E:\Progetti\BOT_TRADING\engine)
warning: field `updated_at` is never read
   --> src\domain\order_typestate.rs:112:5
    |
108 | pub struct Order<S> {
    |            ----- field in this struct
...
112 |     updated_at: u64,
    |     ^^^^^^^^^^
    |
    = note: `Order` has derived impls for the traits `Debug` and `Clone`, but these are intentionally ignored during dead code analysis
    = note: `#[warn(dead_code)]` (part of `#[warn(unused)]`) on by default

warning: `engine` (lib) generated 1 warning
warning: unused import: `std::path::Path`
 --> src\bin\sbe_consumer.rs:3:5
  |
3 | use std::path::Path;
  |     ^^^^^^^^^^^^^^^
  |
  = note: `#[warn(unused_imports)]` (part of `#[warn(unused)]`) on by default

warning: unused import: `Side`
 --> src\bin\sbe_consumer.rs:5:39
  |
5 | use engine::domain::order_typestate::{Side};
  |                                       ^^^^

warning: unused import: `std::path::Path`
 --> src\bin\backtester.rs:2:5
  |
2 | use std::path::Path;
  |     ^^^^^^^^^^^^^^^
  |
  = note: `#[warn(unused_imports)]` (part of `#[warn(unused)]`) on by default

warning: constant `BLOCK_LENGTH` is never used
  --> src\bin\sbe_consumer.rs:11:7
   |
11 | const BLOCK_LENGTH: usize = 33; // 8+8+1+8+8
   |       ^^^^^^^^^^^^
   |
   = note: `#[warn(dead_code)]` (part of `#[warn(unused)]`) on by default

warning: fields `schema_id` and `version` are never read
  --> src\bin\sbe_consumer.rs:17:5
   |
14 | struct SbeHeader {
   |        --------- fields in this struct
...
17 |     schema_id: u16,
   |     ^^^^^^^^^
18 |     version: u16,
   |     ^^^^^^^
   |
   = note: `SbeHeader` has a derived impl for the trait `Debug`, but this is intentionally ignored during dead code analysis

warning: struct `OrderResult` is never constructed
  --> src\bin\sbe_consumer.rs:22:8
   |
22 | struct OrderResult {
   |        ^^^^^^^^^^^

warning: `engine` (bin "sbe_consumer") generated 5 warnings (run `cargo fix --bin "sbe_consumer" -p engine` to apply 2 suggestions)
warning: `engine` (bin "backtester") generated 1 warning (run `cargo fix --bin "backtester" -p engine` to apply 1 suggestion)
    Finished `dev` profile [unoptimized + debuginfo] target(s) in 0.42s

```
</details>

<details><summary>✅ <b>RUST</b>: Unit Tests (0.62s)</summary>

```

running 9 tests
test domain::order_typestate::tests::test_order_lifecycle ... ok
test domain::specification::tests::test_composite_specification ... ok
test domain::specification::tests::test_rule_engine ... ok
test domain::value_objects::tests::test_currency_validation ... ok
test domain::value_objects::tests::test_price_arithmetic ... ok
test domain::value_objects::tests::test_price_creation ... ok
test domain::value_objects::tests::test_price_truncation ... ok
test domain::value_objects::tests::test_quantity_value ... ok
test domain::value_objects::tests::test_trading_pair ... ok

test result: ok. 9 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s


--- STDERR ---
   Compiling engine v0.1.0 (E:\Progetti\BOT_TRADING\engine)
warning: field `updated_at` is never read
   --> src\domain\order_typestate.rs:112:5
    |
108 | pub struct Order<S> {
    |            ----- field in this struct
...
112 |     updated_at: u64,
    |     ^^^^^^^^^^
    |
    = note: `Order` has derived impls for the traits `Debug` and `Clone`, but these are intentionally ignored during dead code analysis
    = note: `#[warn(dead_code)]` (part of `#[warn(unused)]`) on by default

warning: `engine` (lib test) generated 1 warning
    Finished `test` profile [unoptimized + debuginfo] target(s) in 0.52s
     Running unittests src\lib.rs (target\debug\deps\engine-e8e65c89a81e165d.exe)

```
</details>

<details><summary>✅ <b>RUST</b>: Property Tests (1.46s)</summary>

```

running 2 tests
test test_price_construction ... ok
test test_quantity_addition ... ok

test result: ok. 2 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s


--- STDERR ---
   Compiling engine v0.1.0 (E:\Progetti\BOT_TRADING\engine)
warning: field `updated_at` is never read
   --> src\domain\order_typestate.rs:112:5
    |
108 | pub struct Order<S> {
    |            ----- field in this struct
...
112 |     updated_at: u64,
    |     ^^^^^^^^^^
    |
    = note: `Order` has derived impls for the traits `Debug` and `Clone`, but these are intentionally ignored during dead code analysis
    = note: `#[warn(dead_code)]` (part of `#[warn(unused)]`) on by default

warning: `engine` (lib) generated 1 warning
warning: unused import: `std::path::Path`
 --> src\bin\backtester.rs:2:5
  |
2 | use std::path::Path;
  |     ^^^^^^^^^^^^^^^
  |
  = note: `#[warn(unused_imports)]` (part of `#[warn(unused)]`) on by default

warning: unused import: `std::path::Path`
 --> src\bin\sbe_consumer.rs:3:5
  |
3 | use std::path::Path;
  |     ^^^^^^^^^^^^^^^
  |
  = note: `#[warn(unused_imports)]` (part of `#[warn(unused)]`) on by default

warning: unused import: `Side`
 --> src\bin\sbe_consumer.rs:5:39
  |
5 | use engine::domain::order_typestate::{Side};
  |                                       ^^^^

warning: unused import: `std::str::FromStr`
 --> tests\proptest_suite.rs:2:5
  |
2 | use std::str::FromStr;
  |     ^^^^^^^^^^^^^^^^^
  |
  = note: `#[warn(unused_imports)]` (part of `#[warn(unused)]`) on by default

warning: unused import: `Currency`
 --> tests\proptest_suite.rs:5:54
  |
5 | use engine::domain::value_objects::{Price, Quantity, Currency};
  |                                                      ^^^^^^^^

warning: constant `BLOCK_LENGTH` is never used
  --> src\bin\sbe_consumer.rs:11:7
   |
11 | const BLOCK_LENGTH: usize = 33; // 8+8+1+8+8
   |       ^^^^^^^^^^^^
   |
   = note: `#[warn(dead_code)]` (part of `#[warn(unused)]`) on by default

warning: fields `schema_id` and `version` are never read
  --> src\bin\sbe_consumer.rs:17:5
   |
14 | struct SbeHeader {
   |        --------- fields in this struct
...
17 |     schema_id: u16,
   |     ^^^^^^^^^
18 |     version: u16,
   |     ^^^^^^^
   |
   = note: `SbeHeader` has a derived impl for the trait `Debug`, but this is intentionally ignored during dead code analysis

warning: struct `OrderResult` is never constructed
  --> src\bin\sbe_consumer.rs:22:8
   |
22 | struct OrderResult {
   |        ^^^^^^^^^^^

warning: `engine` (bin "sbe_consumer") generated 5 warnings (run `cargo fix --bin "sbe_consumer" -p engine` to apply 2 suggestions)
warning: `engine` (test "proptest_suite") generated 2 warnings (run `cargo fix --test "proptest_suite" -p engine` to apply 2 suggestions)
warning: `engine` (bin "backtester") generated 1 warning (run `cargo fix --bin "backtester" -p engine` to apply 1 suggestion)
    Finished `test` profile [unoptimized + debuginfo] target(s) in 1.34s
     Running tes
```
</details>

<details><summary>✅ <b>RUST</b>: Security Audit (0.46s)</summary>

```

running 1 test
test test_audit_integrity ... ok

test result: ok. 1 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.02s


--- STDERR ---
warning: field `updated_at` is never read
   --> src\domain\order_typestate.rs:112:5
    |
108 | pub struct Order<S> {
    |            ----- field in this struct
...
112 |     updated_at: u64,
    |     ^^^^^^^^^^
    |
    = note: `Order` has derived impls for the traits `Debug` and `Clone`, but these are intentionally ignored during dead code analysis
    = note: `#[warn(dead_code)]` (part of `#[warn(unused)]`) on by default

warning: `engine` (lib) generated 1 warning
   Compiling engine v0.1.0 (E:\Progetti\BOT_TRADING\engine)
warning: unused import: `std::path::Path`
 --> src\bin\backtester.rs:2:5
  |
2 | use std::path::Path;
  |     ^^^^^^^^^^^^^^^
  |
  = note: `#[warn(unused_imports)]` (part of `#[warn(unused)]`) on by default

warning: unused import: `std::path::Path`
 --> src\bin\sbe_consumer.rs:3:5
  |
3 | use std::path::Path;
  |     ^^^^^^^^^^^^^^^
  |
  = note: `#[warn(unused_imports)]` (part of `#[warn(unused)]`) on by default

warning: unused import: `Side`
 --> src\bin\sbe_consumer.rs:5:39
  |
5 | use engine::domain::order_typestate::{Side};
  |                                       ^^^^

warning: constant `BLOCK_LENGTH` is never used
  --> src\bin\sbe_consumer.rs:11:7
   |
11 | const BLOCK_LENGTH: usize = 33; // 8+8+1+8+8
   |       ^^^^^^^^^^^^
   |
   = note: `#[warn(dead_code)]` (part of `#[warn(unused)]`) on by default

warning: fields `schema_id` and `version` are never read
  --> src\bin\sbe_consumer.rs:17:5
   |
14 | struct SbeHeader {
   |        --------- fields in this struct
...
17 |     schema_id: u16,
   |     ^^^^^^^^^
18 |     version: u16,
   |     ^^^^^^^
   |
   = note: `SbeHeader` has a derived impl for the trait `Debug`, but this is intentionally ignored during dead code analysis

warning: struct `OrderResult` is never constructed
  --> src\bin\sbe_consumer.rs:22:8
   |
22 | struct OrderResult {
   |        ^^^^^^^^^^^

warning: `engine` (bin "backtester") generated 1 warning (run `cargo fix --bin "backtester" -p engine` to apply 1 suggestion)
warning: `engine` (bin "sbe_consumer") generated 5 warnings (run `cargo fix --bin "sbe_consumer" -p engine` to apply 2 suggestions)
    Finished `test` profile [unoptimized + debuginfo] target(s) in 0.35s
     Running tests\audit_tamper_test.rs (target\debug\deps\audit_tamper_test-d2d30383137b66d1.exe)

```
</details>

<details><summary>✅ <b>RUST</b>: Release Build (1.46s)</summary>

```

--- STDERR ---
   Compiling engine v0.1.0 (E:\Progetti\BOT_TRADING\engine)
warning: field `updated_at` is never read
   --> src\domain\order_typestate.rs:112:5
    |
108 | pub struct Order<S> {
    |            ----- field in this struct
...
112 |     updated_at: u64,
    |     ^^^^^^^^^^
    |
    = note: `Order` has derived impls for the traits `Debug` and `Clone`, but these are intentionally ignored during dead code analysis
    = note: `#[warn(dead_code)]` (part of `#[warn(unused)]`) on by default

warning: `engine` (lib) generated 1 warning
warning: unused import: `std::path::Path`
 --> src\bin\backtester.rs:2:5
  |
2 | use std::path::Path;
  |     ^^^^^^^^^^^^^^^
  |
  = note: `#[warn(unused_imports)]` (part of `#[warn(unused)]`) on by default

warning: `engine` (bin "backtester") generated 1 warning (run `cargo fix --bin "backtester" -p engine` to apply 1 suggestion)
    Finished `release` profile [optimized] target(s) in 1.40s

```
</details>

<details><summary>✅ <b>GO</b>: Dependencies (0.61s)</summary>

```
all modules verified

```
</details>

<details><summary>✅ <b>GO</b>: Static Analysis (0.52s)</summary>

```

```
</details>

<details><summary>✅ <b>GO</b>: RBAC Layer (0.20s)</summary>

```
=== RUN   TestRBAC
=== RUN   TestRBAC/Admin_accessing_Admin_route
=== RUN   TestRBAC/Trader_trying_to_access_Admin_route
=== RUN   TestRBAC/Trader_accessing_Trader_route
=== RUN   TestRBAC/Auditor_accessing_Viewer_route
=== RUN   TestRBAC/Trader_accessing_Auditor_route_(SoD_check)
--- PASS: TestRBAC (0.00s)
    --- PASS: TestRBAC/Admin_accessing_Admin_route (0.00s)
    --- PASS: TestRBAC/Trader_trying_to_access_Admin_route (0.00s)
    --- PASS: TestRBAC/Trader_accessing_Trader_route (0.00s)
    --- PASS: TestRBAC/Auditor_accessing_Viewer_route (0.00s)
    --- PASS: TestRBAC/Trader_accessing_Auditor_route_(SoD_check) (0.00s)
=== RUN   TestRBAC_NoRole
--- PASS: TestRBAC_NoRole (0.00s)
PASS
ok  	github.com/economic-trading/gateway/internal/middleware	(cached)

```
</details>

<details><summary>✅ <b>GO</b>: Pipeline (0.27s)</summary>

```
=== RUN   TestRecorderLifecycle
[Recorder] Rotated to ticks_20260207_024331.parquet
--- PASS: TestRecorderLifecycle (0.50s)
PASS
ok  	github.com/economic-trading/gateway/internal/pipeline	(cached)

```
</details>

<details><summary>✅ <b>GO</b>: MT5 Bridge (0.23s)</summary>

```
=== RUN   TestBridgeEndToEnd
MT5 Bridge listening on :5555
New MT5 Connection: [::1]:60836
[EXECUTION] Order #123 B 1.500000 @ 45000.000000
    listener_test.go:107: Message sent successfully. Check console output for '[Received]' log.
--- PASS: TestBridgeEndToEnd (0.61s)
PASS
ok  	github.com/economic-trading/gateway/internal/connector/mt5	(cached)

```
</details>

<details><summary>✅ <b>PYTHON</b>: Interpreter (0.02s)</summary>

```
Python 3.10.11

```
</details>

<details><summary>✅ <b>PYTHON</b>: Core Dependencies (2.10s)</summary>

```
Core deps OK

```
</details>

<details><summary>✅ <b>PYTHON</b>: UI Dependencies (0.16s)</summary>

```
UI deps OK

```
</details>

<details><summary>✅ <b>PYTHON</b>: ML Training (2.62s)</summary>

```

--- STDERR ---
2026-02-07 20:30:02.860 | INFO     | __main__:train_dummy:28 - Generating synthetic sine wave data...
2026-02-07 20:30:03.403 | INFO     | __main__:train_dummy:42 - Starting dummy training for 10 epochs...
2026-02-07 20:30:03.585 | INFO     | __main__:train_dummy:54 - Epoch 1/10, Loss: 0.499703
2026-02-07 20:30:03.661 | INFO     | __main__:train_dummy:54 - Epoch 2/10, Loss: 0.204705
2026-02-07 20:30:03.745 | INFO     | __main__:train_dummy:54 - Epoch 3/10, Loss: 0.043715
2026-02-07 20:30:03.830 | INFO     | __main__:train_dummy:54 - Epoch 4/10, Loss: 0.057135
2026-02-07 20:30:03.913 | INFO     | __main__:train_dummy:54 - Epoch 5/10, Loss: 0.071198
2026-02-07 20:30:03.988 | INFO     | __main__:train_dummy:54 - Epoch 6/10, Loss: 0.048415
2026-02-07 20:30:04.070 | INFO     | __main__:train_dummy:54 - Epoch 7/10, Loss: 0.027294
2026-02-07 20:30:04.151 | INFO     | __main__:train_dummy:54 - Epoch 8/10, Loss: 0.054911
2026-02-07 20:30:04.229 | INFO     | __main__:train_dummy:54 - Epoch 9/10, Loss: 0.034281
2026-02-07 20:30:04.311 | INFO     | __main__:train_dummy:54 - Epoch 10/10, Loss: 0.031405
2026-02-07 20:30:04.311 | SUCCESS  | __main__:train_dummy:59 - Dummy training SUCCESS. Final Loss: 0.031405

```
</details>

<details><summary>✅ <b>PYTHON</b>: Phase 2 Modules (1.10s)</summary>

```
Phase 2 OK

```
</details>

<details><summary>✅ <b>SIGNALS</b>: Channel Detection (0.54s)</summary>

```
Channels OK

```
</details>

<details><summary>✅ <b>SIGNALS</b>: Signal Aggregator (0.60s)</summary>

```
Signal Processor OK

```
</details>

<details><summary>✅ <b>SIGNALS</b>: Indicator Optimizer (0.53s)</summary>

```
Optimizer OK

```
</details>

<details><summary>✅ <b>SIGNALS</b>: Neural Decision (0.54s)</summary>

```
Neural Decision OK

```
</details>

<details><summary>✅ <b>SIGNALS</b>: Module Exports (0.02s)</summary>

```

```
</details>

