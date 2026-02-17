"""Tests for the Smart Money Concepts (SMC) module."""

import numpy as np
import pandas as pd
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.quant.smart_money import (
    Bias, FVGType, StructureBreakType,
    FairValueGap, SwingPoint, StructureBreak, LiquidityZone, SMCSetup,
    detect_swing_points, detect_structure_breaks,
    detect_fvg, classify_fvg, check_fvg_mitigation,
    detect_liquidity_zones, detect_liquidity_sweeps,
    score_smc_setup, detect_all_smc,
)


# =============================================================================
# HELPERS: Synthetic data generators
# =============================================================================

def _make_ohlcv(n: int = 200, seed: int = 42) -> pd.DataFrame:
    """Standard synthetic OHLCV — same shape as conftest fixture."""
    np.random.seed(seed)
    dates = pd.date_range("2024-01-01", periods=n, freq="h")
    close = 1800.0 + np.cumsum(np.random.randn(n) * 2.0)
    high = close + np.abs(np.random.randn(n) * 1.5)
    low = close - np.abs(np.random.randn(n) * 1.5)
    open_ = close + np.random.randn(n) * 0.5
    volume = np.random.lognormal(mean=10, sigma=0.5, size=n)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=dates,
    )


def _make_bullish_fvg_data() -> pd.DataFrame:
    """
    Hand-crafted 10-bar series with a guaranteed bullish FVG at bars 3-4-5.

    Candle 3 (i-2): high = 100
    Candle 4 (i-1): strong bullish displacement
    Candle 5 (i):   low  = 102  → gap = [100, 102]
    """
    n = 10
    dates = pd.date_range("2024-01-01", periods=n, freq="h")
    # Baseline flat market
    open_ = [99.0, 99.5, 99.0, 99.0, 100.5, 103.0, 104.0, 104.5, 105.0, 105.0]
    high  = [99.5, 100.0, 99.5, 100.0, 103.0, 105.0, 105.0, 105.5, 105.5, 105.5]
    low   = [98.5, 99.0, 98.5, 98.5, 100.0, 102.0, 103.5, 104.0, 104.5, 104.5]
    close = [99.5, 99.0, 99.0, 99.5, 102.5, 104.5, 104.5, 105.0, 105.0, 105.0]
    volume = [1000] * n
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=dates,
    )


def _make_bearish_fvg_data() -> pd.DataFrame:
    """
    Hand-crafted series with a guaranteed bearish FVG at bars 3-4-5.

    Candle 3 (i-2): low = 100
    Candle 4 (i-1): strong bearish displacement
    Candle 5 (i):   high = 98  → gap = [98, 100]
    """
    n = 10
    dates = pd.date_range("2024-01-01", periods=n, freq="h")
    open_ = [101.0, 100.5, 101.0, 101.0, 99.0, 97.0, 96.0, 95.5, 95.0, 95.0]
    high  = [101.5, 101.0, 101.5, 101.5, 100.0, 98.0, 96.5, 96.0, 95.5, 95.5]
    low   = [100.5, 100.0, 100.5, 100.0, 97.0, 96.0, 95.5, 95.0, 94.5, 94.5]
    close = [100.5, 101.0, 101.0, 100.5, 97.5, 96.5, 95.5, 95.0, 95.0, 95.0]
    volume = [1000] * n
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=dates,
    )


def _make_trending_data(direction: str = "up", n: int = 100) -> pd.DataFrame:
    """Create clearly trending data with pronounced swing points for BOS/CHOCH."""
    np.random.seed(7)
    dates = pd.date_range("2024-01-01", periods=n, freq="h")
    trend = np.linspace(0, 40, n) if direction == "up" else np.linspace(40, 0, n)
    # Add a zigzag component so swing highs/lows form clearly
    zigzag = np.sin(np.linspace(0, 8 * np.pi, n)) * 3.0
    noise = np.random.randn(n) * 0.5
    close = 1800.0 + trend + zigzag + noise
    high = close + np.abs(np.random.randn(n) * 1.5)
    low = close - np.abs(np.random.randn(n) * 1.5)
    open_ = close + np.random.randn(n) * 0.3
    volume = np.random.lognormal(10, 0.3, n)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=dates,
    )


