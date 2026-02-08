//! Domain Value Objects with fixed-point arithmetic
//!
//! These value objects ensure mathematical integrity across the trading domain.
//! All monetary calculations use fixed-point to avoid floating-point errors.

use std::cmp::Ordering;
use std::fmt;
use std::ops::{Add, Sub, Mul, Div};
use serde::{Deserialize, Serialize};

/// Fixed-point decimal with 8 decimal places
/// Stored as i128 for large value support
const DECIMAL_PLACES: u32 = 8;
const SCALE: i128 = 100_000_000; // 10^8

// =============================================================================
// Price Value Object
// =============================================================================

/// Price represents an exchange rate between two currencies
/// 
/// Invariants:
/// - Price must be non-negative
/// - Price precision is 8 decimal places
/// 
/// # Example
/// ```
/// use engine::domain::value_objects::Price;
/// let price = Price::new(50000, 50)?; // $50,000.50
/// # Ok::<(), engine::domain::value_objects::ValueError>(())
/// ```
#[derive(Clone, Copy, Default, Serialize, Deserialize)]
pub struct Price {
    /// Raw value scaled by 10^8
    raw: i128,
}

impl Price {
    /// Create a new Price from integer and fractional parts
    /// 
    /// `fraction` is treated as the raw decimal part scaled to 10^8.
    /// Example: new(100, 50000000) -> 100.50000000
    pub fn new(integer: i64, fraction: i64) -> Result<Self, ValueError> {
        if integer < 0 || fraction < 0 {
            return Err(ValueError::NegativeValue);
        }
        if fraction >= SCALE as i64 {
            // Fraction part cannot exceed the scale (must be < 1.0)
            return Err(ValueError::ParseError("Fraction exceeds scale".to_string()));
        }
        
        let raw = (integer as i128) * SCALE + (fraction as i128);
        Ok(Self { raw })
    }
    
    /// Create from raw scaled value
    pub fn from_raw(raw: i128) -> Result<Self, ValueError> {
        if raw < 0 {
            return Err(ValueError::NegativeValue);
        }
        Ok(Self { raw })
    }
    
    /// Create from a decimal string
    pub fn from_str(s: &str) -> Result<Self, ValueError> {
        let parts: Vec<&str> = s.split('.').collect();
        
        let integer: i128 = parts.get(0)
            .and_then(|s| s.parse().ok())
            .unwrap_or(0);
        
        let fraction: i128 = if let Some(frac) = parts.get(1) {
            let mut f = frac.parse::<i128>().unwrap_or(0);
            // Handle varying lengths of fractional parts
            let len = frac.len();
            if len > DECIMAL_PLACES as usize {
                // Truncate if too long (or round? defaulting to truncate for simplicity)
                 let truncated = &frac[0..DECIMAL_PLACES as usize];
                 f = truncated.parse::<i128>().unwrap_or(0);
            } else {
                let missing_zeros = DECIMAL_PLACES as usize - len;
                f *= 10i128.pow(missing_zeros as u32);
            }
            f
        } else {
            0
        };
        
        let raw = integer * SCALE + fraction;
        if raw < 0 {
            return Err(ValueError::NegativeValue);
        }
        
        Ok(Self { raw })
    }
    
    /// Zero price
    pub fn zero() -> Self {
        Self { raw: 0 }
    }
    
    /// Get raw scaled value
    pub fn raw(&self) -> i128 {
        self.raw
    }
    
    /// Check if zero
    pub fn is_zero(&self) -> bool {
        self.raw == 0
    }
    
    /// Convert to f64 (for display only, not calculations!)
    pub fn to_f64(&self) -> f64 {
        self.raw as f64 / SCALE as f64
    }
}

impl fmt::Display for Price {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let integer = self.raw / SCALE;
        let fraction = (self.raw % SCALE).abs();
        write!(f, "{}.{:08}", integer, fraction)
    }
}

impl fmt::Debug for Price {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "Price({})", self)
    }
}

impl PartialEq for Price {
    fn eq(&self, other: &Self) -> bool {
        self.raw == other.raw
    }
}

impl Eq for Price {}

impl PartialOrd for Price {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}

impl Ord for Price {
    fn cmp(&self, other: &Self) -> Ordering {
        self.raw.cmp(&other.raw)
    }
}

impl Add for Price {
    type Output = Self;
    
    fn add(self, rhs: Self) -> Self::Output {
        Self { raw: self.raw + rhs.raw }
    }
}

impl Sub for Price {
    type Output = Self;
    
    fn sub(self, rhs: Self) -> Self::Output {
        Self { raw: (self.raw - rhs.raw).max(0) }
    }
}

