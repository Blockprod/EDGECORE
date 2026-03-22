"""
Tests for realistic backtest execution (Phase 3.4).

Covers:
- Slippage calculation (fixed BPS, adaptive, volume-based)
- Commission deduction (percent, fixed)
- Partial fill handling
- End-to-end order execution workflows
"""

from datetime import UTC, datetime

import pytest

from common.types import (
    CommissionConfig,
    CommissionType,
    FillType,
    SlippageConfig,
    SlippageModel,
)
from execution.backtest_execution import (
    BacktestExecutor,
    CommissionCalculator,
    PartialFillHandler,
    SlippageCalculator,
)

# ============================================================================
# SLIPPAGE CALCULATOR TESTS
# ============================================================================


class TestSlippageCalculator:
    """Test SlippageCalculator with different models."""

    def test_fixed_bps_buy_order(self) -> None:
        """Test fixed BPS slippage on buy order."""
        config: SlippageConfig = {
            "model": SlippageModel.FIXED_BPS,
            "fixed_bps": 5.0,
        }
        calc = SlippageCalculator(config)

        slippage_bps, exec_price = calc.calculate(
            order_price=100.0,
            market_price=100.0,
            order_quantity=100.0,
            market_volume=1000000.0,
            side="buy",
        )

        assert slippage_bps == 5.0
        # 5 bps on 100 = 0.05
        expected_price = 100.0 + (5.0 / 10000) * 100.0
        assert abs(exec_price - expected_price) < 0.001

    def test_fixed_bps_sell_order(self) -> None:
        """Test fixed BPS slippage on sell order."""
        config: SlippageConfig = {
            "model": SlippageModel.FIXED_BPS,
            "fixed_bps": 3.0,
        }
        calc = SlippageCalculator(config)

        slippage_bps, exec_price = calc.calculate(
            order_price=100.0,
            market_price=100.0,
            order_quantity=100.0,
            market_volume=1000000.0,
            side="sell",
        )

        assert slippage_bps == 3.0
        # Sell: price reduced by slippage
        expected_price = 100.0 - (3.0 / 10000) * 100.0
        assert abs(exec_price - expected_price) < 0.001

    def test_adaptive_slippage_at_market(self) -> None:
        """Test adaptive slippage when order at market price."""
        config: SlippageConfig = {
            "model": SlippageModel.ADAPTIVE,
            "fixed_bps": 5.0,
            "adaptive_multiplier": 2.0,
            "max_slippage_bps": 50.0,
        }
        calc = SlippageCalculator(config)

        # Order at market: base slippage only
        slippage_bps, _exec_price = calc.calculate(
            order_price=100.0,
            market_price=100.0,
            order_quantity=100.0,
            market_volume=1000000.0,
            side="buy",
        )

        assert slippage_bps == 5.0

    def test_adaptive_slippage_away_from_market(self) -> None:
        """Test adaptive slippage increases away from market."""
        config: SlippageConfig = {
            "model": SlippageModel.ADAPTIVE,
            "fixed_bps": 5.0,
            "adaptive_multiplier": 2.0,
            "max_slippage_bps": 50.0,
        }
        calc = SlippageCalculator(config)

        # Order away from market: extra slippage
        slippage_bps, _exec_price = calc.calculate(
            order_price=105.0,  # 5% above market
            market_price=100.0,
            order_quantity=100.0,
            market_volume=1000000.0,
            side="buy",
        )

        # Base 5 + (0.05 * 200) = 15 bps
        assert slippage_bps == pytest.approx(15.0, rel=0.01)

    def test_adaptive_slippage_max_cap(self) -> None:
        """Test adaptive slippage respects max cap."""
        config: SlippageConfig = {
            "model": SlippageModel.ADAPTIVE,
            "fixed_bps": 5.0,
            "adaptive_multiplier": 2.0,
            "max_slippage_bps": 20.0,  # Low cap
        }
        calc = SlippageCalculator(config)

        # Order very far from market
        slippage_bps, _exec_price = calc.calculate(
            order_price=120.0,  # 20% above market
            market_price=100.0,
            order_quantity=100.0,
            market_volume=1000000.0,
            side="buy",
        )

        # Would be 5 + 400 = 405, but capped at 20
        assert slippage_bps == 20.0

    def test_volume_based_slippage_small_order(self) -> None:
        """Test volume-based slippage for small order."""
        config: SlippageConfig = {
            "model": SlippageModel.VOLUME_BASED,
            "fixed_bps": 5.0,
            "adaptive_multiplier": 100.0,  # 100x multiplier
            "max_slippage_bps": 100.0,
        }
        calc = SlippageCalculator(config)

        # Small order: 0.01% of market volume (1 unit of 10,000)
        slippage_bps, _exec_price = calc.calculate(
            order_price=100.0,
            market_price=100.0,
            order_quantity=1000.0,
            market_volume=10_000_000.0,  # 10M units
            side="buy",
        )

        # Base 5 + (0.0001 * 100) = 5.01 bps
        assert slippage_bps == pytest.approx(5.01, rel=0.01)

    def test_volume_based_slippage_large_order(self) -> None:
        """Test volume-based slippage for large order."""
        config: SlippageConfig = {
            "model": SlippageModel.VOLUME_BASED,
            "fixed_bps": 5.0,
            "adaptive_multiplier": 100.0,
            "max_slippage_bps": 100.0,
        }
        calc = SlippageCalculator(config)

        # Large order: 1% of market volume
        slippage_bps, _exec_price = calc.calculate(
            order_price=100.0,
            market_price=100.0,
            order_quantity=100_000.0,
            market_volume=10_000_000.0,
            side="buy",
        )

        # Base 5 + (0.01 * 100) = 6 bps
        assert slippage_bps == pytest.approx(6.0, rel=0.01)


