//! Liquidity Spiral Protection
//! 
//! Prevents "Death Spirals" by throttling liquidations when
//! system-wide liquidation volume exceeds market depth capacity.

use rust_decimal::Decimal;
use rust_decimal_macros::dec;

#[derive(Debug)]
pub enum MarketState {
    Normal,
    Stressed,
    SpiralDetected,
}

pub struct SpiralGuard {
    pub rolling_liquidation_volume: Decimal,
    pub market_depth_threshold: Decimal, // Max volume allowed per minute
    pub last_decay_time: u64,
    pub state: MarketState,
}

impl SpiralGuard {
    pub fn new(depth_capacity: Decimal) -> Self {
        Self {
            rolling_liquidation_volume: Decimal::ZERO,
            market_depth_threshold: depth_capacity,
            last_decay_time: 0,
            state: MarketState::Normal,
        }
    }

    /// Decay the rolling volume counter over time
    fn decay_volume(&mut self, current_time: u64) {
        if self.last_decay_time == 0 {
            self.last_decay_time = current_time;
            return;
        }

        let elapsed = current_time - self.last_decay_time;
        if elapsed > 0 {
            // Simple linear decay: e.g. 1000 units per second
            let decay_rate = self.market_depth_threshold / dec!(600); // drain in 10 mins
            let decay_amount = decay_rate * Decimal::from(elapsed);
            
            if decay_amount >= self.rolling_liquidation_volume {
                self.rolling_liquidation_volume = Decimal::ZERO;
            } else {
                self.rolling_liquidation_volume -= decay_amount;
            }
            self.last_decay_time = current_time;
        }
    }

    /// Request permission to liquidate `amount` USD
    /// Returns: Allowed Amount to liquidate (might be partial or zero)
    pub fn check_liquidation(&mut self, amount: Decimal, current_time: u64) -> Decimal {
        self.decay_volume(current_time);

        self.update_state();

        match self.state {
            MarketState::Normal => {
                self.rolling_liquidation_volume += amount;
                amount // Allow full
            },
            MarketState::Stressed => {
                // Throttle to 50%
                let allowed = amount * dec!(0.5);
                self.rolling_liquidation_volume += allowed;
                allowed
            },
            MarketState::SpiralDetected => {
                // Hault liquidations! Only allow small drip (e.g. 1%)
                let allowed = amount * dec!(0.01);
                self.rolling_liquidation_volume += allowed;
                allowed
            }
        }
    }

    fn update_state(&mut self) {
        if self.rolling_liquidation_volume > self.market_depth_threshold {
            self.state = MarketState::SpiralDetected;
        } else if self.rolling_liquidation_volume > self.market_depth_threshold * dec!(0.7) {
            self.state = MarketState::Stressed;
        } else {
            self.state = MarketState::Normal;
        }
    }
}
