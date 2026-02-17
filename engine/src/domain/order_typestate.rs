//! Typestate Pattern for Order State Machine
//!
//! Makes illegal order state transitions impossible at compile time.
//! You cannot cancel a filled order - the type system prevents it.

use super::value_objects::{Price, Quantity, TradingPair};
use serde::{Deserialize, Serialize};
use std::marker::PhantomData;

// =============================================================================
// Order State Types (Zero-Sized Types for State)
// =============================================================================

/// Order is pending validation
pub struct Pending;

/// Order is validated and can be matched
pub struct Open;

/// Order is partially filled
pub struct PartiallyFilled;

/// Order is completely filled (terminal state)
pub struct Filled;

/// Order is cancelled (terminal state)
pub struct Cancelled;

/// Order is rejected (terminal state)
pub struct Rejected;

/// Order has expired (terminal state)
pub struct Expired;

// =============================================================================
// Order Core Data (Shared across all states)
// =============================================================================

/// Immutable order data that doesn't change with state
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct OrderCore {
    pub id: OrderId,
    pub user_id: UserId,
    pub symbol: TradingPair,
    pub side: Side,
    pub order_type: OrderType,
    pub time_in_force: TimeInForce,
    pub original_quantity: Quantity,
    pub price: Option<Price>, // None for market orders
    pub created_at: u64,
}

/// Order ID value object
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct OrderId(pub u64);

