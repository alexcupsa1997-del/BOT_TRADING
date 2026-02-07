# Goliath-Tensor: HFT Feature Engineering Strategy

This document tracks the mathematical definitions and logic for the HFT Feature Engineering module (`analysis/src/quant/hft_features.py`).

## Core Philosophy
We move away from OHLC Time-Bars towards **Event-Driven Tensors**. The Neural Network learns from the *structure* of market liquidity, not just price history.

## 1. Feature Definitions

### A. Order Book Dynamics (The "Pressure" Metrics)
These metrics detect immediate supply/demand imbalances before price moves.

1.  **Order Book Imbalance (OBI):**
    $$ OBI_t = \frac{V_t^{bid} - V_t^{ask}}{V_t^{bid} + V_t^{ask}} $$
    *   *Range:* [-1, 1]
    *   *Meaning:* Positive = Buying Pressure (Bids > Asks). Negative = Selling Pressure.
    *   *Significance:* Highly predictive of immediate short-term direction (next 1-5 ticks).

2.  **Spread Relative Cost:**
    $$ Spread_t = \frac{Ask_t - Bid_t}{MidPrice_t} 	imes 10000 $$
    *   *Meaning:* Cost of liquidity in basis points.
    *   *Significance:* High spread = Low liquidity / High Risk. Networks should learn to avoid trading during spread expansion.

### B. Price Action Vectors (The "Geometry" Metrics)
Geometric representations of price movement independent of absolute price levels.

3.  **Log-Returns (Instantaneous):**
    $$ r_t = \ln(P_t) - \ln(P_{t-1}) $$
    *   *Meaning:* Percentage change, statistically stationary.

4.  **Micro-Volatility (High-Low Vector):**
    Calculated over a rolling window of $N$ ticks (e.g., 50).
    $$ \sigma_t = 	ext{StdDev}(r_{t-N}...r_t) $$

### C. Cross-Channel Interactions (The "Fusion" Metrics)
Derivatives that combine price and volume.

5.  **Volume-Weighted Velocity (VWV):**
    $$ VWV_t = \frac{\Delta P}{\Delta t} 	imes \log(Volume_t) $$
    *   *Meaning:* Speed of price change amplified by volume significance.

6.  **Trade Aggressor Ratio:**
    Ratio of Buy-initiated trades vs Sell-initiated trades in the last $N$ ticks.

## 2. Implementation Rules

-   **NaN Handling:** All rolling windows produce NaNs at the start. These must be dropped or padded with 0 (if semantically correct) before training.
-   **Normalization:** All features must be Z-Scored (StandardScaler) or MinMax Scaled using a *rolling window* to avoid look-ahead bias.
-   **Performance:** Use vectorized Pandas/NumPy operations. Avoid loops.

## 3. Tensor Construction for ML
Final output for the model is a 3D Tensor:
`[Batch_Size, Sequence_Length (64 ticks), Feature_Count (10+)]`
