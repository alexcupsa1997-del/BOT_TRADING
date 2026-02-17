//! Order Matching Module
//!
//! Core matching engine types and algorithms.

pub mod simd;

use chrono::{DateTime, Utc};
use rust_decimal::Decimal;
use serde::{Deserialize, Serialize};
use thiserror::Error;
use uuid::Uuid;

/// Error type for matching operations
#[derive(Error, Debug, Clone)]
pub enum MatchError {
    #[error("Order not found: {0}")]
    OrderNotFound(Uuid),

    #[error("Invalid order: {0}")]
    InvalidOrder(String),

    #[error("Insufficient liquidity")]
    InsufficientLiquidity,

    #[error("Self-trade prevented")]
    SelfTradePrevented,

    #[error("Order already exists: {0}")]
    OrderAlreadyExists(Uuid),

    #[error("Market closed")]
    MarketClosed,

    #[error("Price out of bounds: {0}")]
    PriceOutOfBounds(String),
}

/// A trade execution record
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Trade {
    /// Unique trade identifier
    pub id: Uuid,
    /// Maker order ID (resting order)
    pub maker_order_id: Uuid,
    /// Taker order ID (incoming order)
    pub taker_order_id: Uuid,
    /// Trading symbol
    pub symbol: String,
    /// Execution price
    pub price: Decimal,
    /// Execution quantity
    pub quantity: Decimal,
    /// Execution timestamp
    pub timestamp: DateTime<Utc>,
}

impl Trade {
    /// Create a new trade record
    pub fn new(
        maker_order_id: Uuid,
        taker_order_id: Uuid,
        symbol: String,
        price: Decimal,
        quantity: Decimal,
    ) -> Self {
        Self {
            id: Uuid::new_v4(),
            maker_order_id,
            taker_order_id,
            symbol,
            price,
            quantity,
            timestamp: Utc::now(),
        }
    }

    /// Calculate the notional value of the trade
    pub fn notional(&self) -> Decimal {
        self.price * self.quantity
    }
}
