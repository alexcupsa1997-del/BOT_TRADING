---
trigger: always_on
glob: "**/*.{sql,py,rs,go,parquet}"
description: "Regole rigorose per la gestione della persistenza dati, serie temporali e integrità per ML."
---

# Database & Data Persistence Rules

## 1. Storage Strategy & Formats
- **Market Data (Historical):** I dati storici (Tick, Candle) DEVONO essere salvati in formato **Apache Parquet** con compressione `SNAPPY` o `ZSTD`.
  - *Motivo:* Ottimizzato per letture colonnari veloci richieste dal training dei modelli ML.
- **Market Data (Live/Hot):** Utilizzare Ring Buffers in memoria o Redis per i dati in tempo reale. Non scrivere su disco per ogni tick.
- **Metadata & Configuration:** Utilizzare SQLite o PostgreSQL per configurazioni, log degli ordini e utenti.

## 2. Data Integrity & Schema
- **Immutabilità:** I dati di mercato storici sono IMMUTABILI. Una volta scritti, non devono mai essere modificati. Se necessario, creare una nuova versione del dataset.
- **Schema Evolution:**
  - Qualsiasi modifica allo schema dei dati (es. nuovi campi in `orders.sbe`) deve essere retro-compatibile.
  - Utilizzare il versionamento semantico per i dataset (es. `v1_ticks`, `v2_ticks`).
- **Data Types:**
  - Prezzi: Utilizzare SEMPRE interi (es. centesimi/pip) o `Decimal` a virgola fissa. **MAI** usare `float` o `double` per valori monetari per evitare errori di arrotondamento IEEE 754.
  - Timestamp: Utilizzare UTC Unix Nanoseconds (`int64`) per precisione assoluta.

## 3. Performance Optimization
- **Partitioning:** I file Parquet devono essere partizionati per `YYYY-MM-DD` e `Symbol` per velocizzare le query di backtesting.
- **Batch Writing:** Le scritture su disco devono avvenire in batch (es. ogni 1000 tick o ogni secondo) per ridurre l'I/O overhead.
- **Indexing:** Nei DB relazionali, indicizzare sempre le colonne `timestamp` e `symbol`.

## 4. ML Specific Data Rules
- **Feature Store:** Le feature calcolate (es. RSI, MACD) per il training devono essere salvate separatamente dai dati grezzi per garantire riproducibilità.
- **Data Sanitization:** Prima di salvare dati per il training:
  - Rimuovere duplicati.
  - Gestire i valori mancanti (NaN) con interpolazione o drop (da documentare).
  - Rilevare outlier anomali (es. flash crash fittizi dovuti a errori API).