//! SIMD Optimizations for Price Calculations.
//! Uses portable SIMD (if available) or auto-vectorization friendly loops.


#[cfg(all(target_arch = "x86_64", target_feature = "avx2"))]
use std::arch::x86_64::*;

pub struct SimdMath;

impl SimdMath {
    /// Calculate total value of a batch of orders (price * quantity)
    /// Optimized for auto-vectorization by processing in flat arrays.
    pub fn batch_value(prices: &[f64], quantities: &[f64]) -> Vec<f64> {
        assert_eq!(prices.len(), quantities.len());
        let mut results = vec![0.0; prices.len()];

        // Compiler auto-vectorization should pick this up
        for i in 0..prices.len() {
            results[i] = prices[i] * quantities[i];
        }

        results
    }

    /// explicit AVX2 implementation for x86_64 if enabled
    #[cfg(all(target_arch = "x86_64", target_feature = "avx2"))]
    pub unsafe fn batch_value_avx2(prices: &[f64], quantities: &[f64]) -> Vec<f64> {
        let n = prices.len();
        let mut results = vec![0.0; n];

        let mut i = 0;
        // Process 4 doubles (256-bit) at a time
        while i + 4 <= n {
            let p_vec = _mm256_loadu_pd(prices.as_ptr().add(i));
            let q_vec = _mm256_loadu_pd(quantities.as_ptr().add(i));

            let mul_vec = _mm256_mul_pd(p_vec, q_vec);

            _mm256_storeu_pd(results.as_mut_ptr().add(i), mul_vec);
            i += 4;
        }

        // Tail
        for j in i..n {
            results[j] = prices[j] * quantities[j];
        }

        results
    }
}
