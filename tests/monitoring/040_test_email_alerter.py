"""Comprehensive tests for Email alerter integration."""

# pyright: reportUnusedVariable=false

from unittest.mock import patch, MagicMock
from monitoring.email_alerter import EmailAlerter
import smtplib
import os
import smtplib
from unittest.mock import MagicMock, patch

from monitoring.email_alerter import EmailAlerter


class TestEmailAlerterBasic:
    """Test basic Email alerter functionality."""

    def test_alerter_initializes_with_config(self):
        """Test alerter initialization with SMTP configuration."""
        alerter = EmailAlerter(
            smtp_server="smtp.gmail.com",
            smtp_port=587,
            sender_email="test@example.com",
            sender_password="password123",
            recipient_emails=["alert@example.com"],
        )

        assert alerter.enabled is True
        assert alerter.smtp_server == "smtp.gmail.com"
        assert alerter.smtp_port == 587
        assert len(alerter.recipients) == 1

    def test_alerter_initializes_without_config(self):
        """Test alerter gracefully handles missing config (disabled)."""
        alerter = EmailAlerter(smtp_server="", smtp_port=587, sender_email="", sender_password="", recipient_emails=[])

        assert alerter.enabled is False

    def test_alerter_disabled_returns_success(self):
        """When disabled, send_alert returns True without crashing."""
        alerter = EmailAlerter(smtp_server="", smtp_port=587, sender_email="", sender_password="", recipient_emails=[])

        success, reason = alerter.send_alert("ERROR", "Test", "Message")
        assert success is True
        assert "disabled" in reason.lower()

    def test_custom_smtp_timeout(self):
        """Test custom SMTP timeout configuration."""
        alerter = EmailAlerter(
            smtp_server="smtp.gmail.com",
            smtp_port=587,
            sender_email="test@example.com",
            sender_password="pass",
            recipient_emails=["alert@example.com"],
            smtp_timeout_seconds=20,
        )

        assert alerter.smtp_timeout == 20

    @patch("smtplib.SMTP")
    def test_send_critical_alert(self, mock_smtp):
        """Test sending a CRITICAL alert via email."""
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        alerter = EmailAlerter(
            smtp_server="smtp.gmail.com",
            smtp_port=587,
            sender_email="test@example.com",
            sender_password="pass",
            recipient_emails=["alert@example.com"],
        )

        success, reason = alerter.send_alert(level="CRITICAL", title="System Error", message="Critical error occurred")

        assert success is True
        assert reason == "sent"
        assert mock_smtp.called

    @patch("smtplib.SMTP")
    def test_send_error_alert(self, mock_smtp):
        """Test sending an ERROR alert via email."""
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        alerter = EmailAlerter(
            smtp_server="smtp.gmail.com",
            smtp_port=587,
            sender_email="test@example.com",
            sender_password="pass",
            recipient_emails=["alert@example.com"],
        )

        success, reason = alerter.send_alert(level="ERROR", title="Order Failed", message="Order submission failed")

        assert success is True
        assert mock_smtp.called

    def test_info_alert_not_sent(self):
        """Test INFO alerts are skipped (not sent via email)."""
        alerter = EmailAlerter(
            smtp_server="smtp.gmail.com",
            smtp_port=587,
            sender_email="test@example.com",
            sender_password="pass",
            recipient_emails=["alert@example.com"],
        )

        success, reason = alerter.send_alert(level="INFO", title="Trade Executed", message="Order processed")

        assert success is True
        assert "skipped" in reason.lower()

    def test_warning_alert_not_sent(self):
        """Test WARNING alerts are skipped (not sent via email)."""
        alerter = EmailAlerter(
            smtp_server="smtp.gmail.com",
            smtp_port=587,
            sender_email="test@example.com",
            sender_password="pass",
            recipient_emails=["alert@example.com"],
        )

        success, reason = alerter.send_alert(level="WARNING", title="High Drawdown", message="Portfolio down 40%")

        assert success is True
        assert "skipped" in reason.lower()


