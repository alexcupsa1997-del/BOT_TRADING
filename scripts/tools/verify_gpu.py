#!/usr/bin/env python3
"""
GOLIATH GPU Verification Script
================================
Verifies GPU setup and provides troubleshooting guidance.
"""

import sys

def check_pytorch():
    """Check PyTorch installation and GPU availability."""
    try:
        import torch
        print(f"✓ PyTorch Version: {torch.__version__}")
        
        # Check for ROCm build
        if "+rocm" in torch.__version__:
            print("✓ PyTorch built with ROCm support")
        elif "+cu" in torch.__version__:
            print("⚠ PyTorch built with CUDA - need ROCm version for AMD GPU")
            return False
            
        # Check GPU availability
        if torch.cuda.is_available():
            device_name = torch.cuda.get_device_name(0)
            device_count = torch.cuda.device_count()
            memory = torch.cuda.get_device_properties(0).total_memory / 1e9
            
            print(f"✓ GPU Available: {device_name}")
            print(f"✓ GPU Count: {device_count}")
            print(f"✓ VRAM: {memory:.1f} GB")
            
            # Quick benchmark
            print("\n--- Quick GPU Benchmark ---")
            x = torch.randn(10000, 10000, device="cuda")
            y = torch.randn(10000, 10000, device="cuda")
            
            import time
            start = time.time()
            z = torch.mm(x, y)
            torch.cuda.synchronize()
            elapsed = time.time() - start
            
            print(f"✓ Matrix multiply (10000x10000): {elapsed*1000:.1f} ms")
            print(f"✓ TFLOPS: {(2 * 10000**3) / elapsed / 1e12:.1f}")
            
            return True
        else:
            print("✗ No GPU detected")
            print("\nTroubleshooting for AMD Radeon 9070XT:")
            print("1. Download AMD Software: PyTorch on Windows Edition")
            print("   URL: https://www.amd.com/en/resources/support-articles/release-notes/RN-AI-PYTCHWIN.html")
            print("2. Install the driver package")
            print("3. Run: setup_rocm.bat")
            print("4. Restart computer if needed")
            return False
            
    except ImportError:
        print("✗ PyTorch not installed")
        print("Run: pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/rocm6.2")
        return False


def check_dependencies():
    """Check all required dependencies."""
    deps = [
        ("numpy", "numpy"),
        ("pandas", "pandas"),
        ("sklearn", "scikit-learn"),
        ("tensorboard", "tensorboard"),
        ("loguru", "loguru"),
        ("pyarrow", "pyarrow"),
    ]
    
    print("\n--- Dependency Check ---")
    all_ok = True
    
    for module, package in deps:
        try:
            __import__(module)
            print(f"✓ {package}")
        except ImportError:
            print(f"✗ {package} - install with: pip install {package}")
            all_ok = False
            
    return all_ok


def main():
    print("=" * 60)
    print("  GOLIATH GPU Verification")
    print("=" * 60)
    print()
    
    gpu_ok = check_pytorch()
    deps_ok = check_dependencies()
    
    print()
    print("=" * 60)
    if gpu_ok and deps_ok:
        print("  ✓ System Ready for Training!")
        print("  Run: python analysis/goliath_trainer_v2.py --mode=week")
    else:
        print("  ✗ Setup incomplete - see above for fixes")
    print("=" * 60)


if __name__ == "__main__":
    main()
