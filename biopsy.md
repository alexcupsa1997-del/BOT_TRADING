# 🔬 PROJECT BIOPSY — Full System Assessment

**Data:** 14 Febbraio 2026
**Autore:** Renan Augusto Macena
**Scope:** (Full Stack)
**Classificazione:** Internal — Engineering Deep Dive

---

> [!IMPORTANT]
> Questo documento rappresenta un'analisi forense completa dello stato attuale dell'intero ecosistema di trading.
> Ogni componente è stato ispezionato a livello di codice sorgente, architettura, sicurezza, e maturità operativa.

---

## 📋 Executive Summary

L'ecosistema di trading è composto da **due progetti principali** che operano su layer architetturali distinti ma complementari:

| Progetto | Ruolo | Stack | Stato |
|----------|-------|-------|-------|
| **Ground_Zero** | Cervello Analitico (AI/ML) | Python, XGBoost, TradingView | 🟡 Alpha Funzionante |
| **BOT_TRADING** | Infrastruttura HFT | Go, Rust, PyTorch, Docker | 🟠 Prototipo Avanzato |

**Verdetto Globale:** Il sistema si trova in uno stato di **"Advanced Prototype"** — la maggior parte dei componenti core esiste e compila, ma manca l'integrazione end-to-end tra i due progetti, il testing è insufficiente (coverage stimata < 5%), e diversi path critici contengono TODO o placeholder. La knowledge base documentale è eccezionalmente ricca (111+ documenti), ma il codice non riflette ancora tutta la sofisticazione della ricerca.

> [!CAUTION]
> **Gap Critico di Integrazione:** I due progetti non comunicano ancora. Ground_Zero produce previsioni XGBoost su timeframe giornaliero, ma non esiste nessun meccanismo per trasferire questi segnali al BOT_TRADING Gateway. L'endpoint `/api/signal/` nel Go Gateway restituisce un placeholder hardcoded `{"direction": "HOLD", "confidence": 0}`. Questo significa che l'intero stack HFT (Rust Engine, GoliathTransformer, RiskManager) opera in isolamento dal cervello predittivo.

**Analisi Tecnica dello Stato Corrente:**

Il sistema presenta una dicotomia architetturale interessante. **Ground_Zero** adotta un approccio monolitico-modulare in Python puro, ottimizzato per prototipazione rapida e iterazione sulla logica ML. Il modello XGBoost opera su feature giornaliere (SMA, RSI, MACD, Bollinger, correlazioni macro Gold-DXY-TNX) con un singolo split temporale al 2024-01-01. **BOT_TRADING** invece implementa un'architettura polyglot enterprise-grade con separazione netta: Go per I/O networking ad alta concorrenza, Rust per la logica di matching e risk con garanzie di safety a compile-time, Python per l'analisi quantitativa e il deep learning.

Il contrasto tra la maturità documentale (9/10) e la maturità del testing (2/10) suggerisce un progetto guidato dalla ricerca dove l'implementazione ha proceduto più velocemente della validazione. Questo è un pattern comune nei progetti di trading algoritmico, ma rappresenta un rischio significativo prima del deployment in live.

### Metriche Aggregate

| Metrica | Ground_Zero | BOT_TRADING | Totale |
|---------|-------------|-------------|--------|
| File Sorgente (core) | 8 Python | 15 Rust + 8 Go + 39 Python | **70** |
| Linee di Codice (stimate) | ~600 | ~4500+ | **~5100** |
| Documenti Knowledge Base | 111 MD | 5 MD | **116** |
| MCP Servers | 3 custom | 1 (blockscout) | **4** |
| Test Files | 0 | 3 (Go+Rust) | **3** |
| Model Checkpoints | 1 (XGBoost) | 3 (PyTorch) | **4** |
| Docker Services | 0 | 4 | **4** |
| Data Files (Parquet/CSV) | 4 CSV | 7 Parquet | **11** |

---

## 🏗️ Architettura di Sistema — Topologia Globale

![System Architecture Overview — mostra la separazione tra Ground_Zero AI Brain e BOT_TRADING HFT Infrastructure con il Data Layer condiviso](diagrams/diagram_01.png)

**Analisi della Topologia:** Il sistema è strutturato su tre macro-layer orizzontali con dipendenze unidirezionali (top-down). Il layer **Data Sources** (TradingView, Yahoo Finance, MT5) alimenta i due engine paralleli. Il layer **Processing** elabora dati con latenza e granularità diverse — Ground_Zero opera su candele giornaliere/4h con cicli di aggiornamento nell'ordine dei secondi, mentre BOT_TRADING processa tick individuali con target di latenza sub-millisecondo. Il layer **Storage** raccoglie output in formati ottimizzati: CSV per compatibilità con il workflow ML Python, Parquet per efficienza colonnare nelle letture analitiche ad alto volume.

> [!NOTE]
> La biforcazione architetturale (monolite Python vs microservizi polyglot) è intenzionale: Ground_Zero privilegia la velocità di iterazione scientifica ("fail fast, learn fast"), BOT_TRADING privilegia la robustezza operativa e le garanzie di performance. La sfida ingegneristica chiave è costruire il ponte tra questi due paradigmi senza compromettere i vantaggi di nessuno dei due.

### Flusso Dati End-to-End (Data Flow Pipeline)

![Data Flow Pipeline — due pipeline parallele: Ground_Zero su dati giornalieri e BOT_TRADING su tick real-time](diagrams/diagram_02.png)

**Analisi del Flusso Dati:** Il diagramma rivela la caratteristica più importante dell'architettura: **due pipeline dati completamente indipendenti** che non si intersecano in nessun punto. La pipeline superiore (Ground_Zero) opera in modalità batch — scarica storico, calcola feature, addestra modelli, produce previsioni. La pipeline inferiore (BOT_TRADING) opera in modalità streaming — riceve tick via TCP, li bufferizza in Parquet, li processa tramite ETL e Transformer.

Questo design "dual-pipeline" è intenzionale per evitare contaminazione tra training offline e inferenza online, ma crea un problema fondamentale: **il segnale prodotto dal Transformer HFT non ha accesso al contesto macro** (correlazioni Gold-DXY, sentiment, analisi fondamentale) che solo Ground_Zero possiede. La fusione di questi due stream informativi è il prossimo milestone architetturale critico.

---

## 🔍 SEZIONE 1: Ground_Zero — Audit Dettagliato

### 1.1 Panoramica Architetturale

Ground_Zero è il **cervello analitico** del sistema, focalizzato esclusivamente su **XAUUSD (Gold)**. Implementa una pipeline ML classica: Data Ingestion → Feature Engineering → Model Training → Live Prediction. Il design è monolitico ma modulare, con separazione chiara tra connectors, models, core e tools.

![Ground_Zero Architecture — 5 layer: Connectors, Core, Models, Tools, Backtest con ~600 LOC totali](diagrams/diagram_03.png)

**Analisi dei Layer Architetturali:**

L'architettura di Ground_Zero segue un pattern **Layered Architecture** classico con dipendenze unidirezionali verso il basso. Tuttavia, l'analisi rivela violazioni importanti:

1. **Connectors → Models bypass:** `fetch_history.py` alimenta direttamente `feature_engineering.py` senza passare per il `DataManager`, creando un accoppiamento implicito che bypassa l'astrazione Core. Questo significa che se si cambia il formato di storage dei dati (es. da CSV a Parquet), bisogna modificare sia `DataManager` che `feature_engineering.py`.

