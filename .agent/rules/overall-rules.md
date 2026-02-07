---
trigger: always_on
glob: "**/*"
description: "Regole fondamentali per l'architettura, il codice e lo sviluppo del modello neuronale."
---

# Overall Architecture & ML Rules

## 1. Neural Network & ML Development
- **No Look-Ahead Bias:** È la regola d'oro. Durante la creazione di dataset per il training:
  - Le feature al tempo `t` NON devono contenere informazioni dal tempo `t+1`.
  - Normalizzare i dati (Z-Score, MinMax) usando statistiche calcolate SOLO sul set di training (rolling window), mai sull'intero dataset futuro.
- **Train/Validation/Test Split:** Separazione temporale rigorosa.
  - Esempio: Train (Gen-Giu), Validation (Lug-Ago), Test (Set). Non mischiare dati randomicamente (shuffle) per serie temporali.
- **Feature Parity:** Il codice che calcola le feature in Python per il training DEVE essere logicamente identico all'implementazione in Rust/Go usata in produzione. Scrivere test di integrazione cross-language per verificarlo.

## 2. Coding Standards
- **Explicit is better than Implicit:** Niente "magia". Il flusso dei dati deve essere tracciabile.
- **Error Handling:**
  - Rust: Mai usare `.unwrap()` in produzione. Gestire ogni `Result` e `Option`.
  - Go: Gestire sempre l'errore ritornato (`if err != nil`).
  - Python: Usare Type Hints (`typing`) ovunque per ridurre errori a runtime.
- **Logging:**
  - Log strutturati (JSON) per facilitare il parsing automatico.
  - Livelli: `DEBUG` (sviluppo), `INFO` (eventi chiave), `WARN` (anomalie recuperabili), `ERROR` (intervento umano richiesto), `FATAL` (shutdown immediato).

## 3. System Resilience
- **Fail-Safe:** Se un componente critico (es. Risk Manager) fallisce, il sistema deve passare in modalità "Safe Mode" (chiudere posizioni o bloccare nuovi ordini), non crashare lasciando ordini aperti.
- **Heartbeats:** Ogni microservizio deve inviare un heartbeat. Se il "Watchdog" non riceve heartbeat per X secondi, deve allertare o riavviare.