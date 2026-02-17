#!/usr/bin/env python3
"""Extract all Mermaid code blocks from biopsy.md and render to PNG via mmdc."""

import re
import subprocess
import sys
from pathlib import Path

BIOPSY = Path("/home/a-cupsa/Desktop/BOT_TRADING/biopsy.md")
OUT_DIR = Path("/home/a-cupsa/Desktop/BOT_TRADING/diagrams")
OUT_DIR.mkdir(exist_ok=True)

content = BIOPSY.read_text(encoding="utf-8")

# Extract all ```mermaid ... ``` blocks
pattern = re.compile(r"```mermaid\n(.*?)```", re.DOTALL)
matches = list(pattern.finditer(content))

print(f"Found {len(matches)} Mermaid diagrams")

for i, m in enumerate(matches, 1):
    mmd_code = m.group(1)
    mmd_path = OUT_DIR / f"diagram_{i:02d}.mmd"
    png_path = OUT_DIR / f"diagram_{i:02d}.png"
    
    mmd_path.write_text(mmd_code, encoding="utf-8")
    
    try:
        result = subprocess.run(
            [
                "npx", "-y", "@mermaid-js/mermaid-cli",
                "-i", str(mmd_path),
                "-o", str(png_path),
                "-b", "transparent",
                "-t", "dark",
                "-w", "1200",
                "-s", "2",
                "--quiet",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if png_path.exists():
            print(f"  ✅ diagram_{i:02d}.png rendered ({png_path.stat().st_size} bytes)")
        else:
            print(f"  ❌ diagram_{i:02d}.png FAILED: {result.stderr[:200]}")
    except subprocess.TimeoutExpired:
        print(f"  ❌ diagram_{i:02d}.png TIMEOUT")
    except Exception as e:
        print(f"  ❌ diagram_{i:02d}.png ERROR: {e}")

print(f"\nDone. Check {OUT_DIR}")
