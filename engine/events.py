"""
engine/events.py - Event Definitions
====================================

Core event types and data structures for the GOLIATH backtest engine.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, Optional
import time

class EventType(Enum):
    """Types of events in the backtest loop."""
    TICK = auto()        # New tick data
    BAR = auto()         # New OHLCV bar
    SIGNAL = auto()      # Strategy signal (buy/sell intent)
    ORDER = auto()       # Order execution request
    FILL = auto()        # Order fill confirmation
    POSITION = auto()    # Position update
    LOG = auto()         # System log event
    END = auto()         # End of backtest

    TIMESTAMP = auto()   # Time sync event (simulated clock)

class SignalType(Enum):
    """Direction of the signal."""
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"

@dataclass
class Event:
    """Base event container."""
    type: EventType
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

@dataclass
class SignalEvent(Event):
    """Specialized Event for Strategy Signals."""
    def __init__(self, symbol: str, timestamp: float, signal_type: SignalType, strength: float = 0.0):
        self.type = EventType.SIGNAL
        self.timestamp = timestamp
        self.data = {
            "symbol": symbol,
            "signal_type": signal_type,
            "strength": strength
        }
