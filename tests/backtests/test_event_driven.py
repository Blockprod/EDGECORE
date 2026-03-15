"""
Tests for Sprint 4.5 ÔÇô Event-driven backtester with order book simulation.

Covers:
  1. Order / MarketState / Fill data classes
  2. simulate_fill ÔÇô bid/ask spread, partial fills, market impact, gap slippage
  3. Participation rate calculation
  4. Full run ÔÇô produces BacktestMetrics
  5. Comparison: event-driven should be more pessimistic than simple fill
  6. Edge cases
"""

import numpy as np
import pandas as pd

from backtests.event_driven import (
    EventDrivenBacktester,
    Order,
    MarketState,
    Fill,
)
from backtests.cost_model import CostModel


# ===================================================================
# Helpers
# ===================================================================

def _default_bt(**kw) -> EventDrivenBacktester:
    return EventDrivenBacktester(cost_model=CostModel(), **kw)


def _simple_order(pair="A_B", symbol="A", side="buy", notional=1000, price=100.0):
    return Order(pair_key=pair, symbol=symbol, side=side, notional=notional, price=price)


def _simple_market(close=100.0, prev_close=99.0, volume=1e9):
    return MarketState(close=close, prev_close=prev_close, volume_24h=volume)


# ===================================================================
# 1. Data classes
# ===================================================================

class TestDataClasses:

    def test_order_repr(self):
        o = _simple_order()
        assert "buy" in repr(o)
        assert "$1000" in repr(o)

    def test_market_state_gap_pct(self):
        ms = MarketState(close=105, prev_close=100, volume_24h=1e9)
        assert abs(ms.gap_pct - 0.05) < 1e-6

    def test_market_state_gap_no_prev(self):
        ms = MarketState(close=100, prev_close=None)
        assert ms.gap_pct == 0.0

    def test_fill_ratio(self):
        f = Fill(
            pair_key="A_B", symbol="A", side="buy",
            requested_notional=1000, filled_notional=500,
            fill_price=100, slippage_bps=50, is_partial=True,
            execution_cost=5, market_impact_bps=10,
        )
        assert f.fill_ratio == 0.5


# ===================================================================
# 2. simulate_fill ÔÇô Bid/Ask spread
# ===================================================================

class TestBidAskSpread:

    def test_buy_fills_above_mid(self):
        bt = _default_bt(book_depth_pct=0.02)  # 1% half-spread
        order = _simple_order(side="buy", price=100.0, notional=100)
        ms = _simple_market(close=100.0, volume=1e12)  # huge volume = no impact
        fill = bt.simulate_fill(order, ms)
        assert fill.fill_price > 100.0

    def test_sell_fills_below_mid(self):
        bt = _default_bt(book_depth_pct=0.02)
        order = _simple_order(side="sell", price=100.0, notional=100)
        ms = _simple_market(close=100.0, volume=1e12)
        fill = bt.simulate_fill(order, ms)
        assert fill.fill_price < 100.0

    def test_wider_spread_means_worse_price(self):
        bt_narrow = _default_bt(book_depth_pct=0.01)
        bt_wide = _default_bt(book_depth_pct=0.04)
        order = _simple_order(side="buy", price=100.0, notional=100)
        ms = _simple_market(close=100.0, volume=1e12)
        fill_n = bt_narrow.simulate_fill(order, ms)
        fill_w = bt_wide.simulate_fill(order, ms)
        assert fill_w.fill_price > fill_n.fill_price

    def test_zero_spread(self):
        bt = _default_bt(book_depth_pct=0.0, market_impact_coeff=0.0)
        order = _simple_order(side="buy", price=100.0, notional=100)
        ms = _simple_market(close=100.0, prev_close=100.0, volume=1e12)
        fill = bt.simulate_fill(order, ms)
        # Only fee, no slippage
        assert abs(fill.fill_price - 100.0) < 0.01


# ===================================================================
# 3. simulate_fill ÔÇô Partial fills
# ===================================================================

