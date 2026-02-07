@echo off
REM ============================================================================
REM GOLIATH: AMD ROCm Setup for Radeon 9070XT (Windows)
REM ============================================================================
REM
REM This script installs PyTorch with ROCm support for AMD GPUs
REM
REM Prerequisites:
REM 1. Install latest AMD Adrenalin GPU drivers from:
REM    https://www.amd.com/en/support
REM
REM 2. (Optional) Install HIP SDK from:
REM    https://www.amd.com/en/developer/resources/hip-sdk.html
REM ============================================================================

echo.
echo ============================================================================
echo   GOLIATH ROCm Setup - AMD Radeon 9070XT
echo ============================================================================
echo.

REM Check Python version
python --version
if errorlevel 1 (
    echo ERROR: Python not found. Please install Python 3.10-3.12
    pause
    exit /b 1
)

echo.
echo [1/4] Uninstalling existing PyTorch (CUDA version)...
pip uninstall torch torchvision torchaudio -y

echo.
echo [2/4] Installing PyTorch with ROCm 6.2 support...
REM Official PyTorch ROCm wheels
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/rocm6.2

echo.
echo [3/4] Installing additional dependencies...
pip install tensorboard loguru scikit-learn pandas pyarrow

echo.
echo [4/4] Verifying installation...
python -c "import torch; print('PyTorch:', torch.__version__); print('GPU available:', torch.cuda.is_available()); print('Device:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU')"
if errorlevel 1 (
    echo.
    echo WARNING: GPU not detected. Try:
    echo 1. Update AMD Adrenalin drivers to latest version
    echo 2. Install HIP SDK from AMD developer site
    echo 3. Restart computer
    echo 4. Run this script again
)

echo.
echo ============================================================================
echo   Setup Complete!
echo.
echo   Next Steps:
echo   1. Verify GPU: python scripts/tools/verify_gpu.py
echo   2. Start training: python analysis/goliath_trainer_v2.py --mode=week
echo ============================================================================
echo.

pause
