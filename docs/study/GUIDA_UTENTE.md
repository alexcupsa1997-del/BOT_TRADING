# 🚀 GOLIATH Trading Bot - Guida Completa

## Requisiti
- Docker Desktop installato e **avviato**
- MetaTrader 5 con Expert Advisors abilitati
- Python 3.10+ con ambiente virtuale attivo

---

## ⚡ Quick Start (Ogni Giorno)

### Accendere il Sistema

```powershell
# 1. Apri PowerShell in E:\Progetti\BOT_TRADING

# 2. Avvia Docker containers
docker-compose up -d

# 3. Verifica che funziona
docker ps
```

Output atteso:
```
CONTAINER ID   IMAGE                    STATUS         PORTS
abc123...      bot_trading-gateway      Up 2 minutes   0.0.0.0:8080->8080/tcp, 5555/tcp
```

### Spegnere il Sistema

```powershell
docker-compose down
```

---

## 🔍 Verificare che Docker Funziona

### Metodo 1: `docker ps`
```powershell
docker ps
# Se vedi "bot_trading-gateway" con STATUS "Up" → OK ✅
```

### Metodo 2: Test API
```powershell
curl http://localhost:8080/health
# Risposta: "OK" → Gateway funzionante ✅
```

### Metodo 3: Logs in tempo reale
```powershell
docker logs -f bot_trading-gateway-1
# Ctrl+C per uscire
```

---

## 📊 Configurare MetaTrader 5

### 1. Abilitare WebRequest (per GoliathHybrid)

1. **Strumenti** → **Opzioni** → **Expert Advisors**
2. Spunta: ✅ "Consenti trading automatico"
3. Spunta: ✅ "Consenti richieste WebRequest per URL elencati"
4. Aggiungi: `http://localhost:8080`
5. Clicca **OK**

### 2. Compilare gli EA

1. Apri **MetaEditor** (F4 da MT5)
2. Apri ogni file da `gateway/mt5_ea/`:
   - `Bridge.mq5`
   - `SignalTrader.mq5`
   - `GoliathHybrid.mq5`
3. Premi **F7** per compilare ciascuno
4. Verifica: nessun errore nella finestra "Errors"

### 3. Attaccare EA al Grafico

1. Apri un grafico (es. EURUSD M1)
2. **Navigatore** → **Expert Advisors** → trascina EA sul grafico
3. Nella finestra popup:
   - Tab **Comune**: ✅ "Consenti trading automatico"
   - Tab **Input**: configura parametri
4. Clicca **OK**
5. Verifica: icona 😊 in alto a destra (non 😞)

---

## 🎯 Quale EA Usare?

| Situazione | EA da Usare |
|------------|-------------|
| **Raccolta dati** (sempre attivo) | `Bridge.mq5` |
| **Backtest strategia** | `SignalTrader.mq5` |
| **Trading live ibrido** | `GoliathHybrid.mq5` |

### Setup Tipico (Trading Live)

1. **Grafico 1**: `Bridge.mq5` su qualsiasi simbolo (raccoglie dati)
2. **Grafico 2**: `GoliathHybrid.mq5` su EURUSD (trading)
3. **Grafico 3**: `GoliathHybrid.mq5` su XAUUSD (trading)

---

## 🛠️ Troubleshooting

### Docker non parte
```powershell
# Riavvia Docker Desktop
# Poi:
docker-compose up -d --build
```

### EA mostra 😞 (faccina triste)
- Vai su **Strumenti** → **Opzioni** → **Expert Advisors**
- Abilita "Consenti trading automatico"
- Clicca il pulsante "AutoTrading" nella toolbar MT5

### Nessuna connessione al Gateway
```powershell
# Verifica che Gateway sia attivo
docker logs bot_trading-gateway-1 --tail 20
# Cerca "MT5 Bridge listening on :5555"
```

### Web Request fallisce
- Aggiungi `http://localhost` alle URL consentite in MT5
- Riavvia MT5 dopo aver modificato le impostazioni

---

## 📋 Checklist Giornaliera

### Mattina (Accensione)
- [ ] Avvia Docker Desktop
- [ ] `docker-compose up -d`
- [ ] `docker ps` → verifica container attivo
- [ ] Apri MT5
- [ ] Attacca EA ai grafici
- [ ] Verifica icona 😊

### Sera (Spegnimento)
- [ ] Scollega EA dai grafici (click destro → "Rimuovi")
- [ ] Chiudi MT5
- [ ] `docker-compose down`
- [ ] (Opzionale) Chiudi Docker Desktop

---

## 🔧 Comandi Utili

```powershell
# Stato containers
docker ps

# Logs Gateway
docker logs bot_trading-gateway-1 --tail 50

# Logs in tempo reale
docker logs -f bot_trading-gateway-1

# Riavvia Gateway
docker-compose restart gateway

# Rebuild completo
docker-compose down
docker-compose build --no-cache
docker-compose up -d

# Test salute sistema
python goliath.py
```
