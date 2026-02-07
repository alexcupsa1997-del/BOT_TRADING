#!/usr/bin/env python3
"""
GOLIATH NeuroVision Pro v5.0
============================
Real-time multi-symbol signal analysis using Phase 3 signal processing.
Integrates channels, patterns, indicators, and neural decision framework.
"""

import time
import sys
import os
import threading
import urllib.request
import json
import numpy as np
from datetime import datetime
from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box
from rich.progress import SpinnerColumn, Progress

console = Console()

# =============================================================================
# CONFIGURATION
# =============================================================================

VERSION = "5.0"
DEFAULT_SYMBOLS = ["BTCUSDT", "ETHUSDT", "EURUSDT"]
TIMEFRAME = "1m"
MAX_LEN = 300

# Parse command line args
SYMBOLS = sys.argv[1:] if len(sys.argv) > 1 else DEFAULT_SYMBOLS[:1]

# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class MarketData:
    """OHLCV data container."""
    open: deque
    high: deque
    low: deque
    close: deque
    volume: deque
    last_update: float = 0.0


class SignalDirection(Enum):
    BULLISH = 1
    NEUTRAL = 0
    BEARISH = -1


@dataclass
class SignalResult:
    """Processed signal result."""
    source: str
    direction: SignalDirection
    strength: float  # 0-100
    weight: float


# Global state
MARKET_DATA: Dict[str, MarketData] = {}
IS_LOADING = True
ANALYSIS_RESULTS: Dict[str, dict] = {}


# =============================================================================
# TECHNICAL INDICATORS (Optimized NumPy)
# =============================================================================

class Indicators:
    """High-performance indicator calculations."""
    
    @staticmethod
    def ema(data: np.ndarray, period: int) -> np.ndarray:
        if len(data) < period:
            return np.zeros_like(data)
        alpha = 2 / (period + 1)
        result = np.zeros_like(data)
        result[0] = data[0]
        for i in range(1, len(data)):
            result[i] = alpha * data[i] + (1 - alpha) * result[i-1]
        return result

    @staticmethod
    def sma(data: np.ndarray, period: int) -> np.ndarray:
        return np.convolve(data, np.ones(period)/period, mode='same')

    @staticmethod
    def rsi(close: np.ndarray, period: int = 14) -> np.ndarray:
        if len(close) < period + 1:
            return np.full_like(close, 50.0)
        delta = np.diff(close, prepend=close[0])
        gain = np.where(delta > 0, delta, 0)
        loss = np.where(delta < 0, -delta, 0)
        avg_gain = Indicators.ema(gain, period)
        avg_loss = Indicators.ema(loss, period)
        with np.errstate(divide='ignore', invalid='ignore'):
            rs = avg_gain / np.where(avg_loss == 0, 1e-10, avg_loss)
        return 100 - (100 / (1 + rs))

    @staticmethod
    def macd(close: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9):
        ema_fast = Indicators.ema(close, fast)
        ema_slow = Indicators.ema(close, slow)
        macd_line = ema_fast - ema_slow
        signal_line = Indicators.ema(macd_line, signal)
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram

    @staticmethod
    def bollinger(close: np.ndarray, period: int = 20, std: float = 2.0):
        sma = Indicators.sma(close, period)
        rolling_std = np.array([
            np.std(close[max(0, i-period+1):i+1]) 
            for i in range(len(close))
        ])
        upper = sma + std * rolling_std
        lower = sma - std * rolling_std
        return upper, sma, lower

    @staticmethod
    def atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
        tr1 = high - low
        tr2 = np.abs(high - np.roll(close, 1))
        tr3 = np.abs(low - np.roll(close, 1))
        tr = np.maximum(tr1, np.maximum(tr2, tr3))
        tr[0] = tr1[0]
        return Indicators.ema(tr, period)

    @staticmethod
    def stochastic(high: np.ndarray, low: np.ndarray, close: np.ndarray, 
                   k_period: int = 14, d_period: int = 3):
        k = np.zeros_like(close)
        for i in range(k_period - 1, len(close)):
            h_max = np.max(high[i-k_period+1:i+1])
            l_min = np.min(low[i-k_period+1:i+1])
            denom = h_max - l_min
            k[i] = 100 * (close[i] - l_min) / denom if denom != 0 else 50
        d = Indicators.sma(k, d_period)
        return k, d

    @staticmethod
    def adx(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14):
        up_move = high - np.roll(high, 1)
        down_move = np.roll(low, 1) - low
        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
        
        tr = Indicators.atr(high, low, close, 1)  # True range
        smooth_tr = Indicators.ema(tr, period)
        smooth_tr = np.where(smooth_tr == 0, 1, smooth_tr)
        
        plus_di = 100 * Indicators.ema(plus_dm, period) / smooth_tr
        minus_di = 100 * Indicators.ema(minus_dm, period) / smooth_tr
        
        with np.errstate(divide='ignore', invalid='ignore'):
            dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)
        adx = Indicators.ema(dx, period)
        return adx, plus_di, minus_di


