#!/usr/bin/env bash
# =============================================================================
# GOLIATH Console di Training v1.0
# =============================================================================
# GUI terminale per training ibrido GPU+CPU, test decisioni e backtest.
# Richiede: whiptail, python3 con PyTorch
#
# Uso: ./scripts/goliath_trainer_gui.sh
# =============================================================================

set -euo pipefail

VERSION="1.0"

# --- Percorsi ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="$PROJECT_ROOT/logs"
CHECKPOINT_DIR="$PROJECT_ROOT/analysis/models_checkpoint"

mkdir -p "$LOG_DIR" "$CHECKPOINT_DIR"

# --- Python ---
if [ -f "$PROJECT_ROOT/bin/python3" ]; then
    PYTHON="$PROJECT_ROOT/bin/python3"
elif command -v python3 &>/dev/null; then
    PYTHON="python3"
else
    echo "ERRORE: python3 non trovato!" >&2
    exit 1
fi

export PYTHONPATH="$PROJECT_ROOT:$PROJECT_ROOT/analysis${PYTHONPATH:+:$PYTHONPATH}"

# --- Colori (per output console) ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# --- Dimensioni terminale ---
TERM_H=$(tput lines 2>/dev/null || echo 24)
TERM_W=$(tput cols 2>/dev/null || echo 80)
WT_H=$((TERM_H - 4))
WT_W=$((TERM_W - 10))
[ "$WT_H" -lt 20 ] && WT_H=20
[ "$WT_W" -lt 60 ] && WT_W=70

# --- Cache hardware ---
GPU_INFO=""
GPU_DETECTED=false

# =============================================================================
# UTILITY
# =============================================================================

log_msg() {
    local ts
    ts="$(date '+%Y-%m-%d %H:%M:%S')"
    echo -e "${CYAN}[$ts]${NC} $1"
    echo "[$ts] $1" >> "$LOG_DIR/gui_session.log"
}

check_whiptail() {
    if ! command -v whiptail &>/dev/null; then
        echo -e "${RED}ERRORE: whiptail non installato.${NC}"
        echo "Installa con: sudo apt install whiptail"
        exit 1
    fi
}

timestamp_file() {
    echo "$LOG_DIR/$(date '+%Y%m%d_%H%M%S')_$1.log"
}

run_with_log() {
    local label="$1"
    shift
    local logfile
    logfile="$(timestamp_file "$label")"
    log_msg "Avvio: $* → $logfile"
    (cd "$PROJECT_ROOT" && "$@" 2>&1 | tee "$logfile")
    local rc=${PIPESTATUS[0]}
    if [ "$rc" -eq 0 ]; then
        log_msg "${GREEN}Completato: $label${NC}"
    else
        log_msg "${RED}Fallito ($rc): $label${NC}"
    fi
    return "$rc"
}

run_with_log_bg() {
    local label="$1"
    shift
    local logfile
    logfile="$(timestamp_file "$label")"
    log_msg "Avvio in background: $* → $logfile"
    (cd "$PROJECT_ROOT" && "$@" > "$logfile" 2>&1) &
    echo "$!"
}

show_log_tail() {
    local logfile="$1"
    local title="${2:-Log}"
    if [ -f "$logfile" ]; then
        whiptail --title "$title" --scrolltext --textbox "$logfile" "$WT_H" "$WT_W"
    else
        whiptail --title "Errore" --msgbox "File non trovato:\n$logfile" 10 50
    fi
}

# =============================================================================
# RILEVAMENTO HARDWARE
# =============================================================================

