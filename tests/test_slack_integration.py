"""Comprehensive tests for Slack alerter integration."""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from monitoring.slack_alerter import SlackAlerter
import requests


class TestSlackAlerterBasic:
    """Test basic Slack alerter functionality."""

    def test_alerter_initializes_with_webhook(self):
        """Test alerter initialization with webhook URL."""
        webhook = "https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXXXXXX"
        alerter = SlackAlerter(webhook_url=webhook)

        assert alerter.enabled is True
        assert alerter.webhook_url == webhook
        assert alerter.throttle_seconds == 30
        assert len(alerter.last_alert_time) == 0

    def test_alerter_initializes_without_webhook(self):
        """Test alerter gracefully handles missing webhook (disabled)."""
        alerter = SlackAlerter(webhook_url=None)

        assert alerter.enabled is False
        assert alerter.webhook_url is None

    def test_alerter_disabled_returns_success(self):
        """When disabled, send_alert returns True without crashing."""
        alerter = SlackAlerter(webhook_url=None)

        success, reason = alerter.send_alert('INFO', 'Test', 'Message')
        assert success is True
        assert 'disabled' in reason.lower()

    def test_custom_throttle_seconds(self):
        """Test custom throttle duration."""
        alerter = SlackAlerter(
            webhook_url="https://example.com",
            throttle_seconds=60
        )

        assert alerter.throttle_seconds == 60

    @patch('requests.post')
    def test_send_alert_success(self, mock_post):
        """Test successful alert sending."""
        mock_post.return_value.status_code = 200

        alerter = SlackAlerter(webhook_url="https://hooks.slack.com/test")
        success, reason = alerter.send_alert(
            level='ERROR',
            title='Test Error',
            message='Something went wrong'
        )

        assert success is True
        assert reason == "sent"
        assert mock_post.called

    @patch('requests.post')
    def test_send_alert_with_data_fields(self, mock_post):
        """Test alert includes custom data fields."""
        mock_post.return_value.status_code = 200

        alerter = SlackAlerter(webhook_url="https://hooks.slack.com/test")
        data = {'symbol': 'BTC/USDT', 'price': 45000.50, 'quantity': 0.5}

        success, reason = alerter.send_alert(
            level='INFO',
            title='Trade Alert',
            message='Buy order executed',
            data=data
        )

        assert success is True

        # Verify payload includes fields
        call_args = mock_post.call_args
        payload = call_args[1]['json']
        fields = payload['attachments'][0]['fields']

        # Should have level, timestamp, plus 3 custom fields
        assert len(fields) >= 5
        field_titles = [f['title'] for f in fields]
        assert 'symbol' in field_titles
        assert 'price' in field_titles
        assert 'quantity' in field_titles

    @patch('requests.post')
    def test_send_alert_color_coding(self, mock_post):
        """Test color coding by severity level."""
        mock_post.return_value.status_code = 200

        alerter = SlackAlerter(webhook_url="https://hooks.slack.com/test")

        levels_colors = {
            'CRITICAL': '#ff0000',
            'ERROR': '#ff6600',
            'WARNING': '#ffff00',
            'INFO': '#00ff00',
        }

        for level, expected_color in levels_colors.items():
            alerter.reset_throttle()  # Reset throttle
            alerter.send_alert(level=level, title='Test', message='msg')

            call_args = mock_post.call_args
            payload = call_args[1]['json']
            actual_color = payload['attachments'][0]['color']

            assert actual_color == expected_color, f"Level {level} has wrong color"


