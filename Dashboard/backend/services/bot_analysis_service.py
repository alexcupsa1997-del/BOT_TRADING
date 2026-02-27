"""
Bot Analysis Service
====================
Wraps TradingOrchestrator to provide structured analysis results.
Falls back to stub data if the analysis module is unavailable.
"""

import sys
import os
import time
import json
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional
from decimal import Decimal
from loguru import logger

# Try to import orchestrator infrastructure
_ORCHESTRATOR_AVAILABLE = False
try:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
    from analysis.src.quant.indicators import compute_all_indicators
    from analysis.src.quant.patterns import detect_all_patterns
    from analysis.src.quant.signal_processor import (
        extract_indicator_signals, extract_pattern_signals,
        aggregate_signals,
    )
    from analysis.src.quant.market_regime import MarketRegimeClassifier, REGIME_LABELS
    _ORCHESTRATOR_AVAILABLE = True
    logger.info("Bot Analysis: orchestrator modules loaded successfully")
except ImportError as e:
    logger.warning(f"Bot Analysis: orchestrator not available ({e}), using stub mode")

# Try ccxt for market data
try:
    import ccxt
    _CCXT_AVAILABLE = True
except ImportError:
    _CCXT_AVAILABLE = False

# Try yfinance for forex fallback
try:
    import yfinance as yf
    _YFINANCE_AVAILABLE = True
except ImportError:
    _YFINANCE_AVAILABLE = False

try:
    import pandas as pd
    import numpy as np
    _PANDAS_AVAILABLE = True
except ImportError:
    _PANDAS_AVAILABLE = False


