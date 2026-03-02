"""
Event-driven backtester with order book simulation.

Sprint 4.5 – replaces or augments the bar-by-bar ``StrategyBacktestSimulator``
with realistic execution modelling:

* **Bid/ask spread** estimated from configurable ``book_depth_pct``
* **Partial fills** when the order exceeds a participation rate threshold
* **Market impact** proportional to order size vs. volume
* **Price gaps** between bars produce additional slippage

Usage::

    from backtests.event_driven import EventDrivenBacktester

    bt = EventDrivenBacktester(cost_model=CostModel(), initial_capital=100_000)
    metrics = bt.run(prices_df, volume_df, fixed_pairs)
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from structlog import get_logger

from backtests.cost_model import CostModel
from backtests.metrics import BacktestMetrics

logger = get_logger(__name__)


# ======================================================================
# Data classes
# ======================================================================

@dataclass
class Order:
    """Represents a single-leg order submitted to the simulated book."""
    pair_key: str
    symbol: str
    side: str         # "buy" or "sell"
    notional: float   # desired USD notional
    price: float      # reference market price (close)

    def __repr__(self) -> str:
        return f"Order({self.symbol} {self.side} ${self.notional:.0f} @{self.price:.4f})"


@dataclass
class MarketState:
    """Snapshot of per-symbol market conditions at a single bar."""
    close: float
    prev_close: Optional[float] = None
    volume_24h: float = 1e9
    high: Optional[float] = None
    low: Optional[float] = None

    @property
    def gap_pct(self) -> float:
        """Absolute price gap since previous bar (0 if no prev)."""
        if self.prev_close is None or self.prev_close == 0:
            return 0.0
        return abs(self.close - self.prev_close) / self.prev_close


@dataclass
class Fill:
    """Result of executing an *Order* through the simulated book."""
    pair_key: str
    symbol: str
    side: str
    requested_notional: float
    filled_notional: float
    fill_price: float
    slippage_bps: float
    is_partial: bool
    execution_cost: float     # total fee + slippage in USD
    market_impact_bps: float

    @property
    def fill_ratio(self) -> float:
        if self.requested_notional <= 0:
            return 0.0
        return self.filled_notional / self.requested_notional


# ======================================================================
# EventDrivenBacktester
# ======================================================================

class EventDrivenBacktester:
    """
    Backtester with order-book simulation for realistic execution.

    Compared to ``StrategyBacktestSimulator``:

    * Orders hit a simulated bid/ask spread (``book_depth_pct / 2`` each side)
    * Large orders receive **partial fills** when participation > threshold
    * Market impact is proportional to ``sqrt(participation_rate)``
    * Price gaps between consecutive bars cause extra slippage

    Parameters
    ----------
    cost_model : CostModel
        Underlying fee/borrow/funding cost model (Sprint 2.3).
    initial_capital : float
        Starting equity in USD.
    book_depth_pct : float
        Full bid/ask spread as a fraction of mid-price (default 0.02 = 2 %).
        Half-spread is applied on each side.
    max_participation_rate : float
        Maximum fraction of bar volume the order can consume before
        partial-fill kicks in (default 0.05 = 5 %).
    market_impact_coeff : float
        Coefficient for the square-root market impact model
        (default 0.10 = 10 bps per unit participation^0.5).
    gap_slippage_multiplier : float
        Extra slippage factor applied when there is a price gap > 1 %
        between consecutive bars (default 2.0).
    """

    def __init__(
        self,
        cost_model: Optional[CostModel] = None,
        initial_capital: float = 100_000.0,
        book_depth_pct: float = 0.02,
        max_participation_rate: float = 0.05,
        market_impact_coeff: float = 0.10,
        gap_slippage_multiplier: float = 2.0,
    ):
        self.cost_model = cost_model or CostModel()
        self.initial_capital = initial_capital
        self.book_depth_pct = book_depth_pct
        self.max_participation_rate = max_participation_rate
        self.market_impact_coeff = market_impact_coeff
        self.gap_slippage_multiplier = gap_slippage_multiplier

    # ------------------------------------------------------------------
    # Core: fill simulation
    # ------------------------------------------------------------------

    def simulate_fill(self, order: Order, market: MarketState) -> Fill:
        """
        Simulate execution of *order* against the simulated book.

        Steps
        -----
        1. Apply half bid/ask spread to get the *effective* side price.
        2. Compute participation rate and apply partial fill if > threshold.
        3. Add market-impact slippage proportional to ``sqrt(participation)``.
        4. Add gap-slippage if the bar has a significant price gap.
        5. Compute total execution cost (fees + slippage).
        """
        mid = order.price
        half_spread = mid * (self.book_depth_pct / 2.0)

        # 1. Bid/ask spread price
        if order.side == "buy":
            effective_price = mid + half_spread  # buy at ask
        else:
            effective_price = mid - half_spread  # sell at bid

        # 2. Participation rate ↓ partial fill
        participation = self._participation_rate(order.notional, mid, market.volume_24h)
        if participation > self.max_participation_rate:
            filled_notional = order.notional * (self.max_participation_rate / participation)
            is_partial = True
        else:
            filled_notional = order.notional
            is_partial = False

        # 3. Market impact: sqrt model
        impact_bps = self.market_impact_coeff * np.sqrt(participation) * 10_000
        impact_factor = impact_bps / 10_000
        if order.side == "buy":
            effective_price *= (1 + impact_factor)
        else:
            effective_price *= (1 - impact_factor)

        # 4. Gap slippage
        gap_pct = market.gap_pct
        if gap_pct > 0.01:
            gap_extra = gap_pct * self.gap_slippage_multiplier
            if order.side == "buy":
                effective_price *= (1 + gap_extra)
            else:
                effective_price *= (1 - gap_extra)

        # Compute slippage in bps
        if mid > 0:
            total_slippage_bps = abs(effective_price - mid) / mid * 10_000
        else:
            total_slippage_bps = 0.0

        # 5. Exchange fees on the filled amount
        fee_bps = self.cost_model.config.taker_fee_bps
        fee_cost = filled_notional * (fee_bps / 10_000)
        slippage_cost = filled_notional * (total_slippage_bps / 10_000)
        total_cost = fee_cost + slippage_cost

        return Fill(
            pair_key=order.pair_key,
            symbol=order.symbol,
            side=order.side,
            requested_notional=order.notional,
            filled_notional=filled_notional,
            fill_price=effective_price,
            slippage_bps=total_slippage_bps,
            is_partial=is_partial,
            execution_cost=total_cost,
            market_impact_bps=impact_bps,
        )

    # ------------------------------------------------------------------
    # Full backtest run
    # ------------------------------------------------------------------

    def run(
        self,
        prices_df: pd.DataFrame,
        volume_df: Optional[pd.DataFrame] = None,
        fixed_pairs: Optional[List[Tuple[str, str, float, float]]] = None,
        allocation_per_pair_pct: float = 2.0,
    ) -> BacktestMetrics:
        """
        Run an event-driven backtest.

        Parameters
        ----------
        prices_df : pd.DataFrame
            Columns = symbol names, index = DatetimeIndex (daily).
        volume_df : pd.DataFrame or None
            Same shape as *prices_df* but with 24 h volume.
            If None, a default high volume (1e9) is assumed.
        fixed_pairs : list[tuple] or None
            Pre-discovered pairs ``(sym1, sym2, pvalue, half_life)``.
        allocation_per_pair_pct : float
            Percent of capital allocated per pair per entry.

        Returns
        -------
        BacktestMetrics
        """
        from strategies.pair_trading import PairTradingStrategy

        strategy = PairTradingStrategy()
        strategy.disable_cache()

        capital = self.initial_capital
        positions: Dict[str, dict] = {}
        portfolio_values: List[float] = [capital]
        daily_returns: List[float] = []
        trades_pnl: List[float] = []
        total_costs: float = 0.0

        lookback_min = max(60, strategy.config.lookback_window)

        if len(prices_df) <= lookback_min:
            logger.warning("event_driven_insufficient_data", rows=len(prices_df))
            return BacktestMetrics(
                start_date=str(prices_df.index[0]) if len(prices_df) > 0 else "",
                end_date=str(prices_df.index[-1]) if len(prices_df) > 0 else "",
                total_return=0.0,
                sharpe_ratio=0.0,
                max_drawdown=0.0,
                win_rate=0.0,
                profit_factor=0.0,
                total_trades=0,
            )

        for bar_idx in range(lookback_min, len(prices_df)):
            window = prices_df.iloc[:bar_idx + 1]
            current_bar = prices_df.iloc[bar_idx]
            prev_bar = prices_df.iloc[bar_idx - 1] if bar_idx > 0 else None

            # --- Generate signals via live strategy code ---
            try:
                signals = strategy.generate_signals(
                    window,
                    discovered_pairs=fixed_pairs,
                )
            except Exception as e:
                logger.debug("event_driven_signal_error", bar=bar_idx, error=str(e)[:80])
                signals = []

            # --- Process signals ---
            for sig in signals:
                pair_key = sig.symbol_pair
                parts = pair_key.split("_")
                if len(parts) != 2:
                    continue
                sym1, sym2 = parts

                if sig.side in ("long", "short") and pair_key not in positions:
                    # ---- ENTRY ----
                    alloc = capital * (allocation_per_pair_pct / 100.0)

                    # Build market states
                    ms1 = self._market_state(sym1, current_bar, prev_bar, volume_df, bar_idx)
                    ms2 = self._market_state(sym2, current_bar, prev_bar, volume_df, bar_idx)
                    if ms1 is None or ms2 is None:
                        continue

                    # Simulate fills for both legs
                    buy_sym = sym1 if sig.side == "long" else sym2
                    sell_sym = sym2 if sig.side == "long" else sym1
                    buy_ms = ms1 if buy_sym == sym1 else ms2
                    sell_ms = ms2 if sell_sym == sym2 else ms1

                    fill_buy = self.simulate_fill(
                        Order(pair_key, buy_sym, "buy", alloc, buy_ms.close), buy_ms
                    )
                    fill_sell = self.simulate_fill(
                        Order(pair_key, sell_sym, "sell", alloc, sell_ms.close), sell_ms
                    )

                    entry_cost = fill_buy.execution_cost + fill_sell.execution_cost
                    total_costs += entry_cost

                    positions[pair_key] = {
                        "side": sig.side,
                        "sym1": sym1,
                        "sym2": sym2,
                        "entry_bar": bar_idx,
                        "entry_price_1": fill_buy.fill_price if buy_sym == sym1 else fill_sell.fill_price,
                        "entry_price_2": fill_sell.fill_price if sell_sym == sym2 else fill_buy.fill_price,
                        "notional": min(fill_buy.filled_notional, fill_sell.filled_notional),
                        "entry_cost": entry_cost,
                        "partial": fill_buy.is_partial or fill_sell.is_partial,
                    }

                    logger.debug(
                        "event_driven_entry",
                        pair=pair_key,
                        side=sig.side,
                        notional=f"${positions[pair_key]['notional']:.0f}",
                        entry_cost_bps=f"{(entry_cost / (2 * alloc) * 10_000):.1f}",
                        partial=positions[pair_key]["partial"],
                    )

                elif sig.side == "exit" and pair_key in positions:
                    # ---- EXIT ----
                    pos = positions[pair_key]

                    ms1 = self._market_state(sym1, current_bar, prev_bar, volume_df, bar_idx)
                    ms2 = self._market_state(sym2, current_bar, prev_bar, volume_df, bar_idx)
                    if ms1 is None or ms2 is None:
                        continue

                    # Close: reverse the original legs
                    close_buy_sym = sym2 if pos["side"] == "long" else sym1
                    close_sell_sym = sym1 if pos["side"] == "long" else sym2
                    close_buy_ms = ms2 if close_buy_sym == sym2 else ms1
                    close_sell_ms = ms1 if close_sell_sym == sym1 else ms2

                    fill_close_buy = self.simulate_fill(
                        Order(pair_key, close_buy_sym, "buy", pos["notional"], close_buy_ms.close),
                        close_buy_ms,
                    )
                    fill_close_sell = self.simulate_fill(
                        Order(pair_key, close_sell_sym, "sell", pos["notional"], close_sell_ms.close),
                        close_sell_ms,
                    )

                    exit_cost = fill_close_buy.execution_cost + fill_close_sell.execution_cost
                    total_costs += exit_cost

                    # P&L: spread change minus costs
                    if pos["side"] == "long":
                        # long sym1, short sym2
                        pnl_leg1 = (ms1.close - pos["entry_price_1"]) / pos["entry_price_1"]
                        pnl_leg2 = (pos["entry_price_2"] - ms2.close) / pos["entry_price_2"]
                    else:
                        # short sym1, long sym2
                        pnl_leg1 = (pos["entry_price_1"] - ms1.close) / pos["entry_price_1"]
                        pnl_leg2 = (ms2.close - pos["entry_price_2"]) / pos["entry_price_2"]

                    gross_pnl = (pnl_leg1 + pnl_leg2) / 2 * pos["notional"]
                    net_pnl = gross_pnl - pos["entry_cost"] - exit_cost

                    # Holding cost
                    holding_days = bar_idx - pos["entry_bar"]
                    hold_cost = self.cost_model.holding_cost(pos["notional"], holding_days)
                    fund_cost = self.cost_model.funding_cost(pos["notional"], holding_days)
                    net_pnl -= (hold_cost + fund_cost)
                    total_costs += hold_cost + fund_cost

                    trades_pnl.append(net_pnl)
                    capital += net_pnl
                    del positions[pair_key]

                    logger.debug(
                        "event_driven_exit",
                        pair=pair_key,
                        pnl=f"${net_pnl:.2f}",
                        holding_days=holding_days,
                        total_cost=f"${pos['entry_cost'] + exit_cost + hold_cost + fund_cost:.2f}",
                    )

            portfolio_values.append(capital)
            if len(portfolio_values) >= 2 and portfolio_values[-2] > 0:
                daily_returns.append(
                    (portfolio_values[-1] - portfolio_values[-2]) / portfolio_values[-2]
                )

        # ---- Build metrics via from_returns ----
        returns_series = pd.Series(daily_returns, dtype=float)
        start_date = str(prices_df.index[lookback_min])
        end_date = str(prices_df.index[-1])

        metrics = BacktestMetrics.from_returns(
            returns=returns_series,
            trades=trades_pnl,
            start_date=start_date,
            end_date=end_date,
            note=f"EventDriven | costs=${total_costs:.2f}",
        )

        logger.info(
            "event_driven_backtest_complete",
            total_return=f"{metrics.total_return:.2%}",
            sharpe=f"{metrics.sharpe_ratio:.2f}",
            max_dd=f"{metrics.max_drawdown:.2%}",
            trades=metrics.total_trades,
            total_costs=f"${total_costs:.2f}",
        )

        return metrics

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _market_state(
        symbol: str,
        current_bar: pd.Series,
        prev_bar: Optional[pd.Series],
        volume_df: Optional[pd.DataFrame],
        bar_idx: int,
    ) -> Optional[MarketState]:
        """Build a *MarketState* for *symbol* from bar data."""
        if symbol not in current_bar.index:
            return None
        close = float(current_bar[symbol])
        prev_close = float(prev_bar[symbol]) if prev_bar is not None and symbol in prev_bar.index else None
        vol = 1e9
        if volume_df is not None and symbol in volume_df.columns:
            vol = float(volume_df.iloc[bar_idx][symbol])
        return MarketState(close=close, prev_close=prev_close, volume_24h=vol)

    def _participation_rate(
        self, notional: float, price: float, volume_24h: float
    ) -> float:
        """Order size as fraction of daily volume (in base units)."""
        if price <= 0 or volume_24h <= 0:
            return 1.0  # worst-case
        order_qty = notional / price
        # Assume volume is in USD-equivalent
        volume_qty = volume_24h / price
        if volume_qty <= 0:
            return 1.0
        return order_qty / volume_qty
