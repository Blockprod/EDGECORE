import pytest
import pandas as pd
import numpy as np
from models.cointegration import engle_granger_test, half_life_mean_reversion

def test_engle_granger_cointegrated_series():
    """Test EG test on known cointegrated pair."""
    np.random.seed(42)
    n = 252
    
    # Create cointegrated pair: y = 2*x + noise
    x = np.cumsum(np.random.randn(n))
    y = 2 * x + np.random.randn(n) * 0.1
    
    result = engle_granger_test(pd.Series(y), pd.Series(x))
    
    assert result['is_cointegrated']
    assert result['adf_pvalue'] < 0.05
    assert abs(result['beta'] - 2.0) < 0.2

def test_half_life_mean_reversion():
    """Test half-life calculation with AR(1) process."""
    np.random.seed(42)
    
    # Generate a true AR(1) process: spread_t = rho * spread_{t-1} + eps
    rho_true = 0.95
    n = 500
    
    spread = np.zeros(n)
    spread[0] = np.random.randn()
    
    for t in range(1, n):
        spread[t] = rho_true * spread[t-1] + 0.05 * np.random.randn()
    
    # Compute half-life
    hl = half_life_mean_reversion(pd.Series(spread))
    
    # Should return a valid half-life for this mean-reverting process
    assert hl is not None, "half_life_mean_reversion should return valid value for AR(1) process"
    assert isinstance(hl, int), f"half_life should be int, got {type(hl)}"
    assert hl > 0, f"Half-life should be positive, got {hl}"
    
    # For rho=0.95, theoretical HL = -ln(2)/ln(0.95) ≈ 13.5 days
    # With estimation error, allow reasonable range (5-25 days)
    assert 5 <= hl <= 25, f"Half-life {hl} outside expected range for rho≈0.95 (should be ~13)"




if __name__ == "__main__":
    test_engle_granger_cointegrated_series()
    test_half_life_mean_reversion()
    print("✓ All tests passed")