class BotAnalysisService:
    """
    Provides structured bot analysis results.
    If analysis modules are available, runs the real pipeline.
    Otherwise, returns intelligent stub data based on live market data.
    """

    def __init__(self):
        self._kraken = None
        self._regime_classifier = None
        self._analysis_log: List[Dict[str, Any]] = []

        # ML model state
        self._model = None
        self._scaler_mean = None
        self._scaler_scale = None
        self._feat_names: Optional[List[str]] = None
        self._model_loaded = False
        self._compute_features_fn = None

        if _ORCHESTRATOR_AVAILABLE:
            self._regime_classifier = MarketRegimeClassifier()

        if _CCXT_AVAILABLE:
            try:
                self._kraken = ccxt.kraken({'enableRateLimit': True})
            except Exception:
                pass

        self._load_ml_model()

    # ─── ML Model Loading ────────────────────────────────────────────────

    def _load_ml_model(self):
        """Load trained XAUTransformer model for real inference."""
        try:
            import torch

            base = Path(__file__).resolve().parents[3]  # BOT_TRADING root
            ckpt_path = base / "analysis" / "models_checkpoint" / "goliath_xau_best.pth"
            scaler_path = base / "analysis" / "models_checkpoint" / "goliath_xau_scaler.json"

            if not ckpt_path.exists() or not scaler_path.exists():
                logger.warning(f"ML model files not found ({ckpt_path.exists()=}, {scaler_path.exists()=})")
                return

            # Load scaler
            with open(scaler_path) as f:
                sc = json.load(f)
            self._scaler_mean = np.array(sc['mean'], dtype=np.float32)
            self._scaler_scale = np.array(sc['scale'], dtype=np.float32)
            self._feat_names = sc['features']

            # Import model class and feature function
            from analysis.train_xau_gpu_live import XAUTransformer, compute_features
            self._compute_features_fn = compute_features

            # Instantiate model with training hyperparameters
            self._model = XAUTransformer(
                n_features=len(self._feat_names),
                d_model=96, nhead=4, num_layers=3, dropout=0.35, seq_len=64,
            )
            state = torch.load(ckpt_path, map_location='cpu', weights_only=True)
            self._model.load_state_dict(state)
            self._model.eval()
            self._model_loaded = True
            logger.success(f"XAUTransformer loaded ({len(self._feat_names)} features, CPU inference)")
        except Exception as e:
            logger.warning(f"ML model not loaded, using indicator stub: {e}")
            self._model_loaded = False

    def _ml_real_inference(self, df, indicators: Dict, verdict: Dict, price: float) -> Dict:
        """Run real XAUTransformer inference on OHLCV data."""
        import torch

        # 1. Compute 33 features from OHLCV
        feat_df, _ = self._compute_features_fn(df)
        feat_arr = feat_df[self._feat_names].values  # [n_bars, 33]

        # 2. Normalize with training scaler
        scaled = (feat_arr - self._scaler_mean) / (self._scaler_scale + 1e-9)
        scaled = np.nan_to_num(scaled, nan=0.0, posinf=0.0, neginf=0.0)

        if len(scaled) < 64:
            logger.warning(f"Not enough bars for ML inference ({len(scaled)} < 64), falling back to stub")
            return self._ml_inference_stub(indicators, verdict)

        # 3. Last 64 bars → [1, 64, 33]
        seq = scaled[-64:]
        x = torch.FloatTensor(seq).unsqueeze(0)

        # 4. Inference
        with torch.no_grad():
            out = self._model(x)

        probs = torch.softmax(out['direction'][0], dim=0).numpy()
        confidence = out['confidence'][0].item()
        sl_dist = out['sl_dist'][0].item()
        tp_dist = out['tp_dist'][0].item()

        action_idx = int(np.argmax(probs))
        action_map = {0: 'SHORT', 1: 'HOLD', 2: 'LONG'}

        # 5. SL/TP from model output, floored by ATR
        atr = indicators.get('atr', {}).get('value', price * 0.01)
        sl_distance = max(sl_dist * price, atr * 1.0)
        tp_distance = max(tp_dist * price, atr * 1.5)

        return {
            'model_type': 'XAUTransformer',
            'model_loaded': True,
            'direction_probabilities': {
                'SELL': round(float(probs[0]), 4),
                'HOLD': round(float(probs[1]), 4),
                'BUY': round(float(probs[2]), 4),
            },
            'predicted_action': action_map[action_idx],
            'confidence': round(float(confidence), 4),
            'tp_multiplier': round(tp_distance / max(sl_distance, 0.01), 2),
            'sl_multiplier': 1.0,
            'sl_distance': round(float(sl_distance), 2),
            'tp_distance': round(float(tp_distance), 2),
            'note': 'Real XAUTransformer inference from trained model',
            'source_tier': 'ML_MODEL',
        }

    # ─── Symbol mapping ─────────────────────────────────────────────────

    # Kraken ccxt symbol for each supported pair
    _KRAKEN_MAP = {
        'EURUSD': 'EUR/USD',   'USDJPY': 'USD/JPY',   'GBPUSD': 'GBP/USD',
        'USDCHF': 'USD/CHF',   'AUDUSD': 'AUD/USD',   'USDCAD': 'USD/CAD',
        'EURJPY': 'EUR/JPY',   'EURGBP': 'EUR/GBP',
        'BTCUSD': 'BTC/USD',   'ETHUSD': 'ETH/USD',
        'XAUUSD': 'XAUT/USD',  # Tether Gold on Kraken
    }

    # Pairs only available via yfinance (not on Kraken)
    _YFINANCE_MAP = {
        'NZDUSD': 'NZDUSD=X',
        'GBPJPY': 'GBPJPY=X',
    }

    _TF_MAP = {
        '1m': '1m', '5m': '5m', '15m': '15m', '1h': '1h', '4h': '4h', '1d': '1d',
    }

    _YF_TF_MAP = {
        '1m': '1m', '5m': '5m', '15m': '15m', '1h': '1h', '4h': '1h', '1d': '1d',
    }

    _YF_PERIOD_MAP = {
        '1m': '1d', '5m': '5d', '15m': '5d', '1h': '30d', '4h': '60d', '1d': '2y',
    }

    # ─── Fetch OHLCV ────────────────────────────────────────────────────

    async def _fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 200) -> Optional[Any]:
        if not _PANDAS_AVAILABLE:
            return None

        # Try Kraken first
        if symbol in self._KRAKEN_MAP and _CCXT_AVAILABLE and self._kraken is not None:
            try:
                ccxt_symbol = self._KRAKEN_MAP[symbol]
                ccxt_tf = self._TF_MAP.get(timeframe, '1h')

                import asyncio
                ohlcv = await asyncio.to_thread(
                    self._kraken.fetch_ohlcv, ccxt_symbol, ccxt_tf, limit=limit
                )

                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                df.set_index('timestamp', inplace=True)
                return df
            except Exception as e:
                logger.warning(f"Kraken fetch failed for {symbol}: {e}")

        # Fallback to yfinance for unsupported pairs or Kraken failures
        if _YFINANCE_AVAILABLE:
            try:
                yf_symbol = self._YFINANCE_MAP.get(symbol)
                if yf_symbol is None:
                    # Build yfinance ticker from symbol (e.g. EURUSD -> EURUSD=X)
                    yf_symbol = f"{symbol}=X"

                yf_tf = self._YF_TF_MAP.get(timeframe, '1h')
                yf_period = self._YF_PERIOD_MAP.get(timeframe, '30d')

                import asyncio
                df = await asyncio.to_thread(
                    lambda: yf.download(yf_symbol, period=yf_period, interval=yf_tf, progress=False)
                )

                if df is not None and len(df) > 0:
                    # yfinance returns MultiIndex columns when single ticker, flatten
                    if isinstance(df.columns, pd.MultiIndex):
                        df.columns = df.columns.get_level_values(0)
                    df.columns = [c.lower() for c in df.columns]
                    if 'volume' not in df.columns:
                        df['volume'] = 0
                    return df
            except Exception as e:
                logger.error(f"yfinance fetch failed for {symbol}: {e}")

        logger.error(f"All data sources failed for {symbol}")
        return None

    # ─── Compute indicators from raw OHLCV ──────────────────────────────

    def _compute_indicators_from_df(self, df) -> Dict[str, Any]:
        """Compute key indicators from a pandas DataFrame."""
        closes = df['close'].values
        highs = df['high'].values
        lows = df['low'].values
        n = len(closes)

        result = {}

        # RSI (14)
        if n >= 15:
            deltas = np.diff(closes)
            gains = np.where(deltas > 0, deltas, 0)
            losses = np.where(deltas < 0, -deltas, 0)
            avg_gain = np.mean(gains[-14:])
            avg_loss = np.mean(losses[-14:])
            if avg_loss == 0:
                rsi = 100.0
            else:
                rs = avg_gain / avg_loss
                rsi = 100 - 100 / (1 + rs)
            result['rsi'] = {'value': round(float(rsi), 2), 'period': 14}

            # RSI zone
            if rsi > 70:
                result['rsi']['zone'] = 'overbought'
            elif rsi < 30:
                result['rsi']['zone'] = 'oversold'
            else:
                result['rsi']['zone'] = 'neutral'

        # EMA 9, 21, 50, 200
        for period in [9, 21, 50, 200]:
            if n >= period:
                k = 2 / (period + 1)
                ema = float(closes[0])
                for j in range(1, n):
                    ema = float(closes[j]) * k + ema * (1 - k)
                result[f'ema_{period}'] = {
                    'value': round(ema, 2),
                    'period': period,
                    'vs_price': 'above' if float(closes[-1]) > ema else 'below',
                }

        # ATR (14)
        if n >= 15:
            trs = []
            for i in range(1, n):
                tr = max(
                    float(highs[i]) - float(lows[i]),
                    abs(float(highs[i]) - float(closes[i-1])),
                    abs(float(lows[i]) - float(closes[i-1])),
                )
                trs.append(tr)
            atr = np.mean(trs[-14:])
            result['atr'] = {'value': round(float(atr), 2), 'period': 14}

        # ADX (14) — simplified
        if n >= 28:
            # Approximate ADX calculation
            plus_dm = []
            minus_dm = []
            for i in range(1, n):
                up = float(highs[i]) - float(highs[i-1])
                down = float(lows[i-1]) - float(lows[i])
                plus_dm.append(up if up > down and up > 0 else 0)
                minus_dm.append(down if down > up and down > 0 else 0)

            # Smoothed averages
            atr_14 = result.get('atr', {}).get('value', 1.0)
            if atr_14 > 0:
                plus_di = 100 * np.mean(plus_dm[-14:]) / atr_14
                minus_di = 100 * np.mean(minus_dm[-14:]) / atr_14
                dx = abs(plus_di - minus_di) / max(plus_di + minus_di, 0.01) * 100
                result['adx'] = {
                    'value': round(float(dx), 2),
                    'period': 14,
                    'trend_strength': 'strong' if dx > 25 else 'weak',
                }

        # MACD (12, 26, 9)
        if n >= 26:
            k12 = 2 / 13
            k26 = 2 / 27
            ema12 = float(closes[0])
            ema26 = float(closes[0])
            for j in range(1, n):
                ema12 = float(closes[j]) * k12 + ema12 * (1 - k12)
                ema26 = float(closes[j]) * k26 + ema26 * (1 - k26)
            macd_line = ema12 - ema26

            # Signal line (simplified)
            result['macd'] = {
                'value': round(float(macd_line), 4),
                'signal': 'bullish' if macd_line > 0 else 'bearish',
            }

        # Bollinger Band position
        if n >= 20:
            sma20 = np.mean(closes[-20:])
            std20 = np.std(closes[-20:])
            upper = sma20 + 2 * std20
            lower = sma20 - 2 * std20
            price = float(closes[-1])
            bb_pct = (price - lower) / max(upper - lower, 0.01)
            result['bollinger'] = {
                'upper': round(float(upper), 2),
                'middle': round(float(sma20), 2),
                'lower': round(float(lower), 2),
                'pct_b': round(float(bb_pct), 4),
                'zone': 'upper' if bb_pct > 0.8 else ('lower' if bb_pct < 0.2 else 'middle'),
            }

        # CCI (20)
        if n >= 20:
            tp = (closes[-20:] + highs[-20:] + lows[-20:]) / 3
            tp_mean = np.mean(tp)
            tp_mad = np.mean(np.abs(tp - tp_mean))
            cci = (tp[-1] - tp_mean) / max(0.015 * tp_mad, 0.01)
            result['cci'] = {'value': round(float(cci), 2), 'period': 20}

        return result

    # ─── Generate signals from indicators ───────────────────────────────

    def _generate_signals(self, indicators: Dict, price: float) -> List[Dict]:
        """Generate signal list from indicator values."""
        signals = []

        # RSI signals
        rsi = indicators.get('rsi', {})
        if rsi:
            rsi_val = rsi.get('value', 50)
            if rsi_val > 70:
                signals.append({
                    'source': 'RSI', 'direction': 'BEARISH',
                    'strength': min((rsi_val - 70) / 30, 1.0),
                    'detail': f'RSI overbought at {rsi_val}',
                })
            elif rsi_val < 30:
                signals.append({
                    'source': 'RSI', 'direction': 'BULLISH',
                    'strength': min((30 - rsi_val) / 30, 1.0),
                    'detail': f'RSI oversold at {rsi_val}',
                })
            else:
                signals.append({
                    'source': 'RSI', 'direction': 'NEUTRAL',
                    'strength': 0.1,
                    'detail': f'RSI neutral at {rsi_val}',
                })

        # EMA cross signals
        ema9 = indicators.get('ema_9', {}).get('value')
        ema21 = indicators.get('ema_21', {}).get('value')
        if ema9 and ema21:
            if ema9 > ema21:
                signals.append({
                    'source': 'EMA Cross', 'direction': 'BULLISH',
                    'strength': min(abs(ema9 - ema21) / (price * 0.001), 1.0),
                    'detail': f'EMA 9 ({ema9:.2f}) > EMA 21 ({ema21:.2f})',
                })
            else:
                signals.append({
                    'source': 'EMA Cross', 'direction': 'BEARISH',
                    'strength': min(abs(ema9 - ema21) / (price * 0.001), 1.0),
                    'detail': f'EMA 9 ({ema9:.2f}) < EMA 21 ({ema21:.2f})',
                })

        # EMA 50 trend
        ema50 = indicators.get('ema_50', {}).get('value')
        if ema50:
            if price > ema50:
                signals.append({
                    'source': 'EMA 50 Trend', 'direction': 'BULLISH',
                    'strength': 0.6,
                    'detail': f'Price above EMA 50 ({ema50:.2f})',
                })
            else:
                signals.append({
                    'source': 'EMA 50 Trend', 'direction': 'BEARISH',
                    'strength': 0.6,
                    'detail': f'Price below EMA 50 ({ema50:.2f})',
                })

        # Bollinger signals
        bb = indicators.get('bollinger', {})
        if bb:
            pct_b = bb.get('pct_b', 0.5)
            if pct_b > 0.95:
                signals.append({
                    'source': 'Bollinger Bands', 'direction': 'BEARISH',
                    'strength': 0.7,
                    'detail': f'Price at upper band (%B = {pct_b:.2f})',
                })
            elif pct_b < 0.05:
                signals.append({
                    'source': 'Bollinger Bands', 'direction': 'BULLISH',
                    'strength': 0.7,
                    'detail': f'Price at lower band (%B = {pct_b:.2f})',
                })

        # MACD
        macd = indicators.get('macd', {})
        if macd:
            macd_val = macd.get('value', 0)
            signals.append({
                'source': 'MACD', 'direction': 'BULLISH' if macd_val > 0 else 'BEARISH',
                'strength': min(abs(macd_val) / (price * 0.001), 1.0),
                'detail': f'MACD line at {macd_val:.4f}',
            })

        # ADX trend strength
        adx = indicators.get('adx', {})
        if adx:
            adx_val = adx.get('value', 0)
            signals.append({
                'source': 'ADX', 'direction': 'NEUTRAL',
                'strength': min(adx_val / 50, 1.0),
                'detail': f'ADX = {adx_val:.1f} ({"strong" if adx_val > 25 else "weak"} trend)',
            })

        return signals

    # ─── Determine market regime ────────────────────────────────────────

    def _detect_regime(self, indicators: Dict) -> Dict:
        """Determine market regime from indicators."""
        adx = indicators.get('adx', {}).get('value', 20)
        atr = indicators.get('atr', {}).get('value', 0)
        bb = indicators.get('bollinger', {})
        bb_width = 0
        if bb:
            upper = bb.get('upper', 0)
            lower = bb.get('lower', 0)
            middle = bb.get('middle', 1)
            if middle > 0:
                bb_width = (upper - lower) / middle

        if adx > 30:
            ema9 = indicators.get('ema_9', {}).get('value', 0)
            ema21 = indicators.get('ema_21', {}).get('value', 0)
            if ema9 > ema21:
                return {
                    'regime': 'TRENDING_UP', 'label': 'Trending ↑',
                    'description': 'Strong uptrend detected',
                    'confidence': min(adx / 50, 1.0),
                    'strategy': 'Trend Following',
                }
            else:
                return {
                    'regime': 'TRENDING_DOWN', 'label': 'Trending ↓',
                    'description': 'Strong downtrend detected',
                    'confidence': min(adx / 50, 1.0),
                    'strategy': 'Trend Following',
                }
        elif bb_width > 0.04:
            return {
                'regime': 'VOLATILE', 'label': 'Volatile ⚡',
                'description': 'High volatility — wide Bollinger Bands',
                'confidence': min(bb_width / 0.08, 1.0),
                'strategy': 'Volatility Breakout',
            }
        else:
            return {
                'regime': 'RANGING', 'label': 'Ranging ↔',
                'description': 'Low trend strength — sideways market',
                'confidence': 1.0 - min(adx / 30, 0.9),
                'strategy': 'Mean Reversion',
            }

    # ─── Generate final verdict ─────────────────────────────────────────

    def _generate_verdict(
        self, signals: List[Dict], indicators: Dict,
        regime: Dict, price: float, atr: float,
    ) -> Dict:
        """Generate final trade verdict from signals and analysis."""
        bullish_weight = 0.0
        bearish_weight = 0.0
        total_strength = 0.0

        for s in signals:
            w = s['strength']
            total_strength += w
            if s['direction'] == 'BULLISH':
                bullish_weight += w
            elif s['direction'] == 'BEARISH':
                bearish_weight += w

        # Compute net direction and confidence
        net = bullish_weight - bearish_weight
        confidence = abs(net) / max(total_strength, 0.01)
        confidence = min(confidence, 1.0)

        # Threshold for action
        if confidence < 0.3 or abs(net) < 0.5:
            action = 'HOLD'
            reasoning = f'Conflicting signals (bull={bullish_weight:.2f}, bear={bearish_weight:.2f}). Confidence too low.'
        elif net > 0:
            action = 'LONG'
            reasoning = f'Net bullish bias ({bullish_weight:.2f} vs {bearish_weight:.2f}). {regime.get("description", "")}'
        else:
            action = 'SHORT'
            reasoning = f'Net bearish bias ({bearish_weight:.2f} vs {bullish_weight:.2f}). {regime.get("description", "")}'

        # SL/TP based on ATR
        sl_distance = atr * 1.5
        tp_distance = atr * 3.0

        if action == 'LONG':
            entry = price
            sl = price - sl_distance
            tp = price + tp_distance
        elif action == 'SHORT':
            entry = price
            sl = price + sl_distance
            tp = price - tp_distance
        else:
            entry = price
            sl = None
            tp = None

        return {
            'action': action,
            'confidence': round(confidence, 4),
            'entry_price': round(entry, 2),
            'stop_loss': round(sl, 2) if sl else None,
            'take_profit': round(tp, 2) if tp else None,
            'risk_reward': round(tp_distance / max(sl_distance, 0.01), 2) if sl else None,
            'position_size_pct': round(min(confidence * 0.1, 0.05), 4),
            'reasoning': reasoning,
            'bullish_weight': round(bullish_weight, 3),
            'bearish_weight': round(bearish_weight, 3),
            'source_tier': 'QUANTITATIVE' if _ORCHESTRATOR_AVAILABLE else 'INDICATOR_BASED',
        }

    # ─── Confidence gates ───────────────────────────────────────────────

    def _evaluate_gates(self, indicators: Dict, signals: List[Dict]) -> Dict:
        """Evaluate confidence gates."""
        # Maturity: do we have enough data?
        indicator_count = len(indicators)
        maturity_ok = indicator_count >= 5

        # Drift: are indicators in unusual ranges?
        rsi = indicators.get('rsi', {}).get('value', 50)
        cci = indicators.get('cci', {}).get('value', 0)
        drift_detected = abs(rsi - 50) > 35 or abs(cci) > 200

        # Silence: conflicting signals?
        bull = sum(1 for s in signals if s['direction'] == 'BULLISH')
        bear = sum(1 for s in signals if s['direction'] == 'BEARISH')
        silence_triggered = bull > 0 and bear > 0 and abs(bull - bear) <= 1

        return {
            'maturity': {
                'passed': maturity_ok,
                'detail': f'{indicator_count} indicators computed',
                'required': 5,
            },
            'drift': {
                'passed': not drift_detected,
                'detail': f'RSI={rsi:.1f} CCI={cci:.1f}',
                'alert': 'Extreme readings detected' if drift_detected else 'Normal range',
            },
            'silence': {
                'passed': not silence_triggered,
                'detail': f'{bull} bullish vs {bear} bearish signals',
                'alert': 'Mixed signals — caution advised' if silence_triggered else 'Clear direction',
            },
        }

    # ─── ML Inference stub ──────────────────────────────────────────────

    def _ml_inference_stub(self, indicators: Dict, verdict: Dict) -> Dict:
        """Generate ML inference results (real model output when available)."""
        action = verdict['action']
        conf = verdict['confidence']

        if action == 'LONG':
            logits = [0.1, 0.15, 0.75]
        elif action == 'SHORT':
            logits = [0.75, 0.15, 0.1]
        else:
            logits = [0.25, 0.5, 0.25]

        # Scale logits by actual confidence
        total = sum(logits)
        logits = [round(l / total, 4) for l in logits]

        return {
            'model_type': 'GoliathTransformerV2',
            'model_loaded': False,
            'direction_probabilities': {
                'SELL': logits[0],
                'HOLD': logits[1],
                'BUY': logits[2],
            },
            'predicted_action': action,
            'confidence': round(conf, 4),
            'tp_multiplier': 2.0,
            'sl_multiplier': 1.0,
            'note': 'Inference derived from indicator analysis (model not loaded for live inference)',
        }

    # ═══ PUBLIC API ═══════════════════════════════════════════════════════

    async def run_analysis(self, symbol: str, timeframe: str = '1h') -> Dict[str, Any]:
        """Run the full analysis pipeline and return structured results."""
        start_time = time.time()

        # Step 1: Fetch data
        df = await self._fetch_ohlcv(symbol, timeframe, limit=200)
        if df is None or len(df) < 30:
            return {
                'status': 'error',
                'error': f'Insufficient data for {symbol} ({0 if df is None else len(df)} bars)',
                'symbol': symbol,
                'timeframe': timeframe,
            }

        price = float(df['close'].iloc[-1])
        timestamp = str(df.index[-1])

        # Step 2: Compute indicators
        indicators = self._compute_indicators_from_df(df)

        # Step 3: Generate signals
        signals = self._generate_signals(indicators, price)

        # Step 4: Detect regime
        regime = self._detect_regime(indicators)

        # Step 5: Evaluate confidence gates
        gates = self._evaluate_gates(indicators, signals)

        # Step 6: Generate verdict
        atr = indicators.get('atr', {}).get('value', price * 0.01)
        verdict = self._generate_verdict(signals, indicators, regime, price, atr)

        # Step 7: ML inference (real model for XAU/USD, stub for others)
        is_gold = symbol.upper() in ('XAUUSD', 'XAU', 'GOLD')
        if self._model_loaded and is_gold:
            try:
                ml_output = self._ml_real_inference(df, indicators, verdict, price)
                # Override verdict with ML model prediction
                ml_action = ml_output['predicted_action']
                ml_conf = ml_output['confidence']
                ml_sl = ml_output['sl_distance']
                ml_tp = ml_output['tp_distance']
                if ml_action == 'LONG':
                    verdict['stop_loss'] = round(price - ml_sl, 2)
                    verdict['take_profit'] = round(price + ml_tp, 2)
                elif ml_action == 'SHORT':
                    verdict['stop_loss'] = round(price + ml_sl, 2)
                    verdict['take_profit'] = round(price - ml_tp, 2)
                else:
                    verdict['stop_loss'] = None
                    verdict['take_profit'] = None
                verdict['action'] = ml_action
                verdict['confidence'] = round(ml_conf, 4)
                verdict['entry_price'] = round(price, 2)
                verdict['risk_reward'] = round(ml_tp / max(ml_sl, 0.01), 2)
                verdict['source_tier'] = 'ML_MODEL'
                verdict['reasoning'] = (
                    f'ML model prediction: {ml_action} '
                    f'(SELL={ml_output["direction_probabilities"]["SELL"]:.1%}, '
                    f'HOLD={ml_output["direction_probabilities"]["HOLD"]:.1%}, '
                    f'BUY={ml_output["direction_probabilities"]["BUY"]:.1%})'
                )
            except Exception as e:
                logger.error(f"ML real inference failed, falling back to stub: {e}")
                ml_output = self._ml_inference_stub(indicators, verdict)
        else:
            ml_output = self._ml_inference_stub(indicators, verdict)

        elapsed = round(time.time() - start_time, 3)

        result = {
            'status': 'ok',
            'symbol': symbol,
            'timeframe': timeframe,
            'timestamp': timestamp,
            'current_price': price,
            'elapsed_ms': int(elapsed * 1000),
            'verdict': verdict,
            'indicators': indicators,
            'signals': signals,
            'regime': regime,
            'ml_inference': ml_output,
            'confidence_gates': gates,
            'pipeline_steps': [
                {'step': 1, 'name': 'Data Fetch', 'status': 'ok', 'detail': f'{len(df)} bars loaded'},
                {'step': 2, 'name': 'Indicators', 'status': 'ok', 'detail': f'{len(indicators)} computed'},
                {'step': 3, 'name': 'Signals', 'status': 'ok', 'detail': f'{len(signals)} signals'},
                {'step': 4, 'name': 'Market Regime', 'status': 'ok', 'detail': regime['label']},
                {'step': 5, 'name': 'Confidence Gates', 'status': 'ok' if all(g['passed'] for g in gates.values()) else 'warn', 'detail': f'{sum(1 for g in gates.values() if g["passed"])}/3 passed'},
                {'step': 6, 'name': 'ML Inference', 'status': 'stub' if not ml_output.get('model_loaded') else 'ok', 'detail': ml_output['model_type']},
                {'step': 7, 'name': 'Verdict', 'status': 'ok', 'detail': f'{verdict["action"]} @ {verdict["confidence"]:.0%}'},
            ],
        }

        # Log this analysis
        self._analysis_log.insert(0, {
            'timestamp': timestamp,
            'symbol': symbol,
            'timeframe': timeframe,
            'action': verdict['action'],
            'confidence': verdict['confidence'],
            'elapsed_ms': int(elapsed * 1000),
        })
        # Keep only last 50
        self._analysis_log = self._analysis_log[:50]

        return result

    async def get_indicators(self, symbol: str, timeframe: str = '1h') -> Dict:
        """Return only indicator values."""
        df = await self._fetch_ohlcv(symbol, timeframe, limit=200)
        if df is None or len(df) < 30:
            return {'status': 'error', 'error': 'Insufficient data'}
        return {'status': 'ok', 'data': self._compute_indicators_from_df(df)}

    async def get_signals(self, symbol: str, timeframe: str = '1h') -> Dict:
        """Return signal breakdown only."""
        df = await self._fetch_ohlcv(symbol, timeframe, limit=200)
        if df is None or len(df) < 30:
            return {'status': 'error', 'error': 'Insufficient data'}
        indicators = self._compute_indicators_from_df(df)
        price = float(df['close'].iloc[-1])
        return {'status': 'ok', 'data': self._generate_signals(indicators, price)}

    async def get_regime(self, symbol: str, timeframe: str = '1h') -> Dict:
        """Return current market regime."""
        df = await self._fetch_ohlcv(symbol, timeframe, limit=200)
        if df is None or len(df) < 30:
            return {'status': 'error', 'error': 'Insufficient data'}
        indicators = self._compute_indicators_from_df(df)
        return {'status': 'ok', 'data': self._detect_regime(indicators)}

    def get_status(self) -> Dict:
        """Return bot operational status."""
        return {
            'orchestrator_available': _ORCHESTRATOR_AVAILABLE,
            'ccxt_available': _CCXT_AVAILABLE,
            'model_loaded': self._model_loaded,
            'model_type': 'XAUTransformer' if self._model_loaded else 'GoliathTransformerV2 (stub)',
            'ml_supported_symbols': ['XAUUSD'] if self._model_loaded else [],
            'analysis_count': len(self._analysis_log),
            'recent_analyses': self._analysis_log[:10],
        }

    def get_log(self) -> List[Dict]:
        """Return analysis log."""
        return self._analysis_log


# Singleton
bot_analysis_service = BotAnalysisService()
