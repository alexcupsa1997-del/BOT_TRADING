"""
config.py - Configuration for Exchange Integration
==================================================

Defines configuration data structures for the Exchange Manager.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional

@dataclass
class ExchangeConfig:
    """Configuration for an exchange connection."""
    exchange_id: str
    sandbox: bool = False
    rate_limit_per_min: int = 1200
    retry_count: int = 3
    retry_delay_base: float = 1.0
    api_key: Optional[str] = None
    secret: Optional[str] = None
    password: Optional[str] = None  # For some exchanges like KuCoin/OKX
    
    def to_ccxt_dict(self) -> Dict:
        """Convert config to CCXT-compatible dictionary."""
        config = {
            'enableRateLimit': True,  # We manage rate limiting ourselves but good to have
            'options': {'defaultType': 'spot'}, # Default to spot, can be overridden
        }
        
        if self.api_key and self.secret:
            config['apiKey'] = self.api_key
            config['secret'] = self.secret
            
        if self.password:
            config['password'] = self.password
            
        if self.sandbox:
            config['test'] = True
            
        return config
