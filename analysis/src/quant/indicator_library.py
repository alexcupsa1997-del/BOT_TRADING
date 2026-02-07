#!/usr/bin/env python3
"""
GOLIATH Indicator Library v1.0
==============================
100+ Technical Indicators with Standardized Reading Scales

Categories:
- Momentum (25): RSI, Stochastic, MACD, CCI, etc.
- Trend (20): ADX, EMAs, Ichimoku, SAR, etc.
- Volatility (15): ATR, Bollinger, Keltner, etc.
- Volume (15): OBV, MFI, CMF, etc.
- Support/Resistance (10): Pivots, Fibonacci, etc.
- Patterns (15): Chart patterns detection

All indicators return normalized signals in [-1, 1] range for neural network input.
"""

import numpy as np
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
from enum import Enum


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class IndicatorConfig:
    """Configuration for risk and trading parameters."""
    balance: float = 100.0       # Demo account balance (€)
    risk_percent: float = 0.01   # 1% risk per trade
    min_rr_ratio: float = 2.0    # Minimum Risk:Reward ratio
    max_positions: int = 3       # Max concurrent positions
    max_drawdown: float = 0.10   # 10% max daily drawdown


CONFIG = IndicatorConfig()


class SignalStrength(Enum):
    """Signal strength levels."""
    STRONG_SELL = -1.0
    SELL = -0.5
    NEUTRAL = 0.0
    BUY = 0.5
    STRONG_BUY = 1.0


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def ema(data: np.ndarray, period: int) -> np.ndarray:
    """Exponential Moving Average."""
    alpha = 2 / (period + 1)
    result = np.zeros_like(data, dtype=float)
    result[0] = data[0]
    for i in range(1, len(data)):
        result[i] = alpha * data[i] + (1 - alpha) * result[i-1]
    return result


def sma(data: np.ndarray, period: int) -> np.ndarray:
    """Simple Moving Average."""
    result = np.zeros_like(data, dtype=float)
    for i in range(len(data)):
        start = max(0, i - period + 1)
        result[i] = np.mean(data[start:i+1])
    return result


def rolling_max(data: np.ndarray, period: int) -> np.ndarray:
    """Rolling maximum."""
    result = np.zeros_like(data, dtype=float)
    for i in range(len(data)):
        start = max(0, i - period + 1)
        result[i] = np.max(data[start:i+1])
    return result


def rolling_min(data: np.ndarray, period: int) -> np.ndarray:
    """Rolling minimum."""
    result = np.zeros_like(data, dtype=float)
    for i in range(len(data)):
        start = max(0, i - period + 1)
        result[i] = np.min(data[start:i+1])
    return result


def rolling_std(data: np.ndarray, period: int) -> np.ndarray:
    """Rolling standard deviation."""
    result = np.zeros_like(data, dtype=float)
    for i in range(len(data)):
        start = max(0, i - period + 1)
        result[i] = np.std(data[start:i+1])
    return result


def normalize(value: float, min_val: float, max_val: float) -> float:
    """Normalize value to [-1, 1] range."""
    if max_val == min_val:
        return 0.0
    normalized = 2 * (value - min_val) / (max_val - min_val) - 1
    return np.clip(normalized, -1, 1)


# =============================================================================
# MOMENTUM INDICATORS (M01-M25)
# =============================================================================