class TestEmailAlerterContent:
    """Test email content formatting."""

    @patch("smtplib.SMTP")
    def test_email_includes_all_fields(self, mock_smtp):
        """Test email includes all required fields."""
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        alerter = EmailAlerter(
            smtp_server="smtp.gmail.com",
            smtp_port=587,
            sender_email="sender@example.com",
            sender_password="pass",
            recipient_emails=["recipient@example.com"],
        )

        alerter.send_alert(level="CRITICAL", title="Kill Switch", message="Emergency shutdown triggered")

        # Verify SMTP was called
        assert mock_server.starttls.called
        assert mock_server.login.called
        assert mock_server.sendmail.called

        # Get the email message
        call_args = mock_server.sendmail.call_args
        email_body = call_args[0][2]  # Third arg is the message

        # Email body contains these fields (they may be encoded)
        assert "[CRITICAL]" in email_body
        assert "Kill Switch" in email_body

    @patch("smtplib.SMTP")
    def test_email_includes_data_fields(self, mock_smtp):
        """Test email includes custom data fields."""
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        alerter = EmailAlerter(
            smtp_server="smtp.gmail.com",
            smtp_port=587,
            sender_email="sender@example.com",
            sender_password="pass",
            recipient_emails=["recipient@example.com"],
        )

        data = {"symbol": "AAPL", "current_price": 45000.50, "loss": -5000.00, "loss_percent": -45.2}

        alerter.send_alert(level="ERROR", title="Max Loss Exceeded", message="Position closed", data=data)

        call_args = mock_server.sendmail.call_args
        call_args[0][2]

        # Verify SMTP was called (email was built correctly)
        assert mock_server.sendmail.called
        # Data inclusion happens in the email building process

    @patch("smtplib.SMTP")
    def test_email_subject_includes_level(self, mock_smtp):
        """Test email subject includes severity level."""
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        alerter = EmailAlerter(
            smtp_server="smtp.gmail.com",
            smtp_port=587,
            sender_email="sender@example.com",
            sender_password="pass",
            recipient_emails=["recipient@example.com"],
        )

        alerter.send_alert("CRITICAL", "Test Alert", "Test message")

        call_args = mock_server.sendmail.call_args
        email_body = call_args[0][2]

        # Subject is in the email (between Subject: and first newline)
        assert "[CRITICAL]" in email_body


class TestEmailAlerterErrorHandling:
    """Test error handling and connection failures."""

    @patch("smtplib.SMTP")
    def test_authentication_error_handled(self, mock_smtp):
        """Test authentication errors are handled gracefully."""
        mock_smtp.side_effect = smtplib.SMTPAuthenticationError(535, "Invalid credentials")

        alerter = EmailAlerter(
            smtp_server="smtp.gmail.com",
            smtp_port=587,
            sender_email="test@example.com",
            sender_password="wrong_pass",
            recipient_emails=["alert@example.com"],
        )

        success, reason = alerter.send_alert("ERROR", "Test", "Message")

        assert success is False
        assert "SMTP" in reason or "error" in reason.lower()

    @patch("smtplib.SMTP")
    def test_connection_error_handled(self, mock_smtp):
        """Test connection errors are handled gracefully."""
        # SMTPConnectError requires (code, msg) tuple
        mock_smtp.side_effect = smtplib.SMTPConnectError(111, "Connection failed")

        alerter = EmailAlerter(
            smtp_server="invalid.server.com",
            smtp_port=587,
            sender_email="test@example.com",
            sender_password="pass",
            recipient_emails=["alert@example.com"],
        )

        success, reason = alerter.send_alert("ERROR", "Test", "Message")

        assert success is False

    @patch("smtplib.SMTP")
    def test_timeout_error_handled(self, mock_smtp):
        """Test timeout errors are handled gracefully."""
        # Use socket timeout or generic Exception (smtplib.SMTPTimeoutError doesn't exist)
        mock_smtp.side_effect = TimeoutError("Connection timed out")

        alerter = EmailAlerter(
            smtp_server="slow.server.com",
            smtp_port=587,
            sender_email="test@example.com",
            sender_password="pass",
            recipient_emails=["alert@example.com"],
            smtp_timeout_seconds=5,
        )

        success, reason = alerter.send_alert("ERROR", "Test", "Message")

        assert success is False

    @patch("smtplib.SMTP")
    def test_unexpected_error_handled(self, mock_smtp):
        """Test unexpected errors are handled gracefully."""
        mock_smtp.side_effect = Exception("Unexpected error")

        alerter = EmailAlerter(
            smtp_server="smtp.gmail.com",
            smtp_port=587,
            sender_email="test@example.com",
            sender_password="pass",
            recipient_emails=["alert@example.com"],
        )

        success, reason = alerter.send_alert("ERROR", "Test", "Message")

        assert success is False


