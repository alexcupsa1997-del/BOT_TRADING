#!/bin/bash
# scripts/test_gpu_overrides.sh
# Tests different HSA_OVERRIDE_GFX_VERSION values

overrides=("11.0.0" "11.0.1" "11.0.2" "11.0.3" "11.5.0" "12.0.0" "12.0.1" "")

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_EXEC="$PROJECT_ROOT/.venv/bin/python3"

echo "Testing GPU with various overrides..."

for ver in "${overrides[@]}"; do
    echo "------------------------------------------------"
    if [ -z "$ver" ]; then
        echo "Testing with NO override..."
        export HSA_OVERRIDE_GFX_VERSION=""
    else
        echo "Testing with HSA_OVERRIDE_GFX_VERSION=$ver ..."
        export HSA_OVERRIDE_GFX_VERSION="$ver"
    fi
    
    # Run a simple python check
    "$PYTHON_EXEC" -c "import torch; print(f'Success! Device: {torch.cuda.get_device_name(0)}')" 2>/dev/null
    
    RET=$?
    if [ $RET -eq 0 ]; then
        echo "✅ SUCCESS with $ver"
        FOUND_VER="$ver"
        # Break or continue? Let's check all just in case.
    elif [ $RET -eq 139 ]; then
        echo "❌ SEGFAULT with $ver"
    else
        echo "❌ FAILED (Exit code $RET) with $ver"
    fi
done

echo "------------------------------------------------"
echo "Done."
