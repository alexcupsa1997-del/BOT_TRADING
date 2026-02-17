#!/usr/bin/env python3
"""
GOLIATH Risk Manager v1.0
=========================
Position sizing, risk management, and budget optimization.

Configuration:
- Balance: 100€ (demo)
- Risk per trade: 1%
- Trade duration: 5 seconds to 8 hours
- Asset: EURUSD
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum
from datetime import datetime, timedelta


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class RiskConfig:
    """Risk management configuration - all values configurable."""
    
    # Account
    initial_balance: float = 100.0      # Demo account (€)
    currency: str = "EUR"
    
    # Risk Limits
    risk_per_trade: float = 0.01        # 1% per trade
    max_daily_risk: float = 0.05        # 5% max daily loss
    max_drawdown: float = 0.10          # 10% max total drawdown
    max_concurrent_positions: int = 3
    
    # Trade Parameters
    min_rr_ratio: float = 2.0           # Minimum Risk:Reward = 1:2
    min_trade_duration: int = 5         # 5 seconds minimum
    max_trade_duration: int = 28800     # 8 hours = 28800 seconds
    
    # Position Sizing
    use_kelly_criterion: bool = False   # Conservative: fixed %
    max_position_pct: float = 0.10      # Max 10% of balance per position
    
    # Asset Configuration
    symbol: str = "EURUSD"
    pip_value: float = 0.0001           # Standard forex pip
    pip_value_per_lot: float = 10.0     # €10 per pip per standard lot
    min_lot: float = 0.01               # Micro lot
    max_lot: float = 1.0
    lot_step: float = 0.01


# =============================================================================
# RISK CALCULATOR
# =============================================================================

class RiskCalculator:
    """Calculate position sizes and risk metrics."""
    
    def __init__(self, config: RiskConfig = None):
        self.config = config or RiskConfig()
        self.current_balance = self.config.initial_balance
        self.daily_pnl = 0.0
        self.open_positions: List[Dict] = []
        self.trade_history: List[Dict] = []
        self.peak_balance = self.config.initial_balance
    
    def calculate_position_size(
        self,
        entry_price: float,
        stop_loss_price: float,
        account_balance: float = None
    ) -> Dict:
        """
        Calculate optimal position size based on risk parameters.
        
        Formula: Position Size = (Balance × Risk%) / (SL_distance × Pip_value)
        
        Returns:
            Dict with lot_size, risk_amount, potential_loss, etc.
        """
        balance = account_balance or self.current_balance
        
        # Calculate SL distance in pips
        sl_distance_price = abs(entry_price - stop_loss_price)
        sl_distance_pips = sl_distance_price / self.config.pip_value
        
        # Risk amount in base currency
        risk_amount = balance * self.config.risk_per_trade
        
        # Position size calculation
        # risk_amount = sl_pips × pip_value_per_lot × lot_size
        # lot_size = risk_amount / (sl_pips × pip_value_per_lot)
        
        if sl_distance_pips <= 0:
            return {'error': 'Invalid SL distance'}
        
        lot_size = risk_amount / (sl_distance_pips * self.config.pip_value_per_lot)
        
        # Apply limits
        lot_size = max(self.config.min_lot, lot_size)
        lot_size = min(self.config.max_lot, lot_size)
        
        # Round to lot step
        lot_size = round(lot_size / self.config.lot_step) * self.config.lot_step
        
        # Recalculate actual risk with adjusted lot size
        actual_risk = sl_distance_pips * self.config.pip_value_per_lot * lot_size
        actual_risk_pct = actual_risk / balance
        
        return {
            'lot_size': lot_size,
            'sl_pips': sl_distance_pips,
            'risk_amount': actual_risk,
            'risk_percent': actual_risk_pct * 100,
            'balance': balance,
            'entry_price': entry_price,
            'stop_loss': stop_loss_price
        }
    
    def calculate_take_profit(
        self,
        entry_price: float,
        stop_loss_price: float,
        rr_ratio: float = None,
        direction: str = 'BUY'
    ) -> Dict:
        """
        Calculate Take Profit based on Risk:Reward ratio.
        
        Args:
            entry_price: Entry price
            stop_loss_price: Stop loss price
            rr_ratio: Risk:Reward ratio (default: min_rr_ratio from config)
            direction: 'BUY' or 'SELL'
        """
        rr = rr_ratio or self.config.min_rr_ratio
        sl_distance = abs(entry_price - stop_loss_price)
        tp_distance = sl_distance * rr
        
        if direction.upper() == 'BUY':
            take_profit = entry_price + tp_distance
        else:
            take_profit = entry_price - tp_distance
        
        return {
            'take_profit': take_profit,
            'tp_pips': tp_distance / self.config.pip_value,
            'sl_pips': sl_distance / self.config.pip_value,
            'rr_ratio': rr,
            'expected_profit': tp_distance,
            'expected_loss': sl_distance
        }
    
    def can_open_trade(self) -> Tuple[bool, str]:
        """
        Check if a new trade can be opened based on risk limits.
        
        Returns:
            (allowed: bool, reason: str)
        """
        # Check concurrent positions
        if len(self.open_positions) >= self.config.max_concurrent_positions:
            return False, f"Max {self.config.max_concurrent_positions} positions reached"
        
        # Check daily loss limit
        if abs(self.daily_pnl) >= self.current_balance * self.config.max_daily_risk:
            return False, f"Daily loss limit ({self.config.max_daily_risk*100}%) reached"
        
        # Check max drawdown
        drawdown = (self.peak_balance - self.current_balance) / self.peak_balance
        if drawdown >= self.config.max_drawdown:
            return False, f"Max drawdown ({self.config.max_drawdown*100}%) reached"
        
        return True, "Trade allowed"
    
    def validate_trade(
        self,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        direction: str
    ) -> Tuple[bool, str]:
        """
        Validate trade parameters.
        """
        # Direction validation
        if direction.upper() == 'BUY':
            if stop_loss >= entry_price:
                return False, "BUY: SL must be below entry"
            if take_profit <= entry_price:
                return False, "BUY: TP must be above entry"
        else:
            if stop_loss <= entry_price:
                return False, "SELL: SL must be above entry"
            if take_profit >= entry_price:
                return False, "SELL: TP must be below entry"
        
        # R:R ratio check
        sl_dist = abs(entry_price - stop_loss)
        tp_dist = abs(entry_price - take_profit)
        rr_ratio = tp_dist / (sl_dist + 1e-10)
        
        if rr_ratio < self.config.min_rr_ratio:
            return False, f"R:R ratio {rr_ratio:.2f} below minimum {self.config.min_rr_ratio}"
        
        return True, "Trade valid"
    
    def update_balance(self, pnl: float):
        """Update balance after a trade closes."""
        self.current_balance += pnl
        self.daily_pnl += pnl
        
        if self.current_balance > self.peak_balance:
            self.peak_balance = self.current_balance
    
    def get_risk_metrics(self) -> Dict:
        """Get current risk metrics."""
        drawdown = (self.peak_balance - self.current_balance) / self.peak_balance if self.peak_balance > 0 else 0
        
        return {
            'current_balance': self.current_balance,
            'initial_balance': self.config.initial_balance,
            'peak_balance': self.peak_balance,
            'drawdown_pct': drawdown * 100,
            'daily_pnl': self.daily_pnl,
            'daily_pnl_pct': (self.daily_pnl / self.config.initial_balance) * 100,
            'open_positions': len(self.open_positions),
            'max_positions': self.config.max_concurrent_positions,
            'risk_per_trade': self.config.risk_per_trade * 100,
            'can_trade': self.can_open_trade()[0]
        }


# =============================================================================
# ATR-BASED STOP LOSS CALCULATOR
# =============================================================================

class ATRStopLoss:
    """Dynamic stop loss based on ATR volatility."""
    
    @staticmethod
    def calculate_atr(high: np.ndarray, low: np.ndarray, close: np.ndarray,
                      period: int = 14) -> np.ndarray:
        """Calculate Average True Range."""
        prev_close = np.roll(close, 1)
        prev_close[0] = close[0]
        
        tr = np.maximum(
            high - low,
            np.maximum(
                np.abs(high - prev_close),
                np.abs(low - prev_close)
            )
        )
        
        # EMA smoothing
        alpha = 2 / (period + 1)
        atr = np.zeros_like(tr)
        atr[0] = tr[0]
        for i in range(1, len(tr)):
            atr[i] = alpha * tr[i] + (1 - alpha) * atr[i-1]
        
        return atr
    
    @staticmethod
    def get_dynamic_sl(
        entry_price: float,
        atr_value: float,
        direction: str,
        multiplier: float = 1.5
    ) -> float:
        """
        Calculate dynamic stop loss based on ATR.
        
        Args:
            entry_price: Entry price
            atr_value: Current ATR value
            direction: 'BUY' or 'SELL'
            multiplier: ATR multiplier (1.5 = moderate, 2.0 = wide, 1.0 = tight)
        """
        sl_distance = atr_value * multiplier
        
        if direction.upper() == 'BUY':
            return entry_price - sl_distance
        else:
            return entry_price + sl_distance
    
    @staticmethod
    def get_dynamic_tp(
        entry_price: float,
        stop_loss: float,
        rr_ratio: float = 2.0,
        direction: str = 'BUY'
    ) -> float:
        """Calculate Take Profit based on SL distance and R:R ratio."""
        sl_distance = abs(entry_price - stop_loss)
        tp_distance = sl_distance * rr_ratio
        
        if direction.upper() == 'BUY':
            return entry_price + tp_distance
        else:
            return entry_price - tp_distance


# =============================================================================
# TRADE DURATION MANAGER
# =============================================================================

class TradeDurationManager:
    """
    Manage trade duration for scalping to swing trades.
    Range: 5 seconds to 8 hours
    """
    
    def __init__(self, min_seconds: int = 5, max_seconds: int = 28800):
        self.min_duration = timedelta(seconds=min_seconds)
        self.max_duration = timedelta(seconds=max_seconds)
    
    def validate_duration(self, open_time: datetime, current_time: datetime) -> Dict:
        """Check if trade is within valid duration."""
        elapsed = current_time - open_time
        
        return {
            'elapsed_seconds': elapsed.total_seconds(),
            'elapsed_str': str(elapsed),
            'min_reached': elapsed >= self.min_duration,
            'max_reached': elapsed >= self.max_duration,
            'should_close': elapsed >= self.max_duration,
            'remaining_seconds': max(0, (self.max_duration - elapsed).total_seconds())
        }
    
    def get_timeout_action(self, elapsed_seconds: float) -> str:
        """Determine action based on elapsed time."""
        if elapsed_seconds < self.min_duration.total_seconds():
            return "HOLD_MIN"  # Don't close yet, minimum not reached
        elif elapsed_seconds >= self.max_duration.total_seconds():
            return "CLOSE_TIMEOUT"  # Max duration reached, close at market
        else:
            return "MONITOR"  # Normal monitoring


# =============================================================================
# BUDGET OPTIMIZER
# =============================================================================

class BudgetOptimizer:
    """
    Optimize position sizing based on account performance.
    Starts conservative with 100€ demo.
    """
    
    def __init__(self, initial_balance: float = 100.0, risk_pct: float = 0.01):
        self.initial_balance = initial_balance
        self.base_risk = risk_pct
        self.win_rate = 0.5  # Will be updated with actual performance
        self.avg_win = 0.0
        self.avg_loss = 0.0
        self.trade_count = 0
        self.winning_trades = 0
    
    def update_stats(self, pnl: float):
        """Update statistics after a trade."""
        self.trade_count += 1
        
        if pnl > 0:
            self.winning_trades += 1
            self.avg_win = ((self.avg_win * (self.winning_trades - 1)) + pnl) / self.winning_trades
        else:
            losing_trades = self.trade_count - self.winning_trades
            self.avg_loss = ((self.avg_loss * (losing_trades - 1)) + abs(pnl)) / losing_trades if losing_trades > 0 else 0
        
        self.win_rate = self.winning_trades / self.trade_count if self.trade_count > 0 else 0.5
    
    def get_kelly_fraction(self) -> float:
        """
        Calculate Kelly Criterion for optimal bet sizing.
        Kelly % = (bp - q) / b
        where: b = win/loss ratio, p = win probability, q = loss probability
        """
        if self.avg_loss == 0 or self.trade_count < 10:
            return self.base_risk  # Not enough data, use base risk
        
        b = self.avg_win / self.avg_loss  # Win/loss ratio
        p = self.win_rate
        q = 1 - p
        
        kelly = (b * p - q) / b
        
        # Use fractional Kelly (half) for safety
        kelly = kelly / 2
        
        # Clamp to reasonable range
        kelly = max(0.005, min(0.05, kelly))  # 0.5% to 5%
        
        return kelly
    
    def get_recommended_risk(self, balance: float) -> Dict:
        """Get recommended risk percentage based on account performance."""
        if self.trade_count < 20:
            # Not enough data - use conservative fixed risk
            risk_pct = self.base_risk
            method = "FIXED_CONSERVATIVE"
        elif self.win_rate < 0.4:
            # Poor performance - reduce risk
            risk_pct = self.base_risk * 0.5
            method = "REDUCED_RISK"
        elif self.win_rate > 0.6 and self.avg_win > self.avg_loss:
            # Good performance - consider Kelly
            risk_pct = self.get_kelly_fraction()
            method = "KELLY_ADJUSTED"
        else:
            risk_pct = self.base_risk
            method = "STANDARD"
        
        return {
            'risk_percent': risk_pct * 100,
            'risk_amount': balance * risk_pct,
            'method': method,
            'win_rate': self.win_rate * 100,
            'trades_analyzed': self.trade_count
        }


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'RiskConfig',
    'RiskCalculator',
    'ATRStopLoss',
    'TradeDurationManager',
    'BudgetOptimizer'
]