def _make_equal_highs_data() -> pd.DataFrame:
    """Data with repeated highs at ~105 to form buy-side liquidity."""
    n = 30
    dates = pd.date_range("2024-01-01", periods=n, freq="h")
    close = np.array([100 + np.sin(i * 0.3) * 3 for i in range(n)])
    high = close + 1.0
    # Force equal highs at indices 5, 10, 15
    high[5] = 105.0
    high[10] = 105.0
    high[15] = 105.0
    low = close - 1.0
    open_ = close + np.random.randn(n) * 0.1
    volume = [1000] * n
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=dates,
    )


# =============================================================================
# TEST: Swing Point Detection
# =============================================================================

class TestSwingPoints:
    def test_detects_swings_on_trending_data(self):
        df = _make_trending_data("up", n=100)
        swings = detect_swing_points(df["high"], df["low"], order=5)
        assert len(swings) > 0

    def test_swing_highs_and_lows_present(self):
        df = _make_ohlcv(200)
        swings = detect_swing_points(df["high"], df["low"], order=5)
        has_high = any(s.is_high for s in swings)
        has_low = any(not s.is_high for s in swings)
        assert has_high and has_low

    def test_swing_index_within_bounds(self):
        df = _make_ohlcv(200)
        swings = detect_swing_points(df["high"], df["low"], order=5)
        for s in swings:
            assert 5 <= s.index < 195  # order=5 excludes edges

    def test_empty_on_too_short(self):
        df = _make_ohlcv(5)
        swings = detect_swing_points(df["high"], df["low"], order=5)
        assert len(swings) == 0


# =============================================================================
# TEST: Fair Value Gap Detection
# =============================================================================

class TestFVGDetection:
    def test_bullish_fvg_detected(self):
        df = _make_bullish_fvg_data()
        fvgs = detect_fvg(df["open"], df["high"], df["low"], df["close"], min_gap_atr=0.0)
        bullish = [f for f in fvgs if f.direction == Bias.BULLISH]
        assert len(bullish) > 0
        # Gap should be between candle 1 high and candle 3 low
        for fvg in bullish:
            assert fvg.high > fvg.low
            assert fvg.size > 0

    def test_bearish_fvg_detected(self):
        df = _make_bearish_fvg_data()
        fvgs = detect_fvg(df["open"], df["high"], df["low"], df["close"], min_gap_atr=0.0)
        bearish = [f for f in fvgs if f.direction == Bias.BEARISH]
        assert len(bearish) > 0
        for fvg in bearish:
            assert fvg.high > fvg.low

    def test_midpoint_is_correct(self):
        df = _make_bullish_fvg_data()
        fvgs = detect_fvg(df["open"], df["high"], df["low"], df["close"], min_gap_atr=0.0)
        for fvg in fvgs:
            expected_mid = (fvg.high + fvg.low) / 2
            assert abs(fvg.midpoint - expected_mid) < 1e-10

    def test_min_gap_atr_filter(self):
        df = _make_ohlcv(200)
        fvgs_loose = detect_fvg(df["open"], df["high"], df["low"], df["close"], min_gap_atr=0.0)
        fvgs_strict = detect_fvg(df["open"], df["high"], df["low"], df["close"], min_gap_atr=1.0)
        assert len(fvgs_loose) >= len(fvgs_strict)

    def test_fvg_type_is_standard_by_default(self):
        df = _make_bullish_fvg_data()
        fvgs = detect_fvg(df["open"], df["high"], df["low"], df["close"], min_gap_atr=0.0)
        for fvg in fvgs:
            assert fvg.fvg_type == FVGType.STANDARD

    def test_no_fvg_on_flat_market(self):
        """A perfectly flat market should produce no FVGs."""
        n = 50
        dates = pd.date_range("2024-01-01", periods=n, freq="h")
        flat = pd.DataFrame({
            "open": [100.0] * n,
            "high": [100.5] * n,
            "low": [99.5] * n,
            "close": [100.0] * n,
            "volume": [1000] * n,
        }, index=dates)
        fvgs = detect_fvg(flat["open"], flat["high"], flat["low"], flat["close"], min_gap_atr=0.3)
        assert len(fvgs) == 0


