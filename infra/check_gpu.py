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
