#!/bin/bash
# scripts/fix_gpu_driver.sh
# Fixes the AMDGPU driver blacklist issue

set -e

echo "=========================================================="
echo "🔧 GOLIATH CPU DRIVER FIXER"
echo "=========================================================="

BLACKLIST_FILE="/etc/modprobe.d/blacklist-amdgpu.conf"

if [ -f "$BLACKLIST_FILE" ]; then
    echo "Found blacklist file: $BLACKLIST_FILE"
    echo "Removing it..."
    rm "$BLACKLIST_FILE"
    echo "✅ Removed blacklist file."
else
    echo "ℹ️  Blacklist file not found (already removed?)"
fi

echo "Updating initramfs (this may take a minute)..."
update-initramfs -u

echo "Attempting to load amdgpu module..."
modprobe amdgpu

if lsmod | grep -q amdgpu; then
    echo "✅ SUCCESS: amdgpu module is loaded!"
    lspci -nnk | grep -A 3 VGA
else
    echo "❌ ERROR: amdgpu module failed to load."
    echo "Check 'dmesg | tail' for details."
fi