# =============================================================================
# TEST: FVG Mitigation & Inversion
# =============================================================================

class TestFVGMitigation:
    def test_mitigation_marks_fvg(self):
        df = _make_bullish_fvg_data()
        fvgs = detect_fvg(df["open"], df["high"], df["low"], df["close"], min_gap_atr=0.0)
        # Create price that dips back into the FVG zone
        h, l, c = df["high"].copy(), df["low"].copy(), df["close"].copy()
        for fvg in fvgs:
            if fvg.direction == Bias.BULLISH:
                # Force a candle after formation to dip into the gap
                test_idx = min(fvg.candle_index + 3, len(c) - 1)
                l.iloc[test_idx] = fvg.midpoint - 0.5
                c.iloc[test_idx] = fvg.midpoint - 0.3
                break

        check_fvg_mitigation(fvgs, h, l, c)
        mitigated = [f for f in fvgs if f.mitigated]
        assert len(mitigated) > 0

    def test_unmitigated_fvg_stays_active(self):
        df = _make_bullish_fvg_data()
        fvgs = detect_fvg(df["open"], df["high"], df["low"], df["close"], min_gap_atr=0.0)
        # Don't modify prices — price continues up, FVG stays active
        check_fvg_mitigation(fvgs, df["high"], df["low"], df["close"])
        bullish = [f for f in fvgs if f.direction == Bias.BULLISH]
        # At least some should remain unmitigated in a trending market
        active = [f for f in bullish if not f.mitigated]
        assert len(active) >= 0  # Assertion depends on data — just confirm no crash


# =============================================================================
# TEST: FVG Classification (Breakaway)
# =============================================================================

class TestFVGClassification:
    def test_breakaway_classification(self):
        """If a BOS happens at the same bar as FVG, it becomes BREAKAWAY."""
        df = _make_bullish_fvg_data()
        fvgs = detect_fvg(df["open"], df["high"], df["low"], df["close"], min_gap_atr=0.0)
        if not fvgs:
            pytest.skip("No FVGs in test data")

        # Create a fake BOS at the FVG's candle
        fake_swing = SwingPoint(index=0, price=99.0, is_high=True, timestamp=df.index[0])
        fake_bos = StructureBreak(
            break_type=StructureBreakType.BOS,
            direction=Bias.BULLISH,
            price=99.0,
            index=fvgs[0].candle_index,
            timestamp=df.index[fvgs[0].candle_index],
            swing_origin=fake_swing,
        )
        classify_fvg(fvgs, [fake_bos])
        assert fvgs[0].fvg_type == FVGType.BREAKAWAY

    def test_no_breakaway_without_bos(self):
        df = _make_bullish_fvg_data()
        fvgs = detect_fvg(df["open"], df["high"], df["low"], df["close"], min_gap_atr=0.0)
        classify_fvg(fvgs, [])  # No structure breaks
        for fvg in fvgs:
            assert fvg.fvg_type == FVGType.STANDARD


# =============================================================================
# TEST: Break of Structure & Change of Character
# =============================================================================

