#!/usr/bin/env python3
"""
GOLIATH Bot Test Suite
======================
Test all Phase 4 modules with EURUSD simulation.

Tests:
1. Indicator Library (100+ indicators)
2. Risk Manager (position sizing)
3. Neural Trader (predictions)
4. Complete trading simulation
"""

import numpy as np
import sys
from datetime import datetime

# Add path
import os
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from analysis.src.quant import (
    # Indicator Library
    IndicatorAggregator, IndicatorConfig, MomentumIndicators,
    TrendIndicators, VolatilityIndicators, VolumeIndicators,
    # Risk Manager
    RiskConfig, RiskCalculator, ATRStopLoss, BudgetOptimizer,
    # Neural Trader
    NeuralTrader, NeuralTraderConfig, IndicatorScaler
)


def print_header(title: str):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def generate_eurusd_data(n_candles: int = 200) -> dict:
    """Generate synthetic EURUSD data for testing."""
    np.random.seed(42)
    
    # Start price around 1.0850
    base_price = 1.0850
    
    # Random walk with trend
    returns = np.random.randn(n_candles) * 0.0005  # 5 pips std dev
    close = base_price + np.cumsum(returns)
    
    # Generate OHLC
    high = close + np.abs(np.random.randn(n_candles) * 0.0003)
    low = close - np.abs(np.random.randn(n_candles) * 0.0003)
    open_ = np.roll(close, 1)
    open_[0] = base_price
    
    # Volume
    volume = np.random.randint(100, 1000, n_candles).astype(float)
    
    return {
        'open': open_,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume
    }


def test_indicator_library():
    """Test all 100+ indicators."""
    print_header("TEST 1: INDICATOR LIBRARY (100+ Indicators)")
    
    data = generate_eurusd_data()
    
    # Test Momentum Indicators
    print("\n📊 Momentum Indicators:")
    mom = MomentumIndicators()
    
    rsi, rsi_sig = mom.rsi(data['close'], 14)
    print(f"  RSI(14): {rsi[-1]:.2f} | Signal: {rsi_sig[-1]:.3f}")
    
    k, d, stoch_sig = mom.stochastic(data['high'], data['low'], data['close'])
    print(f"  Stochastic: K={k[-1]:.2f} D={d[-1]:.2f} | Signal: {stoch_sig[-1]:.3f}")
    
    macd_line, signal_line, hist, macd_sig = mom.macd(data['close'])
    print(f"  MACD: Line={macd_line[-1]:.5f} | Signal: {macd_sig[-1]:.3f}")
    
    # Test Trend Indicators
    print("\n📈 Trend Indicators:")
    trend = TrendIndicators()
    
    adx, plus_di, minus_di, adx_sig = trend.adx(data['high'], data['low'], data['close'])
    print(f"  ADX: {adx[-1]:.2f} | +DI: {plus_di[-1]:.2f} | -DI: {minus_di[-1]:.2f}")
    
    sar, sar_sig = trend.parabolic_sar(data['high'], data['low'], data['close'])
    print(f"  SAR: {sar[-1]:.5f} | Signal: {sar_sig[-1]:.0f}")
    
    st, st_sig = trend.supertrend(data['high'], data['low'], data['close'])
    print(f"  Supertrend: {st[-1]:.5f} | Direction: {st_sig[-1]:.0f}")
    
    # Test Volatility Indicators
    print("\n📉 Volatility Indicators:")
    vol = VolatilityIndicators()
    
    atr_val, atr_pct = vol.atr(data['high'], data['low'], data['close'])
    print(f"  ATR(14): {atr_val[-1]:.5f} ({atr_pct[-1]:.2f}%)")
    
    bb = vol.bollinger_bands(data['close'])
    print(f"  Bollinger: Upper={bb['upper'][-1]:.5f} Lower={bb['lower'][-1]:.5f}")
    print(f"  BB %B: {bb['percent_b'][-1]:.3f} | Signal: {bb['signal'][-1]:.3f}")
    
    # Test Volume Indicators
    print("\n📊 Volume Indicators:")
    volume = VolumeIndicators()
    
    obv, obv_sig = volume.obv(data['close'], data['volume'])
    print(f"  OBV: {obv[-1]:.0f} | Signal: {obv_sig[-1]:.3f}")
    
    mfi, mfi_sig = volume.mfi(data['high'], data['low'], data['close'], data['volume'])
    print(f"  MFI: {mfi[-1]:.2f} | Signal: {mfi_sig[-1]:.3f}")
    
    # Aggregator
    print("\n🔄 Indicator Aggregator:")
    agg = IndicatorAggregator()
    features = agg.compute_all(data['high'], data['low'], data['close'], data['volume'])
    direction, confidence = agg.get_consensus_signal(features)
    
    print(f"  Total features computed: {len(features)}")
    print(f"  Consensus: Direction={direction:.3f} Confidence={confidence:.1%}")
    
    return True


