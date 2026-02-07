//! Liquidation Engine
//! 
//! Handles the logic for liquidating unhealthy positions.
//! Supports:
//! - Fixed Price Liquidation (instant with penalty)
//! - Dutch Auction Liquidation (price decay over time)

use rust_decimal::Decimal;
use rust_decimal_macros::dec;
use crate::risk::margin::AssetRiskParams;

#[derive(Debug)]
pub struct LiquidationResult {
    pub collateral_to_seize: Decimal,
    pub debt_to_cover: Decimal,
    pub liquidator_profit: Decimal,
}

#[derive(Debug)]
pub struct LiquidationEngine {
    pub close_factor: Decimal, // Max % of debt to liquidate at once (e.g., 50%)
}

impl LiquidationEngine {
    pub fn new() -> Self {
        Self {
            close_factor: dec!(0.5),
        }
    }

    /// Calculate liquidation metrics for a specific debt and collateral pair
    pub fn calculate_liquidation(
        &self,
        debt_amount: Decimal,
        debt_price: Decimal,
        collateral_price: Decimal,
        risk_params: &AssetRiskParams,
    ) -> LiquidationResult {
        // 1. Determine max debt to cover
        let max_debt_to_cover = debt_amount * self.close_factor;
        let debt_value_to_cover = max_debt_to_cover * debt_price;

        // 2. Add liquidation bonus to get required collateral value
        // Collateral Value = Debt Value * (1 + Bonus)
        let bonus_multiplier = dec!(1.0) + risk_params.liquidation_bonus;
        let collateral_value_needed = debt_value_to_cover * bonus_multiplier;

        // 3. Convert value back to collateral amount
        let collateral_to_seize = collateral_value_needed / collateral_price;
        
        let liquidator_profit = (collateral_value_needed - debt_value_to_cover) / debt_price; // Value in Debt asset terms

        LiquidationResult {
            collateral_to_seize,
            debt_to_cover: max_debt_to_cover,
            liquidator_profit,
        }
    }

    /// Dutch Auction Price Discovery
    /// Price starts at (Oralce * 1.10) and decays to (Oracle * 0.90) over `duration` seconds
    pub fn get_dutch_auction_price(
        &self,
        oracle_price: Decimal,
        start_time: u64,
        current_time: u64,
        duration: u64,
    ) -> Decimal {
        if current_time < start_time {
            return oracle_price * dec!(1.10);
        }

        let elapsed = current_time - start_time;
        if elapsed >= duration {
            return oracle_price * dec!(0.90); // Floor price
        }

        let progress = Decimal::from(elapsed) / Decimal::from(duration);
        
        // Start multiplier: 1.10, End multiplier: 0.90
        // Decay = 1.10 - (progress * 0.20)
        let decay = progress * dec!(0.20);
        let multiplier = dec!(1.10) - decay;
        
        oracle_price * multiplier
    }
}

impl Default for LiquidationEngine {
    fn default() -> Self {
        Self::new()
    }
}
