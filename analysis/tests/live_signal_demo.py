#!/usr/bin/env python3
"""
GOLIATH v2.0 — Live Trading Signal Demo

Simulates a live trading scenario:
  1. Load synthetic market data (as if streaming from MT5)
  2. Take the latest N bars ("current market")
  3. Run the full TradingOrchestrator pipeline
  4. Display actionable signal with levels, indicators, patterns

Usage:
    PYTHONPATH=. python analysis/tests/live_signal_demo.py
"""

import sys
import time
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger

logger.remove()
logger.add(sys.stderr, level="DEBUG",
           format="<green>{time:HH:mm:ss}</green> | <level>{level:<7}</level> | <level>{message}</level>")


# ANSI colors
class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"


def print_header():
    print(f"""
{C.CYAN}{C.BOLD}╔══════════════════════════════════════════════════════════════╗
║          GOLIATH v2.0 — LIVE SIGNAL GENERATOR               ║
║          4-Tier Fallback Decision Engine                     ║
╚══════════════════════════════════════════════════════════════╝{C.RESET}
""")


def print_signal_box(decision, symbol, timeframe, price, atr, indicators, signals_detail):
    """Print the trading signal in a beautiful terminal box."""

    # Action color
    if decision.action == "LONG":
        action_color = C.BG_GREEN
        arrow = "▲▲▲"
        action_label = " LONG  — BUY "
    elif decision.action == "SHORT":
        action_color = C.BG_RED
        arrow = "▼▼▼"
        action_label = " SHORT — SELL "
    else:
        action_color = C.BG_YELLOW
        arrow = "───"
        action_label = " HOLD  — WAIT "

    # Tier color
    tier_names = {1: "COPER (Memory)", 2: "ML MODEL", 3: "SIGNALS", 4: "CONSERVATIVE"}
    tier_colors = {1: C.MAGENTA, 2: C.BLUE, 3: C.CYAN, 4: C.YELLOW}
    tier_name = tier_names.get(int(decision.source_tier), "UNKNOWN")
    tier_color = tier_colors.get(int(decision.source_tier), C.WHITE)

    # Confidence bar
    conf_pct = decision.confidence * 100
    bar_len = 30
    filled = int(conf_pct / 100 * bar_len)
    if conf_pct >= 70:
        bar_color = C.GREEN
    elif conf_pct >= 40:
        bar_color = C.YELLOW
    else:
        bar_color = C.RED
    bar = f"{bar_color}{'█' * filled}{C.DIM}{'░' * (bar_len - filled)}{C.RESET}"

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print(f"""
{C.BOLD}┌────────────────────────────────────────────────────────────────┐
│  {C.DIM}Timestamp:{C.RESET}{C.BOLD}  {now}                      │
│  {C.DIM}Symbol:{C.RESET}{C.BOLD}     {symbol}  │  Timeframe: {timeframe}                     │
├────────────────────────────────────────────────────────────────┤{C.RESET}
│                                                                │
│  {C.BOLD}      {arrow}  {action_color}{C.BOLD} {action_label} {C.RESET}  {arrow}{C.BOLD}                          │{C.RESET}
│                                                                │
│  {C.DIM}Decision Tier:{C.RESET}  {tier_color}{C.BOLD}{tier_name}{C.RESET}                              │
│  {C.DIM}Reasoning:{C.RESET}      {decision.reasoning:<46s}│
│                                                                │
│  {C.DIM}Confidence:{C.RESET}     [{bar}] {C.BOLD}{conf_pct:5.1f}%{C.RESET}       │
│  {C.DIM}Position Size:{C.RESET}  {C.BOLD}{decision.position_size_pct*100:.1f}%{C.RESET} of capital                              │
│                                                                │
{C.BOLD}├────────────────── PRICE LEVELS ─────────────────────────────────┤{C.RESET}""")

    if decision.action != "HOLD":
        risk = abs(price - decision.stop_loss)
        reward = abs(decision.take_profit - price)
        rr = reward / risk if risk > 0 else 0

        print(f"""│                                                                │
│  {C.GREEN}▸ Entry Price:{C.RESET}    {price:>14.5f}                              │
│  {C.RED}▸ Stop Loss:{C.RESET}      {decision.stop_loss:>14.5f}  ({C.RED}-{risk:.5f}{C.RESET})             │
│  {C.GREEN}▸ Take Profit:{C.RESET}   {decision.take_profit:>14.5f}  ({C.GREEN}+{reward:.5f}{C.RESET})             │
│  {C.CYAN}▸ Risk/Reward:{C.RESET}    {C.BOLD}1:{rr:.1f}{C.RESET}                                       │
│  {C.DIM}▸ ATR (14):{C.RESET}       {atr:>14.5f}                              │""")
    else:
        print(f"""│                                                                │
│  {C.DIM}▸ Current Price:{C.RESET}  {price:>14.5f}                              │
│  {C.DIM}▸ ATR (14):{C.RESET}       {atr:>14.5f}                              │
│  {C.YELLOW}  No entry — waiting for stronger signal{C.RESET}                      │""")

    # Indicators section
    print(f"""{C.BOLD}│                                                                │
├────────────────── INDICATORS ──────────────────────────────────┤{C.RESET}
│                                                                │""")

    for name, value, interp in indicators:
        if interp == "bullish":
            ic = C.GREEN
            sym = "▲"
        elif interp == "bearish":
            ic = C.RED
            sym = "▼"
        else:
            ic = C.YELLOW
            sym = "●"
        print(f"│  {ic}{sym}{C.RESET} {name:<16s} {value:>10s}  {ic}{interp:<10s}{C.RESET}                   │")

    # Signals section
    print(f"""{C.BOLD}│                                                                │
├────────────────── ACTIVE SIGNALS ──────────────────────────────┤{C.RESET}
│                                                                │""")

    if signals_detail:
        for sig_name, sig_dir, sig_str in signals_detail:
            if sig_dir == "BULLISH":
                sc = C.GREEN
            elif sig_dir == "BEARISH":
                sc = C.RED
            else:
                sc = C.YELLOW
            print(f"│  {sc}◆{C.RESET} {sig_name:<28s} {sc}{sig_dir:<8s}{C.RESET} str={sig_str:>5.1f}  │")
    else:
        print(f"│  {C.DIM}  No active signals{C.RESET}                                          │")

    print(f"""{C.BOLD}│                                                                │
└────────────────────────────────────────────────────────────────┘{C.RESET}
""")


