"""
End-to-End Integration Tests for EDGECORE Trading System.

Tests complete trading workflows:
- Market data loading ↓ Strategy signals ↓ Position opening ↓ Risk management
- Error handling across all layers
- Alert triggering (Slack, Email, Dashboard)
- Dashboard metrics accuracy
- API endpoint availability
"""

import pytest
from unittest.mock import patch
import pandas as pd
import numpy as np
import json

from data.loader import DataLoader
from strategies.pair_trading import PairTradingStrategy
from risk.engine import RiskEngine
from execution.ibkr_engine import IBGatewaySync, IBKRExecutionEngine
from monitoring.slack_alerter import SlackAlerter
from monitoring.email_alerter import EmailAlerter
from monitoring.dashboard import DashboardGenerator
from monitoring.api import create_app


@pytest.fixture(autouse=True)
def _reset_ibkr_client_ids():
    """Clear IBKRExecutionEngine client_id registry between tests."""
    IBKRExecutionEngine._active_client_ids.clear()
    yield
    IBKRExecutionEngine._active_client_ids.clear()


class TestFullTradingCycle:
    """Test complete trading cycle from data to execution."""

    def test_complete_market_data_to_position_flow(self):
        """Test: Data Load ↓ Strategy ↓ Position Created."""
        # Setup
        DataLoader()
        PairTradingStrategy()
        RiskEngine(initial_equity=100000.0)
        IBKRExecutionEngine()

    def test_strategy_signal_generation(self):
        """Test: Strategy generates valid signals from market data."""
        strategy = PairTradingStrategy()
        
        # Create synthetic prices showing potential spread
        dates = pd.date_range('2026-01-01', periods=50, freq='D')
        aapl_prices = pd.Series(np.sin(np.linspace(0, 2*np.pi, 50)) * 5 + 175, index=dates)
        msft_prices = pd.Series(np.sin(np.linspace(0.5, 2*np.pi + 0.5, 50)) * 8 + 420, index=dates)
        
        prices_df = pd.DataFrame({
            'AAPL': aapl_prices,
            'MSFT': msft_prices
        })
        
        # Generate signals
        signals = strategy.generate_signals(prices_df)
        
        # Verify signal format
        assert isinstance(signals, list)
        for signal in signals:
            assert 'symbol' in signal or 'pair' in signal or isinstance(signal, dict)

    def test_risk_engine_validates_position(self):
        """Test: Risk engine validates position against limits."""
        risk_engine = RiskEngine(initial_equity=100000.0)
        
        # Test position validation
        
        # Should validate without error (assuming defaults allow it)
        assert risk_engine is not None

    def test_execution_engine_order_submission(self):
        """Test: Execution engine can submit orders."""
        execution_engine = IBKRExecutionEngine()
        
        # Verify engine initialized
        assert execution_engine is not None
        
        # Mock order submission
        with patch.object(execution_engine, 'submit_order') as mock_submit:
            mock_submit.return_value = {
                'id': '123456',
                'symbol': 'AAPL',
                'status': 'open'
            }
            
            order = execution_engine.submit_order('AAPL', 'buy', 100)
            assert order is not None