2. **Duplicazione verticale:** `ask_oracle.py` nel Tools Layer reimplementa gran parte della logica di `feature_engineering.py` nel Models Layer. Questo viola il principio DRY (Don't Repeat Yourself) e introduce rischi di **Feature Parity Drift** — una divergenza silenziosa tra le feature usate in training e quelle usate in produzione, che è la causa #1 di degradazione dei modelli ML in produzione.

3. **Backtest isolato:** Il `BacktestEngine` dipende esclusivamente dal `DataManager` ma non utilizza le feature dell'XGBoost. Valida una strategia SuperTrend che non è correlata al modello ML, rendendo il backtest un componente disconnesso dal loop di validazione ML.

### 1.2 Analisi Componente per Componente

#### 📌 `src/connectors/fetch_history.py` — Data Ingestion Layer

| Attributo | Valore |
|-----------|--------|
| **LOC** | 46 |
| **Complessità Ciclomatica** | Bassa |
| **Dipendenze** | yfinance, pandas, os |
| **Maturità** | 🟢 Funzionante |

**Funzionalità:** Scarica lo storico massimo disponibile per Gold Futures (GC=F), US Dollar Index (DX-Y.NYB) e 10-Year Treasury Yield (^TNX) tramite l'API Yahoo Finance. Salva i dati in CSV nella directory `data/raw/`.

**Punti di Forza:**

- Pulizia dei simboli nel filename (replace di `=` e `^`)
- Selezione esplicita delle colonne OHLCV
- Log informativo con date di inizio/fine

**Criticità Identificate:**

- ❌ **Nessuna gestione errori di rete** — Se yfinance fallisce (rate limit, timeout), lo script crasha silenziosamente
- ❌ **Nessun meccanismo di retry** — Violazione del principio di Resilienza (Rule: System Resilience)
- ❌ **Hardcoded symbols** — I simboli sono definiti come costante globale, non parametrizzati da config
- ⚠️ **Formato data non ISO** — `strftime('%Y-%m-%d')` è corretto ma si perde il timezone info
- ⚠️ **Nessuna validazione dei dati scaricati** — Non verifica duplicati né data integrity

**Raccomandazione:** Aggiungere retry con exponential backoff, validazione schema, e parametrizzazione da `config.yaml`.

---

#### 📌 `src/connectors/tv_bridge.py` — TradingView Real-time Connector

| Attributo | Valore |
|-----------|--------|
| **LOC** | 49 |
| **Complessità Ciclomatica** | Bassa |
| **Dipendenze** | tradingview_ta, pandas, json |
| **Maturità** | 🟢 Funzionante |

**Funzionalità:** Recupera l'analisi tecnica in tempo reale per XAUUSD su due timeframe (15m e 4h) tramite la libreria `tradingview_ta`. Espone dati di RSI, prezzo, SMA200 e sommario del segnale (BUY/SELL/NEUTRAL).

**Punti di Forza:**

- Multi-timeframe analysis (15m + 4h) — approccio professionale
- Output strutturato in JSON
- Gestione eccezione con fallback a None

**Criticità Identificate:**

- ⚠️ **Exchange hardcoded** — `TVC` potrebbe non essere l'exchange ottimale per tutti i broker
- ⚠️ **Nessun caching** — Ogni chiamata è una richiesta di rete
- ❌ **Nessun rate limiting** — Chiamate rapide ripetute rischiano il ban
- ⚠️ **Solo 2 timeframe** — Manca la visione su Daily/Weekly per conferma macro

---

#### 📌 `src/core/data_manager.py` — Core Data Abstraction Layer

| Attributo | Valore |
|-----------|--------|
| **LOC** | 53 |
| **Complessità Ciclomatica** | Media |
| **Dipendenze** | pandas, yfinance, pandas_ta, yaml |
| **Maturità** | 🟡 Funzionante con limitazioni |

**Funzionalità:** Classe centrale che carica la configurazione da `config.yaml`, scarica dati OHLCV tramite yfinance, e aggiunge indicatori tecnici (ATR, RSI, SuperTrend, ADX) usando `pandas_ta`.

**Analisi del Design Pattern:**
Il `DataManager` implementa un **Facade Pattern** rudimentale, nascondendo la complessità di fetching e processing dietro un'interfaccia semplice (`fetch_data()`, `add_indicators()`). Tuttavia, viola il **Single Responsibility Principle (SRP)** — gestisce sia il data fetching che l'indicator calculation.

**Criticità Identificate:**

- ❌ **MultiIndex fix fragile** — Il workaround `df.columns.get_level_values(0)` è un patch per un bug noto di yfinance, ma non è robusto per future versioni
- ❌ **Config path relativo** — `config_path="config.yaml"` assume che il CWD sia la root del progetto. Questo rompe quando si esegue da subdirectory
- ⚠️ **Indicatori non configurabili** — ATR e ADX non leggono parametri dal config, solo RSI e SuperTrend lo fanno
- ⚠️ **Nessun caching** — Ogni chiamata a `fetch_data()` fa una richiesta di rete

---

#### 📌 `src/models/feature_engineering.py` — Feature Pipeline

| Attributo | Valore |
|-----------|--------|
| **LOC** | 91 |
| **Complessità Ciclomatica** | Media |
| **Dipendenze** | pandas, pandas_ta |
| **Maturità** | 🟢 Solido |

**Funzionalità:** Carica e mergia tre dataset (Gold, DXY, TNX), calcola indicatori tecnici (SMA, RSI, ATR, MACD, Bollinger Bands) e feature macro (rolling correlation Gold-DXY, Gold-TNX), e genera il target binario per il training (direzione prezzo domani).

**Punti di Forza:**

- ✅ **Inner join corretto** — Merge solo sui giorni in cui tutti i mercati erano aperti, evitando misalignment
- ✅ **Forward fill** per gap festivi
- ✅ **Rolling correlations** — Feature macro sofisticata (20-day rolling correlation)
- ✅ **Target non contaminante** — `shift(-1)` per il target è corretto (no look-ahead bias nella creazione del target)

**Criticità Identificate:**

- ❌ **Potenziale Look-Ahead Bias negli indicatori** — Le SMA, RSI, MACD usano parametri calcolati sull'**intero dataset** incluso il futuro. Sebbene tecnicamente gli indicatori siano calcolati in modo rolling, il `dropna()` finale opera su tutto il dataframe, il che potrebbe mascherare edge effects
- ⚠️ **Nessuna normalizzazione** — Le feature non sono normalizzate (Z-Score/MinMax). L'XGBoost è tree-based e non ne ha bisogno, ma se si migra a reti neurali sarà critico
- ⚠️ **Feature names dinamiche** — `ta.macd()` e `ta.bbands()` generano nomi colonna come `MACD_12_26_9` che dipendono dalla versione della libreria

---

#### 📌 `src/models/train_model.py` — Model Training Pipeline

| Attributo | Valore |
|-----------|--------|
| **LOC** | 76 |
| **Complessità Ciclomatica** | Bassa |
| **Dipendenze** | xgboost, sklearn, pandas |
| **Maturità** | 🟢 Funzionante |

**Funzionalità:** Carica il dataset processato, effettua split temporale (pre/post 2024-01-01), addestra un XGBClassifier per previsione binaria (Up/Down), e salva il modello.

**Punti di Forza:**

- ✅ **Split temporale rigoroso** — `SPLIT_DATE = "2024-01-01"` evita data leakage
- ✅ **Iperparametri ragionevoli** — `n_estimators=100, learning_rate=0.05, max_depth=5` sono conservativi e anti-overfitting
- ✅ **Feature importance logging** — Top 5 feature display per interpretabilità
- ✅ **Modello persistito** — `.save_model()` nativo di XGBoost

**Criticità Identificate:**

- ⚠️ **Nessuna cross-validation temporale** — Un singolo split non è sufficiente per valutare la stabilità del modello. Servirebbe una `TimeSeriesSplit` o walk-forward validation
- ⚠️ **Nessun early stopping** — Il modello potrebbe overfittare senza `eval_set` e `early_stopping_rounds`
- ❌ **Nessun hyperparameter tuning** — Parametri fissi senza grid search / Bayesian optimization
- ⚠️ **`joblib` importato ma non usato** — Dead import, segno di refactoring incompleto

---

#### 📌 `src/tools/ask_oracle.py` — Live Prediction Engine

| Attributo | Valore |
|-----------|--------|
| **LOC** | 142 |
| **Complessità Ciclomatica** | Media-Alta |
| **Dipendenze** | xgboost, pandas_ta, yfinance |
| **Maturità** | 🟡 Funzionante con rischi |

**Funzionalità:** Il componente più critico: carica il modello XGBoost addestrato, scarica dati live da Yahoo Finance (2 anni di storico), ricalcola tutte le feature esattamente come nel training, e produce una previsione BULLISH/BEARISH con la probabilità.

**Analisi Feature Parity (Regola Fondamentale):**

Questo script è il punto dove la **Feature Parity** (Rule: Neural Network & ML Development §1) è più a rischio. Il codice in `prepare_last_row()` replica la feature engineering di `feature_engineering.py`, ma:

- ✅ `SMA_50`, `SMA_200`, `Dist_SMA200`, `RSI`, `ATR` — **Parità verificata**
- ✅ `MACD`, `BBands` — **Parità verificata**
- ✅ `DXY_SMA_50`, `DXY_Trend`, `TNX_SMA_50` — **Parità verificata**
- ✅ `Corr_Gold_DXY`, `Corr_Gold_TNX` — **Parità verificata**
- ✅ Feature alignment con `model.get_booster().feature_names` — **Sicurezza aggiuntiva**

**Criticità Identificate:**

- ❌ **Duplicazione codice** — La logica di feature engineering è duplicata tra `feature_engineering.py` e `ask_oracle.py`. Una modifica in uno potrebbe non essere propagata nell'altro
- ❌ **`get_latest_data()` è dead code** — La funzione originale non è mai usata, sostituita da `get_latest_data_full()`. Codice morto nel file
- ⚠️ **2 anni di storico** — `period="2y"` è sufficiente per SMA200 ma spreca banda. `period="1y"` sarebbe sufficiente per tutte le feature
- ⚠️ **`outer` join** — Il join outer con ffill può introdurre dati sintetici nei giorni festivi

---

#### 📌 `src/backtest/engine.py` — Backtesting Engine

| Attributo | Valore |
|-----------|--------|
| **LOC** | 74 |
| **Complessità Ciclomatica** | Media |
| **Dipendenze** | pandas, numpy, DataManager |
| **Maturità** | 🟠 MVP — Significative Lacune |

**Funzionalità:** Implementa un backtester event-driven basato su SuperTrend. Itera su ogni candela, rileva cambi di trend, e apre/chiude posizioni Long/Short.

**Analisi del Design:**

![Backtest State Machine — transizioni tra stati Flat, Long, Short basate su SuperTrend direction changes](diagrams/diagram_04.png)

**Analisi della Macchina a Stati:** Il diagramma rivela un modello di trading **always-in-market** senza stato di attesa. Una volta uscito dallo stato `Flat` iniziale tramite la prima inversione SuperTrend, il sistema oscilla perennemente tra `Long` e `Short` attraverso reversals diretti, oppure passa brevemente per `Flat` prima di rientrare. Questo design esclude la possibilità di "non fare nulla" — una strategia che in mercati laterali (range-bound) può accumulare perdite significative da whipsaw. La mancanza di filtri di confluenza (es. "entra Long solo se RSI > 50 E MACD > signal line") rende il sistema vulnerabile a false inversioni.

**Criticità Identificate (SEVERE):**

- ❌ **Nessuno Stop Loss / Take Profit** — Il sistema chiude solo su reversal del trend. In un mercato laterale, accumula perdite senza protezione
- ❌ **Contract size fisso** — `pnl * 100` è un moltiplicatore hardcoded, non legge il config
- ❌ **Nessun slippage/commissioni** — Il `config.yaml` definisce `slippage_model` e `commission_per_lot`, ma l'engine li ignora completamente
- ❌ **Nessun risk management** — `risk_per_trade_pct` e `max_drawdown_limit` dal config non sono implementati
- ❌ **Win rate come unica metrica** — Mancano: Sharpe Ratio, Max Drawdown, Profit Factor, Calmar Ratio, Average Win/Loss
- ⚠️ **Loop non vettorizzato** — Il commento stesso ammette che sarebbe meglio vettorizzare. Per dataset grandi, performance O(n) lineare ma con overhead Python
- ⚠️ **`entry_price` come attributo non inizializzato** — Assegnato solo in `open_long`/`open_short`, potrebbe causare `AttributeError` se `close_position` viene chiamato prima

---

#### 📌 `src/market_monitor.py` — Live Data Collector

| Attributo | Valore |
|-----------|--------|
| **LOC** | 74 |
| **Complessità Ciclomatica** | Bassa |
| **Dipendenze** | tradingview_ta, pandas |
| **Maturità** | 🟢 Funzionante |

**Funzionalità:** Loop infinito che ogni 60 secondi recupera prezzo, RSI, e raccomandazione per GOLD da TradingView, stampando a video e salvando su CSV.

**Criticità Identificate:**

- ⚠️ **CSV append senza dedup** — Se riavviato, non verifica timestamp duplicati
- ⚠️ **Nessun graceful shutdown** — Solo `KeyboardInterrupt`, nessun signal handler (SIGTERM)
- ⚠️ **60 secondi fissi** — Il commento dice "1 minuto per maggiore reattività" ma il timeframe TradingView è anche 1 minuto, quindi i dati sono spesso identici

---

### 1.3 MCP Servers — Audit API Layer

Ground_Zero include **3 server MCP custom** che estendono le capacità dell'agente AI con accesso a dati finanziari esterni:

| Server | Endpoint | API Key Req. | LOC | Stato |
|--------|----------|-------------|-----|-------|
| `fred_server.py` | Federal Reserve FRED | `FRED_API_KEY` | 48 | 🟢 OK |
| `fmp_server.py` | Financial Modeling Prep | `FMP_API_KEY` | 31 | 🟢 OK |
| `brave_server.py` | Brave Search | `BRAVE_API_KEY` | 53 | 🟢 OK |

**Pattern Comune (Positivo):**

- Tutti usano `FastMCP` con la stessa struttura
- Tutti caricano le API key da `.env` (conforme a Security Rules §1)
- Tutti usano `httpx.AsyncClient` per chiamate HTTP non bloccanti

**Criticità Trasversali:**

- ❌ **Nessun rate limiting** — Chiamate illimitate all'API
- ❌ **Nessun caching** — Ogni chiamata è una richiesta di rete, anche per dati identici
- ⚠️ **Error handling minimo** — Solo check di API key mancante, nessuna gestione di HTTP errors (429, 500)
- ⚠️ **Nessun timeout configurato** — Default httpx timeout potrebbe causare hanging

### 1.4 Knowledge Factory — Generatori Automatici

Due script di generazione batch per popolare la knowledge base:

| Script | Target | Records | Stato |
|--------|--------|---------|-------|
| `generate_history_reports.py` | 50 eventi storici | docs/history/ | 🟢 Eseguito |
| `generate_mining_reports.py` | 50 mining tickers | docs/miners/ | 🟢 Eseguito |

**Architettura Intelligente:** Questi script implementano un pattern di **"Knowledge Mining"** — scaricano dati storici da Yahoo Finance intorno a date specifiche (±5/10 giorni) e generano report markdown automaticamente. L'approccio è promettente per il training di LLM su eventi di mercato.

**Criticità:**

- ⚠️ **Rate limiting rudimentale** — `time.sleep(0.2)` / `time.sleep(0.5)` funziona ma è fragile per 50+ chiamate
- ⚠️ **Path hardcoded assoluto** — `/home/a-cupsa/Desktop/Ground_Zero/docs/history` non è portabile
- ⚠️ **Business summary troncato** — `[:800]` nel mining report potrebbe tagliare informazioni critiche

---

## 🔍 SEZIONE 2: BOT_TRADING — Audit Infrastruttura HFT

### 2.1 Panoramica — Architettura Microservizi

BOT_TRADING implementa un'architettura **polyglot microservices** con separazione netta delle responsabilità:

![BOT_TRADING Microservices Architecture — 4 servizi Docker con Gateway Go, Engine Rust, Analysis Python, Watchdog Alpine](diagrams/diagram_05.png)

**Analisi della Topologia Microservizi:** Il Gateway Go funge da **API Gateway pattern** con responsabilità multiple: reverse proxy per il Signal API, ingestion TCP per tick MT5, e pipeline recording per persistenza Parquet. Questa concentrazione di responsabilità è un compromesso ragionevole per un team piccolo, ma in scala richiederebbe decomposizione (es. separare ingestion da API serving). Il collegamento `PIPE → ETL → GOLIATH → HTTP` forma la **hot path** del sistema — la latenza end-to-end di questa catena determina la freshness delle previsioni.

### 2.2 Go Gateway — Analisi Approfondita

#### `cmd/gateway/main.go` — Entry Point (80 LOC)

Il gateway è il **punto di ingresso unico** del sistema. Implementa tre funzionalità chiave:

1. **Pipeline Recorder** — Scrive tick di mercato su file Parquet con rotazione oraria
2. **MT5 Bridge** — Server TCP sulla porta 5555 per ricevere tick dal MetaTrader 5
3. **HTTP API** — Health check, admin RBAC-protected, e Signal API

**Configurazione del Recorder:**

```
BasePath:      "./data"
RotInterval:   1 ora
BufferSize:    10.000 tick
MaxFileSizeMB: 100 MB
FlushInterval: 5 secondi
```

**Criticità Identificate:**

- ✅ **Timeouts configurati** — `ReadTimeout: 5s, WriteTimeout: 5s` — Best practice HTTP
- ✅ **Graceful shutdown del recorder** — `defer recorder.Stop()`
- ❌ **Signal API è un TODO** — `/api/signal/` restituisce sempre `{"direction": "HOLD", "confidence": 0}`. Il collegamento con il Python Brain non è implementato
- ❌ **Nessun graceful shutdown HTTP** — `server.ListenAndServe()` non gestisce `SIGTERM`. In Docker, questo significa interruzione forzata senza drain delle connessioni
- ⚠️ **Nessun middleware di logging** — Le richieste HTTP non sono loggate
- ⚠️ **Nessun CORS** — Se il frontend deve chiamare l'API, fallirà

#### `internal/pipeline/recorder.go` — Data Ingestion Core (170 LOC)

Componente di alta qualità ingegneristica. Implementa un **buffered async writer** con le seguenti caratteristiche:

**Pattern Architetturale: Producer-Consumer con Backpressure**

![Pipeline Recorder Sequence — Producer-Consumer pattern with backpressure via channel buffer drop](diagrams/diagram_06.png)

**Analisi del Pattern di Backpressure:** Il diagramma illustra l'implementazione del principio **"Better to lose history than block Trading Engine"** — un trade-off fondamentale nei sistemi HFT. Il buffer a 10K capacità con drop silenzioso implementa una politica **Latest-Wins** dove la consistenza storica viene sacrificata in favore della latenza operativa. In condizioni normali (throughput < capacità buffer), zero tick vengono persi. Sotto stress (burst > 10K tick/ciclo di flush), i tick più vecchi nel buffer vengono preservati mentre i nuovi vengono scartati. Questo è il comportamento corretto per analytics — un gap nei dati è preferibile a un deadlock nella pipeline di trading.

**Punti di Forza (Enterprise-Grade):**

- ✅ **Non-blocking Record()** — `select` con `default` per drop senza blocco. Implementazione corretta del principio "Latest-wins" (Rule: Backend §1.2)
- ✅ **Parquet output** — Formato colonnare ottimo per analytics ML (Rule: Database §1)
- ✅ **File rotation** — Time-based con naming `ticks_YYYYMMDD_HHMMSS.parquet`
- ✅ **Graceful shutdown** — `drain()` svuota il buffer prima di chiudere
- ✅ **Metriche predisposte** — `ticksProcessed` e `ticksDropped` come `uint64` (pronte per atomic increment)

**Criticità Identificate:**

- ⚠️ **Metriche non implementate** — I campi `ticksProcessed`/`ticksDropped` esistono ma non sono incrementati (commento: "we might increment")
- ⚠️ **`float64` per prezzi** — Violazione della regola sui tipi monetari (Rule: Database §2.3). Dovrebbero essere interi (pip/centesimi) o `Decimal`
- ⚠️ **Timestamp in millisecondi** — La regola richiede **nanosecondi** (Rule: Database §2.3)
- ⚠️ **Nessun checksum** — I file Parquet non hanno integrity verification

#### `internal/middleware/rbac.go` — Access Control

Implementa un middleware RBAC (Role-Based Access Control) basato su header HTTP. Il pattern è corretto ma rudimentale — i ruoli sono probabilmente hardcoded. Conforme al principio di Least Privilege (Rule: Security §2).

#### `internal/middleware/pii.go` — PII Scrubber

Middleware per rimuovere Personally Identifiable Information dalle risposte HTTP. Componente di compliance regolamentare — essenziale per GDPR/MiFID II.

---

### 2.3 Rust Engine — Analisi Core Trading

L'engine Rust è il cuore computazionale del sistema, con **4 moduli principali**:

![Rust Engine Module Dependencies — Domain → Matching/Risk → Audit con flusso unidirezionale](diagrams/diagram_07.png)

**Analisi delle Dipendenze:** Il grafo mostra un design **acyclic dependency** corretto: `domain` è il modulo fondamento (zero dipendenze esterne), `matching` e `risk` dipendono entrambi da `domain` per i Value Objects, e `audit` siede in cima come consumatore puro. La dipendenza `risk → matching` indica che il Risk Module può bloccare o modificare ordini prima che raggiungano il matching engine — un pattern di **pre-trade risk check** conforme alle best practice dei sistemi di trading regolamentati (MiFID II Article 17).

**Dipendenze Rust (da Cargo.toml):**

| Crate | Versione | Scopo |
|-------|----------|-------|
| `rust_decimal` | 1.33 | Aritmetica a virgola fissa (Rule-compliant!) |
| `serde` | 1.0 | Serialization |
| `uuid` | 1.6 | Unique identifiers per ordini |
| `chrono` | 0.4 | Timestamp management |
| `sha2` | 0.10.9 | Audit trail hashing |
| `parquet` | 52.0.0 | Output dati in formato colonnare |
| `proptest` | 1.10.0 (dev) | Property-based testing |

**Punti di Forza Architetturali:**

- ✅ **`rust_decimal`** — Conformità totale alla regola "MAI usare float per valori monetari" (Rule: Database §2.3)
- ✅ **Typestate Pattern** — `order_typestate.rs` usa il type system di Rust per garantire che gli ordini attraversino stati validi a compile-time
- ✅ **SHA-256 Audit Trail** — `audit.rs` implementa una hash chain per tamper detection
- ✅ **Circuit Breaker** — `circuit_breaker.rs` implementa protezione contro cascading failures
- ✅ **Spiral Protection** — `spiral_protection.rs` previene death spiral in liquidazioni a catena
- ✅ **Property-Based Testing** — `proptest` per test generativi su proprietà invarianti
- ✅ **SIMD Matching** — `simd.rs` per matching ottimizzato con istruzioni vettoriali

**Criticità Identificate:**

- ⚠️ **Timestamp come `int64`** — Non specificato se nanoseconds o milliseconds. La regola richiede **nanoseconds** espliciti (Rule: Database §2.3)
- ⚠️ **SBE non integrato** — Il file `orders.sbe` esiste nella root ma non c'è evidenza di integrazione nel codice Rust. La regola richiede SBE per messaggistica interna (Rule: Backend §1.1)
- ⚠️ **Binari `.exe`** — `sbe_consumer.exe` e `main.exe` nel gateway suggeriscono compilazione Windows, ma il target dichiarato è Docker Linux

---

### 2.4 Python Analysis Layer — Audit ML/Quant

L'analysis layer è il componente più ricco con **39 file Python** che coprono:

![Analysis Layer Mindmap — 5 aree: ML Models, Quant Engine, Trading Logic, Data Pipeline, Integration](diagrams/diagram_08.png)

**Analisi della Complessità:** Con 39 file Python distribuiti su 5 sotto-domini, l'Analysis Layer è il componente con la maggiore superficie di attacco per bug e inconsistenze. Il rapporto LOC/file è relativamente basso (~50-120 LOC/file), suggerendo buona modularità. Tuttavia, la presenza di file multipli con scopo simile (es. `train_hft.py` vs `train_hft_v3.py`, `indicators.py` vs `indicator_library.py`) suggerisce evoluzione organica senza refactoring — un pattern tipico di "append-only development" dove nuove versioni vengono aggiunte senza deprecare le precedenti.

#### GoliathTransformer — Deep Analysis

| Attributo | Valore |
|-----------|--------|
| **LOC** | 126 |
| **Architettura** | Transformer Encoder |
| **d_model** | 256 (produzione), 64 (test) |
| **nhead** | 8 attention heads |
| **num_layers** | 6 encoder layers |
| **dim_feedforward** | 1024 |
| **dropout** | 0.2 |
| **output_dim** | 3 (Up/Down/Neutral) |
| **max_seq_len** | 64 ticks |

**Analisi Architetturale:**

![GoliathTransformer Architecture — Input Projection → Context Fusion → Positional Encoding → 6x Transformer Encoder → Last Timestep → Decoder](diagrams/diagram_09.png)

**Analisi del Flusso di Forward Pass:** Il Transformer accetta due input paralleli: un tensore temporale `[Batch, 64, Features]` (64 tick con N feature ciascuno) e un vettore di contesto globale `[Batch, ctx_dim]`. La fusione avviene tramite **broadcast addition** — il contesto viene proiettato su `d_model=256` e sommato a ogni timestep, un approccio più leggero rispetto alla cross-attention ma che assume che il contesto influenzi uniformemente tutti i timestep. L'estrazione dell'ultimo timestep `output[:, -1, :]` è una scelta di design che privilegia il segnale più recente, ma scarta l'informazione aggregata — un **mean pooling** o **attention pooling** potrebbe catturare pattern più robusti.

**Punti di Forza:**

- ✅ **Context Fusion** — L'architettura supporta il merge di contesto globale (sentiment, macro) con dati tick-level tramite broadcast addition. Design sofisticato
- ✅ **Sanity Check integrato** — Il `__main__` esegue un forward pass di verifica con NaN detection
- ✅ **Configurazione dataclass** — `GoliathConfig` è pulita e type-hinted

**Criticità Identificate:**

- ❌ **PositionalEncoding non definito** — La classe `PositionalEncoding` è referenziata ma **non è definita nel file**. Questo causerà un `NameError` a runtime. Probabilmente è definita altrove e dovrebbe essere importata
- ⚠️ **Solo last timestep** — `output[:, -1, :]` scarta l'informazione di tutti gli altri timestep. Un pooling (mean/attention) potrebbe essere superiore
- ⚠️ **Nessuna regolarizzazione avanzata** — Solo dropout, nessun LayerNorm aggiuntivo o weight decay esplicito

#### RiskManager — Analisi Componente Critico (440 LOC)

Il `RiskManager` è il componente di **safety-critical** più maturo dell'intero progetto:

**Componenti:**

1. **`RiskConfig`** — Dataclass con 16 parametri configurabili (balance, risk%, drawdown limit, Kelly, lot sizing)
2. **`RiskCalculator`** — Position sizing con formula `(Balance × Risk%) / (SL_distance × Pip_value)`, validazione trade, budget tracking
3. **`ATRStopLoss`** — Stop loss dinamico basato su ATR con multiplier configurabile
4. **`TradeDurationManager`** — Gestione durata trade (5 secondi → 8 ore)

**Punti di Forza:**

- ✅ **Kelly Criterion opzionale** — Implementazione del criterio di Kelly per position sizing ottimale
- ✅ **Max drawdown kill-switch** — Conforme a Security Rules §3
- ✅ **Lot step rounding** — Arrotonda ai lot step consentiti dal broker
- ✅ **Trade validation multi-layer** — Verifica R:R ratio, distanza SL, budget disponibile

**Criticità:**

- ⚠️ **Ancora EURUSD hardcoded** — `symbol: str = "EURUSD"` quando il progetto è per XAUUSD/Gold
- ⚠️ **Balance demo** — `initial_balance: float = 100.0` (100€ demo) — appropriato per test ma da parametrizzare

---

## 🔍 SEZIONE 3: Security Audit — Analisi Vulnerabilità

### 3.1 Matrice di Sicurezza

![Security Posture Quadrant Chart — mappatura rischio/gravità delle 8 vulnerabilità principali](diagrams/diagram_10.png)

**Interpretazione del Quadrante:** Le vulnerabilità nel quadrante **CRITICO** (alto rischio + alta gravità) richiedono intervento immediato. `No Auth on Signal` (0.75, 0.85) è la vulnerabilità più urgente — espone l'intelligenza operativa del sistema senza alcuna protezione. `float64 per prezzi` (0.70, 0.80) è un rischio silenzioso: gli errori di arrotondamento IEEE 754 su valori Gold (∼$2000/oz) possono accumularsi in divergenze significative nel P&L su migliaia di operazioni.

### 3.2 Findings per Categoria OWASP

#### 🔴 A01:2021 — Broken Access Control

| ID | Finding | Severità | Componente |
|----|---------|----------|------------|
| SEC-001 | `/api/signal/` non ha autenticazione | **CRITICAL** | Gateway `main.go` |
| SEC-002 | Health endpoint esposto senza restrizioni | LOW | Gateway `main.go` |
| SEC-003 | RBAC solo su `/admin`, nessun altro endpoint protetto | **HIGH** | `rbac.go` |

**Dettaglio SEC-001:** L'endpoint `/api/signal/{symbol}` è il cuore operativo del sistema — fornisce i segnali di trading. Attualmente restituisce un placeholder, ma quando sarà collegato al Python Brain, qualsiasi client HTTP potrà ricevere i segnali senza autenticazione. Un attaccante potrebbe:

1. Leggere i segnali in tempo reale (information leakage)
2. Flood l'endpoint con richieste (DoS)
3. Analizzare la latenza delle risposte per inferire lo stato del modello (side-channel attack)

**Remediation:** Implementare JWT tokens o API key authentication su tutti gli endpoint operativi. Aggiungere rate limiting con token bucket algorithm.

#### 🟠 A02:2021 — Cryptographic Failures

| ID | Finding | Severità | Componente |
|----|---------|----------|------------|
| SEC-004 | Nessun TLS/HTTPS configurato sul server HTTP | **HIGH** | Gateway `main.go` |
| SEC-005 | Audit trail SHA-256 senza salt | MEDIUM | `audit.rs` |

#### 🟡 A03:2021 — Injection

| ID | Finding | Severità | Componente |
|----|---------|----------|------------|
| SEC-006 | Symbol da URL path non sanitizzato | MEDIUM | `/api/signal/` |
| SEC-007 | Nessuna validazione input su MCP server tools | LOW | `fred_server.py` et al. |

**Dettaglio SEC-006:** Il parametro `symbol` è estratto direttamente dal path URL (`r.URL.Path[len("/api/signal/"):]`) senza sanitizzazione. Se usato in query DB o comando shell downstream, potrebbe consentire path traversal o injection.

#### 🟡 A05:2021 — Security Misconfiguration

| ID | Finding | Severità | Componente |
|----|---------|----------|------------|
| SEC-008 | Docker compose `version: '3.8'` è deprecato | LOW | `docker-compose.yml` |
| SEC-009 | Analysis container usa `tty: true` con keep-alive | LOW | `docker-compose.yml` |
| SEC-010 | Watchdog usa `alpine:latest` (tag mutabile) | MEDIUM | `docker-compose.yml` |
| SEC-011 | Nessun security header HTTP (CSP, HSTS, X-Frame) | **HIGH** | Gateway |

#### 🟢 Conformità alle Regole di Progetto

| Regola | Stato | Note |
|--------|-------|------|
| No Hardcoded Secrets | ✅ PASS | `.env` + `load_dotenv()` |
| .gitignore corretto | ✅ PASS | `.env`, `*.pem`, `*.key` presenti |
| Dry-Run Mode | ❌ FAIL | Nessun `--dry-run` flag implementato |
| Max Drawdown Kill-Switch | ✅ PASS | Implementato in `RiskConfig` |
| API Whitelisting | ❌ FAIL | Nessun IP whitelisting configurato |
| Least Privilege DB | ⚠️ N/A | Nessun database relazionale in uso |

---

## 🔍 SEZIONE 4: Infrastruttura & DevOps Assessment

### 4.1 Docker Compose — Analisi Architetturale

![Docker Compose Topology — 4 servizi con dipendenze esplicite sulla rete bridge trading-net](diagrams/diagram_11.png)

**Analisi delle Dipendenze Docker:** Il diagramma rivela un pattern **star topology** con il Gateway come hub centrale. Il servizio `analysis` usa un workaround anomalo (`command: sleep loop`) per mantenere il container attivo — questo indica che il servizio Python non ha ancora un entry point proprio e viene usato come ambiente di sviluppo più che come microservizio autonomo. Il Watchdog implementa un health check primitivo (`nc -z`) che verifica solo la raggiungibilità della porta, non lo stato funzionale del servizio.

**Criticità Docker:**

- ❌ **Analysis container è un placeholder** — Il command è `python -c "import time; [time.sleep(3600) ...]"`. Non esegue alcuna analisi reale
- ❌ **Nessun health check Docker-native** — Solo il watchdog esterno con `nc -z`, ma Docker ha il proprio meccanismo `HEALTHCHECK` nelle Dockerfile
- ❌ **Nessun resource limit** — Memory e CPU non limitati, rischio di OOM kill in produzione
- ❌ **Nessun logging driver** — I log vanno a stdout senza rotazione o aggregazione
- ⚠️ **Volume condiviso** — Tutti i servizi montano `./data` in lettura/scrittura, violando il principio di Least Privilege (Rule: Security §2)
- ⚠️ **Nessun `.dockerignore`** — Build context potrebbe includere `.venv`, `.git`, binari

### 4.2 Stato CI/CD

| Componente | Stato | Note |
|------------|-------|------|
| CI Pipeline | ❌ Assente | `draft_ci_pipeline.yml` esiste solo come plan |
| CD Pipeline | ❌ Assente | Nessun deployment automatico |
| Linting | ❌ Assente | Nessun linter configurato |
| Testing | 🟠 Minimo | 3 file di test (Go + Rust), nessun Python test |
| Code Coverage | ❌ Assente | Nessuna metrica di copertura |
| Vulnerability Scanning | ❌ Assente | Nessun scanner di dipendenze |

### 4.3 Testing Coverage

![Test Coverage Distribution — Go: 2 test files, Rust: 2 test files, Python: 0 test files](diagrams/diagram_12.png)

**Analisi Critica:** La distribuzione dei test rivela un'asimmetria allarmante: il linguaggio con la maggiore superficie di codice (Python, 39 file) ha zero test, mentre Go e Rust (con meno file) hanno almeno unit test di base. Questo è particolarmente critico perché Python è il linguaggio meno type-safe dei tre — Rust cattura errori a compile-time, Go ha static typing, ma Python senza test può nascondere TypeError, ValueError e bug logici fino al runtime in produzione.

**Dettaglio Test Esistenti:**

| File | Tipo | Componente Testato |
|------|------|-------------------|
| `recorder_test.go` | Unit | Pipeline Recorder |
| `rbac_test.go` | Unit | RBAC Middleware |
| `audit_tamper_test.rs` | Integration | Audit Trail tamper detection |
| `proptest_suite.rs` | Property-based | Domain invariants |

**Gap Critico:** Zero test per l'intero stack Python (39 file). Il `RiskManager` (safety-critical, 440 LOC) non ha nessun test unitario. Il `GoliathTransformer` ha solo un sanity check nel `__main__`, non un test formale.

---

## 🔍 SEZIONE 5: Technical Debt Inventory

### 5.1 Classificazione del Debito Tecnico

![Technical Debt Distribution — Missing Tests 40%, Error Handling 15%, Dead Code 15%, Feature Parity 10%, Hardcoding 10%, Stale Docs 10%](diagrams/diagram_13.png)

**Analisi della Distribuzione:** Il 40% del debito tecnico concentrato nei test mancanti conferma il pattern di "ricerca-first, validazione-later" tipico dei progetti di data science. Il secondo cluster (Error Handling 15% + Dead Code 15% = 30%) suggerisce un codebase in evoluzione rapida dove nuove feature vengono aggiunte senza pulire le vecchie. Il Feature Parity Drift (10%) è il debito più insidioso perché silenzioso: un modello ML che vede feature diverse in training e produzione degraderà le performance senza segnali espliciti di errore.

### 5.2 Inventario Dettagliato

| ID | Tipo | Descrizione | Impatto | Sforzo | Priorità |
|----|------|-------------|---------|--------|----------|
| TD-001 | Dead Code | `get_latest_data()` in `ask_oracle.py` non è usata | Basso | 5 min | P3 |
| TD-002 | Dead Import | `joblib` importato in `train_model.py` mai usato | Basso | 1 min | P4 |
| TD-003 | TODO | Signal API in `main.go` restituisce placeholder | **Alto** | 2-4h | **P0** |
| TD-004 | Duplication | Feature engineering duplicata tra 2 file Python | Medio | 2h | P1 |
| TD-005 | Hardcoding | `EURUSD` nel RiskManager invece di XAUUSD | Medio | 30 min | P1 |
| TD-006 | Missing Test | 0 test per 39 file Python di analysis | **Alto** | 16h+ | **P0** |
| TD-007 | Missing Test | 0 test per Ground_Zero (8 file) | **Alto** | 8h+ | **P0** |
| TD-008 | Config | Path assoluti hardcoded nei knowledge generators | Medio | 1h | P2 |
| TD-009 | Type Safety | `float64` per prezzi nel Go Recorder | Medio | 2h | P1 |
| TD-010 | PositionalEncoding | Classe mancante in `goliath_transformer.py` | **Alto** | 1h | **P0** |
| TD-011 | Backtest | Nessun SL/TP/commission nel BacktestEngine | **Alto** | 4h | P1 |
| TD-012 | Integration | Nessun ponte Python ↔ Go Gateway | **Alto** | 8h+ | **P0** |
| TD-013 | Monitoring | Metriche Prometheus/Grafana assenti | Medio | 4h | P2 |
| TD-014 | SBE | Schema SBE non integrato nel codice | Medio | 4h | P2 |

### 5.3 Grafo delle Dipendenze del Debito

![Technical Debt Dependency Graph — mostra come TD-003 (Signal API) blocca TD-012 (Integration) che a sua volta blocca TD-010 e TD-005](diagrams/diagram_14.png)

**Analisi delle Dipendenze del Debito:** Il grafo rivela una **catena critica** chiara: TD-003 (Signal API placeholder) → TD-012 (Python↔Go Integration) → TD-010 (PositionalEncoding). Questa catena rappresenta il **critical path** del progetto: senza risolvere il Signal API, l'integrazione è impossibile, e senza integrazione il GoliathTransformer (che richiede PositionalEncoding) non può essere validato end-to-end. Il ramo parallelo (TD-006 → TD-004, TD-009 → TD-014) può procedere indipendentemente.

---

## 🔍 SEZIONE 6: Maturity Matrix — Scorecard Globale

### 6.1 Radar Chart di Maturità

![Maturity Score Radar — Documentation 9/10, Architecture 7/10, ML/AI 6/10, Data Pipeline 6/10, Code Quality 5/10, Security 4/10, DevOps 3/10, Testing 2/10](diagrams/diagram_15.png)

**Interpretazione dello Score:** Il profilo di maturità è **fortemente asimmetrico** — eccellenza nella documentazione e architettura, ma debolezza critica nelle discipline operative (Testing, DevOps, Security). Questo è il profilo tipico di un progetto guidato da research engineers piuttosto che da production engineers. Lo score complessivo di **5.25/10** posiziona il sistema nella zona "non production-ready" — il passaggio a production richiede di colmare il gap operativo senza degradare i punti di forza esistenti.

### 6.2 Scorecard Dettagliata

| Dimensione | Score | Giudizio | Dettaglio |
|------------|-------|----------|-----------|
| **Architettura** | 7/10 | 🟢 Buona | Separazione polyglot (Go/Rust/Python) con pattern corretti. Microservizi ben delineati. Manca solo l'integrazione |
| **Code Quality** | 5/10 | 🟡 Media | Rust: eccellente (typestate, decimal). Python: variabile. Go: buono ma incompleto |
| **Testing** | 2/10 | 🔴 Critico | Solo 4 file di test su 70+ file sorgente. Zero test Python. Zero test Ground_Zero |
| **Security** | 4/10 | 🟠 Insufficiente | Good: secrets in .env, PII scrubber, RBAC. Bad: no auth su API, no TLS, no rate limit |
| **DevOps/CI** | 3/10 | 🔴 Critico | Docker funziona ma nessun CI/CD, nessun health check nativo, nessun monitoring |
| **Documentation** | 9/10 | 🟢 Eccellente | 111 documenti di knowledge base, 18 fasi tematiche, INDEX organizzato. Tra i migliori visti |
| **ML/AI** | 6/10 | 🟡 Buona | XGBoost funzionante, GoliathTransformer ben progettato, feature parity quasi verificata. Manca cross-validation e hyperparameter tuning |
| **Data Pipeline** | 6/10 | 🟡 Buona | Parquet per ticks (ottimo), CSV per storico, pipeline ETL presente. Manca validazione e schema enforcement |
| **MEDIA** | **5.25/10** | 🟡 | **Advanced Prototype — Non pronto per produzione** |

---

## 🔍 SEZIONE 7: Ricerca POMDP — Status Assessment

Nella directory `plans/` sono presenti **10 documenti di ricerca** sul framework POMDP (Partially Observable Markov Decision Process):

| Documento | LOC (bytes) | Focus |
|-----------|-------------|-------|
| `POMDP_Full_Research.md` | 32 KB | Documento completo integrale |
| `POMDP_Master_Chapter1-5.md` | ~32 KB totali | 5 capitoli master |
| `POMDP_Deep_Dive_Part1-4.md` | ~22 KB totali | 4 deep dive specializzati |

**Valutazione:** La ricerca POMDP rappresenta un'evoluzione significativa rispetto all'approccio XGBoost attuale. Il POMDP modella esplicitamente l'**osservabilità parziale** dei mercati finanziari — il fatto che lo stato reale del mercato (intenzioni degli istituzionali, flussi di liquidità nascosti) non è direttamente osservabile. Questa ricerca è un investimento a lungo termine che potrebbe portare a un vantaggio competitivo significativo se implementata correttamente.

**Gap con l'implementazione:** Attualmente nessun codice nel progetto implementa POMDP. La transizione da XGBoost (classificazione supervisionata) a POMDP (decisione sequenziale sotto incertezza) richiederebbe un redesign fondamentale del layer ML.

---

## 🔍 SEZIONE 8: Assessment Shell Scripts & Hardware

Nella directory temporanea sono presenti **8 shell scripts** per configurazione hardware e DevSecOps:

| Script | LOC | Scopo | Stato |
|--------|-----|-------|-------|
| `aggressive_fix_amd.sh` | ~40 | Fix driver AMD GPU | 🟡 One-shot |
| `fix_amd_install.sh` | ~45 | Install AMD GPU drivers | 🟡 One-shot |
| `fix_cooling.sh` | ~55 | Fix ventole/cooling | 🟡 One-shot |
| `fix_grub_acpi.sh` | ~35 | Fix GRUB ACPI | 🟡 One-shot |
| `install_amd_official.sh` | ~45 | AMD official driver install | 🟡 One-shot |
| `install_fan_driver.sh` | ~55 | Fan driver installation | 🟡 One-shot |
| `install_native_rocm.sh` | ~35 | ROCm for AMD GPU compute | 🟡 One-shot |
| `setup_devsecops.sh` | ~100 | Full DevSecOps setup | 🟡 Planned |
| `setup_hardware.sh` | ~90 | Hardware optimization | 🟡 Planned |

**Osservazione:** La presenza di script ROCm indica l'intenzione di usare AMD GPU per il training ML. Questo è un scelta non convenzionale (la maggior parte dell'industria usa NVIDIA/CUDA) che potrebbe creare friction con librerie come PyTorch (supporto ROCm ancora meno maturo).