detect_hardware() {
    GPU_INFO=$($PYTHON -c "
import torch, os, platform

# GPU
if torch.cuda.is_available():
    name = torch.cuda.get_device_name(0)
    vram = torch.cuda.get_device_properties(0).total_memory / 1e9
    backend = 'ROCm' if ('AMD' in name or 'Radeon' in name) else 'CUDA'
    print(f'GPU: {name} ({vram:.1f} GB VRAM) — {backend}')
    print(f'GPU_OK=1')
else:
    print('GPU: Nessuna GPU rilevata (solo CPU)')
    print('GPU_OK=0')

# PyTorch
print(f'PyTorch: {torch.__version__}')

# CPU
cores = os.cpu_count() or 1
print(f'Core CPU: {cores}')

# RAM
try:
    with open('/proc/meminfo') as f:
        mem = int(f.readline().split()[1]) / 1024 / 1024
    print(f'RAM: {mem:.1f} GB')
except:
    print('RAM: N/D')

# OS
print(f'OS: {platform.system()} {platform.release()}')
" 2>/dev/null || echo "ERRORE: Impossibile rilevare hardware")

    if echo "$GPU_INFO" | grep -q "GPU_OK=1"; then
        GPU_DETECTED=true
    else
        GPU_DETECTED=false
    fi
}

check_dependencies() {
    $PYTHON -c "
import importlib, sys

deps = {
    'torch': 'PyTorch',
    'numpy': 'NumPy',
    'pandas': 'Pandas',
    'polars': 'Polars',
    'sklearn': 'Scikit-learn',
    'loguru': 'Loguru',
}

optional = {
    'lightgbm': 'LightGBM',
    'xgboost': 'XGBoost',
    'tensorboard': 'TensorBoard',
}

ok = True
for mod, name in deps.items():
    try:
        importlib.import_module(mod)
        print(f'  [OK] {name}')
    except ImportError:
        print(f'  [!!] {name} — MANCANTE')
        ok = False

print()
for mod, name in optional.items():
    try:
        importlib.import_module(mod)
        print(f'  [OK] {name} (opzionale)')
    except ImportError:
        print(f'  [--] {name} (opzionale, non installato)')

if not ok:
    sys.exit(1)
" 2>&1
}

check_data() {
    $PYTHON -c "
import glob, os

data_dir = '$PROJECT_ROOT/data'
parquet = glob.glob(os.path.join(data_dir, '**/*.parquet'), recursive=True)
csv_files = glob.glob(os.path.join(data_dir, '**/*.csv'), recursive=True)

total = len(parquet) + len(csv_files)
if total > 0:
    print(f'Dati: {len(parquet)} file parquet, {len(csv_files)} file CSV')
else:
    print('Dati: NESSUN FILE trovato in data/')
    print('  Aggiungi file .parquet o .csv nella cartella data/')
" 2>&1
}

# =============================================================================
# MENU: CONTROLLO SISTEMA
# =============================================================================

menu_system_check() {
    log_msg "Avvio controllo sistema..."

    local info=""

    # Hardware
    detect_hardware
    info+="━━━ HARDWARE ━━━\n"
    info+=$(echo "$GPU_INFO" | grep -v "GPU_OK=")
    info+="\n\n"

    # Dipendenze
    info+="━━━ DIPENDENZE ━━━\n"
    local deps_out
    deps_out=$(check_dependencies 2>&1) || true
    info+="$deps_out\n\n"

    # Dati
    info+="━━━ DATI ━━━\n"
    local data_out
    data_out=$(check_data 2>&1) || true
    info+="$data_out\n\n"

    # Checkpoint
    info+="━━━ MODELLI ━━━\n"
    if [ -d "$CHECKPOINT_DIR" ]; then
        local n_ckpt
        n_ckpt=$(find "$CHECKPOINT_DIR" -name "*.pth" -o -name "*.joblib" 2>/dev/null | wc -l)
        info+="Checkpoint trovati: $n_ckpt\n"
    else
        info+="Nessun checkpoint\n"
    fi

    # Mostra risultato
    echo -e "$info" > "/tmp/goliath_syscheck.txt"
    whiptail --title "Controllo Sistema GOLIATH" --scrolltext \
        --textbox "/tmp/goliath_syscheck.txt" "$WT_H" "$WT_W"
}

# =============================================================================
# MENU: TRAINING
# =============================================================================

menu_train() {
    while true; do
        local choice
        choice=$(whiptail --title "Addestra Modelli" \
            --menu "Seleziona modalita di training:" "$WT_H" "$WT_W" 8 \
            "1" "Test Rapido (5 epoche — validazione)" \
            "2" "Goliath Base (10 epoche su GPU)" \
            "3" "HFT v3 Pro (15 epoche, OneCycleLR)" \
            "4" "Settimana Intensiva (100 epoche, mixed prec.)" \
            "5" "Continuo 24/7 (daemon)" \
            "6" "Ibrido GPU+CPU (neurale + alberi in parallelo)" \
            "0" "← Indietro" \
            3>&1 1>&2 2>&3) || break

        case "$choice" in
            1)
                whiptail --title "Test Rapido" --yesno \
                    "Avviare training di test (5 epoche)?\n\nUtile per verificare che tutto funzioni." \
                    10 50 || continue
                run_with_log "test_rapido" \
                    $PYTHON analysis/goliath_trainer_v2.py --mode=test || true
                show_log_tail "$(ls -t "$LOG_DIR"/????????_??????_test_rapido.log 2>/dev/null | head -1)" \
                    "Risultati Test Rapido"
                ;;
            2)
                whiptail --title "Goliath Base" --yesno \
                    "Avviare training base GoliathTransformer?\n\n- 10 epoche\n- Auto-detect GPU/CPU" \
                    12 50 || continue
                run_with_log "goliath_base" \
                    $PYTHON analysis/train_goliath.py || true
                show_log_tail "$(ls -t "$LOG_DIR"/????????_??????_goliath_base.log 2>/dev/null | head -1)" \
                    "Risultati Goliath Base"
                ;;
            3)
                whiptail --title "HFT v3 Pro" --yesno \
                    "Avviare training HFT Pro v3?\n\n- 15 epoche\n- OneCycleLR scheduler\n- Etichette dinamiche" \
                    14 50 || continue
                run_with_log "hft_v3_pro" \
                    $PYTHON analysis/src/ml/train_hft_v3.py || true
                show_log_tail "$(ls -t "$LOG_DIR"/????????_??????_hft_v3_pro.log 2>/dev/null | head -1)" \
                    "Risultati HFT v3 Pro"
                ;;
            4)
                whiptail --title "Settimana Intensiva" --yesno \
                    "Avviare training intensivo?\n\n- 100 epoche per sessione\n- Mixed precision (FP16)\n- TensorBoard attivo\n- Target: 80% accuratezza\n\nATTENZIONE: processo lungo!" \
                    16 55 || continue
                run_with_log "settimana_intensiva" \
                    $PYTHON analysis/goliath_trainer_v2.py --mode=week || true
                show_log_tail "$(ls -t "$LOG_DIR"/????????_??????_settimana_intensiva.log 2>/dev/null | head -1)" \
                    "Risultati Settimana Intensiva"
                ;;
            5)
                whiptail --title "Continuo 24/7" --yesno \
                    "Avviare training continuo?\n\nIl processo girera in background finche non viene fermato.\nUsa Ctrl+C per interrompere." \
                    12 55 || continue
                run_with_log "continuo" \
                    $PYTHON analysis/goliath_trainer_v2.py --mode=continuous || true
                ;;
            6)
                run_hybrid_training
                ;;
            0) break ;;
        esac
    done
}

