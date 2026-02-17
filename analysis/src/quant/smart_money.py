"""
Smart Money Concepts (SMC) Module

ICT-based structural analysis for GOLIATH trading system.
Implements:
- Fair Value Gap (FVG) detection (standard, breakaway, inversion)
- Break of Structure (BOS) and Change of Character (CHOCH)
- Swing structure (Higher Highs/Lows, Lower Highs/Lows)
- Liquidity zone detection (equal highs/lows, sweep detection)
- Confluence scoring for high-probability setups
"""

import numpy as np
import pandas as pd
from typing import List, Optional, Tuple, Dict
from dataclasses import dataclass, field
from enum import Enum


# =============================================================================
# ENUMS & DATA STRUCTURES
# =============================================================================

class Bias(Enum):
    BULLISH = 1
    BEARISH = -1
    NEUTRAL = 0


class FVGType(Enum):
    STANDARD = "standard"
    BREAKAWAY = "breakaway"
    INVERSION = "inversion"


class StructureBreakType(Enum):
    BOS = "bos"       # Break of Structure (continuation)
    CHOCH = "choch"   # Change of Character (reversal)


@dataclass
class FairValueGap:
    """A single Fair Value Gap."""
    direction: Bias               # BULLISH or BEARISH
    fvg_type: FVGType
    high: float                   # Upper boundary of gap
    low: float                    # Lower boundary of gap
    midpoint: float               # 50% mitigation level
    candle_index: int             # Index of the middle (impulsive) candle
    timestamp: pd.Timestamp
    size: float                   # Absolute size (high - low)
    size_atr_ratio: float         # Size relative to ATR
    mitigated: bool = False       # Whether price has returned to fill the gap
    mitigation_index: int = -1    # Bar where mitigation occurred


@dataclass
class SwingPoint:
    """A swing high or swing low in market structure."""
    index: int
    price: float
    is_high: bool                 # True = swing high, False = swing low
    timestamp: pd.Timestamp


@dataclass
class StructureBreak:
    """A BOS or CHOCH event."""
    break_type: StructureBreakType
    direction: Bias               # Direction AFTER the break
    price: float                  # Price level that was broken
    index: int                    # Bar where the break occurred
    timestamp: pd.Timestamp
    swing_origin: SwingPoint      # The swing point that was broken


@dataclass
class LiquidityZone:
    """An area of clustered stop-loss orders."""
    price: float
    is_buy_side: bool             # True = above highs (buy stops), False = below lows (sell stops)
    strength: int                 # Number of equal highs/lows forming the pool
    indices: List[int] = field(default_factory=list)
    swept: bool = False
    sweep_index: int = -1


@dataclass
class SMCSetup:
    """A complete Smart Money setup combining multiple confluences."""
    direction: Bias
    fvg: Optional[FairValueGap]
    structure_break: Optional[StructureBreak]
    liquidity_sweep: Optional[LiquidityZone]
    confluence_score: float       # 0-100
    reasoning: List[str] = field(default_factory=list)


# =============================================================================
# SWING STRUCTURE DETECTION
# =============================================================================

def detect_swing_points(
    high: pd.Series,
    low: pd.Series,
    order: int = 5,
) -> List[SwingPoint]:
    """
    Identify swing highs and swing lows.

    A swing high at bar *i* requires ``high[i]`` to be the maximum of
    ``high[i-order : i+order+1]``.  Swing lows mirror this on ``low``.

    Args:
        high: High price series.
        low: Low price series.
        order: Number of bars on each side to confirm the swing.

    Returns:
        Chronologically sorted list of SwingPoint objects.
    """
    swings: List[SwingPoint] = []
    n = len(high)

    for i in range(order, n - order):
        window_high = high.iloc[i - order: i + order + 1]
        window_low = low.iloc[i - order: i + order + 1]

        if high.iloc[i] == window_high.max():
            swings.append(SwingPoint(
                index=i,
                price=high.iloc[i],
                is_high=True,
                timestamp=high.index[i],
            ))
        if low.iloc[i] == window_low.min():
            swings.append(SwingPoint(
                index=i,
                price=low.iloc[i],
                is_high=False,
                timestamp=low.index[i],
            ))

    swings.sort(key=lambda s: s.index)
    return swings