class TestSlackAlerterThrottling:
    """Test throttling behavior to prevent alert spam."""

    @patch('requests.post')
    def test_duplicate_alert_throttled(self, mock_post):
        """Test duplicate alerts are throttled."""
        mock_post.return_value.status_code = 200

        alerter = SlackAlerter(
            webhook_url="https://hooks.slack.com/test",
            throttle_seconds=2
        )

        # First alert
        success1, reason1 = alerter.send_alert('ERROR', 'Test', 'msg1')
        assert success1 is True

        # Immediate second alert (same key) - should be throttled
        success2, reason2 = alerter.send_alert('ERROR', 'Test', 'msg2')
        assert success2 is False
        assert 'throttled' in reason2.lower()

        # Only first call made
        assert mock_post.call_count == 1

    @patch('requests.post')
    def test_throttle_expires(self, mock_post):
        """Test throttle expires after timeout period."""
        mock_post.return_value.status_code = 200

        alerter = SlackAlerter(
            webhook_url="https://hooks.slack.com/test",
            throttle_seconds=1
        )

        # First alert
        success1, _ = alerter.send_alert('ERROR', 'Test', 'msg1')
        assert success1 is True
        assert mock_post.call_count == 1

        # Wait for throttle to expire
        time.sleep(1.1)

        # Second alert should succeed (throttle expired)
        success2, _ = alerter.send_alert('ERROR', 'Test', 'msg2')
        assert success2 is True
        assert mock_post.call_count == 2

    @patch('requests.post')
    def test_different_titles_not_throttled(self, mock_post):
        """Test alerts with different titles bypass throttling."""
        mock_post.return_value.status_code = 200

        alerter = SlackAlerter(webhook_url="https://hooks.slack.com/test")

        # Two different alerts
        success1, _ = alerter.send_alert('ERROR', 'Error A', 'msg1')
        success2, _ = alerter.send_alert('ERROR', 'Error B', 'msg2')

        assert success1 is True
        assert success2 is True
        assert mock_post.call_count == 2

    @patch('requests.post')
    def test_different_levels_not_throttled(self, mock_post):
        """Test alerts with different levels bypass throttling."""
        mock_post.return_value.status_code = 200

        alerter = SlackAlerter(webhook_url="https://hooks.slack.com/test")

        # Same title, different levels
        success1, _ = alerter.send_alert('ERROR', 'Issue', 'msg1')
        success2, _ = alerter.send_alert('WARNING', 'Issue', 'msg2')

        assert success1 is True
        assert success2 is True
        assert mock_post.call_count == 2

    def test_reset_throttle_specific(self):
        """Test resetting throttle for specific alert."""
        alerter = SlackAlerter(webhook_url="https://hooks.slack.com/test")

        # Manually add throttle entries
        alerter.last_alert_time['ERROR:Issue'] = time.time()
        alerter.last_alert_time['WARNING:Issue'] = time.time()

        # Reset specific
        alerter.reset_throttle('ERROR', 'Issue')

        assert 'ERROR:Issue' not in alerter.last_alert_time
        assert 'WARNING:Issue' in alerter.last_alert_time

    def test_reset_throttle_all(self):
        """Test resetting all throttles."""
        alerter = SlackAlerter(webhook_url="https://hooks.slack.com/test")

        alerter.last_alert_time['ERROR:Issue'] = time.time()
        alerter.last_alert_time['WARNING:Issue'] = time.time()

        alerter.reset_throttle()

        assert len(alerter.last_alert_time) == 0


class TestSlackAlerterErrorHandling:
    """Test error handling and network failures."""

    @patch('requests.post')
    def test_http_error_handled(self, mock_post):
        """Test HTTP errors are handled gracefully."""
        mock_post.return_value.status_code = 400

        alerter = SlackAlerter(webhook_url="https://hooks.slack.com/test")
        success, reason = alerter.send_alert('INFO', 'Test', 'msg')

        assert success is False
        assert 'HTTP 400' in reason

    @patch('requests.post')
    def test_connection_error_handled(self, mock_post):
        """Test connection errors are handled gracefully."""
        mock_post.side_effect = requests.exceptions.ConnectionError("Connection refused")

        alerter = SlackAlerter(webhook_url="https://hooks.slack.com/test")
        success, reason = alerter.send_alert('INFO', 'Test', 'msg')

        assert success is False
        assert 'connection' in reason.lower()

    @patch('requests.post')
    def test_timeout_handled(self, mock_post):
        """Test request timeouts are handled gracefully."""
        mock_post.side_effect = requests.exceptions.Timeout("Request timed out")

        alerter = SlackAlerter(webhook_url="https://hooks.slack.com/test")
        success, reason = alerter.send_alert('INFO', 'Test', 'msg')

        assert success is False
        assert 'timeout' in reason.lower()

    @patch('requests.post')
    def test_unexpected_error_handled(self, mock_post):
        """Test unexpected errors are handled gracefully."""
        mock_post.side_effect = Exception("Unexpected error")

        alerter = SlackAlerter(webhook_url="https://hooks.slack.com/test")
        success, reason = alerter.send_alert('INFO', 'Test', 'msg')

        assert success is False

    @patch('requests.post')
    def test_invalid_level_defaults_to_info(self, mock_post):
        """Test invalid levels default to INFO."""
        mock_post.return_value.status_code = 200

        alerter = SlackAlerter(webhook_url="https://hooks.slack.com/test")
        success, _ = alerter.send_alert('INVALID_LEVEL', 'Test', 'msg')

        assert success is True
        # Should still have sent with defaulted level


class TestSlackAlerterHelpers:
    """Test helper methods for common alert types."""

    @patch('requests.post')
    def test_send_trade_alert(self, mock_post):
        """Test sending a trade execution alert."""
        mock_post.return_value.status_code = 200

        alerter = SlackAlerter(webhook_url="https://hooks.slack.com/test")
        success = alerter.send_trade_alert(
            symbol='BTC/USDT',
            side='buy',
            quantity=0.5,
            price=45000.50,
            order_id='12345'
        )

        assert success is True
        assert mock_post.called

    @patch('requests.post')
    def test_send_error_alert(self, mock_post):
        """Test sending an error alert."""
        mock_post.return_value.status_code = 200

        alerter = SlackAlerter(webhook_url="https://hooks.slack.com/test")
        success = alerter.send_error_alert(
            error_type='InsufficientFunds',
            message='Cannot open position - insufficient balance',
            context={'available': 100.0, 'required': 150.0}
        )

        assert success is True

    @patch('requests.post')
    def test_send_critical_alert(self, mock_post):
        """Test sending a critical alert."""
        mock_post.return_value.status_code = 200

        alerter = SlackAlerter(webhook_url="https://hooks.slack.com/test")
        success = alerter.send_critical_alert(
            title='Kill-Switch Activated',
            message='Trading halted due to max loss exceeding threshold',
            context={'max_loss': -5000.0, 'threshold': -4500.0}
        )

        assert success is True

    @patch('requests.post')
    def test_trade_alert_includes_order_id(self, mock_post):
        """Test trade alert includes order ID when provided."""
        mock_post.return_value.status_code = 200

        alerter = SlackAlerter(webhook_url="https://hooks.slack.com/test")
        alerter.send_trade_alert(
            symbol='BTC/USDT',
            side='sell',
            quantity=0.25,
            price=44000,
            order_id='order_123'
        )

        call_args = mock_post.call_args
        payload = call_args[1]['json']
        fields = payload['attachments'][0]['fields']
        field_titles = [f['title'] for f in fields]

        assert 'order_id' in field_titles


