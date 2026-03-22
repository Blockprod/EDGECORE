"""
Beta-Neutral Hedge ÔÇô Phase 3 (addresses equity migration risk).

Problem
-------
In a pair-trading portfolio on equities, each pair is dollar-neutral (long
one leg, short the other), but the **portfolio** may still have residual
beta to the broad market (SPY / SPX).  During a broad sell-off, a positive
residual beta means losses even if pairs are individually hedged.

Solution
--------
1. Estimate the portfolio's residual beta to a benchmark (default: SPY)
   by regressing the portfolio's daily returns on the benchmark's returns.
2. If |beta| > ``max_beta`` (default 0.10), compute the notional hedge
   required: ``hedge_notional = -beta ├ù portfolio_value``.
3. Express the hedge as a long or short position in the benchmark ETF.

The hedge is recalculated every ``rebalance_interval`` bars and bounded to
prevent over-hedging.

Usage::

    hedger = BetaNeutralHedger(benchmark_symbol="SPY")
    hedge = hedger.compute_hedge(portfolio_returns, benchmark_returns, portfolio_value)
    if hedge["action"] != "none":
        # execute benchmark trade
        ...
"""

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from structlog import get_logger

logger = get_logger(__name__)


@dataclass
class BetaNeutralConfig:
    """Configuration for the beta-neutral hedge."""

    benchmark_symbol: str = "SPY"
    """Benchmark ETF to hedge against."""

    max_beta: float = 0.10
    """Maximum tolerable absolute residual beta.  If |beta| exceeds
    this, a hedge is recommended."""

    lookback_window: int = 60
    """Number of daily returns used for beta estimation."""

    rebalance_interval: int = 5
    """Bars between hedge rebalancings."""

    max_hedge_pct: float = 0.20
    """Maximum hedge size as fraction of portfolio value.
    Prevents over-hedging on noisy beta estimates."""

    min_observations: int = 20
    """Minimum returns needed before estimating beta."""


class BetaNeutralHedger:
    """
    Estimates and manages a benchmark hedge to achieve market neutrality.
    """

    def __init__(self, config: BetaNeutralConfig | None = None):
        self.config = config or BetaNeutralConfig()
        self._current_hedge_notional: float = 0.0
        self._last_beta: float | None = None
        self._bars_since_rebalance: int = 0
        logger.info(
            "beta_neutral_hedger_initialized",
            benchmark=self.config.benchmark_symbol,
            max_beta=self.config.max_beta,
        )

    def estimate_beta(
        self,
        portfolio_returns: pd.Series,
        benchmark_returns: pd.Series,
    ) -> float | None:
        """Estimate the portfolio's beta to the benchmark.

        Uses OLS regression: R_portfolio = alpha + beta * R_benchmark + epsilon.

        Returns:
            beta (float) or None if insufficient data.
        """
        # Align
        common = portfolio_returns.index.intersection(benchmark_returns.index)
        if len(common) < self.config.min_observations:
            return None

        pr = portfolio_returns.loc[common].values[-self.config.lookback_window:]
        br = benchmark_returns.loc[common].values[-self.config.lookback_window:]

        n = len(pr)
        if n < self.config.min_observations:
            return None

        # Clean NaN/inf
        mask = np.isfinite(pr) & np.isfinite(br)
        pr, br = pr[mask], br[mask]
        if len(pr) < self.config.min_observations:
            return None

        # OLS
        X = np.column_stack([np.ones(len(br)), br])
        beta_vec = np.linalg.lstsq(X, pr, rcond=None)[0]
        beta = float(beta_vec[1])

        self._last_beta = beta
        return beta

    def compute_hedge(
        self,
        portfolio_returns: pd.Series,
        benchmark_returns: pd.Series,
        portfolio_value: float,
    ) -> dict[str, Any]:
        """Compute the hedge recommendation.

        Args:
            portfolio_returns: Daily return series of the pair portfolio.
            benchmark_returns: Daily return series of the benchmark.
            portfolio_value: Current portfolio NAV.

        Returns:
            Dict with 'action' ('buy'|'sell'|'none'), 'notional',
            'shares' (assuming priceÔëê1 for simplicity ÔÇô caller resolves),
            'beta', 'hedge_ratio'.
        """
        self._bars_since_rebalance += 1

        # Only rebalance at intervals (or first call)
        if (
            self._bars_since_rebalance < self.config.rebalance_interval
            and self._current_hedge_notional != 0
        ):
            return {
                "action": "hold",
                "notional": self._current_hedge_notional,
                "beta": self._last_beta,
                "hedge_ratio": self._current_hedge_notional / max(portfolio_value, 1),
            }

        beta = self.estimate_beta(portfolio_returns, benchmark_returns)
        if beta is None:
            return {"action": "none", "notional": 0.0, "beta": None, "hedge_ratio": 0.0}

        if abs(beta) <= self.config.max_beta:
            # Beta is small enough ÔÇô unwind any existing hedge
            if self._current_hedge_notional != 0:
                old_hedge = self._current_hedge_notional
                self._current_hedge_notional = 0.0
                self._bars_since_rebalance = 0
                logger.info("beta_neutral_hedge_unwound", beta=round(beta, 4))
                return {
                    "action": "unwind",
                    "notional": -old_hedge,
                    "beta": beta,
                    "hedge_ratio": 0.0,
                }
            return {"action": "none", "notional": 0.0, "beta": beta, "hedge_ratio": 0.0}

        # Need hedge: notional = -beta * portfolio_value
        raw_hedge = -beta * portfolio_value

        # Cap the hedge
        max_hedge = self.config.max_hedge_pct * portfolio_value
        capped_hedge = np.clip(raw_hedge, -max_hedge, max_hedge)

        delta = capped_hedge - self._current_hedge_notional
        self._current_hedge_notional = capped_hedge
        self._bars_since_rebalance = 0

        action = "buy" if delta > 0 else "sell"

        logger.info(
            "beta_neutral_hedge_computed",
            beta=round(beta, 4),
            raw_hedge=round(raw_hedge, 2),
            capped_hedge=round(capped_hedge, 2),
            delta=round(delta, 2),
            action=action,
        )

        return {
            "action": action,
            "notional": capped_hedge,
            "delta_notional": delta,
            "beta": beta,
            "hedge_ratio": capped_hedge / max(portfolio_value, 1),
        }

    def get_status(self) -> dict[str, Any]:
        """Get current hedge status."""
        return {
            "current_hedge_notional": self._current_hedge_notional,
            "last_beta": self._last_beta,
            "bars_since_rebalance": self._bars_since_rebalance,
            "benchmark": self.config.benchmark_symbol,
        }

    def reset(self) -> None:
        """Reset hedge state."""
        self._current_hedge_notional = 0.0
        self._last_beta = None
        self._bars_since_rebalance = 0


__all__ = [
    "BetaNeutralConfig",
    "BetaNeutralHedger",
]