# =============================================================================
# TRAINING IBRIDO GPU+CPU
# =============================================================================

run_hybrid_training() {
    whiptail --title "Training Ibrido GPU+CPU" --yesno \
        "Avviare training ibrido?\n\n\
GPU → GoliathTransformer (Settimana Intensiva, 100 epoche)\n\
CPU → LightGBM + XGBoost (alberi decisionali)\n\n\
I due processi girano IN PARALLELO per\n\
massimizzare l'uso dell'hardware." \
        16 60 || return

    log_msg "Avvio training ibrido GPU+CPU..."

    local gpu_log cpu_log
    gpu_log="$(timestamp_file "ibrido_gpu")"
    cpu_log="$(timestamp_file "ibrido_cpu")"

    # Avvia GPU training in background
    log_msg "Avvio training GPU (Settimana Intensiva)..."
    (cd "$PROJECT_ROOT" && $PYTHON analysis/goliath_trainer_v2.py --mode=week > "$gpu_log" 2>&1) &
    local GPU_PID=$!

    # Avvia CPU training in background
    log_msg "Avvio training CPU (LightGBM + XGBoost)..."
    (cd "$PROJECT_ROOT" && $PYTHON scripts/train_cpu_models.py > "$cpu_log" 2>&1) &
    local CPU_PID=$!

    log_msg "PID GPU: $GPU_PID | PID CPU: $CPU_PID"

    # Monitor loop con gauge
    local gpu_status="In corso" cpu_status="In corso"
    local pct=0

    while true; do
        # Controlla stato processi
        if ! kill -0 "$GPU_PID" 2>/dev/null; then
            wait "$GPU_PID" 2>/dev/null && gpu_status="Completato" || gpu_status="ERRORE"
            GPU_PID=0
        fi
        if ! kill -0 "$CPU_PID" 2>/dev/null; then
            wait "$CPU_PID" 2>/dev/null && cpu_status="Completato" || cpu_status="ERRORE"
            CPU_PID=0
        fi

        # Estrai ultima riga di log
        local gpu_last cpu_last
        gpu_last=$(tail -1 "$gpu_log" 2>/dev/null | head -c 70 || echo "Attesa...")
        cpu_last=$(tail -1 "$cpu_log" 2>/dev/null | head -c 70 || echo "Attesa...")

        # Calcola progresso approssimativo
        if [ "$gpu_status" = "Completato" ] && [ "$cpu_status" = "Completato" ]; then
            pct=100
        elif [ "$gpu_status" != "In corso" ] || [ "$cpu_status" != "In corso" ]; then
            pct=75
        else
            # Stima dal numero di righe nel log GPU
            local n_lines
            n_lines=$(wc -l < "$gpu_log" 2>/dev/null || echo 0)
            pct=$((n_lines / 5))
            [ "$pct" -gt 95 ] && pct=95
        fi

        # Mostra infobox
        whiptail --title "Training Ibrido — Monitoraggio" \
            --infobox "\
Training GPU [$gpu_status]\n\
  $gpu_last\n\
\n\
Training CPU [$cpu_status]\n\
  $cpu_last\n\
\n\
Progresso stimato: ${pct}%\n\
\n\
(Attendere... aggiornamento ogni 5 secondi)" 16 "$WT_W"

        # Esci se entrambi completati
        if [ "$GPU_PID" -eq 0 ] && [ "$CPU_PID" -eq 0 ]; then
            break
        fi

        sleep 5
    done

    # Mostra risultati
    local summary=""
    summary+="━━━ RISULTATI TRAINING IBRIDO ━━━\n\n"
    summary+="GPU ($gpu_status):\n"
    summary+="$(tail -20 "$gpu_log" 2>/dev/null || echo 'Nessun log')\n\n"
    summary+="CPU ($cpu_status):\n"
    summary+="$(tail -20 "$cpu_log" 2>/dev/null || echo 'Nessun log')\n\n"
    summary+="Log GPU: $gpu_log\n"
    summary+="Log CPU: $cpu_log\n"

    echo -e "$summary" > "/tmp/goliath_hybrid_result.txt"
    whiptail --title "Risultati Training Ibrido" --scrolltext \
        --textbox "/tmp/goliath_hybrid_result.txt" "$WT_H" "$WT_W"
}

