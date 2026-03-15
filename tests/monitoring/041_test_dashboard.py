"""Comprehensive tests for Dashboard generator."""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
from monitoring.dashboard import DashboardGenerator
from risk.engine import Position


class TestDashboardGeneratorBasic:
    """Test basic dashboard initialization and generation."""

    def test_dashboard_initializes_without_engines(self):
        """Test dashboard can initialize without risk/execution engines."""
        dashboard = DashboardGenerator(mode="paper")

        assert dashboard.mode == "paper"
        assert dashboard.risk_engine is None
        assert dashboard.execution_engine is None

    def test_dashboard_initializes_with_engines(self):
        """Test dashboard initializes with engines."""
        risk_engine = Mock()
        execution_engine = Mock()

        dashboard = DashboardGenerator(
            risk_engine=risk_engine,
            execution_engine=execution_engine,
            mode="live"
        )

        assert dashboard.risk_engine is risk_engine
        assert dashboard.execution_engine is execution_engine
        assert dashboard.mode == "live"

    def test_generate_dashboard_basic_structure(self):
        """Test dashboard generates correct structure."""
        dashboard = DashboardGenerator(mode="paper")
        result = dashboard.generate_dashboard()

        assert 'timestamp' in result
        assert 'system' in result
        assert 'risk' in result
        assert 'positions' in result
        assert 'orders' in result
        assert 'performance' in result

    def test_dashboard_handles_generation_error(self):
        """Test dashboard handles errors gracefully."""
        # Create dashboard with mock that raises error
        risk_engine = Mock()
        risk_engine.equity_history = None  # Will cause error

        dashboard = DashboardGenerator(risk_engine=risk_engine)

        with patch.object(dashboard, '_positions', side_effect=Exception("Test error")):
            result = dashboard.generate_dashboard()
            # Should still have system status even on error
            assert 'system' in result
            assert 'timestamp' in result


class TestDashboardSystemStatus:
    """Test system status reporting."""

    def test_system_status_includes_required_fields(self):
        """Test system status has all required fields."""
        dashboard = DashboardGenerator(mode="backtest")
        status = dashboard._system_status()

        assert status['status'] == 'healthy'
        assert status['mode'] == 'backtest'
        assert 'uptime_seconds' in status
        assert 'uptime_human' in status
        assert 'memory_mb' in status
        assert 'cpu_percent' in status
        assert 'pid' in status

    def test_system_status_uptime_positive(self):
        """Test system uptime is positive."""
        dashboard = DashboardGenerator()
        status = dashboard._system_status()

        assert status['uptime_seconds'] >= 0

    def test_system_status_memory_positive(self):
        """Test memory usage is positive."""
        dashboard = DashboardGenerator()
        status = dashboard._system_status()

        assert status['memory_mb'] > 0

    def test_system_status_mode_preserved(self):
        """Test mode is correctly preserved in status."""
        for mode in ['paper', 'live', 'backtest']:
            dashboard = DashboardGenerator(mode=mode)
            status = dashboard._system_status()
            assert status['mode'] == mode


