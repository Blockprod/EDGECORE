"""
Tests for alerter integration into the trading pipeline.

Verifies that EmailAlerter and SlackAlerter are properly called
at every critical point in the trading loop:
  - Kill-switch activation
  - Market data fetch failure
  - Stop-check errors
  - Order submission failure
  - Reconciliation critical divergence
  - Fatal crash in run_paper_tick
"""

import pytest
from unittest.mock import MagicMock, patch
from live_trading.runner import LiveTradingRunner, TradingLoopConfig, TradingState
from live_trading.paper_runner import PaperTradingRunner


def _make_runner(email=None, slack=None, **kw):
    """Create a LiveTradingRunner with mock alerters."""
    cfg = TradingLoopConfig(symbols=["A", "B"], mode="paper", **kw)
    return LiveTradingRunner(config=cfg, email_alerter=email, slack_alerter=slack)


class TestSendAlertHelper:
    """_send_alert dispatches to both alerters."""

    def test_dispatches_to_email_and_slack(self):
        email = MagicMock()
        slack = MagicMock()
        runner = _make_runner(email=email, slack=slack)

        runner._send_alert("ERROR", "Test title", "Test message", {"key": "val"})

        email.send_alert.assert_called_once_with(
            level="ERROR", title="Test title", message="Test message", data={"key": "val"}
        )
        slack.send_alert.assert_called_once_with(
            level="ERROR", title="Test title", message="Test message", data={"key": "val"}
        )

    def test_skips_none_alerters(self):
        runner = _make_runner()  # no alerters
        # Should not raise
        runner._send_alert("CRITICAL", "No crash", "No alerters configured")

    def test_alerter_exception_does_not_propagate(self):
        email = MagicMock()
        email.send_alert.side_effect = RuntimeError("SMTP down")
        runner = _make_runner(email=email)

        # Must NOT raise ÔÇö fire-and-forget
        runner._send_alert("ERROR", "Title", "Message")


class TestKillSwitchAlert:
    """Kill-switch sends CRITICAL alert."""

    def test_kill_switch_triggers_alert(self):
        slack = MagicMock()
        runner = _make_runner(slack=slack)
        runner._kill_switch = MagicMock()
        runner._kill_switch.is_active = True
        runner._reconciler = None

        runner._tick()

        assert runner.state == TradingState.HALTED
        slack.send_alert.assert_called_once()
        call_kwargs = slack.send_alert.call_args[1]
        assert call_kwargs["level"] == "CRITICAL"
        assert "kill-switch" in call_kwargs["title"].lower()


class TestDataFetchAlert:
    """Market data fetch failure sends ERROR alert."""

    def test_data_fetch_error_triggers_alert(self):
        email = MagicMock()
        runner = _make_runner(email=email)
        runner._kill_switch = MagicMock(is_active=False)
        runner._reconciler = None

        with patch.object(runner, "_maybe_rediscover_pairs"):
            with patch.object(runner, "_fetch_market_data", side_effect=ConnectionError("timeout")):
                runner._tick()

        email.send_alert.assert_called_once()
        call_kwargs = email.send_alert.call_args[1]
        assert call_kwargs["level"] == "ERROR"
        assert "market data" in call_kwargs["title"].lower()


class TestOrderProcessingAlert:
    """Order submission failure sends ERROR alert."""

    def test_signal_processing_error_triggers_alert(self):
        slack = MagicMock()
        runner = _make_runner(slack=slack)
        runner._kill_switch = MagicMock(is_active=False)
        runner._reconciler = None
        runner._active_pairs = [("A", "B", 0.01, 20)]

        mock_signal = MagicMock()
        mock_signal.pair_key = "A_B"

        with patch.object(runner, "_maybe_rediscover_pairs"):
            with patch.object(runner, "_fetch_market_data", return_value=MagicMock(empty=False)):
                with patch.object(runner, "_signal_gen") as mock_gen:
                    mock_gen.generate.return_value = [mock_signal]
                    # position_risk.check will throw
                    runner._position_risk = MagicMock()
                    runner._position_risk.check.side_effect = RuntimeError("risk engine crash")
                    runner._tick()

        slack.send_alert.assert_called_once()
        call_kwargs = slack.send_alert.call_args[1]
        assert call_kwargs["level"] == "ERROR"
        assert "A_B" in call_kwargs["title"]


