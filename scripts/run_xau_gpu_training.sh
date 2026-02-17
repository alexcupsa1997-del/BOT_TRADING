#!/usr/bin/env bash
# =============================================================================
# GOLIATH XAU/USD — GPU Training Launcher (AMD ROCm / NVIDIA CUDA)
# =============================================================================
# Uso:
#   ./scripts/run_xau_gpu_training.sh             # 50 epoche standard
#   ./scripts/run_xau_gpu_training.sh --fast      # 10 epoche rapide (test)
#   ./scripts/run_xau_gpu_training.sh --demo      # solo simulazione trade
#   ./scripts/run_xau_gpu_training.sh --epochs 100 --reason-every 10
#   ./scripts/run_xau_gpu_training.sh --refresh   # ri-scarica tutti i dati
#
# Variabili ambiente supportate:
#   XAU_EPOCHS=100 ./scripts/run_xau_gpu_training.sh
# =============================================================================

set -euo pipefail

# ─── Colori
RED='\033[91m'; GREEN='\033[92m'; YELLOW='\033[93m'
CYAN='\033[96m'; BOLD='\033[1m'; RESET='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo ""
echo -e "${CYAN}═══════════════════════════════════════════════════════════════════════${RESET}"
echo -e "${BOLD}  GOLIATH  XAU/USD  GPU  TRAINING  LAUNCHER${RESET}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════════════════${RESET}"
echo ""

# ─── Cambia in project root
cd "${PROJECT_ROOT}"

# ─── Rilevamento GPU AMD ROCm
if command -v rocminfo &>/dev/null; then
    GPU_INFO=$(rocminfo 2>/dev/null | grep -i "Marketing Name" | head -1 | sed 's/.*: //')
    echo -e "  ${GREEN}GPU AMD ROCm rilevata: ${BOLD}${GPU_INFO:-unknown}${RESET}"

    # Variabili ROCm per massime prestazioni
    export HSA_ENABLE_SDMA=0
    export ROCR_VISIBLE_DEVICES=0
    export HIP_VISIBLE_DEVICES=0
    export HCC_AMDGPU_TARGET=gfx1201
    export PYTORCH_HIP_ALLOC_CONF="max_split_size_mb:512,garbage_collection_threshold:0.9"
    export PYTORCH_TUNABLEOP_ENABLED=1
    export MIOPEN_COMPILE_PARALLEL_LEVEL=4
    echo -e "  ${CYAN}→ Variabili ROCm configurate${RESET}"

elif command -v nvidia-smi &>/dev/null; then
    GPU_INFO=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1)
    echo -e "  ${GREEN}GPU NVIDIA CUDA rilevata: ${BOLD}${GPU_INFO:-unknown}${RESET}"
    export CUDA_DEVICE_ORDER="PCI_BUS_ID"
    export CUDA_VISIBLE_DEVICES=0

else
    echo -e "  ${YELLOW}⚠ Nessuna GPU rilevata — Training su CPU (più lento)${RESET}"
fi

# ─── Virtual environment
VENV_PATHS=(
    "${PROJECT_ROOT}/.venv/bin/activate"
    "${PROJECT_ROOT}/venv/bin/activate"
    "${HOME}/.venv/bin/activate"
)
VENV_ACTIVATED=false
for venv_path in "${VENV_PATHS[@]}"; do
    if [[ -f "$venv_path" ]]; then
        # shellcheck disable=SC1090
        source "$venv_path"
        echo -e "  ${GREEN}→ virtualenv attivato: ${venv_path}${RESET}"
        VENV_ACTIVATED=true
        break
    fi
done
if [[ "$VENV_ACTIVATED" == "false" ]]; then
    echo -e "  ${YELLOW}→ Nessun virtualenv trovato, uso Python di sistema${RESET}"
fi

# ─── Verifica dipendenze minime
echo ""
python -c "
import sys
deps = ['torch', 'numpy', 'pandas', 'yfinance', 'sklearn']
missing = []
for d in deps:
    try:
        __import__(d)
    except ImportError:
        missing.append(d)
if missing:
    print(f'  MANCANTI: {missing}')
    print('  Installa con: pip install -r analysis/requirements.txt')
    sys.exit(1)
import torch
if torch.cuda.is_available():
    n = torch.cuda.get_device_name(0)
    v = torch.cuda.get_device_properties(0).total_memory/1e9
    print(f'  Dipendenze OK | GPU: {n} {v:.1f}GB')
else:
    print('  Dipendenze OK | Nessuna GPU (CPU)')
" || { echo -e "${RED}Errore dipendenze. Esegui: pip install -r analysis/requirements.txt${RESET}"; exit 1; }

# ─── Argomenti passthrough + override da env
EPOCHS="${XAU_EPOCHS:-50}"
EXTRA_ARGS="$*"

echo ""
echo -e "  ${BOLD}Avvio training...${RESET}"
echo -e "  ${CYAN}python analysis/train_xau_gpu_live.py ${EXTRA_ARGS}${RESET}"
echo ""

# ─── Lancio
exec python "${PROJECT_ROOT}/analysis/train_xau_gpu_live.py" \
    --epochs "${EPOCHS}" \
    ${EXTRA_ARGS}