---

## 📊 SEZIONE 9: Raccomandazioni Strategiche & Roadmap

### 9.1 Priority Matrix — Azioni Immediate

![8-Week Stabilization Roadmap Gantt Chart — P0 Critical (Week 1-2), P1 Important (Week 3-4), P2 Infrastructure (Week 5-6), P3 Evolution (Week 7-8)](diagrams/diagram_16_gantt.png)

> [!NOTE]
> La roadmap sopra è stata convertita in formato testuale poiché il diagramma Gantt Mermaid non era disponibile per rendering statico. Vedi la tabella seguente per il dettaglio temporale.

| Settimana | Priorità | Task | Durata |
|-----------|----------|------|--------|
| 1 | **P0** | Fix PositionalEncoding import | 1 giorno |
| 1 | **P0** | Auth su Signal API (JWT/API Key) | 2 giorni |
| 1-2 | **P0** | Python Test Suite base (RiskCalc, Backtest, Goliath) | 5 giorni |
| 2-3 | **P0** | Python ↔ Go Integration (gRPC/REST) | 5 giorni |
| 3 | P1 | Feature Engineering unificata | 2 giorni |
| 3-4 | P1 | BacktestEngine SL/TP/Commissions | 3 giorni |
| 4 | P1 | float64 → Decimal nel Go + RiskManager XAUUSD | 3 giorni |
| 5-6 | P2 | CI/CD Pipeline + Prometheus/Grafana | 6 giorni |
| 5-6 | P2 | SBE Integration | 3 giorni |
| 7-8 | P3 | POMDP Prototype + Walk-Forward + HyperTuning | 20 giorni |

