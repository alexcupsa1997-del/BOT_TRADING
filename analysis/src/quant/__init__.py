from .engines import OptionType, BlackScholesMerton, MonteCarlo, CrankNicolson
from .indicators import (
    ema, sma, macd, adx, rsi, stochastic, cci, atr, bollinger_bands,
    compute_all_indicators, resample_ohlcv
)
from .patterns import detect_all_patterns, detect_support_resistance
from .features import (
    fractional_differencing, triple_barrier_labels,
    compute_rolling_volatility, compute_rolling_sharpe
)
from .channels import (
    detect_channel, detect_channels_mtf, get_channel_confluence,
    detect_wedge, detect_triangle, Channel, ChannelBreakout
)
from .signal_processor import (
    Signal, AggregatedSignal, SignalType, SignalDirection,
    extract_indicator_signals, extract_pattern_signals,
    aggregate_signals, process_all_symbols, get_top_opportunities
)
from .indicator_optimizer import (
    OptimizedParams, optimize_rsi, optimize_macd, optimize_bollinger,
    optimize_for_symbol, normalize_indicator_scale
)
from .neural_decision import (
    TradeDecision, TradeAction, FeatureVector,
    generate_decision, process_decisions, get_best_entries
)

# Phase 4: Neural Trading System
from .indicator_library import (
    IndicatorConfig, CONFIG, SignalStrength,
    MomentumIndicators, TrendIndicators, VolatilityIndicators,
    VolumeIndicators, SupportResistanceIndicators, IndicatorAggregator
)
from .risk_manager import (
    RiskConfig, RiskCalculator, ATRStopLoss,
    TradeDurationManager, BudgetOptimizer
)
from .neural_trader import (
    NeuralTraderConfig, TradeDirection, IndicatorScaler,
    NeuralTrader, TrainingPipeline
)


