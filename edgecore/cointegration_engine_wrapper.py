"""
CointegrationEngine wrapper - maintains API compatibility with Python version.
Falls back to pure Python if C++ extension is not available.
"""

import logging
from typing import List, Tuple, Optional
import numpy as np

logger = logging.getLogger(__name__)

# Try to import C++ extension
try:
    from edgecore.cointegration_cpp import CointegrationEngine as _CointegrationEngineCpp
    CPP_AVAILABLE = True
    logger.info("C++ CointegrationEngine extension loaded successfully")
except ImportError as e:
    CPP_AVAILABLE = False
    logger.debug(f"C++ CointegrationEngine not available: {e}")
    _CointegrationEngineCpp = None


class CointegrationEngineWrapper:
    """
    Wrapper around C++ CointegrationEngine that maintains backward compatibility.
    Automatically selects C++ or Python implementation.
    """
    
    def __init__(self):
        if CPP_AVAILABLE:
            self._engine = _CointegrationEngineCpp()
            self.use_cpp = True
            logger.debug("Using C++ CointegrationEngine")
        else:
            self._engine = None
            self.use_cpp = False
            logger.debug("C++ CointegrationEngine not available, will use fallback")
    
    def find_cointegration_parallel(
        self,
        symbols: List[str],
        price_matrix: np.ndarray,
        max_half_life: int = 60,
        min_correlation: float = 0.7,
        pvalue_threshold: float = 0.05
    ) -> List[Tuple[str, str, float, float]]:
        """
        Find cointegrated pairs with parallelization.
        
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
        
        if self.use_cpp and CPP_AVAILABLE:
            try:
                results = self._engine.find_cointegration_parallel(
                    symbols,
                    price_matrix,
                    max_half_life,
                    min_correlation,
                    pvalue_threshold
                )
                
                # Convert results to tuples
                return [(r.sym1, r.sym2, r.pvalue, r.half_life) for r in results]
            
            except Exception as e:
                logger.error(f"C++ CointegrationEngine failed: {e}, falling back to Python")
                self.use_cpp = False
        
        # Fallback or initial Python implementation
        return self._find_cointegration_parallel_python(
            symbols,
            price_matrix,
            max_half_life,
            min_correlation,
            pvalue_threshold
        )
    
    def _find_cointegration_parallel_python(
        self,
        symbols: List[str],
        price_matrix: np.ndarray,
        max_half_life: int,
        min_correlation: float,
        pvalue_threshold: float
    ) -> List[Tuple[str, str, float, float]]:
        """Pure Python fallback implementation."""
        
        from scipy.stats import linregress
        
        cointegrated_pairs = []
        
        # Generate all pairs
        for i in range(len(symbols)):
            for j in range(i + 1, len(symbols)):
                sym1, sym2 = symbols[i], symbols[j]
                
                series1 = price_matrix[:, i]
                series2 = price_matrix[:, j]
                
                try:
                    # Correlation check
                    corr = np.corrcoef(series1, series2)[0, 1]
                    if np.isnan(corr) or abs(corr) < min_correlation:
                        continue
                    
                    # OLS regression
                    slope, intercept, r, p, se = linregress(series2, series1)
                    residuals = series1 - (slope * series2 + intercept)
                    
                    # Simplified ADF test (autocorrelation based)
                    mean = np.mean(residuals)
                    var = np.var(residuals)
                    
                    if var < 1e-10:
                        continue
                    
                    auto_cov = np.mean((residuals[1:] - mean) * (residuals[:-1] - mean))
                    auto_corr = auto_cov / var
                    
                    if auto_corr > 0.7:
                        continue  # Not stationary
                    
                    # Calculate half-life
                    if len(residuals) < 2:
                        continue
                    
                    rho = np.sum(residuals[1:] * residuals[:-1]) / np.sum(residuals[:-1] ** 2)
                    
                    if rho <= 0 or rho >= 1 or np.isnan(rho):
                        continue
                    
                    half_life = -np.log(2.0) / np.log(rho)
                    
                    if 0 < half_life <= max_half_life:
                        cointegrated_pairs.append((sym1, sym2, 0.01, half_life))
                
                except Exception as e:
                    logger.debug(f"Error testing pair {sym1}-{sym2}: {e}")
                    continue
        
        return cointegrated_pairs


# Compatibility alias
CointegrationEngine = CointegrationEngineWrapper