### 9.2 Raccomandazioni Dettagliate

#### 🔴 Priorità 0 — Fix Bloccanti

1. **Fix `PositionalEncoding` import** — La classe manca in `goliath_transformer.py`. Senza di essa, il modello non può girare. Implementare la sinusoidal PE standard o importarla dal modulo corretto.

2. **Autenticazione Signal API** — Aggiungere JWT o API key su `/api/signal/`. Senza questo, chiunque sulla rete può leggere i segnali di trading.

3. **Test Suite Python** — Creare almeno test per: `RiskCalculator`, `BacktestEngine`, `GoliathTransformer` forward pass, `feature_engineering` pipeline. Target minimo: 60% coverage sui file critici.

4. **Integrazione Python ↔ Go** — Implementare il collegamento tra Go Gateway e Python Analysis. Opzioni: gRPC, HTTP REST, o Redis Pub/Sub.

#### 🟠 Priorità 1 — Stabilizzazione

1. **Unificare Feature Engineering** — Estrarre la logica comune di `feature_engineering.py` e `ask_oracle.py` in un modulo `features/` condiviso. Un singolo source of truth per il calcolo delle feature.

2. **BacktestEngine Professionale** — Aggiungere: Stop Loss, Take Profit, commissioni, slippage, drawdown tracking, Sharpe Ratio, Profit Factor. Il backtest attuale è un PoC, non uno strumento decisionale.

