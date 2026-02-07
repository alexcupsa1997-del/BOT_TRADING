"""
Quantitative Finance Engines

Financial mathematics implementations:
- Black-Scholes-Merton for European options
- Greeks calculation (Delta, Gamma, Vega, Theta, Rho)
- Monte Carlo for path-dependent derivatives
- Crank-Nicolson for American options
"""

import numpy as np
from typing import Tuple, Optional
from dataclasses import dataclass
from enum import Enum
from scipy.stats import norm
from scipy.linalg import solve_banded

from loguru import logger


class OptionType(Enum):
    CALL = "call"
    PUT = "put"


@dataclass
class BSMResult:
    """Result from Black-Scholes-Merton pricing."""
    price: float
    delta: float
    gamma: float
    vega: float
    theta: float
    rho: float


class BlackScholesMerton:
    """
    Black-Scholes-Merton option pricing engine.
    
    Implements European option pricing and Greeks calculation.
    """
    
    @staticmethod
    def d1(S: float, K: float, r: float, sigma: float, T: float) -> float:
        """Calculate d1 for BSM formula."""
        if T <= 0 or sigma <= 0:
            return 0.0
        return (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    
    @staticmethod
    def d2(S: float, K: float, r: float, sigma: float, T: float) -> float:
        """Calculate d2 for BSM formula."""
        if T <= 0 or sigma <= 0:
            return 0.0
        return BlackScholesMerton.d1(S, K, r, sigma, T) - sigma * np.sqrt(T)
    
    @classmethod
    def price(
        cls,
        S: float,      # Spot price
        K: float,      # Strike price
        r: float,      # Risk-free rate
        sigma: float,  # Volatility
        T: float,      # Time to expiry (years)
        option_type: OptionType = OptionType.CALL,
    ) -> float:
        """Calculate European option price."""
        if T <= 0:
            # At expiry
            if option_type == OptionType.CALL:
                return max(S - K, 0)
            else:
                return max(K - S, 0)
        
        d1 = cls.d1(S, K, r, sigma, T)
        d2 = cls.d2(S, K, r, sigma, T)
        
        if option_type == OptionType.CALL:
            return S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
        else:
            return K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
    
    @classmethod
    def price_with_greeks(
        cls,
        S: float,
        K: float,
        r: float,
        sigma: float,
        T: float,
        option_type: OptionType = OptionType.CALL,
    ) -> BSMResult:
        """Calculate option price and all Greeks."""
        price = cls.price(S, K, r, sigma, T, option_type)
        
        if T <= 0:
            # At expiry, most Greeks are 0 or undefined
            return BSMResult(price=price, delta=0, gamma=0, vega=0, theta=0, rho=0)
        
        d1 = cls.d1(S, K, r, sigma, T)
        d2 = cls.d2(S, K, r, sigma, T)
        sqrt_T = np.sqrt(T)
        
        # Delta
        if option_type == OptionType.CALL:
            delta = norm.cdf(d1)
        else:
            delta = norm.cdf(d1) - 1
        
        # Gamma (same for calls and puts)
        gamma = norm.pdf(d1) / (S * sigma * sqrt_T)
        
        # Vega (same for calls and puts, per 1% vol change)
        vega = S * norm.pdf(d1) * sqrt_T / 100
        
        # Theta (per day, assuming 252 trading days)
        if option_type == OptionType.CALL:
            theta = (
                -S * norm.pdf(d1) * sigma / (2 * sqrt_T)
                - r * K * np.exp(-r * T) * norm.cdf(d2)
            ) / 252
        else:
            theta = (
                -S * norm.pdf(d1) * sigma / (2 * sqrt_T)
                + r * K * np.exp(-r * T) * norm.cdf(-d2)
            ) / 252
        
        # Rho (per 1% rate change)
        if option_type == OptionType.CALL:
            rho = K * T * np.exp(-r * T) * norm.cdf(d2) / 100
        else:
            rho = -K * T * np.exp(-r * T) * norm.cdf(-d2) / 100
        
        return BSMResult(
            price=price,
            delta=delta,
            gamma=gamma,
            vega=vega,
            theta=theta,
            rho=rho,
        )
    
    @classmethod
    def implied_volatility(
        cls,
        market_price: float,
        S: float,
        K: float,
        r: float,
        T: float,
        option_type: OptionType = OptionType.CALL,
        tol: float = 1e-6,
        max_iter: int = 100,
    ) -> float:
        """Calculate implied volatility using Newton-Raphson."""
        sigma = 0.2  # Initial guess
        
        for _ in range(max_iter):
            result = cls.price_with_greeks(S, K, r, sigma, T, option_type)
            diff = result.price - market_price
            
            if abs(diff) < tol:
                return sigma
            
            if result.vega == 0:
                break
            
            sigma -= diff / (result.vega * 100)  # Vega is per 1%
            sigma = max(0.01, min(5.0, sigma))  # Bound sigma
        
        return sigma


class MonteCarlo:
    """
    Monte Carlo simulator for path-dependent derivatives.
    
    Features:
    - Antithetic variates for variance reduction
    - Asian option pricing
    - Barrier option pricing
    """
    
    def __init__(
        self,
        n_paths: int = 100000,
        n_steps: int = 252,
        use_antithetic: bool = True,
        seed: Optional[int] = None,
    ):
        self.n_paths = n_paths
        self.n_steps = n_steps
        self.use_antithetic = use_antithetic
        
        if seed is not None:
            np.random.seed(seed)
    
    def simulate_paths(
        self,
        S0: float,
        r: float,
        sigma: float,
        T: float,
    ) -> np.ndarray:
        """Simulate GBM price paths."""
        dt = T / self.n_steps
        
        # Generate random shocks
        if self.use_antithetic:
            # Antithetic variates: use both Z and -Z
            n_half = self.n_paths // 2
            Z = np.random.standard_normal((n_half, self.n_steps))
            Z = np.vstack([Z, -Z])  # Antithetic pairs
        else:
            Z = np.random.standard_normal((self.n_paths, self.n_steps))
        
        # GBM: S(t+dt) = S(t) * exp((r - 0.5*sigma^2)*dt + sigma*sqrt(dt)*Z)
        drift = (r - 0.5 * sigma**2) * dt
        diffusion = sigma * np.sqrt(dt) * Z
        log_returns = drift + diffusion
        
        # Cumulative sum and exponentiate
        log_paths = np.cumsum(log_returns, axis=1)
        paths = S0 * np.exp(np.column_stack([np.zeros(self.n_paths), log_paths]))
        
        return paths
    
    def price_european(
        self,
        S0: float,
        K: float,
        r: float,
        sigma: float,
        T: float,
        option_type: OptionType = OptionType.CALL,
    ) -> Tuple[float, float]:
        """Price European option with MC (for validation)."""
        paths = self.simulate_paths(S0, r, sigma, T)
        final_prices = paths[:, -1]
        
        if option_type == OptionType.CALL:
            payoffs = np.maximum(final_prices - K, 0)
        else:
            payoffs = np.maximum(K - final_prices, 0)
        
        discount = np.exp(-r * T)
        price = discount * np.mean(payoffs)
        std_err = discount * np.std(payoffs) / np.sqrt(self.n_paths)
        
        return price, std_err
    
    def price_asian(
        self,
        S0: float,
        K: float,
        r: float,
        sigma: float,
        T: float,
        option_type: OptionType = OptionType.CALL,
        averaging: str = "arithmetic",  # or "geometric"
    ) -> Tuple[float, float]:
        """
        Price Asian option.
        
        Asian options have payoff based on average price path.
        """
        paths = self.simulate_paths(S0, r, sigma, T)
        
        if averaging == "arithmetic":
            avg_prices = np.mean(paths, axis=1)
        else:
            avg_prices = np.exp(np.mean(np.log(paths), axis=1))
        
        if option_type == OptionType.CALL:
            payoffs = np.maximum(avg_prices - K, 0)
        else:
            payoffs = np.maximum(K - avg_prices, 0)
        
        discount = np.exp(-r * T)
        price = discount * np.mean(payoffs)
        std_err = discount * np.std(payoffs) / np.sqrt(self.n_paths)
        
        return price, std_err
    
    def price_barrier(
        self,
        S0: float,
        K: float,
        r: float,
        sigma: float,
        T: float,
        barrier: float,
        option_type: OptionType = OptionType.CALL,
        barrier_type: str = "down-and-out",  # or "up-and-out", etc.
    ) -> Tuple[float, float]:
        """
        Price Barrier option.
        
        Barrier options are knocked in or out when price crosses barrier.
        """
        paths = self.simulate_paths(S0, r, sigma, T)
        final_prices = paths[:, -1]
        
        # Check barrier condition
        if "down" in barrier_type:
            barrier_hit = np.any(paths <= barrier, axis=1)
        else:
            barrier_hit = np.any(paths >= barrier, axis=1)
        
        # Calculate payoffs
        if option_type == OptionType.CALL:
            payoffs = np.maximum(final_prices - K, 0)
        else:
            payoffs = np.maximum(K - final_prices, 0)
        
        # Apply barrier condition
        if "out" in barrier_type:
            payoffs = np.where(barrier_hit, 0, payoffs)
        else:  # knock-in
            payoffs = np.where(barrier_hit, payoffs, 0)
        
        discount = np.exp(-r * T)
        price = discount * np.mean(payoffs)
        std_err = discount * np.std(payoffs) / np.sqrt(self.n_paths)
        
        return price, std_err


class CrankNicolson:
    """
    Crank-Nicolson finite difference method for American options.
    
    This method is:
    - Unconditionally stable
    - Second-order accurate in both space and time
    - Can handle early exercise (American style)
    """
    
    def __init__(
        self,
        n_space: int = 200,
        n_time: int = 200,
        s_max_mult: float = 3.0,
    ):
        self.n_space = n_space
        self.n_time = n_time
        self.s_max_mult = s_max_mult
    
    def price(
        self,
        S0: float,
        K: float,
        r: float,
        sigma: float,
        T: float,
        option_type: OptionType = OptionType.PUT,  # American puts are common
    ) -> float:
        """Price American option using Crank-Nicolson."""
        # Grid setup
        S_max = K * self.s_max_mult
        dS = S_max / self.n_space
        dt = T / self.n_time
        S = np.linspace(0, S_max, self.n_space + 1)
        
        # Terminal condition (payoff at expiry)
        if option_type == OptionType.CALL:
            V = np.maximum(S - K, 0)
        else:
            V = np.maximum(K - S, 0)
        
        # Coefficients for tridiagonal system
        j = np.arange(1, self.n_space)
        alpha = 0.25 * dt * (sigma**2 * j**2 - r * j)
        beta = -0.5 * dt * (sigma**2 * j**2 + r)
        gamma = 0.25 * dt * (sigma**2 * j**2 + r * j)
        
        # Matrices for Crank-Nicolson
        # M1 * V_new = M2 * V_old
        M1_diag = 1 - beta
        M1_lower = -alpha[1:]
        M1_upper = -gamma[:-1]
        
        M2_diag = 1 + beta
        M2_lower = alpha[1:]
        M2_upper = gamma[:-1]
        
        # Time stepping (backward)
        for _ in range(self.n_time):
            # Right-hand side from M2 * V_old
            rhs = np.zeros(self.n_space - 1)
            rhs[0] = M2_lower[0] * V[0] + M2_diag[0] * V[1] + M2_upper[0] * V[2]
            for i in range(1, self.n_space - 2):
                rhs[i] = M2_lower[i] * V[i] + M2_diag[i] * V[i+1] + M2_upper[i] * V[i+2]
            rhs[-1] = M2_lower[-1] * V[-3] + M2_diag[-1] * V[-2] + M2_upper[-1] * V[-1]
            
            # Boundary conditions
            if option_type == OptionType.PUT:
                rhs[0] += alpha[0] * K  # V(0) = K for put
                rhs[-1] += gamma[-1] * 0  # V(S_max) = 0 for put
            else:
                rhs[0] += alpha[0] * 0  # V(0) = 0 for call
                rhs[-1] += gamma[-1] * (S_max - K * np.exp(-r * dt))
            
            # Solve tridiagonal system
            ab = np.zeros((3, self.n_space - 1))
            ab[0, 1:] = M1_upper
            ab[1, :] = M1_diag
            ab[2, :-1] = M1_lower
            
            V_interior = solve_banded((1, 1), ab, rhs)
            
            # Update with boundary conditions
            V[1:-1] = V_interior
            if option_type == OptionType.PUT:
                V[0] = K
                V[-1] = 0
            else:
                V[0] = 0
                V[-1] = S_max - K
            
            # Early exercise check (American style)
            if option_type == OptionType.CALL:
                exercise_value = np.maximum(S - K, 0)
            else:
                exercise_value = np.maximum(K - S, 0)
            V = np.maximum(V, exercise_value)
        
        # Interpolate to get price at S0
        idx = int(S0 / dS)
        if idx >= self.n_space:
            return V[-1]
        if idx <= 0:
            return V[0]
        
        # Linear interpolation
        weight = (S0 - S[idx]) / dS
        return V[idx] * (1 - weight) + V[idx + 1] * weight