# =============================================================================
# SIGNAL ANALYSIS ENGINE
# =============================================================================

def analyze_symbol(symbol: str, data: MarketData) -> dict:
    """
    Comprehensive signal analysis for a symbol.
    
    Returns dict with:
    - signals: List[SignalResult]
    - direction: Overall direction
    - confidence: 0-100 score
    - action: BUY/SELL/HOLD
    """
    c = np.array(data.close)
    h = np.array(data.high)
    l = np.array(data.low)
    v = np.array(data.volume)
    
    if len(c) < 60:
        return {'signals': [], 'direction': 'NEUTRAL', 'confidence': 0, 'action': 'LOADING'}
    
    signals = []
    
    # === MOMENTUM SIGNALS ===
    rsi = Indicators.rsi(c)[-1]
    if rsi < 30:
        signals.append(SignalResult('RSI_Oversold', SignalDirection.BULLISH, 80, 1.5))
    elif rsi > 70:
        signals.append(SignalResult('RSI_Overbought', SignalDirection.BEARISH, 80, 1.5))
    elif rsi > 50:
        signals.append(SignalResult('RSI_Bullish', SignalDirection.BULLISH, 40, 0.5))
    else:
        signals.append(SignalResult('RSI_Bearish', SignalDirection.BEARISH, 40, 0.5))
    
    # MACD
    macd, sig, hist = Indicators.macd(c)
    if len(hist) >= 2:
        if hist[-1] > 0 and hist[-2] <= 0:
            signals.append(SignalResult('MACD_BullCross', SignalDirection.BULLISH, 85, 2.0))
        elif hist[-1] < 0 and hist[-2] >= 0:
            signals.append(SignalResult('MACD_BearCross', SignalDirection.BEARISH, 85, 2.0))
        elif hist[-1] > 0:
            signals.append(SignalResult('MACD_Positive', SignalDirection.BULLISH, 50, 0.8))
        else:
            signals.append(SignalResult('MACD_Negative', SignalDirection.BEARISH, 50, 0.8))
    
    # Stochastic
    k, d = Indicators.stochastic(h, l, c)
    if k[-1] < 20 and d[-1] < 20:
        signals.append(SignalResult('Stoch_Oversold', SignalDirection.BULLISH, 70, 1.2))
    elif k[-1] > 80 and d[-1] > 80:
        signals.append(SignalResult('Stoch_Overbought', SignalDirection.BEARISH, 70, 1.2))
    
    # === TREND SIGNALS ===
    adx, plus_di, minus_di = Indicators.adx(h, l, c)
    trend_strength = adx[-1]
    if plus_di[-1] > minus_di[-1]:
        if trend_strength > 25:
            signals.append(SignalResult('ADX_StrongBull', SignalDirection.BULLISH, 75, 1.5))
        else:
            signals.append(SignalResult('ADX_WeakBull', SignalDirection.BULLISH, 40, 0.6))
    else:
        if trend_strength > 25:
            signals.append(SignalResult('ADX_StrongBear', SignalDirection.BEARISH, 75, 1.5))
        else:
            signals.append(SignalResult('ADX_WeakBear', SignalDirection.BEARISH, 40, 0.6))
    
    # Moving Average
    ema_20 = Indicators.ema(c, 20)[-1]
    ema_50 = Indicators.ema(c, 50)[-1] if len(c) >= 50 else ema_20
    current = c[-1]
    
    if current > ema_20 and ema_20 > ema_50:
        signals.append(SignalResult('EMA_Bullish', SignalDirection.BULLISH, 60, 1.0))
    elif current < ema_20 and ema_20 < ema_50:
        signals.append(SignalResult('EMA_Bearish', SignalDirection.BEARISH, 60, 1.0))
    
    # === VOLATILITY SIGNALS ===
    bb_upper, bb_mid, bb_lower = Indicators.bollinger(c)
    bb_pos = (current - bb_lower[-1]) / (bb_upper[-1] - bb_lower[-1] + 1e-10)
    
    if bb_pos < 0.1:
        signals.append(SignalResult('BB_LowerBand', SignalDirection.BULLISH, 65, 1.3))
    elif bb_pos > 0.9:
        signals.append(SignalResult('BB_UpperBand', SignalDirection.BEARISH, 65, 1.3))
    
    # === AGGREGATE ===
    bullish_score = sum(s.strength * s.weight for s in signals if s.direction == SignalDirection.BULLISH)
    bearish_score = sum(s.strength * s.weight for s in signals if s.direction == SignalDirection.BEARISH)
    total = bullish_score + bearish_score
    
    if total == 0:
        direction = 'NEUTRAL'
        confidence = 0
    elif bullish_score > bearish_score:
        direction = 'BULLISH'
        confidence = min(100, bullish_score / (total + 1) * 100)
    else:
        direction = 'BEARISH'
        confidence = min(100, bearish_score / (total + 1) * 100)
    
    # Determine action
    if confidence > 70:
        action = 'STRONG BUY' if direction == 'BULLISH' else 'STRONG SELL'
    elif confidence > 50:
        action = 'BUY' if direction == 'BULLISH' else 'SELL'
    else:
        action = 'HOLD'
    
    return {
        'signals': signals,
        'direction': direction,
        'confidence': confidence,
        'action': action,
        'price': current,
        'rsi': rsi,
        'adx': trend_strength,
        'bb_position': bb_pos * 100
    }