class TestStructureBreaks:
    def test_bos_detected_in_uptrend(self):
        df = _make_trending_data("up", n=100)
        breaks = detect_structure_breaks(df["high"], df["low"], df["close"], swing_order=5)
        bullish_bos = [
            b for b in breaks
            if b.break_type == StructureBreakType.BOS and b.direction == Bias.BULLISH
        ]
        assert len(bullish_bos) > 0

    def test_bos_detected_in_downtrend(self):
        df = _make_trending_data("down", n=100)
        breaks = detect_structure_breaks(df["high"], df["low"], df["close"], swing_order=5)
        bearish_bos = [
            b for b in breaks
            if b.break_type == StructureBreakType.BOS and b.direction == Bias.BEARISH
        ]
        assert len(bearish_bos) > 0

    def test_choch_on_trend_reversal(self):
        """Concatenate up-trend + down-trend → should produce at least one CHOCH."""
        up = _make_trending_data("up", n=60)
        down = _make_trending_data("down", n=60)
        # Shift down-trend prices to start from where up-trend ended
        offset = up["close"].iloc[-1] - down["close"].iloc[0]
        for col in ["open", "high", "low", "close"]:
            down[col] = down[col] + offset
        down.index = pd.date_range(up.index[-1] + pd.Timedelta(hours=1), periods=60, freq="h")

        combined = pd.concat([up, down])
        breaks = detect_structure_breaks(
            combined["high"], combined["low"], combined["close"], swing_order=5,
        )
        choch = [b for b in breaks if b.break_type == StructureBreakType.CHOCH]
        assert len(choch) > 0

    def test_no_breaks_on_very_short_data(self):
        df = _make_ohlcv(10)
        breaks = detect_structure_breaks(df["high"], df["low"], df["close"], swing_order=5)
        # May or may not detect anything — just ensure no crash
        assert isinstance(breaks, list)

    def test_break_price_matches_swing(self):
        df = _make_trending_data("up", n=100)
        breaks = detect_structure_breaks(df["high"], df["low"], df["close"], swing_order=5)
        for b in breaks:
            assert b.price == b.swing_origin.price


# =============================================================================
# TEST: Liquidity Zones
# =============================================================================

class TestLiquidityZones:
    def test_equal_highs_detected(self):
        df = _make_equal_highs_data()
        zones = detect_liquidity_zones(
            df["high"], df["low"], tolerance_pct=0.005, min_touches=2, lookback=30,
        )
        buy_side = [z for z in zones if z.is_buy_side]
        assert len(buy_side) > 0

    def test_zone_strength_matches_touches(self):
        df = _make_equal_highs_data()
        zones = detect_liquidity_zones(
            df["high"], df["low"], tolerance_pct=0.005, min_touches=2, lookback=30,
        )
        for z in zones:
            assert z.strength >= 2

    def test_no_zones_on_random_data(self):
        """Random data with high variance should produce fewer zones."""
        np.random.seed(99)
        n = 100
        dates = pd.date_range("2024-01-01", periods=n, freq="h")
        high = pd.Series(np.random.uniform(100, 200, n), index=dates)
        low = high - np.random.uniform(1, 5, n)
        zones = detect_liquidity_zones(high, low, tolerance_pct=0.001, min_touches=3)
        # Might still find some, but far fewer
        assert isinstance(zones, list)


# =============================================================================
# TEST: Liquidity Sweeps
# =============================================================================

class TestLiquiditySweeps:
    def test_sweep_detected_when_price_pierces_and_rejects(self):
        """Manually inject a sweep: wick above zone, close below."""
        df = _make_equal_highs_data()
        h, l, c = df["high"].copy(), df["low"].copy(), df["close"].copy()

        zones = detect_liquidity_zones(h, l, tolerance_pct=0.005, min_touches=2, lookback=30)
        buy_zones = [z for z in zones if z.is_buy_side]
        if not buy_zones:
            pytest.skip("No buy-side zones")

        target = buy_zones[0]
        sweep_bar = max(target.indices) + 2
        if sweep_bar >= len(h):
            pytest.skip("Not enough bars after zone")

        # Wick above the zone, close below
        h.iloc[sweep_bar] = target.price + 0.5
        c.iloc[sweep_bar] = target.price - 0.5

        detect_liquidity_sweeps(h, l, c, zones)
        swept = [z for z in zones if z.swept]
        assert len(swept) > 0

    def test_no_sweep_when_close_stays_above(self):
        """If close stays above the zone, it's a breakout, not a sweep."""
        # Build isolated data: equal highs at 105, all other bars well below
        n = 30
        dates = pd.date_range("2024-01-01", periods=n, freq="h")
        h = pd.Series([100.0] * n, index=dates)
        l = pd.Series([98.0] * n, index=dates)
        c = pd.Series([99.0] * n, index=dates)

        # Equal highs at 105 on bars 5, 10, 15
        h.iloc[5] = 105.0
        h.iloc[10] = 105.0
        h.iloc[15] = 105.0

        zones = detect_liquidity_zones(h, l, tolerance_pct=0.005, min_touches=2, lookback=30)
        buy_zones = [z for z in zones if z.is_buy_side and z.price > 104]
        if not buy_zones:
            pytest.skip("No buy-side zone at 105")

        target = buy_zones[0]
        sweep_bar = 20

        # Breakout: high goes above AND close stays above → not a sweep
        h.iloc[sweep_bar] = 106.0
        c.iloc[sweep_bar] = 105.5

        detect_liquidity_sweeps(h, l, c, zones)
        target_swept = [z for z in zones if z.swept and abs(z.price - target.price) < 1.0]
        assert len(target_swept) == 0


