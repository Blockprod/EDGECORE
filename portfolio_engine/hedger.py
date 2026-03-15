"""
Portfolio Hedger ÔÇö Beta-neutral hedging and PCA factor monitoring.

Composes:
    1. BetaNeutralHedger  ÔÇö Hedges residual market beta via benchmark ETF
    2. PCASpreadMonitor   ÔÇö Detects hidden factor concentration across spreads
    3. SpreadCorrelationGuard ÔÇö Rejects entries correlated with existing positions

These three layers work together to ensure the portfolio maintains
genuine diversification, not just position-count diversification.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

import pandas as pd
from structlog import get_logger

from risk.beta_neutral import BetaNeutralHedger, BetaNeutralConfig
from risk.pca_spread_monitor import PCASpreadMonitor, PCASpreadConfig
from risk.spread_correlation import SpreadCorrelationGuard, SpreadCorrelationConfig

logger = get_logger(__name__)


class PortfolioHedger:
    """
    Unified portfolio hedging and diversification enforcement.

    Usage::

        hedger = PortfolioHedger()

        # On position entry:
        hedger.register_spread("AAPL_MSFT", spread_series)

        # Before new entry:
        ok, reason = hedger.check_diversification("JPM_BAC", candidate_spread)

        # Periodic beta check:
        hedge_rec = hedger.compute_beta_hedge(port_returns, bench_returns, nav)
    """

    def __init__(
        self,
        max_correlation: float = 0.60,
        max_pc1_variance: float = 0.50,
        max_beta: float = 0.10,
        benchmark_symbol: str = "SPY",
    ):
        self.corr_guard = SpreadCorrelationGuard(
            SpreadCorrelationConfig(max_correlation=max_correlation),
        )
        self.pca_monitor = PCASpreadMonitor(
            PCASpreadConfig(max_pc1_variance=max_pc1_variance),
        )
        self.beta_hedger = BetaNeutralHedger(
            BetaNeutralConfig(
                benchmark_symbol=benchmark_symbol,
                max_beta=max_beta,
            ),
        )

        logger.info(
            "portfolio_hedger_initialized",
            max_corr=max_correlation,
            max_pc1=max_pc1_variance,
            max_beta=max_beta,
        )

    # ------------------------------------------------------------------
    # Spread registration
    # ------------------------------------------------------------------

    def register_spread(self, pair_key: str, spread: pd.Series) -> None:
        """Register a spread for correlation and PCA monitoring."""
        self.corr_guard.register_spread(pair_key, spread)
        self.pca_monitor.register_spread(pair_key, spread)

    def remove_spread(self, pair_key: str) -> None:
        """Remove a spread on position exit."""
        self.corr_guard.remove_spread(pair_key)
        self.pca_monitor.remove_spread(pair_key)

    # ------------------------------------------------------------------
    # Pre-entry diversification check
    # ------------------------------------------------------------------

    def check_diversification(
        self,
        pair_key: str,
        candidate_spread: pd.Series,
    ) -> Tuple[bool, str]:
        """
        Check if a new pair would degrade portfolio diversification.

        Runs both the pairwise correlation guard and the PCA factor
        concentration check.

        Returns:
            (allowed, reason).
        """
        # Pairwise correlation check
        corr_ok, corr_reason = self.corr_guard.check_entry(pair_key, candidate_spread)
        if not corr_ok:
            return False, corr_reason or "Spread too correlated with existing positions"

        # PCA factor concentration check
        pca_ok, pca_reason = self.pca_monitor.check_entry(pair_key, candidate_spread)
        if not pca_ok:
            return False, pca_reason or "Portfolio factor-concentrated (PC1)"

        return True, ""

    # ------------------------------------------------------------------
    # Beta-neutral hedging
    # ------------------------------------------------------------------

    def compute_beta_hedge(
        self,
        portfolio_returns: pd.Series,
        benchmark_returns: pd.Series,
        portfolio_value: float,
    ) -> Dict[str, Any]:
        """
        Compute benchmark hedge recommendation.

        Returns:
            Dict with ``action``, ``notional``, ``beta``, ``hedge_ratio``.
        """
        return self.beta_hedger.compute_hedge(
            portfolio_returns=portfolio_returns,
            benchmark_returns=benchmark_returns,
            portfolio_value=portfolio_value,
        )

    def get_beta(self) -> Optional[float]:
        """Return the last estimated portfolio beta."""
        return self.beta_hedger._last_beta