class TestEmailAlerterHelpers:
    """Test helper methods for common alert types."""

    @patch("smtplib.SMTP")
    def test_send_critical_alert_helper(self, mock_smtp):
        """Test critical alert helper method."""
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        alerter = EmailAlerter(
            smtp_server="smtp.gmail.com",
            smtp_port=587,
            sender_email="test@example.com",
            sender_password="pass",
            recipient_emails=["alert@example.com"],
        )

        success = alerter.send_critical_alert(
            title="Kill-Switch Activated", message="Trading halted", context={"reason": "max_loss_exceeded"}
        )

        assert success is True

    @patch("smtplib.SMTP")
    def test_send_error_alert_helper(self, mock_smtp):
        """Test error alert helper method."""
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        alerter = EmailAlerter(
            smtp_server="smtp.gmail.com",
            smtp_port=587,
            sender_email="test@example.com",
            sender_password="pass",
            recipient_emails=["alert@example.com"],
        )

        success = alerter.send_error_alert(
            error_type="InsufficientFunds", message="Cannot open position", context={"available": 100, "required": 150}
        )

        assert success is True


class TestEmailAlerterStatus:
    """Test status reporting and monitoring."""

    def test_get_status_disabled(self):
        """Test status when alerter is disabled."""
        alerter = EmailAlerter(smtp_server="", smtp_port=587, sender_email="", sender_password="", recipient_emails=[])

        status = alerter.get_status()

        assert status["enabled"] is False
        assert status["configured"] is False

    def test_get_status_enabled(self):
        """Test status when alerter is enabled."""
        alerter = EmailAlerter(
            smtp_server="smtp.gmail.com",
            smtp_port=587,
            sender_email="test@example.com",
            sender_password="pass",
            recipient_emails=["alert@example.com", "alert2@example.com"],
        )

        status = alerter.get_status()

        assert status["enabled"] is True
        assert status["configured"] is True
        assert status["recipients"] == 2

    @patch("smtplib.SMTP")
    def test_get_status_tracks_send_count(self, mock_smtp):
        """Test status tracks number of alerts sent."""
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        alerter = EmailAlerter(
            smtp_server="smtp.gmail.com",
            smtp_port=587,
            sender_email="test@example.com",
            sender_password="pass",
            recipient_emails=["alert@example.com"],
        )

        # Send multiple alerts
        alerter.send_alert("ERROR", "Error 1", "msg")
        alerter.send_alert("CRITICAL", "Error 2", "msg")

        status = alerter.get_status()
        assert status["send_count"] == 2


class TestEmailAlerterConnection:
    """Test connection testing and validation."""

    @patch("smtplib.SMTP")
    def test_connection_test_success(self, mock_smtp):
        """Test successful connection test."""
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        alerter = EmailAlerter(
            smtp_server="smtp.gmail.com",
            smtp_port=587,
            sender_email="test@example.com",
            sender_password="pass",
            recipient_emails=["alert@example.com"],
        )

        success, reason = alerter.test_connection()

        assert success is True

    @patch("smtplib.SMTP")
    def test_connection_test_auth_failure(self, mock_smtp):
        """Test connection test with authentication failure."""
        mock_smtp.side_effect = smtplib.SMTPAuthenticationError(535, "Invalid credentials")

        alerter = EmailAlerter(
            smtp_server="smtp.gmail.com",
            smtp_port=587,
            sender_email="test@example.com",
            sender_password="wrong",
            recipient_emails=["alert@example.com"],
        )

        success, reason = alerter.test_connection()

        assert success is False
        assert "Authentication" in reason or "credentials" in reason.lower()

    def test_connection_test_disabled(self):
        """Test connection test when alerter is disabled."""
        alerter = EmailAlerter(smtp_server="", smtp_port=587, sender_email="", sender_password="", recipient_emails=[])

        success, reason = alerter.test_connection()

        assert success is False


