"""
Market Regime Classifier — HMM-based regime detection.

Uses a Gaussian Hidden Markov Model with 4 states to classify
the current market regime from indicator features. Includes a
persistence filter (inspired by Gekko) to prevent whipsawing.

States:
    TRENDING  — ADX > 25, EMA aligned, moderate vol
    RANGING   — ADX < 20, narrow BB, low volume
    VOLATILE  — ATR > 2x mean, wide BB, high volume
    LOW_VOL   — ATR < 0.5x mean, BB squeeze, very low volume

Ref: FUSION_PLAN Fase 4, item 4.1
"""

from __future__ import annotations

from enum import IntEnum
from typing import Optional

import numpy as np
import pandas as pd
from loguru import logger


class Regime(IntEnum):
    TRENDING = 0
    RANGING = 1
    VOLATILE = 2
    LOW_VOL = 3


# Human-readable labels
REGIME_LABELS = {
    Regime.TRENDING: "TRENDING",
    Regime.RANGING: "RANGING",
    Regime.VOLATILE: "VOLATILE",
    Regime.LOW_VOL: "LOW_VOL",
}


class MarketRegimeClassifier:
    """
    Gaussian HMM with 4 components for market regime classification.

    Features (computed per bar over a rolling window):
        1. ADX (trend strength, 0-100)
        2. ATR / close (relative volatility)
        3. BB_width / close (bandwidth, relative)
        4. Volume ratio (vs 20-bar mean)
        5. EMA alignment score [-1, +1]

    The persistence filter requires a new regime to persist for
    `min_persistence` consecutive bars before switching.
    """

    def __init__(self, n_states: int = 4, min_persistence: int = 5,
                 seed: int = 42):
        self.n_states = n_states
        self.min_persistence = min_persistence
        self.seed = seed
        self._hmm = None
        self._fitted = False

    def _extract_features(self, df: pd.DataFrame) -> np.ndarray:
        """
        Extract 5-dim feature matrix from indicator DataFrame.

        Expects columns: adx, atr, close, bb_bandwidth (or bb_upper/bb_lower),
        volume, ema_9, ema_21, ema_50, ema_200.
        """
        feats = pd.DataFrame(index=df.index)

        # 1. ADX (trend strength)
        if "adx" in df.columns:
            feats["adx"] = df["adx"].fillna(20.0)
        else:
            feats["adx"] = 20.0

        # 2. Relative volatility: ATR / close
        if "atr" in df.columns and "close" in df.columns:
            feats["atr_rel"] = (df["atr"] / df["close"].replace(0, np.nan)).fillna(0.01)
        else:
            feats["atr_rel"] = 0.01

        # 3. Bollinger bandwidth relative
        if "bb_bandwidth" in df.columns and "close" in df.columns:
            feats["bb_rel"] = (df["bb_bandwidth"] / df["close"].replace(0, np.nan)).fillna(0.02)
        elif "bb_upper" in df.columns and "bb_lower" in df.columns and "close" in df.columns:
            bb_w = df["bb_upper"] - df["bb_lower"]
            feats["bb_rel"] = (bb_w / df["close"].replace(0, np.nan)).fillna(0.02)
        else:
            feats["bb_rel"] = 0.02

        # 4. Volume ratio (vs 20-bar SMA)
        if "volume" in df.columns:
            vol_ma = df["volume"].rolling(20, min_periods=1).mean()
            feats["vol_ratio"] = (df["volume"] / vol_ma.replace(0, 1.0)).fillna(1.0)
        else:
            feats["vol_ratio"] = 1.0

        # 5. EMA alignment score [-1, +1]
        ema_cols = [c for c in ["ema_9", "ema_21", "ema_50", "ema_200"] if c in df.columns]
        if len(ema_cols) >= 2:
            scores = np.zeros(len(df))
            for i in range(len(ema_cols) - 1):
                diff = df[ema_cols[i]].values - df[ema_cols[i + 1]].values
                scores += np.sign(diff)
            max_score = max(len(ema_cols) - 1, 1)
            feats["ema_align"] = pd.Series(scores / max_score, index=df.index).fillna(0.0)
        else:
            feats["ema_align"] = 0.0

        return feats.values.astype(np.float64)

    def fit(self, df: pd.DataFrame) -> "MarketRegimeClassifier":
        """
        Train the HMM on historical data with pre-computed indicators.

        Args:
            df: DataFrame with indicator columns (from compute_all_indicators).
        """
        try:
            from hmmlearn.hmm import GaussianHMM
        except ImportError:
            raise ImportError("hmmlearn required: pip install hmmlearn>=0.3.0")

        X = self._extract_features(df)
        valid = ~np.isnan(X).any(axis=1) & ~np.isinf(X).any(axis=1)
        X_clean = X[valid]

        if len(X_clean) < self.n_states * 10:
            logger.warning(f"Insufficient data for HMM ({len(X_clean)} rows), "
                           "falling back to rule-based classification")
            self._fitted = False
            return self

        self._hmm = GaussianHMM(
            n_components=self.n_states,
            covariance_type="full",
            n_iter=100,
            random_state=self.seed,
            verbose=False,
        )
        self._hmm.fit(X_clean)
        self._fitted = True

        # Map HMM states to Regime enum based on feature means
        self._map_states_to_regimes(X_clean)

        logger.info(f"HMM fitted on {len(X_clean)} bars, "
                    f"score={self._hmm.score(X_clean):.1f}")
        return self

    def _map_states_to_regimes(self, X: np.ndarray) -> None:
        """
        Map HMM hidden states to semantic Regime labels using feature means.

        Logic: rank states by ADX mean and ATR_rel mean to assign labels.
        """
        means = self._hmm.means_  # (n_states, n_features)
        # ADX is col 0, ATR_rel is col 1
        adx_means = means[:, 0]
        atr_means = means[:, 1]

        # Assign regimes by characteristic feature patterns
        state_map = {}
        remaining = set(range(self.n_states))

        # VOLATILE: highest ATR_rel
        volatile_state = max(remaining, key=lambda s: atr_means[s])
        state_map[volatile_state] = Regime.VOLATILE
        remaining.discard(volatile_state)

        # LOW_VOL: lowest ATR_rel
        lowvol_state = min(remaining, key=lambda s: atr_means[s])
        state_map[lowvol_state] = Regime.LOW_VOL
        remaining.discard(lowvol_state)

        # TRENDING: highest ADX among remaining
        trending_state = max(remaining, key=lambda s: adx_means[s])
        state_map[trending_state] = Regime.TRENDING
        remaining.discard(trending_state)

        # RANGING: the last one
        ranging_state = remaining.pop()
        state_map[ranging_state] = Regime.RANGING

        self._state_map = state_map

    def classify(self, df: pd.DataFrame) -> pd.Series:
        """
        Classify each bar into a regime.

        Returns a Series of Regime values with persistence filter applied.
        """
        X = self._extract_features(df)

        if self._fitted and self._hmm is not None:
            valid = ~np.isnan(X).any(axis=1) & ~np.isinf(X).any(axis=1)
            raw_states = np.full(len(X), -1, dtype=int)
            if valid.any():
                raw_states[valid] = self._hmm.predict(X[valid])
            regimes = np.array([
                self._state_map.get(s, Regime.RANGING) if s >= 0 else Regime.RANGING
                for s in raw_states
            ])
        else:
            regimes = self._rule_based_classify(X)

        # Apply persistence filter
        filtered = self._persistence_filter(regimes)

        return pd.Series(filtered, index=df.index, name="regime")

    def current_regime(self, df: pd.DataFrame) -> Regime:
        """Return the regime at the last bar."""
        regimes = self.classify(df)
        return Regime(regimes.iloc[-1])

    def _rule_based_classify(self, X: np.ndarray) -> np.ndarray:
        """
        Fallback classification when HMM is not fitted.

        Uses simple thresholds on features:
            ADX > 25 → TRENDING
            ATR_rel > 2x median → VOLATILE
            ATR_rel < 0.5x median → LOW_VOL
            else → RANGING
        """
        adx_vals = X[:, 0]
        atr_vals = X[:, 1]
        atr_median = np.nanmedian(atr_vals) if len(atr_vals) > 0 else 0.01

        regimes = np.full(len(X), Regime.RANGING, dtype=int)

        for i in range(len(X)):
            if np.isnan(adx_vals[i]) or np.isnan(atr_vals[i]):
                continue
            if atr_vals[i] > 2.0 * atr_median:
                regimes[i] = Regime.VOLATILE
            elif atr_vals[i] < 0.5 * atr_median:
                regimes[i] = Regime.LOW_VOL
            elif adx_vals[i] > 25:
                regimes[i] = Regime.TRENDING
            # else stays RANGING

        return regimes

    def _persistence_filter(self, regimes: np.ndarray) -> np.ndarray:
        """
        Apply persistence filter to prevent whipsawing.

        A regime change only takes effect if the new regime persists
        for at least `min_persistence` consecutive bars.
        """
        if len(regimes) == 0:
            return regimes

        filtered = np.copy(regimes)
        current = regimes[0]
        pending = regimes[0]
        count = 0

        for i in range(len(regimes)):
            if regimes[i] == current:
                filtered[i] = current
                pending = current
                count = 0
            elif regimes[i] == pending:
                count += 1
                if count >= self.min_persistence:
                    current = pending
                    filtered[i] = current
                else:
                    filtered[i] = current
            else:
                pending = regimes[i]
                count = 1
                filtered[i] = current

        return filtered
