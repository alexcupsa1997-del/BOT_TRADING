"""
System metrics service using psutil.
Provides real-time CPU, RAM, disk metrics independently from Redis.
"""

import time
import psutil


_boot_time = psutil.boot_time()


def get_system_metrics() -> dict:
    """Collect current system metrics via psutil."""
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    return {
        "cpu_percent": psutil.cpu_percent(interval=None),
        "ram_percent": mem.percent,
        "ram_mb": int(mem.used / 1024 / 1024),
        "ram_total_mb": int(mem.total / 1024 / 1024),
        "disk_usage": disk.percent,
        "disk_used_gb": round(disk.used / (1024**3), 1),
        "disk_total_gb": round(disk.total / (1024**3), 1),
        "uptime_seconds": int(time.time() - _boot_time),
    }
