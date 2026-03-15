"""
Out-of-Sample (OOS) Validation Engine.

Prevents overfitting by validating pair discoveries against future data.
This is a critical safeguard against data snooping and curve-fitting biases
that are endemic in pair trading strategies.

Core Idea:
  1. Discover cointegrated pairs using in-sample data [t-252:t]
  2. Test if these pairs remain cointegrated in OOS period [t:t+21]
  3. Only keep pairs that pass OOS validation (70%+ cointegration persistence)
  4. This prevents trading phantom correlations

Validation Metrics:
  - Cointegration persistence rate (% of pairs that remain cointegrated OOS)
  - OOS half-life vs IS half-life (should be similar; divergence = overfitting)
  - OOS spread mean-reversion rate (should match IS for valid pairs)
"""

from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass
import pandas as pd
from structlog import get_logger
from models.cointegration import engle_granger_test, half_life_mean_reversion

logger = get_logger(__name__)


@dataclass
class OOSValidationResult:
    """Result of OOS validation for a single pair."""
    
    symbol_1: str
    symbol_2: str
    is_sample_cointegrated: bool  # Was cointegrated in-sample?
    oos_sample_cointegrated: bool  # Remains cointegrated OOS?
    is_pvalue: float  # In-sample p-value
    oos_pvalue: float  # OOS p-value
    is_half_life: Optional[float]  # In-sample half-life (days)
    oos_half_life: Optional[float]  # OOS half-life (days)
    validation_passed: bool  # Did it pass OOS acceptance criteria?
    reason: str  # Why validation passed or failed
    
    def __repr__(self):
        status = "Ô£ô PASS" if self.validation_passed else "Ô£ö FAIL"
        is_hl_str = f"{self.is_half_life:.1f}d" if self.is_half_life else "N/A"
        oos_hl_str = f"{self.oos_half_life:.1f}d" if self.oos_half_life else "N/A"
        return (
            f"{status} {self.symbol_1}_{self.symbol_2}: "
            f"IS p={self.is_pvalue:.2e} HL={is_hl_str} | "
            f"OOS p={self.oos_pvalue:.2e} HL={oos_hl_str} | "
            f"{self.reason}"
        )


