---
trigger: always_on
glob: "**/*.{env,yml,json,toml}"
description: "Regole di sicurezza operativa e protezione dei dati."
---

# Security Rules

## 1. Credentials & Secrets
- **No Hardcoded Secrets:** Mai inserire password, API Keys o chiavi private nel codice sorgente.
- **Environment Variables:** Utilizzare file `.env` (non committati su git) o Secret Managers.
- **GitIgnore:** Assicurarsi che `.env`, `*.pem`, `*.key` siano nel `.gitignore` globale e locale.

## 2. Network & Access
- **API Whitelisting:** Configurare le API dell'Exchange per accettare richieste solo dall'IP statico del server di produzione.
- **Least Privilege:** Il database user per l'analisi dati deve avere permessi di `READ-ONLY`. Solo il servizio di ingestion ha permessi di `WRITE`.

## 3. Operational Security
- **Dry-Run Mode:** Il bot deve avere un flag `--dry-run` o `--paper` che inibisce l'invio reale di ordini, permettendo di testare tutta la logica di connessione e calcolo in sicurezza.
- **Max Drawdown Kill-Switch:** Implementare un hard-stop a livello di codice. Se la perdita giornaliera supera X%, il bot si spegne automaticamente e revoca tutti gli ordini pendenti.