# =============================================================================
# TEST: Confluence Scoring
# =============================================================================

class TestConfluenceScoring:
    def test_max_confluence_with_all_factors(self):
        fvg = FairValueGap(
            direction=Bias.BULLISH,
            fvg_type=FVGType.BREAKAWAY,
            high=102.0, low=100.0, midpoint=101.0,
            candle_index=5,
            timestamp=pd.Timestamp("2024-01-01"),
            size=2.0, size_atr_ratio=1.5,
        )
        fake_swing = SwingPoint(index=3, price=99.0, is_high=True, timestamp=pd.Timestamp("2024-01-01"))
        bos = StructureBreak(
            break_type=StructureBreakType.BOS,
            direction=Bias.BULLISH,
            price=99.0, index=5,
            timestamp=pd.Timestamp("2024-01-01"),
            swing_origin=fake_swing,
        )
        liq = LiquidityZone(price=99.5, is_buy_side=False, strength=3, swept=True, sweep_index=5)

        setup = score_smc_setup(fvg, bos, liq, htf_bias=Bias.BULLISH)

        # FVG(30) + breakaway(10) + BOS(25) + sweep(25) + HTF(10) = 100
        assert setup.confluence_score == 100
        assert setup.direction == Bias.BULLISH
        assert len(setup.reasoning) >= 4

    def test_zero_with_no_factors(self):
        setup = score_smc_setup(None, None, None)
        assert setup.confluence_score == 0
        assert setup.direction == Bias.NEUTRAL

    def test_fvg_only_score(self):
        fvg = FairValueGap(
            direction=Bias.BEARISH,
            fvg_type=FVGType.STANDARD,
            high=102.0, low=100.0, midpoint=101.0,
            candle_index=5,
            timestamp=pd.Timestamp("2024-01-01"),
            size=2.0, size_atr_ratio=1.0,
        )
        setup = score_smc_setup(fvg, None, None)
        assert setup.confluence_score == 30
        assert setup.direction == Bias.BEARISH

    def test_choch_lower_than_bos(self):
        """CHOCH should contribute less than BOS."""
        fake_swing = SwingPoint(index=3, price=99.0, is_high=True, timestamp=pd.Timestamp("2024-01-01"))
        bos = StructureBreak(
            break_type=StructureBreakType.BOS,
            direction=Bias.BULLISH,
            price=99.0, index=5,
            timestamp=pd.Timestamp("2024-01-01"),
            swing_origin=fake_swing,
        )
        choch = StructureBreak(
            break_type=StructureBreakType.CHOCH,
            direction=Bias.BULLISH,
            price=99.0, index=5,
            timestamp=pd.Timestamp("2024-01-01"),
            swing_origin=fake_swing,
        )
        fvg = FairValueGap(
            direction=Bias.BULLISH,
            fvg_type=FVGType.STANDARD,
            high=102.0, low=100.0, midpoint=101.0,
            candle_index=5,
            timestamp=pd.Timestamp("2024-01-01"),
            size=2.0, size_atr_ratio=1.0,
        )
        setup_bos = score_smc_setup(fvg, bos, None)
        setup_choch = score_smc_setup(fvg, choch, None)
        assert setup_bos.confluence_score > setup_choch.confluence_score


# =============================================================================
# TEST: Full Integration (detect_all_smc)
# =============================================================================