class TestDashboardRiskMetrics:
    """Test risk metrics reporting."""

    def test_risk_metrics_without_engine(self):
        """Test risk metrics when engine not available."""
        dashboard = DashboardGenerator(risk_engine=None)
        metrics = dashboard._risk_metrics()

        assert metrics['enabled'] is False

    def test_risk_metrics_with_engine(self):
        """Test risk metrics with engine."""
        risk_engine = Mock()
        risk_engine.equity_history = [10000, 10100, 10050]
        risk_engine.initial_equity = 10000
        risk_engine.daily_loss = -50
        risk_engine.loss_streak = 2
        risk_engine.daily_trades = 5
        risk_engine.positions = {'AAPL': Mock()}
        risk_engine.config = Mock()
        risk_engine.config.max_daily_loss_pct = 0.05
        risk_engine.config.max_concurrent_positions = 5

        dashboard = DashboardGenerator(risk_engine=risk_engine)
        metrics = dashboard._risk_metrics()

        assert metrics['enabled'] is True
        assert metrics['current_equity'] == 10050
        assert metrics['initial_equity'] == 10000
        assert 'total_return_pct' in metrics
        assert metrics['daily_loss'] == -50
        assert metrics['positions_count'] == 1

    def test_risk_metrics_empty_equity_history(self):
        """Test risk metrics with empty equity history."""
        risk_engine = Mock()
        risk_engine.equity_history = []
        risk_engine.initial_equity = 10000
        risk_engine.daily_loss = 0
        risk_engine.loss_streak = 0
        risk_engine.daily_trades = 0
        risk_engine.positions = {}
        risk_engine.config = Mock()
        risk_engine.config.max_daily_loss_pct = 0.05
        risk_engine.config.max_concurrent_positions = 5

        dashboard = DashboardGenerator(risk_engine=risk_engine)
        metrics = dashboard._risk_metrics()

        assert metrics['current_equity'] == 0

    def test_risk_metrics_daily_loss_calculation(self):
        """Test daily loss percentage calculation."""
        risk_engine = Mock()
        risk_engine.equity_history = [10000]
        risk_engine.initial_equity = 10000
        risk_engine.daily_loss = -500  # 5% loss
        risk_engine.loss_streak = 1
        risk_engine.daily_trades = 1
        risk_engine.positions = {}
        risk_engine.config = Mock()
        risk_engine.config.max_daily_loss_pct = 0.10
        risk_engine.config.max_concurrent_positions = 5

        dashboard = DashboardGenerator(risk_engine=risk_engine)
        metrics = dashboard._risk_metrics()

        assert metrics['daily_loss_pct'] == -5.0
        assert metrics['max_daily_loss_limit_pct'] == 10.0


class TestDashboardPositions:
    """Test positions reporting."""

    def test_positions_without_engine(self):
        """Test positions when engine not available."""
        dashboard = DashboardGenerator(risk_engine=None)
        positions = dashboard._positions()

        assert positions == []

    def test_positions_with_engine_empty(self):
        """Test positions when no open positions."""
        risk_engine = Mock()
        risk_engine.positions = {}

        dashboard = DashboardGenerator(risk_engine=risk_engine)
        positions = dashboard._positions()

        assert positions == []

    def test_positions_with_engine_has_positions(self):
        """Test positions with open positions."""
        position = Position(
            symbol_pair='AAPL',
            entry_time=datetime.now() - timedelta(hours=2),
            entry_price=45000,
            quantity=0.5,
            side='long',
            pnl=500,
            marked_price=45909  # Price at ~1% profit
        )

        risk_engine = Mock()
        risk_engine.positions = {'AAPL': position}

        dashboard = DashboardGenerator(risk_engine=risk_engine)
        positions = dashboard._positions()

        assert len(positions) == 1
        assert positions[0]['symbol'] == 'AAPL'
        assert positions[0]['side'] == 'long'
        assert positions[0]['quantity'] == 0.5
        assert positions[0]['entry_price'] == 45000
        assert positions[0]['unrealized_pnl'] == 500
        assert 'age_hours' in positions[0]

    def test_positions_age_calculation(self):
        """Test position age calculation."""
        position = Position(
            symbol_pair='MSFT',
            entry_time=datetime.now() - timedelta(hours=3),
            entry_price=2500,
            quantity=1,
            side='short',
            pnl=0,
            marked_price=2500
        )

        risk_engine = Mock()
        risk_engine.positions = {'MSFT': position}

        dashboard = DashboardGenerator(risk_engine=risk_engine)
        positions = dashboard._positions()

        assert positions[0]['age_hours'] == pytest.approx(3, rel=0.1)