class TestSlackAlerterStatus:
    """Test status reporting and monitoring."""

    def test_get_status_disabled(self):
        """Test status when alerter is disabled."""
        alerter = SlackAlerter(webhook_url=None)
        status = alerter.get_status()

        assert status['enabled'] is False
        assert status['webhook_configured'] is False

    def test_get_status_enabled(self):
        """Test status when alerter is enabled."""
        alerter = SlackAlerter(webhook_url="https://hooks.slack.com/test")
        status = alerter.get_status()

        assert status['enabled'] is True
        assert status['webhook_configured'] is True
        assert status['throttle_seconds'] == 30
        assert status['pending_throttles'] == 0

    @patch('requests.post')
    def test_get_status_with_throttles(self, mock_post):
        """Test status includes pending throttles."""
        mock_post.return_value.status_code = 200

        alerter = SlackAlerter(webhook_url="https://hooks.slack.com/test")

        # Send a few alerts
        alerter.send_alert('ERROR', 'Error 1', 'msg')
        alerter.send_alert('WARNING', 'Warning 1', 'msg')

        status = alerter.get_status()
        assert status['pending_throttles'] == 2
        assert len(status['recent_alerts']) == 2


class TestSlackAlerterIntegration:
    """Integration tests with realistic scenarios."""

    @patch('requests.post')
    def test_rapid_fire_alerts_throttled(self, mock_post):
        """Test rapid fire same alert is throttled."""
        mock_post.return_value.status_code = 200

        alerter = SlackAlerter(
            webhook_url="https://hooks.slack.com/test",
            throttle_seconds=5
        )

        # Simulate rapid API errors
        for i in range(10):
            alerter.send_alert('ERROR', 'API Error', f'attempt {i}')

        # Only first should succeed
        assert mock_post.call_count == 1

    @patch('requests.post')
    def test_different_alerts_all_sent(self, mock_post):
        """Test different alerts all get sent."""
        mock_post.return_value.status_code = 200

        alerter = SlackAlerter(webhook_url="https://hooks.slack.com/test")

        # Various alerts
        alerter.send_alert('CRITICAL', 'Kill Switch', 'Activated')
        alerter.send_alert('ERROR', 'Order Failed', 'Insufficient funds')
        alerter.send_alert('WARNING', 'High Drawdown', 'At 45% threshold')
        alerter.send_alert('INFO', 'Trade Executed', 'BTC buy')

        # All should be sent
        assert mock_post.call_count == 4

    @patch('requests.post')
    def test_payload_structure(self, mock_post):
        """Test Slack payload structure is correct."""
        mock_post.return_value.status_code = 200

        alerter = SlackAlerter(webhook_url="https://hooks.slack.com/test")
        alerter.send_alert(
            level='ERROR',
            title='Test Error',
            message='Detailed error message',
            data={'symbol': 'BTC/USDT', 'amount': 100}
        )

        call_args = mock_post.call_args
        payload = call_args[1]['json']

        # Verify structure
        assert 'attachments' in payload
        assert len(payload['attachments']) == 1
        attachment = payload['attachments'][0]

        assert 'color' in attachment
        assert 'title' in attachment
        assert 'text' in attachment
        assert 'ts' in attachment
        assert 'fields' in attachment


class TestSlackAlerterTimeoutConfig:
    """Test timeout configuration and behavior."""

    def test_custom_timeout(self):
        """Test custom request timeout can be configured."""
        alerter = SlackAlerter(
            webhook_url="https://hooks.slack.com/test",
            timeout_seconds=10
        )

        assert alerter.timeout_seconds == 10

    @patch('requests.post')
    def test_timeout_passed_to_requests(self, mock_post):
        """Test timeout is passed to requests.post call."""
        mock_post.return_value.status_code = 200

        alerter = SlackAlerter(
            webhook_url="https://hooks.slack.com/test",
            timeout_seconds=15
        )

        alerter.send_alert('INFO', 'Test', 'msg')

        # Verify timeout was passed
        call_args = mock_post.call_args
        assert call_args[1]['timeout'] == 15