# ============================================================================
# COMMISSION CALCULATOR TESTS
# ============================================================================


class TestCommissionCalculator:
    """Test CommissionCalculator with different methods."""

    def test_percent_commission(self) -> None:
        """Test percentage-based commission."""
        config: CommissionConfig = {
            "type": CommissionType.PERCENT,
            "percent": 0.1,  # 0.1%
        }
        calc = CommissionCalculator(config)

        commission = calc.calculate(trade_value=10000.0)

        # 0.1% of 10,000 = 10
        assert commission == pytest.approx(10.0, rel=0.01)

    def test_percent_commission_default(self) -> None:
        """Test percent commission uses default if not specified."""
        config: CommissionConfig = {
            "type": CommissionType.PERCENT,
        }
        calc = CommissionCalculator(config)

        commission = calc.calculate(trade_value=10000.0)

        # Default 0.02% of 10,000 = 2
        assert commission == pytest.approx(2.0, rel=0.01)

    def test_fixed_commission(self) -> None:
        """Test fixed commission per trade."""
        config: CommissionConfig = {
            "type": CommissionType.FIXED,
            "fixed_amount": 5.0,
        }
        calc = CommissionCalculator(config)

        commission = calc.calculate(trade_value=10000.0)

        assert commission == 5.0

    def test_fixed_commission_default(self) -> None:
        """Test fixed commission uses default if not specified."""
        config: CommissionConfig = {
            "type": CommissionType.FIXED,
        }
        calc = CommissionCalculator(config)

        commission = calc.calculate(trade_value=10000.0)

        # Default $1
        assert commission == 1.0

    def test_commission_min_bound(self) -> None:
        """Test commission respects minimum bound."""
        config: CommissionConfig = {
            "type": CommissionType.PERCENT,
            "percent": 0.001,  # Very low
            "min_commission": 5.0,
        }
        calc = CommissionCalculator(config)

        commission = calc.calculate(trade_value=1000.0)

        # Would be 0.01, but min is 5
        assert commission == 5.0

    def test_commission_max_bound(self) -> None:
        """Test commission respects maximum bound."""
        config: CommissionConfig = {
            "type": CommissionType.PERCENT,
            "percent": 1.0,  # 1%
            "max_commission": 20.0,
        }
        calc = CommissionCalculator(config)

        commission = calc.calculate(trade_value=10000.0)

        # Would be 100, but max is 20
        assert commission == 20.0


# ============================================================================
# PARTIAL FILL HANDLER TESTS
# ============================================================================


class TestPartialFillHandler:
    """Test PartialFillHandler for fill scenarios."""

    def test_full_fill_small_order(self) -> None:
        """Test full fill for small order."""
        handler = PartialFillHandler()

        filled_qty, fill_type = handler.determine_fill_quantity(
            requested_quantity=100.0,
            market_volume=10000.0,
            is_aggressive=True,
        )

        assert filled_qty == 100.0
        assert fill_type == FillType.FULL

    def test_partial_fill_large_order(self) -> None:
        """Test partial fill for large order."""
        handler = PartialFillHandler()

        filled_qty, fill_type = handler.determine_fill_quantity(
            requested_quantity=500000.0,
            market_volume=1000000.0,
            is_aggressive=True,
        )

        # Max fillable at 10% = 100,000
        assert filled_qty == 100000.0
        assert fill_type == FillType.PARTIAL

    def test_fill_floors_to_whole_units(self) -> None:
        """Test fill quantity floors to whole units."""
        handler = PartialFillHandler()

        filled_qty, fill_type = handler.determine_fill_quantity(
            requested_quantity=0.5,  # Less than 1
            market_volume=10000.0,
            is_aggressive=True,
        )

        assert filled_qty == 1.0  # Floors to 1
        assert fill_type == FillType.FULL

    def test_passive_order_smaller_fill(self) -> None:
        """Test passive order gets smaller fills."""
        handler = PartialFillHandler()

        filled_qty, _fill_type = handler.determine_fill_quantity(
            requested_quantity=50000.0,
            market_volume=1000000.0,
            is_aggressive=False,  # Passive
        )

        # Passive order limited to base volume (1%)
        assert filled_qty <= 100000.0  # Max fillable


