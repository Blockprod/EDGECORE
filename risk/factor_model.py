"""
Phase 2.1 — Per-Pair Beta-Neutral Weights + Portfolio Beta Monitor.

Two responsibilities:
1. **Per-pair**: Adjust the hedge ratio so each pair trade has net beta ≈ 0.
   For a pair (long A, short B):
       w_B = beta_A / beta_B  (so beta_net = beta_A - w_B * beta_B = 0)
   This replaces dollar-neutral with beta-neutral at the pair level.

2. **Portfolio**: Monitor aggregate residual beta and emit warnings if
   |beta_portfolio| > threshold (complement to the existing BetaNeutralHedger
   which computes a SPY hedge overlay).
"""

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd
from structlog import get_logger

logger = get_logger(__name__)


@dataclass
class FactorModelConfig:
    """Configuration for the per-pair beta-neutral factor model."""

    benchmark_col: str = "SPY"
    """Column name (or symbol) in prices_df used as the market benchmark."""

    lookback: int = 60
    """Rolling window (bars) for beta estimation."""

    min_observations: int = 30
    """Minimum data points before computing beta."""

    max_portfolio_beta: float = 0.05
    """Target: |sum(beta_i * weight_i)| < this value."""

    beta_clip_min: float = 0.10
    """Minimum absolute beta to avoid division-by-near-zero in weight calc."""

    reestimate_interval: int = 5
    """Bars between beta re-estimations (avoid excessive computation)."""


class FactorModel:
    """
    Per-pair beta estimation and beta-neutral weight computation.

    Usage::

        fm = FactorModel()
        # At pair entry:
        ratio = fm.compute_beta_neutral_ratio(prices_df, "AAPL", "MSFT", bar_idx)
        # ratio > 1 means short more of B per unit of A

        # At portfolio level:
        beta = fm.portfolio_beta(positions, prices_df, bar_idx, portfolio_value)
    """

    def __init__(self, config: Optional[FactorModelConfig] = None):
        self.config = config or FactorModelConfig()
        self._beta_cache: Dict[str, float] = {}
        self._bars_since_estimate: int = 0
        logger.info(
            "factor_model_initialized",
            benchmark=self.config.benchmark_col,
            lookback=self.config.lookback,
            max_portfolio_beta=self.config.max_portfolio_beta,
        )

    def estimate_beta(
        self,
        prices_df: pd.DataFrame,
        symbol: str,
        bar_idx: int,
    ) -> Optional[float]:
        """Estimate rolling beta of *symbol* to the benchmark.

        Uses OLS: R_sym = alpha + beta * R_bench + eps
        over the last ``lookback`` bars ending at ``bar_idx``.
        """
        bench_col = self.config.benchmark_col
        if bench_col not in prices_df.columns or symbol not in prices_df.columns:
            return None

        start = max(0, bar_idx - self.config.lookback)
        sym_prices = prices_df[symbol].iloc[start:bar_idx + 1]
        bench_prices = prices_df[bench_col].iloc[start:bar_idx + 1]

        if len(sym_prices) < self.config.min_observations:
            return None

        sym_ret = sym_prices.pct_change().dropna().values
        bench_ret = bench_prices.pct_change().dropna().values
        n = min(len(sym_ret), len(bench_ret))
        if n < self.config.min_observations - 1:
            return None

        sym_ret = sym_ret[-n:]
        bench_ret = bench_ret[-n:]

        mask = np.isfinite(sym_ret) & np.isfinite(bench_ret)
        sym_ret = sym_ret[mask]
        bench_ret = bench_ret[mask]
        if len(sym_ret) < self.config.min_observations - 1:
            return None

        var_bench = np.var(bench_ret)
        if var_bench < 1e-15:
            return None

        cov = np.cov(sym_ret, bench_ret)[0, 1]
        beta = float(cov / var_bench)

        self._beta_cache[symbol] = beta
        return beta

    def compute_beta_neutral_ratio(
        self,
        prices_df: pd.DataFrame,
        sym_long: str,
        sym_short: str,
        bar_idx: int,
    ) -> float:
        """Compute the weight multiplier for the short leg to achieve beta neutrality.

        For a pair trade long A / short B:
            w_B = beta_A / beta_B
        so net beta = beta_A * 1.0 - beta_B * w_B = 0.

        Returns:
            Ratio > 0 (typically near 1.0). Multiply the short leg notional
            by this ratio vs the long leg. Returns 1.0 if betas unavailable.
        """
        beta_long = self.estimate_beta(prices_df, sym_long, bar_idx)
        beta_short = self.estimate_beta(prices_df, sym_short, bar_idx)

        if beta_long is None or beta_short is None:
            return 1.0

        abs_short = abs(beta_short)
        if abs_short < self.config.beta_clip_min:
            abs_short = self.config.beta_clip_min

        ratio = abs(beta_long) / abs_short

        # Clip to prevent extreme imbalances
        ratio = float(np.clip(ratio, 0.5, 2.0))

        logger.debug(
            "beta_neutral_ratio_computed",
            long=sym_long,
            short=sym_short,
            beta_long=round(beta_long, 4),
            beta_short=round(beta_short, 4),
            ratio=round(ratio, 4),
        )

        return ratio

    def portfolio_beta(
        self,
        positions: Dict[str, dict],
        prices_df: pd.DataFrame,
        bar_idx: int,
        portfolio_value: float,
    ) -> Tuple[float, bool]:
        """Compute the aggregate portfolio beta and check if within limits.

        Each position contributes: beta_sym * (notional_sym / portfolio_value).
        For a pair trade (long A, short B):
            contribution = beta_A * w_A - beta_B * w_B
        where w_X = notional_per_leg / portfolio_value.

        Returns:
            (portfolio_beta: float, is_neutral: bool)
            is_neutral is True if |portfolio_beta| <= max_portfolio_beta.
        """
        if not positions or portfolio_value <= 0:
            return 0.0, True

        total_beta = 0.0
        for _pair_key, pos in positions.items():
            sym1, sym2 = pos["sym1"], pos["sym2"]
            not_per_leg = pos["notional"] / 2.0

            beta1 = self._beta_cache.get(sym1) or self.estimate_beta(
                prices_df, sym1, bar_idx
            )
            beta2 = self._beta_cache.get(sym2) or self.estimate_beta(
                prices_df, sym2, bar_idx
            )

            if beta1 is None:
                beta1 = 1.0
            if beta2 is None:
                beta2 = 1.0

            w1 = not_per_leg / portfolio_value
            w2 = not_per_leg / portfolio_value

            if pos["side"] == "long":
                total_beta += beta1 * w1 - beta2 * w2
            else:
                total_beta += -beta1 * w1 + beta2 * w2

        is_neutral = abs(total_beta) <= self.config.max_portfolio_beta

        if not is_neutral:
            logger.warning(
                "portfolio_beta_breach",
                portfolio_beta=round(total_beta, 4),
                limit=self.config.max_portfolio_beta,
                num_positions=len(positions),
            )

        return float(total_beta), is_neutral

    def get_cached_betas(self) -> Dict[str, float]:
        """Return the current beta cache for diagnostics."""
        return dict(self._beta_cache)

    def clear_cache(self) -> None:
        """Clear the beta cache."""
        self._beta_cache.clear()


__all__ = ["FactorModel", "FactorModelConfig"]
