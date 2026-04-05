"""
Secrets management for secure API key handling.

Provides:
- Centralized secrets vault
- Environment variable loading
- Masked logging (prevents key leaks)
- Rotation tracking
- Access audit logging
"""

import logging
import os
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from functools import wraps
from typing import Any, Callable

from structlog import get_logger

logger = get_logger(__name__)


class SecretsError(Exception):
    """Raised when secrets operation fails."""

    pass


class SecretNotFoundError(SecretsError):
    """Raised when secret is not found."""

    pass


@dataclass
class SecretMetadata:
    """Metadata about a secret."""

    name: str
    created_at: datetime
    last_accessed: datetime = field(default_factory=lambda: datetime.now(UTC))
    access_count: int = 0
    rotated_at: datetime | None = None
    rotation_interval_days: int | None = None

    def __post_init__(self):
        if self.created_at.tzinfo is None:
            self.created_at = self.created_at.replace(tzinfo=UTC)
        if self.last_accessed.tzinfo is None:
            self.last_accessed = self.last_accessed.replace(tzinfo=UTC)
        if self.rotated_at is not None and self.rotated_at.tzinfo is None:
            self.rotated_at = self.rotated_at.replace(tzinfo=UTC)

    def needs_rotation(self) -> bool:
        """Check if secret needs rotation."""
        if not self.rotation_interval_days:
            return False

        last_rotation = self.rotated_at or self.created_at
        days_since = (datetime.now(UTC) - last_rotation).days
        return days_since >= self.rotation_interval_days

    def mark_accessed(self) -> None:
        """Update access metadata."""
        self.last_accessed = datetime.now(UTC)
        self.access_count += 1

    def mark_rotated(self) -> None:
        """Mark as just rotated."""
        self.rotated_at = datetime.now(UTC)


class MaskedString:
    """String that masks itself when logged."""

    def __init__(self, value: str, mask_ratio: float = 0.8):
        """
        Initialize masked string.

        Args:
            value: Secret value
            mask_ratio: Fraction of value to mask (0.0 to 1.0)
        """
        self.value = value
        self.mask_ratio = mask_ratio

    def __str__(self) -> str:
        """Return masked representation."""
        return self.get_masked()

    def __repr__(self) -> str:
        """Return masked representation."""
        return self.get_masked()

    def get_masked(self) -> str:
        """Get masked value showing only edges."""
        if len(self.value) <= 2:
            return "*" * len(self.value)

        visible_chars = max(1, int(len(self.value) * (1 - self.mask_ratio)))
        show_start = visible_chars // 2
        show_end = visible_chars - show_start

        if show_end == 0:
            return self.value[:show_start] + "*" * (len(self.value) - show_start)

        masked = self.value[:show_start] + "*" * (len(self.value) - show_start - show_end) + self.value[-show_end:]
        return masked

    def get_unmasked(self) -> str:
        """Get actual secret value."""
        return self.value


