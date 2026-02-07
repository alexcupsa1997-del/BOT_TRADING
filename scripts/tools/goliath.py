#!/usr/bin/env python3
"""
GOLIATH Enterprise System Validator v3.0
=========================================
Professional-grade system health checker for the GOLIATH trading ecosystem.
Validates Rust Core, Go Gateway, Python Brain, and Phase 3 Signal Processing.
"""

import subprocess
import sys
import os
import socket
import time
import platform
import psutil
import logging
import json
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple
from datetime import datetime
from enum import Enum

# =============================================================================
# CONFIGURATION
# =============================================================================

VERSION = "3.0"
PROJECT_ROOT = Path(__file__).parent.parent.parent.absolute()
REPORT_FILE = PROJECT_ROOT / "docs" / "reports" / "GOLIATH_REPORT.md"
LOG_FILE = PROJECT_ROOT / "goliath.log"

# Thresholds
MIN_DISK_GB = 10
MIN_RAM_GB = 4
REQUIRED_PY_VERSION = (3, 10)

# =============================================================================
# LOGGING
# =============================================================================

class ColorFormatter(logging.Formatter):
    """Colored console output."""
    
    COLORS = {
        'DEBUG': '\033[90m',
        'INFO': '\033[97m',
        'WARNING': '\033[93m',
        'ERROR': '\033[91m',
        'CRITICAL': '\033[95m',
    }
    RESET = '\033[0m'
    GREEN = '\033[92m'
    CYAN = '\033[96m'
    
    def format(self, record):
        color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{color}{record.levelname}{self.RESET}"
        record.name = f"{self.CYAN}{record.name}{self.RESET}"
        return super().format(record)


def setup_logging():
    logger = logging.getLogger("GOLIATH")
    logger.setLevel(logging.INFO)
    
    # File handler
    fh = logging.FileHandler(LOG_FILE, mode='w', encoding='utf-8')
    fh.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] [%(name)s] %(message)s'))
    logger.addHandler(fh)
    
    # Console handler with colors
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(ColorFormatter('%(asctime)s [%(levelname)s] [%(name)s] %(message)s'))
    logger.addHandler(ch)
    
    return logger


logger = setup_logging()


# =============================================================================
# DATA STRUCTURES
# =============================================================================

