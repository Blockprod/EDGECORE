"""
Dynamic liquidity filter for pair trading universe.

Sprint 2.4 (M-04) – Eliminates survivorship/selection bias by filtering
symbols with insufficient liquidity before pair discovery.

Key rules:
  - Minimum 24h volume threshold (default: $5M)
  - Volume estimated from rolling 30-day average
  - Configurable via LiquidityConfig
"""

import pandas as pd
from dataclasses import dataclass
from typing import List, Dict, Optional
from structlog import get_logger

logger = get_logger(__name__)


@dataclass
class LiquidityConfig:
    """Liquidity filter parameters."""
    min_volume_24h_usd: float = 5_000_000  # $5M minimum daily volume
    volume_lookback_days: int = 30          # Rolling window for avg volume
    strict_mode: bool = False               # If True, reject symbols without volume data


class LiquidityFilter:
    """
    Filter symbols by minimum liquidity requirements.
    
    Prevents trading illiquid tokens that cause:
    - High slippage beyond cost model estimates
    - Difficulty entering/exiting positions
    - Survivorship bias in backtests
    
    Usage::
    
        lf = LiquidityFilter()
        safe_symbols = lf.filter_symbols(
            symbols=["AAPL", "PENNY_STOCK"],
            volume_data={"AAPL": 1e9, "PENNY_STOCK": 50_000}
        )
        # Returns: ["AAPL"]
    """

    def __init__(self, config: Optional[LiquidityConfig] = None):
        self.config = config or LiquidityConfig()
        self.rejection_log: List[Dict] = []
        
        logger.info(
            "liquidity_filter_initialized",
            min_volume_24h_usd=self.config.min_volume_24h_usd,
            volume_lookback_days=self.config.volume_lookback_days,
            strict_mode=self.config.strict_mode,
        )

    def filter_symbols(
        self,
        symbols: List[str],
        volume_data: Optional[Dict[str, float]] = None,
        price_data: Optional[pd.DataFrame] = None,
        volume_df: Optional[pd.DataFrame] = None,
    ) -> List[str]:
        """
        Filter symbols by liquidity.
        
        Accepts volume in multiple formats:
        - volume_data: Dict mapping symbol ↓ avg 24h volume in USD
        - volume_df: DataFrame with symbol columns and daily volume rows
        - price_data: DataFrame with a MultiIndex or 'volume' attribute (fallback)
        
        If no volume info available and strict_mode is False, symbol passes.
        
        Args:
            symbols: List of symbol tickers to filter
            volume_data: Pre-computed {symbol: avg_volume} dict
            price_data: Price DataFrame (used as fallback)
            volume_df: Volume DataFrame with daily volumes per symbol
            
        Returns:
            List of symbols that pass the liquidity filter
        """
        self.rejection_log.clear()
        accepted = []
        
        for sym in symbols:
            vol = self._get_volume(sym, volume_data, volume_df, price_data)
            
            if vol is None:
                if self.config.strict_mode:
                    self._reject(sym, "no_volume_data", 0.0)
                    continue
                else:
                    # No volume info ↓ accept (best effort)
                    accepted.append(sym)
                    continue
            
            if vol >= self.config.min_volume_24h_usd:
                accepted.append(sym)
            else:
                self._reject(sym, "below_min_volume", vol)
        
        logger.info(
            "liquidity_filter_applied",
            total_symbols=len(symbols),
            accepted=len(accepted),
            rejected=len(self.rejection_log),
            min_volume_threshold=self.config.min_volume_24h_usd,
        )
        
        return accepted

    def _get_volume(
        self,
        symbol: str,
        volume_data: Optional[Dict[str, float]],
        volume_df: Optional[pd.DataFrame],
        price_data: Optional[pd.DataFrame],
    ) -> Optional[float]:
        """Extract average volume for a symbol from available sources."""
        # Source 1: explicit dict
        if volume_data is not None and symbol in volume_data:
            return volume_data[symbol]
        
        # Source 2: volume DataFrame
        if volume_df is not None and symbol in volume_df.columns:
            tail = volume_df[symbol].dropna().tail(self.config.volume_lookback_days)
            if len(tail) > 0:
                return float(tail.mean())
        
        # Source 3: price_data with volume attribute (rare, exchange-specific)
        if price_data is not None and symbol in price_data.columns:
            col = price_data[symbol]
            if hasattr(col, 'volume'):
                tail = col.tail(self.config.volume_lookback_days)
                if len(tail) > 0:
                    return float(tail.mean())
        
        return None

    def _reject(self, symbol: str, reason: str, volume: float) -> None:
        """Log rejection."""
        entry = {
            "symbol": symbol,
            "reason": reason,
            "volume_24h": volume,
            "threshold": self.config.min_volume_24h_usd,
        }
        self.rejection_log.append(entry)
        logger.warning(
            "liquidity_filter_rejected",
            symbol=symbol,
            reason=reason,
            volume_24h=round(volume, 0),
            threshold=self.config.min_volume_24h_usd,
        )

    def get_rejection_summary(self) -> List[Dict]:
        """Get list of rejected symbols with reasons."""
        return list(self.rejection_log)