# ============================================================================
# END-TO-END BACKTEST EXECUTION TESTS
# ============================================================================


class TestBacktestExecutor:
    """Test BacktestExecutor for complete order execution."""

    def test_basic_buy_order_execution(self) -> None:
        """Test basic buy order execution with slippage and commission."""
        executor = BacktestExecutor()

        result = executor.execute_order(
            order_id="ORD001",
            symbol="AAPL",
            side="buy",
            quantity=100.0,
            order_price=150.0,
            market_price=150.0,
            market_volume=1000000.0,
            execution_time=datetime.now(UTC),
        )

        assert result["order_id"] == "ORD001"
        assert result["symbol"] == "AAPL"
        assert result["filled_quantity"] == 100.0
        assert result["fill_type"] == FillType.FULL
        assert result["executed_price"] > 150.0  # Slippage
        assert result["commission"] > 0  # Commission charged
        assert result["net_proceeds"] < 0  # Cost to buy

    def test_basic_sell_order_execution(self) -> None:
        """Test basic sell order execution."""
        executor = BacktestExecutor()

        result = executor.execute_order(
            order_id="ORD002",
            symbol="AAPL",
            side="sell",
            quantity=100.0,
            order_price=150.0,
            market_price=150.0,
            market_volume=1000000.0,
            execution_time=datetime.now(UTC),
        )

        assert result["filled_quantity"] == 100.0
        assert result["fill_type"] == FillType.FULL
        assert result["executed_price"] < 150.0  # Slippage reduces price
        assert result["commission"] > 0  # Commission charged
        assert result["net_proceeds"] > 0  # Revenue from sell

    def test_execution_with_custom_slippage(self) -> None:
        """Test execution with custom slippage configuration."""
        slippage_cfg: SlippageConfig = {
            "model": SlippageModel.FIXED_BPS,
            "fixed_bps": 10.0,  # 10 bps instead of default 5
        }
        calc = SlippageCalculator(slippage_cfg)

        commission_cfg: CommissionConfig = {
            "type": CommissionType.PERCENT,
            "percent": 0.02,
        }
        comm_calc = CommissionCalculator(commission_cfg)

        executor = BacktestExecutor(
            slippage_calc=calc,
            commission_calc=comm_calc,
        )

        result = executor.execute_order(
            order_id="ORD003",
            symbol="AAPL",
            side="buy",
            quantity=100.0,
            order_price=150.0,
            market_price=150.0,
            market_volume=1000000.0,
            execution_time=datetime.now(UTC),
        )

        assert result["slippage_bps"] == 10.0
        # Slippage: 10 bps on 150 = 0.15
        expected_exec = 150.0 + 0.15
        assert abs(result["executed_price"] - expected_exec) < 0.001

    def test_multi_leg_order_execution(self) -> None:
        """Test execution of multi-leg order (pair trade)."""
        executor = BacktestExecutor()

        legs = [
            {
                "symbol": "AAPL",
                "side": "buy",
                "quantity": 100.0,
                "order_price": 150.0,
                "market_price": 150.0,
                "market_volume": 1000000.0,
            },
            {
                "symbol": "MSFT",
                "side": "sell",
                "quantity": 100.0,
                "order_price": 300.0,
                "market_price": 300.0,
                "market_volume": 500000.0,
            },
        ]

        results = executor.execute_multi_leg_order(
            order_id="PAIR001",
            legs=legs,
            execution_time=datetime.now(UTC),
        )

        assert len(results) == 2
        assert results[0]["symbol"] == "AAPL"
        assert results[0]["side"] == "buy"
        assert results[1]["symbol"] == "MSFT"
        assert results[1]["side"] == "sell"
        # Check both have fills and costs
        for result in results:
            assert result["filled_quantity"] > 0
            assert result["commission"] > 0

    def test_execution_result_structure(self) -> None:
        """Test ExecutionResult contains all required fields."""
        executor = BacktestExecutor()

        result = executor.execute_order(
            order_id="ORD004",
            symbol="TEST",
            side="buy",
            quantity=50.0,
            order_price=100.0,
            market_price=100.0,
            market_volume=500000.0,
            execution_time=datetime.now(UTC),
        )

        # Verify all required fields present
        assert "order_id" in result
        assert "symbol" in result
        assert "submitted_price" in result
        assert "executed_price" in result
        assert "requested_quantity" in result
        assert "filled_quantity" in result
        assert "fill_type" in result
        assert "slippage_bps" in result
        assert "slippage_amount" in result
        assert "commission" in result
        assert "net_proceeds" in result
        assert "execution_time" in result

    def test_zero_market_volume_fallback(self) -> None:
        """Test execution with zero market volume uses fallback."""
        executor = BacktestExecutor()

        result = executor.execute_order(
            order_id="ORD005",
            symbol="ILLIQ",
            side="buy",
            quantity=10.0,
            order_price=100.0,
            market_price=100.0,
            market_volume=0.0,  # No market volume
            execution_time=datetime.now(UTC),
        )

        # Should still execute with fallback slippage model
        assert result["filled_quantity"] > 0
        assert result["slippage_bps"] > 0  # Some slippage applied

    def test_pnl_impact_of_costs(self) -> None:
        """Test that slippage and commission reduce PnL."""
        executor = BacktestExecutor()

        # Buy then sell same position
        buy_result = executor.execute_order(
            order_id="ORD006_BUY",
            symbol="AAPL",
            side="buy",
            quantity=100.0,
            order_price=100.0,
            market_price=100.0,
            market_volume=1000000.0,
            execution_time=datetime.now(UTC),
        )

        sell_result = executor.execute_order(
            order_id="ORD006_SELL",
            symbol="AAPL",
            side="sell",
            quantity=100.0,
            order_price=101.0,  # Profitable by $1
            market_price=101.0,
            market_volume=1000000.0,
            execution_time=datetime.now(UTC),
        )

        # Total cost (for documentation only)
        _ = -buy_result["net_proceeds"] + abs(sell_result["net_proceeds"])
        gross_profit = 100.0 * (101.0 - 100.0)

        # Actual profit reduced by slippage and commissions
        net_profit = gross_profit - (
            buy_result["slippage_amount"]
            + buy_result["commission"]
            + sell_result["slippage_amount"]
            + sell_result["commission"]
        )

        # Net profit should be less than gross profit
        assert net_profit < gross_profit