def test_risk_manager():
    """Test risk management calculations."""
    print_header("TEST 2: RISK MANAGER (100€ Demo, 1% Risk)")
    
    config = RiskConfig(
        initial_balance=100.0,
        risk_per_trade=0.01,
        symbol="EURUSD"
    )
    
    calc = RiskCalculator(config)
    
    # Test position sizing
    print("\n💰 Position Sizing:")
    entry = 1.0850
    sl = 1.0800  # 50 pips SL
    
    pos = calc.calculate_position_size(entry, sl)
    print(f"  Entry: {entry} | SL: {sl}")
    print(f"  SL Distance: {pos['sl_pips']:.1f} pips")
    print(f"  Position Size: {pos['lot_size']} lots")
    print(f"  Risk Amount: €{pos['risk_amount']:.2f} ({pos['risk_percent']:.1f}%)")
    
    # Test TP calculation
    print("\n🎯 Take Profit (R:R = 2:1):")
    tp_data = calc.calculate_take_profit(entry, sl, rr_ratio=2.0, direction='BUY')
    print(f"  TP: {tp_data['take_profit']:.5f}")
    print(f"  TP Distance: {tp_data['tp_pips']:.1f} pips")
    print(f"  R:R Ratio: 1:{tp_data['rr_ratio']:.1f}")
    
    # Test ATR-based SL
    print("\n📏 ATR-Based Dynamic SL:")
    data = generate_eurusd_data()
    atr_val = ATRStopLoss.calculate_atr(data['high'], data['low'], data['close'])[-1]
    
    dynamic_sl = ATRStopLoss.get_dynamic_sl(entry, atr_val, 'BUY', multiplier=1.5)
    dynamic_tp = ATRStopLoss.get_dynamic_tp(entry, dynamic_sl, rr_ratio=2.0, direction='BUY')
    
    print(f"  ATR Value: {atr_val:.5f}")
    print(f"  Dynamic SL: {dynamic_sl:.5f}")
    print(f"  Dynamic TP: {dynamic_tp:.5f}")
    
    # Test trade validation
    print("\n✅ Trade Validation:")
    can_trade, reason = calc.can_open_trade()
    print(f"  Can open trade: {can_trade} - {reason}")
    
    valid, msg = calc.validate_trade(entry, dynamic_sl, dynamic_tp, 'BUY')
    print(f"  Trade valid: {valid} - {msg}")
    
    # Risk metrics
    print("\n📊 Risk Metrics:")
    metrics = calc.get_risk_metrics()
    for key, val in metrics.items():
        print(f"  {key}: {val}")
    
    return True


def test_neural_trader():
    """Test neural network predictions."""
    print_header("TEST 3: NEURAL TRADER (Risk-Aware NN)")
    
    config = NeuralTraderConfig(
        input_features=100,
        lstm_units=128,
        dense_units=64
    )
    
    trader = NeuralTrader(config)
    
    # Test with random features
    print("\n🧠 Model Architecture:")
    print(f"  Input Features: {config.input_features}")
    print(f"  LSTM Units: {config.lstm_units}")
    print(f"  Dense Units: {config.dense_units}")
    
    # Generate indicator features
    print("\n📊 Generating Indicator Features...")
    data = generate_eurusd_data()
    agg = IndicatorAggregator()
    features = agg.compute_all(data['high'], data['low'], data['close'], data['volume'])
    
    print(f"  Computed {len(features)} indicators")
    
    # Convert to array
    feature_array = np.array(list(features.values()))
    
    # Pad to 100 features
    if len(feature_array) < 100:
        feature_array = np.pad(feature_array, (0, 100 - len(feature_array)))
    
    # Make prediction
    print("\n🔮 Neural Network Prediction:")
    prediction = trader.forward(feature_array.reshape(1, -1))
    
    print(f"  Direction: {prediction['direction'].name}")
    print(f"  Direction Value: {prediction['direction_value']:.3f}")
    print(f"  Confidence: {prediction['confidence']:.1f}%")
    print(f"  Stop Loss: {prediction['stop_loss_pips']:.1f} pips")
    print(f"  Take Profit: {prediction['take_profit_pips']:.1f} pips")
    print(f"  Position Size: {prediction['position_size']} lots")
    print(f"  R:R Ratio: 1:{prediction['rr_ratio']:.2f}")
    
    # Test indicator importance
    print("\n📈 Indicator Importance:")
    indicator_names = list(features.keys())[:10]  # Top 10
    importance = trader.compute_indicator_importance(
        feature_array.reshape(1, -1), 
        indicator_names
    )
    
    sorted_imp = sorted(importance.items(), key=lambda x: x[1], reverse=True)[:5]
    for name, imp in sorted_imp:
        print(f"  {name}: {imp:.1f}%")
    
    return True


