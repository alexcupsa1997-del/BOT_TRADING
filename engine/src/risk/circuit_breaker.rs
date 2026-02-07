//! Circuit Breakers & System Protections
//! 
//! Stops trading if volatility exceeds safety limits.

use rust_decimal::Decimal;

#[derive(Debug)]
pub enum CircuitState {
    Active,
    Triggered(u64), // Timestamp when triggered
    CoolingDown,
}

pub struct VolatilityBreaker {
    pub max_drop_percentage: Decimal, // e.g., 0.10 (10%)
    pub window_seconds: u64,
    pub last_price: Decimal,
    pub last_update: u64,
    pub state: CircuitState,
}

impl VolatilityBreaker {
    pub fn new(max_drop: Decimal) -> Self {
        Self {
            max_drop_percentage: max_drop,
            window_seconds: 60,
            last_price: Decimal::ZERO,
            last_update: 0,
            state: CircuitState::Active,
        }
    }

    pub fn check(&mut self, current_price: Decimal, new_price: Decimal) -> bool {
        if self.last_price.is_zero() {
            self.last_price = current_price;
            return true; // OK
        }

        let change = (new_price - self.last_price).abs() / self.last_price;
        
        if change > self.max_drop_percentage {
            // Trigger Breaker!
            return false;
        }

        self.last_price = new_price;
        true
    }
}
