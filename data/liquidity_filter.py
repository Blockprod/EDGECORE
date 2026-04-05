"""
Dynamic liquidity filter for pair trading universe.

<<<<<<< HEAD
Sprint 2.4 (M-04) ��� Eliminates survivorship/selection bias by filtering
=======
Sprint 2.4 (M-04) – Eliminates survivorship/selection bias by filtering
>>>>>>> origin/main
symbols with insufficient liquidity before pair discovery.

Key rules:
  - Minimum 24h volume threshold (default: $5M)
  - Volume estimated from rolling 30-day average
  - Configurable via LiquidityConfig
"""

<<<<<<< HEAD
from dataclasses import dataclass

import pandas as pd
=======
import pandas as pd
from dataclasses import dataclass
from typing import List, Dict, Optional
>>>>>>> origin/main
from structlog import get_logger

logger = get_logger(__name__)


@dataclass
class LiquidityConfig:
    """Liquidity filter parameters."""
<<<<<<< HEAD

    min_volume_24h_usd: float = 5_000_000  # $5M minimum daily volume
    volume_lookback_days: int = 30  # Rolling window for avg volume
    strict_mode: bool = False  # If True, reject symbols without volume data
=======
    min_volume_24h_usd: float = 5_000_000  # $5M minimum daily volume
    volume_lookback_days: int = 30          # Rolling window for avg volume
    strict_mode: bool = False               # If True, reject symbols without volume data
>>>>>>> origin/main


class LiquidityFilter:
    """
    Filter symbols by minimum liquidity requirements.
<<<<<<< HEAD

=======
    
>>>>>>> origin/main
    Prevents trading illiquid tokens that cause:
    - High slippage beyond cost model estimates
    - Difficulty entering/exiting positions
    - Survivorship bias in backtests
<<<<<<< HEAD

    Usage::

=======
    
    Usage::
    
>>>>>>> origin/main
        lf = LiquidityFilter()
        safe_symbols = lf.filter_symbols(
            symbols=["AAPL", "PENNY_STOCK"],
            volume_data={"AAPL": 1e9, "PENNY_STOCK": 50_000}
        )
        # Returns: ["AAPL"]
    """

<<<<<<< HEAD
    def __init__(self, config: LiquidityConfig | None = None):
        self.config = config or LiquidityConfig()
        self.rejection_log: list[dict] = []

=======
    def __init__(self, config: Optional[LiquidityConfig] = None):
        self.config = config or LiquidityConfig()
        self.rejection_log: List[Dict] = []
        
>>>>>>> origin/main
        logger.info(
            "liquidity_filter_initialized",
            min_volume_24h_usd=self.config.min_volume_24h_usd,
            volume_lookback_days=self.config.volume_lookback_days,
            strict_mode=self.config.strict_mode,
        )

    def filter_symbols(
        self,
<<<<<<< HEAD
        symbols: list[str],
        volume_data: dict[str, float] | None = None,
        price_data: pd.DataFrame | None = None,
        volume_df: pd.DataFrame | None = None,
    ) -> list[str]:
        """
        Filter symbols by liquidity.

        Accepts volume in multiple formats:
        - volume_data: Dict mapping symbol ��� avg 24h volume in USD
        - volume_df: DataFrame with symbol columns and daily volume rows
        - price_data: DataFrame with a MultiIndex or 'volume' attribute (fallback)

        If no volume info available and strict_mode is False, symbol passes.

=======
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
        
>>>>>>> origin/main
        Args:
            symbols: List of symbol tickers to filter
            volume_data: Pre-computed {symbol: avg_volume} dict
            price_data: Price DataFrame (used as fallback)
            volume_df: Volume DataFrame with daily volumes per symbol
<<<<<<< HEAD

=======
            
>>>>>>> origin/main
        Returns:
            List of symbols that pass the liquidity filter
        """
        self.rejection_log.clear()
        accepted = []
<<<<<<< HEAD

        for sym in symbols:
            vol = self._get_volume(sym, volume_data, volume_df, price_data)

=======
        
        for sym in symbols:
            vol = self._get_volume(sym, volume_data, volume_df, price_data)
            
>>>>>>> origin/main
            if vol is None:
                if self.config.strict_mode:
                    self._reject(sym, "no_volume_data", 0.0)
                    continue
                else:
<<<<<<< HEAD
                    # No volume info ��� accept (best effort)
                    accepted.append(sym)
                    continue

=======
                    # No volume info ↓ accept (best effort)
                    accepted.append(sym)
                    continue
            
>>>>>>> origin/main
            if vol >= self.config.min_volume_24h_usd:
                accepted.append(sym)
            else:
                self._reject(sym, "below_min_volume", vol)
<<<<<<< HEAD

=======
        
>>>>>>> origin/main
        logger.info(
            "liquidity_filter_applied",
            total_symbols=len(symbols),
            accepted=len(accepted),
            rejected=len(self.rejection_log),
            min_volume_threshold=self.config.min_volume_24h_usd,
        )
<<<<<<< HEAD

=======
        
>>>>>>> origin/main
        return accepted

    def _get_volume(
        self,
        symbol: str,
<<<<<<< HEAD
        volume_data: dict[str, float] | None,
        volume_df: pd.DataFrame | None,
        price_data: pd.DataFrame | None,
    ) -> float | None:
=======
        volume_data: Optional[Dict[str, float]],
        volume_df: Optional[pd.DataFrame],
        price_data: Optional[pd.DataFrame],
    ) -> Optional[float]:
>>>>>>> origin/main
        """Extract average volume for a symbol from available sources."""
        # Source 1: explicit dict
        if volume_data is not None and symbol in volume_data:
            return volume_data[symbol]
<<<<<<< HEAD

=======
        
>>>>>>> origin/main
        # Source 2: volume DataFrame
        if volume_df is not None and symbol in volume_df.columns:
            tail = volume_df[symbol].dropna().tail(self.config.volume_lookback_days)
            if len(tail) > 0:
                return float(tail.mean())
<<<<<<< HEAD

        # Source 3: price_data with volume attribute (rare, exchange-specific)
        if price_data is not None and symbol in price_data.columns:
            col = price_data[symbol]
            if hasattr(col, "volume"):
                tail = col.tail(self.config.volume_lookback_days)
                if len(tail) > 0:
                    return float(tail.mean())

=======
        
        # Source 3: price_data with volume attribute (rare, exchange-specific)
        if price_data is not None and symbol in price_data.columns:
            col = price_data[symbol]
            if hasattr(col, 'volume'):
                tail = col.tail(self.config.volume_lookback_days)
                if len(tail) > 0:
                    return float(tail.mean())
        
>>>>>>> origin/main
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

<<<<<<< HEAD
    def get_rejection_summary(self) -> list[dict]:
=======
    def get_rejection_summary(self) -> List[Dict]:
>>>>>>> origin/main
        """Get list of rejected symbols with reasons."""
        return list(self.rejection_log)