3. **Correzione tipi monetari** — Migrare `float64` nel Go Recorder a `int64` (micropips) o `Decimal`. Allineare con `rust_decimal` del Rust Engine.

#### 🟡 Priorità 2 — Infrastruttura

1. **CI/CD Pipeline** — GitHub Actions con: lint (golangci-lint, clippy, ruff), test, build Docker, scan vulnerabilità (Snyk/Trivy).

2. **Monitoring Stack** — Prometheus per metriche + Grafana per dashboard. Esporre metriche da Go Gateway (request latency, tick rate, buffer fill %).

#### 🟢 Priorità 3 — Evoluzione

1. **Prototipo POMDP** — Implementare un agent POMDP minimale che opera sulle stesse feature dell'XGBoost attuale, per confronto diretto.

### 9.3 Architettura Target (To-Be)

![Target Architecture v2.0 — sistema integrato con Auth, TLS, Unified Feature Engine, multi-model intelligence (XGBoost + Goliath + POMDP), e monitoring stack](diagrams/diagram_17_target.png)

> [!IMPORTANT]
> L'architettura target v2.0 rappresenta la visione a medio termine (3-6 mesi). I cambiamenti chiave rispetto allo stato attuale sono:
>
> - **Gateway v2:** Aggiunta di autenticazione (JWT), TLS, rate limiting, e prezzi in `int64` con timestamp a nanosecondi
> - **Unified Feature Engine:** Unico punto di calcolo feature condiviso da tutti i modelli, eliminando il Feature Parity Drift
> - **Multi-Model Intelligence:** XGBoost (baseline), GoliathTransformer (deep learning), POMDP Agent (reinforcement learning) alimentano tutti il RiskManager v2
> - **Observability Stack:** Prometheus + Grafana + Structured JSON Logs per visibility completa

