---
trigger: always_on
glob: "**/*.{rs,go,py}"
description: "Regole per la gestione dei flussi dati ad alta frequenza, code e latenza."
---

# Backend & Data Flow Rules

## 1. High Frequency Data Handling
- **SBE (Simple Binary Encoding):**
  - Utilizzare SBE per la messaggistica interna tra Gateway (Go), Engine (Rust) e Analytics (Python).
  - Preferire la deserializzazione "Zero-Copy" dove possibile (specialmente in Rust).
- **Backpressure:** Implementare meccanismi di backpressure. Se l'Engine non riesce a elaborare i tick velocemente quanto il Gateway li riceve, i dati vecchi devono essere scartati (drop) in favore dei nuovi (Latest-wins policy) per il trading live. Per il logging, usare code separate senza drop.

## 2. Concurrency & Parallelism
- **Rust Engine:** Utilizzare il pattern "Actor Model" (es. `tokio` channels) per isolare Risk Management, Matching Engine e Signal Processing.
- **Python ML:** Utilizzare `multiprocessing` invece di `threading` per aggirare il GIL durante l'elaborazione dati pesante (ETL).
- **Locking:** Evitare Lock globali (Mutex) nelle hot-path critiche. Preferire strutture dati lock-free o passaggio di messaggi.

## 3. Pipeline Integrity
- **Idempotenza:** I consumatori di messaggi (es. chi aggiorna il saldo) devono essere idempotenti. Elaborare lo stesso messaggio due volte non deve corrompere lo stato.
- **Dead Letter Queues:** I messaggi malformati o che causano crash devono essere deviati in una "Dead Letter Queue" per analisi successiva, senza bloccare il flusso principale.

## 4. Latency Monitoring
- Ogni messaggio critico deve avere un `ingress_timestamp` (quando è entrato nel sistema) e un `egress_timestamp`.
- Loggare avvisi se la latenza interna `egress - ingress` supera una soglia critica (es. 5ms).