/// User ID value object
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct UserId(pub u64);

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum Side {
    Buy,
    Sell,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum OrderType {
    Limit,
    Market,
    StopLoss,
    TakeProfit,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum TimeInForce {
    GoodTillCancelled,
    ImmediateOrCancel,
    FillOrKill,
}

// =============================================================================
// Fill Record
// =============================================================================

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Fill {
    pub fill_id: u64,
    pub price: Price,
    pub quantity: Quantity,
    pub timestamp: u64,
    pub is_maker: bool,
}

// =============================================================================
// Order with Typestate
// =============================================================================

/// Order with compile-time state tracking
///
/// The state parameter S determines what operations are available:
/// - `Order<Pending>` can be validated or rejected
/// - `Order<Open>` can be matched, cancelled, or expired
/// - `Order<PartiallyFilled>` can be filled more or cancelled
/// - `Order<Filled>` is terminal - no operations allowed
/// - `Order<Cancelled>` is terminal - no operations allowed
#[derive(Clone, Debug)]
pub struct Order<S> {
    core: OrderCore,
    filled_quantity: Quantity,
    fills: Vec<Fill>,
    #[allow(dead_code)] // Set on every transition; read when persistence is added
    updated_at: u64,
    _state: PhantomData<S>,
}

// =============================================================================
// Order Creation (Always starts as Pending)
// =============================================================================

impl Order<Pending> {
    /// Create a new order (always starts in Pending state)
    pub fn new(
        id: OrderId,
        user_id: UserId,
        symbol: TradingPair,
        side: Side,
        order_type: OrderType,
        time_in_force: TimeInForce,
        quantity: Quantity,
        price: Option<Price>,
    ) -> Self {
        let now = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .expect("Time went backwards")
            .as_millis() as u64;

        Order {
            core: OrderCore {
                id,
                user_id,
                symbol,
                side,
                order_type,
                time_in_force,
                original_quantity: quantity,
                price,
                created_at: now,
            },
            filled_quantity: Quantity::zero(),
            fills: Vec::new(),
            updated_at: now,
            _state: PhantomData,
        }
    }

    /// Validate order and transition to Open state
    pub fn validate(self) -> Order<Open> {
        Order {
            core: self.core,
            filled_quantity: self.filled_quantity,
            fills: self.fills,
            updated_at: now(),
            _state: PhantomData,
        }
    }

    /// Reject order (terminal state)
    pub fn reject(self, _reason: &str) -> Order<Rejected> {
        Order {
            core: self.core,
            filled_quantity: self.filled_quantity,
            fills: self.fills,
            updated_at: now(),
            _state: PhantomData,
        }
    }
}

// =============================================================================
// Open Order Operations
// =============================================================================

impl Order<Open> {
    /// Fill the order (complete or partial)
    pub fn fill(self, fill: Fill) -> FillResult {
        let new_filled = self.filled_quantity + fill.quantity;
        let remaining = self.remaining_quantity();

        if fill.quantity >= remaining {
            // Complete fill
            let mut fills = self.fills;
            fills.push(fill);

            let original_quantity = self.core.original_quantity;
            FillResult::Complete(Order {
                core: self.core,
                filled_quantity: original_quantity,
                fills,
                updated_at: now(),
                _state: PhantomData,
            })
        } else {
            // Partial fill
            let mut fills = self.fills;
            fills.push(fill);

            FillResult::Partial(Order {
                core: self.core,
                filled_quantity: new_filled,
                fills,
                updated_at: now(),
                _state: PhantomData,
            })
        }
    }

    /// Cancel the order (terminal state)
    pub fn cancel(self) -> Order<Cancelled> {
        Order {
            core: self.core,
            filled_quantity: self.filled_quantity,
            fills: self.fills,
            updated_at: now(),
            _state: PhantomData,
        }
    }

    /// Expire the order (terminal state)
    pub fn expire(self) -> Order<Expired> {
        Order {
            core: self.core,
            filled_quantity: self.filled_quantity,
            fills: self.fills,
            updated_at: now(),
            _state: PhantomData,
        }
    }
}

// =============================================================================
// Partially Filled Order Operations
// =============================================================================

impl Order<PartiallyFilled> {
    /// Add another fill
    pub fn fill(self, fill: Fill) -> FillResult {
        let new_filled = self.filled_quantity + fill.quantity;
        let remaining = self.remaining_quantity();

        if fill.quantity >= remaining {
            // Complete fill
            let mut fills = self.fills;
            fills.push(fill);

            let original_quantity = self.core.original_quantity;
            FillResult::Complete(Order {
                core: self.core,
                filled_quantity: original_quantity,
                fills,
                updated_at: now(),
                _state: PhantomData,
            })
        } else {
            // Still partial
            let mut fills = self.fills;
            fills.push(fill);

            FillResult::Partial(Order {
                core: self.core,
                filled_quantity: new_filled,
                fills,
                updated_at: now(),
                _state: PhantomData,
            })
        }
    }

    /// Cancel remaining quantity
    pub fn cancel(self) -> Order<Cancelled> {
        Order {
            core: self.core,
            filled_quantity: self.filled_quantity,
            fills: self.fills,
            updated_at: now(),
            _state: PhantomData,
        }
    }
}

// =============================================================================
// Fill Result (Sum Type for Fill Outcome)
// =============================================================================

pub enum FillResult {
    Complete(Order<Filled>),
    Partial(Order<PartiallyFilled>),
}

// =============================================================================
// Common Read Operations (Available in all states via trait)
// =============================================================================

/// Trait for common order queries
pub trait OrderInfo {
    fn id(&self) -> OrderId;
    fn user_id(&self) -> UserId;
    fn symbol(&self) -> &TradingPair;
    fn side(&self) -> Side;
    fn order_type(&self) -> OrderType;
    fn original_quantity(&self) -> Quantity;
    fn filled_quantity(&self) -> Quantity;
    fn remaining_quantity(&self) -> Quantity;
    fn fills(&self) -> &[Fill];
    fn average_fill_price(&self) -> Option<Price>;
}

impl<S> OrderInfo for Order<S> {
    fn id(&self) -> OrderId {
        self.core.id
    }

    fn user_id(&self) -> UserId {
        self.core.user_id
    }

    fn symbol(&self) -> &TradingPair {
        &self.core.symbol
    }

    fn side(&self) -> Side {
        self.core.side
    }

    fn order_type(&self) -> OrderType {
        self.core.order_type
    }

    fn original_quantity(&self) -> Quantity {
        self.core.original_quantity
    }

    fn filled_quantity(&self) -> Quantity {
        self.filled_quantity
    }

    fn remaining_quantity(&self) -> Quantity {
        self.core.original_quantity - self.filled_quantity
    }

    fn fills(&self) -> &[Fill] {
        &self.fills
    }

    fn average_fill_price(&self) -> Option<Price> {
        if self.fills.is_empty() {
            return None;
        }

        let total_value: i128 = self
            .fills
            .iter()
            .map(|f| f.price.raw() * f.quantity.raw() / 100_000_000)
            .sum();

        let total_qty = self.filled_quantity.raw();
        if total_qty == 0 {
            return None;
        }

        Price::from_raw(total_value * 100_000_000 / total_qty).ok()
    }
}

// =============================================================================
// Helpers
// =============================================================================

fn now() -> u64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .expect("Time went backwards")
        .as_millis() as u64
}

// =============================================================================
// Tests
// =============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_order_lifecycle() {
        // Create order (Pending)
        let order = Order::new(
            OrderId(1),
            UserId(100),
            TradingPair::from_str("BTC-EUSD").unwrap(),
            Side::Buy,
            OrderType::Limit,
            TimeInForce::GoodTillCancelled,
            Quantity::from_str("1.0").unwrap(),
            Some(Price::from_str("50000.0").unwrap()),
        );

        // Validate -> Open
        let order = order.validate();

        // Partial fill
        let fill = Fill {
            fill_id: 1,
            price: Price::from_str("50000.0").unwrap(),
            quantity: Quantity::from_str("0.5").unwrap(),
            timestamp: 0,
            is_maker: true,
        };

        let result = order.fill(fill);

        match result {
            FillResult::Partial(order) => {
                // Can still fill more or cancel
                let _cancelled = order.cancel();
            }
            FillResult::Complete(_order) => {
                // Cannot call any methods! Compile error if we try.
                // order.cancel(); // ERROR: no method named `cancel`
            }
        }
    }
}
