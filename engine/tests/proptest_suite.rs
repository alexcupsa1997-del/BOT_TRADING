use proptest::prelude::*;

// Import your published crate's modules
use engine::domain::value_objects::{Price, Quantity};

proptest! {
    // Fuzz test that Price creation works for valid positive integers
    #[test]
    fn test_price_construction(
        integer in 0i64..1_000_000_000,
        fraction in 0i64..99_999_999
    ) {
        let price = Price::new(integer, fraction).expect("Price should be valid");

        // Basic identity check
        assert!(price.raw() >= 0);

        // Identity: integer part should match
        let recovered_int = price.raw() / 100_000_000;
        assert_eq!(recovered_int as i64, integer);
    }

    // Fuzz test for Quantity validation (must be positive) and addition
    // Quantity::from_str is the easiest entry point to test if we don't have a direct (i64, i64) constructor visible
    #[test]
    fn test_quantity_addition(
        v1 in 1i128..1_000_000_000_000,
        v2 in 1i128..1_000_000_000_000
    ) {
        let q1 = Quantity::from_raw(v1).expect("Valid raw qty");
        let q2 = Quantity::from_raw(v2).expect("Valid raw qty");

        let sum = q1 + q2;

        // Mathematical property: sum > parts (since positive)
        assert!(sum.raw() > q1.raw());
        assert!(sum.raw() > q2.raw());

        // Exact arithmetic check
        assert_eq!(sum.raw(), v1 + v2);
    }
}