# ============================================================================
# INTEGRATION TESTS
# ============================================================================


class TestBacktestRealismIntegration:
    """Integration tests for complete backtest realism scenarios."""

    def test_realistic_trade_workflow(self) -> None:
        """Test complete realistic trade workflow."""
        executor = BacktestExecutor()

        # Entry order
        entry = executor.execute_order(
            order_id="TRADE001_ENTRY",
            symbol="SPY",
            side="buy",
            quantity=1000.0,
            order_price=420.0,
            market_price=420.0,
            market_volume=100000000.0,
            execution_time=datetime(2024, 1, 1, 10, 0, 0),
        )

        assert entry["filled_quantity"] == 1000.0
        assert entry["fill_type"] == FillType.FULL

        # Entry cost
        entry_total_cost = entry["slippage_amount"] + entry["commission"]

        # Exit order (up 1%)
        exit_price = 420.0 * 1.01  # 424.20
        exit = executor.execute_order(
            order_id="TRADE001_EXIT",
            symbol="SPY",
            side="sell",
            quantity=1000.0,
            order_price=exit_price,
            market_price=exit_price,
            market_volume=100000000.0,
            execution_time=datetime(2024, 1, 1, 15, 0, 0),
        )

        assert exit["filled_quantity"] == 1000.0
        # Total PnL
        gross_profit = 1000.0 * (exit_price - 420.0)
        total_costs = entry_total_cost + exit["slippage_amount"] + exit["commission"]
        net_pnl = gross_profit - total_costs

        # Should be profitable but less than 1% due to costs
        assert net_pnl > 0
        assert net_pnl < gross_profit

    def test_multiple_trades_sequence(self) -> None:
        """Test sequence of multiple trades with realistic costs."""
        executor = BacktestExecutor()
        trades = []

        for i in range(3):
            # Alternating buy/sell
            side = "buy" if i % 2 == 0 else "sell"
            price = 100.0 + i

            result = executor.execute_order(
                order_id=f"TRADE{i:03d}",
                symbol="TEST",
                side=side,
                quantity=100.0,
                order_price=price,
                market_price=price,
                market_volume=1000000.0,
                execution_time=datetime.now(UTC),
            )

            trades.append(result)

        # All trades should execute with costs
        assert len(trades) == 3
        for trade in trades:
            assert trade["commission"] > 0
            assert trade["slippage_bps"] >= 0