class SecretsVault:
    """Centralized secrets management vault.

    Stores API keys, passwords, tokens with:
    - Metadata tracking (access, rotation)
    - Masked logging
    - Environment variable support
    - Audit trail

    Architecture decision � secrets strategy:
        v1 (current): secrets are read from environment variables at process
        start (via os.getenv / python-dotenv from a local .env file).  They
        are held in-memory as MaskedString objects inside this vault.  This
        is secure enough for a single-host deployment where the .env file is
        protected by filesystem permissions (chmod 600).

        v2 (future, production scale): replace the in-memory dict with a call
        to an external secrets-manager such as HashiCorp Vault, AWS Secrets
        Manager, or Azure Key Vault.  The ``_retrieve`` method below should
        become the sole integration point � swap its implementation without
        touching any caller.  Use short-lived tokens (TTL = 1 h) and enable
        audit logging on the external vault.

        Migration path: set the env var ``SECRETS_BACKEND=vault`` (or
        ``aws_sm``, ``azure_kv``) to activate the v2 backend once it is
        implemented.  The default is ``env`` (current v1 behaviour).
    """

    # Patterns for sensitive data masking
    SENSITIVE_PATTERNS = [
        r"api[_-]?key",
        r"secret[_-]?key",
        r"password",
        r"token",
        r"auth",
        r"credential",
        r"bearer",
        r"signature",
    ]

    def __init__(self, auto_load_env: bool = True):
        """
        Initialize secrets vault.

        Args:
            auto_load_env: If True, load from environment on init
        """
        self._secrets: dict[str, MaskedString] = {}
        self._metadata: dict[str, SecretMetadata] = {}
        self._audit_log: list[dict[str, Any]] = []
        self._rotation_callbacks: dict[str, Callable] = {}

        if auto_load_env:
            self.load_from_env()

    def store_secret(self, name: str, value: str, rotation_interval_days: int | None = None) -> None:
        """
        Store a secret in the vault.

        Args:
            name: Secret name (e.g., "IBKR_API_KEY")
            value: Secret value
            rotation_interval_days: Days before rotation recommended

        Raises:
            SecretsError: If secret name is invalid
        """
        if not name or not isinstance(name, str):
            raise SecretsError("Secret name must be non-empty string")

        if not value or not isinstance(value, str):
            raise SecretsError("Secret value must be non-empty string")

        # Store masked version
        self._secrets[name] = MaskedString(value)

        # Store metadata
        self._metadata[name] = SecretMetadata(
            name=name, created_at=datetime.now(UTC), rotation_interval_days=rotation_interval_days
        )

        # Audit log
        self._log_audit("store", name, success=True)

        logger.info("secret_stored", secret_name=name, rotated=False)

    def get_secret(self, name: str) -> str:
        """
        Retrieve secret from vault.

        Args:
            name: Secret name

        Returns:
            Unmasked secret value

        Raises:
            SecretNotFoundError: If secret doesn't exist
        """
        if name not in self._secrets:
            self._log_audit("retrieve", name, success=False)
            raise SecretNotFoundError(f"Secret not found: {name}")

        # Update metadata
        self._metadata[name].mark_accessed()

        # Check rotation needed
        if self._metadata[name].needs_rotation():
            logger.warning(
                "secret_needs_rotation", secret_name=name, days_since_rotation=self._calculate_rotation_age(name)
            )

        # Audit log
        self._log_audit("retrieve", name, success=True)

        return self._secrets[name].get_unmasked()

    def has_secret(self, name: str) -> bool:
        """Check if secret exists."""
        return name in self._secrets

    def rotate_secret(self, name: str, new_value: str) -> None:
        """
        Rotate (replace) a secret.

        Args:
            name: Secret name
            new_value: New secret value

        Raises:
            SecretNotFoundError: If secret doesn't exist
        """
        if name not in self._secrets:
            raise SecretNotFoundError(f"Secret not found: {name}")

        # Store new value
        old_masked = self._secrets[name].get_masked()
        self._secrets[name] = MaskedString(new_value)
        self._metadata[name].mark_rotated()

        # Audit log
        self._log_audit("rotate", name, success=True, details={"old_masked": old_masked})

        # Run rotation callback if registered
        if name in self._rotation_callbacks:
            try:
                self._rotation_callbacks[name](name, new_value)
            except Exception as e:
                logger.error("rotation_callback_failed", secret_name=name, error=str(e))

        logger.info("secret_rotated", secret_name=name)

    def delete_secret(self, name: str) -> None:
        """
        Delete a secret from vault.

        Args:
            name: Secret name

        Raises:
            SecretNotFoundError: If secret doesn't exist
        """
        if name not in self._secrets:
            raise SecretNotFoundError(f"Secret not found: {name}")

        # Delete
        del self._secrets[name]
        del self._metadata[name]

        # Audit log
        self._log_audit("delete", name, success=True)

        logger.info("secret_deleted", secret_name=name)

    def get_secret_rotation_status(self) -> dict[str, dict[str, Any]]:
        """
        Get rotation status for all secrets.

        Returns:
            Dict mapping secret names to rotation status info:
            {
                "SECRET_NAME": {
                    "created_at": datetime,
                    "rotated_at": datetime or None,
                    "next_rotation_date": datetime or None,
                    "days_since_last": int,
                    "needs_rotation": bool,
                    "access_count": int
                }
            }
        """
        status = {}

        for secret_name, metadata in self._metadata.items():
            last_rotation = metadata.rotated_at or metadata.created_at
            days_since = (datetime.now(UTC) - last_rotation).days

            next_rotation = None
            needs_rotation = False

            if metadata.rotation_interval_days:
                next_rotation = last_rotation + timedelta(days=metadata.rotation_interval_days)
                needs_rotation = metadata.needs_rotation()

            status[secret_name] = {
                "created_at": metadata.created_at,
                "rotated_at": metadata.rotated_at,
                "next_rotation_date": next_rotation,
                "days_since_last": days_since,
                "needs_rotation": needs_rotation,
                "access_count": metadata.access_count,
                "last_accessed": metadata.last_accessed,
            }

        return status

    def load_from_env(self, prefix: str = "") -> None:
        """
        Load secrets from environment variables.

        Args:
            prefix: Optional prefix filter (e.g., "TRADING_")
        """
        loaded = 0

        for env_var, value in os.environ.items():
            # Filter by prefix if provided
            if prefix and not env_var.startswith(prefix):
                continue

            # Check if looks like a secret
            if self._is_potentially_secret(env_var):
                self.store_secret(env_var, value)
                loaded += 1

        logger.info("loaded_from_env", count=loaded, prefix=prefix)

    def register_rotation_callback(self, secret_name: str, callback: Callable) -> None:
        """
        Register callback to run on secret rotation.

        Args:
            secret_name: Which secret to watch
            callback: Function(name, new_value) to call on rotation
        """
        self._rotation_callbacks[secret_name] = callback

    def get_metadata(self, name: str) -> SecretMetadata | None:
        """Get metadata for a secret."""
        return self._metadata.get(name)

    def get_secrets_needing_rotation(self) -> set[str]:
        """Get list of secrets that need rotation."""
        return {name for name, meta in self._metadata.items() if meta.needs_rotation()}

    def get_audit_log(self, action: str | None = None, days: int = 7) -> list[dict[str, Any]]:
        """
        Get audit log entries.

        Args:
            action: Optional filter by action type
            days: Only return entries from last N days

        Returns:
            List of audit log entries
        """
        cutoff = datetime.now(UTC) - timedelta(days=days)

        entries = [e for e in self._audit_log if e["timestamp"] >= cutoff]

        if action:
            entries = [e for e in entries if e["action"] == action]

        return entries

    def _is_potentially_secret(self, env_var_name: str) -> bool:
        """Check if environment variable looks like a secret."""
        name_lower = env_var_name.lower()

        for pattern in self.SENSITIVE_PATTERNS:
            if re.search(pattern, name_lower):
                return True

        return False

    def _log_audit(self, action: str, secret_name: str, success: bool, details: dict[str, Any] | None = None) -> None:
        """Log action to audit trail."""
        self._audit_log.append(
            {
                "timestamp": datetime.now(UTC),
                "action": action,
                "secret_name": secret_name,
                "success": success,
                "details": details or {},
            }
        )

    def _calculate_rotation_age(self, secret_name: str) -> int:
        """Calculate days since last rotation."""
        meta = self._metadata.get(secret_name)
        if not meta:
            return 0

        last_rotation = meta.rotated_at or meta.created_at
        return (datetime.now(UTC) - last_rotation).days