# =============================================================================
# MENU: TEST DECISIONI
# =============================================================================

menu_decision_test() {
    whiptail --title "Test Decisioni" --yesno \
        "Avviare la suite di test?\n\n\
1. Libreria Indicatori (100+ indicatori)\n\
2. Risk Manager (dimensionamento posizioni)\n\
3. Neural Trader (predizioni)\n\
4. Simulazione trading completa (10 operazioni)" \
        16 55 || return

    log_msg "Avvio test decisioni..."
    run_with_log "test_decisioni" \
        $PYTHON scripts/tools/test_bot.py || true
    show_log_tail "$(ls -t "$LOG_DIR"/????????_??????_test_decisioni.log 2>/dev/null | head -1)" \
        "Risultati Test Decisioni"
}

# =============================================================================
# MENU: BACKTEST
# =============================================================================

menu_backtest() {
    # Selezione strategia
    local strategy
    strategy=$(whiptail --title "Backtest" \
        --menu "Seleziona strategia:" 14 50 3 \
        "breakout" "Strategia Breakout (Bollinger Bands)" \
        "grid"     "Strategia Grid (livelli fissi)" \
        3>&1 1>&2 2>&3) || return

    # Simbolo
    local symbol
    symbol=$(whiptail --title "Backtest" \
        --inputbox "Simbolo (es. BTCUSD, EURUSD):" 10 50 "BTCUSD" \
        3>&1 1>&2 2>&3) || return

    # Giorni
    local days
    days=$(whiptail --title "Backtest" \
        --inputbox "Giorni di storico:" 10 50 "30" \
        3>&1 1>&2 2>&3) || return

    whiptail --title "Backtest" --yesno \
        "Conferma backtest:\n\nStrategia: $strategy\nSimbolo: $symbol\nGiorni: $days" \
        12 50 || return

    log_msg "Avvio backtest: $strategy su $symbol ($days giorni)"
    run_with_log "backtest_${strategy}" \
        $PYTHON backtest.py --strategy "$strategy" --symbol "$symbol" --days "$days" || true
    show_log_tail "$(ls -t "$LOG_DIR"/????????_??????_backtest_*.log 2>/dev/null | head -1)" \
        "Risultati Backtest — $strategy $symbol"
}

