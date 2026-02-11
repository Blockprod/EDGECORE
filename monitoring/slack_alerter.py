"""Slack alerting integration for real-time trading alerts."""

import requests
import time
from typing import Dict, Optional, Tuple
from datetime import datetime
import structlog

logger = structlog.get_logger(__name__)


class SlackAlerter:
    """Send critical trading alerts to Slack webhook."""

    # Color codes for severity levels
    COLOR_MAP = {
        'CRITICAL': '#ff0000',  # Red
        'ERROR': '#ff6600',     # Orange
        'WARNING': '#ffff00',   # Yellow
        'INFO': '#00ff00',      # Green
    }

    def __init__(self, webhook_url: Optional[str] = None, 
                 throttle_seconds: int = 30,
                 timeout_seconds: int = 5):
        """
        Initialize Slack alerter.

        Args:
            webhook_url: Slack Incoming Webhook URL
                        If None, alerter disabled but doesn't crash
            throttle_seconds: Minimum seconds between duplicate alerts (default 30)
            timeout_seconds: HTTP request timeout (default 5)
        """
        self.webhook_url = webhook_url
        self.throttle_seconds = throttle_seconds
        self.timeout_seconds = timeout_seconds
        self.last_alert_time: Dict[str, float] = {}  # Track by alert key
        self.enabled = webhook_url is not None
        
        if not self.enabled:
            logger.warning(
                "slack_alerter_disabled",
                reason="SLACK_WEBHOOK_URL not configured - critical alerts will NOT be sent to Slack"
            )

    def send_alert(self, level: str, title: str, message: str,
                   data: Optional[Dict] = None) -> Tuple[bool, str]:
        """
        Send alert to Slack.

        Args:
            level: CRITICAL, ERROR, WARNING, INFO
            title: Short alert title (max 150 chars)
            message: Detailed alert message
            data: Optional metadata dict to include as fields

        Returns:
            Tuple of (success: bool, reason: str)
        """

        if not self.enabled:
            logger.info("SLACK_DISABLED", level=level, title=title)
            return True, "Slack alerter disabled"

        try:
            # Validate level
            if level not in self.COLOR_MAP:
                logger.warning("SLACK_INVALID_LEVEL", level=level)
                level = 'INFO'

            # Check throttle
            alert_key = f"{level}:{title}"
            now = time.time()

            if alert_key in self.last_alert_time:
                elapsed = now - self.last_alert_time[alert_key]
                if elapsed < self.throttle_seconds:
                    reason = f"throttled ({elapsed:.1f}s < {self.throttle_seconds}s)"
                    logger.debug("SLACK_ALERT_THROTTLED", alert_key=alert_key, reason=reason)
                    return False, reason

            # Build Slack payload
            payload = {
                'attachments': [{
                    'color': self.COLOR_MAP.get(level, '#cccccc'),
                    'title': title,
                    'text': message,
                    'ts': int(now),
                    'fields': [
                        {'title': 'Severity', 'value': level, 'short': True},
                        {'title': 'Timestamp', 'value': datetime.now().isoformat(), 'short': True}
                    ]
                }]
            }

            # Add custom fields from data dict
            if data:
                for key, value in data.items():
                    payload['attachments'][0]['fields'].append({
                        'title': key,
                        'value': str(value)[:1000],  # Cap at 1000 chars
                        'short': len(str(value)) < 50
                    })

            # Send to Slack
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=self.timeout_seconds
            )

            if response.status_code == 200:
                self.last_alert_time[alert_key] = now
                logger.info("SLACK_ALERT_SENT", level=level, title=title)
                return True, "sent"
            else:
                logger.error(
                    "SLACK_ALERT_FAILED",
                    status=response.status_code,
                    response=response.text[:500]
                )
                return False, f"HTTP {response.status_code}"

        except requests.exceptions.Timeout:
            logger.error("SLACK_TIMEOUT", timeout=self.timeout_seconds)
            return False, "timeout"
        except requests.exceptions.ConnectionError as e:
            logger.error("SLACK_CONNECTION_ERROR", error=str(e)[:100])
            return False, "connection error"
        except Exception as e:
            logger.error("SLACK_UNEXPECTED_ERROR", error=str(e)[:100])
            return False, f"error: {str(e)[:50]}"

    def send_trade_alert(self, symbol: str, side: str, quantity: float,
                        price: float, order_id: str = None) -> bool:
        """Send a trade execution alert."""
        title = f"Trade Executed: {symbol} {side.upper()}"
        message = f"Executed {quantity} @ ${price}"
        data = {
            'symbol': symbol,
            'side': side,
            'quantity': quantity,
            'price': price,
        }
        if order_id:
            data['order_id'] = order_id

        success, _ = self.send_alert('INFO', title, message, data)
        return success

    def send_error_alert(self, error_type: str, message: str,
                        context: Optional[Dict] = None) -> bool:
        """Send an error alert."""
        title = f"Trading Error: {error_type}"
        data = context or {}

        success, _ = self.send_alert('ERROR', title, message, data)
        return success

    def send_critical_alert(self, title: str, message: str,
                           context: Optional[Dict] = None) -> bool:
        """Send a critical alert (highest priority)."""
        data = context or {}
        success, _ = self.send_alert('CRITICAL', title, message, data)
        return success

    def reset_throttle(self, level: str = None, title: str = None) -> None:
        """
        Reset throttle for testing/manual override.

        Args:
            level: If provided, only reset this level's throttle
            title: If provided with level, reset specific alert
        """
        if level and title:
            key = f"{level}:{title}"
            if key in self.last_alert_time:
                del self.last_alert_time[key]
                logger.debug("SLACK_THROTTLE_RESET", key=key)
        else:
            self.last_alert_time.clear()
            logger.debug("SLACK_THROTTLE_RESET_ALL")

    def get_status(self) -> Dict:
        """Get alerter status for monitoring."""
        return {
            'enabled': self.enabled,
            'webhook_configured': bool(self.webhook_url),
            'throttle_seconds': self.throttle_seconds,
            'pending_throttles': len(self.last_alert_time),
            'recent_alerts': list(self.last_alert_time.keys())[-5:] if self.last_alert_time else []
        }