# Global vault instance
_global_vault: SecretsVault | None = None


def get_vault() -> SecretsVault:
    """Get or create global secrets vault."""
    global _global_vault

    if _global_vault is None:
        _global_vault = SecretsVault(auto_load_env=True)

    return _global_vault


def mask_sensitive_data(text: str) -> str:
    """
    Mask sensitive data in text.

    Args:
        text: Input text that may contain secrets

    Returns:
        Text with secrets masked
    """
    for pattern in SecretsVault.SENSITIVE_PATTERNS:
        # Match patterns like:
        # api_key=xxxxx, api_key: xxxxx, "api_key": "xxxxx", 'api_key': 'xxxxx'
        # Handles quoted and unquoted values
        text = re.sub(
            rf'({pattern}\s*[:=]\s*["\']?)([^\s"\']+)(["\']?)',
            lambda m: (
                m.group(1)
                + m.group(2)[0]
                + "*" * max(3, len(m.group(2)) - 2)
                + (m.group(2)[-1] if len(m.group(2)) > 1 else "")
                + m.group(3)
            ),
            text,
            flags=re.IGNORECASE,
        )

    return text


def inject_secrets(logging_handler=None) -> None:
    """
    Inject secret masking into Python logging.

    Ensures all log messages have secrets masked.

    Args:
        logging_handler: Optional specific handler to inject
    """
    get_vault()

    class MaskingFilter(logging.Filter):
        """Logging filter that masks secrets."""

        def filter(self, record):
            """Mask secrets in log record."""
            record.msg = mask_sensitive_data(str(record.msg))

            # Mask args if present
            if record.args:
                if isinstance(record.args, dict):
                    record.args = {k: mask_sensitive_data(str(v)) for k, v in record.args.items()}
                elif isinstance(record.args, (list, tuple)):
                    record.args = tuple(mask_sensitive_data(str(v)) for v in record.args)

            return True

    # Apply to all handlers
    logger_module = logging.getLogger()

    if logging_handler:
        logging_handler.addFilter(MaskingFilter())
    else:
        for handler in logger_module.handlers:
            handler.addFilter(MaskingFilter())


def use_secret(secret_name: str):
    """
    Decorator to inject secret as function argument.

    Example:
        @use_secret('API_KEY')
        def my_function(api_key, other_arg):
            # Use api_key securely — never log or print it
            ...
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            vault = get_vault()
            try:
                secret_value = vault.get_secret(secret_name)
                # Inject as first kwarg
                kwargs[secret_name.lower()] = secret_value
            except SecretNotFoundError:
                logger.warning("secret_not_found_for_decorator", secret_name=secret_name, function=func.__name__)

            return func(*args, **kwargs)

        return wrapper

    return decorator