// =============================================================================
// Quantity Value Object
// =============================================================================

/// Quantity represents an amount of an asset
/// 
/// Invariants:
/// - Quantity must be non-negative
/// - Quantity precision is 8 decimal places
#[derive(Clone, Copy, Default, Serialize, Deserialize)]
pub struct Quantity {
    raw: i128,
}

impl Quantity {
    /// Create from raw scaled value
    pub fn from_raw(raw: i128) -> Result<Self, ValueError> {
        if raw < 0 {
            return Err(ValueError::NegativeValue);
        }
        Ok(Self { raw })
    }
    
    /// Create from a decimal string
    pub fn from_str(s: &str) -> Result<Self, ValueError> {
        let parts: Vec<&str> = s.split('.').collect();
        
        let integer: i128 = parts.get(0)
            .and_then(|s| s.parse().ok())
            .unwrap_or(0);
        
        let fraction: i128 = if let Some(frac) = parts.get(1) {
             let mut f = frac.parse::<i128>().unwrap_or(0);
            let len = frac.len();
             if len > DECIMAL_PLACES as usize {
                 let truncated = &frac[0..DECIMAL_PLACES as usize];
                 f = truncated.parse::<i128>().unwrap_or(0);
             } else {
                 let missing_zeros = DECIMAL_PLACES as usize - len;
                 f *= 10i128.pow(missing_zeros as u32);
             }
             f
        } else {
            0
        };
        
        let raw = integer * SCALE + fraction;
        if raw < 0 {
            return Err(ValueError::NegativeValue);
        }
        
        Ok(Self { raw })
    }
    
    /// Zero quantity
    pub fn zero() -> Self {
        Self { raw: 0 }
    }
    
    /// Get raw scaled value
    pub fn raw(&self) -> i128 {
        self.raw
    }
    
    /// Check if zero
    pub fn is_zero(&self) -> bool {
        self.raw == 0
    }
    
    /// Convert to f64 (for display only!)
    pub fn to_f64(&self) -> f64 {
        self.raw as f64 / SCALE as f64
    }
    
    /// Calculate total value: Quantity * Price = Price (value)
    pub fn value_at(&self, price: Price) -> Price {
        let raw = (self.raw * price.raw()) / SCALE;
        Price::from_raw(raw).unwrap_or(Price::zero())
    }
}

impl fmt::Display for Quantity {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let integer = self.raw / SCALE;
        let fraction = (self.raw % SCALE).abs();
        write!(f, "{}.{:08}", integer, fraction)
    }
}

impl fmt::Debug for Quantity {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "Quantity({})", self)
    }
}

impl PartialEq for Quantity {
    fn eq(&self, other: &Self) -> bool {
        self.raw == other.raw
    }
}

impl Eq for Quantity {}

impl PartialOrd for Quantity {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}

impl Ord for Quantity {
    fn cmp(&self, other: &Self) -> Ordering {
        self.raw.cmp(&other.raw)
    }
}

impl Add for Quantity {
    type Output = Self;
    
    fn add(self, rhs: Self) -> Self::Output {
        Self { raw: self.raw + rhs.raw }
    }
}

impl Sub for Quantity {
    type Output = Self;
    
    fn sub(self, rhs: Self) -> Self::Output {
        Self { raw: (self.raw - rhs.raw).max(0) }
    }
}

impl Mul<i64> for Quantity {
    type Output = Self;
    
    fn mul(self, rhs: i64) -> Self::Output {
        Self { raw: self.raw * rhs as i128 }
    }
}

impl Div<i64> for Quantity {
    type Output = Self;
    
    fn div(self, rhs: i64) -> Self::Output {
        Self { raw: self.raw / rhs as i128 }
    }
}

// =============================================================================
// Currency Value Object
// =============================================================================

/// Currency represents an asset identifier
/// 
/// Invariants:
/// - 3-6 uppercase characters
/// - Immutable once created
#[derive(Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct Currency {
    code: String,
}

impl Currency {
    pub fn new(code: &str) -> Result<Self, ValueError> {
        let code = code.to_uppercase();
        
        if code.len() < 3 || code.len() > 8 { // Extended from 6 to 8 for some crypto symbols
            return Err(ValueError::InvalidCurrency);
        }
        
        if !code.chars().all(|c| c.is_ascii_alphanumeric()) {
            return Err(ValueError::InvalidCurrency);
        }
        
        Ok(Self { code })
    }
    
    pub fn code(&self) -> &str {
        &self.code
    }
}

impl fmt::Display for Currency {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.code)
    }
}

impl fmt::Debug for Currency {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "Currency({})", self.code)
    }
}

