#!/usr/bin/env python3
"""
GOLIATH XAU/USD — GPU Training con AI Reasoning Live & Simulazione Trade
=========================================================================

FUNZIONALITÀ:
  1. Scarica TUTTI i dati reali XAU/USD (GC=F) da Yahoo Finance
       - Daily  : dal 2000-01-01 ad oggi (~6500+ barre)
       - Hourly : ultimi 730 giorni (~11000+ barre) – limite Yahoo Finance
       - Combina i due timeframe per massimizzare i dati
  2. Calcola ~40 indicatori tecnici inline (no dipendenze esterne)
  3. Allena un Transformer GPU con:
       - Auto-detection AMD ROCm / NVIDIA CUDA / CPU fallback
       - Mixed Precision FP16
       - Gradient Accumulation
       - Cosine Annealing scheduler
  4. Mostra i PENSIERI dell'AI dopo ogni epoca:
       - Feature importance (gradient salience)
       - Attenzione temporale (quali barre storiche contano di più)
       - Breakdown confidenza SELL / HOLD / BUY
       - Regime di mercato rilevato
       - Ragionamento testuale della decisione
  5. Simula trade XAU/USD in tempo reale con:
       - Entrata (direzione, prezzo, lot size)
       - Stop Loss e Take Profit con barra di progresso
       - Aggiornamento tick-per-tick sul dataset reale
       - Chiusura con motivo (SL HIT / TP HIT / SIGNAL REVERSAL)
       - Statistiche cumulate (win rate, PnL totale)

UTILIZZO:
    python analysis/train_xau_gpu_live.py
    python analysis/train_xau_gpu_live.py --epochs 30
    python analysis/train_xau_gpu_live.py --demo     # solo simulazione, no training
    python analysis/train_xau_gpu_live.py --fast     # 10 epoche rapide (test)
"""

import os
import sys
import time
import json
import math
import argparse
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
from sklearn.preprocessing import StandardScaler
from loguru import logger

try:
    import yfinance as yf
    HAS_YFINANCE = True
except ImportError:
    HAS_YFINANCE = False
    logger.error("yfinance non trovato. Installa con: pip install yfinance")

# =============================================================================
# ANSI COLORS & TERMINAL UTILITIES
# =============================================================================

