# GOLIATH: Autonomous Quantitative Trading Ecosystem
## Master Technical Whitepaper & Roadmap v2.0

**Data:** 6 Febbraio 2026  
**Autore:** Gemini Agent (System Architect)  
**Versione:** 2.0.1  
**Stato Progetto:** Alpha Operativa (Infrastruttura Convalidata)

---

# 1. Executive Summary e Stato dell'Arte

Il progetto GOLIATH rappresenta un'architettura di trading algoritmico ibrida ad alta frequenza (HFT) e machine learning (ML), progettata per superare i limiti delle piattaforme retail standard. A differenza dei tradizionali Expert Advisor (EA) che eseguono logica e calcoli all'interno di MetaTrader, GOLIATH adotta un approccio a **microservizi distribuiti**.

### 1.1 Analisi dello Stato Attuale
Attualmente, il sistema ha superato la fase di "Proof of Concept" (PoC) per i componenti infrastrutturali critici.

*   **Frontend (MQL5):** Agisce come "Dumb Pipe". Non "pensa", trasmette solo dati di mercato grezzi (Tick) e riceve ordini di esecuzione. Questo minimizza la latenza interna di MT5.
*   **Gateway (Go):** Funziona come collettore ad alte prestazioni. Gestisce la connessione TCP, decodifica il protocollo binario SBE (Simple Binary Encoding) e scrive i dati su disco in formato Parquet (colonanre), ideale per l'analisi big data.
*   **Core (Rust):** Il motore di esecuzione e rischio è scritto in Rust per garantire la "Memory Safety" e velocità vicine al metallo. I moduli di audit e validazione matematica sono completi.
*   **Brain (Python):** Il modulo di analisi contiene algoritmi avanzati (Fractional Differencing, Triple Barrier Method) ma attualmente gira su dati sintetici ("dummy loop").

**Verdetto:** L'autostrada dei dati è costruita. Ora bisogna far circolare le macchine (i dati reali) e addestrare il pilota (la rete neurale).

---

# 2. Architettura del Flusso Dati (Data Pipeline)

Questa sezione risponde alla necessità critica di acquisire e immagazzinare dati per l'addestramento su molteplici asset.

### 2.1 Il Protocollo SBE (Simple Binary Encoding)
Non usiamo JSON o CSV in transito. Usiamo SBE.
*   **Perché:** Un tick JSON pesa ~150 byte e richiede parsing costoso (CPU). Un tick SBE pesa <50 byte e si mappa direttamente in memoria.
*   **Struttura del Pacchetto:**
    *   `Header`: BlockLength, TemplateID, SchemaID, Version.
    *   `Body`: SymbolID (int64), Timestamp (int64), Bid/Ask/Vol (int64 - prezzi normalizzati per evitare float errors).

### 2.2 Strategia Multi-Asset su MetaTrader 5
Per monitorare 10, 20 o 50 asset contemporaneamente senza crashare MT5:
1.  **Market Watch Loop:** L'EA `Bridge.mq5` non deve essere attaccato a 50 grafici. Deve girare su **UN SOLO** grafico (es. EURUSD) ma usare `OnTimer` o `OnBookEvent` per iterare su una lista di simboli definiti nel "Market Watch".
2.  **Multiplexing:** Ogni pacchetto inviato al Gateway contiene un `SymbolID`.
    *   Es. `1 = EURUSD`, `2 = BTCUSD`, `3 = GOLD`.
    *   Il Gateway Go riceve il flusso misto e lo smista.

### 2.3 Storage: Dal "Data Lake" al "Feature Store"
L'archiviazione avviene in tre stadi (Medallion Architecture):

1.  **Bronze Layer (Raw Logs):**
    *   Il Gateway Go scrive file `.sbe` grezzi (append-only). È la "scatola nera" in caso di disastri.
    *   *Posizione:* `data/raw/`

2.  **Silver Layer (Structured Parquet):**
    *   Ogni 15 minuti (o 100MB), il Gateway Go ruota il file e converte i dati in **Apache Parquet**.
    *   *Vantaggio:* Parquet è colonnare. Se la rete neurale serve solo il "Bid", legge solo quella colonna, ignorando il resto. Compressione 10x rispetto al CSV.
    *   *Schema:* `Timestamp, SymbolID, Bid, Ask, Volume, Flags`.
    *   *Posizione:* `data/parquet/`

3.  **Gold Layer (Feature Store - Python):**
    *   Qui entra in gioco il modulo Python. Legge i Parquet e calcola le feature complesse (RSI, Volatilità, FracDiff).
    *   Salva i tensori pronti per PyTorch/TensorFlow.

---

# 3. La Strategia di Machine Learning (Il "Cervello")

Per addestrare la rete a determinare Entry, Take Profit (TP) e Stop Loss (SL) ottimali, non usiamo la predizione del prezzo (che è rumore), ma la classificazione delle probabilità.

