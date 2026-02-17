
import os
import sys
import torch
import subprocess

def main():
    print("="*60)
    print(" 🕵️  Goliath GPU Verification Tool")
    print("="*60)
    
    print(f"Python:   {sys.version.split()[0]}")
    print(f"PyTorch:  {torch.__version__}")
    
    # Check for ROCm/HIP
    is_rocm = "rocm" in torch.__version__ or torch.version.hip is not None
    print(f"ROCm/HIP: {'✅ Yes' if is_rocm else '❌ No (Standard CUDA/CPU build)'}")
    
    # Check GPU Visibility
    if torch.cuda.is_available():
        print(f"\n✅ GPU Available: True")
        print(f"   Count:  {torch.cuda.device_count()}")
        print(f"   Name:   {torch.cuda.get_device_name(0)}")
        print(f"   VRAM:   {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB")
        print("\n🎉 Your environment is READY for training!")
    else:
        print(f"\n❌ GPU Available: False")
        
        # Diagnostics
        print("\n🔍 Diagnostics:")
        
        # check kfd
        kfd_ok = os.access('/dev/kfd', os.R_OK | os.W_OK)
        print(f"   /dev/kfd:           {'✅ Accessible' if kfd_ok else '❌ Missing or Permission Denied'}")
        
        # check render nodes
        render_nodes = [f for f in os.listdir('/dev/dri') if f.startswith('render')] if os.path.exists('/dev/dri') else []
        print(f"   Render Nodes:       {render_nodes if render_nodes else '❌ None found'}")
        
        # check amdgpu module
        try:
            lsmod = subprocess.check_output(['lsmod']).decode()
            driver_loaded = 'amdgpu' in lsmod
            print(f"   Driver (amdgpu):    {'✅ Loaded' if driver_loaded else '❌ Not Loaded'}")
        except:
             print(f"   Driver (amdgpu):    ❓ Unknown (lsmod failed)")

        print("\n💡 SUGGESTIONS:")
        if not kfd_ok or not render_nodes:
            print("   - CRITICAL: Your system requires a Kernel/Driver update for Radeon RX 9070 (RDNA 4).")
            print("   - Action: Install Kernel 6.11+ and latest linux-firmware.")
        elif not is_rocm:
             print("   - CRITICAL: PyTorch is not built with ROCm support.")
             print("   - Action: Check requirements.txt and reinstall torch.")

if __name__ == "__main__":
    main()
