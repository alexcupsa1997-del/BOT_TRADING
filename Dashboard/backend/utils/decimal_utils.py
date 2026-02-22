"""
Decimal serialization utilities.
All financial values MUST use Decimal, never float.
"""

from decimal import Decimal, InvalidOperation
from typing import Any


def to_decimal(value: Any) -> Decimal:
    """Convert any value to Decimal safely."""
    if isinstance(value, Decimal):
        return value
    if isinstance(value, float):
        return Decimal(str(value))
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return Decimal("0")


def decimal_to_str(value: Decimal) -> str:
    """Convert Decimal to string for JSON serialization."""
    return str(value)


def safe_json_value(value: Any) -> Any:
    """Convert Decimal values in dicts/lists to strings for JSON."""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {k: safe_json_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe_json_value(item) for item in value]
    return value