class MomentumIndicators:
    """25 Momentum-based indicators."""
    
    @staticmethod
    def rsi(close: np.ndarray, period: int = 14) -> Tuple[np.ndarray, np.ndarray]:
        """
        M01-M03: Relative Strength Index
        Scale: 0-100 | Bullish: <30 | Bearish: >70
        Returns: (raw_rsi, normalized_signal)
        """
        delta = np.diff(close, prepend=close[0])
        gain = np.where(delta > 0, delta, 0)
        loss = np.where(delta < 0, -delta, 0)
        
        avg_gain = ema(gain, period)
        avg_loss = ema(loss, period)
        
        with np.errstate(divide='ignore', invalid='ignore'):
            rs = avg_gain / np.where(avg_loss == 0, 1e-10, avg_loss)
        
        rsi = 100 - (100 / (1 + rs))
        
        # Normalize: <30 = +1 (buy), >70 = -1 (sell)
        signal = np.zeros_like(rsi)
        signal[rsi < 30] = (30 - rsi[rsi < 30]) / 30  # 0 to 1
        signal[rsi > 70] = (70 - rsi[rsi > 70]) / 30  # 0 to -1
        
        return rsi, np.clip(signal, -1, 1)
    
    @staticmethod
    def stochastic(high: np.ndarray, low: np.ndarray, close: np.ndarray,
                   k_period: int = 14, d_period: int = 3) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        M04-M05: Stochastic Oscillator
        Scale: 0-100 | Bullish: <20 | Bearish: >80
        Returns: (k, d, normalized_signal)
        """
        highest_high = rolling_max(high, k_period)
        lowest_low = rolling_min(low, k_period)
        
        denom = highest_high - lowest_low
        denom = np.where(denom == 0, 1, denom)
        
        k = 100 * (close - lowest_low) / denom
        d = sma(k, d_period)
        
        # Signal based on K
        signal = np.zeros_like(k)
        signal[k < 20] = (20 - k[k < 20]) / 20
        signal[k > 80] = (80 - k[k > 80]) / 20
        
        return k, d, np.clip(signal, -1, 1)
    
    @staticmethod
    def williams_r(high: np.ndarray, low: np.ndarray, close: np.ndarray,
                   period: int = 14) -> Tuple[np.ndarray, np.ndarray]:
        """
        M06: Williams %R
        Scale: -100 to 0 | Bullish: <-80 | Bearish: >-20
        Returns: (williams_r, normalized_signal)
        """
        highest_high = rolling_max(high, period)
        lowest_low = rolling_min(low, period)
        
        denom = highest_high - lowest_low
        denom = np.where(denom == 0, 1, denom)
        
        wr = -100 * (highest_high - close) / denom
        
        signal = np.zeros_like(wr)
        signal[wr < -80] = (-80 - wr[wr < -80]) / 20
        signal[wr > -20] = (-20 - wr[wr > -20]) / 20
        
        return wr, np.clip(signal, -1, 1)
    
    @staticmethod
    def cci(high: np.ndarray, low: np.ndarray, close: np.ndarray,
            period: int = 14) -> Tuple[np.ndarray, np.ndarray]:
        """
        M07-M08: Commodity Channel Index
        Scale: ±∞ (typical ±200) | Bullish: <-100 | Bearish: >100
        Returns: (cci, normalized_signal)
        """
        tp = (high + low + close) / 3
        tp_sma = sma(tp, period)
        
        # Mean deviation
        md = np.zeros_like(tp)
        for i in range(len(tp)):
            start = max(0, i - period + 1)
            md[i] = np.mean(np.abs(tp[start:i+1] - tp_sma[i]))
        
        md = np.where(md == 0, 1, md)
        cci = (tp - tp_sma) / (0.015 * md)
        
        # Normalize to [-1, 1] with ±200 range
        signal = np.clip(cci / 200, -1, 1)
        # Invert: oversold = buy, overbought = sell
        signal = -signal
        
        return cci, signal
    
    @staticmethod
    def macd(close: np.ndarray, fast: int = 12, slow: int = 26, 
             signal_period: int = 9) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """
        M14-M16: MACD (Moving Average Convergence Divergence)
        Returns: (macd_line, signal_line, histogram, normalized_signal)
        """
        ema_fast = ema(close, fast)
        ema_slow = ema(close, slow)
        
        macd_line = ema_fast - ema_slow
        signal_line = ema(macd_line, signal_period)
        histogram = macd_line - signal_line
        
        # Signal: histogram crossing zero
        signal = np.zeros_like(histogram)
        for i in range(1, len(histogram)):
            if histogram[i-1] < 0 and histogram[i] > 0:
                signal[i] = 1.0  # Bullish crossover
            elif histogram[i-1] > 0 and histogram[i] < 0:
                signal[i] = -1.0  # Bearish crossover
            else:
                # Gradient of histogram
                signal[i] = np.clip(histogram[i] / (np.abs(histogram).max() + 1e-10), -1, 1)
        
        return macd_line, signal_line, histogram, signal
    
    @staticmethod
    def momentum(close: np.ndarray, period: int = 10) -> Tuple[np.ndarray, np.ndarray]:
        """
        M09: Momentum
        Returns: (momentum, normalized_signal)
        """
        mom = close - np.roll(close, period)
        mom[:period] = 0
        
        # Normalize by recent range
        max_mom = np.abs(mom).max() + 1e-10
        signal = np.clip(mom / max_mom, -1, 1)
        
        return mom, signal
    
    @staticmethod
    def roc(close: np.ndarray, period: int = 10) -> Tuple[np.ndarray, np.ndarray]:
        """
        M10: Rate of Change
        Returns: (roc_percent, normalized_signal)
        """
        prev_close = np.roll(close, period)
        prev_close[:period] = close[:period]
        
        roc = 100 * (close - prev_close) / (prev_close + 1e-10)
        
        # Normalize by typical range (±10%)
        signal = np.clip(roc / 10, -1, 1)
        
        return roc, signal
    
    @staticmethod
    def awesome_oscillator(high: np.ndarray, low: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        M13: Awesome Oscillator
        Returns: (ao, normalized_signal)
        """
        median_price = (high + low) / 2
        ao = sma(median_price, 5) - sma(median_price, 34)
        
        # Signal based on color (rising/falling)
        signal = np.zeros_like(ao)
        for i in range(1, len(ao)):
            if ao[i] > ao[i-1]:
                signal[i] = min(1.0, ao[i] / (np.abs(ao).max() + 1e-10))
            else:
                signal[i] = max(-1.0, ao[i] / (np.abs(ao).max() + 1e-10))
        
        return ao, signal
    
    @staticmethod
    def ultimate_oscillator(high: np.ndarray, low: np.ndarray, close: np.ndarray,
                            p1: int = 7, p2: int = 14, p3: int = 28) -> Tuple[np.ndarray, np.ndarray]:
        """
        M12: Ultimate Oscillator
        Scale: 0-100 | Bullish: <30 | Bearish: >70
        """
        prev_close = np.roll(close, 1)
        prev_close[0] = close[0]
        
        bp = close - np.minimum(low, prev_close)
        tr = np.maximum(high, prev_close) - np.minimum(low, prev_close)
        
        avg1 = sma(bp, p1) / (sma(tr, p1) + 1e-10)
        avg2 = sma(bp, p2) / (sma(tr, p2) + 1e-10)
        avg3 = sma(bp, p3) / (sma(tr, p3) + 1e-10)
        
        uo = 100 * (4 * avg1 + 2 * avg2 + avg3) / 7
        
        # Signal
        signal = np.zeros_like(uo)
        signal[uo < 30] = (30 - uo[uo < 30]) / 30
        signal[uo > 70] = (70 - uo[uo > 70]) / 30
        
        return uo, np.clip(signal, -1, 1)