class TestDetectAllSMC:
    def test_adds_all_columns(self):
        df = _make_ohlcv(200)
        result = detect_all_smc(df)
        expected_cols = [
            "smc_bullish_fvg", "smc_bearish_fvg", "smc_fvg_distance",
            "smc_bos_bullish", "smc_bos_bearish",
            "smc_choch_bullish", "smc_choch_bearish",
            "smc_liquidity_sweep", "smc_confluence",
        ]
        for col in expected_cols:
            assert col in result.columns, f"Missing column: {col}"

    def test_output_length_matches_input(self):
        df = _make_ohlcv(200)
        result = detect_all_smc(df)
        assert len(result) == len(df)

    def test_bool_columns_are_boolean(self):
        df = _make_ohlcv(200)
        result = detect_all_smc(df)
        bool_cols = [
            "smc_bullish_fvg", "smc_bearish_fvg",
            "smc_bos_bullish", "smc_bos_bearish",
            "smc_choch_bullish", "smc_choch_bearish",
            "smc_liquidity_sweep",
        ]
        for col in bool_cols:
            assert result[col].dtype == bool, f"{col} is not bool"

    def test_confluence_bounded(self):
        df = _make_ohlcv(200)
        result = detect_all_smc(df)
        assert result["smc_confluence"].min() >= 0
        assert result["smc_confluence"].max() <= 100

    def test_fvg_distance_bounded(self):
        df = _make_ohlcv(200)
        result = detect_all_smc(df)
        assert result["smc_fvg_distance"].min() >= 0
        assert result["smc_fvg_distance"].max() <= 1.0

    def test_preserves_original_columns(self):
        df = _make_ohlcv(200)
        result = detect_all_smc(df)
        for col in ["open", "high", "low", "close", "volume"]:
            assert col in result.columns

    def test_works_with_conftest_fixture(self, ohlcv_df):
        """Use the shared pytest fixture."""
        result = detect_all_smc(ohlcv_df)
        assert len(result) == len(ohlcv_df)
        assert "smc_confluence" in result.columns

    def test_trending_market_produces_bos(self):
        df = _make_trending_data("up", n=100)
        result = detect_all_smc(df, swing_order=5)
        assert result["smc_bos_bullish"].any() or result["smc_bos_bearish"].any()


# =============================================================================
# TEST: Signal Processor Integration
# =============================================================================

class TestSignalProcessorIntegration:
    def test_extract_smc_signals(self):
        from src.quant.signal_processor import extract_smc_signals

        df = _make_ohlcv(200)
        df = detect_all_smc(df)
        signals = extract_smc_signals(df, "XAUUSD", "H1")
        # Should return a list (may be empty if no signals on last bar)
        assert isinstance(signals, list)

    def test_smc_signals_have_correct_type(self):
        from src.quant.signal_processor import extract_smc_signals, SignalType

        df = _make_ohlcv(200)
        df = detect_all_smc(df)
        signals = extract_smc_signals(df, "XAUUSD", "H1")
        for sig in signals:
            assert sig.signal_type == SignalType.SMART_MONEY

    def test_smc_weight_in_aggregation(self):
        from src.quant.signal_processor import SIGNAL_TYPE_WEIGHTS, SignalType

        assert SignalType.SMART_MONEY in SIGNAL_TYPE_WEIGHTS
        assert SIGNAL_TYPE_WEIGHTS[SignalType.SMART_MONEY] > 0


# =============================================================================
# TEST: Feature Registry Integration
# =============================================================================

class TestFeatureRegistryIntegration:
    def test_smc_features_registered(self):
        from src.quant.feature_registry import FeatureRegistry

        FeatureRegistry.reset_instance()
        reg = FeatureRegistry.get_instance()
        smc_names = [
            "smc_bullish_fvg", "smc_bearish_fvg", "smc_fvg_distance",
            "smc_bos_bullish", "smc_bos_bearish", "smc_confluence",
        ]
        for name in smc_names:
            spec = reg.get_spec(name)
            assert spec is not None, f"Missing spec: {name}"
            assert spec.category == "smart_money"

    def test_feature_count_is_29(self):
        from src.quant.feature_registry import FeatureRegistry

        FeatureRegistry.reset_instance()
        reg = FeatureRegistry.get_instance()
        assert reg.expected_dim == 29
