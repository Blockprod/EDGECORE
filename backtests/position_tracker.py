"""
Position-level P&L calculations — extracted from StrategyBacktestSimulator.

Handles position closure, ADV estimation, volatility estimation, and
spread computation.  All methods that operated on ``self`` in the simulator
are moved here; ``StrategyBacktestSimulator`` keeps delegation wrappers with
the original names so no call-site changes are required.
"""

from __future__ import annotations

from typing import Any, cast

import numpy as np
import pandas as pd
from structlog import get_logger

logger = get_logger(__name__)


class PositionTracker:
    """Handles position-level P&L accounting and cost attribution.

    Injected with the simulator's cost and sizing objects so it can
    compute realistic exit costs, borrow fees, and record trade outcomes
    for downstream analytics.

    Args:
        cost_model: Trading cost model instance.
        kelly_sizer: Optional Kelly sizer for per-trade recording.
        pair_blacklist: Dynamic pair blacklist for consecutive-loss tracking.
        ml_combiner: ML signal combiner for trade-outcome training.
        adv_by_symbol: Pre-computed real ADV values keyed by uppercase symbol.
    """

    # ADV estimates by market-cap tier (USD notional/day).
    _ADV_MEGA_CAP = 500_000_000  # $500M/day — AAPL, MSFT, NVDA, etc.
    _ADV_LARGE_CAP = 150_000_000  # $150M/day — CL, SO, DUK, etc.
    _ADV_MID_CAP = 30_000_000  # $30M/day — fallback

    # Symbols known to be mega-cap (top-20 ADV in v31h universe)
    _MEGA_CAP_SYMBOLS: frozenset[str] = frozenset(
        {
            "AAPL",
            "MSFT",
            "GOOGL",
            "META",
            "NVDA",
            "AMD",
            "AVGO",
            "JPM",
            "BAC",
            "SPY",
            "XOM",
            "WMT",
            "UNH",
            "JNJ",
            "PFE",
            "GS",
            "WFC",
            "C",
            "MRK",
            "ABBV",
        }
    )

    def __init__(
        self,
        cost_model: Any,
        kelly_sizer: Any | None,
        pair_blacklist: Any,
        ml_combiner: Any,
        adv_by_symbol: dict[str, float] | None = None,
    ) -> None:
        self.cost_model = cost_model
        self.kelly_sizer = kelly_sizer
        self.pair_blacklist = pair_blacklist
        self.ml_combiner = ml_combiner
        self.adv_by_symbol: dict[str, float] = adv_by_symbol or {}

    def close_position(
        self,
        pos: dict[str, Any],
        prices_df: pd.DataFrame,
        bar_idx: int,
    ) -> tuple[float, float, int]:
        """Close a position and compute net P&L.

        Args:
            pos: Position dict from ``SimulatedOrderBook``.
            prices_df: Full price DataFrame.
            bar_idx: Current bar index (exit at bar_idx+1, clamped).

        Returns:
            ``(daily_realized_pnl, full_round_trip_pnl, holding_days)``
        """
        sym1, sym2 = pos["sym1"], pos["sym2"]
        # C-02: T+1 fill — execute exit at bar T+1 (clamped to last bar).
        _n_bars = len(prices_df)
        exec_bar = min(bar_idx + 1, _n_bars - 1)
        exit_price_1 = prices_df[sym1].iloc[exec_bar]
        exit_price_2 = prices_df[sym2].iloc[exec_bar]
        entry_price_1 = pos["entry_price_1"]
        entry_price_2 = pos["entry_price_2"]
        notional = pos["notional"]
        not_1 = pos.get("notional_1", notional / 2.0)
        not_2 = pos.get("notional_2", notional / 2.0)
        notional_per_leg = notional / 2.0  # average (for cost estimation)
        holding_days = max(exec_bar - pos["entry_bar"], 0)

        # P&L per leg (% return × beta-neutral per-leg notional)
        if pos["side"] == "long":
            # Long sym1, short sym2
            ret_1 = (exit_price_1 - entry_price_1) / entry_price_1 if entry_price_1 != 0 else 0.0
            ret_2 = (entry_price_2 - exit_price_2) / entry_price_2 if entry_price_2 != 0 else 0.0
        else:
            # Short sym1, long sym2
            ret_1 = (entry_price_1 - exit_price_1) / entry_price_1 if entry_price_1 != 0 else 0.0
            ret_2 = (exit_price_2 - entry_price_2) / entry_price_2 if entry_price_2 != 0 else 0.0

        pnl_gross = not_1 * ret_1 + not_2 * ret_2

        # Exit-day costs (Almgren-Chriss: use stored vol + estimated ADV)
        _sig1 = pos.get("sigma1", 0.02)
        _sig2 = pos.get("sigma2", 0.02)
        _adv1 = self.estimate_adv(sym1, prices_df, notional_per_leg)
        _adv2 = self.estimate_adv(sym2, prices_df, notional_per_leg)
        x_cost = self.cost_model.exit_cost(
            notional_per_leg,
            volume_24h_sym1=_adv1,
            volume_24h_sym2=_adv2,
            sigma_sym1=_sig1,
            sigma_sym2=_sig2,
        )
        borrow = self.cost_model.holding_cost(notional_per_leg, holding_days)
        # Phase 0.4: Use per-position borrow fee when available
        _pos_borrow_fee = pos.get("borrow_fee_pct")
        if _pos_borrow_fee is not None and _pos_borrow_fee != self.cost_model.config.borrowing_cost_annual_pct:
            borrow = notional_per_leg * (_pos_borrow_fee / 100.0 / 365.0) * holding_days
        funding = self.cost_model.funding_cost(notional_per_leg, holding_days)

        daily_realized = pnl_gross - x_cost - borrow - funding
        full_trade = daily_realized - pos["entry_cost"]  # include entry cost

        logger.debug(
            "simulated_trade_closed",
            pair=f"{sym1}_{sym2}",
            side=pos["side"],
            holding_days=holding_days,
            pnl_gross=round(pnl_gross, 2),
            exit_cost=round(x_cost, 2),
            borrow_cost=round(borrow, 2),
            trade_pnl=round(full_trade, 2),
        )

        # Post-v27 Étape 3: Record outcome for dynamic pair blacklist
        try:
            _exit_date = cast(pd.Timestamp, pd.Timestamp(str(prices_df.index[bar_idx]))).date()
            self.pair_blacklist.record_outcome(
                f"{sym1}_{sym2}",
                pnl=full_trade,
                trade_date=_exit_date,
            )
        except Exception:
            pass  # Non-critical — don't break the backtest

        # Phase 0.2: Record trade for adaptive Kelly computation
        if self.kelly_sizer is not None:
            self.kelly_sizer.record_trade(full_trade)

        # Phase 4.4: Record trade outcome for ML combiner training
        _ml_feats = pos.get("ml_features")
        if _ml_feats is not None:
            self.ml_combiner.record_trade(
                bar_idx=pos["entry_bar"],
                features=_ml_feats,
                outcome=full_trade / notional if notional > 0 else 0.0,
            )

        return daily_realized, full_trade, holding_days

    def estimate_adv(
        self,
        symbol: str,
        prices_df: pd.DataFrame,
        notional_per_leg: float,
    ) -> float:
        """Estimate Average Daily Volume in USD for slippage calculation.

        Lookup order:
        1. ``self.adv_by_symbol`` (injected real ADV from DataLoader / caller)
        2. Static mega-cap / large-cap tier table (conservative fallback)
        """
        injected = self.adv_by_symbol.get(symbol.upper())
        if injected is not None:
            return injected
        if symbol not in prices_df.columns:
            logger.debug(
                "adv_estimate_symbol_not_in_prices",
                symbol=symbol,
                notional_per_leg=notional_per_leg,
            )
        if symbol in self._MEGA_CAP_SYMBOLS:
            return self._ADV_MEGA_CAP
        # All v31h symbols are large-cap at minimum
        return self._ADV_LARGE_CAP

    @staticmethod
    def estimate_sigma(
        prices_df: pd.DataFrame,
        symbol: str,
        lookback: int = 60,
    ) -> float:
        """Estimate daily return volatility for a symbol from recent prices.

        Returns a decimal (e.g. 0.02 for 2% daily vol).
        """
        try:
            series = prices_df[symbol].iloc[-lookback:]
            if len(series) < 10:
                return 0.02
            vol = series.pct_change().dropna().std()
            return max(vol, 0.005)  # floor at 0.5%
        except Exception:
            return 0.02

    @staticmethod
    def compute_spread(
        prices_df: pd.DataFrame,
        sym1: str,
        sym2: str,
    ) -> pd.Series | None:
        """Compute a simple OLS-residual spread for the correlation guard.

        Uses log-price ratio as a lightweight proxy (avoids a full
        SpreadModel fit on every bar).  Returns ``None`` on failure.
        """
        try:
            s1 = prices_df[sym1]
            s2 = prices_df[sym2]
            if len(s1) < 30 or len(s2) < 30:
                return None
            # Normalised spread: log(s1) − β̂·log(s2), β via simple OLS
            s1_cleaned = s1.replace(0, np.nan).dropna()
            s2_cleaned = s2.replace(0, np.nan).dropna()
            ls1 = pd.Series(np.log(s1_cleaned.values), index=s1_cleaned.index, dtype=float)
            ls2 = pd.Series(np.log(s2_cleaned.values), index=s2_cleaned.index, dtype=float)
            common = ls1.index.intersection(ls2.index)
            if len(common) < 30:
                return None
            ls1 = ls1.loc[common]
            ls2 = ls2.loc[common]
            beta = np.polyfit(np.asarray(ls2.values, dtype=float), np.asarray(ls1.values, dtype=float), 1)[0]
            spread = ls1 - beta * ls2
            return spread
        except Exception:
            return None
