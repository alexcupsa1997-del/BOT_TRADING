#!/bin/bash
# Install PyTorch ROCm (AMD GPU) Support

echo "Starting AMD ROCm Installation..."

# 1. Activate venv if exists
if [ -d ".venv" ]; then
    source .venv/bin/activate
else
    echo "Creating virtual environment..."
    python3 -m venv .venv
    source .venv/bin/activate
fi

# 2. Uninstall CUDA torch
echo "Uninstalling existing torch..."
pip uninstall -y torch torchvision torchaudio 2>/dev/null

# 3. Install ROCm torch (6.2)
echo "Installing PyTorch ROCm 6.2..."
# This is the official command for ROCm 6.2 support:
# pip3 install --pre torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/rocm6.2
# OR for stable 6.1:
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/rocm6.1

# 4. Create check script
cat <<EOF > infra/check_gpu.py
import torch
import os

# Force override for RDNA cards if needed
# os.environ["HSA_OVERRIDE_GFX_VERSION"] = "11.0.0"

print(f"PyTorch Version: {torch.__version__}")
print(f"ROCm Available: {torch.version.hip if hasattr(torch.version, 'hip') else 'No'}")
print(f"CUDA (HIP) Available: {torch.cuda.is_available()}")

if torch.cuda.is_available():
    print(f"Device Name: {torch.cuda.get_device_name(0)}")
    try:
        x = torch.rand(5, 3).cuda()
        print("Tensor Test: SUCCESS (Allocated on GPU)")
    except Exception as e:
        print(f"Tensor Test: FAILED ({e})")
else:
    print("WARNING: GPU not detected by PyTorch.")
    print("Check: 'dmesg | grep amdgpu' or 'rocminfo'")
EOF

echo "Installation complete. Run 'python infra/check_gpu.py' to verify."
