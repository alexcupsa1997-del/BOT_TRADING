//! Specification Pattern for Trading Eligibility Rules
//!
//! Decouples complex business rules from the matching engine.
//! Specifications can be composed with AND, OR, NOT.

use std::sync::Arc;
use super::value_objects::{Price, Quantity, Percentage};
use super::order_typestate::{Order, Open, OrderInfo, Side};

// =============================================================================
// Specification Trait
// =============================================================================

/// Specification pattern - encapsulates a business rule
pub trait Specification<T>: Send + Sync {
    /// Check if the candidate satisfies this specification
    fn is_satisfied_by(&self, candidate: &T) -> bool;
    
    /// Get a human-readable description of this rule
    fn description(&self) -> String;
    
    /// Explain why the specification failed (if it did)
    fn explain(&self, candidate: &T) -> Option<String> {
        if self.is_satisfied_by(candidate) {
            None
        } else {
            Some(format!("Failed: {}", self.description()))
        }
    }
}

// =============================================================================
// Composite Specifications
// =============================================================================

/// AND specification - both must be satisfied
pub struct AndSpecification<T> {
    left: Arc<dyn Specification<T>>,
    right: Arc<dyn Specification<T>>,
}

impl<T> AndSpecification<T> {
    pub fn new(left: Arc<dyn Specification<T>>, right: Arc<dyn Specification<T>>) -> Self {
        Self { left, right }
    }
}

impl<T: Send + Sync> Specification<T> for AndSpecification<T> {
    fn is_satisfied_by(&self, candidate: &T) -> bool {
        self.left.is_satisfied_by(candidate) && self.right.is_satisfied_by(candidate)
    }
    
    fn description(&self) -> String {
        format!("({} AND {})", self.left.description(), self.right.description())
    }
    
    fn explain(&self, candidate: &T) -> Option<String> {
        let left_fail = self.left.explain(candidate);
        let right_fail = self.right.explain(candidate);
        
        match (left_fail, right_fail) {
            (None, None) => None,
            (Some(l), None) => Some(l),
            (None, Some(r)) => Some(r),
            (Some(l), Some(r)) => Some(format!("{} AND {}", l, r)),
        }
    }
}

/// OR specification - at least one must be satisfied
pub struct OrSpecification<T> {
    left: Arc<dyn Specification<T>>,
    right: Arc<dyn Specification<T>>,
}

impl<T> OrSpecification<T> {
    pub fn new(left: Arc<dyn Specification<T>>, right: Arc<dyn Specification<T>>) -> Self {
        Self { left, right }
    }
}

impl<T: Send + Sync> Specification<T> for OrSpecification<T> {
    fn is_satisfied_by(&self, candidate: &T) -> bool {
        self.left.is_satisfied_by(candidate) || self.right.is_satisfied_by(candidate)
    }
    
    fn description(&self) -> String {
        format!("({} OR {})", self.left.description(), self.right.description())
    }
}

/// NOT specification - must not be satisfied
pub struct NotSpecification<T> {
    spec: Arc<dyn Specification<T>>,
}

impl<T> NotSpecification<T> {
    pub fn new(spec: Arc<dyn Specification<T>>) -> Self {
        Self { spec }
    }
}

impl<T: Send + Sync> Specification<T> for NotSpecification<T> {
    fn is_satisfied_by(&self, candidate: &T) -> bool {
        !self.spec.is_satisfied_by(candidate)
    }
    
    fn description(&self) -> String {
        format!("NOT ({})", self.spec.description())
    }
}

// =============================================================================
// Extension Trait for Fluent API
// =============================================================================

