"""
Configuration service for reading/writing paper_trading.json.
Atomic writes to prevent corruption.
"""

import json
import os
import tempfile
from pathlib import Path

from config import settings


def read_config() -> dict:
    """Read the current trading configuration."""
    config_path = Path(settings.config_path)
    if not config_path.exists():
        return {}
    with open(config_path, "r") as f:
        return json.load(f)


def write_config(data: dict) -> None:
    """Write configuration atomically (temp file + rename)."""
    config_path = Path(settings.config_path)
    config_dir = config_path.parent
    config_dir.mkdir(parents=True, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(dir=str(config_dir), suffix=".json.tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=4)
        os.replace(tmp_path, str(config_path))
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def update_config_section(section: str, data: dict) -> dict:
    """Update a specific section of the config and return full config."""
    config = read_config()
    if section == "root":
        config.update(data)
    else:
        config[section] = data
    write_config(config)
    return config