# =============================================================================
# DATA FETCHER
# =============================================================================

def fetch_data():
    global MARKET_DATA, IS_LOADING, ANALYSIS_RESULTS
    
    base_url = "https://api.binance.com/api/v3/klines"
    
    # Initialize data structures
    for sym in SYMBOLS:
        MARKET_DATA[sym] = MarketData(
            open=deque(maxlen=MAX_LEN),
            high=deque(maxlen=MAX_LEN),
            low=deque(maxlen=MAX_LEN),
            close=deque(maxlen=MAX_LEN),
            volume=deque(maxlen=MAX_LEN)
        )
    
    while True:
        for sym in SYMBOLS:
            try:
                url = f"{base_url}?symbol={sym}&interval={TIMEFRAME}&limit={MAX_LEN}"
                with urllib.request.urlopen(url, timeout=5) as response:
                    raw = json.loads(response.read().decode())
                
                data = MARKET_DATA[sym]
                data.open.clear(); data.high.clear(); data.low.clear()
                data.close.clear(); data.volume.clear()
                
                for candle in raw:
                    data.open.append(float(candle[1]))
                    data.high.append(float(candle[2]))
                    data.low.append(float(candle[3]))
                    data.close.append(float(candle[4]))
                    data.volume.append(float(candle[5]))
                
                data.last_update = time.time()
                
                # Analyze
                ANALYSIS_RESULTS[sym] = analyze_symbol(sym, data)
                IS_LOADING = False
                
            except Exception as e:
                pass
        
        time.sleep(2)