### 3.1 Feature Engineering Avanzata
Nel file `features.py` abbiamo implementato concetti istituzionali:

*   **Fractional Differencing (FracDiff):**
    *   *Problema:* I prezzi non sono stazionari (la media cambia), ma se fai la differenza (Prezzo oggi - Prezzo ieri) per renderli stazionari, cancelli la memoria del trend.
    *   *Soluzione:* FracDiff differenzia solo "una frazione" (es. 0.4). Mantiene la stazionarietà E la memoria storica. **Cruciale per le reti neurali.**

*   **Ortogonalizzazione (PCA):**
    *   Indicatori come RSI e MACD sono spesso correlati. Usiamo la PCA per pulire i dati e dare alla rete input non ridondanti.

### 3.2 Il Metodo delle Tre Barriere (Triple Barrier Method)
Come definiamo se un trade è "buono" per il training?
Non basta dire "il prezzo è salito".
Ogni trade ha 3 limiti:
1.  **Barriera Superiore (TP):** Profitto desiderato (es. +2%).
2.  **Barriera Inferiore (SL):** Perdita massima (es. -1%).
3.  **Barriera Verticale (Tempo):** Tempo massimo di hold (es. 1 ora).

**Labeling:**
*   Se tocca TP per primo -> Label `1` (Buy).
*   Se tocca SL per primo -> Label `-1` (Sell/Avoid).
*   Se tocca Tempo -> Label `0` (Exit Flat).

La rete neurale non impara "quanto varrà Bitcoin", impara **"Qual è la probabilità di toccare la barriera superiore prima di quella inferiore?"**.

---

# 4. Roadmap di Implementazione

Ecco la guida passo-passo per i prossimi sviluppi.

### FASE 1: Consolidamento Acquisizione Dati (Settimane 1-2)
**Obiettivo:** Creare un dataset storico solido di almeno 3-6 mesi su 5 asset diversi.

1.  **Modifica EA (MQL5):** Aggiornare `Bridge.mq5` per ciclare su una lista di simboli (Array `string Symbols[]`) invece di leggere solo il simbolo corrente.
2.  **Go Recorder:** Verificare che il Gateway crei file Parquet separati per giorno o partizionati per `SymbolID`.
3.  **Azione Utente:** Lasciare MT5 aperto 24/7 per popolare la cartella `data/`.

### FASE 2: La Fabbrica delle Features (Settimane 3-4)
**Obiettivo:** Trasformare i dati grezzi in input per la AI.

1.  **Pipeline Python:** Scrivere uno script `etl_pipeline.py` che:
    *   Carica i file Parquet accumulati.
    *   Applica `fractional_differencing` e `triple_barrier_labels` (già presenti in `features.py`).
    *   Salva il risultato in un formato `.npz` (NumPy compresso) pronto per il training.

### FASE 3: Training del Modello (Settimane 5-6)
**Obiettivo:** Addestrare la prima LSTM/Transformer.

1.  **Architettura Rete:**
    *   Input: Finestra di 60 tick (o candele) con feature FracDiff.
    *   Hidden Layers: 2 layer LSTM o Temporal Convolutional Network (TCN).
    *   Output: Softmax su 3 classi (Buy, Sell, Hold).
2.  **Backtesting:** Usare il modulo Rust (che è velocissimo) per simulare l'esecuzione dei segnali generati dal modello Python sui dati passati.

### FASE 4: Loop in Tempo Reale (Live Trading)
**Obiettivo:** Connettere il cervello ai muscoli.

1.  **Inference Server:** Il modello Python deve esporre una API (es. via ZeroMQ o gRPC) che accetta lo stato attuale del mercato e restituisce la probabilità.
2.  **Rust Execution:** L'engine Rust riceve il tick dal Gateway -> interroga Python -> se probabilità > 80% -> invia ordine a MT5.

---

# 5. Istruzioni Operative per l'Utente

### Come procedere ORA:
1.  **Data Mining:** Avviare MT5 con il bridge. Assicurarsi di avere dati storici di qualità (anche scaricandoli dal broker).
2.  **Monitoraggio:** Usare `python dashboard.py` per verificare che i tick arrivino.
3.  **Espansione Asset:** Modificare l'input dell'EA per includere `EURUSD`, `GBPUSD`, `XAUUSD`, `BTCUSD`.

### Come allenare le reti (Futuro Prossimo):
Una volta accumulati 1GB+ di dati Parquet:
```python
# Pseudo-codice del workflow futuro
dataset = load_parquet("data/*.parquet")
features = apply_frac_diff(dataset)
labels = apply_triple_barrier(dataset, tp=0.02, sl=0.01)
model = train_lstm(features, labels)
model.save("brain_v1.pth")
```

Questo documento costituisce la "Stella Polare" per lo sviluppo di GOLIATH. L'infrastruttura è pronta; ora si passa alla scienza dei dati.