class Severity(Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class Diagnostic:
    probable_cause: str
    suggested_fix: str
    severity: Severity = Severity.HIGH
    docs_link: str = ""


@dataclass
class TestResult:
    component: str
    test_name: str
    status: bool
    output: str
    duration: float
    diagnostic: Optional[Diagnostic] = None
    metrics: Dict = field(default_factory=dict)


# =============================================================================
# DIAGNOSTICS ENGINE
# =============================================================================

class DiagnosticsEngine:
    """AI-like error analysis for actionable fixes."""
    
    PATTERNS = [
        # Python
        (r"modulenotfounderror.*'(\w+)'", 
         "Missing Python Module: {0}", 
         "pip install {0} or check PYTHONPATH",
         Severity.MEDIUM),
        (r"importerror.*cannot import name '(\w+)'",
         "Import Error: {0} not found",
         "Check module structure and __init__.py exports",
         Severity.MEDIUM),
        
        # Rust
        (r"error\[e(\d+)\]",
         "Rust Compiler Error E{0}",
         "Run 'cargo check' for details. See rustc --explain E{0}",
         Severity.CRITICAL),
        (r"cannot find.*in this scope",
         "Rust: Undefined Symbol",
         "Check imports with 'use' statements",
         Severity.HIGH),
        
        # Go
        (r"undefined: (\w+)",
         "Go: Undefined '{0}'",
         "Check imports or run 'go mod tidy'",
         Severity.HIGH),
        (r"cannot find package",
         "Go: Missing Package",
         "Run 'go mod download' or 'go get <package>'",
         Severity.HIGH),
        
        # Network
        (r"connection refused",
         "Service Not Responding",
         "Ensure target service is running (docker ps)",
         Severity.HIGH),
        (r"timeout",
         "Connection Timeout",
         "Check network connectivity and firewall",
         Severity.MEDIUM),
        
        # Docker
        (r"docker.*not found|daemon.*not running",
         "Docker Not Available",
         "Start Docker Desktop or install Docker",
         Severity.CRITICAL),
    ]
    
    @classmethod
    def analyze(cls, output: str) -> Optional[Diagnostic]:
        output_lower = output.lower()
        
        for pattern, cause_template, fix_template, severity in cls.PATTERNS:
            match = re.search(pattern, output_lower)
            if match:
                groups = match.groups() if match.groups() else [""]
                return Diagnostic(
                    probable_cause=cause_template.format(*groups),
                    suggested_fix=fix_template.format(*groups),
                    severity=severity
                )
        
        return None


# =============================================================================
# GOLIATH VALIDATOR
# =============================================================================

class Goliath:
    """Enterprise System Validator."""
    
    def __init__(self):
        self.results: List[TestResult] = []
        self.start_time = time.time()
        self._print_banner()
    
    def _print_banner(self):
        banner = r"""
   ██████╗  ██████╗ ██╗     ██╗ █████╗ ████████╗██╗  ██╗
  ██╔════╝ ██╔═══██╗██║     ██║██╔══██╗╚══██╔══╝██║  ██║
  ██║  ███╗██║   ██║██║     ██║███████║   ██║   ███████║
  ██║   ██║██║   ██║██║     ██║██╔══██║   ██║   ██╔══██║
  ╚██████╔╝╚██████╔╝███████╗██║██║  ██║   ██║   ██║  ██║
   ╚═════╝  ╚═════╝ ╚══════╝╚═╝╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═╝
                                                    v{VERSION}
        ╔══════════════════════════════════════════════╗
        ║   ENTERPRISE SYSTEM VALIDATOR                ║
        ║   Rust · Go · Python · Phase 3 Signals       ║
        ╚══════════════════════════════════════════════╝
        """.format(VERSION=VERSION)
        print(banner)
        self._log_system_info()
    
    def _log_system_info(self):
        logger.info("━" * 50)
        logger.info("SYSTEM TELEMETRY")
        logger.info("━" * 50)
        
        try:
            # OS
            os_info = f"{platform.system()} {platform.release()}"
            logger.info(f"  OS       : {os_info}")
            
            # CPU
            cpu_count = psutil.cpu_count(logical=True)
            cpu_freq = psutil.cpu_freq()
            freq_str = f" @ {cpu_freq.current:.0f}MHz" if cpu_freq else ""
            logger.info(f"  CPU      : {cpu_count} Cores{freq_str}")
            
            # RAM
            ram = psutil.virtual_memory()
            ram_gb = ram.total / (1024**3)
            ram_used = ram.percent
            logger.info(f"  RAM      : {ram_gb:.1f} GB ({ram_used:.0f}% used)")
            
            # Disk
            disk = psutil.disk_usage(str(PROJECT_ROOT))
            disk_free = disk.free / (1024**3)
            disk_status = "✓" if disk_free > MIN_DISK_GB else "⚠"
            logger.info(f"  Disk     : {disk_free:.1f} GB Free {disk_status}")
            
            # Python
            py_ver = sys.version.split()[0]
            logger.info(f"  Python   : {py_ver}")
            
            # Docker
            docker_status = self._check_docker()
            logger.info(f"  Docker   : {docker_status}")
            
        except Exception as e:
            logger.error(f"Telemetry error: {e}")
        
        logger.info("━" * 50)
    
    def _check_docker(self) -> str:
        try:
            result = subprocess.run(
                ["docker", "info"], 
                capture_output=True, 
                text=True, 
                timeout=5
            )
            if result.returncode == 0:
                return "✓ Running"
            return "⚠ Not Running"
        except:
            return "✗ Not Installed"
    
    def run_command(
        self, 
        cmd: List[str], 
        cwd: Path, 
        component: str, 
        test_name: str, 
        env: Dict = None,
        timeout: int = 60
    ) -> bool:
        """Execute a test command with comprehensive error handling."""
        start = time.time()
        logger.info(f"[{component}] EXEC: {test_name}")
        
        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)
        
        try:
            result = subprocess.run(
                cmd,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                shell=True,
                env=merged_env,
                timeout=timeout
            )
            duration = time.time() - start
            success = result.returncode == 0
            
            output = result.stdout
            if result.stderr:
                output += "\n--- STDERR ---\n" + result.stderr
            
            diagnostic = None
            if not success:
                logger.error(f"[{component}] FAIL: {test_name} ({duration:.2f}s)")
                diagnostic = DiagnosticsEngine.analyze(output)
            else:
                logger.info(f"[{component}] PASS: {test_name} ({duration:.2f}s)")
            
            self.results.append(TestResult(
                component=component,
                test_name=test_name,
                status=success,
                output=output,
                duration=duration,
                diagnostic=diagnostic
            ))
            return success
            
        except subprocess.TimeoutExpired:
            logger.error(f"[{component}] TIMEOUT: {test_name}")
            self.results.append(TestResult(
                component=component,
                test_name=test_name,
                status=False,
                output="Command timed out",
                duration=timeout,
                diagnostic=Diagnostic(
                    "Command Timeout",
                    f"Process exceeded {timeout}s limit",
                    Severity.HIGH
                )
            ))
            return False
            
        except Exception as e:
            logger.critical(f"[{component}] CRASH: {str(e)}")
            self.results.append(TestResult(
                component=component,
                test_name=test_name,
                status=False,
                output=str(e),
                duration=0.0,
                diagnostic=Diagnostic("Tool Crash", "Debug Goliath script", Severity.CRITICAL)
            ))
            return False
    
    # =========================================================================
    # TEST SUITES
    # =========================================================================
    
    def verify_infrastructure(self):
        """Check system prerequisites."""
        comp = "INFRA"
        
        # Disk space
        try:
            disk = psutil.disk_usage(str(PROJECT_ROOT))
            disk_free = disk.free / (1024**3)
            if disk_free >= MIN_DISK_GB:
                self.results.append(TestResult(
                    comp, "Disk Space", True,
                    f"{disk_free:.1f} GB available", 0.0
                ))
            else:
                self.results.append(TestResult(
                    comp, "Disk Space", False,
                    f"Only {disk_free:.1f} GB free",
                    0.0,
                    Diagnostic("Low Disk Space", f"Need at least {MIN_DISK_GB} GB", Severity.HIGH)
                ))
        except:
            pass
        
        # Data directory
        data_dir = PROJECT_ROOT / "data"
        if data_dir.exists():
            files = list(data_dir.glob("*.parquet"))
            size = sum(f.stat().st_size for f in files) / (1024*1024)
            self.results.append(TestResult(
                comp, "Data Storage", True,
                f"{len(files)} parquet files ({size:.1f} MB)", 0.0
            ))
        else:
            self.results.append(TestResult(
                comp, "Data Storage", False,
                "Data directory not found", 0.0,
                Diagnostic("No Data", "Run ETL pipeline to generate data", Severity.MEDIUM)
            ))
        
        # Internet
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=3)
            self.results.append(TestResult(comp, "Internet", True, "Connected", 0.1))
        except:
            self.results.append(TestResult(
                comp, "Internet", False, "No connection", 0.1,
                Diagnostic("Network Down", "Check internet connection", Severity.MEDIUM)
            ))
    
    def verify_rust_core(self):
        """Validate Rust engine components."""
        comp = "RUST"
        path = PROJECT_ROOT / "engine"
        
        if not path.exists():
            logger.warning(f"[{comp}] Engine directory not found, skipping")
            return
        
        checks = [
            (["cargo", "check"], "Syntax Check"),
            (["cargo", "test", "--lib"], "Unit Tests"),
            (["cargo", "test", "--test", "proptest_suite"], "Property Tests"),
            (["cargo", "test", "--test", "audit_tamper_test"], "Security Audit"),
            (["cargo", "build", "--bin", "backtester", "--release"], "Release Build"),
        ]
        
        for cmd, name in checks:
            self.run_command(cmd, path, comp, name)
    
    def verify_go_gateway(self):
        """Validate Go gateway components."""
        comp = "GO"
        path = PROJECT_ROOT / "gateway"
        
        if not path.exists():
            logger.warning(f"[{comp}] Gateway directory not found, skipping")
            return
        
        checks = [
            (["go", "mod", "verify"], "Dependencies"),
            (["go", "vet", "./..."], "Static Analysis"),
            (["go", "test", "-v", "./internal/middleware"], "RBAC Layer"),
            (["go", "test", "-v", "./internal/pipeline"], "Pipeline"),
            (["go", "test", "-v", "./internal/connector/mt5"], "MT5 Bridge"),
        ]
        
        for cmd, name in checks:
            self.run_command(cmd, path, comp, name)
    
    def verify_python_brain(self):
        """Validate Python analysis components."""
        comp = "PYTHON"
        env = {"PYTHONPATH": str(PROJECT_ROOT)}
        
        checks = [
            (["python", "--version"], "Interpreter"),
            (["python", "-c", "import pandas, numpy, torch; print('Core deps OK')"], "Core Dependencies"),
            (["python", "-c", "from loguru import logger; from rich.console import Console; print('UI deps OK')"], "UI Dependencies"),
            (["python", "analysis/dummy_train.py"], "ML Training"),
            (["python", "-c", "from analysis.src.quant import indicators, patterns, features; print('Phase 2 OK')"], "Phase 2 Modules"),
        ]
        
        for cmd, name in checks:
            self.run_command(cmd, PROJECT_ROOT, comp, name, env=env)
    
    def verify_phase3_signals(self):
        """Validate Phase 3 signal processing modules."""
        comp = "SIGNALS"
        env = {"PYTHONPATH": str(PROJECT_ROOT)}
        
        checks = [
            (["python", "-c", "from analysis.src.quant import channels; print('Channels OK')"], "Channel Detection"),
            (["python", "-c", "from analysis.src.quant import signal_processor; print('Signal Processor OK')"], "Signal Aggregator"),
            (["python", "-c", "from analysis.src.quant import indicator_optimizer; print('Optimizer OK')"], "Indicator Optimizer"),
            (["python", "-c", "from analysis.src.quant import neural_decision; print('Neural Decision OK')"], "Neural Decision"),
            (["python", "-c", """
from analysis.src.quant import TradeDecision, TradeAction, Signal, AggregatedSignal
from analysis.src.quant import Channel, detect_channel
print('All exports OK')
"""], "Module Exports"),
        ]
        
        for cmd, name in checks:
            self.run_command(cmd, PROJECT_ROOT, comp, name, env=env)
    
    # =========================================================================
    # REPORTING
    # =========================================================================
    
    def generate_report(self):
        """Generate comprehensive markdown report."""
        duration = time.time() - self.start_time
        passed = sum(1 for r in self.results if r.status)
        total = len(self.results)
        score = (passed / total) * 100 if total > 0 else 0
        
        logger.info(f"Generating report: {REPORT_FILE}")
        
        with open(REPORT_FILE, "w", encoding="utf-8") as f:
            # Header
            f.write(f"# 🛡️ GOLIATH System Report v{VERSION}\n\n")
            f.write("> **Generated:** {0}  \n".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            f.write(f"> **Platform:** {platform.system()} {platform.release()}  \n")
            f.write(f"> **Duration:** {duration:.1f}s  \n")
            f.write(f"> **Health Score:** {score:.0f}%\n\n")
            
            # Score badge
            if score == 100:
                f.write("![Status](https://img.shields.io/badge/Status-ALL%20PASS-brightgreen?style=for-the-badge)\n\n")
            elif score >= 80:
                f.write("![Status](https://img.shields.io/badge/Status-MOSTLY%20PASS-yellow?style=for-the-badge)\n\n")
            else:
                f.write("![Status](https://img.shields.io/badge/Status-ISSUES%20DETECTED-red?style=for-the-badge)\n\n")
            
            # Summary table
            f.write("## Summary\n\n")
            f.write("| Component | Tests | Passed | Status |\n")
            f.write("|-----------|-------|--------|--------|\n")
            
            components = {}
            for r in self.results:
                if r.component not in components:
                    components[r.component] = {'total': 0, 'passed': 0}
                components[r.component]['total'] += 1
                if r.status:
                    components[r.component]['passed'] += 1
            
            for comp, stats in components.items():
                badge = "✅" if stats['passed'] == stats['total'] else "⚠️"
                f.write(f"| {comp} | {stats['total']} | {stats['passed']} | {badge} |\n")
            
            # Failures
            failures = [r for r in self.results if not r.status]
            if failures:
                f.write("\n## 🚨 Issues Detected\n\n")
                for r in failures:
                    f.write(f"### ❌ {r.component}: {r.test_name}\n\n")
                    if r.diagnostic:
                        f.write(f"**Cause:** {r.diagnostic.probable_cause}  \n")
                        f.write(f"**Fix:** {r.diagnostic.suggested_fix}  \n")
                        f.write(f"**Severity:** {r.diagnostic.severity.value}\n\n")
                    f.write("<details><summary>Output</summary>\n\n")
                    f.write(f"```\n{r.output[:2000]}\n```\n</details>\n\n")
            else:
                f.write("\n## ✅ All Systems Operational\n\n")
                f.write("No issues detected. System ready for trading.\n\n")
            
            # Detailed logs
            f.write("## 📋 Test Details\n\n")
            for r in self.results:
                icon = "✅" if r.status else "❌"
                f.write(f"<details><summary>{icon} <b>{r.component}</b>: {r.test_name} ({r.duration:.2f}s)</summary>\n\n")
                f.write(f"```\n{r.output[:3000]}\n```\n</details>\n\n")
        
        print(f"\n{'='*60}")
        print(f"  REPORT: {REPORT_FILE}")
        print(f"  SCORE:  {score:.0f}% ({passed}/{total} passed)")
        print(f"{'='*60}")


# =============================================================================
# MAIN
# =============================================================================

def main():
    g = Goliath()
    
    # Run all verification suites
    g.verify_infrastructure()
    g.verify_rust_core()
    g.verify_go_gateway()
    g.verify_python_brain()
    g.verify_phase3_signals()  # NEW: Phase 3 validation
    
    # Generate report
    g.generate_report()


if __name__ == "__main__":
    main()