def main():
    print_header()

    t0 = time.time()

    # ── 1. LOAD DATA ──────────────────────────────────────────────
    logger.info("Loading market data...")
    data_path = Path(__file__).parent.parent / "data" / "synthetic_market.parquet"
    if not data_path.exists():
        logger.error(f"Data not found: {data_path}")
        logger.info("Run: PYTHONPATH=. python analysis/generate_data.py")
        return 1

    raw = pd.read_parquet(data_path)

    if "timestamp" in raw.columns:
        raw["timestamp"] = pd.to_datetime(raw["timestamp"], unit="ms")
        raw = raw.set_index("timestamp")

    if "close" not in raw.columns and "bid" in raw.columns:
        raw["price"] = (raw["bid"] + raw["ask"]) / 2
        price_col = "price"
    elif "close" in raw.columns:
        price_col = "close"
    else:
        price_col = "price"

    # Resample to 1H
    ohlcv = raw[price_col].resample("1h").agg(["first", "max", "min", "last"])
    ohlcv.columns = ["open", "high", "low", "close"]
    if "volume" in raw.columns:
        ohlcv["volume"] = raw["volume"].resample("1h").sum()
    else:
        ohlcv["volume"] = 100.0
    ohlcv = ohlcv.dropna()

    logger.info(f"Loaded {len(ohlcv):,} bars (1H)")

    # ── 2. SIMULATE LIVE — scan for actionable signal ───────────────
    WINDOW = 500
    symbol = "XAUUSD"
    timeframe = "H1"

    from src.orchestrator import TradingOrchestrator, OrchestratorConfig
    from src.quant.signal_processor import extract_indicator_signals as _ext_ind
    from src.quant.signal_processor import extract_pattern_signals as _ext_pat
    from src.quant.signal_processor import extract_smc_signals as _ext_smc

    orch = TradingOrchestrator(OrchestratorConfig(
        enable_brain=False,
        enable_ensemble=False,
    ))

    # Scan backwards from end to find a bar with a real signal
    logger.info("Scanning for actionable market moment...")
    best_decision = None
    best_offset = len(ohlcv) - WINDOW

    for offset in range(len(ohlcv) - WINDOW, max(WINDOW, len(ohlcv) - 3000), -240):
        chunk = ohlcv.iloc[offset:offset + WINDOW].copy()
        d = orch.analyze(symbol, timeframe, chunk)
        if d.action in ("LONG", "SHORT"):
            best_decision = d
            best_offset = offset
            break

    live_df = ohlcv.iloc[best_offset:best_offset + WINDOW].copy()
    decision = best_decision if best_decision else orch.analyze(symbol, timeframe, live_df)

    current_price = float(live_df["close"].iloc[-1])
    logger.info(f"Simulating live feed: {symbol} {timeframe}")
    logger.info(f"Current price: {current_price:.5f}")
    logger.info(f"Bar time: {live_df.index[-1]}")

    logger.info(f"Decision: {decision.action} (tier={decision.source_tier.name}, "
                f"conf={decision.confidence:.2f})")

    # ── 4. GATHER INDICATOR VALUES FOR DISPLAY ─────────────────────
    from src.quant.indicators import compute_all_indicators
    from src.quant.patterns import detect_all_patterns
    from src.quant.signal_processor import (
        extract_indicator_signals, extract_pattern_signals,
        aggregate_signals,
    )

    df_ind = compute_all_indicators(live_df)
    df_pat = detect_all_patterns(live_df)

    # Key indicators for display
    indicators = []

    # RSI
    rsi_val = float(df_ind["rsi"].iloc[-1])
    rsi_interp = "oversold" if rsi_val < 30 else ("overbought" if rsi_val > 70 else "neutral")
    indicators.append(("RSI (14)", f"{rsi_val:.1f}", rsi_interp if rsi_interp == "neutral" else ("bullish" if rsi_interp == "oversold" else "bearish")))

    # ADX
    adx_val = float(df_ind["adx"].iloc[-1])
    adx_interp = "strong" if adx_val > 25 else "weak"
    indicators.append(("ADX (14)", f"{adx_val:.1f}", "bullish" if adx_val > 25 else "neutral"))

    # MACD
    macd_val = float(df_ind["macd"].iloc[-1])
    macd_sig = float(df_ind["macd_signal"].iloc[-1])
    macd_interp = "bullish" if macd_val > macd_sig else "bearish"
    indicators.append(("MACD", f"{macd_val:.4f}", macd_interp))

    # CCI
    if "cci" in df_ind.columns:
        cci_val = float(df_ind["cci"].iloc[-1])
        cci_interp = "bullish" if cci_val < -100 else ("bearish" if cci_val > 100 else "neutral")
        indicators.append(("CCI (20)", f"{cci_val:.1f}", cci_interp))

    # Stochastic
    if "stoch_k" in df_ind.columns:
        k_val = float(df_ind["stoch_k"].iloc[-1])
        k_interp = "bullish" if k_val < 20 else ("bearish" if k_val > 80 else "neutral")
        indicators.append(("Stoch %K", f"{k_val:.1f}", k_interp))

    # ATR
    atr_val = float(df_ind["atr"].iloc[-1]) if "atr" in df_ind.columns else current_price * 0.01
    indicators.append(("ATR (14)", f"{atr_val:.5f}", "neutral"))

    # Bollinger
    if "bb_upper" in df_ind.columns:
        bb_up = float(df_ind["bb_upper"].iloc[-1])
        bb_lo = float(df_ind["bb_lower"].iloc[-1])
        if current_price > bb_up:
            bb_interp = "bearish"
        elif current_price < bb_lo:
            bb_interp = "bullish"
        else:
            bb_interp = "neutral"
        indicators.append(("Bollinger", f"{bb_lo:.2f}-{bb_up:.2f}", bb_interp))

    # ── 5. GATHER SIGNALS FOR DISPLAY ──────────────────────────────
    ind_signals = extract_indicator_signals(df_ind, symbol, timeframe)
    pat_signals = extract_pattern_signals(df_pat, symbol, timeframe)
    all_signals = ind_signals + pat_signals
    agg = aggregate_signals(all_signals, symbol)

    signals_detail = []
    for s in all_signals:
        signals_detail.append((s.source, s.direction.name, s.strength))

    # ── 6. DISPLAY ─────────────────────────────────────────────────
    print_signal_box(
        decision=decision,
        symbol=symbol,
        timeframe=timeframe,
        price=current_price,
        atr=atr_val,
        indicators=indicators,
        signals_detail=signals_detail,
    )

    # Summary
    elapsed = time.time() - t0
    print(f"{C.DIM}  Pipeline latency: {elapsed*1000:.0f}ms{C.RESET}")
    print(f"{C.DIM}  Signals analyzed: {len(all_signals)} ({agg.bullish_count} bull, {agg.bearish_count} bear){C.RESET}")
    print(f"{C.DIM}  Signal confidence: {agg.confidence:.1f}% → Direction: {agg.direction.name}{C.RESET}")
    print(f"{C.DIM}  Fallback tier used: {decision.source_tier.name} (Tier {int(decision.source_tier)}){C.RESET}")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