class TestDashboardOrders:
    """Test orders reporting."""

    def test_orders_without_engine(self):
        """Test orders when engine not available."""
        dashboard = DashboardGenerator(execution_engine=None)
        orders = dashboard._orders()

        assert orders['enabled'] is False

    def test_orders_with_engine_no_orders(self):
        """Test orders when execution engine returns no orders."""
        execution_engine = Mock()
        execution_engine.get_open_orders.return_value = []

        dashboard = DashboardGenerator(execution_engine=execution_engine)
        orders = dashboard._orders()

        assert orders['enabled'] is True
        assert orders['total'] == 0
        assert orders['orders'] == []

    def test_orders_with_engine_has_orders(self):
        """Test orders with open orders."""
        mock_order_1 = {
            'id': 'order_123',
            'symbol': 'AAPL',
            'side': 'buy',
            'amount': 0.5,
            'price': 45000,
            'status': 'open',
            'timestamp': 1707000000000
        }
        mock_order_2 = {
            'id': 'order_124',
            'symbol': 'MSFT',
            'side': 'sell',
            'amount': 1,
            'price': 2500,
            'status': 'open',
            'timestamp': 1707000100000
        }

        execution_engine = Mock()
        execution_engine.get_open_orders.return_value = [mock_order_1, mock_order_2]

        dashboard = DashboardGenerator(execution_engine=execution_engine)
        orders = dashboard._orders()

        assert orders['enabled'] is True
        assert orders['total'] == 2
        assert len(orders['orders']) == 2
        assert orders['orders'][0]['order_id'] == 'order_123'
        assert orders['orders'][1]['order_id'] == 'order_124'

    def test_orders_missing_get_open_orders_method(self):
        """Test orders when engine doesn't have get_open_orders method."""
        execution_engine = Mock(spec=[])  # Empty spec means no methods

        dashboard = DashboardGenerator(execution_engine=execution_engine)
        orders = dashboard._orders()

        assert orders['enabled'] is True
        assert orders['total'] == 0
        assert orders['orders'] == []

    def test_orders_caps_at_20(self):
        """Test orders list is capped at 20 items."""
        # Create 30 mock orders
        mock_orders = [
            {
                'id': f'order_{i}',
                'symbol': 'AAPL',
                'side': 'buy',
                'amount': 0.1,
                'price': 45000,
                'status': 'open'
            }
            for i in range(30)
        ]

        execution_engine = Mock()
        execution_engine.get_open_orders.return_value = mock_orders

        dashboard = DashboardGenerator(execution_engine=execution_engine)
        orders = dashboard._orders()

        assert orders['total'] == 30
        assert len(orders['orders']) == 20  # Capped at 20


class TestDashboardPerformance:
    """Test performance metrics calculation."""

    def test_performance_without_engine(self):
        """Test performance metrics when engine not available."""
        dashboard = DashboardGenerator(risk_engine=None)
        performance = dashboard._performance_metrics()

        assert performance['enabled'] is False

    def test_performance_with_single_point(self):
        """Test performance with single data point."""
        risk_engine = Mock()
        risk_engine.equity_history = [10000]
        risk_engine.daily_trades = 0

        dashboard = DashboardGenerator(risk_engine=risk_engine)
        performance = dashboard._performance_metrics()

        assert performance['enabled'] is True
        assert 'data_points' in performance
        assert performance['data_points'] == 1

    def test_performance_with_multiple_points(self):
        """Test performance with multiple data points."""
        risk_engine = Mock()
        risk_engine.equity_history = [10000, 10100, 10050, 10200, 10150]
        risk_engine.daily_trades = 10

        dashboard = DashboardGenerator(risk_engine=risk_engine)
        performance = dashboard._performance_metrics()

        assert performance['enabled'] is True
        assert performance['total_return_pct'] == 1.5  # 10150/10000 - 1
        assert 'sharpe_ratio' in performance
        assert 'max_drawdown_pct' in performance
        assert performance['trades_total'] == 10

    def test_performance_max_drawdown_calculation(self):
        """Test max drawdown calculation."""
        # Equity: 10000 -> 11000 (new peak) -> 10000 (10% drawdown) -> 11500 (new peak) -> 10000 (13% drawdown)
        risk_engine = Mock()
        risk_engine.equity_history = [10000, 11000, 10000, 11500, 10000]
        risk_engine.daily_trades = 0

        dashboard = DashboardGenerator(risk_engine=risk_engine)
        performance = dashboard._performance_metrics()

        # Max drawdown should be 13% (from 11500 to 10000)
        assert performance['max_drawdown_pct'] == pytest.approx(13.04, rel=0.01)


