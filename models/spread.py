import pandas as pd
import numpy as np
from typing import Tuple
from structlog import get_logger

logger = get_logger(__name__)

class SpreadModel:
    """Linear spread model for pair trading."""
    
    def __init__(self, y: pd.Series, x: pd.Series):
        """
        Initialize spread model via OLS regression: y = alpha + beta * x + residuals
        
        Args:
            y: Dependent series (typically first asset price)
            x: Independent series (typically second asset price)
        """
        X = np.column_stack([np.ones(len(x)), x.values])
        beta = np.linalg.lstsq(X, y.values, rcond=None)[0]
        
        self.intercept = beta[0]
        self.beta = beta[1]
        self.y = y
        self.x = x
        self.residuals = y.values - X @ beta
        self.std_residuals = np.std(self.residuals)
    
    def compute_spread(self, y: pd.Series, x: pd.Series) -> pd.Series:
        """
        Compute spread as: spread = y - (intercept + beta * x)
        
        Args:
            y: Dependent series
            x: Independent series
        
        Returns:
            Spread series
        """
        return y - (self.intercept + self.beta * x)
    
    def compute_z_score(self, spread: pd.Series, lookback: int = 20) -> pd.Series:
        """
        Compute rolling Z-score of spread.
        
        Args:
            spread: Spread series
            lookback: Rolling window size
        
        Returns:
            Z-score series
        """
        rolling_mean = spread.rolling(window=lookback).mean()
        rolling_std = spread.rolling(window=lookback).std()
        z_score = (spread - rolling_mean) / (rolling_std + 1e-8)
        return z_score
    
    def get_model_info(self) -> dict:
        """Return model parameters for inspection."""
        return {
            'intercept': self.intercept,
            'beta': self.beta,
            'residual_std': self.std_residuals,
            'residual_mean': np.mean(self.residuals)
        }