# =============================================================================
# MENU: MONITOR
# =============================================================================

menu_monitor() {
    while true; do
        local choice
        choice=$(whiptail --title "Monitora Training" \
            --menu "Seleziona azione:" "$WT_H" "$WT_W" 5 \
            "1" "Visualizza ultimo log" \
            "2" "Lancia TensorBoard (porta 6006)" \
            "3" "Lista checkpoint salvati" \
            "4" "Visualizza log specifico" \
            "0" "← Indietro" \
            3>&1 1>&2 2>&3) || break

        case "$choice" in
            1)
                local latest
                latest=$(ls -t "$LOG_DIR"/*.log 2>/dev/null | head -1)
                if [ -n "$latest" ]; then
                    show_log_tail "$latest" "Ultimo Log: $(basename "$latest")"
                else
                    whiptail --title "Monitor" --msgbox "Nessun log trovato in:\n$LOG_DIR" 10 50
                fi
                ;;
            2)
                local tb_dir="$PROJECT_ROOT/analysis/runs"
                if command -v tensorboard &>/dev/null; then
                    # Chiudi eventuali istanze precedenti
                    pkill -f "tensorboard.*--logdir.*$tb_dir" 2>/dev/null || true
                    sleep 1
                    tensorboard --logdir "$tb_dir" --port 6006 --bind_all &>/dev/null &
                    whiptail --title "TensorBoard" --msgbox \
                        "TensorBoard avviato!\n\nApri nel browser:\n  http://localhost:6006\n\nPID: $!" 12 50
                else
                    whiptail --title "TensorBoard" --msgbox \
                        "TensorBoard non installato.\n\nInstalla con:\n  pip install tensorboard" 10 50
                fi
                ;;
            3)
                local ckpt_list
                ckpt_list=$(ls -lh "$CHECKPOINT_DIR"/*.pth "$CHECKPOINT_DIR"/*.joblib 2>/dev/null \
                    | awk '{print $NF, $5}' || echo "Nessun checkpoint trovato")
                echo "$ckpt_list" > "/tmp/goliath_ckpts.txt"
                whiptail --title "Checkpoint Salvati" --scrolltext \
                    --textbox "/tmp/goliath_ckpts.txt" "$WT_H" "$WT_W"
                ;;
            4)
                local files
                files=$(ls -t "$LOG_DIR"/*.log 2>/dev/null | head -10)
                if [ -z "$files" ]; then
                    whiptail --title "Monitor" --msgbox "Nessun log trovato." 8 40
                    continue
                fi
                local menu_args=()
                local idx=1
                while IFS= read -r f; do
                    menu_args+=("$idx" "$(basename "$f")")
                    idx=$((idx + 1))
                done <<< "$files"

                local sel
                sel=$(whiptail --title "Seleziona Log" \
                    --menu "Ultimi 10 log:" "$WT_H" "$WT_W" 10 \
                    "${menu_args[@]}" \
                    3>&1 1>&2 2>&3) || continue

                local selected_file
                selected_file=$(echo "$files" | sed -n "${sel}p")
                show_log_tail "$selected_file" "Log: $(basename "$selected_file")"
                ;;
            0) break ;;
        esac
    done
}

# =============================================================================
# PIPELINE COMPLETA
# =============================================================================

menu_full_pipeline() {
    whiptail --title "Pipeline Completa" --yesno \
        "Eseguire la pipeline completa?\n\n\
1. Controllo sistema\n\
2. Training ibrido GPU+CPU\n\
3. Test decisioni\n\
4. Backtest (breakout, BTCUSD, 30 giorni)\n\n\
ATTENZIONE: operazione lunga!" \
        16 55 || return

    log_msg "Avvio pipeline completa..."

    # 1. Controllo sistema
    whiptail --title "Pipeline — Passo 1/4" --infobox \
        "Controllo sistema in corso..." 6 40
    detect_hardware
    if [ "$GPU_DETECTED" = false ]; then
        whiptail --title "Avviso" --yesno \
            "Nessuna GPU rilevata!\n\nContinuare con solo CPU?\n(Il training sara molto piu lento)" \
            12 50 || return
    fi

    # 2. Training ibrido
    whiptail --title "Pipeline — Passo 2/4" --infobox \
        "Avvio training ibrido GPU+CPU..." 6 45
    sleep 1

    local gpu_log cpu_log
    gpu_log="$(timestamp_file "pipeline_gpu")"
    cpu_log="$(timestamp_file "pipeline_cpu")"

    (cd "$PROJECT_ROOT" && $PYTHON analysis/goliath_trainer_v2.py --mode=week > "$gpu_log" 2>&1) &
    local GPU_PID=$!
    (cd "$PROJECT_ROOT" && $PYTHON scripts/train_cpu_models.py > "$cpu_log" 2>&1) &
    local CPU_PID=$!

    # Attendi completamento con progresso
    local step=0
    while kill -0 "$GPU_PID" 2>/dev/null || kill -0 "$CPU_PID" 2>/dev/null; do
        local gpu_s="attivo" cpu_s="attivo"
        kill -0 "$GPU_PID" 2>/dev/null || gpu_s="completato"
        kill -0 "$CPU_PID" 2>/dev/null || cpu_s="completato"

        whiptail --title "Pipeline — Passo 2/4: Training" --infobox \
            "GPU: $gpu_s | CPU: $cpu_s\n\nAttesa completamento... (${step}s)" 8 50
        sleep 5
        step=$((step + 5))
    done

    wait "$GPU_PID" 2>/dev/null || true
    wait "$CPU_PID" 2>/dev/null || true

    # 3. Test decisioni
    whiptail --title "Pipeline — Passo 3/4" --infobox \
        "Esecuzione test decisioni..." 6 40
    run_with_log "pipeline_test" \
        $PYTHON scripts/tools/test_bot.py || true

    # 4. Backtest
    whiptail --title "Pipeline — Passo 4/4" --infobox \
        "Esecuzione backtest (breakout, BTCUSD)..." 6 50
    run_with_log "pipeline_backtest" \
        $PYTHON backtest.py --strategy breakout --symbol BTCUSD --days 30 || true

    # Riepilogo finale
    local report=""
    report+="━━━ PIPELINE COMPLETA ━━━\n\n"
    report+="[1] Controllo sistema: OK\n"
    report+="[2] Training GPU: $(tail -3 "$gpu_log" 2>/dev/null | head -1)\n"
    report+="    Training CPU: $(tail -3 "$cpu_log" 2>/dev/null | head -1)\n"
    report+="[3] Test decisioni: $(tail -1 "$(ls -t "$LOG_DIR"/*pipeline_test* 2>/dev/null | head -1)" 2>/dev/null)\n"
    report+="[4] Backtest: $(tail -1 "$(ls -t "$LOG_DIR"/*pipeline_backtest* 2>/dev/null | head -1)" 2>/dev/null)\n"
    report+="\nLog salvati in: $LOG_DIR/\n"

    echo -e "$report" > "/tmp/goliath_pipeline_result.txt"
    whiptail --title "Pipeline Completa — Riepilogo" --scrolltext \
        --textbox "/tmp/goliath_pipeline_result.txt" "$WT_H" "$WT_W"
}

# =============================================================================
# MENU PRINCIPALE
# =============================================================================

main_menu() {
    check_whiptail
    detect_hardware

    local gpu_line
    gpu_line=$(echo "$GPU_INFO" | grep "^GPU:" | head -1)
    [ -z "$gpu_line" ] && gpu_line="GPU: Rilevamento..."

    while true; do
        local choice
        choice=$(whiptail --title "GOLIATH Console di Training v${VERSION}" \
            --menu "$gpu_line" "$WT_H" "$WT_W" 8 \
            "1" "Controllo Sistema" \
            "2" "Addestra Modelli                    ►" \
            "3" "Test Decisioni" \
            "4" "Backtest                            ►" \
            "5" "Monitora Training                   ►" \
            "6" "Pipeline Completa (tutto)" \
            "7" "Esci" \
            3>&1 1>&2 2>&3) || break

        case "$choice" in
            1) menu_system_check ;;
            2) menu_train ;;
            3) menu_decision_test ;;
            4) menu_backtest ;;
            5) menu_monitor ;;
            6) menu_full_pipeline ;;
            7) break ;;
        esac
    done

    log_msg "Sessione terminata."
    echo -e "${GREEN}Arrivederci! Log salvati in: $LOG_DIR/${NC}"
}

# =============================================================================
# ENTRY POINT
# =============================================================================

main_menu
