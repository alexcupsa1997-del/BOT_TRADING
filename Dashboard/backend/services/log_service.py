"""
Log aggregation service.
Reads from Redis critical logs and tails log files.
"""

import os
from pathlib import Path
from typing import Optional

from config import settings


def read_log_file(filename: Optional[str] = None, lines: int = 100) -> list[str]:
    """Read last N lines from a log file."""
    log_dir = Path(settings.log_dir).resolve()
    if not log_dir.exists():
        return []

    if filename:
        # Sanitize filename to prevent path traversal
        safe_name = Path(filename).name
        if safe_name != filename or ".." in filename:
            return []
        log_path = log_dir / safe_name
        # Verify resolved path is still inside log_dir
        if not log_path.resolve().is_relative_to(log_dir):
            return []
    else:
        # Find most recent log file
        log_files = sorted(log_dir.glob("*.log"), key=os.path.getmtime, reverse=True)
        if not log_files:
            return []
        log_path = log_files[0]

    if not log_path.exists():
        return []

    try:
        with open(log_path, "r") as f:
            all_lines = f.readlines()
            return [line.rstrip() for line in all_lines[-lines:]]
    except Exception:
        return []


def list_log_files() -> list[dict]:
    """List available log files with sizes."""
    log_dir = Path(settings.log_dir)
    if not log_dir.exists():
        return []

    files = []
    for f in sorted(log_dir.glob("*.log"), key=os.path.getmtime, reverse=True):
        files.append({
            "name": f.name,
            "size_kb": round(f.stat().st_size / 1024, 1),
            "modified": f.stat().st_mtime,
        })
    return files
