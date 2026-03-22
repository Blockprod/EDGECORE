"""Email alerting for critical trading events."""

import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

import structlog

logger = structlog.get_logger(__name__)


class EmailAlerter:
    """Send critical trading alerts via SMTP email."""

    def __init__(
        self,
        smtp_server: str,
        smtp_port: int,
        sender_email: str,
        sender_password: str,
        recipient_emails: list[str],
        smtp_timeout_seconds: int = 10,
    ):
        """
        Initialize Email alerter with SMTP configuration.

        Args:
            smtp_server: SMTP server hostname (e.g., 'smtp.gmail.com')
            smtp_port: SMTP port (usually 587 for TLS or 465 for SSL)
            sender_email: Email address to send from
            sender_password: Email account password or app token
            recipient_emails: List of recipient email addresses
            smtp_timeout_seconds: Connection timeout
        """
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.sender_email = sender_email
        self.sender_password = sender_password
        self.recipients = recipient_emails
        self.smtp_timeout = smtp_timeout_seconds
        self.enabled = bool(smtp_server and sender_email and recipient_emails)
        self.send_count = 0
        self.failure_count = 0
        # Set via alerter.trading_mode = "paper" | "live" | "backtest"
        # Overrides PROJECT_NAME env var when set
        self.trading_mode: str | None = None

    def send_alert(self, level: str, title: str, message: str, data: dict | None = None) -> tuple[bool, str]:
        """
        Send alert via email.

        Args:
            level: CRITICAL, ERROR, WARNING, INFO
            title: Alert title
            message: Alert message
            data: Optional metadata dict

        Returns:
            Tuple of (success: bool, reason: str)

        Note:
            Only sends ERROR and CRITICAL alerts (not INFO/WARNING spam)
        """

        if not self.enabled:
            logger.info("EMAIL_DISABLED", level=level, title=title)
            return True, "Email alerter disabled"

        # Only send ERROR and CRITICAL via email (not INFO/WARNING spam)
        if level not in ["ERROR", "CRITICAL"]:
            logger.debug("EMAIL_ALERT_SKIPPED", level=level, reason="only ERROR/CRITICAL sent via email")
            return True, f"skipped ({level} not sent via email)"

        try:
            # Build email
            msg = MIMEMultipart("text", "plain")
            msg["From"] = self.sender_email
            msg["To"] = ", ".join(self.recipients)
            base_name = os.environ.get("PROJECT_NAME", "EDGECORE")
            if self.trading_mode:
                project = f"{base_name} ÔÇö {self.trading_mode.title()} Trading"
            else:
                project = base_name
            msg["Subject"] = f"[{project}] [{level}] {title}"

            # Build body
            body = f"""{project} ÔÇö Trading System Alert

ÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉ
Project:     {project}
Severity:    {level}
Title:       {title}
Timestamp:   {datetime.now().isoformat()}
ÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉ

Message:
{message}

"""

            if data:
                body += "Details:\n"
                for key, value in data.items():
                    body += f"  ÔÇó {key}: {value}\n"

            body += """
ÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉ
This is an automated alert from {project} trading system.
Do not reply to this email.
ÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉ
"""

            msg.attach(MIMEText(body))

            # Send email via SMTP
            self._send_smtp(msg)

            self.send_count += 1
            logger.info("EMAIL_ALERT_SENT", level=level, title=title, recipients=len(self.recipients))
            return True, "sent"

        except smtplib.SMTPException as e:
            self.failure_count += 1
            logger.error("EMAIL_SMTP_ERROR", error=str(e)[:200])
            return False, f"SMTP error: {str(e)[:50]}"
        except Exception as e:
            self.failure_count += 1
            logger.error("EMAIL_UNEXPECTED_ERROR", error=str(e)[:200])
            return False, f"error: {str(e)[:50]}"

    def _send_smtp(self, msg: MIMEMultipart) -> None:
        """
        Send email via SMTP with TLS.

        Raises:
            smtplib.SMTPException: On SMTP errors
            Exception: On other errors
        """
        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=self.smtp_timeout) as server:
                server.starttls()  # Start TLS encryption
                server.login(self.sender_email, self.sender_password)
                server.sendmail(self.sender_email, self.recipients, msg.as_string())
        except smtplib.SMTPAuthenticationError as e:
            raise smtplib.SMTPException("Authentication failed - check credentials") from e
        except smtplib.SMTPConnectError as e:
            raise smtplib.SMTPException("Connection failed - check hostname/port") from e
        except (smtplib.SMTPException, TimeoutError) as e:
            raise smtplib.SMTPException(f"Timeout - no response in {self.smtp_timeout}s") from e

    def send_critical_alert(self, title: str, message: str, context: dict | None = None) -> bool:
        """Send a critical alert (highest priority)."""
        data = context or {}
        success, _ = self.send_alert("CRITICAL", title, message, data)
        return success

    def send_error_alert(self, error_type: str, message: str, context: dict | None = None) -> bool:
        """Send an error alert."""
        title = f"Error: {error_type}"
        data = context or {}
        success, _ = self.send_alert("ERROR", title, message, data)
        return success

    def get_status(self) -> dict:
        """Get alerter status for monitoring."""
        return {
            "enabled": self.enabled,
            "configured": bool(self.smtp_server and self.sender_email),
            "recipients": len(self.recipients),
            "send_count": self.send_count,
            "failure_count": self.failure_count,
            "recipient_list": self.recipients,
        }

    def test_connection(self) -> tuple[bool, str]:
        """
        Test SMTP connection without sending an email.

        Returns:
            Tuple of (success: bool, reason: str)
        """
        if not self.enabled:
            return False, "Email alerter not configured"

        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=self.smtp_timeout) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
            logger.info("EMAIL_CONNECTION_TEST_PASSED")
            return True, "Connection successful"
        except smtplib.SMTPAuthenticationError:
            return False, "Authentication failed - check credentials"
        except smtplib.SMTPConnectError:
            return False, "Connection failed - check hostname/port"
        except Exception as e:
            return False, str(e)[:100]

    @staticmethod
    def from_env() -> Optional["EmailAlerter"]:
        """
        Create EmailAlerter from environment variables.

        Supported env vars (checks both legacy and current names):
            - SMTP_SERVER / EMAIL_SMTP_SERVER:  SMTP hostname
            - SMTP_PORT / EMAIL_SMTP_PORT:      SMTP port
            - SENDER_EMAIL / EMAIL_SMTP_USER:   Sender email address
            - GOOGLE_MAIL_PASSWORD / EMAIL_SMTP_PASS:  Sender password / app token
            - RECEIVER_EMAIL / EMAIL_RECIPIENTS: Comma-separated recipient emails

        Returns:
            EmailAlerter instance or None if not configured
        """
        import os

        smtp_server = os.getenv("SMTP_SERVER") or os.getenv("EMAIL_SMTP_SERVER")
        smtp_port_str = os.getenv("SMTP_PORT") or os.getenv("EMAIL_SMTP_PORT")
        sender_email = os.getenv("SENDER_EMAIL") or os.getenv("EMAIL_SMTP_USER")
        sender_password = os.getenv("GOOGLE_MAIL_PASSWORD") or os.getenv("EMAIL_SMTP_PASS")
        recipients_str = os.getenv("RECEIVER_EMAIL") or os.getenv("EMAIL_RECIPIENTS")

        if not all([smtp_server, smtp_port_str, sender_email, sender_password, recipients_str]):
            logger.debug(
                "EMAIL_NOT_CONFIGURED",
                missing=[
                    "SMTP_SERVER" if not smtp_server else None,
                    "SMTP_PORT" if not smtp_port_str else None,
                    "SMTP_USER" if not sender_email else None,
                    "SMTP_PASS" if not sender_password else None,
                    "RECIPIENTS" if not recipients_str else None,
                ],
            )
            return None

        try:
            smtp_port = int(smtp_port_str or "0")
            recipients = [e.strip() for e in (recipients_str or "").split(",")]

            alerter = EmailAlerter(
                smtp_server=smtp_server or "",
                smtp_port=smtp_port,
                sender_email=sender_email or "",
                sender_password=sender_password or "",
                recipient_emails=recipients,
            )
            logger.info("EMAIL_ALERTER_INITIALIZED", server=smtp_server, recipients=len(recipients))
            return alerter

        except ValueError:
            logger.error("EMAIL_INVALID_PORT", port=smtp_port_str)
            return None
        except Exception as e:
            logger.error("EMAIL_INITIALIZATION_ERROR", error=str(e))
            return None