def test_complete_simulation():
    """Test complete trading simulation."""
    print_header("TEST 4: COMPLETE TRADING SIMULATION")
    
    print("\n🎮 Simulation Configuration:")
    print("  Asset: EURUSD")
    print("  Balance: €100 (demo)")
    print("  Risk: 1% per trade")
    print("  Duration: 5s - 8h")
    
    # Initialize components
    risk_calc = RiskCalculator(RiskConfig(initial_balance=100.0, risk_per_trade=0.01))
    neural = NeuralTrader()
    budget_opt = BudgetOptimizer(initial_balance=100.0, risk_pct=0.01)
    
    # Generate data
    data = generate_eurusd_data(500)
    agg = IndicatorAggregator()
    
    print("\n📊 Running Simulation (10 trades)...")
    
    trades = []
    for i in range(10):
        # Get features at this point
        idx = 200 + i * 20
        features = agg.compute_all(
            data['high'][idx-100:idx],
            data['low'][idx-100:idx],
            data['close'][idx-100:idx],
            data['volume'][idx-100:idx]
        )
        
        # Neural prediction
        feature_array = np.array(list(features.values()))
        if len(feature_array) < 100:
            feature_array = np.pad(feature_array, (0, 100 - len(feature_array)))
        
        pred = neural.forward(feature_array.reshape(1, -1))
        
        # Skip HOLD signals
        if pred['direction'].value == 0:
            continue
        
        # Calculate position
        entry = data['close'][idx]
        direction = 'BUY' if pred['direction'].value == 1 else 'SELL'
        
        if direction == 'BUY':
            sl = entry - pred['stop_loss_pips'] * 0.0001
            tp = entry + pred['take_profit_pips'] * 0.0001
        else:
            sl = entry + pred['stop_loss_pips'] * 0.0001
            tp = entry - pred['take_profit_pips'] * 0.0001
        
        pos = risk_calc.calculate_position_size(entry, sl)
        
        # Simulate outcome (random for demo)
        win = np.random.random() > 0.4  # 60% win rate simulation
        if win:
            pnl = pred['take_profit_pips'] * 0.10 * pos['lot_size']  # Simplified
        else:
            pnl = -pred['stop_loss_pips'] * 0.10 * pos['lot_size']
        
        risk_calc.update_balance(pnl)
        budget_opt.update_stats(pnl)
        
        trades.append({
            'entry': entry,
            'direction': direction,
            'sl_pips': pred['stop_loss_pips'],
            'tp_pips': pred['take_profit_pips'],
            'lot_size': pos['lot_size'],
            'pnl': pnl,
            'result': 'WIN' if win else 'LOSS'
        })
        
        print(f"  Trade {len(trades)}: {direction} @ {entry:.5f} | "
              f"SL: {pred['stop_loss_pips']:.0f} TP: {pred['take_profit_pips']:.0f} | "
              f"{trades[-1]['result']} €{pnl:.2f}")
    
    # Final results
    print("\n📊 Simulation Results:")
    metrics = risk_calc.get_risk_metrics()
    print(f"  Initial Balance: €{metrics['initial_balance']:.2f}")
    print(f"  Final Balance: €{metrics['current_balance']:.2f}")
    print(f"  P&L: €{metrics['current_balance'] - metrics['initial_balance']:.2f}")
    print(f"  Drawdown: {metrics['drawdown_pct']:.1f}%")
    
    rec_risk = budget_opt.get_recommended_risk(metrics['current_balance'])
    print(f"\n  Win Rate: {rec_risk['win_rate']:.1f}%")
    print(f"  Recommended Risk: {rec_risk['risk_percent']:.2f}%")
    print(f"  Method: {rec_risk['method']}")
    
    return True


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("  🤖 GOLIATH NEURAL TRADING BOT - TEST SUITE")
    print("=" * 60)
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("  Asset: EURUSD | Budget: €100 | Risk: 1%")
    
    tests = [
        ("Indicator Library", test_indicator_library),
        ("Risk Manager", test_risk_manager),
        ("Neural Trader", test_neural_trader),
        ("Complete Simulation", test_complete_simulation),
    ]
    
    results = []
    for name, test_fn in tests:
        try:
            success = test_fn()
            results.append((name, success))
        except Exception as e:
            print(f"\n❌ Error in {name}: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    print_header("TEST RESULTS SUMMARY")
    
    for name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"  {status} - {name}")
    
    passed = sum(1 for _, s in results if s)
    print(f"\n  Total: {passed}/{len(results)} tests passed")
    
    print("\n" + "=" * 60)
    print("  Test suite complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