class C:
    """Codici ANSI per colori terminale."""
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    RED     = "\033[91m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    BLUE    = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN    = "\033[96m"
    WHITE   = "\033[97m"
    GRAY    = "\033[90m"
    BG_RED  = "\033[41m"
    BG_GREEN= "\033[42m"
    BG_BLUE = "\033[44m"
    BG_DARK = "\033[40m"


def bar_chart(value: float, width: int = 12,
              filled: str = "█", empty: str = "░") -> str:
    """Crea barra ASCII proporzionale al valore [0..1]."""
    n = max(0, min(width, round(value * width)))
    return filled * n + empty * (width - n)


def color_value(v: float, low: float = 0, high: float = 1) -> str:
    """Colora un valore: rosso=basso, giallo=medio, verde=alto."""
    norm = (v - low) / max(high - low, 1e-9)
    if norm < 0.33:
        return f"{C.RED}{v:.4f}{C.RESET}"
    elif norm < 0.66:
        return f"{C.YELLOW}{v:.4f}{C.RESET}"
    return f"{C.GREEN}{v:.4f}{C.RESET}"


def pnl_str(value: float, currency: str = "$") -> str:
    sign = "+" if value >= 0 else ""
    color = C.GREEN if value >= 0 else C.RED
    return f"{color}{sign}{currency}{value:.2f}{C.RESET}"


def divider(char: str = "═", width: int = 72, color: str = C.CYAN) -> str:
    return f"{color}{char * width}{C.RESET}"


def header(title: str, width: int = 72, color: str = C.CYAN) -> str:
    pad = (width - len(title) - 2) // 2
    return (f"{color}{'═' * pad} {C.BOLD}{title}{C.RESET}{color}"
            f" {'═' * (width - pad - len(title) - 2)}{C.RESET}")


# =============================================================================
# GPU DETECTION
# =============================================================================

def detect_gpu() -> Tuple[torch.device, bool, str]:
    """
    Rileva GPU disponibile: AMD ROCm o NVIDIA CUDA.
    Returns: (device, has_gpu, description)
    """
    if torch.cuda.is_available():
        name = torch.cuda.get_device_name(0)
        vram = torch.cuda.get_device_properties(0).total_memory / 1e9
        backend = "ROCm" if ("AMD" in name or "Radeon" in name) else "CUDA"
        desc = f"{name} [{backend}] VRAM: {vram:.1f}GB"
        return torch.device("cuda"), True, desc
    return torch.device("cpu"), False, "CPU (nessuna GPU rilevata)"


# =============================================================================
# DATA COLLECTION — XAU/USD REALE DA YAHOO FINANCE
# =============================================================================

DATA_DIR = Path(__file__).parent / "data"
XAU_DAILY_FILE = DATA_DIR / "xau_usd_daily.parquet"
XAU_HOURLY_FILE = DATA_DIR / "xau_usd_hourly.parquet"


def fetch_xau_daily() -> pd.DataFrame:
    """Scarica dati giornalieri GC=F dal 2000 ad oggi."""
    print(f"\n{C.CYAN}[DATA]{C.RESET} Scaricamento dati DAILY XAU/USD (GC=F) dal 2000...")
    try:
        ticker = yf.Ticker("GC=F")
        df = ticker.history(start="2000-01-01", interval="1d")
        if df.empty:
            raise ValueError("Nessun dato ricevuto per il daily")
        df = df.reset_index()
        df = df.rename(columns={
            "Date": "timestamp", "Open": "open", "High": "high",
            "Low": "low", "Close": "close", "Volume": "volume"
        })[["timestamp", "open", "high", "low", "close", "volume"]]
        df["timestamp"] = pd.to_datetime(df["timestamp"]).dt.tz_localize(None)
        df["timeframe"] = "D1"
        df = df.dropna().reset_index(drop=True)
        print(f"{C.GREEN}  ✓ Daily: {len(df):,} barre "
              f"({df['timestamp'].min().date()} → {df['timestamp'].max().date()}){C.RESET}")
        return df
    except Exception as e:
        print(f"{C.YELLOW}  ⚠ Daily fetch fallito: {e}{C.RESET}")
        return pd.DataFrame()


def fetch_xau_hourly() -> pd.DataFrame:
    """Scarica dati orari GC=F (limite Yahoo: 730 giorni)."""
    print(f"{C.CYAN}[DATA]{C.RESET} Scaricamento dati HOURLY XAU/USD (ultimi 730 giorni)...")
    try:
        start = (datetime.now() - timedelta(days=720)).strftime("%Y-%m-%d")
        ticker = yf.Ticker("GC=F")
        df = ticker.history(start=start, interval="1h")
        if df.empty:
            raise ValueError("Nessun dato orario ricevuto")
        df = df.reset_index()
        df = df.rename(columns={
            "Datetime": "timestamp", "Open": "open", "High": "high",
            "Low": "low", "Close": "close", "Volume": "volume"
        })[["timestamp", "open", "high", "low", "close", "volume"]]
        df["timestamp"] = pd.to_datetime(df["timestamp"]).dt.tz_localize(None)
        df["timeframe"] = "H1"
        df = df.dropna().reset_index(drop=True)
        print(f"{C.GREEN}  ✓ Hourly: {len(df):,} barre "
              f"({df['timestamp'].min().date()} → {df['timestamp'].max().date()}){C.RESET}")
        return df
    except Exception as e:
        print(f"{C.YELLOW}  ⚠ Hourly fetch fallito: {e}{C.RESET}")
        return pd.DataFrame()


def load_or_fetch_data(force_refresh: bool = False) -> pd.DataFrame:
    """Carica dati da cache Parquet o scarica da Yahoo Finance."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    daily_fresh = (not force_refresh and XAU_DAILY_FILE.exists()
                   and (time.time() - XAU_DAILY_FILE.stat().st_mtime) < 86400)
    hourly_fresh = (not force_refresh and XAU_HOURLY_FILE.exists()
                    and (time.time() - XAU_HOURLY_FILE.stat().st_mtime) < 3600)

    if daily_fresh:
        daily = pd.read_parquet(XAU_DAILY_FILE)
        print(f"{C.GREEN}[DATA]{C.RESET} Daily caricato da cache: {len(daily):,} barre")
    else:
        daily = fetch_xau_daily()
        if not daily.empty:
            daily.to_parquet(XAU_DAILY_FILE, compression="snappy")

    if hourly_fresh:
        hourly = pd.read_parquet(XAU_HOURLY_FILE)
        print(f"{C.GREEN}[DATA]{C.RESET} Hourly caricato da cache: {len(hourly):,} barre")
    else:
        hourly = fetch_xau_hourly()
        if not hourly.empty:
            hourly.to_parquet(XAU_HOURLY_FILE, compression="snappy")

    # Usa i dati hourly per il training (più granulari, più dati recenti)
    # Usa daily come fallback o per regime di mercato
    if not hourly.empty:
        df = hourly.copy()
        print(f"\n{C.BOLD}[DATA]{C.RESET} Training su HOURLY: {len(df):,} barre")
    elif not daily.empty:
        df = daily.copy()
        print(f"\n{C.BOLD}[DATA]{C.RESET} Training su DAILY: {len(df):,} barre")
    else:
        raise RuntimeError("Impossibile scaricare dati XAU/USD. Controlla la connessione.")

    df = df.sort_values("timestamp").reset_index(drop=True)
    return df


# =============================================================================
# FEATURE ENGINEERING — INDICATORI TECNICI INLINE
# =============================================================================

def compute_features(df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
    """
    Calcola ~40 indicatori tecnici. Tutti normalizzati o stazionari.
    Non usa dipendenze esterne (solo numpy/pandas).
    """
    close = df["close"].values.astype(np.float64)
    high  = df["high"].values.astype(np.float64)
    low   = df["low"].values.astype(np.float64)
    vol   = df["volume"].values.astype(np.float64)
    n     = len(close)

    feat = {}

    # --- Log Returns ---
    lr = np.zeros(n)
    lr[1:] = np.log(close[1:] / np.where(close[:-1] > 0, close[:-1], 1e-9))
    feat["lr_1"]  = lr
    feat["lr_5"]  = pd.Series(lr).rolling(5).sum().fillna(0).values
    feat["lr_10"] = pd.Series(lr).rolling(10).sum().fillna(0).values
    feat["lr_20"] = pd.Series(lr).rolling(20).sum().fillna(0).values

    # --- Rolling Volatility ---
    feat["vol_10"]  = pd.Series(lr).rolling(10).std().fillna(0).values
    feat["vol_20"]  = pd.Series(lr).rolling(20).std().fillna(0).values
    feat["vol_50"]  = pd.Series(lr).rolling(50).std().fillna(0).values

    # --- RSI ---
    def compute_rsi(prices: np.ndarray, period: int = 14) -> np.ndarray:
        delta = np.diff(prices, prepend=prices[0])
        gain  = np.where(delta > 0, delta, 0.0)
        loss  = np.where(delta < 0, -delta, 0.0)
        avg_g = pd.Series(gain).ewm(com=period-1, adjust=False).mean().values
        avg_l = pd.Series(loss).ewm(com=period-1, adjust=False).mean().values
        rs    = avg_g / np.where(avg_l > 0, avg_l, 1e-9)
        return 100 - (100 / (1 + rs))

    rsi14 = compute_rsi(close, 14)
    rsi21 = compute_rsi(close, 21)
    feat["rsi14"]  = (rsi14 - 50) / 50          # normalizzato [-1, +1]
    feat["rsi21"]  = (rsi21 - 50) / 50
    feat["rsi14_raw"] = rsi14 / 100

    # --- MACD ---
    ema12 = pd.Series(close).ewm(span=12, adjust=False).mean().values
    ema26 = pd.Series(close).ewm(span=26, adjust=False).mean().values
    macd_line = ema12 - ema26
    macd_sig  = pd.Series(macd_line).ewm(span=9, adjust=False).mean().values
    macd_hist = macd_line - macd_sig
    # Normalizza diviso per prezzo
    feat["macd_line"] = macd_line / np.where(close > 0, close, 1)
    feat["macd_sig"]  = macd_sig  / np.where(close > 0, close, 1)
    feat["macd_hist"] = macd_hist / np.where(close > 0, close, 1)

    # --- Bollinger Bands ---
    sma20 = pd.Series(close).rolling(20).mean().values
    std20 = pd.Series(close).rolling(20).std().fillna(1).values
    feat["bb_pct_b"] = np.where(std20 > 0, (close - (sma20 - 2*std20)) / (4*std20 + 1e-9), 0.5)
    feat["bb_width"] = np.where(sma20 > 0, 4*std20 / sma20, 0)

    # --- ATR ---
    def compute_atr(h: np.ndarray, l: np.ndarray, c: np.ndarray, p: int = 14) -> np.ndarray:
        prev_c = np.roll(c, 1)
        prev_c[0] = c[0]
        tr = np.maximum(h - l, np.maximum(np.abs(h - prev_c), np.abs(l - prev_c)))
        return pd.Series(tr).ewm(com=p-1, adjust=False).mean().values

    atr14 = compute_atr(high, low, close, 14)
    atr7  = compute_atr(high, low, close, 7)
    feat["atr14_norm"] = np.where(close > 0, atr14 / close, 0)
    feat["atr7_norm"]  = np.where(close > 0, atr7  / close, 0)

    # --- Stochastic ---
    def stochastic(h, l, c, kp=14, dp=3):
        k_arr = np.zeros(len(c))
        for i in range(kp, len(c)):
            hh = np.max(h[i-kp:i+1])
            ll = np.min(l[i-kp:i+1])
            k_arr[i] = ((c[i] - ll) / (hh - ll + 1e-9)) * 100
        d_arr = pd.Series(k_arr).rolling(dp).mean().fillna(k_arr[0]).values
        return k_arr, d_arr

    stoch_k, stoch_d = stochastic(high, low, close)
    feat["stoch_k"]  = (stoch_k - 50) / 50
    feat["stoch_d"]  = (stoch_d - 50) / 50

    # --- ADX ---
    def compute_adx(h, l, c, p=14):
        prev_h = np.roll(h, 1); prev_h[0] = h[0]
        prev_l = np.roll(l, 1); prev_l[0] = l[0]
        plus_dm  = np.where((h - prev_h) > (prev_l - l), np.maximum(h - prev_h, 0), 0)
        minus_dm = np.where((prev_l - l) > (h - prev_h), np.maximum(prev_l - l, 0), 0)
        atr = compute_atr(h, l, c, p)
        plus_di  = 100 * pd.Series(plus_dm).ewm(com=p-1, adjust=False).mean().values / (atr + 1e-9)
        minus_di = 100 * pd.Series(minus_dm).ewm(com=p-1, adjust=False).mean().values / (atr + 1e-9)
        dx = np.where(plus_di + minus_di > 0,
                      100 * np.abs(plus_di - minus_di) / (plus_di + minus_di + 1e-9), 0)
        return pd.Series(dx).ewm(com=p-1, adjust=False).mean().values, plus_di, minus_di

    adx, pdi, mdi = compute_adx(high, low, close)
    feat["adx"]      = adx / 100
    feat["pdi_mdi"]  = (pdi - mdi) / (pdi + mdi + 1e-9)  # trend direction

    # --- EMA Crossovers ---
    ema9   = pd.Series(close).ewm(span=9,   adjust=False).mean().values
    ema21  = pd.Series(close).ewm(span=21,  adjust=False).mean().values
    ema50  = pd.Series(close).ewm(span=50,  adjust=False).mean().values
    ema200 = pd.Series(close).ewm(span=200, adjust=False).mean().values

    feat["ema9_50_cross"]   = np.where(close > 0, (ema9 - ema50)   / close, 0)
    feat["ema21_50_cross"]  = np.where(close > 0, (ema21 - ema50)  / close, 0)
    feat["ema50_200_cross"] = np.where(close > 0, (ema50 - ema200) / close, 0)
    feat["price_ema50"]     = np.where(close > 0, (close - ema50)  / close, 0)

    # --- Williams %R ---
    def williams_r(h, l, c, p=14):
        wr = np.zeros(len(c))
        for i in range(p, len(c)):
            hh = np.max(h[i-p:i+1])
            ll = np.min(l[i-p:i+1])
            wr[i] = -100 * (hh - c[i]) / (hh - ll + 1e-9)
        return wr

    wr14 = williams_r(high, low, close)
    feat["williams_r"] = (wr14 + 50) / 50  # da [-100,0] a [-1,+1]

    # --- CCI ---
    def compute_cci(h, l, c, p=14):
        tp = (h + l + c) / 3
        tp_s = pd.Series(tp)
        sma_tp = tp_s.rolling(p).mean().fillna(tp[0]).values
        mad = tp_s.rolling(p).apply(lambda x: np.mean(np.abs(x - np.mean(x)))).fillna(0.001).values
        return (tp - sma_tp) / (0.015 * mad + 1e-9)

    cci = compute_cci(high, low, close)
    feat["cci"] = np.clip(cci / 200, -1, 1)

    # --- Volume Features ---
    vol_sma20 = pd.Series(vol).rolling(20).mean().fillna(vol.mean()).values
    feat["vol_ratio"]  = np.where(vol_sma20 > 0, vol / vol_sma20 - 1, 0)
    # OBV normalizzato
    obv = np.zeros(n)
    for i in range(1, n):
        if close[i] > close[i-1]:
            obv[i] = obv[i-1] + vol[i]
        elif close[i] < close[i-1]:
            obv[i] = obv[i-1] - vol[i]
        else:
            obv[i] = obv[i-1]
    obv_std = np.std(obv) + 1e-9
    feat["obv_norm"] = (obv - np.mean(obv)) / obv_std

    # --- High/Low Range ---
    feat["hl_range"] = np.where(close > 0, (high - low) / close, 0)

    # --- Momentum (Rate of Change) ---
    for p in [5, 10, 20]:
        rolled = pd.Series(close).pct_change(p).fillna(0).values
        feat[f"roc_{p}"] = np.clip(rolled, -0.5, 0.5)

    # Assembla DataFrame features
    feat_df = pd.DataFrame(feat, index=df.index)
    feat_names = list(feat.keys())

    # Sostituisci inf e NaN
    feat_df = feat_df.replace([np.inf, -np.inf], 0).fillna(0)

    return feat_df, feat_names


# =============================================================================
# LABEL GENERATION — TRIPLE BARRIER
# =============================================================================

def create_labels(df: pd.DataFrame, tp_pct: float = 0.015,
                  sl_pct: float = 0.008, horizon: int = 20) -> np.ndarray:
    """
    Triple Barrier Labeling per XAU/USD.
    Uscita con:
      2 = BUY   (price tocca TP prima di SL)
      0 = SELL  (price tocca SL prima di TP)
      1 = HOLD  (scaduto horizon senza toccare nessun livello)
    """
    close = df["close"].values
    labels = np.ones(len(close), dtype=np.int64)  # Default HOLD

    for i in range(len(close) - horizon):
        entry = close[i]
        tp_long  = entry * (1 + tp_pct)
        sl_long  = entry * (1 - sl_pct)
        tp_short = entry * (1 - tp_pct)
        sl_short = entry * (1 + sl_pct)

        future = close[i+1:i+1+horizon]
        # Controlla quale livello viene toccato per primo
        hit_tp_long  = np.argmax(future >= tp_long)  if np.any(future >= tp_long)  else horizon
        hit_sl_long  = np.argmax(future <= sl_long)  if np.any(future <= sl_long)  else horizon
        hit_tp_short = np.argmax(future <= tp_short) if np.any(future <= tp_short) else horizon
        hit_sl_short = np.argmax(future >= sl_short) if np.any(future >= sl_short) else horizon

        # Forza dominante
        if hit_tp_long < hit_sl_long and hit_tp_long < horizon:
            labels[i] = 2  # BUY
        elif hit_sl_long < hit_tp_long and hit_sl_long < horizon:
            labels[i] = 0  # SELL
        elif hit_tp_short < hit_sl_short and hit_tp_short < horizon:
            labels[i] = 0  # SELL
        elif hit_sl_short < hit_tp_short and hit_sl_short < horizon:
            labels[i] = 2  # BUY
        # else HOLD

    return labels


# =============================================================================
# TRANSFORMER MODEL — STANDALONE (no dipendenze engine/)
# =============================================================================

class PositionalEncoding(nn.Module):
    def __init__(self, d_model: int, max_len: int = 512, dropout: float = 0.1):
        super().__init__()
        self.dropout = nn.Dropout(p=dropout)
        pe = torch.zeros(max_len, d_model)
        pos = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div = torch.exp(torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model))
        pe[:, 0::2] = torch.sin(pos * div)
        pe[:, 1::2] = torch.cos(pos * div)
        self.register_buffer("pe", pe.unsqueeze(0))  # [1, max_len, d_model]

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = x + self.pe[:, :x.size(1)]
        return self.dropout(x)


class XAUTransformer(nn.Module):
    """
    Transformer per XAU/USD.
    Input:  [batch, seq_len, n_features]
    Output: {direction: [batch,3], confidence: [batch], sl_dist: [batch], tp_dist: [batch]}
    """
    def __init__(self, n_features: int, d_model: int = 128, nhead: int = 4,
                 num_layers: int = 4, dropout: float = 0.2, seq_len: int = 64):
        super().__init__()
        self.input_proj = nn.Linear(n_features, d_model)
        self.pos_enc    = PositionalEncoding(d_model, max_len=512, dropout=dropout)
        enc_layer = nn.TransformerEncoderLayer(
            d_model=d_model, nhead=nhead, dim_feedforward=d_model * 4,
            dropout=dropout, batch_first=True, norm_first=True
        )
        self.transformer = nn.TransformerEncoder(enc_layer, num_layers=num_layers,
                                                   enable_nested_tensor=False)
        self.norm = nn.LayerNorm(d_model)

        # Output heads
        self.direction_head  = nn.Sequential(
            nn.Linear(d_model, d_model // 2), nn.GELU(),
            nn.Dropout(dropout), nn.Linear(d_model // 2, 3)
        )
        self.confidence_head = nn.Sequential(
            nn.Linear(d_model, d_model // 4), nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(d_model // 4, 1), nn.Sigmoid()
        )
        self.sl_head = nn.Sequential(
            nn.Linear(d_model, 32), nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(32, 1), nn.Softplus()
        )
        self.tp_head = nn.Sequential(
            nn.Linear(d_model, 32), nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(32, 1), nn.Softplus()
        )

    def forward(self, x: torch.Tensor) -> Dict[str, torch.Tensor]:
        # x: [B, T, F]
        h = self.input_proj(x)           # [B, T, d_model]
        h = self.pos_enc(h)
        h = self.transformer(h)          # [B, T, d_model]
        h = self.norm(h)
        # Usa l'ultimo token come rappresentazione
        last = h[:, -1, :]              # [B, d_model]
        return {
            "direction":  self.direction_head(last),   # [B, 3]
            "confidence": self.confidence_head(last).squeeze(-1),  # [B]
            "sl_dist":    self.sl_head(last).squeeze(-1) * 0.02,   # [B]
            "tp_dist":    self.tp_head(last).squeeze(-1) * 0.04,   # [B]
        }


# =============================================================================
# AI REASONER — DISPLAY PENSIERI IN TEMPO REALE
# =============================================================================

FEAT_LABELS: Dict[str, str] = {
    "rsi14":         "RSI(14)",
    "rsi21":         "RSI(21)",
    "macd_hist":     "MACD Histogram",
    "macd_line":     "MACD Line",
    "bb_pct_b":      "Bollinger %B",
    "bb_width":      "Bollinger Width",
    "atr14_norm":    "ATR(14) normaliz.",
    "stoch_k":       "Stochastic %K",
    "stoch_d":       "Stochastic %D",
    "adx":           "ADX(14)",
    "pdi_mdi":       "+DI − −DI",
    "ema9_50_cross": "EMA9/EMA50 cross",
    "ema21_50_cross":"EMA21/EMA50 cross",
    "ema50_200_cross":"EMA50/EMA200 cross",
    "price_ema50":   "Price vs EMA50",
    "williams_r":    "Williams %R",
    "cci":           "CCI(14)",
    "vol_ratio":     "Volume vs Media",
    "obv_norm":      "OBV normalizzato",
    "hl_range":      "High-Low Range",
    "lr_1":          "Log Return 1B",
    "lr_5":          "Log Return 5B",
    "lr_10":         "Log Return 10B",
    "lr_20":         "Log Return 20B",
    "vol_10":        "Volatilità 10B",
    "vol_20":        "Volatilità 20B",
    "roc_5":         "Rate of Change 5B",
    "roc_10":        "Rate of Change 10B",
    "roc_20":        "Rate of Change 20B",
}

DIRECTION_NAMES = {0: "SELL", 1: "HOLD", 2: "BUY"}
DIRECTION_COLORS = {0: C.RED, 1: C.YELLOW, 2: C.GREEN}
DIRECTION_ARROWS = {0: "▼ SELL", 1: "◆ HOLD", 2: "▲ BUY"}


class AIReasoner:
    """Mostra i pensieri e ragionamenti dell'AI in tempo reale."""

    def __init__(self, model: XAUTransformer, scaler: StandardScaler,
                 feat_names: List[str], device: torch.device):
        self.model      = model
        self.scaler     = scaler
        self.feat_names = feat_names
        self.device     = device

    def reason(self, x_seq: np.ndarray, df_window: pd.DataFrame,
               current_price: float, epoch: int) -> Dict:
        """
        Esegue inferenza e produce reasoning completo.
        x_seq: [1, seq_len, n_features] numpy array (già scalato)
        """
        self.model.eval()

        # ── Pass 1: inferenza senza gradienti (veloce)
        with torch.no_grad():
            x_t = torch.FloatTensor(x_seq).to(self.device)
            out = self.model(x_t)
            direction_logits = out["direction"][0]
            direction_probs  = torch.softmax(direction_logits, dim=0).cpu().numpy()
            confidence       = out["confidence"][0].item()
            sl_dist          = out["sl_dist"][0].item()
            tp_dist          = out["tp_dist"][0].item()
            decision         = int(np.argmax(direction_probs))

        # ── Pass 2: gradient salience per feature importance (richiede grad)
        x_t2 = torch.FloatTensor(x_seq).to(self.device)
        x_t2.requires_grad_(True)
        self.model.zero_grad()
        out2 = self.model(x_t2)
        out2["direction"][0, decision].backward()
        grads = x_t2.grad[0].abs().detach().cpu().numpy()  # [seq_len, n_features]
        feat_importance = grads.mean(axis=0)               # [n_features]

        # Temporal salience (quale barra storica conta di più)
        temporal_sal = grads.mean(axis=1)         # [seq_len]

        # Market regime (semplice euristica)
        adx_idx = self.feat_names.index("adx") if "adx" in self.feat_names else 0
        rsi_idx = self.feat_names.index("rsi14_raw") if "rsi14_raw" in self.feat_names else 1
        vol_idx = self.feat_names.index("vol_20") if "vol_20" in self.feat_names else 2

        last_feats = x_seq[0, -1, :]  # ultimo timestep (scalato)
        # Ritorna a valori grezzi per interpretazione (approssimato)
        adx_raw = max(0, min(100, abs(last_feats[adx_idx]) * 100)) if adx_idx < len(last_feats) else 25
        regime = ("TRENDING" if adx_raw > 35 else
                  "RANGING"  if adx_raw < 20 else "MISTO")

        return {
            "decision":      decision,
            "probs":         direction_probs,
            "confidence":    confidence,
            "sl_dist":       sl_dist,
            "tp_dist":       tp_dist,
            "feat_importance": feat_importance,
            "temporal_sal":  temporal_sal,
            "regime":        regime,
            "price":         current_price,
            "epoch":         epoch,
        }

    def display(self, r: Dict, feat_names: List[str]):
        """Stampa il reasoning completo dell'AI."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        decision  = r["decision"]
        probs     = r["probs"]
        conf      = r["confidence"]
        price     = r["price"]
        regime    = r["regime"]
        sl_dist   = r["sl_dist"]
        tp_dist   = r["tp_dist"]

        dcol = DIRECTION_COLORS[decision]
        dname = DIRECTION_ARROWS[decision]

        print()
        print(header(f"AI REASONING ENGINE — XAU/USD   [Epoca {r['epoch']}]"))
        print(f"  {C.DIM}{now}{C.RESET}")
        print()

        # Market overview
        print(f"  {C.BOLD}ANALISI MERCATO:{C.RESET}")
        print(f"  ├─ Prezzo corrente : {C.BOLD}${price:,.2f}{C.RESET}")
        regime_col = C.GREEN if "TREND" in regime else (C.YELLOW if "MISTO" in regime else C.CYAN)
        print(f"  ├─ Regime rilevato : {regime_col}{C.BOLD}{regime}{C.RESET}")
        sl_price = price * (1 - sl_dist)
        tp_price = price * (1 + tp_dist)
        print(f"  ├─ Stop Loss calc. : {C.RED}${sl_price:,.2f}{C.RESET}  "
              f"({sl_dist*100:.2f}% / {sl_dist*price:.2f}$)")
        print(f"  └─ Take Profit cal.: {C.GREEN}${tp_price:,.2f}{C.RESET}  "
              f"({tp_dist*100:.2f}% / {tp_dist*price:.2f}$)")
        print()

        # Top features
        feat_imp = r["feat_importance"]
        top_idx  = np.argsort(feat_imp)[::-1][:12]
        max_imp  = feat_imp[top_idx[0]] + 1e-9

        print(f"  {C.BOLD}FATTORI CHIAVE{C.RESET} "
              f"{C.DIM}(importanza gradient salience, top 12):{C.RESET}")
        for rank, idx in enumerate(top_idx):
            if idx >= len(feat_names):
                continue
            name = FEAT_LABELS.get(feat_names[idx], feat_names[idx])
            imp  = feat_imp[idx] / max_imp
            bstr = bar_chart(imp, width=10)
            connector = "└─" if rank == min(11, len(top_idx)-1) else "├─"
            # Colora la feature in base al segno della sua attivazione (semplificato)
            val = r.get("feat_importance", [])[idx] if idx < len(r["feat_importance"]) else 0
            print(f"  {connector} {bstr}  {color_value(imp)}  {C.DIM}{name:<28}{C.RESET}")
        print()

        # Temporal attention (ultimi 10 timestep più importanti)
        temp_sal = r["temporal_sal"]
        seq_len  = len(temp_sal)
        # Mostra gli ultimi 16 periodi
        show_n = min(16, seq_len)
        tail_sal = temp_sal[-show_n:]
        max_t = max(tail_sal) + 1e-9

        print(f"  {C.BOLD}ATTENZIONE TEMPORALE{C.RESET} "
              f"{C.DIM}(rilevanza su ultime {show_n} barre):{C.RESET}")
        print("  ", end="")
        for i, s in enumerate(tail_sal):
            norm = s / max_t
            bh = int(norm * 8)
            blocks = ["░", "▁", "▂", "▃", "▄", "▅", "▆", "▇", "█"]
            col = C.GREEN if norm > 0.66 else (C.YELLOW if norm > 0.33 else C.DIM)
            print(f"{col}{blocks[bh]}{C.RESET}", end="")
        print(f"  {C.DIM}← passato    presente →{C.RESET}")
        print()

        # Probabilità per classe
        print(f"  {C.BOLD}PROBABILITÀ PER DIREZIONE:{C.RESET}")
        for cls in [2, 1, 0]:
            p = probs[cls]
            col = DIRECTION_COLORS[cls]
            bstr = bar_chart(p, width=20)
            print(f"  {'  ' if cls != decision else C.BOLD + '→'} "
                  f"{col}{DIRECTION_NAMES[cls]:>4}{C.RESET}  "
                  f"{col}{bstr}{C.RESET}  {C.BOLD if cls == decision else ''}{p*100:5.1f}%{C.RESET}")
        print()

        # Decisione finale
        print(f"  {C.BOLD}DECISIONE FINALE:{C.RESET}")
        print(f"  ╔{'═'*42}╗")
        conf_bar = bar_chart(conf, width=10)
        print(f"  ║  {dcol}{C.BOLD}{dname:>6}{C.RESET}    "
              f"Confidenza: {dcol}{C.BOLD}{conf*100:5.1f}%{C.RESET}  {conf_bar}   ║")

        # Ragionamento testuale
        rationale = _build_rationale(decision, probs, conf, regime, tp_dist, sl_dist)
        print(f"  ║  {C.DIM}{rationale:<40}{C.RESET}║")
        print(f"  ╚{'═'*42}╝")
        print(divider())


def _build_rationale(decision: int, probs: np.ndarray, conf: float,
                     regime: str, tp: float, sl: float) -> str:
    """Genera testo di ragionamento."""
    dominance = probs[decision] - max(p for i, p in enumerate(probs) if i != decision)
    if decision == 2:  # BUY
        if conf > 0.75:
            return f"Segnale rialzista forte. R:R={tp/sl:.1f}. Trend confermato."
        return f"Leggero bias rialzista in regime {regime}. R:R={tp/sl:.1f}."
    elif decision == 0:  # SELL
        if conf > 0.75:
            return f"Segnale ribassista forte. R:R={tp/sl:.1f}. Momentum negativo."
        return f"Possibile correzione in regime {regime}. R:R={tp/sl:.1f}."
    else:  # HOLD
        if dominance < 0.1:
            return "Mercato indeciso. Attesa di conferma prima di entrare."
        return f"Consolidamento. Regime {regime}. Aspetto breakout."


# =============================================================================
# TRADE SIMULATOR — SL/TP CON DISPLAY LIVE
# =============================================================================

class SimulatedTrade:
    """Rappresenta un trade simulato con SL/TP."""
    def __init__(self, direction: int, entry_price: float,
                 sl_price: float, tp_price: float,
                 lot_size: float = 0.10, bar_idx: int = 0):
        self.direction   = direction
        self.entry_price = entry_price
        self.sl_price    = sl_price
        self.tp_price    = tp_price
        self.lot_size    = lot_size
        self.bar_idx     = bar_idx
        self.open_time   = datetime.now()
        self.bars_open   = 0
        self.is_open     = True
        self.exit_reason = ""
        self.exit_price  = 0.0
        self.pnl_usd     = 0.0
        # Per XAU/USD: 1 lot = 100 oz, pip = $0.1
        self.pip_value   = lot_size * 100 * 0.1  # $ per pip ($0.01)


class TradeSimulator:
    """
    Gestisce apertura e chiusura di trade simulati su dati reali XAU/USD.
    Mostra SL/TP live nel terminale.
    """
    def __init__(self):
        self.open_trades:   List[SimulatedTrade] = []
        self.closed_trades: List[SimulatedTrade] = []
        self.total_pnl   = 0.0
        self.wins        = 0
        self.losses      = 0

    def open_trade(self, decision: int, current_price: float,
                   sl_dist: float, tp_dist: float,
                   lot_size: float = 0.10, bar_idx: int = 0) -> Optional[SimulatedTrade]:
        """Apre un nuovo trade simulato."""
        if decision == 1:  # HOLD — nessun trade
            return None
        if len(self.open_trades) >= 2:  # max 2 trade aperti
            return None

        if decision == 2:  # LONG
            sl_price = current_price * (1 - sl_dist)
            tp_price = current_price * (1 + tp_dist)
        else:              # SHORT
            sl_price = current_price * (1 + sl_dist)
            tp_price = current_price * (1 - tp_dist)

        trade = SimulatedTrade(decision, current_price, sl_price, tp_price,
                               lot_size, bar_idx)
        self.open_trades.append(trade)
        self._display_open(trade)
        return trade

    def _display_open(self, t: SimulatedTrade):
        dcol = C.GREEN if t.direction == 2 else C.RED
        dname = "LONG ▲" if t.direction == 2 else "SHORT ▼"
        tp_dist_pct = abs(t.tp_price - t.entry_price) / t.entry_price * 100
        sl_dist_pct = abs(t.sl_price - t.entry_price) / t.entry_price * 100
        tp_usd      = abs(t.tp_price - t.entry_price) * t.lot_size * 100
        sl_usd      = abs(t.sl_price - t.entry_price) * t.lot_size * 100

        print()
        print(f"  {C.BOLD}{'─'*50}{C.RESET}")
        print(f"  {C.BG_DARK} TRADE APERTO {C.RESET} {dcol}{C.BOLD}{dname}{C.RESET}  "
              f"{C.BOLD}XAU/USD   lot {t.lot_size:.2f}{C.RESET}")
        print(f"  ┌{'─'*48}┐")
        print(f"  │  Entrata  : {C.BOLD}${t.entry_price:>10,.2f}{C.RESET}"
              f"                    │")
        print(f"  │  Take Profit: {C.GREEN}${t.tp_price:>10,.2f}{C.RESET}"
              f"  (+{tp_dist_pct:.2f}% / +${tp_usd:.2f})  │")
        print(f"  │  Stop Loss  : {C.RED}${t.sl_price:>10,.2f}{C.RESET}"
              f"  (-{sl_dist_pct:.2f}% / -${sl_usd:.2f})  │")
        print(f"  └{'─'*48}┘")

    def update_trades(self, current_price: float,
                      current_high: float, current_low: float,
                      bar_idx: int):
        """Aggiorna i trade aperti con il nuovo prezzo e controlla SL/TP."""
        closed_now = []
        for t in self.open_trades:
            t.bars_open += 1

            # Check SL/TP
            if t.direction == 2:  # LONG
                if current_low <= t.sl_price:
                    t.exit_price  = t.sl_price
                    t.exit_reason = "STOP LOSS"
                    t.is_open     = False
                elif current_high >= t.tp_price:
                    t.exit_price  = t.tp_price
                    t.exit_reason = "TAKE PROFIT"
                    t.is_open     = False
            else:  # SHORT
                if current_high >= t.sl_price:
                    t.exit_price  = t.sl_price
                    t.exit_reason = "STOP LOSS"
                    t.is_open     = False
                elif current_low <= t.tp_price:
                    t.exit_price  = t.tp_price
                    t.exit_reason = "TAKE PROFIT"
                    t.is_open     = False

            # Calcola PnL
            if t.direction == 2:
                t.pnl_usd = (current_price - t.entry_price) * t.lot_size * 100
            else:
                t.pnl_usd = (t.entry_price - current_price) * t.lot_size * 100

            if not t.is_open:
                if t.direction == 2:
                    final_pnl = (t.exit_price - t.entry_price) * t.lot_size * 100
                else:
                    final_pnl = (t.entry_price - t.exit_price) * t.lot_size * 100
                t.pnl_usd = final_pnl
                closed_now.append(t)

            # Display progresso
            self._display_progress(t, current_price)

        for t in closed_now:
            self.open_trades.remove(t)
            self.closed_trades.append(t)
            self.total_pnl += t.pnl_usd
            if t.pnl_usd > 0:
                self.wins += 1
            else:
                self.losses += 1
            self._display_close(t)

    def _display_progress(self, t: SimulatedTrade, current_price: float):
        """Mostra barra di progresso SL → prezzo → TP."""
        if t.direction == 2:  # LONG
            total_range = t.tp_price - t.sl_price
            progress    = (current_price - t.sl_price) / max(total_range, 1e-9)
        else:  # SHORT
            total_range = t.sl_price - t.tp_price
            progress    = (t.sl_price - current_price) / max(total_range, 1e-9)

        progress = max(0, min(1, progress))
        bar_width = 30
        pos = int(progress * bar_width)

        bar_str = ""
        for i in range(bar_width):
            if i < pos:
                bar_str += f"{C.GREEN}─{C.RESET}"
            elif i == pos:
                bar_str += f"{C.BOLD}●{C.RESET}"
            else:
                bar_str += f"{C.DIM}─{C.RESET}"

        dcol  = C.GREEN if t.direction == 2 else C.RED
        pnl   = pnl_str(t.pnl_usd)
        dname = "LONG" if t.direction == 2 else "SHORT"

        if t.is_open:
            print(f"  [{dname}] {C.RED}SL{C.RESET} {bar_str} {C.GREEN}TP{C.RESET}  "
                  f"${current_price:,.2f}  P&L: {pnl}  "
                  f"{C.DIM}barra {t.bars_open}{C.RESET}")

    def _display_close(self, t: SimulatedTrade):
        """Mostra chiusura trade con risultato."""
        won    = t.pnl_usd > 0
        reason = t.exit_reason
        col    = C.GREEN if won else C.RED
        emoji  = "✓ WIN " if won else "✗ LOSS"
        dname  = "LONG ▲" if t.direction == 2 else "SHORT ▼"
        total  = len(self.closed_trades)
        wr     = self.wins / total * 100 if total > 0 else 0

        print()
        print(f"  {col}{'═'*52}{C.RESET}")
        print(f"  {col}{C.BOLD}  TRADE CHIUSO — {reason}{C.RESET}")
        print(f"  {col}{'─'*52}{C.RESET}")
        print(f"  {emoji}  {dname}  |  "
              f"Entrata: ${t.entry_price:,.2f}  "
              f"Uscita: ${t.exit_price:,.2f}")
        print(f"  P&L: {pnl_str(t.pnl_usd)}    Durata: {t.bars_open} barre")
        print(f"  Statistiche: "
              f"{C.GREEN}W:{self.wins}{C.RESET} / {C.RED}L:{self.losses}{C.RESET}  "
              f"WR:{wr:.1f}%  "
              f"Tot P&L: {pnl_str(self.total_pnl)}")
        print(f"  {col}{'═'*52}{C.RESET}")

    def display_summary(self):
        """Mostra sommario finale dei trade."""
        total = len(self.closed_trades)
        if total == 0:
            print(f"\n  {C.DIM}Nessun trade simulato.{C.RESET}")
            return
        wr = self.wins / total * 100
        avg_pnl = self.total_pnl / total
        print()
        print(header("SOMMARIO TRADE SIMULATI"))
        print(f"  Trade totali   : {total}")
        print(f"  Win  : {C.GREEN}{self.wins}{C.RESET}")
        print(f"  Loss : {C.RED}{self.losses}{C.RESET}")
        print(f"  Win Rate       : {C.BOLD}{wr:.1f}%{C.RESET}")
        print(f"  P&L totale     : {pnl_str(self.total_pnl)}")
        print(f"  P&L medio/trade: {pnl_str(avg_pnl)}")
        print(divider())


# =============================================================================
# TRAINING ENGINE
# =============================================================================

CHECKPOINT_DIR = Path(__file__).parent / "models_checkpoint"


def build_sequences(feat_arr: np.ndarray, labels: np.ndarray,
                    seq_len: int = 64) -> Tuple[np.ndarray, np.ndarray]:
    """Crea sequenze sliding-window."""
    n = min(len(feat_arr), len(labels))
    X, y = [], []
    for i in range(n - seq_len):
        X.append(feat_arr[i:i+seq_len])
        y.append(labels[i + seq_len - 1])
    return np.array(X, dtype=np.float32), np.array(y, dtype=np.int64)


def _augment_batch(xb: torch.Tensor, noise_std: float = 0.03,
                    mask_ratio: float = 0.10) -> torch.Tensor:
    """Data augmentation: Gaussian noise + temporal masking."""
    # Gaussian noise
    xb = xb + torch.randn_like(xb) * noise_std
    # Temporal masking: zero-out 10% dei timestep casuali
    B, T, F = xb.shape
    mask = torch.rand(B, T, 1, device=xb.device) > mask_ratio
    xb = xb * mask.float()
    return xb


def train_epoch(model, loader, optimizer, criterion, device,
                grad_scaler=None, accumulation: int = 4) -> Tuple[float, float]:
    model.train()
    total_loss, correct, total = 0.0, 0, 0
    optimizer.zero_grad()

    for step, (xb, yb) in enumerate(loader):
        xb, yb = xb.to(device), yb.to(device)
        # Data augmentation (solo durante il training)
        xb = _augment_batch(xb)

        if grad_scaler:
            with torch.amp.autocast("cuda"):
                out  = model(xb)
                loss = criterion(out["direction"], yb) / accumulation
            grad_scaler.scale(loss).backward()
            if (step + 1) % accumulation == 0:
                grad_scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
                grad_scaler.step(optimizer)
                grad_scaler.update()
                optimizer.zero_grad()
        else:
            out  = model(xb)
            loss = criterion(out["direction"], yb) / accumulation
            loss.backward()
            if (step + 1) % accumulation == 0:
                torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
                optimizer.step()
                optimizer.zero_grad()

        total_loss += loss.item() * accumulation
        preds = out["direction"].argmax(1)
        correct += (preds == yb).sum().item()
        total   += yb.size(0)

    return total_loss / len(loader), 100 * correct / total


@torch.no_grad()
def evaluate(model, loader, criterion, device,
             grad_scaler=None) -> Tuple[float, float]:
    model.eval()
    total_loss, correct, total = 0.0, 0, 0
    for xb, yb in loader:
        xb, yb = xb.to(device), yb.to(device)
        if grad_scaler:
            with torch.amp.autocast("cuda"):
                out  = model(xb)
                loss = criterion(out["direction"], yb)
        else:
            out  = model(xb)
            loss = criterion(out["direction"], yb)
        total_loss += loss.item()
        preds = out["direction"].argmax(1)
        correct += (preds == yb).sum().item()
        total   += yb.size(0)
    return total_loss / len(loader), 100 * correct / total


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="GOLIATH XAU/USD — GPU Training con AI Reasoning Live")
    parser.add_argument("--epochs",  type=int,   default=50,
                        help="Numero epoche (default: 50)")
    parser.add_argument("--batch",   type=int,   default=128,
                        help="Batch size (default: 128)")
    parser.add_argument("--seq",     type=int,   default=64,
                        help="Lunghezza sequenza (default: 64)")
    parser.add_argument("--lr",      type=float, default=3e-4,
                        help="Learning rate (default: 3e-4)")
    parser.add_argument("--demo",    action="store_true",
                        help="Solo simulazione demo, nessun training")
    parser.add_argument("--fast",    action="store_true",
                        help="Modalità fast (10 epoche, batch piccolo)")
    parser.add_argument("--refresh", action="store_true",
                        help="Forza nuovo download dati")
    parser.add_argument("--fresh",   action="store_true",
                        help="Ignora checkpoint precedente, riparti da zero")
    parser.add_argument("--patience", type=int, default=40,
                        help="Early stopping patience (default: 40 epoche)")
    parser.add_argument("--reason-every", type=int, default=5,
                        help="Mostra reasoning ogni N epoche (default: 5)")
    args = parser.parse_args()

    if args.fast:
        args.epochs = 10
        args.batch  = 64

    # ── Banner
    print()
    print(divider("═", 72, C.YELLOW))
    print(header("GOLIATH — XAU/USD GPU TRAINING LIVE", color=C.YELLOW))
    print(f"{C.YELLOW}{'═'*72}{C.RESET}")
    print(f"  {C.DIM}v2.0 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | "
          f"epoche={args.epochs} | seq={args.seq} | batch={args.batch}{C.RESET}")
    print()

    # ── GPU Detection
    device, has_gpu, gpu_desc = detect_gpu()
    col = C.GREEN if has_gpu else C.YELLOW
    print(f"  {C.BOLD}GPU:{C.RESET} {col}{gpu_desc}{C.RESET}")
    grad_scaler = torch.amp.GradScaler("cuda") if has_gpu else None
    print()

    # ── Dati
    if not HAS_YFINANCE:
        sys.exit(1)

    df = load_or_fetch_data(force_refresh=args.refresh)

    # ── Feature Engineering
    print(f"\n{C.CYAN}[FEATURES]{C.RESET} Calcolo indicatori tecnici...")
    feat_df, feat_names = compute_features(df)
    print(f"  {C.GREEN}✓ {len(feat_names)} features calcolate{C.RESET}: "
          f"{', '.join(feat_names[:6])}... (+{len(feat_names)-6} altre)")

    # ── Labels
    print(f"\n{C.CYAN}[LABELS]{C.RESET} Triple Barrier Labeling (TP=1.5%, SL=0.8%, horizon=20)...")
    labels = create_labels(df, tp_pct=0.015, sl_pct=0.008, horizon=20)

    label_counts = {0: (labels == 0).sum(), 1: (labels == 1).sum(), 2: (labels == 2).sum()}
    total_l = len(labels)
    print(f"  SELL: {C.RED}{label_counts[0]:,}{C.RESET} ({label_counts[0]/total_l*100:.1f}%)  "
          f"HOLD: {C.YELLOW}{label_counts[1]:,}{C.RESET} ({label_counts[1]/total_l*100:.1f}%)  "
          f"BUY: {C.GREEN}{label_counts[2]:,}{C.RESET} ({label_counts[2]/total_l*100:.1f}%)")

    # ── Sequenze
    print(f"\n{C.CYAN}[DATA]{C.RESET} Preparazione sequenze (seq_len={args.seq})...")
    feat_arr = feat_df.values[:len(labels)]

    # Scale
    scaler   = StandardScaler()
    feat_scaled = scaler.fit_transform(feat_arr)
    feat_scaled = np.nan_to_num(feat_scaled, nan=0.0, posinf=0.0, neginf=0.0)

    X, y = build_sequences(feat_scaled, labels, seq_len=args.seq)
    print(f"  {C.GREEN}✓ {len(X):,} sequenze create{C.RESET}  shape: {X.shape}")

    # Split train/val/test (80/10/10)
    n      = len(X)
    n_tr   = int(n * 0.80)
    n_val  = int(n * 0.10)
    X_tr,  y_tr  = X[:n_tr],          y[:n_tr]
    X_val, y_val = X[n_tr:n_tr+n_val], y[n_tr:n_tr+n_val]
    X_te,  y_te  = X[n_tr+n_val:],    y[n_tr+n_val:]

    print(f"  Train: {len(X_tr):,}  Val: {len(X_val):,}  Test: {len(X_te):,}")

    ds_tr  = TensorDataset(torch.FloatTensor(X_tr),  torch.LongTensor(y_tr))
    ds_val = TensorDataset(torch.FloatTensor(X_val), torch.LongTensor(y_val))
    ds_te  = TensorDataset(torch.FloatTensor(X_te),  torch.LongTensor(y_te))

    loader_tr  = DataLoader(ds_tr,  batch_size=args.batch, shuffle=True,
                             num_workers=0, pin_memory=has_gpu)
    loader_val = DataLoader(ds_val, batch_size=args.batch, shuffle=False,
                             num_workers=0, pin_memory=has_gpu)
    loader_te  = DataLoader(ds_te,  batch_size=args.batch, shuffle=False,
                             num_workers=0)

    # ── Modello
    print(f"\n{C.CYAN}[MODEL]{C.RESET} Inizializzazione XAUTransformer...")
    model = XAUTransformer(
        n_features=len(feat_names),
        d_model=96,
        nhead=4,
        num_layers=3,
        dropout=0.35,
        seq_len=args.seq,
    ).to(device)

    params = sum(p.numel() for p in model.parameters())
    print(f"  {C.GREEN}✓ Parametri: {params:,}{C.RESET}  device: {device}")

    # Carica checkpoint se esiste (a meno che --fresh)
    best_ckpt = CHECKPOINT_DIR / "goliath_xau_best.pth"
    if args.fresh:
        print(f"  {C.YELLOW}→ --fresh: modello inizializzato da zero{C.RESET}")
    elif best_ckpt.exists():
        try:
            model.load_state_dict(torch.load(best_ckpt, map_location=device))
            print(f"  {C.GREEN}✓ Checkpoint caricato: {best_ckpt.name}{C.RESET}")
        except Exception as e:
            print(f"  {C.YELLOW}⚠ Checkpoint non compatibile ({e}). Nuovo modello.{C.RESET}")

    criterion = nn.CrossEntropyLoss(label_smoothing=0.10)
    optimizer = optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.05)
    scheduler = optim.lr_scheduler.CosineAnnealingWarmRestarts(
        optimizer, T_0=10, T_mult=2, eta_min=1e-6
    )

    # ── AI Reasoner & Trade Simulator
    reasoner  = AIReasoner(model, scaler, feat_names, device)
    simulator = TradeSimulator()

    # Demo mode: solo simulazione
    if args.demo:
        print(f"\n{C.MAGENTA}[DEMO]{C.RESET} Modalità demo — simulazione trade senza training\n")
        _run_demo_simulation(model, scaler, feat_names, feat_scaled, df,
                             reasoner, simulator, device, args.seq)
        simulator.display_summary()
        return

    # ── Training Loop
    print()
    print(header("INIZIO TRAINING GPU"))
    print(f"  {C.DIM}Epoche: {args.epochs} | "
          f"Reasoning ogni: {args.reason_every} epoche{C.RESET}\n")

    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    best_val_acc  = 0.0
    best_val_loss = float("inf")
    patience_ctr  = 0   # contatore early stopping
    history = []

    for epoch in range(1, args.epochs + 1):
        t0 = time.time()

        # Train
        tr_loss, tr_acc = train_epoch(
            model, loader_tr, optimizer, criterion, device,
            grad_scaler, accumulation=4
        )
        # Validate
        val_loss, val_acc = evaluate(model, loader_val, criterion, device, grad_scaler)
        scheduler.step()
        elapsed = time.time() - t0

        lr_now = optimizer.param_groups[0]["lr"]
        gap    = tr_acc - val_acc
        history.append({"epoch": epoch, "tr_acc": tr_acc, "val_acc": val_acc,
                         "tr_loss": tr_loss, "val_loss": val_loss})

        # Colora accuratezza + mostra gap
        acc_col = (C.GREEN if val_acc > 60 else C.YELLOW if val_acc > 50 else C.RED)
        gap_col = C.GREEN if gap < 15 else (C.YELLOW if gap < 25 else C.RED)
        print(f"  Ep {epoch:3d}/{args.epochs}  "
              f"Train: {C.CYAN}{tr_acc:5.1f}%{C.RESET}  "
              f"Val: {acc_col}{val_acc:5.1f}%{C.RESET}  "
              f"Gap: {gap_col}{gap:4.1f}{C.RESET}  "
              f"Loss: {tr_loss:.4f}/{val_loss:.4f}  "
              f"LR: {lr_now:.2e}  {C.DIM}{elapsed:.1f}s{C.RESET}")

        # Salva miglior modello (basato su val_loss, non solo val_acc)
        improved = False
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            improved = True
        if val_acc > best_val_acc:
            best_val_acc = val_acc
            improved = True

        if improved:
            patience_ctr = 0
            torch.save(model.state_dict(), best_ckpt)
            scaler_path = CHECKPOINT_DIR / "goliath_xau_scaler.json"
            with open(scaler_path, "w") as f:
                json.dump({"mean": scaler.mean_.tolist(),
                           "scale": scaler.scale_.tolist(),
                           "features": feat_names}, f)
            print(f"  {C.GREEN}  ★ Nuovo miglior modello: {val_acc:.2f}%  "
                  f"(val_loss: {val_loss:.4f}){C.RESET}")
        else:
            patience_ctr += 1

        # Early stopping
        if patience_ctr >= args.patience:
            print(f"\n  {C.YELLOW}{C.BOLD}⚡ EARLY STOPPING{C.RESET} "
                  f"dopo {args.patience} epoche senza miglioramento "
                  f"(best val: {best_val_acc:.2f}%)")
            # Ricarica miglior checkpoint
            model.load_state_dict(torch.load(best_ckpt, map_location=device))
            break

        # AI Reasoning + Trade Simulation
        if epoch % args.reason_every == 0 or epoch == args.epochs:
            # Prendi un campione recente dal test set per il reasoning
            recent_idx = max(0, len(feat_scaled) - args.seq - 50)
            seq_raw = feat_scaled[recent_idx:recent_idx + args.seq]
            if len(seq_raw) == args.seq:
                x_seq = seq_raw[np.newaxis, :, :]   # [1, seq_len, n_feat]
                current_price = float(df["close"].iloc[recent_idx + args.seq - 1])
                df_window     = df.iloc[recent_idx:recent_idx + args.seq]

                # Mostra reasoning
                r = reasoner.reason(x_seq, df_window, current_price, epoch)
                reasoner.display(r, feat_names)

                # Simula trade
                _run_trade_simulation(r, simulator, df, recent_idx + args.seq,
                                      feat_scaled, model, scaler, feat_names,
                                      device, args.seq)

    # ── Test finale
    print()
    print(header("VALUTAZIONE FINALE SUL TEST SET"))
    te_loss, te_acc = evaluate(model, loader_te, criterion, device, grad_scaler)
    print(f"  Test Loss    : {te_loss:.4f}")
    print(f"  Test Accuracy: {C.BOLD}{te_acc:.2f}%{C.RESET}")
    print(f"  Best Val Acc : {C.GREEN}{best_val_acc:.2f}%{C.RESET}")
    print(f"  Checkpoint   : {best_ckpt}")
    print()

    # Sommario trade
    simulator.display_summary()

    # ── Salva history
    history_path = CHECKPOINT_DIR / "xau_training_history.json"
    with open(history_path, "w") as f:
        json.dump(history, f, indent=2)
    print(f"\n  {C.DIM}History salvata in: {history_path}{C.RESET}")
    print(divider("═", 72, C.YELLOW))


def _run_trade_simulation(r: Dict, simulator: TradeSimulator,
                          df: pd.DataFrame, start_idx: int,
                          feat_scaled: np.ndarray,
                          model: XAUTransformer, scaler: StandardScaler,
                          feat_names: List[str], device: torch.device,
                          seq_len: int):
    """
    Simula un trade dopo il reasoning su barre reali successive.
    Mostra l'evoluzione con SL/TP live.
    """
    decision   = r["decision"]
    price      = r["price"]
    sl_dist    = r["sl_dist"]
    tp_dist    = r["tp_dist"]

    trade = simulator.open_trade(decision, price, sl_dist, tp_dist,
                                 lot_size=0.10, bar_idx=start_idx)
    if trade is None:
        return

    # Avanza sulle barre successive
    max_bars = min(60, len(df) - start_idx - 1)
    print(f"\n  {C.DIM}Simulazione trade su {max_bars} barre reali...{C.RESET}")

    for i in range(max_bars):
        bar_i = start_idx + i
        if bar_i >= len(df):
            break

        curr_price = float(df["close"].iloc[bar_i])
        curr_high  = float(df["high"].iloc[bar_i])
        curr_low   = float(df["low"].iloc[bar_i])

        simulator.update_trades(curr_price, curr_high, curr_low, bar_i)

        # Trade chiuso
        if not simulator.open_trades or trade not in simulator.open_trades:
            break

        # Breve pausa per effetto live
        time.sleep(0.05)

    # Se ancora aperto dopo max_bars, forza chiusura
    if trade in simulator.open_trades:
        trade.exit_price  = float(df["close"].iloc[min(start_idx + max_bars, len(df)-1)])
        trade.exit_reason = "TIMEOUT (max barre)"
        trade.is_open     = False
        if trade.direction == 2:
            trade.pnl_usd = (trade.exit_price - trade.entry_price) * trade.lot_size * 100
        else:
            trade.pnl_usd = (trade.entry_price - trade.exit_price) * trade.lot_size * 100

        simulator.open_trades.remove(trade)
        simulator.closed_trades.append(trade)
        simulator.total_pnl += trade.pnl_usd
        if trade.pnl_usd > 0:
            simulator.wins += 1
        else:
            simulator.losses += 1
        simulator._display_close(trade)


def _run_demo_simulation(model: XAUTransformer, scaler: StandardScaler,
                         feat_names: List[str], feat_scaled: np.ndarray,
                         df: pd.DataFrame, reasoner: AIReasoner,
                         simulator: TradeSimulator, device: torch.device,
                         seq_len: int):
    """Demo: reasoning + simulazione su 5 punti del dataset."""
    n   = len(feat_scaled)
    pts = np.linspace(seq_len, n - 100, 5, dtype=int)

    for i, idx in enumerate(pts):
        print(f"\n{header(f'DEMO SEGNALE {i+1}/5')}")
        x_seq = feat_scaled[idx - seq_len:idx][np.newaxis, :, :]
        if x_seq.shape[1] != seq_len:
            continue
        price     = float(df["close"].iloc[idx - 1])
        df_window = df.iloc[idx - seq_len:idx]

        r = reasoner.reason(x_seq, df_window, price, epoch=0)
        reasoner.display(r, feat_names)
        _run_trade_simulation(r, simulator, df, idx, feat_scaled,
                              model, scaler, feat_names, device, seq_len)
        time.sleep(0.5)


if __name__ == "__main__":
    # Rimuovi handler loguru default e usa print per output formattato
    logger.remove()
    logger.add(sys.stderr, level="WARNING")
    main()