# =============================================================================
# UI COMPONENTS
# =============================================================================

def generate_header() -> Panel:
    grid = Table.grid(expand=True)
    grid.add_column(justify="left")
    grid.add_column(justify="center")
    grid.add_column(justify="right")
    
    status = "[green]● ONLINE[/]" if not IS_LOADING else "[yellow]● CONNECTING[/]"
    symbols_str = " | ".join([f"[cyan]{s}[/]" for s in SYMBOLS])
    
    grid.add_row(
        f"[bold white]GOLIATH NEUROVISION PRO[/] [dim]v{VERSION}[/]",
        symbols_str,
        f"{status} | [dim]{datetime.now().strftime('%H:%M:%S')}[/]"
    )
    return Panel(grid, style="white on #1a1a2e", box=box.DOUBLE)


def generate_analysis_panel(symbol: str) -> Panel:
    if symbol not in ANALYSIS_RESULTS or IS_LOADING:
        return Panel(f"[dim]Loading {symbol}...[/]", title=symbol)
    
    result = ANALYSIS_RESULTS[symbol]
    
    table = Table(expand=True, box=box.SIMPLE, padding=(0, 1))
    table.add_column("Metric", style="cyan", width=16)
    table.add_column("Value", justify="right", width=12)
    table.add_column("Signal", width=20)
    
    # Price
    table.add_row("Price", f"${result['price']:.4f}", "")
    
    # RSI
    rsi = result['rsi']
    rsi_color = "green" if rsi < 30 else ("red" if rsi > 70 else "white")
    rsi_sig = "Oversold ↑" if rsi < 30 else ("Overbought ↓" if rsi > 70 else "Neutral")
    table.add_row("RSI (14)", f"[{rsi_color}]{rsi:.1f}[/]", rsi_sig)
    
    # ADX
    adx = result['adx']
    adx_str = "Strong" if adx > 25 else "Weak"
    table.add_row("ADX (14)", f"{adx:.1f}", f"{adx_str} Trend")
    
    # BB Position
    bb = result['bb_position']
    bb_color = "green" if bb < 20 else ("red" if bb > 80 else "yellow")
    table.add_row("BB Position", f"[{bb_color}]{bb:.0f}%[/]", "")
    
    # Top signals
    table.add_section()
    top_signals = sorted(result['signals'], key=lambda s: s.strength * s.weight, reverse=True)[:3]
    for sig in top_signals:
        dir_icon = "↑" if sig.direction == SignalDirection.BULLISH else "↓"
        color = "green" if sig.direction == SignalDirection.BULLISH else "red"
        table.add_row(sig.source, f"[{color}]{sig.strength:.0f}%[/]", f"[{color}]{dir_icon}[/]")
    
    # Border color based on direction
    border_color = "green" if result['direction'] == 'BULLISH' else ("red" if result['direction'] == 'BEARISH' else "yellow")
    
    return Panel(table, title=f"[bold]{symbol}[/]", border_style=border_color)