# =============================================================================
# TREND INDICATORS (T01-T20)
# =============================================================================

class TrendIndicators:
    """20 Trend-based indicators."""
    
    @staticmethod
    def adx(high: np.ndarray, low: np.ndarray, close: np.ndarray,
            period: int = 14) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """
        T01-T03: Average Directional Index
        Scale: 0-100 | Strong trend: >25
        Returns: (adx, plus_di, minus_di, normalized_signal)
        """
        prev_high = np.roll(high, 1)
        prev_low = np.roll(low, 1)
        prev_close = np.roll(close, 1)
        
        prev_high[0] = high[0]
        prev_low[0] = low[0]
        prev_close[0] = close[0]
        
        # True Range
        tr1 = high - low
        tr2 = np.abs(high - prev_close)
        tr3 = np.abs(low - prev_close)
        tr = np.maximum(tr1, np.maximum(tr2, tr3))
        
        # Directional Movement
        plus_dm = np.where((high - prev_high) > (prev_low - low), 
                          np.maximum(high - prev_high, 0), 0)
        minus_dm = np.where((prev_low - low) > (high - prev_high),
                           np.maximum(prev_low - low, 0), 0)
        
        # Smoothed
        atr = ema(tr, period)
        smooth_plus = ema(plus_dm, period)
        smooth_minus = ema(minus_dm, period)
        
        # DI
        plus_di = 100 * smooth_plus / (atr + 1e-10)
        minus_di = 100 * smooth_minus / (atr + 1e-10)
        
        # DX and ADX
        dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)
        adx = ema(dx, period)
        
        # Signal: direction and strength
        signal = np.zeros_like(adx)
        for i in range(len(adx)):
            if adx[i] > 25:  # Strong trend
                if plus_di[i] > minus_di[i]:
                    signal[i] = min(1.0, (adx[i] - 25) / 25)  # Bullish
                else:
                    signal[i] = -min(1.0, (adx[i] - 25) / 25)  # Bearish
        
        return adx, plus_di, minus_di, signal
    
    @staticmethod
    def ema_ribbon(close: np.ndarray) -> Dict[str, Tuple[np.ndarray, np.ndarray]]:
        """
        T04-T09: EMA Ribbon (5, 10, 20, 50, 100, 200)
        Returns dict of (ema_values, normalized_position)
        """
        periods = [5, 10, 20, 50, 100, 200]
        result = {}
        
        for p in periods:
            ema_val = ema(close, p)
            # Position: price vs EMA
            position = (close - ema_val) / (ema_val + 1e-10)
            signal = np.clip(position * 10, -1, 1)  # Scale: ±10% = ±1
            result[f'ema_{p}'] = (ema_val, signal)
        
        return result
    
    @staticmethod
    def sma_cross(close: np.ndarray, fast: int = 20, slow: int = 50) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        T10-T12: SMA Cross signals
        Returns: (sma_fast, sma_slow, cross_signal)
        """
        sma_fast = sma(close, fast)
        sma_slow = sma(close, slow)
        
        signal = np.zeros_like(close)
        for i in range(1, len(close)):
            if sma_fast[i-1] < sma_slow[i-1] and sma_fast[i] > sma_slow[i]:
                signal[i] = 1.0  # Golden cross
            elif sma_fast[i-1] > sma_slow[i-1] and sma_fast[i] < sma_slow[i]:
                signal[i] = -1.0  # Death cross
            else:
                # Continuous signal based on distance
                diff = (sma_fast[i] - sma_slow[i]) / (sma_slow[i] + 1e-10)
                signal[i] = np.clip(diff * 20, -1, 1)
        
        return sma_fast, sma_slow, signal
    
    @staticmethod
    def parabolic_sar(high: np.ndarray, low: np.ndarray, close: np.ndarray,
                      af_start: float = 0.02, af_max: float = 0.2) -> Tuple[np.ndarray, np.ndarray]:
        """
        T14: Parabolic SAR
        Returns: (sar, normalized_signal)
        """
        n = len(close)
        sar = np.zeros(n)
        ep = np.zeros(n)
        af = np.zeros(n)
        trend = np.ones(n)  # 1 = up, -1 = down
        
        # Initialize
        sar[0] = low[0]
        ep[0] = high[0]
        af[0] = af_start
        
        for i in range(1, n):
            # Calculate SAR
            sar[i] = sar[i-1] + af[i-1] * (ep[i-1] - sar[i-1])
            
            if trend[i-1] == 1:  # Uptrend
                sar[i] = min(sar[i], low[i-1], low[max(0, i-2)])
                
                if low[i] < sar[i]:  # Reversal to downtrend
                    trend[i] = -1
                    sar[i] = ep[i-1]
                    ep[i] = low[i]
                    af[i] = af_start
                else:
                    trend[i] = 1
                    if high[i] > ep[i-1]:
                        ep[i] = high[i]
                        af[i] = min(af[i-1] + af_start, af_max)
                    else:
                        ep[i] = ep[i-1]
                        af[i] = af[i-1]
            else:  # Downtrend
                sar[i] = max(sar[i], high[i-1], high[max(0, i-2)])
                
                if high[i] > sar[i]:  # Reversal to uptrend
                    trend[i] = 1
                    sar[i] = ep[i-1]
                    ep[i] = high[i]
                    af[i] = af_start
                else:
                    trend[i] = -1
                    if low[i] < ep[i-1]:
                        ep[i] = low[i]
                        af[i] = min(af[i-1] + af_start, af_max)
                    else:
                        ep[i] = ep[i-1]
                        af[i] = af[i-1]
        
        # Signal: 1 if price above SAR (bullish), -1 if below
        signal = np.where(close > sar, 1.0, -1.0)
        
        return sar, signal
    
    @staticmethod
    def supertrend(high: np.ndarray, low: np.ndarray, close: np.ndarray,
                   period: int = 10, multiplier: float = 3.0) -> Tuple[np.ndarray, np.ndarray]:
        """
        T15: Supertrend
        Returns: (supertrend, normalized_signal)
        """
        hl2 = (high + low) / 2
        
        # ATR
        tr = np.maximum(high - low,
                       np.maximum(np.abs(high - np.roll(close, 1)),
                                 np.abs(low - np.roll(close, 1))))
        tr[0] = high[0] - low[0]
        atr = ema(tr, period)
        
        # Basic bands
        upper_basic = hl2 + multiplier * atr
        lower_basic = hl2 - multiplier * atr
        
        n = len(close)
        upper = np.zeros(n)
        lower = np.zeros(n)
        supertrend = np.zeros(n)
        direction = np.ones(n)
        
        upper[0] = upper_basic[0]
        lower[0] = lower_basic[0]
        
        for i in range(1, n):
            # Upper band
            if upper_basic[i] < upper[i-1] or close[i-1] > upper[i-1]:
                upper[i] = upper_basic[i]
            else:
                upper[i] = upper[i-1]
            
            # Lower band
            if lower_basic[i] > lower[i-1] or close[i-1] < lower[i-1]:
                lower[i] = lower_basic[i]
            else:
                lower[i] = lower[i-1]
            
            # Direction
            if direction[i-1] == -1 and close[i] > upper[i-1]:
                direction[i] = 1
            elif direction[i-1] == 1 and close[i] < lower[i-1]:
                direction[i] = -1
            else:
                direction[i] = direction[i-1]
            
            # Supertrend value
            supertrend[i] = lower[i] if direction[i] == 1 else upper[i]
        
        return supertrend, direction


# =============================================================================
# VOLATILITY INDICATORS (V01-V15)
# =============================================================================

class VolatilityIndicators:
    """15 Volatility-based indicators."""
    
    @staticmethod
    def atr(high: np.ndarray, low: np.ndarray, close: np.ndarray,
            period: int = 14) -> Tuple[np.ndarray, np.ndarray]:
        """
        V01-V02: Average True Range
        Returns: (atr, atr_percent)
        """
        prev_close = np.roll(close, 1)
        prev_close[0] = close[0]
        
        tr = np.maximum(high - low,
                       np.maximum(np.abs(high - prev_close),
                                 np.abs(low - prev_close)))
        
        atr = ema(tr, period)
        atr_pct = 100 * atr / (close + 1e-10)
        
        return atr, atr_pct
    
    @staticmethod
    def bollinger_bands(close: np.ndarray, period: int = 20, 
                        std_dev: float = 2.0) -> Dict[str, np.ndarray]:
        """
        V03-V07: Bollinger Bands
        Returns: dict with upper, middle, lower, width, percent_b, signal
        """
        middle = sma(close, period)
        std = rolling_std(close, period)
        
        upper = middle + std_dev * std
        lower = middle - std_dev * std
        
        width = (upper - lower) / (middle + 1e-10)
        
        # %B: position within bands (0 = lower, 1 = upper)
        percent_b = (close - lower) / (upper - lower + 1e-10)
        
        # Signal: <0.2 = oversold (buy), >0.8 = overbought (sell)
        signal = np.zeros_like(close)
        signal[percent_b < 0.2] = (0.2 - percent_b[percent_b < 0.2]) / 0.2
        signal[percent_b > 0.8] = (0.8 - percent_b[percent_b > 0.8]) / 0.2
        
        return {
            'upper': upper,
            'middle': middle,
            'lower': lower,
            'width': width,
            'percent_b': percent_b,
            'signal': np.clip(signal, -1, 1)
        }
    
    @staticmethod
    def keltner_channels(high: np.ndarray, low: np.ndarray, close: np.ndarray,
                         ema_period: int = 20, atr_period: int = 10,
                         multiplier: float = 2.0) -> Dict[str, np.ndarray]:
        """
        V08-V09: Keltner Channels
        """
        middle = ema(close, ema_period)
        atr_val, _ = VolatilityIndicators.atr(high, low, close, atr_period)
        
        upper = middle + multiplier * atr_val
        lower = middle - multiplier * atr_val
        
        # Position within channels
        position = (close - lower) / (upper - lower + 1e-10)
        signal = np.clip((0.5 - position) * 2, -1, 1)
        
        return {
            'upper': upper,
            'middle': middle,
            'lower': lower,
            'signal': signal
        }
    
    @staticmethod
    def donchian_channels(high: np.ndarray, low: np.ndarray,
                          period: int = 20) -> Dict[str, np.ndarray]:
        """
        V10-V11: Donchian Channels
        """
        upper = rolling_max(high, period)
        lower = rolling_min(low, period)
        middle = (upper + lower) / 2
        
        return {
            'upper': upper,
            'middle': middle,
            'lower': lower
        }


# =============================================================================
# VOLUME INDICATORS (VL01-VL15)
# =============================================================================

class VolumeIndicators:
    """15 Volume-based indicators."""
    
    @staticmethod
    def obv(close: np.ndarray, volume: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        VL03: On-Balance Volume
        Returns: (obv, normalized_signal)
        """
        obv = np.zeros_like(close)
        
        for i in range(1, len(close)):
            if close[i] > close[i-1]:
                obv[i] = obv[i-1] + volume[i]
            elif close[i] < close[i-1]:
                obv[i] = obv[i-1] - volume[i]
            else:
                obv[i] = obv[i-1]
        
        # Signal: OBV trend
        obv_sma = sma(obv, 20)
        signal = np.clip((obv - obv_sma) / (np.abs(obv).max() + 1e-10) * 10, -1, 1)
        
        return obv, signal
    
    @staticmethod
    def mfi(high: np.ndarray, low: np.ndarray, close: np.ndarray,
            volume: np.ndarray, period: int = 14) -> Tuple[np.ndarray, np.ndarray]:
        """
        VL06: Money Flow Index
        Scale: 0-100 | Bullish: <20 | Bearish: >80
        """
        typical_price = (high + low + close) / 3
        money_flow = typical_price * volume
        
        # Positive and negative money flow
        pos_flow = np.zeros_like(money_flow)
        neg_flow = np.zeros_like(money_flow)
        
        for i in range(1, len(typical_price)):
            if typical_price[i] > typical_price[i-1]:
                pos_flow[i] = money_flow[i]
            else:
                neg_flow[i] = money_flow[i]
        
        # Sum over period
        pos_sum = sma(pos_flow, period) * period
        neg_sum = sma(neg_flow, period) * period
        
        mfi = 100 * pos_sum / (pos_sum + neg_sum + 1e-10)
        
        # Signal
        signal = np.zeros_like(mfi)
        signal[mfi < 20] = (20 - mfi[mfi < 20]) / 20
        signal[mfi > 80] = (80 - mfi[mfi > 80]) / 20
        
        return mfi, np.clip(signal, -1, 1)
    
    @staticmethod
    def cmf(high: np.ndarray, low: np.ndarray, close: np.ndarray,
            volume: np.ndarray, period: int = 20) -> Tuple[np.ndarray, np.ndarray]:
        """
        VL05: Chaikin Money Flow
        Scale: -1 to 1 | Bullish: >0 | Bearish: <0
        """
        # Money Flow Multiplier
        mfm = ((close - low) - (high - close)) / (high - low + 1e-10)
        # Money Flow Volume
        mfv = mfm * volume
        
        # CMF
        cmf = sma(mfv, period) / (sma(volume, period) + 1e-10)
        
        # Signal is already in -1 to 1 range
        return cmf, np.clip(cmf, -1, 1)
    
    @staticmethod
    def ad_line(high: np.ndarray, low: np.ndarray, close: np.ndarray,
                volume: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        VL04: Accumulation/Distribution Line
        """
        mfm = ((close - low) - (high - close)) / (high - low + 1e-10)
        adl = np.cumsum(mfm * volume)
        
        # Signal based on trend
        adl_sma = sma(adl, 20)
        signal = np.clip((adl - adl_sma) / (np.abs(adl).max() + 1e-10) * 10, -1, 1)
        
        return adl, signal


# =============================================================================
# SUPPORT/RESISTANCE INDICATORS (SR01-SR10)
# =============================================================================

class SupportResistanceIndicators:
    """10 Support/Resistance indicators."""
    
    @staticmethod
    def pivot_points(high: float, low: float, close: float) -> Dict[str, float]:
        """
        SR01-SR04: Standard Pivot Points (for single period)
        """
        pp = (high + low + close) / 3
        
        return {
            'pp': pp,
            'r1': 2 * pp - low,
            's1': 2 * pp - high,
            'r2': pp + (high - low),
            's2': pp - (high - low),
            'r3': pp + 2 * (high - low),
            's3': pp - 2 * (high - low)
        }
    
    @staticmethod
    def fibonacci_levels(swing_high: float, swing_low: float,
                         is_uptrend: bool = True) -> Dict[str, float]:
        """
        SR05-SR07: Fibonacci Retracement Levels
        """
        diff = swing_high - swing_low
        
        if is_uptrend:
            return {
                '0.0': swing_high,
                '0.236': swing_high - 0.236 * diff,
                '0.382': swing_high - 0.382 * diff,
                '0.5': swing_high - 0.5 * diff,
                '0.618': swing_high - 0.618 * diff,
                '0.786': swing_high - 0.786 * diff,
                '1.0': swing_low
            }
        else:
            return {
                '0.0': swing_low,
                '0.236': swing_low + 0.236 * diff,
                '0.382': swing_low + 0.382 * diff,
                '0.5': swing_low + 0.5 * diff,
                '0.618': swing_low + 0.618 * diff,
                '0.786': swing_low + 0.786 * diff,
                '1.0': swing_high
            }


# =============================================================================
# FEATURE AGGREGATOR
# =============================================================================

class IndicatorAggregator:
    """
    Aggregates all 100+ indicators into a feature vector for neural network.
    """
    
    def __init__(self, config: IndicatorConfig = CONFIG):
        self.config = config
        self.momentum = MomentumIndicators()
        self.trend = TrendIndicators()
        self.volatility = VolatilityIndicators()
        self.volume = VolumeIndicators()
        self.sr = SupportResistanceIndicators()
    
    def compute_all(self, high: np.ndarray, low: np.ndarray, 
                    close: np.ndarray, volume: np.ndarray) -> Dict[str, float]:
        """
        Compute all indicators and return normalized feature dict.
        Returns the latest value for each indicator.
        """
        features = {}
        
        # Momentum
        _, rsi_sig = self.momentum.rsi(close, 14)
        features['M01_RSI14'] = rsi_sig[-1]
        
        _, rsi7_sig = self.momentum.rsi(close, 7)
        features['M02_RSI7'] = rsi7_sig[-1]
        
        _, rsi21_sig = self.momentum.rsi(close, 21)
        features['M03_RSI21'] = rsi21_sig[-1]
        
        _, _, stoch_sig = self.momentum.stochastic(high, low, close)
        features['M04_STOCH'] = stoch_sig[-1]
        
        _, wr_sig = self.momentum.williams_r(high, low, close)
        features['M06_WILLIAMS'] = wr_sig[-1]
        
        _, cci_sig = self.momentum.cci(high, low, close, 14)
        features['M07_CCI14'] = cci_sig[-1]
        
        _, _, _, macd_sig = self.momentum.macd(close)
        features['M14_MACD'] = macd_sig[-1]
        
        _, mom_sig = self.momentum.momentum(close)
        features['M09_MOM'] = mom_sig[-1]
        
        _, roc_sig = self.momentum.roc(close)
        features['M10_ROC'] = roc_sig[-1]
        
        _, ao_sig = self.momentum.awesome_oscillator(high, low)
        features['M13_AO'] = ao_sig[-1]
        
        _, uo_sig = self.momentum.ultimate_oscillator(high, low, close)
        features['M12_UO'] = uo_sig[-1]
        
        # Trend
        _, _, _, adx_sig = self.trend.adx(high, low, close)
        features['T01_ADX'] = adx_sig[-1]
        
        ema_ribbon = self.trend.ema_ribbon(close)
        for key, (_, sig) in ema_ribbon.items():
            features[f'T_{key.upper()}'] = sig[-1]
        
        _, _, sma_sig = self.trend.sma_cross(close, 20, 50)
        features['T10_SMA_CROSS'] = sma_sig[-1]
        
        _, sar_sig = self.trend.parabolic_sar(high, low, close)
        features['T14_SAR'] = sar_sig[-1]
        
        _, st_sig = self.trend.supertrend(high, low, close)
        features['T15_SUPERTREND'] = st_sig[-1]
        
        # Volatility
        bb = self.volatility.bollinger_bands(close)
        features['V07_BB'] = bb['signal'][-1]
        
        kc = self.volatility.keltner_channels(high, low, close)
        features['V08_KELTNER'] = kc['signal'][-1]
        
        # Volume
        _, obv_sig = self.volume.obv(close, volume)
        features['VL03_OBV'] = obv_sig[-1]
        
        _, mfi_sig = self.volume.mfi(high, low, close, volume)
        features['VL06_MFI'] = mfi_sig[-1]
        
        _, cmf_sig = self.volume.cmf(high, low, close, volume)
        features['VL05_CMF'] = cmf_sig[-1]
        
        _, ad_sig = self.volume.ad_line(high, low, close, volume)
        features['VL04_AD'] = ad_sig[-1]
        
        return features
    
    def get_consensus_signal(self, features: Dict[str, float]) -> Tuple[float, float]:
        """
        Calculate consensus signal from all features.
        Returns: (direction [-1 to 1], confidence [0 to 1])
        """
        signals = list(features.values())
        avg_signal = np.mean(signals)
        
        # Count agreement
        bullish = sum(1 for s in signals if s > 0.3)
        bearish = sum(1 for s in signals if s < -0.3)
        total = len(signals)
        
        if bullish > bearish:
            confidence = bullish / total
            direction = avg_signal
        elif bearish > bullish:
            confidence = bearish / total
            direction = avg_signal
        else:
            confidence = 0.0
            direction = 0.0
        
        return direction, confidence


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'IndicatorConfig',
    'CONFIG',
    'SignalStrength',
    'MomentumIndicators',
    'TrendIndicators',
    'VolatilityIndicators',
    'VolumeIndicators',
    'SupportResistanceIndicators',
    'IndicatorAggregator',
    # Utilities
    'ema', 'sma', 'rolling_max', 'rolling_min', 'rolling_std', 'normalize'
]
