"""Smoke tests for the signal aggregation pipeline."""

import pandas as pd
import pytest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.quant.signal_processor import (
    Signal, AggregatedSignal, SignalType, SignalDirection,
    extract_indicator_signals, aggregate_signals,
)
from src.quant.indicators import compute_all_indicators


# =============================================================================
# Signal Dataclass
# =============================================================================

class TestSignalDataclass:
    def test_create_signal(self):
        sig = Signal(
            source="RSI",
            signal_type=SignalType.INDICATOR,
            direction=SignalDirection.BULLISH,
            strength=75.0,
            timeframe="H1",
            symbol="XAUUSD",
            timestamp=pd.Timestamp.now(),
        )
        assert sig.source == "RSI"
        assert sig.direction == SignalDirection.BULLISH
        assert sig.strength == 75.0


class TestAggregatedSignalDataclass:
    def test_create_empty(self):
        agg = AggregatedSignal(
            symbol="XAUUSD",
            direction=SignalDirection.NEUTRAL,
            confidence=0.0,
            signals=[],
            bullish_count=0,
            bearish_count=0,
            dominant_timeframe="",
            timestamp=pd.Timestamp.now(),
        )
        assert agg.confidence == 0.0
        assert agg.bullish_count == 0


# =============================================================================
# Signal Extraction
# =============================================================================

class TestExtractIndicatorSignals:
    def test_returns_list(self, ohlcv_df):
        df = compute_all_indicators(ohlcv_df)
        signals = extract_indicator_signals(df, symbol="XAUUSD", timeframe="H1")
        assert isinstance(signals, list)
        for sig in signals:
            assert isinstance(sig, Signal)

    def test_signals_have_correct_symbol(self, ohlcv_df):
        df = compute_all_indicators(ohlcv_df)
        signals = extract_indicator_signals(df, symbol="XAUUSD", timeframe="H1")
        for sig in signals:
            assert sig.symbol == "XAUUSD"
            assert sig.timeframe == "H1"


# =============================================================================
# Signal Aggregation
# =============================================================================

class TestAggregateSignals:
    def test_empty_signals_returns_neutral(self):
        result = aggregate_signals([], symbol="XAUUSD")
        assert result.direction == SignalDirection.NEUTRAL
        assert result.confidence == 0.0

    def test_single_bullish_signal(self):
        sig = Signal(
            source="RSI",
            signal_type=SignalType.INDICATOR,
            direction=SignalDirection.BULLISH,
            strength=80.0,
            timeframe="H1",
            symbol="XAUUSD",
            timestamp=pd.Timestamp.now(),
        )
        result = aggregate_signals([sig], symbol="XAUUSD")
        assert result.direction == SignalDirection.BULLISH
        assert result.confidence > 0
        assert result.bullish_count == 1
        assert result.bearish_count == 0

    def test_mixed_signals(self):
        bull = Signal(
            source="RSI",
            signal_type=SignalType.INDICATOR,
            direction=SignalDirection.BULLISH,
            strength=90.0,
            timeframe="H1",
            symbol="XAUUSD",
            timestamp=pd.Timestamp.now(),
        )
        bear = Signal(
            source="MACD",
            signal_type=SignalType.INDICATOR,
            direction=SignalDirection.BEARISH,
            strength=60.0,
            timeframe="H1",
            symbol="XAUUSD",
            timestamp=pd.Timestamp.now(),
        )
        result = aggregate_signals([bull, bear], symbol="XAUUSD")
        assert result.bullish_count == 1
        assert result.bearish_count == 1
        assert result.confidence > 0


# =============================================================================
# Round-trip: OHLCV -> Indicators -> Signals -> Aggregation
# =============================================================================

class TestRoundTrip:
    def test_full_pipeline(self, ohlcv_df):
        df = compute_all_indicators(ohlcv_df)
        signals = extract_indicator_signals(df, symbol="XAUUSD", timeframe="H1")
        result = aggregate_signals(signals, symbol="XAUUSD")
        assert isinstance(result, AggregatedSignal)
        assert result.symbol == "XAUUSD"
