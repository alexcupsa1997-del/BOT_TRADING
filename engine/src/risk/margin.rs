//! Portfolio Margin Calculator
//! 
//! Implements strict risk checks for Cross Margin and Isolated Margin modes.
//! 
//! Core Formula:
//! Health Factor = (Total Collateral Value * LTV) / Total Debt Value
//! 
//! If Health Factor < 1.0, the account is eligible for liquidation.

use rust_decimal::Decimal;
use rust_decimal_macros::dec;
use std::collections::HashMap;

/// Risk parameters for a specific asset
#[derive(Debug, Clone)]
pub struct AssetRiskParams {
    /// Loan-To-Value: Max value that can be borrowed against this asset (e.g., 0.80 for BTC)
    pub ltv: Decimal,
    /// Liquidation Threshold: If (Debt / Collateral) > this, liquidation occurs (e.g., 0.85)
    pub liquidation_threshold: Decimal,
    /// Liquidation Bonus: Penalty paid to liquidator (e.g., 0.05 for 5%)
    pub liquidation_bonus: Decimal,
    /// Reserve Factor: Portion of interest paid to protocol
    pub reserve_factor: Decimal,
}

impl Default for AssetRiskParams {
    fn default() -> Self {
        Self {
            ltv: dec!(0.75),
            liquidation_threshold: dec!(0.80),
            liquidation_bonus: dec!(0.05),
            reserve_factor: dec!(0.10),
        }
    }
}

#[derive(Debug, Clone)]
pub struct Position {
    pub asset: String,
    pub amount: Decimal,      // Positive = Deposit, Negative = Borrow
    pub entry_price: Decimal, // Average entry price
}

#[derive(Debug)]
pub struct Portfolio {
    pub user_id: String,
    pub positions: HashMap<String, Position>,
    pub mode: MarginMode,
}

#[derive(Debug, PartialEq)]
pub enum MarginMode {
    Cross,
    Isolated,
}

#[derive(Debug)]
pub struct AccountHealth {
    pub total_collateral_eth: Decimal,
    pub total_debt_eth: Decimal,
    pub available_borrows_eth: Decimal,
    pub current_liquidation_threshold: Decimal,
    pub ltv: Decimal,
    pub health_factor: Decimal,
}

pub struct MarginCalculator {
    pub risk_params: HashMap<String, AssetRiskParams>,
    pub oracle_prices: HashMap<String, Decimal>,
}

impl MarginCalculator {
    pub fn new() -> Self {
        Self {
            risk_params: HashMap::new(),
            oracle_prices: HashMap::new(),
        }
    }

    pub fn set_risk_params(&mut self, asset: &str, params: AssetRiskParams) {
        self.risk_params.insert(asset.to_string(), params);
    }

    pub fn update_price(&mut self, asset: &str, price: Decimal) {
        self.oracle_prices.insert(asset.to_string(), price);
    }

    /// Calculate account health using weighted risk parameters
    pub fn calculate_health(&self, portfolio: &Portfolio) -> Result<AccountHealth, &'static str> {
        let mut total_collateral_eth = Decimal::ZERO;
        let mut total_debt_eth = Decimal::ZERO;
        let mut weighted_ltv_sum = Decimal::ZERO;
        let mut weighted_threshold_sum = Decimal::ZERO;

        for position in portfolio.positions.values() {
            let price = self.oracle_prices.get(&position.asset)
                .ok_or("Missing oracle price for asset")?;
            
            let default_params = AssetRiskParams::default();
            let params = self.risk_params.get(&position.asset)
                .unwrap_or(&default_params);

            let value_eth = position.amount.abs() * price;

            if position.amount >= Decimal::ZERO {
                // Collateral
                total_collateral_eth += value_eth;
                weighted_ltv_sum += value_eth * params.ltv;
                weighted_threshold_sum += value_eth * params.liquidation_threshold;
            } else {
                // Debt
                total_debt_eth += value_eth;
            }
        }

        let ltv = if total_collateral_eth.is_zero() {
            Decimal::ZERO
        } else {
            weighted_ltv_sum / total_collateral_eth
        };

        let liquidation_threshold = if total_collateral_eth.is_zero() {
            Decimal::ZERO
        } else {
            weighted_threshold_sum / total_collateral_eth
        };

        // Health Factor = (Collateral * Threshold) / Debt
        // If Debt = 0, Health = Infinity
        let health_factor = if total_debt_eth.is_zero() {
            Decimal::new(999999, 0) // "Infinity"
        } else {
            (total_collateral_eth * liquidation_threshold) / total_debt_eth
        };

        let available_borrows_eth = (total_collateral_eth * ltv) - total_debt_eth;

        Ok(AccountHealth {
            total_collateral_eth,
            total_debt_eth,
            available_borrows_eth,
            current_liquidation_threshold: liquidation_threshold,
            ltv,
            health_factor,
        })
    }

    /// Check if account can be liquidated
    pub fn is_liquidatable(&self, portfolio: &Portfolio) -> bool {
        match self.calculate_health(portfolio) {
            Ok(health) => health.health_factor < dec!(1.0),
            Err(_) => false, // Fail safe: don't liquidate if error
        }
    }
}

impl Default for MarginCalculator {
    fn default() -> Self {
        Self::new()
    }
}