**Nota:** I diagrammi Gantt e Target Architecture sono stati convertiti in formato tabellare/testuale dove il rendering PNG diretto non era disponibile. Tutti gli altri 15 diagrammi sono stati renderizzati come immagini PNG ad alta risoluzione nella directory `diagrams/`.

---

## 📋 Appendice A: File Inventory Completo

### Ground_Zero

| Path | Tipo | LOC | Stato |
|------|------|-----|-------|
| `src/backtest/engine.py` | Core | 74 | 🟠 MVP |
| `src/connectors/fetch_history.py` | Connector | 46 | 🟢 OK |
| `src/connectors/tv_bridge.py` | Connector | 49 | 🟢 OK |
| `src/core/data_manager.py` | Core | 53 | 🟡 Limitato |
| `src/models/feature_engineering.py` | ML | 91 | 🟢 Solido |
| `src/models/train_model.py` | ML | 76 | 🟢 OK |
| `src/tools/ask_oracle.py` | Tool | 142 | 🟡 Rischi |
| `src/market_monitor.py` | Tool | 74 | 🟢 OK |
| `mcp_servers/fred_server.py` | MCP | 48 | 🟢 OK |
| `mcp_servers/fmp_server.py` | MCP | 31 | 🟢 OK |
| `mcp_servers/brave_server.py` | MCP | 53 | 🟢 OK |
| `knowledge_factory/generate_history_reports.py` | Gen | 109 | 🟢 OK |
| `knowledge_factory/generate_mining_reports.py` | Gen | 69 | 🟢 OK |