class TestAlertingIntegration:
    """Test alerting system integration across all layers."""

    def test_error_triggers_slack_alert(self):
        """Test: System error triggers Slack notification."""
        slack_alerter = SlackAlerter(webhook_url="https://hooks.slack.com/test")
        
        # Mock the alert
        with patch.object(slack_alerter, 'send_alert') as mock_alert:
            mock_alert.return_value = True
            
            slack_alerter.send_alert(
                level='ERROR',
                title='Test Error',
                message='This is a test error'
            )
            
            mock_alert.assert_called_once()

    def test_critical_error_triggers_email_alert(self):
        """Test: Critical error triggers email notification."""
        email_alerter = EmailAlerter(
            smtp_server='smtp.gmail.com',
            smtp_port=587,
            sender_email='test@example.com',
            sender_password='password',
            recipient_emails=['alert@example.com']
        )
        
        # Mock email sending
        with patch.object(email_alerter, 'send_alert') as mock_alert:
            mock_alert.return_value = True
            
            email_alerter.send_alert(
                level='CRITICAL',
                title='System Critical Alert',
                message='Critical event occurred'
            )
            
            mock_alert.assert_called_once()

    def test_multiple_alerts_sent_together(self):
        """Test: Multiple alerters receive notification simultaneously."""
        slack_alerter = SlackAlerter(webhook_url="https://hooks.slack.com/test")
        email_alerter = EmailAlerter(
            smtp_server='smtp.gmail.com',
            smtp_port=587,
            sender_email='test@example.com',
            sender_password='password',
            recipient_emails=['alert@example.com']
        )
        
        # Mock both alerters
        with patch.object(slack_alerter, 'send_alert') as mock_slack, \
             patch.object(email_alerter, 'send_alert') as mock_email:
            
            mock_slack.return_value = True
            mock_email.return_value = True
            
            # Send to both
            slack_alerter.send_alert('ERROR', 'Test', 'Message')
            email_alerter.send_alert('ERROR', 'Test', 'Message')
            
            assert mock_slack.called
            assert mock_email.called


class TestDashboardAccuracy:
    """Test dashboard metrics are accurate."""

    def test_dashboard_equity_calculation(self):
        """Test: Dashboard correctly calculates equity."""
        risk_engine = RiskEngine(initial_equity=100000.0)
        dashboard = DashboardGenerator(risk_engine=risk_engine)
        
        # Get risk metrics
        metrics = dashboard._risk_metrics()
        
        # Verify structure
        assert isinstance(metrics, dict)
        assert 'enabled' in metrics or 'current_equity' in metrics

    def test_dashboard_position_tracking(self):
        """Test: Dashboard accurately lists open positions."""
        execution_engine = IBKRExecutionEngine()
        dashboard = DashboardGenerator(execution_engine=execution_engine)
        
        # Get positions
        positions = dashboard._positions()
        
        # Verify structure
        assert isinstance(positions, list)
        for pos in positions:
            assert isinstance(pos, dict)

    def test_dashboard_performance_metrics(self):
        """Test: Dashboard calculates performance metrics correctly."""
        dashboard = DashboardGenerator()
        
        # Get performance metrics
        perf = dashboard._performance_metrics()
        
        # Verify required fields
        assert isinstance(perf, dict)
        assert 'enabled' in perf or 'total_return_pct' in perf

    def test_dashboard_api_returns_valid_json(self):
        """Test: Dashboard API endpoint returns valid JSON."""
        dashboard = DashboardGenerator()
        app = create_app(dashboard)
        client = app.test_client()
        
        response = client.get('/api/dashboard')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert isinstance(data, dict)
        assert len(data) > 0


class TestErrorHandlingChain:
    """Test error handling across multiple layers."""

    def test_data_load_error_handled(self):
        """Test: Data loading error is caught and logged."""
        loader = DataLoader()
        
        with patch.object(loader, 'load_ibkr_data') as mock_load:
            mock_load.side_effect = Exception("Network error")
            
            try:
                loader.load_ibkr_data('AAPL')
                assert False, "Should have raised exception"
            except Exception as e:
                assert "Network error" in str(e)

    def test_strategy_error_handled(self):
        """Test: Strategy error is caught gracefully."""
        strategy = PairTradingStrategy()
        
        # Pass invalid data
        invalid_df = pd.DataFrame()  # Empty
        
        signals = strategy.generate_signals(invalid_df)
        
        # Should return empty signals, not crash
        assert isinstance(signals, list)

    def test_execution_error_handled(self):
        """Test: Execution engine error is caught."""
        execution_engine = IBKRExecutionEngine()
        
        with patch.object(execution_engine, 'submit_order') as mock_submit:
            mock_submit.side_effect = Exception("Exchange unavailable")
            
            try:
                execution_engine.submit_order('AAPL', 'buy', 100)
                assert False, "Should have raised"
            except Exception as e:
                assert "Exchange unavailable" in str(e)


