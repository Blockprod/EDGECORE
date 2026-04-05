"""
CointegrationEngine wrapper - maintains API compatibility.
Uses Cython-accelerated implementation with fallback to pure Python.
"""

import logging
<<<<<<< HEAD

=======
from typing import List, Tuple
>>>>>>> origin/main
import numpy as np

logger = logging.getLogger(__name__)

# Import Cython-accelerated cointegration test
from models.cointegration import engle_granger_test_cpp_optimized


class CointegrationEngineWrapper:
    """
    Wrapper for cointegration testing with Cython acceleration.
    Automatically uses Cython if compiled, Python otherwise.
    """

    def __init__(self):
        self._engine = None
        self.use_cpp = False  # Cython is transparent, not accessed via this flag
        logger.debug("CointegrationEngineWrapper using Cython-accelerated backend")
<<<<<<< HEAD

=======
    
>>>>>>> origin/main
    def find_cointegration_parallel(
        self,
        symbols: list[str],
        price_matrix: np.ndarray,
        max_half_life: int = 60,
        min_correlation: float = 0.7,
        pvalue_threshold: float = 0.05,
    ) -> list[tuple[str, str, float, float]]:
        """
        Find cointegrated pairs using Cython-accelerated testing.
<<<<<<< HEAD

=======
        
>>>>>>> origin/main
        Args:
            symbols: List of symbol names
            price_matrix: NumPy array of prices (rows=days, cols=symbols)
            max_half_life: Maximum half-life threshold
            min_correlation: Minimum correlation threshold
            pvalue_threshold: ADF test p-value threshold

        Returns:
            List of tuples (sym1, sym2, pvalue, half_life)
        """

        if price_matrix.size == 0:
            return []

        if not isinstance(price_matrix, np.ndarray):
            price_matrix = np.array(price_matrix)

        if len(price_matrix.shape) != 2:
            raise ValueError("price_matrix must be 2D")

        if price_matrix.shape[1] != len(symbols):
            raise ValueError("price_matrix columns must match symbols count")
<<<<<<< HEAD

        # Use Cython-accelerated testing (with Python fallback)
        return self._find_cointegration_parallel_optimized(
            symbols, price_matrix, max_half_life, min_correlation, pvalue_threshold
        )

=======
        
        # Use Cython-accelerated testing (with Python fallback)
        return self._find_cointegration_parallel_optimized(
            symbols,
            price_matrix,
            max_half_life,
            min_correlation,
            pvalue_threshold
        )
    
>>>>>>> origin/main
    def _find_cointegration_parallel_optimized(
        self,
        symbols: list[str],
        price_matrix: np.ndarray,
        max_half_life: int,
        min_correlation: float,
<<<<<<< HEAD
        pvalue_threshold: float,
    ) -> list[tuple[str, str, float, float]]:
        """Test pairs using Cython-accelerated engle_granger_test."""
        import pandas as pd

        cointegrated_pairs = []

=======
        pvalue_threshold: float
    ) -> List[Tuple[str, str, float, float]]:
        """Test pairs using Cython-accelerated engle_granger_test."""
        import pandas as pd
        
        cointegrated_pairs = []
        
>>>>>>> origin/main
        # Test all pairs
        for i in range(len(symbols)):
            for j in range(i + 1, len(symbols)):
                sym1, sym2 = symbols[i], symbols[j]
<<<<<<< HEAD

                try:
                    series1 = pd.Series(price_matrix[:, i])
                    series2 = pd.Series(price_matrix[:, j])

=======
                
                try:
                    series1 = pd.Series(price_matrix[:, i])
                    series2 = pd.Series(price_matrix[:, j])
                    
>>>>>>> origin/main
                    # Correlation check
                    corr = series1.corr(series2)
                    if np.isnan(corr) or abs(corr) < min_correlation:
                        continue
<<<<<<< HEAD

                    # Use Cython-accelerated test (with Bonferroni correction)
                    result = engle_granger_test_cpp_optimized(
                        series1, series2, num_symbols=len(symbols), apply_bonferroni=True
                    )

                    if result.get("is_cointegrated", False):
                        pvalue = result.get("adf_pvalue", 1.0)
                        if pvalue < pvalue_threshold:
                            # Calculate half-life from residuals if available
                            from models.cointegration import half_life_mean_reversion

                            residuals = pd.Series(result.get("residuals", []))
                            half_life = half_life_mean_reversion(residuals)

                            if half_life and half_life > 0 and half_life <= max_half_life:
                                cointegrated_pairs.append((sym1, sym2, pvalue, half_life))

=======
                    
                    # Use Cython-accelerated test (with Bonferroni correction)
                    result = engle_granger_test_cpp_optimized(
                        series1, series2,
                        num_symbols=len(symbols),
                        apply_bonferroni=True
                    )
                    
                    if result.get('is_cointegrated', False):
                        pvalue = result.get('adf_pvalue', 1.0)
                        if pvalue < pvalue_threshold:
                            # Calculate half-life from residuals if available
                            from models.cointegration import half_life_mean_reversion
                            residuals = pd.Series(result.get('residuals', []))
                            half_life = half_life_mean_reversion(residuals)
                            
                            if half_life and half_life > 0 and half_life <= max_half_life:
                                cointegrated_pairs.append((sym1, sym2, pvalue, half_life))
                
>>>>>>> origin/main
                except Exception as e:
                    logger.debug(f"Error testing pair {sym1}-{sym2}: {e}")
                    continue

        return cointegrated_pairs


# Compatibility alias
CointegrationEngine = CointegrationEngineWrapper
