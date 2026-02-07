"""
SBE Stream Producer Tool

Generates a binary stream of SBE messages to verify system wiring.
Simulates an Exchange sending Execution Reports.

Usage:
    python -m src.integration.producer --count 100 --output orders.sbe
"""

import argparse
import random
import time
import sys
from pathlib import Path
from loguru import logger

# Allow direct execution
if __name__ == "__main__" and __package__ is None:
    # Add the 'analysis' root directory to sys.path
    file_path = Path(__file__).resolve()
    # Go up 3 levels: src/integration/producer.py -> analysis/
    root_path = file_path.parent.parent.parent
    sys.path.append(str(root_path))
    
    # Re-import to fix package context (optional, but sys.path is enough for absolute imports)
    from src.integration.sbe import MessageFactory, Side
else:
    from .sbe import MessageFactory, Side

def generate_stream(count: int, output_path: str):
    logger.info(f"Generating {count} SBE OrderResult messages...")
    
    with open(output_path, 'wb') as f:
        for i in range(count):
            # Synthetic Data
            order_id = 1000 + i
            symbol_id = 1 # BTC/USD
            side = random.choice([Side.BUY, Side.SELL])
            price = 45000.0 + random.uniform(-100, 100)
            qty = random.uniform(0.1, 2.0)
            
            msg = MessageFactory.create_order_result(
                order_id=order_id,
                symbol_id=symbol_id,
                side=side,
                price_float=price,
                qty_float=qty
            )
            
            # Write binary
            f.write(msg.pack())
            
            if i % 10000 == 0 and i > 0:
                logger.info(f"Generated {i} messages...")
                
    logger.success(f"Stream generation complete. Output: {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SBE Stream Producer")
    parser.add_argument("--count", type=int, default=100, help="Number of messages")
    parser.add_argument("--output", type=str, default="orders.sbe", help="Output file path")
    
    args = parser.parse_args()
    generate_stream(args.count, args.output)