class OutOfSampleValidator:
    """
    Validates pair trading strategy against out-of-sample forward data.
    
    The key insight: A pair discovered as cointegrated in [T-252:T] must remain
    cointegrated in [T:T+21] to be tradeable. Otherwise it's a false positive.
    
    Validation Rules:
      1. Pair must be cointegrated in both in-sample AND OOS periods
      2. OOS p-value should be < 0.05 (before Bonferroni)
      3. OOS half-life should be similar to IS (┬▒50% tolerance)
      4. If 70%+ of pairs pass: strategy validates as robust
      5. If <30% pass: strategy severely overfitted to backtest period
    """
    
    def __init__(
        self,
        oos_acceptance_threshold: float = 0.70,
        hl_drift_tolerance: float = 0.50,
        num_symbols: int = 100
    ):
        """
        Initialize OOS validator.
        
        Args:
            oos_acceptance_threshold: % of pairs that must validate OOS (default: 70%)
            hl_drift_tolerance: Max allowed half-life drift (default: ┬▒50%)
            num_symbols: Number of symbols in universe (for Bonferroni correction)
        """
        self.oos_acceptance_threshold = oos_acceptance_threshold
        self.hl_drift_tolerance = hl_drift_tolerance
        self.num_symbols = num_symbols
        self.validation_results: List[OOSValidationResult] = []
    
    def validate_pair(
        self,
        symbol_1: str,
        symbol_2: str,
        is_series_1: pd.Series,
        is_series_2: pd.Series,
        oos_series_1: pd.Series,
        oos_series_2: pd.Series,
        is_pvalue: float,
        is_half_life: Optional[float] = None
    ) -> OOSValidationResult:
        """
        Validate a single pair against out-of-sample data.
        
        Args:
            symbol_1, symbol_2: Pair identifiers
            is_series_1, is_series_2: In-sample price series
            oos_series_1, oos_series_2: Out-of-sample price series
            is_pvalue: In-sample cointegration p-value
            is_half_life: In-sample half-life (optional)
        
        Returns:
            OOSValidationResult with pass/fail determination
        """
        # Test cointegration OOS
        oos_result = engle_granger_test(
            oos_series_2,
            oos_series_1,
            num_symbols=self.num_symbols,
            apply_bonferroni=True
        )
        
        oos_pvalue = oos_result['adf_pvalue']
        oos_is_cointegrated = oos_result['is_cointegrated']
        
        # Calculate OOS half-life if available
        oos_half_life = None
        if oos_is_cointegrated and len(oos_result['residuals']) > 0:
            try:
                oos_half_life = half_life_mean_reversion(
                    pd.Series(oos_result['residuals'])
                )
            except Exception:
                oos_half_life = None
        
        # Determine validation status
        validation_passed, reason = self._evaluate_validation(
            is_cointegrated=is_pvalue < 0.05,  # Before Bonferroni
            oos_cointegrated=oos_is_cointegrated,
            is_half_life=is_half_life,
            oos_half_life=oos_half_life,
            is_pvalue=is_pvalue,
            oos_pvalue=oos_pvalue
        )
        
        result = OOSValidationResult(
            symbol_1=symbol_1,
            symbol_2=symbol_2,
            is_sample_cointegrated=(is_pvalue < 0.05),
            oos_sample_cointegrated=oos_is_cointegrated,
            is_pvalue=is_pvalue,
            oos_pvalue=oos_pvalue,
            is_half_life=is_half_life,
            oos_half_life=oos_half_life,
            validation_passed=validation_passed,
            reason=reason
        )
        
        self.validation_results.append(result)
        return result
    
    def _evaluate_validation(
        self,
        is_cointegrated: bool,
        oos_cointegrated: bool,
        is_half_life: Optional[float],
        oos_half_life: Optional[float],
        is_pvalue: float,
        oos_pvalue: float
    ) -> Tuple[bool, str]:
        """
        Evaluate if a pair passes OOS validation.
        
        Returns:
            (passed, reason) tuple
        """
        # Rule 1: Must be cointegrated both IS and OOS
        if not is_cointegrated:
            return False, "Not cointegrated in-sample"
        
        if not oos_cointegrated:
            return False, f"Failed OOS cointegration (p={oos_pvalue:.2e})"
        
        # Rule 2: OOS p-value should be reasonable (not just barely passing Bonferroni)
        if oos_pvalue > 0.001 and oos_pvalue < 0.05:
            # Borderline ÔÇô likely false positive
            return False, f"Weak OOS cointegration (p={oos_pvalue:.4f})"
        
        # Rule 3: Half-life should be stable (if available)
        if is_half_life and oos_half_life:
            hl_ratio = oos_half_life / is_half_life if is_half_life > 0 else float('inf')
            hl_drift = abs(1.0 - hl_ratio)
            
            if hl_drift > self.hl_drift_tolerance:
                return False, (
                    f"Half-life drifted {hl_drift:.0%} "
                    f"(IS={is_half_life:.1f}d OOS={oos_half_life:.1f}d)"
                )
        
        # Passed all checks
        return True, f"Valid pair (IS p={is_pvalue:.2e} OOS p={oos_pvalue:.2e})"
    
    def validate_pair_set(
        self,
        pairs_with_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Validate a set of discovered pairs against OOS data.
        
        Args:
            pairs_with_data: List of dicts with:
              {
                'symbol_1': str,
                'symbol_2': str,
                'is_series_1': pd.Series,
                'is_series_2': pd.Series,
                'oos_series_1': pd.Series,
                'oos_series_2': pd.Series,
                'is_pvalue': float,
                'is_half_life': float or None
              }
        
        Returns:
            Dictionary with validation statistics:
              {
                'total_pairs_tested': int,
                'valid_pairs': int,
                'invalid_pairs': int,
                'validation_rate': float,  # % valid
                'passed_pairs': list of (sym1, sym2) tuples,
                'failed_pairs': list of (sym1, sym2) tuples,
                'results': list of OOSValidationResult
              }
        """
        self.validation_results = []  # Reset
        
        for pair_data in pairs_with_data:
            self.validate_pair(
                symbol_1=pair_data['symbol_1'],
                symbol_2=pair_data['symbol_2'],
                is_series_1=pair_data['is_series_1'],
                is_series_2=pair_data['is_series_2'],
                oos_series_1=pair_data['oos_series_1'],
                oos_series_2=pair_data['oos_series_2'],
                is_pvalue=pair_data['is_pvalue'],
                is_half_life=pair_data.get('is_half_life', None)
            )
        
        # Aggregate statistics
        total = len(self.validation_results)
        passed = sum(1 for r in self.validation_results if r.validation_passed)
        failed = total - passed
        validation_rate = passed / total if total > 0 else 0.0
        
        passed_pairs = [
            (r.symbol_1, r.symbol_2)
            for r in self.validation_results
            if r.validation_passed
        ]
        
        failed_pairs = [
            (r.symbol_1, r.symbol_2)
            for r in self.validation_results
            if not r.validation_passed
        ]
        
        # Log summary
        logger.info(
            "oos_validation_complete",
            total_pairs=total,
            valid_pairs=passed,
            invalid_pairs=failed,
            validation_rate=f"{validation_rate:.1%}",
            strategy_robustness=(
                "robust" if validation_rate >= self.oos_acceptance_threshold
                else "OVERFITTED"
            )
        )
        
        # Log each failed pair for debugging
        for result in self.validation_results:
            if not result.validation_passed:
                logger.debug(
                    "oos_validation_failed",
                    pair=f"{result.symbol_1}_{result.symbol_2}",
                    reason=result.reason,
                    is_pvalue=f"{result.is_pvalue:.2e}",
                    oos_pvalue=f"{result.oos_pvalue:.2e}"
                )
        
        return {
            'total_pairs_tested': total,
            'valid_pairs': passed,
            'invalid_pairs': failed,
            'validation_rate': validation_rate,
            'passed_pairs': passed_pairs,
            'failed_pairs': failed_pairs,
            'strategy_robustness': "robust" if validation_rate >= self.oos_acceptance_threshold else "overfitted",
            'results': self.validation_results
        }
    
    def report(self) -> str:
        """
        Generate human-readable validation report.
        
        Returns:
            Formatted report string
        """
        if not self.validation_results:
            return "No validation results to report"
        
        total = len(self.validation_results)
        passed = sum(1 for r in self.validation_results if r.validation_passed)
        passed_pct = (passed / total * 100) if total > 0 else 0
        
        lines = [
            "\n" + "="*80,
            "OUT-OF-SAMPLE VALIDATION REPORT",
            "="*80,
            f"Total Pairs Tested:      {total}",
            f"Valid Pairs (OOS Pass):  {passed} ({passed_pct:.1f}%)",
            f"Invalid Pairs (OOS Fail): {total - passed} ({100-passed_pct:.1f}%)",
            "\nRobustness Assessment:   ",
            (
                f"  Ô£ô ROBUST ({passed_pct:.1f}% >= {self.oos_acceptance_threshold:.0%} threshold)"
                if passed_pct >= self.oos_acceptance_threshold * 100
                else f"  Ô£ö OVERFITTED ({passed_pct:.1f}% < {self.oos_acceptance_threshold:.0%} threshold)"
            ),
            "\nDetailed Results:",
            "-" * 80
        ]
        
        # Show all results (passed first, then failed)
        passed_results = [r for r in self.validation_results if r.validation_passed]
        failed_results = [r for r in self.validation_results if not r.validation_passed]
        
        if passed_results:
            lines.append("\nPASSED PAIRS:")
            for r in passed_results[:10]:  # Show first 10
                lines.append(f"  {r}")
            if len(passed_results) > 10:
                lines.append(f"  ... and {len(passed_results) - 10} more")
        
        if failed_results:
            lines.append("\nFAILED PAIRS:")
            for r in failed_results[:10]:  # Show first 10
                lines.append(f"  {r}")
            if len(failed_results) > 10:
                lines.append(f"  ... and {len(failed_results) - 10} more")
        
        lines.append("=" * 80 + "\n")
        
        return "\n".join(lines)


def validate_walk_forward_period(
    is_prices: pd.DataFrame,
    oos_prices: pd.DataFrame,
    discovered_pairs: List[Tuple[str, str, float, Optional[float]]],
    num_symbols: int = 100
) -> OOSValidationResult:
    """
    Convenience function to validate all discovered pairs for a walk-forward period.
    
    Args:
        is_prices: In-sample price data
        oos_prices: Out-of-sample price data
        discovered_pairs: List of (sym1, sym2, pvalue, half_life) tuples
        num_symbols: Number of symbols in universe
    
    Returns:
        Summary validation results
    """
    validator = OutOfSampleValidator(num_symbols=num_symbols)
    
    pairs_with_data = []
    for sym1, sym2, pvalue, hl in discovered_pairs:
        if sym1 in is_prices.columns and sym2 in is_prices.columns:
            if sym1 in oos_prices.columns and sym2 in oos_prices.columns:
                pairs_with_data.append({
                    'symbol_1': sym1,
                    'symbol_2': sym2,
                    'is_series_1': is_prices[sym1],
                    'is_series_2': is_prices[sym2],
                    'oos_series_1': oos_prices[sym1],
                    'oos_series_2': oos_prices[sym2],
                    'is_pvalue': pvalue,
                    'is_half_life': hl
                })
    
    return validator.validate_pair_set(pairs_with_data)