# =============================================================================
# BREAK OF STRUCTURE (BOS) & CHANGE OF CHARACTER (CHOCH)
# =============================================================================

def detect_structure_breaks(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    swing_order: int = 5,
) -> List[StructureBreak]:
    """
    Detect BOS (continuation) and CHOCH (reversal) events.

    Logic:
    - Track the most recent swing high (SH) and swing low (SL).
    - In an uptrend (last break was bullish):
        * Close > previous SH → **BOS bullish** (continuation).
        * Close < previous SL → **CHOCH bearish** (reversal signal).
    - In a downtrend (last break was bearish):
        * Close < previous SL → **BOS bearish** (continuation).
        * Close > previous SH → **CHOCH bullish** (reversal signal).

    Returns:
        Chronological list of StructureBreak events.
    """
    swings = detect_swing_points(high, low, order=swing_order)
    if len(swings) < 2:
        return []

    breaks: List[StructureBreak] = []

    # Initialise with the first swing high and swing low we find
    last_sh: Optional[SwingPoint] = None
    last_sl: Optional[SwingPoint] = None
    current_bias = Bias.NEUTRAL

    for sp in swings:
        if sp.is_high:
            last_sh = sp
        else:
            last_sl = sp

        if last_sh is not None and last_sl is not None:
            break  # We have initial reference points
    else:
        return []

    # Walk through the price series starting after the latest initial swing
    start = max(last_sh.index, last_sl.index) + 1

    for i in range(start, len(close)):
        c = close.iloc[i]

        if last_sh is not None and c > last_sh.price:
            if current_bias == Bias.BEARISH or current_bias == Bias.NEUTRAL:
                btype = StructureBreakType.CHOCH
            else:
                btype = StructureBreakType.BOS

            breaks.append(StructureBreak(
                break_type=btype,
                direction=Bias.BULLISH,
                price=last_sh.price,
                index=i,
                timestamp=close.index[i],
                swing_origin=last_sh,
            ))
            current_bias = Bias.BULLISH
            last_sh = None  # Consumed; wait for the next swing high

        elif last_sl is not None and c < last_sl.price:
            if current_bias == Bias.BULLISH or current_bias == Bias.NEUTRAL:
                btype = StructureBreakType.CHOCH
            else:
                btype = StructureBreakType.BOS

            breaks.append(StructureBreak(
                break_type=btype,
                direction=Bias.BEARISH,
                price=last_sl.price,
                index=i,
                timestamp=close.index[i],
                swing_origin=last_sl,
            ))
            current_bias = Bias.BEARISH
            last_sl = None

        # Update swing references from new swing points discovered at bar *i*
        for sp in swings:
            if sp.index == i:
                if sp.is_high and (last_sh is None or sp.price > last_sh.price):
                    last_sh = sp
                elif not sp.is_high and (last_sl is None or sp.price < last_sl.price):
                    last_sl = sp

    return breaks


# =============================================================================
# FAIR VALUE GAP (FVG) DETECTION
# =============================================================================

def _compute_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """ATR helper (avoids importing from indicators to keep the module self-contained)."""
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(period, min_periods=1).mean()