### BOT_TRADING (Selezione Chiave)

| Path | Tipo | LOC | Stato |
|------|------|-----|-------|
| `gateway/cmd/gateway/main.go` | Go | 80 | 🟡 TODO |
| `gateway/internal/pipeline/recorder.go` | Go | 170 | 🟢 Solido |
| `gateway/internal/middleware/rbac.go` | Go | ~50 | 🟢 OK |
| `gateway/internal/middleware/pii.go` | Go | ~40 | 🟢 OK |
| `engine/src/lib.rs` | Rust | 5 | 🟢 Stub |
| `engine/src/domain/` | Rust | ~300 | 🟢 Solido |
| `engine/src/matching/` | Rust | ~200 | 🟢 Solido |
| `engine/src/risk/` | Rust | ~400 | 🟢 Solido |
| `engine/src/audit.rs` | Rust | ~100 | 🟢 Solido |
| `analysis/src/ml/models/goliath_transformer.py` | ML | 126 | 🟠 Bug |
| `analysis/src/quant/risk_manager.py` | Quant | 440 | 🟢 Maturo |
| `analysis/src/quant/hft_features.py` | Quant | ~200 | 🟡 OK |
| `analysis/src/ml/train_hft_v3.py` | ML | ~300 | 🟡 OK |

---

## 📋 Appendice B: Glossario Tecnico

| Termine | Definizione |
|---------|------------|
| **SBE** | Simple Binary Encoding — protocollo di serializzazione a bassa latenza per messaggistica finanziaria |
| **POMDP** | Partially Observable Markov Decision Process — framework decisionale sotto incertezza |
| **Typestate Pattern** | Pattern Rust che usa il type system per codificare stati validi a compile-time |
| **Circuit Breaker** | Pattern di resilienza che apre il circuito dopo N fallimenti consecutivi |
| **Backpressure** | Meccanismo per rallentare il producer quando il consumer è sovraccarico |
| **Feature Parity** | Garanzia che le feature calcolate in training siano identiche a quelle in produzione |
| **Walk-Forward Validation** | Tecnica di cross-validation temporale per serie storiche |
| **Kelly Criterion** | Formula matematica per il position sizing ottimale basato su probabilità e payoff |
| **Death Spiral** | Cascata di liquidazioni forzate che amplifica i movimenti di prezzo |
| **PII Scrubber** | Componente che rimuove dati personali identificabili dalle risposte |

---

*Questo documento è fatto da Renan Augusto Macena per conto di Alex Cupsa — 14 Febbraio 2026*
*Versione 1.0*
