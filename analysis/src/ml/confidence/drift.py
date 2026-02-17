"""
Meta-Drift Surveillance — Feature Distribution Drift Detection

Detects when feature distributions or prediction statistics shift away
from training-time baselines. Transfers AI_BIOPSY_PART2.md §3.7.

Drift formula:
    stat_drift       = |recent_mean - baseline_mean| / max(|baseline_mean|, 1e-8) / 0.20
    distribution_drift = avg KL divergence across feature histograms
    combined         = 0.4 × stat + 0.6 × distribution
    confidence_adj   = raw × max(1.0 - drift × 0.5, 0.5)
    retrain trigger  = combined_drift > threshold (default 0.8)
"""

from collections import deque
from typing import Dict, Optional

import numpy as np


class DriftDetector:
    """Detects statistical and distributional drift from training baselines."""

    def __init__(self, window_size: int = 100, n_bins: int = 50,
                 retrain_threshold: float = 0.8):
        self.window_size = window_size
        self.n_bins = n_bins
        self._retrain_threshold = retrain_threshold

        # Rolling prediction window
        self._predictions: deque = deque(maxlen=window_size)

        # Rolling feature windows: {feature_name: deque of values}
        self._feature_windows: Dict[str, deque] = {}

        # Baselines (set during training)
        self._baseline_pred_mean: float = 0.0
        self._baseline_pred_std: float = 1.0
        self._baseline_histograms: Dict[str, np.ndarray] = {}
        self._baseline_edges: Dict[str, np.ndarray] = {}
        self._baseline_set: bool = False

    def set_baseline(self, training_predictions: np.ndarray,
                     training_features: Dict[str, np.ndarray]):
        """
        Set training-time baselines for drift comparison.

        Args:
            training_predictions: Array of model predictions during training.
            training_features: Dict of {feature_name: array of feature values}.
        """
        self._baseline_pred_mean = float(np.mean(training_predictions))
        self._baseline_pred_std = float(np.std(training_predictions)) + 1e-8

        for name, values in training_features.items():
            hist, edges = np.histogram(values, bins=self.n_bins)
            hist = hist.astype(float) + 1e-10  # Prevent log(0)
            self._baseline_histograms[name] = hist / hist.sum()
            self._baseline_edges[name] = edges
            self._feature_windows[name] = deque(maxlen=self.window_size)

        self._baseline_set = True

    def record_prediction(self, prediction: float,
                          features: Optional[Dict[str, float]] = None):
        """Record a single inference-time prediction and feature values."""
        self._predictions.append(prediction)
        if features:
            for name, value in features.items():
                if name not in self._feature_windows:
                    self._feature_windows[name] = deque(maxlen=self.window_size)
                self._feature_windows[name].append(value)

    def detect_stat_drift(self) -> float:
        """
        Compare recent prediction mean to baseline.
        A 20% shift = max drift (1.0).
        """
        if not self._predictions or not self._baseline_set:
            return 0.0

        recent_mean = float(np.mean(list(self._predictions)))
        shift = abs(recent_mean - self._baseline_pred_mean)
        drift = shift / max(abs(self._baseline_pred_mean), 1e-8) / 0.20
        return min(drift, 1.0)

    def detect_distribution_drift(self) -> float:
        """
        Average KL divergence across feature histograms.
        Normalized to [0, 1].
        """
        if not self._baseline_set or not self._feature_windows:
            return 0.0

        kl_divs = []
        for name, baseline_hist in self._baseline_histograms.items():
            window = self._feature_windows.get(name)
            if not window or len(window) < 10:
                continue

            values = np.array(list(window))
            edges = self._baseline_edges[name]
            recent_hist, _ = np.histogram(values, bins=edges)
            recent_hist = recent_hist.astype(float) + 1e-10
            recent_hist = recent_hist / recent_hist.sum()

            # KL divergence: sum(P × log(P/Q))
            kl = float(np.sum(recent_hist * np.log(recent_hist / baseline_hist)))
            kl_divs.append(kl)

        if not kl_divs:
            return 0.0

        avg_kl = np.mean(kl_divs)
        # Normalize: KL of 1.0 maps to drift=1.0
        return min(float(avg_kl), 1.0)

    def combined_drift(self) -> float:
        """Weighted combination: 0.4 × stat + 0.6 × distribution."""
        return 0.4 * self.detect_stat_drift() + 0.6 * self.detect_distribution_drift()

    def adjust_confidence(self, raw_confidence: float) -> float:
        """Reduce confidence proportional to drift, floored at 50%."""
        drift = self.combined_drift()
        adjustment = max(1.0 - drift * 0.5, 0.5)
        return raw_confidence * adjustment

    def should_retrain(self) -> bool:
        """True if combined drift exceeds the retrain threshold."""
        return self.combined_drift() > self._retrain_threshold