def detect_fvg(
    open_: pd.Series,
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    min_gap_atr: float = 0.3,
    atr_period: int = 14,
) -> List[FairValueGap]:
    """
    Detect Fair Value Gaps using the 3-candle ICT rule.

    **Bullish FVG:** ``high[i-2] < low[i]``
        → Gap zone = [high[i-2], low[i]]

    **Bearish FVG:** ``low[i-2] > high[i]``
        → Gap zone = [high[i], low[i-2]]

    Args:
        open_: Open prices.
        high: High prices.
        low: Low prices.
        close: Close prices.
        min_gap_atr: Minimum gap size as ATR multiple (filters noise).
        atr_period: ATR look-back.

    Returns:
        List of FairValueGap objects.
    """
    atr = _compute_atr(high, low, close, period=atr_period)
    fvgs: List[FairValueGap] = []

    for i in range(2, len(high)):
        cur_atr = atr.iloc[i]
        if cur_atr == 0 or np.isnan(cur_atr):
            continue

        # --- Bullish FVG ---
        gap_low = high.iloc[i - 2]   # Candle 1 high
        gap_high = low.iloc[i]       # Candle 3 low
        if gap_high > gap_low:
            size = gap_high - gap_low
            if size / cur_atr >= min_gap_atr:
                fvgs.append(FairValueGap(
                    direction=Bias.BULLISH,
                    fvg_type=FVGType.STANDARD,
                    high=gap_high,
                    low=gap_low,
                    midpoint=(gap_high + gap_low) / 2,
                    candle_index=i - 1,
                    timestamp=high.index[i - 1],
                    size=size,
                    size_atr_ratio=size / cur_atr,
                ))

        # --- Bearish FVG ---
        gap_high_b = low.iloc[i - 2]  # Candle 1 low
        gap_low_b = high.iloc[i]      # Candle 3 high
        if gap_high_b > gap_low_b:
            size = gap_high_b - gap_low_b
            if size / cur_atr >= min_gap_atr:
                fvgs.append(FairValueGap(
                    direction=Bias.BEARISH,
                    fvg_type=FVGType.STANDARD,
                    high=gap_high_b,
                    low=gap_low_b,
                    midpoint=(gap_high_b + gap_low_b) / 2,
                    candle_index=i - 1,
                    timestamp=high.index[i - 1],
                    size=size,
                    size_atr_ratio=size / cur_atr,
                ))

    return fvgs


def classify_fvg(
    fvgs: List[FairValueGap],
    structure_breaks: List[StructureBreak],
) -> List[FairValueGap]:
    """
    Upgrade FVG type based on context:
    - **Breakaway FVG**: Forms during a BOS in the same direction.
    - Type remains STANDARD if no BOS coincides.

    Mutates the ``fvg_type`` field in-place and returns the same list.
    """
    if not structure_breaks:
        return fvgs

    bos_indices = {
        sb.index: sb for sb in structure_breaks
        if sb.break_type == StructureBreakType.BOS
    }

    for fvg in fvgs:
        # Check if BOS happened within ±1 bar of the FVG middle candle
        for offset in (-1, 0, 1):
            sb = bos_indices.get(fvg.candle_index + offset)
            if sb is not None:
                same_dir = (
                    (fvg.direction == Bias.BULLISH and sb.direction == Bias.BULLISH) or
                    (fvg.direction == Bias.BEARISH and sb.direction == Bias.BEARISH)
                )
                if same_dir:
                    fvg.fvg_type = FVGType.BREAKAWAY
                    break

    return fvgs


def check_fvg_mitigation(
    fvgs: List[FairValueGap],
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
) -> List[FairValueGap]:
    """
    Mark FVGs as mitigated when price returns into the gap.

    - Bullish FVG is mitigated when a subsequent candle's low <= gap midpoint.
    - Bearish FVG is mitigated when a subsequent candle's high >= gap midpoint.

    Also detects **Inversion FVGs**: a mitigated gap where price then closes
    on the opposite side, turning it into a zone of the other polarity.
    """
    for fvg in fvgs:
        if fvg.mitigated:
            continue

        start = fvg.candle_index + 2  # Skip the 3-candle formation window
        for i in range(start, len(close)):
            if fvg.direction == Bias.BULLISH:
                if low.iloc[i] <= fvg.midpoint:
                    fvg.mitigated = True
                    fvg.mitigation_index = i
                    # Inversion: if close below the gap entirely
                    if close.iloc[i] < fvg.low:
                        fvg.fvg_type = FVGType.INVERSION
                        fvg.direction = Bias.BEARISH
                    break
            else:  # BEARISH
                if high.iloc[i] >= fvg.midpoint:
                    fvg.mitigated = True
                    fvg.mitigation_index = i
                    if close.iloc[i] > fvg.high:
                        fvg.fvg_type = FVGType.INVERSION
                        fvg.direction = Bias.BULLISH
                    break

    return fvgs


# =============================================================================
# LIQUIDITY ZONE DETECTION
# =============================================================================

