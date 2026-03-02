"""
OOS Validation Engine — Out-of-sample validation wrapper.

Wraps :class:`validation.oos_validator.OutOfSampleValidator` behind a clean
API.  This module ensures that pair discoveries are validated against
unseen forward data before live deployment.

Key principle: A pair that is cointegrated in [T-252:T] must remain
cointegrated in [T:T+21].  If not, it is a false positive that would
lose money in production.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import pandas as pd
from structlog import get_logger

from validation.oos_validator import (
    OutOfSampleValidator,
    OOSValidationResult as _RawResult,
)

logger = get_logger(__name__)


@dataclass
class OOSConfig:
    """Configuration for OOS validation."""
    acceptance_threshold: float = 0.70    # 70% of pairs must validate
    half_life_drift_tolerance: float = 0.50  # max ±50% HL drift
    num_symbols: int = 50                    # for Bonferroni correction
    oos_window_days: int = 21                # forward test window


@dataclass
class OOSReport:
    """Aggregated OOS validation report."""
    total_pairs: int
    passed_pairs: int
    failed_pairs: int
    persistence_rate: float        # fraction of pairs that pass OOS
    strategy_validated: bool       # True if persistence_rate >= threshold
    per_pair_results: List[_RawResult] = field(default_factory=list)
    config: OOSConfig = field(default_factory=OOSConfig)

    def summary(self) -> Dict[str, Any]:
        return {
            "total_pairs": self.total_pairs,
            "passed_pairs": self.passed_pairs,
            "failed_pairs": self.failed_pairs,
            "persistence_rate": round(self.persistence_rate, 3),
            "strategy_validated": self.strategy_validated,
        }


class OOSValidationEngine:
    """
    Out-of-sample validation engine.

    Usage::

        engine = OOSValidationEngine(OOSConfig(
            acceptance_threshold=0.70,
            oos_window_days=21,
        ))

        report = engine.validate(
            pairs=[("AAPL", "MSFT"), ("KO", "PEP")],
            price_data=df,
            split_date="2023-06-01",
        )

        if report.strategy_validated:
            print("Strategy passes OOS validation")
    """

    def __init__(self, config: Optional[OOSConfig] = None):
        self.config = config or OOSConfig()
        self._validator = OutOfSampleValidator(
            oos_acceptance_threshold=self.config.acceptance_threshold,
            hl_drift_tolerance=self.config.half_life_drift_tolerance,
            num_symbols=self.config.num_symbols,
        )

    def validate(
        self,
        pairs: List[tuple],
        price_data: pd.DataFrame,
        split_date: str,
    ) -> OOSReport:
        """
        Validate a set of discovered pairs against OOS data.

        Args:
            pairs: List of (symbol_1, symbol_2) tuples to validate.
            price_data: DataFrame with columns for all symbols (prices).
            split_date: Date separating in-sample from OOS period.

        Returns:
            OOSReport with per-pair results and aggregate verdict.
        """
        split_ts = pd.Timestamp(split_date)
        is_data = price_data.loc[:split_ts]
        oos_data = price_data.loc[split_ts:]

        if oos_data.empty:
            logger.error("oos_validation_no_oos_data", split_date=split_date)
            return OOSReport(
                total_pairs=len(pairs),
                passed_pairs=0,
                failed_pairs=len(pairs),
                persistence_rate=0.0,
                strategy_validated=False,
                config=self.config,
            )

        results: List[_RawResult] = []

        for sym1, sym2 in pairs:
            if sym1 not in price_data.columns or sym2 not in price_data.columns:
                logger.warning("oos_skip_missing_symbol", sym1=sym1, sym2=sym2)
                continue

            is_s1, is_s2 = is_data[sym1].dropna(), is_data[sym2].dropna()
            oos_s1, oos_s2 = oos_data[sym1].dropna(), oos_data[sym2].dropna()

            if len(is_s1) < 30 or len(oos_s1) < 10:
                logger.warning("oos_skip_insufficient_data", sym1=sym1, sym2=sym2)
                continue

            result = self._validator.validate_pair(
                symbol_1=sym1,
                symbol_2=sym2,
                is_series_1=is_s1,
                is_series_2=is_s2,
                oos_series_1=oos_s1,
                oos_series_2=oos_s2,
                is_pvalue=0.0,  # will be recalculated internally
            )
            results.append(result)

        passed = sum(1 for r in results if r.validation_passed)
        total = max(len(results), 1)
        persistence = passed / total

        report = OOSReport(
            total_pairs=len(results),
            passed_pairs=passed,
            failed_pairs=total - passed,
            persistence_rate=persistence,
            strategy_validated=persistence >= self.config.acceptance_threshold,
            per_pair_results=results,
            config=self.config,
        )

        logger.info("oos_validation_complete", **report.summary())

        return report
