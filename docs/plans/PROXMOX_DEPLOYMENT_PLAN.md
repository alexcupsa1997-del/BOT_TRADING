# GOLIATH — Full Project Audit + Proxmox Deployment + CI/CD Plan

## Context

All 6 FUSION_PLAN phases are implemented (424 tests passing). The system has the full ML/quant pipeline working: indicators, patterns, signals, regime detection, strategy routing, ML ensemble, fallback decisions, risk management, paper trading, Monte Carlo, and notifications. **However**, the bot cannot yet operate end-to-end because:

1. The Gateway's `/api/signal/` endpoint returns hardcoded `HOLD` (line 60 of `gateway/cmd/gateway/main.go` says `TODO: Connect to Python Brain`)
2. The Analysis container runs a sleep loop (line 39 of `docker-compose.yml`) instead of an actual service
3. No CI/CD exists — no `.github/workflows`, no Jenkinsfile, nothing
4. 79 modified + 73 untracked files are uncommitted

The user wants to: (a) see the bot work before Proxmox, (b) deploy everything to their self-hosted Proxmox server, (c) have CI/CD for continued development after migration.

---

## 1. Project Status Assessment

### Development Progress

| Phase | Description | Status | Tests | LOC |
|-------|------------|--------|-------|-----|
| Fase 1 | Exchange connectors + WebSocket | DONE | ~40 | ~830 |
| Fase 2 | BacktestEngine + TripleBarrier + WalkForward | DONE | ~80 | ~1800 |
| Fase 3 | Model Zoo + Ensemble + HyperOpt | DONE | ~90 | ~2200 |
| Fase 4 | MarketRegime + StrategyRouter + SmartMoney | DONE | ~80 | ~1800 |
| Fase 5 | Monte Carlo + Notifier | DONE | 40 | ~500 |
| Fase 6 | Paper Trading + Integration | DONE | 43 | ~1050 |
| **Total** | | **6/6 DONE** | **424** | **~8500** |

### What Works
- Full analysis pipeline: OHLCV → 100+ indicators → patterns → signals → regime → strategy → ML decision
- 4-tier fallback engine (COPER → ML_MODEL → SIGNALS → CONSERVATIVE)
- Confidence gating (maturity + drift + silence)
- Paper trading harness with circuit breaker, failsafe, TripleBarrier exits
- Multi-channel notifications (Telegram/Discord)
- Monte Carlo risk simulation
- All 424 tests green in 4.56s

### What Does NOT Work Yet (Critical Gaps)

**Gap 1 — Gateway ↔ Analysis bridge** (`gateway/cmd/gateway/main.go:60`)
The Go gateway has a TODO stub returning `{"direction":"HOLD","confidence":0}`. The Analysis container needs an HTTP server so the Gateway can proxy signals. Without this, GoliathHybrid.mq5 gets no AI signals.

**Gap 2 — Analysis container is a sleep loop** (`docker-compose.yml:39`)
The analysis service runs `time.sleep(3600)` forever. It should run either the paper trading runner or an HTTP signal server (or both).

**Gap 3 — 152 files uncommitted**
79 modified + 73 untracked files. This is the accumulated work from Fases 1-6.

---

## 2. Implementation Plan — 3 Phases

### Phase A: Make the Bot Work End-to-End (Before Proxmox)

This is the "see it working" phase. 4 steps:

#### A.1 — Signal Server in Analysis Container
Create `analysis/src/integration/signal_server.py` (~80 LOC)

A lightweight FastAPI/Flask server exposing:
```
GET /predict/{symbol}?timeframe=H1
→ {"direction":"LONG","confidence":0.82,"stop_loss":49000,"take_profit":52000,"position_size_pct":0.05,"reasoning":"...","source_tier":"ML_MODEL"}
```

Internally calls `TradingOrchestrator.analyze()` with recent OHLCV data (fetched from exchange or from shared Parquet). Runs on `:8000` inside the `trading-net` Docker network.

**Files:**
- `analysis/src/integration/signal_server.py` — NEW (~80 LOC)
- `analysis/requirements.txt` — ADD `fastapi`, `uvicorn`

#### A.2 — Gateway Proxy to Analysis
Modify `gateway/cmd/gateway/main.go` line 60-63: replace the TODO stub with an HTTP call to `http://analysis:8000/predict/{symbol}`.