def detect_liquidity_zones(
    high: pd.Series,
    low: pd.Series,
    tolerance_pct: float = 0.001,
    min_touches: int = 2,
    lookback: int = 100,
) -> List[LiquidityZone]:
    """
    Find clusters of equal highs/lows that form liquidity pools.

    Buy-side liquidity sits above equal highs (clusters of similar swing highs).
    Sell-side liquidity sits below equal lows (clusters of similar swing lows).

    Args:
        high: High prices.
        low: Low prices.
        tolerance_pct: Maximum relative price difference to consider levels "equal".
        min_touches: Minimum repeated touches to qualify as a pool.
        lookback: Number of recent bars to analyse.

    Returns:
        List of LiquidityZone objects.
    """
    zones: List[LiquidityZone] = []
    n = len(high)
    start = max(0, n - lookback)

    # --- Buy-side (equal highs) ---
    highs = [(i, high.iloc[i]) for i in range(start, n)]
    zones.extend(_cluster_levels(highs, tolerance_pct, min_touches, is_buy_side=True))

    # --- Sell-side (equal lows) ---
    lows = [(i, low.iloc[i]) for i in range(start, n)]
    zones.extend(_cluster_levels(lows, tolerance_pct, min_touches, is_buy_side=False))

    return zones


def _cluster_levels(
    index_price_pairs: List[Tuple[int, float]],
    tolerance_pct: float,
    min_touches: int,
    is_buy_side: bool,
) -> List[LiquidityZone]:
    """Group price levels within *tolerance_pct* and return qualifying pools."""
    if not index_price_pairs:
        return []

    sorted_pairs = sorted(index_price_pairs, key=lambda p: p[1])
    clusters: List[List[Tuple[int, float]]] = []
    current: List[Tuple[int, float]] = [sorted_pairs[0]]

    for idx, price in sorted_pairs[1:]:
        ref_price = current[0][1]
        if ref_price == 0:
            current.append((idx, price))
            continue
        if abs(price - ref_price) / abs(ref_price) <= tolerance_pct:
            current.append((idx, price))
        else:
            clusters.append(current)
            current = [(idx, price)]
    clusters.append(current)

    zones: List[LiquidityZone] = []
    for cluster in clusters:
        if len(cluster) >= min_touches:
            avg_price = np.mean([p for _, p in cluster])
            indices = [i for i, _ in cluster]
            zones.append(LiquidityZone(
                price=float(avg_price),
                is_buy_side=is_buy_side,
                strength=len(cluster),
                indices=indices,
            ))

    return zones


def detect_liquidity_sweeps(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    liquidity_zones: List[LiquidityZone],
) -> List[LiquidityZone]:
    """
    Detect sweeps: price pierces through a liquidity zone but closes back.

    - Buy-side sweep: high > zone price but close < zone price (rejection).
    - Sell-side sweep: low < zone price but close > zone price (rejection).

    Mutates ``swept`` and ``sweep_index`` in-place.
    """
    for zone in liquidity_zones:
        if zone.swept:
            continue

        last_zone_bar = max(zone.indices) if zone.indices else 0
        for i in range(last_zone_bar + 1, len(close)):
            if zone.is_buy_side:
                if high.iloc[i] > zone.price and close.iloc[i] < zone.price:
                    zone.swept = True
                    zone.sweep_index = i
                    break
            else:
                if low.iloc[i] < zone.price and close.iloc[i] > zone.price:
                    zone.swept = True
                    zone.sweep_index = i
                    break

    return liquidity_zones


# =============================================================================
# CONFLUENCE SCORING (A+ SETUP DETECTION)
# =============================================================================

