#!/usr/bin/env python3
"""
GOLIATH Project Cleanup Script
==============================
Identifies and removes obsolete/heavy files to save disk space.

Run with --dry-run to preview changes without deleting.
"""

import os
import shutil
import argparse
from pathlib import Path

# Folders that can be safely deleted (will be regenerated)
DELETABLE_FOLDERS = [
    "engine/target",           # Rust build artifacts (~5+ GB)
    "__pycache__",             # Python bytecode cache
    ".pytest_cache",           # Pytest cache
    ".mypy_cache",             # Mypy cache
    "node_modules",            # Node.js dependencies (if any)
    "frontend/node_modules",   # Frontend Node.js dependencies
    ".coverage",               # Coverage reports
    "htmlcov",                 # HTML coverage reports
    "*.egg-info",              # Python package info
    "dist",                    # Build distribution
    "build",                   # Build output
    "analysis/runs",           # TensorBoard logs (optional)
    "analysis/models_checkpoint",  # Model checkpoints (optional - keep if training!)
]

# File patterns that can be deleted
DELETABLE_PATTERNS = [
    "*.pyc",           # Python compiled
    "*.pyo",           # Python optimized
    "*.pdb",           # Debug symbols
    "*.log",           # Log files
    "*.tmp",           # Temporary files
    "*.bak",           # Backup files
    "thumbs.db",       # Windows thumbnails
    ".DS_Store",       # macOS metadata
]

# Files/folders to keep (never delete)
PROTECTED = [
    ".git",
    ".venv",
    "data",            # Training data
    ".env",
    "*.parquet",       # Data files
]


def get_folder_size(path: Path) -> int:
    """Get total size of folder in bytes."""
    total = 0
    try:
        for entry in path.rglob("*"):
            if entry.is_file():
                total += entry.stat().st_size
    except (PermissionError, OSError):
        pass
    return total


def format_size(size: int) -> str:
    """Format size in human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} TB"


def find_deletable(root: Path, include_optional: bool = False) -> dict:
    """Find all deletable folders and files."""
    results = {"folders": [], "files": [], "total_size": 0}
    
    # Find __pycache__ folders
    for pycache in root.rglob("__pycache__"):
        if pycache.is_dir():
            size = get_folder_size(pycache)
            results["folders"].append((pycache, size))
            results["total_size"] += size
    
    # Find .pytest_cache folders
    for cache in root.rglob(".pytest_cache"):
        if cache.is_dir():
            size = get_folder_size(cache)
            results["folders"].append((cache, size))
            results["total_size"] += size
    
    # Find .mypy_cache folders
    for cache in root.rglob(".mypy_cache"):
        if cache.is_dir():
            size = get_folder_size(cache)
            results["folders"].append((cache, size))
            results["total_size"] += size
    
    # Check for engine/target (Rust build)
    target = root / "engine" / "target"
    if target.exists():
        size = get_folder_size(target)
        results["folders"].append((target, size))
        results["total_size"] += size
    
    # Check for corrupted parquet files (0 bytes)
    data_dir = root / "data"
    if data_dir.exists():
        for pq in data_dir.glob("*.parquet"):
            if pq.stat().st_size == 0:
                results["files"].append((pq, 0, "corrupted (0 bytes)"))
    
    return results


def main():
    parser = argparse.ArgumentParser(description="GOLIATH Project Cleanup")
    parser.add_argument("--dry-run", action="store_true", help="Preview without deleting")
    parser.add_argument("--include-optional", action="store_true", help="Include TensorBoard logs and checkpoints")
    args = parser.parse_args()
    
    root = Path(__file__).parent.parent.parent
    
    print("=" * 60)
    print("  GOLIATH Project Cleanup")
    print("=" * 60)
    print()
    
    results = find_deletable(root, args.include_optional)
    
    if not results["folders"] and not results["files"]:
        print("✓ No cleanup needed!")
        return
    
    print(f"Found {len(results['folders'])} folders and {len(results['files'])} files to clean")
    print(f"Total space to free: {format_size(results['total_size'])}")
    print()
    
    # Show folders
    print("--- Folders ---")
    for folder, size in sorted(results["folders"], key=lambda x: -x[1])[:20]:
        rel = folder.relative_to(root)
        print(f"  {format_size(size):>10}  {rel}")
    
    if len(results["folders"]) > 20:
        print(f"  ... and {len(results['folders']) - 20} more")
    
    # Show files
    if results["files"]:
        print()
        print("--- Files ---")
        for file, size, reason in results["files"]:
            rel = file.relative_to(root)
            print(f"  {rel} ({reason})")
    
    print()
    
    if args.dry_run:
        print("[DRY RUN] No files deleted. Run without --dry-run to delete.")
        return
    
    # Confirm deletion
    response = input(f"Delete {format_size(results['total_size'])}? [y/N]: ")
    if response.lower() != 'y':
        print("Cancelled.")
        return
    
    # Delete folders
    deleted_size = 0
    for folder, size in results["folders"]:
        try:
            shutil.rmtree(folder)
            deleted_size += size
            print(f"  ✓ Deleted {folder.relative_to(root)}")
        except Exception as e:
            print(f"  ✗ Failed to delete {folder}: {e}")
    
    # Delete files
    for file, size, _ in results["files"]:
        try:
            file.unlink()
            deleted_size += size
            print(f"  ✓ Deleted {file.relative_to(root)}")
        except Exception as e:
            print(f"  ✗ Failed to delete {file}: {e}")
    
    print()
    print(f"✓ Freed {format_size(deleted_size)}")


if __name__ == "__main__":
    main()
