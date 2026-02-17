"""
engine/indicators.py
====================

Incremental Technical Indicators for Event-Driven Backtesting.
All calculations use Decimal for precision.
"""

import abc
from collections import deque
from decimal import Decimal, Context, ROUND_HALF_UP
from typing import Optional, Deque, Tuple

# Precision context for indicators
CTX = Context(prec=28, rounding=ROUND_HALF_UP)

class Indicator(abc.ABC):
    """Base class for incremental indicators."""
    
    def __init__(self):
        self._value: Optional[Decimal] = None
        self._ready: bool = False

    @abc.abstractmethod
    def update(self, value: Decimal) -> Decimal:
        """Update the indicator with a new value."""
        pass

    @property
    def value(self) -> Decimal:
        if not self._ready or self._value is None:
            raise ValueError("Indicator not ready")
        return self._value

    @property
    def ready(self) -> bool:
        return self._ready

class SMA(Indicator):
    """Simple Moving Average."""
    
    def __init__(self, period: int):
        super().__init__()
        self.period = period
        self.window: Deque[Decimal] = deque(maxlen=period)
        self.sum = Decimal("0")

    def update(self, value: Decimal) -> Decimal:
        if len(self.window) == self.period:
            self.sum -= self.window[0]
        
        self.window.append(value)
        self.sum += value
        
        if len(self.window) == self.period:
            self._value = self.sum / self.period
            self._ready = True
        else:
            self._ready = False
            self._value = Decimal("0") # Not ready
            
        return self._value if self._ready else Decimal("0")

class EMA(Indicator):
    """Exponential Moving Average."""
    
    def __init__(self, period: int):
        super().__init__()
        self.period = period
        # Multiplier: 2 / (N + 1)
        self.multiplier = Decimal(2) / (Decimal(period) + Decimal(1))
        self._initialized = False

    def update(self, value: Decimal) -> Decimal:
        if not self._initialized:
            self._value = value
            self._initialized = True
            self._ready = False # Typically EMA needs a startup period tailored to preference, but strictly index 0 IS the average.
            # However, for stability, we might want to wait 'period' ticks. 
            # In standard def, first value is SMA or just Price. Let's say it's ready immediately for simplicity, 
            # or track count.
            # Let's say it becomes ready after 'period' updates to stabilize.
            self._count = 1
        else:
            self._value = (value - self._value) * self.multiplier + self._value
            self._count += 1
            
        if self._count >= self.period:
            self._ready = True
            
        return self._value

class RSI(Indicator):
    """Relative Strength Index."""
    
    def __init__(self, period: int = 14):
        super().__init__()
        self.period = period
        self.prev_value: Optional[Decimal] = None
        self.gains: Deque[Decimal] = deque(maxlen=period)
        self.losses: Deque[Decimal] = deque(maxlen=period)
        
        # We need simpler smoothing: Wilder's Smoothing is standard for RSI.
        # But for simplicity in V1, we can use simple average of gains/losses or Wilder's.
        # Standard RSI uses Wilder's: AvgGain = (PrevAvgGain * (n-1) + CurrentGain) / n
        self.avg_gain = Decimal("0")
        self.avg_loss = Decimal("0")
        self.count = 0

    def update(self, value: Decimal) -> Decimal:
        if self.prev_value is None:
            self.prev_value = value
            return Decimal("0")

        change = value - self.prev_value
        self.prev_value = value
        
        gain = change if change > 0 else Decimal("0")
        loss = -change if change < 0 else Decimal("0")
        
        self.count += 1
        
        if self.count <= self.period:
            # First calculation: Simple Average
            self.avg_gain += gain
            self.avg_loss += loss
            if self.count == self.period:
                self.avg_gain /= self.period
                self.avg_loss /= self.period
                self._ready = True
        else:
            # Wilder's Smoothing
            self.avg_gain = ((self.avg_gain * (self.period - 1)) + gain) / self.period
            self.avg_loss = ((self.avg_loss * (self.period - 1)) + loss) / self.period
            
        if self._ready:
            if self.avg_loss == 0:
                self._value = Decimal("100")
            else:
                rs = self.avg_gain / self.avg_loss
                self._value = Decimal("100") - (Decimal("100") / (Decimal("1") + rs))
        else:
            self._value = Decimal("0")
            
        return self._value

class BollingerBands(Indicator):
    """Bollinger Bands."""
    
    def __init__(self, period: int = 20, std_dev: int = 2):
        super().__init__()
        self.period = period
        self.std_dev_mult = Decimal(std_dev)
        self.sma = SMA(period)
        self.window: Deque[Decimal] = deque(maxlen=period)
        
        self.upper: Optional[Decimal] = None
        self.lower: Optional[Decimal] = None
        self.middle: Optional[Decimal] = None

    def update(self, value: Decimal) -> Decimal:
        self.middle = self.sma.update(value)
        self.window.append(value)
        
        if self.sma.ready:
            # Calculate StdDev
            # Variance = Sum((x - mean)^2) / n
            variance = sum((x - self.middle) ** 2 for x in self.window) / self.period
            std_dev = variance.sqrt()
            
            self.upper = self.middle + (std_dev * self.std_dev_mult)
            self.lower = self.middle - (std_dev * self.std_dev_mult)
            self._ready = True
            self._value = self.upper # Default value is Upper Band? Or return tuple? 
            # Indicator base class expects single value. 
            # Strategies should access .upper / .lower directly.
        else:
            self._ready = False
            self.upper = Decimal("0")
            self.lower = Decimal("0")
            
        return self.middle