class TestPartialFills:

    def test_small_order_fully_filled(self):
        """Order smaller than 5% of volume Ôåô full fill."""
        bt = _default_bt(max_participation_rate=0.05)
        order = _simple_order(notional=100, price=100.0)
        ms = _simple_market(volume=1e9)  # 100/(1e9) << 5%
        fill = bt.simulate_fill(order, ms)
        assert fill.is_partial is False
        assert fill.filled_notional == 100

    def test_large_order_partially_filled(self):
        """Order exceeding 5% volume Ôåô partial fill, capped to 5%."""
        bt = _default_bt(max_participation_rate=0.05)
        # volume = 10,000 USD-equiv Ôåô 5% = 500 Ôåô order 1000 Ôåô partial
        order = _simple_order(notional=1000, price=100.0)
        ms = _simple_market(close=100.0, volume=10_000)
        fill = bt.simulate_fill(order, ms)
        assert fill.is_partial is True
        assert fill.filled_notional < fill.requested_notional
        assert fill.fill_ratio <= 0.05 / (1000 / 10_000) + 0.01  # rough check

    def test_participation_at_boundary(self):
        """Order exactly at 5% Ôåô full fill."""
        bt = _default_bt(max_participation_rate=0.05)
        # volume = 20,000 Ôåô 5% = 1000 Ôåô order 1000 Ôåô exactly at boundary
        order = _simple_order(notional=1000, price=100.0)
        ms = _simple_market(close=100.0, volume=20_000)
        fill = bt.simulate_fill(order, ms)
        assert fill.is_partial is False


# ===================================================================
# 4. simulate_fill ÔÇô Market impact
# ===================================================================

class TestMarketImpact:

    def test_impact_increases_with_order_size(self):
        bt = _default_bt(book_depth_pct=0.0)  # isolate impact
        ms = _simple_market(close=100.0, prev_close=100.0, volume=100_000)
        small = bt.simulate_fill(_simple_order(notional=100, price=100.0), ms)
        large = bt.simulate_fill(_simple_order(notional=10_000, price=100.0), ms)
        assert large.market_impact_bps > small.market_impact_bps

    def test_impact_buy_raises_price(self):
        bt = _default_bt(book_depth_pct=0.0, market_impact_coeff=0.5)
        order = _simple_order(side="buy", notional=5000, price=100.0)
        ms = _simple_market(close=100.0, prev_close=100.0, volume=50_000)
        fill = bt.simulate_fill(order, ms)
        assert fill.fill_price > 100.0

    def test_impact_sell_lowers_price(self):
        bt = _default_bt(book_depth_pct=0.0, market_impact_coeff=0.5)
        order = _simple_order(side="sell", notional=5000, price=100.0)
        ms = _simple_market(close=100.0, prev_close=100.0, volume=50_000)
        fill = bt.simulate_fill(order, ms)
        assert fill.fill_price < 100.0


# ===================================================================
# 5. simulate_fill ÔÇô Gap slippage
# ===================================================================

class TestGapSlippage:

    def test_no_gap_no_extra_slippage(self):
        bt = _default_bt(book_depth_pct=0.0, market_impact_coeff=0.0)
        order = _simple_order(side="buy", price=100.0, notional=100)
        ms = _simple_market(close=100.0, prev_close=100.0, volume=1e12)
        fill = bt.simulate_fill(order, ms)
        assert fill.slippage_bps < 1.0  # effectively zero

    def test_large_gap_adds_slippage(self):
        bt = _default_bt(book_depth_pct=0.0, market_impact_coeff=0.0, gap_slippage_multiplier=2.0)
        order = _simple_order(side="buy", price=100.0, notional=100)
        # 5% gap Ôåô extra slippage
        ms = _simple_market(close=100.0, prev_close=95.0, volume=1e12)
        fill = bt.simulate_fill(order, ms)
        assert fill.slippage_bps > 50  # significant extra slippage

    def test_gap_multiplier_effect(self):
        order = _simple_order(side="buy", price=100.0, notional=100)
        ms = _simple_market(close=100.0, prev_close=90.0, volume=1e12)  # 10% gap
        bt_low = _default_bt(book_depth_pct=0.0, market_impact_coeff=0.0, gap_slippage_multiplier=1.0)
        bt_high = _default_bt(book_depth_pct=0.0, market_impact_coeff=0.0, gap_slippage_multiplier=3.0)
        fill_low = bt_low.simulate_fill(order, ms)
        fill_high = bt_high.simulate_fill(order, ms)
        assert fill_high.slippage_bps > fill_low.slippage_bps


# ===================================================================
# 6. simulate_fill ÔÇô Execution cost
# ===================================================================

class TestExecutionCost:

    def test_cost_includes_fee_and_slippage(self):
        bt = _default_bt(book_depth_pct=0.02)
        order = _simple_order(notional=10_000, price=100.0)
        ms = _simple_market(volume=1e9)
        fill = bt.simulate_fill(order, ms)
        assert fill.execution_cost > 0
        # Should be at least the fee component (10 bps on 10k = $1)
        assert fill.execution_cost >= 0.9

    def test_cost_zero_for_zero_notional(self):
        bt = _default_bt()
        order = _simple_order(notional=0, price=100.0)
        ms = _simple_market(volume=1e9)
        fill = bt.simulate_fill(order, ms)
        assert fill.execution_cost == 0.0


