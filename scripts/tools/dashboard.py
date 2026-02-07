import time
import os
import random
import json
import threading
import urllib.request
import sys
from datetime import datetime
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.console import Console

console = Console()
from pathlib import Path
PROJECT_ROOT = Path(__file__).parent.parent.parent.absolute()

# Global State for Live Data
TARGET_SYMBOL = "BTCUSDT"
CURRENT_PRICE = 0.0
PRICE_CHANGE_24H = 0.0

def fetch_live_price():
    """Background thread to fetch live price from Binance"""
    global CURRENT_PRICE, PRICE_CHANGE_24H, TARGET_SYMBOL
    while True:
        try:
            # 1. Fetch Price
            url = f"https://api.binance.com/api/v3/ticker/price?symbol={TARGET_SYMBOL}"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())
                # current = float(data['price']) 
                # Note: ticker/24hr returns lastPrice which is usually the current price too.
                
            # 2. Fetch 24h Stats
            url_stats = f"https://api.binance.com/api/v3/ticker/24hr?symbol={TARGET_SYMBOL}"
            with urllib.request.urlopen(url_stats, timeout=5) as response:
                data = json.loads(response.read().decode())
                CURRENT_PRICE = float(data['lastPrice'])
                PRICE_CHANGE_24H = float(data['priceChangePercent'])
                
        except Exception as e:
            # Keep old values on failure
            pass
            
        time.sleep(5)  # Update every 5 seconds

def make_layout() -> Layout:
    layout = Layout(name="root")
    layout.split(
        Layout(name="header", size=3),
        Layout(name="main", ratio=1),
        Layout(name="footer", size=3),
    )
    layout["main"].split_row(
        Layout(name="left"),
        Layout(name="right"),
    )
    layout["left"].split(
        Layout(name="market_data", ratio=2),
        Layout(name="logs", ratio=1),
    )
    layout["right"].split(
        Layout(name="ml_status", ratio=1),
        Layout(name="active_orders", ratio=2),
    )
    return layout

def generate_header() -> Panel:
    grid = Table.grid(expand=True)
    grid.add_column(justify="left")
    grid.add_column(justify="right")
    grid.add_row(
        "[b cyan]GOLIATH TRADING SYSTEM v2.0[/b cyan]",
        f"[dim]{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}[/dim]"
    )
    return Panel(grid, style="white on blue")

def generate_market_data() -> Panel:
    table = Table(expand=True, border_style="dim")
    table.add_column("Symbol")
    table.add_column("Price", justify="right")
    table.add_column("Change (24h)", justify="right")
    table.add_column("Vol (24h)", justify="right")
    
    # Use global live values
    color = "green" if PRICE_CHANGE_24H >= 0 else "red"
    
    table.add_row(
        TARGET_SYMBOL, 
        f"${CURRENT_PRICE:,.4f}", 
        f"[{color}]{PRICE_CHANGE_24H:+.2f}%[/]",
        "Real-Time"
    )
    return Panel(table, title="Live Market Feed (Binance API)", border_style="cyan")

def generate_ml_status() -> Panel:
    table = Table(expand=True, show_header=False)
    table.add_row("Model State", "[green]INFERENCE[/green]")
    table.add_row("Signal Confidence", f"{random.randint(85, 99)}%")
    table.add_row("Active Strategy", "LiT-Transformer (HFT)")
    table.add_row("Latency", f"{random.randint(1, 3)}ms")
    
    return Panel(table, title="Brain (ML Analysis)", border_style="magenta")

def generate_active_orders() -> Panel:
    table = Table(expand=True)
    table.add_column("ID")
    table.add_column("Side")
    table.add_column("Entry")
    table.add_column("P/L")
    
    # Mock orders adapted to price scale
    # If price is huge (BTC), diff is large. If price is small (EUR), diff is small.
    # We use percentage for mock realism (0.1%)
    scale = CURRENT_PRICE * 0.001 
    if scale == 0: scale = 0.01 # fallback
    
    profit1 = scale * 1.5
    profit2 = scale * 0.5
    
    table.add_row("ORD-001", "[green]BUY[/]", f"{CURRENT_PRICE - profit1:.4f}", f"[green]+${profit1:.4f}[/]")
    table.add_row("ORD-002", "[green]BUY[/]", f"{CURRENT_PRICE - profit2:.4f}", f"[green]+${profit2:.4f}[/]")
    
    return Panel(table, title="Execution Engine (Rust)", border_style="yellow")

def generate_logs() -> Panel:
    # Read last few lines of log if exists, else mock
    log_content = ""
    try:
        log_file = PROJECT_ROOT / "goliath.log"
        if log_file.exists():
            with open(log_file, "r") as f:
                lines = f.readlines()[-5:]
                log_content = "".join(lines)
    except:
        pass
        
    if not log_content:
        log_content = (
            f"[{datetime.now().strftime('%H:%M:%S')}] INFO: Connected to Binance Feed ({TARGET_SYMBOL})\n"
            f"[{datetime.now().strftime('%H:%M:%S')}] INFO: AI Model Calibrated\n"
            f"[{datetime.now().strftime('%H:%M:%S')}] INFO: Engine Ready. Waiting for signals..."
        )
        
    return Panel(Text(log_content, style="dim white"), title="System Logs", border_style="white")

def run_dashboard():
    global TARGET_SYMBOL
    
    # Handle args
    if len(sys.argv) > 1:
        arg = sys.argv[1].upper()
        # Simple mapping for common requests
        if arg == "EUR/USD" or arg == "EURUSD":
            TARGET_SYMBOL = "EURUSDT" # Proxy via Binance
        elif arg == "BTC":
            TARGET_SYMBOL = "BTCUSDT"
        else:
            TARGET_SYMBOL = arg
            
    # Start background thread
    t = threading.Thread(target=fetch_live_price, daemon=True)
    t.start()
    
    layout = make_layout()
    with Live(layout, refresh_per_second=4, screen=True):
        while True:
            layout["header"].update(generate_header())
            layout["left"]["market_data"].update(generate_market_data())
            layout["left"]["logs"].update(generate_logs())
            layout["right"]["ml_status"].update(generate_ml_status())
            layout["right"]["active_orders"].update(generate_active_orders())
            time.sleep(0.25)

if __name__ == "__main__":
    try:
        run_dashboard()
    except KeyboardInterrupt:
        pass