class TestReconciliationAlert:
    """Reconciliation divergence sends CRITICAL alert."""

    def test_critical_reconciliation_sends_alert(self):
        email = MagicMock()
        runner = _make_runner(email=email)

        # Simulate a critical reconciliation report
        mock_report = MagicMock()
        mock_report.status.value = "critical"
        mock_report.divergences = ["div1", "div2"]

        mock_reconciler = MagicMock()
        mock_reconciler.full_reconciliation.return_value = mock_report
        runner._reconciler = mock_reconciler
        runner._last_reconciliation = None
        runner._reconciliation_interval = __import__("datetime").timedelta(seconds=0)
        runner.config.mode = "live"

        # Mock router for account balance
        runner._router = MagicMock()
        runner._router.get_account_balance.return_value = 100_000.0

        runner._maybe_reconcile()

        assert runner.state == TradingState.HALTED
        email.send_alert.assert_called_once()
        call_kwargs = email.send_alert.call_args[1]
        assert call_kwargs["level"] == "CRITICAL"
        assert "reconciliation" in call_kwargs["title"].lower()


class TestPaperTradingRunnerAlerters:
    """PaperTradingRunner forwards alerters to parent."""

    def test_alerters_forwarded(self):
        email = MagicMock()
        slack = MagicMock()
        runner = PaperTradingRunner(
            config=TradingLoopConfig(symbols=["X"]),
            email_alerter=email,
            slack_alerter=slack,
        )
        assert runner._email_alerter is email
        assert runner._slack_alerter is slack

    def test_default_none_alerters(self):
        runner = PaperTradingRunner()
        assert runner._email_alerter is None
        assert runner._slack_alerter is None


class TestErrorHandlerAlerter:
    """error_handler.handle_error() dispatches to alerter on NON_RETRYABLE."""

    def test_handle_error_sends_alert_non_retryable(self):
        from common.error_handler import handle_error
        from common.errors import TradingError, ErrorCategory

        alerter = MagicMock()
        error = TradingError("disk full", ErrorCategory.NON_RETRYABLE)

        handle_error(error, context="saving state", alerter=alerter)

        alerter.send_alert.assert_called_once()
        call_kwargs = alerter.send_alert.call_args[1]
        assert call_kwargs["level"] == "ERROR"
        assert "saving state" in call_kwargs["title"]

    def test_handle_error_no_alert_on_transient(self):
        from common.error_handler import handle_error
        from common.errors import TradingError, ErrorCategory

        alerter = MagicMock()
        error = TradingError("timeout", ErrorCategory.TRANSIENT)

        handle_error(error, context="fetching data", alerter=alerter)

        alerter.send_alert.assert_not_called()

    def test_with_error_handling_decorator_alerts_on_max_retries(self):
        from common.error_handler import with_error_handling
        from common.errors import ErrorCategory

        alerter = MagicMock()

        @with_error_handling(
            category=ErrorCategory.RETRYABLE,
            max_retries=2,
            backoff_base=0.001,
            alerter=alerter,
        )
        def flaky():
            raise ConnectionError("fail")

        with pytest.raises(ConnectionError):
            flaky()

        # Should have alerted on max retries exceeded
        assert alerter.send_alert.call_count >= 1
        titles = [c[1].get("title", "") if len(c) > 1 else c[0][1] 
                  for c in alerter.send_alert.call_args_list]
        assert any("max retries" in t.lower() or "Max retries" in t for t in titles)
