#!/bin/bash
# scripts/train_gpu.sh
# Launcher for Goliath Training on AMD GPU (ROCm)

# Exit on error
set -e

# Configuration
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "=========================================================="
echo "🚀 GOLIATH GPU TRAINING LAUNCHER (AMD ROCm)"
echo "=========================================================="

# 1. Environment Variables for AMD ROCm
# Essential for consumer cards (Radeon) to work with ROCm
# export HSA_OVERRIDE_GFX_VERSION=11.0.0 # Not needed with PyTorch 2.10+ROCm 6.3 for RX 9070
export ROVER_DISABLE_URT_DS=1 # Sometimes needed for stability

# Debugging
# export AMD_LOG_LEVEL=1

echo "Environment Configured:"
echo "  HSA_OVERRIDE_GFX_VERSION=$HSA_OVERRIDE_GFX_VERSION"
echo "  Project Root: $PROJECT_ROOT"

# 2. Python Path
export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"

# 3. Check for PyTorch ROCm
if ! "$PROJECT_ROOT/.venv/bin/python3" -c "import torch; exit(0 if torch.version.hip else 1)" 2>/dev/null; then
    echo "⚠️  WARNING: It seems PyTorch is NOT installed with ROCm support (HIP)."
    echo "   Please install it using:"
    echo "   pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/rocm6.2"
    echo ""
    echo "   Running anyway (might fall back to CPU)..."
    sleep 2
fi

# 4. Run Training
# Pass all arguments to the python script
echo "Starting Training..."
"$PROJECT_ROOT/.venv/bin/python3" analysis/goliath_trainer_v2.py --mode=week "$@"
