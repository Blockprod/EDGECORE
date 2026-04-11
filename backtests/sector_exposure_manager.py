"""
Sector exposure accounting and volatility sizing — extracted from StrategyBacktestSimulator.

Provides two focused helpers used during backtest entry filtering:

* ``BacktestSectorExposureManager.compute_sector_exposure`` — aggregate sector
  weights as % of portfolio for the sector monitor gate.
* ``BacktestSectorExposureManager.volatility_sizing_multiplier`` — inverse-vol
  multiplier that adapts position size to spread volatility.

``StrategyBacktestSimulator`` keeps delegation wrappers with the original names
(``_compute_sector_exposure``, ``_volatility_sizing_multiplier``) so no
call-site changes are required.

.. note::
    This class is distinct from :class:`risk.sector_exposure.SectorExposureMonitor`
    which enforces live risk limits.  This class serves backtest analytics only.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


class BacktestSectorExposureManager:
    """Sector exposure accounting and volatility-based allocation scaling.

    Args:
        sector_map: Mapping of symbol → sector name.  Used to compute
            per-sector portfolio weight.
    """

    def __init__(self, sector_map: dict[str, str] | None = None) -> None:
        self._sector_map: dict[str, str] = sector_map or {}

    def compute_sector_exposure(
        self,
        positions: dict[str, dict],
        portfolio_value: float,
    ) -> dict[str, float]:
        """Compute sector exposure as % of portfolio value.

        Returns dict mapping sector → exposure percentage.
        """
        if portfolio_value <= 0 or not positions:
            return {}
        sector_notional: dict[str, float] = {}
        for pos in positions.values():
            s1 = self._sector_map.get(pos["sym1"], "unknown")
            s2 = self._sector_map.get(pos["sym2"], "unknown")
            sector = s1 if s1 != "unknown" else s2
            sector_notional[sector] = sector_notional.get(sector, 0.0) + pos["notional"]
        return {s: (n / portfolio_value) * 100.0 for s, n in sector_notional.items()}

    @staticmethod
    def volatility_sizing_multiplier(
        prices_df: pd.DataFrame,
        sym1: str,
        sym2: str,
        lookback: int = 60,
    ) -> float:
        """Return an inverse-volatility multiplier in [0.4, 1.5].

        High-vol spreads get reduced allocation; tight mean-reverting
        spreads get a boost.  Uses log-return volatility of the simple
        spread as a proxy.
        """
        try:
            s1 = prices_df[sym1].iloc[-lookback:]
            s2 = prices_df[sym2].iloc[-lookback:]
            if len(s1) < 20 or len(s2) < 20:
                return 1.0
            # Simple spread vol (% of combined price)
            spread_ret = (s1.pct_change() - s2.pct_change()).dropna()
            if len(spread_ret) < 10:
                return 1.0
            vol = spread_ret.std()
            if vol <= 0:
                return 1.0
            # Inverse-vol: target 2% daily spread vol.
            # If vol is lower → bigger position (up to 1.5×);
            # if higher → smaller (down to 0.4×).
            target_vol = 0.02
            raw = target_vol / vol
            return float(np.clip(raw, 0.4, 1.5))
        except Exception:
            return 1.0