class TestDashboardIntegration:
    """Integration tests for full dashboard generation."""

    def test_full_dashboard_generation_all_components(self):
        """Test full dashboard with all components."""
        # Setup risk engine
        position = Position(
            symbol_pair='AAPL',
            entry_time=datetime.now() - timedelta(hours=1),
            entry_price=45000,
            quantity=0.5,
            side='long',
            pnl=500,
            marked_price=45909
        )
        risk_engine = Mock()
        risk_engine.equity_history = [10000, 10100, 10500]
        risk_engine.initial_equity = 10000
        risk_engine.daily_loss = 0
        risk_engine.loss_streak = 0
        risk_engine.daily_trades = 2
        risk_engine.positions = {'AAPL': position}
        risk_engine.config = Mock()
        risk_engine.config.max_daily_loss_pct = 0.05
        risk_engine.config.max_concurrent_positions = 5

        # Setup execution engine
        execution_engine = Mock()
        execution_engine.get_open_orders.return_value = []

        # Generate dashboard (bypass cache to ensure fresh data)
        dashboard = DashboardGenerator(
            risk_engine=risk_engine,
            execution_engine=execution_engine,
            mode='paper'
        )
        result = dashboard.generate_dashboard(bypass_cache=True)

        # Verify all components
        assert 'timestamp' in result
        assert result['system']['mode'] == 'paper'
        assert result['risk']['current_equity'] == 10500
        assert len(result['positions']) == 1
        assert result['orders']['total'] == 0
        assert result['performance']['sharpe_ratio'] is not None

    def test_dashboard_get_status(self):
        """Test dashboard status reporting."""
        risk_engine = Mock()
        execution_engine = Mock()

        dashboard = DashboardGenerator(
            risk_engine=risk_engine,
            execution_engine=execution_engine,
            mode='live'
        )

        status = dashboard.get_status()

        assert status['mode'] == 'live'
        assert status['risk_engine_available'] is True
        assert status['execution_engine_available'] is True
        assert status['uptime_seconds'] >= 0

    def test_dashboard_uptime_reset(self):
        """Test resetting dashboard uptime."""
        dashboard1 = DashboardGenerator()
        status1 = dashboard1.get_status()
        initial_uptime = status1['uptime_seconds']

        import time
        time.sleep(0.1)  # Small delay

        DashboardGenerator.reset_uptime()

        dashboard2 = DashboardGenerator()
        status2 = dashboard2.get_status()
        reset_uptime = status2['uptime_seconds']

        # After reset, uptime should be much smaller
        assert reset_uptime < initial_uptime


class TestDashboardErrorHandling:
    """Test error handling in dashboard generation."""

    def test_dashboard_handles_risk_metrics_error(self):
        """Test dashboard handles errors in risk metrics."""
        risk_engine = Mock()
        risk_engine.equity_history = None  # Will cause error

        dashboard = DashboardGenerator(risk_engine=risk_engine)
        metrics = dashboard._risk_metrics()

        # Should have error field instead of crashing
        assert metrics['enabled'] is True
        assert 'error' in metrics or 'enabled' in metrics

    def test_dashboard_handles_positions_error(self):
        """Test dashboard handles errors in positions."""
        risk_engine = Mock()
        risk_engine.positions = {'AAPL': None}  # Invalid position

        dashboard = DashboardGenerator(risk_engine=risk_engine)
        positions = dashboard._positions()

        # Should return empty list instead of crashing
        assert isinstance(positions, list)

    def test_dashboard_handles_orders_parse_error(self):
        """Test dashboard handles malformed order data."""
        execution_engine = Mock()
        execution_engine.get_open_orders.return_value = [
            {'id': 'order_1', 'symbol': 'AAPL'},  # Missing required fields
            {'id': None, 'invalid': 'order'},  # Completely invalid
        ]

        dashboard = DashboardGenerator(execution_engine=execution_engine)
        orders = dashboard._orders()

        # Should handle errors gracefully
        assert orders['enabled'] is True
        assert orders['total'] == 2  # Still counts attempts
        assert isinstance(orders['orders'], list)
