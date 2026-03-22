"""
Delisting guard ��� detects tokens at risk of delisting.

Sprint 2.4 (M-04) ��� Protects against trading dying tokens.

Detection criteria:
  - Volume drop > 80% over 7 days
  - Price below $0.001
  - No data for > 3 consecutive days (stale)
"""

from dataclasses import dataclass

import pandas as pd
from structlog import get_logger

logger = get_logger(__name__)


@dataclass
class DelistingConfig:
    """Delisting guard parameters."""

    volume_drop_pct_threshold: float = 80.0  # % drop over monitoring window
    volume_monitoring_days: int = 7  # Window for volume drop check
    min_price_threshold: float = 0.001  # Below this = likely dead
    max_stale_days: int = 3  # No data for N days = stale


class DelistingGuard:
    """
    Detect tokens at risk of delisting or collapse.

    Checks three conditions:
    1. Volume crash: 24h volume dropped > 80% vs 7-day average
    2. Penny stock: price < $0.001
    3. Stale data: no price updates in > 3 days

    Usage::

        guard = DelistingGuard()
        safe = guard.is_safe("ENRN", price_series, volume_series)
        # Returns: (True/False, reason_string)
    """

    def __init__(self, config: DelistingConfig | None = None):
        self.config = config or DelistingConfig()
        logger.info(
            "delisting_guard_initialized",
            volume_drop_threshold_pct=self.config.volume_drop_pct_threshold,
            min_price=self.config.min_price_threshold,
            max_stale_days=self.config.max_stale_days,
        )

    def is_safe(
        self,
        symbol: str,
        price_series: pd.Series | None = None,
        volume_series: pd.Series | None = None,
    ) -> tuple:
        """
        Check if a symbol is safe to trade (not at risk of delisting).

        Args:
            symbol: Ticker symbol
            price_series: Recent price history (index should be dates)
            volume_series: Recent volume history

        Returns:
            Tuple of (is_safe: bool, reason: str)
            reason is empty string if safe, else description of risk.
        """
        # Check 1: Stale data
        if price_series is not None and len(price_series) > 0:
            stale_reason = self._check_stale(symbol, price_series)
            if stale_reason:
                return False, stale_reason

        # Check 2: Penny price
        if price_series is not None and len(price_series) > 0:
            price_reason = self._check_penny_price(symbol, price_series)
            if price_reason:
                return False, price_reason

        # Check 3: Volume crash
        if volume_series is not None and len(volume_series) > 0:
            vol_reason = self._check_volume_crash(symbol, volume_series)
            if vol_reason:
                return False, vol_reason

        return True, ""

    def _check_stale(self, symbol: str, price_series: pd.Series) -> str | None:
        """Check if data is stale (no updates recently)."""
        if not hasattr(price_series.index, "max"):
            return None

        # Count trailing NaN/zero values
        non_null = price_series.dropna()
        if len(non_null) == 0:
            reason = f"No valid price data for {symbol}"
            logger.warning("delisting_guard_stale", symbol=symbol, reason=reason)
            return reason

        # Check consecutive NaN at end
        reversed_vals = price_series.iloc[::-1]
        stale_count = 0
        for val in reversed_vals:
            if pd.isna(val) or val == 0:
                stale_count += 1
            else:
                break

        if stale_count > self.config.max_stale_days:
            reason = (
                f"Stale data for {symbol}: {stale_count} days without updates (threshold: {self.config.max_stale_days})"
            )
            logger.warning("delisting_guard_stale", symbol=symbol, stale_days=stale_count)
            return reason

        return None

    def _check_penny_price(self, symbol: str, price_series: pd.Series) -> str | None:
        """Check if current price is below penny threshold."""
        last_valid = price_series.dropna()
        if len(last_valid) == 0:
            return None

        current_price = float(last_valid.iloc[-1])
        if current_price < self.config.min_price_threshold:
            reason = f"Penny price for {symbol}: ${current_price:.6f} < ${self.config.min_price_threshold}"
            logger.warning(
                "delisting_guard_penny",
                symbol=symbol,
                price=current_price,
                threshold=self.config.min_price_threshold,
            )
            return reason

        return None

    def _check_volume_crash(self, symbol: str, volume_series: pd.Series) -> str | None:
        """Check if volume has crashed (drop > threshold over monitoring window)."""
        clean = volume_series.dropna()
        if len(clean) < self.config.volume_monitoring_days + 1:
            return None  # Not enough data to evaluate

        # Compare recent volume to earlier window average
        monitoring = clean.tail(self.config.volume_monitoring_days)
        earlier = clean.iloc[: -self.config.volume_monitoring_days]

        if len(earlier) == 0:
            return None

        avg_earlier = float(earlier.mean())
        avg_recent = float(monitoring.mean())

        if avg_earlier <= 0:
            return None

        drop_pct = (1 - avg_recent / avg_earlier) * 100

        if drop_pct >= self.config.volume_drop_pct_threshold:
            reason = (
                f"Volume crash for {symbol}: {drop_pct:.0f}% drop (threshold: {self.config.volume_drop_pct_threshold}%)"
            )
            logger.warning(
                "delisting_guard_volume_crash",
                symbol=symbol,
                drop_pct=round(drop_pct, 1),
                avg_recent=round(avg_recent, 0),
                avg_earlier=round(avg_earlier, 0),
            )
            return reason

        return None

    def check_batch(
        self,
        symbols: list,
        price_data: pd.DataFrame | None = None,
        volume_data: pd.DataFrame | None = None,
    ) -> dict[str, tuple]:
        """
        Check multiple symbols at once.

        Args:
            symbols: List of symbols
            price_data: DataFrame with price columns per symbol
            volume_data: DataFrame with volume columns per symbol

        Returns:
            Dict mapping symbol ��� (is_safe, reason)
        """
        results = {}
        for sym in symbols:
            price_s = price_data[sym] if price_data is not None and sym in price_data.columns else None
            vol_s = volume_data[sym] if volume_data is not None and sym in volume_data.columns else None
            results[sym] = self.is_safe(sym, price_s, vol_s)
        return results

