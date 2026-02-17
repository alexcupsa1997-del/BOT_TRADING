"""
strategies/ml_strategy.py - ML-Based Strategy
=============================================

Uses Deep Learning model for trade decisions.
Integrates FeatureCalculator and ModelLoader.
"""

from decimal import Decimal
import numpy as np
from loguru import logger
from typing import Dict, Any, Optional

from engine.strategy import Strategy
from engine.events import Event, EventType, SignalEvent, SignalType
from engine.features import FeatureCalculator, FeatureBuffer
from engine.model_loader import ModelLoader
from engine.order import Order


class MLStrategy(Strategy):
    """
    Deep Learning Strategy using Goliath Model.
    """
    
    def __init__(self, 
                 model_path: str, 
                 scaler_path: str,
                 symbol: str = "BTCUSD", 
                 confidence_threshold: float = 0.6):
        super().__init__(symbol)
        self.model_path = model_path
        self.scaler_path = scaler_path
        self.confidence_threshold = confidence_threshold
        
        # Components
        self.features = FeatureCalculator(window_size=100) # Calculator needs >52
        self.buffer = FeatureBuffer(sequence_length=64, feature_dim=8)
        self.model_loader = ModelLoader(model_path, scaler_path)
        
        # State
        self.model_loaded = False
        
    def on_start(self):
        """Load model on startup."""
        logger.info("Initializing ML Strategy...")
        try:
            self.model_loader.load()
            self.model_loaded = True
        except Exception as e:
            logger.error(f"Failed to load ML model: {e}")
            self.model_loaded = False

    def on_bar(self, event: Event):
        if not self.model_loaded:
            return

        # 1. Update Features
        feature_vector = self.features.update(event)
        
        if feature_vector is None:
            return # Not enough history yet
            
        # 2. Update Sequence Buffer
        self.buffer.add(feature_vector)
        
        if not self.buffer.is_ready():
            return
            
        # 3. Get Sequence
        # Shape: (1, 64, 8) - buffer returns (1, seq, feat)
        # But model loader expects (seq, feat) for transform, or we transform before buffering?
        # Let's check model loader logic.
        # Loader.predict takes (seq_len, features) and handles normalizing.
        # But buffer stores RAW features? Yes, FeatureCalculator returns RAW.
        # So we pass (64, 8) to predict.
        
        sequence_batch = self.buffer.get_sequence() 
        # get_sequence returns (1, 64, 8). 
        # predict expects (64, 8) based on docstring "sequence: np.ndarray of shape (seq_len, features)"
        sequence = sequence_batch[0]
        
        # 4. Inference
        prediction = self.model_loader.predict(sequence)
        
        action = prediction['action']
        confidence = prediction['confidence']
        tp_sl = prediction['tp_sl']
        
        # 5. Logic
        # 0: SELL, 1: HOLD, 2: BUY
        
        timestamp = event.data['timestamp']
        price = Decimal(str(event.data['close']))
        
        if confidence < self.confidence_threshold:
            return # Skip low confidence
            
        if action == 2: # BUY
            # Create Order
            # Simple sizing: 1.0 unit for now (Risk Manager handles sizing usually)
            order = Order(
                symbol=self.symbol,
                quantity=Decimal("0.1"), # Fixed size for testing
                direction="BUY",
                order_type="MARKET",
                timestamp=timestamp
            )
            
            # Wrap in Event
            event_order = Event(EventType.ORDER, {"order": order}, timestamp=timestamp)
            self.engine.put(event_order)
            
        elif action == 0: # SELL
            order = Order(
                symbol=self.symbol,
                quantity=Decimal("0.1"),
                direction="SELL", 
                order_type="MARKET",
                timestamp=timestamp
            )
            event_order = Event(EventType.ORDER, {"order": order}, timestamp=timestamp)
            self.engine.put(event_order)

            
    def on_tick(self, event: Event):
        pass # Not used yet
        
    def on_order(self, event: Event):
        pass
        
    def on_fill(self, event: Event):
        pass
        
    def on_stop(self):
        logger.info("ML Strategy Stopped.")