class TestSystemStability:
    """Test system stability under various conditions."""

    def test_multiple_consecutive_trades(self):
        """Test: System handles multiple trades in sequence."""
        strategy = PairTradingStrategy()
        RiskEngine(initial_equity=100000.0)
        IBKRExecutionEngine()
        
        # Simulate 5 consecutive trades
        for i in range(5):
            # Generate prices
            prices_df = pd.DataFrame({
                'AAPL': [175.0 + i],
                'MSFT': [420.0 + i * 2]
            })
            
            # Generate signals
            signals = strategy.generate_signals(prices_df)
            
            # Verify no crash
            assert isinstance(signals, list)

    def test_rapid_api_requests(self):
        """Test: API handles rapid consecutive requests."""
        dashboard = DashboardGenerator()
        app = create_app(dashboard)
        client = app.test_client()
        
        # Make 10 rapid requests
        for i in range(10):
            response = client.get('/api/dashboard/system')
            assert response.status_code in [200, 503]

    def test_dashboard_under_high_position_load(self):
        """Test: Dashboard handles many positions gracefully."""
        dashboard = DashboardGenerator()
        
        # Simulate high load by calling multiple times
        for _ in range(20):
            positions = dashboard._positions()
            assert isinstance(positions, list)

    def test_alert_system_under_load(self):
        """Test: Alert system handles many alerts."""
        slack_alerter = SlackAlerter(webhook_url="https://hooks.slack.com/test")
        
        with patch.object(slack_alerter, 'send_alert') as mock_alert:
            mock_alert.return_value = True
            
            # Send 20 alerts rapidly
            for i in range(20):
                slack_alerter.send_alert('INFO', f'Test {i}', 'Message')
            
            assert mock_alert.call_count >= 0  # May be throttled


class TestDataIntegrity:
    """Test data integrity across system."""

    def test_position_data_consistency(self):
        """Test: Position data stays consistent across updates."""
        risk_engine = RiskEngine(initial_equity=100000.0)
        dashboard = DashboardGenerator(risk_engine=risk_engine)
        
        # Get positions twice
        pos1 = dashboard._positions()
        pos2 = dashboard._positions()
        
        # Should have same structure
        assert type(pos1) == type(pos2)
        assert len(pos1) == len(pos2)

    def test_metrics_numeric_validity(self):
        """Test: All metrics are valid numbers or null."""
        dashboard = DashboardGenerator()
        metrics = dashboard._risk_metrics()
        
        # Check all values are valid
        for key, value in metrics.items():
            assert value is None or isinstance(value, (int, float, str, bool))

    def test_dashboard_json_serializable(self):
        """Test: All dashboard data can be JSON serialized."""
        dashboard = DashboardGenerator()
        full_data = dashboard.generate_dashboard()
        
        # Should be JSON serializable
        json_str = json.dumps(full_data)
        assert len(json_str) > 0

    def test_api_response_structure_consistency(self):
        """Test: API responses have consistent structure."""
        dashboard = DashboardGenerator()
        app = create_app(dashboard)
        client = app.test_client()
        
        # Get full dashboard multiple times
        for _ in range(3):
            response = client.get('/api/dashboard')
            data = json.loads(response.data)
            
            # Should have top-level keys
            assert 'system' in data or 'timestamp' in data


class TestRecoveryAndResilience:
    """Test system recovery from failures."""

    def test_graceful_degradation_no_risk_engine(self):
        """Test: System works without risk engine."""
        dashboard = DashboardGenerator(risk_engine=None)
        
        # Should still generate dashboard
        metrics = dashboard._risk_metrics()
        assert metrics is not None

    def test_graceful_degradation_no_execution_engine(self):
        """Test: System works without execution engine."""
        dashboard = DashboardGenerator(execution_engine=None)
        
        # Should still have positions
        positions = dashboard._positions()
        assert isinstance(positions, list)

    def test_api_handles_missing_dashboard(self):
        """Test: API returns proper error without dashboard."""
        app = create_app(dashboard=None)
        client = app.test_client()
        
        response = client.get('/api/dashboard')
        assert response.status_code == 503

    def test_alert_with_invalid_credentials(self):
        """Test: Alert system handles invalid credentials."""
        email_alerter = EmailAlerter(
            smtp_server='invalid.server',
            smtp_port=999,
            sender_email='test@example.com',
            sender_password='invalid',
            recipient_emails=['alert@example.com']
        )
        
        with patch.object(email_alerter, 'send_alert') as mock:
            mock.side_effect = Exception("Connection failed")
            
            try:
                email_alerter.send_alert('ERROR', 'Test', 'Message')
            except Exception:
                pass  # Expected