def score_smc_setup(
    fvg: Optional[FairValueGap],
    structure_break: Optional[StructureBreak],
    liquidity_sweep: Optional[LiquidityZone],
    htf_bias: Bias = Bias.NEUTRAL,
) -> SMCSetup:
    """
    Score a Smart Money setup based on confluence of factors.

    Scoring (max 100):
        +30  FVG present and unmitigated
        +10  Breakaway FVG bonus
        +25  BOS in same direction
        +25  Liquidity sweep in setup direction
        +10  HTF bias alignment

    Returns:
        SMCSetup with confluence_score and reasoning list.
    """
    score = 0.0
    reasoning: List[str] = []

    # Determine setup direction
    direction = Bias.NEUTRAL
    if fvg is not None:
        direction = fvg.direction
    elif structure_break is not None:
        direction = structure_break.direction

    # --- FVG contribution ---
    if fvg is not None and not fvg.mitigated:
        score += 30
        reasoning.append(f"{fvg.direction.name} FVG ({fvg.fvg_type.value}) at {fvg.low:.5f}-{fvg.high:.5f}")
        if fvg.fvg_type == FVGType.BREAKAWAY:
            score += 10
            reasoning.append("Breakaway FVG (formed with BOS)")
    elif fvg is not None and fvg.mitigated:
        score += 10
        reasoning.append("FVG already mitigated (reduced weight)")

    # --- Structure break contribution ---
    if structure_break is not None:
        same_dir = structure_break.direction == direction
        if structure_break.break_type == StructureBreakType.BOS and same_dir:
            score += 25
            reasoning.append(f"BOS {structure_break.direction.name} at {structure_break.price:.5f}")
        elif structure_break.break_type == StructureBreakType.CHOCH:
            score += 15
            reasoning.append(f"CHOCH {structure_break.direction.name} (early reversal signal)")

    # --- Liquidity sweep contribution ---
    if liquidity_sweep is not None and liquidity_sweep.swept:
        sweep_dir = Bias.BEARISH if liquidity_sweep.is_buy_side else Bias.BULLISH
        if sweep_dir == direction:
            score += 25
            side = "buy-side" if liquidity_sweep.is_buy_side else "sell-side"
            reasoning.append(f"Liquidity sweep of {side} at {liquidity_sweep.price:.5f}")

    # --- HTF alignment ---
    if htf_bias != Bias.NEUTRAL and htf_bias == direction:
        score += 10
        reasoning.append("Aligned with HTF bias")

    return SMCSetup(
        direction=direction,
        fvg=fvg,
        structure_break=structure_break,
        liquidity_sweep=liquidity_sweep,
        confluence_score=min(100, score),
        reasoning=reasoning,
    )


# =============================================================================
# COLUMN-BASED DETECTION (DataFrame integration)
# =============================================================================