def generate_decision_panel() -> Panel:
    if IS_LOADING or not ANALYSIS_RESULTS:
        return Panel("[dim]Analyzing...[/]", title="CONSENSUS")
    
    # Aggregate all symbols
    total_bullish = 0
    total_bearish = 0
    
    for sym, result in ANALYSIS_RESULTS.items():
        if result['direction'] == 'BULLISH':
            total_bullish += result['confidence']
        elif result['direction'] == 'BEARISH':
            total_bearish += result['confidence']
    
    total = total_bullish + total_bearish
    if total == 0:
        bias = "NEUTRAL"
        overall_conf = 0
        color = "yellow"
    elif total_bullish > total_bearish:
        bias = "BULLISH"
        overall_conf = total_bullish / (total) * 100
        color = "bright_green" if overall_conf > 70 else "green"
    else:
        bias = "BEARISH"
        overall_conf = total_bearish / (total) * 100
        color = "bright_red" if overall_conf > 70 else "red"
    
    # Action text
    if overall_conf > 75:
        action = "STRONG " + ("BUY" if bias == "BULLISH" else "SELL")
    elif overall_conf > 55:
        action = "BUY" if bias == "BULLISH" else "SELL"
    else:
        action = "WAIT / HOLD"
    
    grid = Table.grid(expand=True)
    grid.add_column(justify="center")
    grid.add_row(f"[bold {color} underline]{action}[/]")
    grid.add_row("")
    grid.add_row(f"[dim]Bias: {bias}[/]")
    grid.add_row(f"[dim]Confidence: {overall_conf:.0f}%[/]")
    grid.add_row("")
    grid.add_row(f"[dim]Bullish: {total_bullish:.0f} | Bearish: {total_bearish:.0f}[/]")
    
    return Panel(grid, title="[bold]AI CONSENSUS[/]", border_style=color, box=box.DOUBLE)


def generate_signals_table() -> Panel:
    if IS_LOADING or not ANALYSIS_RESULTS:
        return Panel("[dim]Loading signals...[/]", title="Signal Matrix")
    
    table = Table(expand=True, box=box.SIMPLE_HEAVY, show_header=True)
    table.add_column("Symbol", style="cyan")
    table.add_column("Price", justify="right")
    table.add_column("RSI", justify="center")
    table.add_column("ADX", justify="center")
    table.add_column("Direction", justify="center")
    table.add_column("Conf", justify="right")
    table.add_column("Action", justify="center")
    
    for sym, result in ANALYSIS_RESULTS.items():
        if result['action'] == 'LOADING':
            continue
        
        dir_color = "green" if result['direction'] == 'BULLISH' else ("red" if result['direction'] == 'BEARISH' else "yellow")
        action_color = "bright_green" if 'BUY' in result['action'] else ("bright_red" if 'SELL' in result['action'] else "dim")
        
        rsi = result['rsi']
        rsi_color = "green" if rsi < 30 else ("red" if rsi > 70 else "white")
        
        table.add_row(
            sym,
            f"${result['price']:.4f}",
            f"[{rsi_color}]{rsi:.1f}[/]",
            f"{result['adx']:.1f}",
            f"[{dir_color}]{result['direction']}[/]",
            f"{result['confidence']:.0f}%",
            f"[{action_color}]{result['action']}[/]"
        )
    
    return Panel(table, title="[bold]SIGNAL MATRIX[/]", border_style="blue")


# =============================================================================
# MAIN
# =============================================================================

def run():
    # Start data fetcher
    fetcher = threading.Thread(target=fetch_data, daemon=True)
    fetcher.start()
    
    # Layout
    layout = Layout()
    layout.split(
        Layout(name="header", size=3),
        Layout(name="body"),
        Layout(name="footer", size=1)
    )
    
    if len(SYMBOLS) == 1:
        layout["body"].split_row(
            Layout(name="main", ratio=7),
            Layout(name="decision", ratio=3)
        )
    else:
        layout["body"].split_row(
            Layout(name="matrix", ratio=6),
            Layout(name="decision", ratio=4)
        )
    
    with Live(layout, refresh_per_second=2, screen=True):
        while True:
            layout["header"].update(generate_header())
            
            if len(SYMBOLS) == 1:
                layout["main"].update(generate_analysis_panel(SYMBOLS[0]))
            else:
                layout["matrix"].update(generate_signals_table())
            
            layout["decision"].update(generate_decision_panel())
            layout["footer"].update(Panel(
                "[dim]Press Ctrl+C to exit | Phase 3 Signal Processing Active[/]",
                style="dim", box=box.SIMPLE
            ))
            
            time.sleep(0.5)


if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        console.print("\n[yellow]NeuroVision terminated.[/]")