// =============================================================================
// Trading Pair Value Object
// =============================================================================

/// TradingPair represents a market (e.g., BTC-EUSD)
#[derive(Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct TradingPair {
    base: Currency,
    quote: Currency,
}

impl TradingPair {
    pub fn new(base: Currency, quote: Currency) -> Self {
        Self { base, quote }
    }
    
    pub fn from_str(s: &str) -> Result<Self, ValueError> {
        let parts: Vec<&str> = s.split('-').collect();
        if parts.len() != 2 {
            return Err(ValueError::InvalidSymbol);
        }
        
        let base = Currency::new(parts[0])?;
        let quote = Currency::new(parts[1])?;
        
        Ok(Self { base, quote })
    }
    
    pub fn base(&self) -> &Currency {
        &self.base
    }
    
    pub fn quote(&self) -> &Currency {
        &self.quote
    }
    
    pub fn symbol(&self) -> String {
        format!("{}-{}", self.base, self.quote)
    }
}

impl fmt::Display for TradingPair {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}-{}", self.base, self.quote)
    }
}

impl fmt::Debug for TradingPair {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "TradingPair({})", self)
    }
}

// =============================================================================
// Percentage Value Object
// =============================================================================

/// Percentage for rates, fees, etc.
/// Stored as basis points (1/10000)
#[derive(Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct Percentage {
    basis_points: i32, // 100% = 10000 bp
}

impl Percentage {
    pub fn from_basis_points(bp: i32) -> Self {
        Self { basis_points: bp }
    }
    
    pub fn from_percent(pct: f64) -> Self {
        Self { basis_points: (pct * 100.0) as i32 }
    }
    
    pub fn basis_points(&self) -> i32 {
        self.basis_points
    }
    
    pub fn as_decimal(&self) -> f64 {
        self.basis_points as f64 / 10000.0
    }
    
    /// Apply percentage to a quantity
    pub fn of(&self, qty: Quantity) -> Quantity {
        let raw = (qty.raw() * self.basis_points as i128) / 10000;
        Quantity::from_raw(raw).unwrap_or(Quantity::zero())
    }
}

impl fmt::Display for Percentage {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let pct = self.basis_points as f64 / 100.0;
        write!(f, "{:.2}%", pct)
    }
}

// =============================================================================
// Errors
// =============================================================================

#[derive(Debug, Clone, PartialEq)]
pub enum ValueError {
    NegativeValue,
    InvalidCurrency,
    InvalidSymbol,
    Overflow,
    ParseError(String),
}

impl fmt::Display for ValueError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            ValueError::NegativeValue => write!(f, "Value cannot be negative"),
            ValueError::InvalidCurrency => write!(f, "Invalid currency code"),
            ValueError::InvalidSymbol => write!(f, "Invalid trading pair symbol"),
            ValueError::Overflow => write!(f, "Arithmetic overflow"),
            ValueError::ParseError(s) => write!(f, "Parse error: {}", s),
        }
    }
}

impl std::error::Error for ValueError {}

// =============================================================================
// Tests
// =============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_price_creation() {
        let price = Price::from_str("50000.12345678").unwrap();
        assert_eq!(price.to_string(), "50000.12345678");
    }
    
    #[test]
    fn test_price_truncation() {
        // Test that we handle >8 decimal places gracefully (by truncating)
        let price = Price::from_str("50000.123456789").unwrap();
        assert_eq!(price.to_string(), "50000.12345678");
    }

    #[test]
    fn test_price_arithmetic() {
        let p1 = Price::from_str("100.00").unwrap();
        let p2 = Price::from_str("50.00").unwrap();
        
        assert_eq!((p1 + p2).to_string(), "150.00000000");
        assert_eq!((p1 - p2).to_string(), "50.00000000");
    }

    #[test]
    fn test_quantity_value() {
        let qty = Quantity::from_str("10.0").unwrap();
        let price = Price::from_str("100.0").unwrap();
        
        let value = qty.value_at(price);
        assert_eq!(value.to_string(), "1000.00000000");
    }

    #[test]
    fn test_currency_validation() {
        assert!(Currency::new("BTC").is_ok());
        assert!(Currency::new("EUSD").is_ok());
        assert!(Currency::new("AB").is_err()); // Too short
        assert!(Currency::new("ABCDEFG").is_ok()); // 7 chars ok
    }

    #[test]
    fn test_trading_pair() {
        let pair = TradingPair::from_str("BTC-EUSD").unwrap();
        assert_eq!(pair.base().code(), "BTC");
        assert_eq!(pair.quote().code(), "EUSD");
        assert_eq!(pair.symbol(), "BTC-EUSD");
    }
}