# ===================================================================
# 7. Participation rate
# ===================================================================

class TestParticipationRate:

    def test_participation_rate_normal(self):
        bt = _default_bt()
        rate = bt._participation_rate(notional=1000, price=100.0, volume_24h=100_000)
        # 1000/(100_000) = 1%
        assert abs(rate - 0.01) < 1e-6

    def test_participation_rate_zero_volume(self):
        bt = _default_bt()
        rate = bt._participation_rate(notional=1000, price=100.0, volume_24h=0)
        assert rate == 1.0  # worst case

    def test_participation_rate_zero_price(self):
        bt = _default_bt()
        rate = bt._participation_rate(notional=1000, price=0, volume_24h=100_000)
        assert rate == 1.0


# ===================================================================
# 8. Full run ÔÇô basic
# ===================================================================

class TestFullRun:

    def _gen_cointegrated_prices(self, n=300, seed=42):
        rng = np.random.RandomState(seed)
        x = 100 * np.exp(np.cumsum(rng.randn(n) * 0.01))
        noise = rng.randn(n) * 0.5
        y = 2 * x + noise
        dates = pd.date_range("2024-01-01", periods=n, freq="D")
        return pd.DataFrame({"SYM1": x, "SYM2": y}, index=dates)

    def test_run_returns_metrics(self):
        """run() should return a BacktestMetrics with total_return."""
        bt = _default_bt(initial_capital=100_000)
        df = self._gen_cointegrated_prices()
        # Use fixed pairs to avoid heavy pair discovery
        metrics = bt.run(df, fixed_pairs=[("SYM1", "SYM2", 0.001, 10)])
        assert hasattr(metrics, 'total_return')
        assert hasattr(metrics, 'total_trades')

    def test_run_with_volume(self):
        """Providing volume data should not crash."""
        bt = _default_bt()
        df = self._gen_cointegrated_prices()
        vol = pd.DataFrame(
            np.full_like(df.values, 1e6),
            columns=df.columns, index=df.index,
        )
        metrics = bt.run(df, volume_df=vol, fixed_pairs=[("SYM1", "SYM2", 0.001, 10)])
        assert hasattr(metrics, 'total_trades')

    def test_insufficient_data(self):
        bt = _default_bt()
        df = pd.DataFrame({"A": [1, 2, 3], "B": [2, 4, 6]}, index=pd.date_range("2024-01-01", periods=3))
        metrics = bt.run(df)
        assert metrics.total_trades == 0
        assert metrics.total_return == 0.0


# ===================================================================
# 9. Event-driven is more pessimistic than simple fill-at-close
# ===================================================================

class TestMorePessimistic:
    """
    With realistic bid/ask spread and market impact, the event-driven
    backtest should produce higher costs than a simple fee-only model.
    """

    def test_fill_cost_exceeds_fee_only(self):
        """Single fill cost should exceed bare fee cost."""
        bt = _default_bt(book_depth_pct=0.02, market_impact_coeff=0.10)
        order = _simple_order(notional=5000, price=100.0)
        ms = _simple_market(close=100.0, prev_close=100.0, volume=100_000)
        fill = bt.simulate_fill(order, ms)
        # Fee-only cost: 10 bps on $5000 = $0.50
        fee_only = 5000 * 10 / 10_000
        assert fill.execution_cost > fee_only

    def test_slippage_bps_positive(self):
        bt = _default_bt(book_depth_pct=0.02)
        order = _simple_order(notional=5000, price=100.0)
        ms = _simple_market(volume=100_000)
        fill = bt.simulate_fill(order, ms)
        assert fill.slippage_bps > 0


# ===================================================================
# 10. Edge cases
# ===================================================================

class TestEdgeCases:

    def test_zero_price_order(self):
        bt = _default_bt()
        order = _simple_order(price=0.0, notional=100)
        ms = _simple_market(close=0.0, volume=1e9)
        fill = bt.simulate_fill(order, ms)
        assert fill.slippage_bps == 0.0

    def test_negative_volume_handled(self):
        bt = _default_bt()
        rate = bt._participation_rate(1000, 100.0, -1)
        assert rate == 1.0

    def test_market_state_with_all_fields(self):
        ms = MarketState(close=100, prev_close=95, volume_24h=1e8, high=102, low=94)
        assert ms.gap_pct > 0