def detect_all_smc(
    df: pd.DataFrame,
    swing_order: int = 5,
    min_gap_atr: float = 0.3,
    liquidity_lookback: int = 100,
) -> pd.DataFrame:
    """
    Run the full SMC analysis and add boolean/scalar columns to the DataFrame.

    Columns added:
        smc_bullish_fvg      : bool — active (unmitigated) bullish FVG at this bar
        smc_bearish_fvg      : bool — active (unmitigated) bearish FVG at this bar
        smc_fvg_distance     : float — normalised distance to nearest active FVG (0-1)
        smc_bos_bullish      : bool — bullish BOS on this bar
        smc_bos_bearish      : bool — bearish BOS on this bar
        smc_choch_bullish    : bool — bullish CHOCH on this bar
        smc_choch_bearish    : bool — bearish CHOCH on this bar
        smc_liquidity_sweep  : bool — liquidity sweep detected on this bar
        smc_confluence        : float — confluence score (0-100) for any setup at this bar

    Args:
        df: OHLCV DataFrame.
        swing_order: Bars on each side for swing detection.
        min_gap_atr: Minimum FVG size in ATR multiples.
        liquidity_lookback: Bars for liquidity zone detection.

    Returns:
        DataFrame with SMC columns appended.
    """
    result = df.copy()
    o, h, l, c = df["open"], df["high"], df["low"], df["close"]
    n = len(df)

    # 1. FVG detection
    fvgs = detect_fvg(o, h, l, c, min_gap_atr=min_gap_atr)
    fvgs = check_fvg_mitigation(fvgs, h, l, c)

    bull_fvg = pd.Series(False, index=df.index)
    bear_fvg = pd.Series(False, index=df.index)
    fvg_dist = pd.Series(1.0, index=df.index)

    atr = _compute_atr(h, l, c)

    for fvg in fvgs:
        # Mark the formation bar
        idx = fvg.candle_index
        if 0 <= idx < n:
            if fvg.direction == Bias.BULLISH and not fvg.mitigated:
                bull_fvg.iloc[idx] = True
            elif fvg.direction == Bias.BEARISH and not fvg.mitigated:
                bear_fvg.iloc[idx] = True

        # Compute distance to FVG for bars after formation
        end = fvg.mitigation_index if fvg.mitigated else n
        for j in range(idx + 1, min(end, n)):
            price = c.iloc[j]
            cur_atr = atr.iloc[j]
            if cur_atr > 0:
                dist = min(abs(price - fvg.high), abs(price - fvg.low)) / cur_atr
                fvg_dist.iloc[j] = min(fvg_dist.iloc[j], dist)

    # Clamp distance to [0, 1]
    fvg_dist = fvg_dist.clip(0, 1)

    result["smc_bullish_fvg"] = bull_fvg
    result["smc_bearish_fvg"] = bear_fvg
    result["smc_fvg_distance"] = fvg_dist

    # 2. Structure breaks
    breaks = detect_structure_breaks(h, l, c, swing_order=swing_order)

    # Classify FVGs as breakaway where applicable
    classify_fvg(fvgs, breaks)

    bos_bull = pd.Series(False, index=df.index)
    bos_bear = pd.Series(False, index=df.index)
    choch_bull = pd.Series(False, index=df.index)
    choch_bear = pd.Series(False, index=df.index)

    for sb in breaks:
        if 0 <= sb.index < n:
            if sb.break_type == StructureBreakType.BOS:
                if sb.direction == Bias.BULLISH:
                    bos_bull.iloc[sb.index] = True
                else:
                    bos_bear.iloc[sb.index] = True
            else:
                if sb.direction == Bias.BULLISH:
                    choch_bull.iloc[sb.index] = True
                else:
                    choch_bear.iloc[sb.index] = True

    result["smc_bos_bullish"] = bos_bull
    result["smc_bos_bearish"] = bos_bear
    result["smc_choch_bullish"] = choch_bull
    result["smc_choch_bearish"] = choch_bear

    # 3. Liquidity zones & sweeps
    liq_zones = detect_liquidity_zones(h, l, lookback=liquidity_lookback)
    detect_liquidity_sweeps(h, l, c, liq_zones)

    sweep_col = pd.Series(False, index=df.index)
    for zone in liq_zones:
        if zone.swept and 0 <= zone.sweep_index < n:
            sweep_col.iloc[zone.sweep_index] = True

    result["smc_liquidity_sweep"] = sweep_col

    # 4. Confluence score per bar
    confluence = pd.Series(0.0, index=df.index)

    # Build lookup dicts for fast access
    break_by_idx = {}
    for sb in breaks:
        break_by_idx[sb.index] = sb

    sweep_zones_by_idx: Dict[int, LiquidityZone] = {}
    for zone in liq_zones:
        if zone.swept:
            sweep_zones_by_idx[zone.sweep_index] = zone

    active_fvgs: List[FairValueGap] = []
    for i in range(n):
        # Add FVGs that just formed
        for fvg in fvgs:
            if fvg.candle_index == i - 1:
                active_fvgs.append(fvg)

        # Remove mitigated FVGs
        active_fvgs = [f for f in active_fvgs if not f.mitigated or f.mitigation_index > i]

        # Find best setup at this bar
        best_score = 0.0
        for fvg in active_fvgs:
            sb = break_by_idx.get(i)
            liq = sweep_zones_by_idx.get(i)
            setup = score_smc_setup(fvg, sb, liq)
            if setup.confluence_score > best_score:
                best_score = setup.confluence_score

        # Even without an FVG, a BOS+sweep can form a partial setup
        if i in break_by_idx or i in sweep_zones_by_idx:
            sb = break_by_idx.get(i)
            liq = sweep_zones_by_idx.get(i)
            setup = score_smc_setup(None, sb, liq)
            if setup.confluence_score > best_score:
                best_score = setup.confluence_score

        confluence.iloc[i] = best_score

    result["smc_confluence"] = confluence

    return result
