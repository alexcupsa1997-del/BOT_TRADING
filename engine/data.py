"""
engine/data.py
==============

Data Feed definitions.
"""

import abc
from decimal import Decimal
from typing import Optional, Iterator, Any
import polars as pl
from loguru import logger
from engine.events import Event, EventType

class DataFeed(abc.ABC):
    """Abstract Base Class for Data Feeds (Data Layer)."""

    @abc.abstractmethod
    def load(self, start_date: str, end_date: str) -> None:
        """Load data into memory (or lazy scan)."""
        pass

    @abc.abstractmethod
    def get_next(self) -> Optional[Event]:
        """Return the next bar/tick event or None if exhausted."""
        pass

    @abc.abstractmethod
    def reset(self) -> None:
        """Reset the feed iterator to the beginning."""
        pass

class PolarsDataFeed(DataFeed):
    """DataFeed implementation using Polars for high-performance reading."""

    def __init__(self, file_path: Optional[str] = None, symbol: str = "BTCUSD", dataframe: Optional[pl.DataFrame] = None):
        self.file_path = file_path
        self.symbol = symbol
        self.df: Optional[pl.DataFrame] = dataframe
        self.iterator: Optional[Iterator] = None

    def load(self, start_date: str = None, end_date: str = None) -> None:
        """
        Load data from file.
        start_date/end_date arguments are kept for interface compatibility 
        but logic is simplified here.
        """
        if self.file_path is None and self.df is not None:
             logger.info(f"Using in-memory dataframe for {self.symbol} ({len(self.df)} rows).")
             self.reset()
             return

        logger.info(f"Loading data for {self.symbol} from {self.file_path}...")
        try:
            if self.file_path.endswith(".csv"):
                # Configure CSV reading
                self.df = pl.read_csv(self.file_path, try_parse_dates=True)
            else:
                # Default to Parquet
                self.df = pl.read_parquet(self.file_path)
                
            # Ensure columns exist and rename if necessary (basic normalization)
            # Map 'time' to 'timestamp' if needed
            if "time" in self.df.columns and "timestamp" not in self.df.columns:
                self.df = self.df.rename({"time": "timestamp"})
            
            logger.info(f"Loaded {len(self.df)} rows.")
        except Exception as e:
            logger.error(f"Could not load data ({e}).")
            self.df = None

        self.reset()

    def slice(self, start: Any, end: Any) -> 'PolarsDataFeed':
        """Return a new PolarsDataFeed with data within [start, end)."""
        if self.df is None:
             raise ValueError("Data not loaded.")
        
        # Ensure timestamp column is proper type for comparison
        # Assuming timestamp is int64 (ns) or datetime
        # We might need to cast start/end to match df type
        
        # Determine strict type of column
        # logic... for now assume datetime or timestamp matches
        
        filtered_df = self.df.filter(
            (pl.col("timestamp") >= start) & (pl.col("timestamp") < end)
        )
        
        return PolarsDataFeed(symbol=self.symbol, dataframe=filtered_df)

    
    def reset(self) -> None:
        self.iterator = self.df.iter_rows(named=True) if self.df is not None else iter([])

    def get_next(self) -> Optional[Event]:
        try:
            if self.iterator is None:
                return None
            row = next(self.iterator)
            
            # Strict Type Conversion
            strict_data = {
                "symbol": self.symbol, 
                "timestamp": row["timestamp"],
                "open": Decimal(str(row["open"])),
                "high": Decimal(str(row["high"])),
                "low": Decimal(str(row["low"])),
                "close": Decimal(str(row["close"])),
                "volume": Decimal(str(row["volume"])),
            }
            return Event(type=EventType.BAR, data=strict_data)
        except StopIteration:
            return None
        except Exception:
            return None