pub trait SpecificationExt<T>: Specification<T> + Sized {
    fn and(self, other: impl Specification<T> + 'static) -> AndSpecification<T>
    where
        Self: 'static,
    {
        AndSpecification::new(Arc::new(self), Arc::new(other))
    }
    
    fn or(self, other: impl Specification<T> + 'static) -> OrSpecification<T>
    where
        Self: 'static,
    {
        OrSpecification::new(Arc::new(self), Arc::new(other))
    }
    
    fn not(self) -> NotSpecification<T>
    where
        Self: 'static,
    {
        NotSpecification::new(Arc::new(self))
    }
}

impl<T, S: Specification<T>> SpecificationExt<T> for S {}

// =============================================================================
// Order Eligibility Context
// =============================================================================

/// Context for order eligibility checks
pub struct OrderContext {
    pub order: Order<Open>,
    pub user_balance: Quantity,
    pub user_daily_volume: Quantity,
    pub current_price: Price,
    pub user_tier: UserTier,
    pub is_market_open: bool,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum UserTier {
    Basic,
    Verified,
    Professional,
    Institutional,
}

// =============================================================================
// Concrete Order Specifications
// =============================================================================

/// Minimum order size specification
pub struct MinimumOrderSize {
    min_quantity: Quantity,
}

impl MinimumOrderSize {
    pub fn new(min_quantity: Quantity) -> Self {
        Self { min_quantity }
    }
}

impl Specification<OrderContext> for MinimumOrderSize {
    fn is_satisfied_by(&self, ctx: &OrderContext) -> bool {
        ctx.order.original_quantity() >= self.min_quantity
    }
    
    fn description(&self) -> String {
        format!("Order quantity >= {}", self.min_quantity)
    }
}

/// Maximum order size specification
pub struct MaximumOrderSize {
    max_quantity: Quantity,
}

impl MaximumOrderSize {
    pub fn new(max_quantity: Quantity) -> Self {
        Self { max_quantity }
    }
}

impl Specification<OrderContext> for MaximumOrderSize {
    fn is_satisfied_by(&self, ctx: &OrderContext) -> bool {
        ctx.order.original_quantity() <= self.max_quantity
    }
    
    fn description(&self) -> String {
        format!("Order quantity <= {}", self.max_quantity)
    }
}

/// Sufficient balance specification
pub struct SufficientBalance;

impl Specification<OrderContext> for SufficientBalance {
    fn is_satisfied_by(&self, ctx: &OrderContext) -> bool {
        let required = ctx.order.original_quantity().value_at(ctx.current_price);
        ctx.user_balance >= Quantity::from_raw(required.raw()).unwrap_or(Quantity::zero())
    }
    
    fn description(&self) -> String {
        "User has sufficient balance for order".to_string()
    }
}

/// Daily volume limit specification
pub struct DailyVolumeLimit {
    max_daily_volume: Quantity,
}

impl DailyVolumeLimit {
    pub fn new(max_daily_volume: Quantity) -> Self {
        Self { max_daily_volume }
    }
}

impl Specification<OrderContext> for DailyVolumeLimit {
    fn is_satisfied_by(&self, ctx: &OrderContext) -> bool {
        let new_total = ctx.user_daily_volume + ctx.order.original_quantity();
        new_total <= self.max_daily_volume
    }
    
    fn description(&self) -> String {
        format!("Daily volume <= {}", self.max_daily_volume)
    }
}

/// User tier requirement specification
pub struct RequiredUserTier {
    minimum_tier: UserTier,
}

impl RequiredUserTier {
    pub fn new(minimum_tier: UserTier) -> Self {
        Self { minimum_tier }
    }
}

impl Specification<OrderContext> for RequiredUserTier {
    fn is_satisfied_by(&self, ctx: &OrderContext) -> bool {
        tier_level(ctx.user_tier) >= tier_level(self.minimum_tier)
    }
    
    fn description(&self) -> String {
        format!("User tier >= {:?}", self.minimum_tier)
    }
}

fn tier_level(tier: UserTier) -> u8 {
    match tier {
        UserTier::Basic => 0,
        UserTier::Verified => 1,
        UserTier::Professional => 2,
        UserTier::Institutional => 3,
    }
}

/// Market hours specification
pub struct MarketIsOpen;

impl Specification<OrderContext> for MarketIsOpen {
    fn is_satisfied_by(&self, ctx: &OrderContext) -> bool {
        ctx.is_market_open
    }
    
    fn description(&self) -> String {
        "Market is open for trading".to_string()
    }
}

/// Price deviation limit (circuit breaker)
pub struct PriceDeviationLimit {
    reference_price: Price,
    max_deviation: Percentage,
}

impl PriceDeviationLimit {
    pub fn new(reference_price: Price, max_deviation: Percentage) -> Self {
        Self { reference_price, max_deviation }
    }
}

impl Specification<OrderContext> for PriceDeviationLimit {
    fn is_satisfied_by(&self, ctx: &OrderContext) -> bool {
        let order_price = match ctx.order.side() {
            Side::Buy => ctx.current_price, // For market orders, use current price
            Side::Sell => ctx.current_price,
        };
        
        let ref_raw = self.reference_price.raw();
        let price_raw = order_price.raw();
        
        if ref_raw == 0 {
            return true;
        }
        
        let deviation_bp = ((price_raw - ref_raw).abs() * 10000) / ref_raw;
        deviation_bp <= self.max_deviation.basis_points() as i128
    }
    
    fn description(&self) -> String {
        format!("Price within {}% of reference", self.max_deviation.basis_points() as f64 / 100.0)
    }
}

// =============================================================================
// Specification Registry (Rule Engine)
// =============================================================================

/// Registry of trading rules
pub struct TradingRuleEngine {
    rules: Vec<Arc<dyn Specification<OrderContext>>>,
}

impl TradingRuleEngine {
    pub fn new() -> Self {
        Self { rules: Vec::new() }
    }
    
    pub fn add_rule(&mut self, rule: impl Specification<OrderContext> + 'static) {
        self.rules.push(Arc::new(rule));
    }
    
    /// Check if order is eligible
    pub fn is_eligible(&self, ctx: &OrderContext) -> bool {
        self.rules.iter().all(|rule| rule.is_satisfied_by(ctx))
    }
    
    /// Get all failures
    pub fn get_failures(&self, ctx: &OrderContext) -> Vec<String> {
        self.rules
            .iter()
            .filter_map(|rule| rule.explain(ctx))
            .collect()
    }
    
    /// Validate and return detailed result
    pub fn validate(&self, ctx: &OrderContext) -> ValidationResult {
        let failures = self.get_failures(ctx);
        if failures.is_empty() {
            ValidationResult::Eligible
        } else {
            ValidationResult::Ineligible(failures)
        }
    }
}

impl Default for TradingRuleEngine {
    fn default() -> Self {
        Self::new()
    }
}

#[derive(Debug)]
pub enum ValidationResult {
    Eligible,
    Ineligible(Vec<String>),
}

// =============================================================================
// Factory for Common Rule Sets
// =============================================================================

pub fn create_standard_rules() -> TradingRuleEngine {
    let mut engine = TradingRuleEngine::new();
    
    // Basic order validation
    engine.add_rule(MinimumOrderSize::new(
        Quantity::from_str("0.00001").unwrap()
    ));
    engine.add_rule(MaximumOrderSize::new(
        Quantity::from_str("1000.0").unwrap()
    ));
    
    // Balance check
    engine.add_rule(SufficientBalance);
    
    // Market hours
    engine.add_rule(MarketIsOpen);
    
    engine
}

pub fn create_institutional_rules() -> TradingRuleEngine {
    let mut engine = create_standard_rules();
    
    // Require professional tier
    engine.add_rule(RequiredUserTier::new(UserTier::Professional));
    
    // Higher volume limits
    engine.add_rule(DailyVolumeLimit::new(
        Quantity::from_str("100000.0").unwrap()
    ));
    
    engine
}

// =============================================================================
// Tests
// =============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_composite_specification() {
        let min = MinimumOrderSize::new(Quantity::from_str("0.01").unwrap());
        let max = MaximumOrderSize::new(Quantity::from_str("100.0").unwrap());
        
        let combined = min.and(max);
        
        assert_eq!(
            combined.description(),
            "(Order quantity >= 0.01000000 AND Order quantity <= 100.00000000)"
        );
    }

    #[test]
    fn test_rule_engine() {
        let engine = create_standard_rules();
        
        // Engine should have multiple rules
        assert!(!engine.rules.is_empty());
    }
}