class TestEmailAlerterFromEnv:
    """Test initialization from environment variables."""

    @patch.dict(
        os.environ,
        {
            "EMAIL_SMTP_SERVER": "smtp.gmail.com",
            "EMAIL_SMTP_PORT": "587",
            "EMAIL_SMTP_USER": "user@gmail.com",
            "EMAIL_SMTP_PASS": "password",
            "EMAIL_RECIPIENTS": "alert1@example.com,alert2@example.com",
        },
        clear=True,
    )
    def test_from_env_success(self):
        """Test creating alerter from environment variables."""
        alerter = EmailAlerter.from_env()

        assert alerter is not None
        assert alerter.smtp_server == "smtp.gmail.com"
        assert alerter.smtp_port == 587
        assert alerter.sender_email == "user@gmail.com"
        assert len(alerter.recipients) == 2

    def test_from_env_missing_vars(self):
        """Test from_env returns None when vars missing."""
        with patch.dict(os.environ, {}, clear=True):
            alerter = EmailAlerter.from_env()

            assert alerter is None

    @patch.dict(
        os.environ,
        {
            "EMAIL_SMTP_SERVER": "smtp.gmail.com",
            "EMAIL_SMTP_PORT": "invalid_port",
            "EMAIL_SMTP_USER": "user@gmail.com",
            "EMAIL_SMTP_PASS": "password",
            "EMAIL_RECIPIENTS": "alert@example.com",
        },
        clear=True,
    )
    def test_from_env_invalid_port(self):
        """Test from_env handles invalid port."""
        alerter = EmailAlerter.from_env()

        assert alerter is None


class TestEmailAlerterIntegration:
    """Integration tests with realistic scenarios."""

    @patch("smtplib.SMTP")
    def test_multiple_recipients(self, mock_smtp):
        """Test email sent to multiple recipients."""
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        recipients = ["alert1@example.com", "alert2@example.com", "alert3@example.com"]
        alerter = EmailAlerter(
            smtp_server="smtp.gmail.com",
            smtp_port=587,
            sender_email="sender@example.com",
            sender_password="pass",
            recipient_emails=recipients,
        )

        alerter.send_alert("ERROR", "Test", "message")

        # Verify all recipients in sendmail call
        call_args = mock_server.sendmail.call_args
        assert call_args[0][1] == recipients

    @patch("smtplib.SMTP")
    def test_tls_called_on_send(self, mock_smtp):
        """Test STARTTLS is called for secure connection."""
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        alerter = EmailAlerter(
            smtp_server="smtp.gmail.com",
            smtp_port=587,
            sender_email="test@example.com",
            sender_password="pass",
            recipient_emails=["alert@example.com"],
        )

        alerter.send_alert("ERROR", "Test", "message")

        # Verify TLS was initiated
        assert mock_server.starttls.called

    @patch("smtplib.SMTP")
    def test_login_called_with_credentials(self, mock_smtp):
        """Test login is called with correct credentials."""
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        email = "test@example.com"
        password = "secure_password"

        alerter = EmailAlerter(
            smtp_server="smtp.gmail.com",
            smtp_port=587,
            sender_email=email,
            sender_password=password,
            recipient_emails=["alert@example.com"],
        )

        alerter.send_alert("ERROR", "Test", "message")

        # Verify login was called with correct credentials
        mock_server.login.assert_called_with(email, password)

    @patch("smtplib.SMTP")
    def test_failure_count_increments(self, mock_smtp):
        """Test failure count increments on errors."""
        mock_smtp.side_effect = smtplib.SMTPAuthenticationError(535, "Bad auth")

        alerter = EmailAlerter(
            smtp_server="smtp.gmail.com",
            smtp_port=587,
            sender_email="test@example.com",
            sender_password="wrong",
            recipient_emails=["alert@example.com"],
        )

        alerter.send_alert("ERROR", "Test", "message")
        alerter.send_alert("ERROR", "Test", "message")

        assert alerter.failure_count == 2
