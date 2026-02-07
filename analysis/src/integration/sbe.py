"""
SBE (Simple Binary Encoding) Protocol Library

Enterprise-grade implementation of the SBE protocol for the Python Analysis Service.
Strictly adheres to the `gateway/sbe-schema.xml` definition.

Features:
- Little-Endian encoding (standard for x86/64).
- Type-safe packaging of Headers and Messages.
- Fixed-Point Decimal handling.
"""

import struct
from dataclasses import dataclass
from enum import Enum
from typing import BinaryIO, Optional
from loguru import logger

# ==============================================================================
# Constants & Enums
# ==============================================================================

SBE_HEADER_FORMAT = '<HHH'  # BlockLength(u16), TemplateId(u16), SchemaId(u16), Version(u16)
# Note: Struct format for header is actually 4 uint16s. 
# '<HHHH' = Little Endian: BlockLength, TemplateId, SchemaId, Version
SBE_HEADER_SIZE = 8

class Side(Enum):
    BUY = b'B'
    SELL = b'S'

class OrderType(Enum):
    LIMIT = b'L'
    MARKET = b'M'

# ==============================================================================
# Value Objects
# ==============================================================================

@dataclass
class Decimal9:
    """Fixed-point decimal with 9 decimal places (as per schema)."""
    mantissa: int
    exponent: int = -9  # Constant from schema
    
    def pack(self) -> bytes:
        """Pack to int64 mantissa (Little Endian)."""
        return struct.pack('<q', self.mantissa)
    
    @classmethod
    def from_float(cls, value: float) -> 'Decimal9':
        """Create from float (lossy conversion warning)."""
        # value = mantissa * 10^-9
        # mantissa = value * 10^9
        mantissa = int(value * 1_000_000_000)
        return cls(mantissa=mantissa)

# ==============================================================================
# Header
# ==============================================================================

@dataclass
class SbeHeader:
    block_length: int
    template_id: int
    schema_id: int
    version: int
    
    def pack(self) -> bytes:
        return struct.pack('<HHHH', self.block_length, self.template_id, self.schema_id, self.version)

# ==============================================================================
# Messages
# ==============================================================================

@dataclass
class OrderResult:
    """
    Message ID: 2
    Description: Execution Report
    """
    order_id: int      # int64
    symbol: int        # int64 (ID mapping)
    side: Side         # char
    price: Decimal9    # decimal9
    quantity: Decimal9 # decimal9
    
    BLOCK_LENGTH = 33 # 8(id) + 8(sym) + 1(side) + 8(px) + 8(qty) = 33 bytes
    TEMPLATE_ID = 2
    SCHEMA_ID = 1
    VERSION = 1
    
    def pack(self) -> bytes:
        """Serialize message to bytes including Header."""
        header = SbeHeader(
            block_length=self.BLOCK_LENGTH,
            template_id=self.TEMPLATE_ID,
            schema_id=self.SCHEMA_ID,
            version=self.VERSION
        )
        
        body = bytearray()
        body.extend(struct.pack('<q', self.order_id))
        body.extend(struct.pack('<q', self.symbol))
        body.extend(self.side.value)  # char (1 byte)
        body.extend(self.price.pack()) # 8 bytes
        body.extend(self.quantity.pack()) # 8 bytes
        
        return header.pack() + body

# ==============================================================================
# Utilities
# ==============================================================================

class MessageFactory:
    @staticmethod
    def create_order_result(
        order_id: int,
        symbol_id: int,
        side: Side,
        price_float: float,
        qty_float: float
    ) -> OrderResult:
        return OrderResult(
            order_id=order_id,
            symbol=symbol_id,
            side=side,
            price=Decimal9.from_float(price_float),
            quantity=Decimal9.from_float(qty_float)
        )