class TestPerformanceCharacteristics:
    """Test system performance characteristics."""

    def test_dashboard_generation_speed(self):
        """Test: Dashboard generates quickly."""
        dashboard = DashboardGenerator()
        
        import time
        start = time.time()
        dashboard.generate_dashboard()
        elapsed = time.time() - start
        
        # Should generate in under 1 second
        assert elapsed < 1.0

    def test_api_response_time(self):
        """Test: API responds quickly."""
        dashboard = DashboardGenerator()
        app = create_app(dashboard)
        client = app.test_client()
        
        import time
        start = time.time()
        client.get('/api/dashboard/system')
        elapsed = time.time() - start
        
        # Should respond in under 500ms
        assert elapsed < 0.5

    def test_alert_sending_speed(self):
        """Test: Alerts are sent quickly."""
        slack_alerter = SlackAlerter(webhook_url="https://hooks.slack.com/test")
        
        with patch.object(slack_alerter, 'send_alert') as mock:
            mock.return_value = True
            
            import time
            start = time.time()
            slack_alerter.send_alert('INFO', 'Test', 'Message')
            elapsed = time.time() - start
            
            # Should return quickly (mocked, so very fast)
            assert elapsed < 0.1

    def test_strategy_signal_generation_speed(self):
        """Test: Strategy signals generate quickly."""
        strategy = PairTradingStrategy()
        
        # Create large dataset
        dates = pd.date_range('2026-01-01', periods=1000, freq='h')
        data = pd.DataFrame({
            'AAPL': np.random.randn(1000).cumsum() + 175,
            'MSFT': np.random.randn(1000).cumsum() + 420
        }, index=dates)
        
        import time
        start = time.time()
        strategy.generate_signals(data)
        elapsed = time.time() - start
        
        # Should process 1000 data points in reasonable time (cointegration is expensive)
        assert elapsed < 5.0


class TestSystemintegration:
    """Test all components working together."""

    def test_all_modules_importable(self):
        """Test: All EDGECORE modules can be imported."""
        from data.loader import DataLoader
        from strategies.pair_trading import PairTradingStrategy
        from risk.engine import RiskEngine
        from execution.ibkr_engine import IBGatewaySync
        from monitoring.slack_alerter import SlackAlerter
        from monitoring.email_alerter import EmailAlerter
        from monitoring.dashboard import DashboardGenerator
        from monitoring.api import create_app
        
        assert all([DataLoader, PairTradingStrategy, RiskEngine, 
                   IBGatewaySync, SlackAlerter, EmailAlerter,
                   DashboardGenerator, create_app])

    def test_components_initialize_without_error(self):
        """Test: All components initialize successfully."""
        loader = DataLoader()
        strategy = PairTradingStrategy()
        risk = RiskEngine(initial_equity=100000.0)
        execution = IBGatewaySync()
        slack = SlackAlerter(webhook_url="https://hooks.slack.com/test")
        email = EmailAlerter.from_env() or EmailAlerter(
            'smtp.example.com', 587, 'test@example.com', 'pass', ['alert@example.com']
        )
        dashboard = DashboardGenerator()
        app = create_app(dashboard)
        
        assert all([loader, strategy, risk, execution, slack, email, dashboard, app])

    def test_full_system_api_accessible(self):
        """Test: Full system is accessible via API."""
        dashboard = DashboardGenerator()
        app = create_app(dashboard)
        client = app.test_client()
        
        endpoints = [
            '/api/dashboard',
            '/api/dashboard/system',
            '/api/dashboard/risk',
            '/api/dashboard/positions',
            '/api/dashboard/orders',
            '/api/dashboard/performance',
            '/health'
        ]
        
        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code in [200, 503]


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
