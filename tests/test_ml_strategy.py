import unittest
import os
import sys
import shutil
from decimal import Decimal
import numpy as np
import polars as pl
from datetime import datetime, timedelta

# Add project root
sys.path.append(os.getcwd())

from engine.backtest_engine import BacktestEngine
from engine.data import PolarsDataFeed
from engine.events import Event, EventType
from strategies.ml_strategy import MLStrategy
from tests.generate_mock_model import generate_mock

class TestMLStrategy(unittest.TestCase):
    def setUp(self):
        # Generate mock artifacts
        generate_mock()
        self.model_path = "tests/data/goliath_mock.pth"
        self.scaler_path = "tests/data/scaler_mock.json"
        
        # Create Synthetic Data
        # We need enough data to fill the window (100) + sequence (64) buffer
        # Total needed > 164
        self.dates = [datetime(2023, 1, 1) + timedelta(minutes=i) for i in range(300)]
        self.prices = [100.0 + np.sin(i/10.0) * 10.0 for i in range(300)] # Sine wave
        
        # Create DataFrame using Polars directly
        self.pl_df = pl.DataFrame({
            'timestamp': self.dates,
            'open': self.prices,
            'high': self.prices,
            'low': self.prices,
            'close': self.prices,
            'volume': [1000.0] * 300
        })
        
    def tearDown(self):
        if os.path.exists("tests/data"):
            shutil.rmtree("tests/data")

    def test_end_to_end_flow(self):
        """Test full loop: Data -> FeatureCalc -> Buffer -> Model -> Signal"""
        
        engine = BacktestEngine(initial_cash=Decimal("10000"))
        
        # Data Feed
        feed = PolarsDataFeed(dataframe=self.pl_df)
        engine.add_data_feed(feed)
        
        # Strategy
        # Note: With a random model, output is garbage, but we test the pipeline integrity.
        # We set confidence threshold to 0 to ensure we get SOME signals if logic works.
        strategy = MLStrategy(
            model_path=self.model_path,
            scaler_path=self.scaler_path,
            symbol="BTCUSD",
            confidence_threshold=0.0 # Force signals
        )
        engine.add_strategy(strategy)
        
        # Run
        engine.run()
        
        # Verify
        # 1. Did we process events? 
        # (We can't easily check internal state of strategy, but we can check if signals were generated)
        # Since model is random, it might output Hold(1).
        # We just want to ensure no crash and feature buffer filled.
        
        print(f"Initial Cash: {engine.initial_cash}")
        print(f"Final Equity: {engine.history[-1]['total_equity'] if engine.history else 'N/A'}")
        
        # We manually verify if features were calculated by checking internal state if possible
        # or relying on no errors.

if __name__ == "__main__":
    unittest.main()