**Files:**
- `gateway/cmd/gateway/main.go` — MODIFY (~10 LOC changed)

#### A.3 — Fix Analysis Container Command
In `docker-compose.yml`, replace the sleep loop with the signal server + optional paper trading.

**Files:**
- `docker-compose.yml` — MODIFY (replace line 39 command, add healthchecks, add env_file)
- `.env.example` — already has the needed vars

#### A.4 — Commit Everything
Stage and commit all 152 files with a clear commit message documenting Fases 1-6 + signal bridge.

---

### Phase B: Proxmox Infrastructure Setup

#### B.1 — Proxmox Topology

```
PROXMOX HOST (bare metal)
│
├── VM 100: "goliath-docker" (Ubuntu 24.04 LTS)
│   │  8 CPU, 16GB RAM, 60GB disk
│   │  Static IP: 10.0.0.100
│   │  Ports: 8080 (HTTP), 5555 (MT5 TCP)
│   │  GPU passthrough (optional, for training)
│   │
│   ├── [Docker] gateway    (:8080, :5555)
│   ├── [Docker] engine     (internal)
│   ├── [Docker] analysis   (:8000 internal, GPU mapped)
│   └── [Docker] watchdog   (internal)
│
├── VM 101: "goliath-mt5" (Windows 10/11)
│   │  4 CPU, 8GB RAM, 40GB disk
│   │  Static IP: 10.0.0.101
│   │  MT5 terminal + Bridge.mq5 + GoliathHybrid.mq5
│   │  Connects to: 10.0.0.100:5555 (TCP), 10.0.0.100:8080 (HTTP)
│
├── LXC 200: "goliath-ci" (Debian 12)
│   │  2 CPU, 4GB RAM, 30GB disk
│   │  Static IP: 10.0.0.200
│   │  Forgejo git server (:3000) + Actions runner
│
└── LXC 201: "goliath-monitor" (Debian 12) [OPTIONAL]
       1 CPU, 2GB RAM, 20GB disk
       Grafana + Loki for log aggregation
```

**Why this layout:**
- Docker host needs a full VM (not LXC) for GPU passthrough and Docker-in-Linux
- Windows VM is mandatory — MT5 only runs on Windows
- CI server is lightweight → LXC saves resources
- All on same `vmbr0` bridge network → services communicate via static IPs

#### B.2 — Storage (ZFS)
- Proxmox on ZFS pool (NVMe/SSD)
- Daily ZFS snapshots for point-in-time recovery of Parquet tick data
- 30-day retention

#### B.3 — GPU (Optional)
The TradingBrain model is ~2.4M params — inference runs fine on CPU (<10ms). GPU only needed for training. If available:
- IOMMU passthrough to VM 100
- NVIDIA Container Toolkit in Docker
- Add `deploy.resources.reservations.devices` to `docker-compose.yml` analysis service

**Recommendation:** Start without GPU. Add later if training on-server is needed.

#### B.4 — MT5 Configuration
Only 2 changes in the MQL5 EAs when migrating:
- `Bridge.mq5` line 16: `InpAddress = "10.0.0.100"` (was `"localhost"`)
- `GoliathHybrid.mq5` line 18-19: `InpGatewayHost = "10.0.0.100"` (was `"localhost"`)

MT5 EAs auto-reconnect, so redeployments of the Docker services don't require MT5 restart.

---

### Phase C: CI/CD Pipeline

#### C.1 — Self-Hosted CI with Forgejo Actions

Forgejo (community fork of Gitea) has built-in Actions using GitHub-Actions-compatible YAML syntax. Single binary, no external services.

Create `.forgejo/workflows/ci.yml`:

```yaml
name: GOLIATH CI/CD

on:
  push:
    branches: [main]

jobs:
  gateway:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-go@v5
        with: { go-version: '1.24' }
      - run: cd gateway && go test -v -race ./...
      - run: cd gateway && CGO_ENABLED=0 go build -o gateway ./cmd/gateway/main.go

  engine:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: dtolnay/rust-toolchain@stable
      - run: cd engine && cargo test --release
      - run: cd engine && cargo build --release --bins

  analysis:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.10' }
      - run: cd analysis && pip install -r requirements.txt
      - run: cd analysis && PYTHONPATH=. pytest tests/ -v --tb=short

  deploy:
    needs: [gateway, engine, analysis]
    runs-on: ubuntu-latest
    steps:
      - uses: appleboy/ssh-action@v1
        with:
          host: 10.0.0.100
          username: goliath
          key: ${{ secrets.DEPLOY_SSH_KEY }}
          script: |
            cd /opt/goliath
            git pull origin main
            docker compose build --parallel
            docker compose up -d --remove-orphans
            sleep 5
            curl -sf http://localhost:8080/health || exit 1
```

#### C.2 — Developer Workflow After Migration

```
Laptop (develop + test locally)
  ↓ git push
Forgejo (LXC 200, runs CI pipeline)
  ↓ if all green
SSH deploy to Docker host (VM 100)
  ↓ docker compose up -d
Services restart with new code
  ↓
MT5 (VM 101) auto-reconnects
```

**Rollback:** `git checkout <previous-sha>` + `docker compose up -d`

#### C.3 — Makefile for Local Development

Create `Makefile` at project root:

```makefile
.PHONY: test-all test-py test-go test-rs up down logs health

test-py:
	cd analysis && PYTHONPATH=. pytest tests/ -v

test-go:
	cd gateway && go test -v ./...

test-rs:
	cd engine && cargo test --release

test-all: test-py test-go test-rs

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f --tail=100

health:
	@curl -sf http://localhost:8080/health && echo " Gateway OK" || echo " Gateway DOWN"
```

---

## 3. Files to Create/Modify

| File | Action | ~LOC | Purpose |
|------|--------|------|---------|
| `analysis/src/integration/signal_server.py` | NEW | 80 | FastAPI signal endpoint for Gateway |
| `analysis/tests/test_signal_server.py` | NEW | 60 | Tests for signal server |
| `gateway/cmd/gateway/main.go` | MODIFY | ~10 | Replace TODO with HTTP proxy to Analysis |
| `docker-compose.yml` | MODIFY | ~20 | Healthchecks, env_file, fix analysis command |
| `.forgejo/workflows/ci.yml` | NEW | 60 | CI/CD pipeline definition |
| `Makefile` | NEW | 30 | Local dev shortcuts |

**Total new code:** ~260 LOC (production + tests + config)

---

## 4. Execution Order

1. **Signal server** (`signal_server.py`) — the critical missing bridge
2. **Gateway proxy** (modify `main.go`) — connect Gateway to Analysis
3. **Docker compose fixes** — healthchecks, real analysis command
4. **Tests** for signal server
5. **Makefile** + CI workflow file
6. **Full regression** (424+ tests)
7. **Commit everything** — clean state for future Proxmox migration

---

## 5. Verification

```bash
# 1. Run all Python tests
cd analysis && PYTHONPATH=. pytest tests/ -v

# 2. Run Go tests
cd gateway && go test -v ./...

# 3. Docker integration test
docker compose up -d --build
sleep 10
curl http://localhost:8080/health              # → "OK"
curl http://localhost:8080/api/signal/BTCUSDT   # → real AI signal (not HOLD stub)

# 4. Paper trading smoke test
docker compose exec analysis python -m src.execution.runner --symbol BTC/USDT --sandbox
```

---

## 6. Proxmox Migration Checklist (for when the server is ready)

- [ ] Install Proxmox VE on bare metal
- [ ] Create ZFS pool
- [ ] Create VM 100 (Ubuntu + Docker), VM 101 (Windows + MT5), LXC 200 (Forgejo)
- [ ] Configure static IPs on vmbr0
- [ ] Set up SSH keys (laptop → CI → Docker host)
- [ ] Push repo to Forgejo
- [ ] Clone on Docker host: `git clone → /opt/goliath`
- [ ] Create `.env` on Docker host (never in git)
- [ ] `docker compose up -d`
- [ ] Install MT5 on Windows VM, configure EA addresses to `10.0.0.100`
- [ ] Register Forgejo Actions runner
- [ ] Test full pipeline: push from laptop → CI → auto-deploy
- [ ] Set up ZFS snapshot cron (daily, 30-day retention)
- [ ] Configure Docker log rotation

**Minimum server hardware:** 16 cores, 32GB RAM, 256GB SSD
