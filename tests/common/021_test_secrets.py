"""
Tests for secrets management.

Covers:
- Secret storage and retrieval
- Masked logging
- Rotation tracking
- Audit logging
- Environment variable loading
- Global vault management
"""

import os
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock, patch

import pytest

from common.secrets import (
    MaskedString,
    SecretMetadata,
    SecretNotFoundError,
    SecretsError,
    SecretsVault,
    get_vault,
    mask_sensitive_data,
    use_secret,
)


class TestMaskedString:
    """Test MaskedString for secure display."""

    def test_masked_string_short(self):
        """Test masking of short secrets."""
        masked = MaskedString("abc", mask_ratio=0.8)
        masked_str = str(masked)

        assert len(masked_str) == 3
        assert "*" in masked_str

    def test_masked_string_medium(self):
        """Test masking of medium secrets."""
        secret = "my_super_secret_api_key"
        masked = MaskedString(secret, mask_ratio=0.8)
        masked_str = str(masked)

        # Should show some edges but mask most
        assert masked_str.startswith("m")
        assert masked_str.endswith("y")
        assert "*" in masked_str
        assert len(masked_str) == len(secret)

    def test_masked_string_long(self):
        """Test masking of long secrets."""
        secret = "a" * 100
        masked = MaskedString(secret, mask_ratio=0.8)
        masked_str = str(masked)

        assert len(masked_str) == 100
        assert masked_str.count("*") > 80

    def test_masked_string_repr(self):
        """Test repr returns masked."""
        masked = MaskedString("secret_value")

        assert repr(masked) == str(masked)

    def test_get_unmasked(self):
        """Test retrieving actual value."""
        value = "my_secret"
        masked = MaskedString(value)

        assert masked.get_unmasked() == value

    def test_masked_string_different_ratios(self):
        """Test different masking ratios."""
        secret = "a" * 20

        masked_low = MaskedString(secret, mask_ratio=0.2)
        masked_high = MaskedString(secret, mask_ratio=0.9)

        # Higher ratio = more masking
        assert masked_high.get_masked().count("*") > masked_low.get_masked().count("*")


class TestSecretMetadata:
    """Test secret metadata tracking."""

    def test_metadata_creation(self):
        """Test creating metadata."""
        meta = SecretMetadata(name="TEST_KEY", created_at=datetime.now(UTC))

        assert meta.name == "TEST_KEY"
        assert meta.access_count == 0
        assert meta.rotated_at is None

    def test_needs_rotation_false(self):
        """Test rotation not needed."""
        meta = SecretMetadata(name="TEST_KEY", created_at=datetime.now(UTC), rotation_interval_days=90)

        assert meta.needs_rotation() is False

    def test_needs_rotation_true(self):
        """Test rotation needed."""
        old_date = datetime.now(UTC) - timedelta(days=100)
        meta = SecretMetadata(name="TEST_KEY", created_at=old_date, rotation_interval_days=90)

        assert meta.needs_rotation() is True

    def test_needs_rotation_no_interval(self):
        """Test no rotation tracking if interval not set."""
        old_date = datetime.now(UTC) - timedelta(days=1000)
        meta = SecretMetadata(name="TEST_KEY", created_at=old_date)

        assert meta.needs_rotation() is False

    def test_mark_accessed(self):
        """Test access tracking."""
        meta = SecretMetadata(name="TEST_KEY", created_at=datetime.now(UTC))

        original_time = meta.last_accessed
        meta.mark_accessed()

        assert meta.access_count == 1
        assert meta.last_accessed >= original_time

    def test_mark_rotated(self):
        """Test rotation timestamp."""
        meta = SecretMetadata(name="TEST_KEY", created_at=datetime.now(UTC))

        before_rotate = datetime.now(UTC)
        meta.mark_rotated()
        after_rotate = datetime.now(UTC)

        assert meta.rotated_at is not None
        assert before_rotate <= meta.rotated_at <= after_rotate


class TestSecretsVault:
    """Test secrets vault functionality."""

    def test_vault_creation(self):
        """Test creating vault."""
        vault = SecretsVault(auto_load_env=False)

        assert len(vault._secrets) == 0
        assert len(vault._metadata) == 0

    def test_store_and_retrieve_secret(self):
        """Test storing and retrieving secret."""
        vault = SecretsVault(auto_load_env=False)

        vault.store_secret("MY_API_KEY", "super_secret_value_123")
        retrieved = vault.get_secret("MY_API_KEY")

        assert retrieved == "super_secret_value_123"

    def test_store_invalid_name(self):
        """Test rejection of invalid secret name."""
        vault = SecretsVault(auto_load_env=False)

        with pytest.raises(SecretsError):
            vault.store_secret("", "value")

        with pytest.raises(SecretsError):
            vault.store_secret(None, "value")  # type: ignore[arg-type]

    def test_store_invalid_value(self):
        """Test rejection of invalid secret value."""
        vault = SecretsVault(auto_load_env=False)

        with pytest.raises(SecretsError):
            vault.store_secret("KEY", "")

        with pytest.raises(SecretsError):
            vault.store_secret("KEY", None)  # type: ignore[arg-type]

    def test_retrieve_nonexistent_secret(self):
        """Test retrieving non-existent secret."""
        vault = SecretsVault(auto_load_env=False)

        with pytest.raises(SecretNotFoundError):
            vault.get_secret("NONEXISTENT")

    def test_has_secret(self):
        """Test secret existence check."""
        vault = SecretsVault(auto_load_env=False)

        vault.store_secret("MY_KEY", "value")

        assert vault.has_secret("MY_KEY") is True
        assert vault.has_secret("OTHER_KEY") is False

    def test_delete_secret(self):
        """Test secret deletion."""
        vault = SecretsVault(auto_load_env=False)

        vault.store_secret("MY_KEY", "value")
        assert vault.has_secret("MY_KEY") is True

        vault.delete_secret("MY_KEY")
        assert vault.has_secret("MY_KEY") is False

    def test_delete_nonexistent_secret(self):
        """Test deleting non-existent secret."""
        vault = SecretsVault(auto_load_env=False)

        with pytest.raises(SecretNotFoundError):
            vault.delete_secret("NONEXISTENT")

    def test_rotate_secret(self):
        """Test secret rotation."""
        vault = SecretsVault(auto_load_env=False)

        vault.store_secret("MY_KEY", "old_value")
        vault.rotate_secret("MY_KEY", "new_value")

        retrieved = vault.get_secret("MY_KEY")
        assert retrieved == "new_value"
        assert vault.get_metadata("MY_KEY").rotated_at is not None  # type: ignore[union-attr]

    def test_rotate_nonexistent_secret(self):
        """Test rotating non-existent secret."""
        vault = SecretsVault(auto_load_env=False)

        with pytest.raises(SecretNotFoundError):
            vault.rotate_secret("NONEXISTENT", "value")

    def test_metadata_access_tracking(self):
        """Test access count tracking."""
        vault = SecretsVault(auto_load_env=False)

        vault.store_secret("MY_KEY", "value")

        assert vault.get_metadata("MY_KEY").access_count == 0  # type: ignore[union-attr]

        vault.get_secret("MY_KEY")
        assert vault.get_metadata("MY_KEY").access_count == 1  # type: ignore[union-attr]

        vault.get_secret("MY_KEY")
        assert vault.get_metadata("MY_KEY").access_count == 2  # type: ignore[union-attr]

    def test_rotation_interval_check(self):
        """Test rotation interval checking."""
        vault = SecretsVault(auto_load_env=False)

        # Create old secret
        old_date = datetime.now(UTC) - timedelta(days=100)
        vault.store_secret("OLD_KEY", "value", rotation_interval_days=90)
        vault._metadata["OLD_KEY"].created_at = old_date

        needing_rotation = vault.get_secrets_needing_rotation()

        assert "OLD_KEY" in needing_rotation

    def test_rotation_callback(self):
        """Test rotation callback execution."""
        vault = SecretsVault(auto_load_env=False)

        callback = Mock()
        vault.register_rotation_callback("MY_KEY", callback)

        vault.store_secret("MY_KEY", "old_value")
        vault.rotate_secret("MY_KEY", "new_value")

        callback.assert_called_once_with("MY_KEY", "new_value")

    def test_get_metadata(self):
        """Test getting metadata."""
        vault = SecretsVault(auto_load_env=False)

        vault.store_secret("MY_KEY", "value")
        meta = vault.get_metadata("MY_KEY")

        assert meta is not None
        assert meta.name == "MY_KEY"

    def test_get_nonexistent_metadata(self):
        """Test getting metadata for non-existent secret."""
        vault = SecretsVault(auto_load_env=False)

        meta = vault.get_metadata("NONEXISTENT")
        assert meta is None

    def test_audit_log(self):
        """Test audit logging."""
        vault = SecretsVault(auto_load_env=False)

        vault.store_secret("MY_KEY", "value")
        vault.get_secret("MY_KEY")
        vault.rotate_secret("MY_KEY", "new_value")

        audit_log = vault.get_audit_log()

        assert len(audit_log) >= 3
        assert audit_log[0]["action"] == "store"
        assert audit_log[1]["action"] == "retrieve"
        assert audit_log[2]["action"] == "rotate"

    def test_audit_log_filter_by_action(self):
        """Test audit log filtering."""
        vault = SecretsVault(auto_load_env=False)

        vault.store_secret("KEY1", "value1")
        vault.store_secret("KEY2", "value2")
        vault.get_secret("KEY1")

        store_logs = vault.get_audit_log(action="store")

        assert len(store_logs) == 2
        assert all(log["action"] == "store" for log in store_logs)

    def test_audit_log_time_filter(self):
        """Test audit log time filtering."""
        vault = SecretsVault(auto_load_env=False)

        vault.store_secret("OLD_KEY", "value")
        # Manually backdate
        vault._audit_log[0]["timestamp"] = datetime.now(UTC) - timedelta(days=10)

        vault.store_secret("NEW_KEY", "value")

        recent_logs = vault.get_audit_log(days=1)

        assert len(recent_logs) == 1
        assert recent_logs[0]["secret_name"] == "NEW_KEY"


class TestLoadFromEnvironment:
    """Test loading secrets from environment."""

    def test_load_from_env_with_api_keys(self):
        """Test loading API keys from environment."""
        with patch.dict(
            os.environ,
            {"IBKR_API_KEY": "test_key_123", "IBKR_SECRET_KEY": "test_secret_456", "OTHER_VAR": "not_secret"},
        ):
            vault = SecretsVault(auto_load_env=True)

            assert vault.has_secret("IBKR_API_KEY")
            assert vault.has_secret("IBKR_SECRET_KEY")
            assert vault.has_secret("OTHER_VAR") is False

    def test_load_with_prefix(self):
        """Test loading with prefix filter."""
        with patch.dict(os.environ, {"TRADING_API_KEY": "key1", "TRADING_PASSWORD": "pass1", "OTHER_API_KEY": "key2"}):
            vault = SecretsVault(auto_load_env=False)
            vault.load_from_env(prefix="TRADING_")

            assert vault.has_secret("TRADING_API_KEY")
            assert vault.has_secret("TRADING_PASSWORD")
            assert vault.has_secret("OTHER_API_KEY") is False


class TestMaskSensitiveData:
    """Test masking sensitive data in text."""

    def test_mask_api_key(self):
        """Test masking API key."""
        text = "api_key=my_secret_key_123"
        masked = mask_sensitive_data(text)

        assert masked != text
        assert "my_secret" not in masked
        assert "*" in masked

    def test_mask_password(self):
        """Test masking password."""
        text = "password: super_secret_123"
        masked = mask_sensitive_data(text)

        assert "super_secret" not in masked

    def test_mask_token(self):
        """Test masking token."""
        text = "token=abc123def456"
        masked = mask_sensitive_data(text)

        # Token value should be partially masked
        assert masked != text
        assert "*" in masked

    def test_mask_preserves_structure(self):
        """Test that masking preserves log structure."""
        text = "action=login, api_key=secret123, status=ok"
        masked = mask_sensitive_data(text)

        assert "action=login" in masked
        assert "status=ok" in masked
        assert "secret123" not in masked


class TestGlobalVault:
    """Test global vault singleton."""

    def test_get_vault_singleton(self):
        """Test that get_vault returns same instance."""
        vault1 = get_vault()
        vault2 = get_vault()

        assert vault1 is vault2


class TestUseSecretDecorator:
    """Test use_secret decorator."""

    def test_inject_secret_as_kwarg(self):
        """Test injecting secret as keyword argument."""
        vault = SecretsVault(auto_load_env=False)
        vault.store_secret("API_KEY", "test_api_key_123")

        # Manually set global vault for this test
        import common.secrets as secrets_module

        original_vault = secrets_module._global_vault
        secrets_module._global_vault = vault

        try:

            @use_secret("API_KEY")
            def my_function(api_key=None):
                return api_key

            result = my_function()

            assert result == "test_api_key_123"
        finally:
            secrets_module._global_vault = original_vault


class TestSecretsMasking:
    """Test that secrets are properly masked in logs."""

    def test_masked_string_in_logs(self):
        """Test that MaskedString masks in logs."""
        secret = "super_secret_api_key_12345"
        masked = MaskedString(secret)

        log_output = str(masked)

        assert secret not in log_output
        assert len(log_output) == len(secret)
        assert "*" in log_output


class TestSecretsIntegration:
    """Integration tests for secrets management."""

    def test_full_secret_lifecycle(self):
        """Test complete secret lifecycle."""
        vault = SecretsVault(auto_load_env=False)

        # Store
        vault.store_secret("API_KEY", "initial_value")
        assert vault.get_secret("API_KEY") == "initial_value"
        assert vault.get_metadata("API_KEY").access_count == 1  # type: ignore[union-attr]

        # Access again
        vault.get_secret("API_KEY")
        assert vault.get_metadata("API_KEY").access_count == 2  # type: ignore[union-attr]

        # Rotate
        vault.rotate_secret("API_KEY", "new_value")
        assert vault.get_secret("API_KEY") == "new_value"
        assert vault.get_metadata("API_KEY").access_count == 3  # Incremented by get_secret  # type: ignore[union-attr]
        assert vault.get_metadata("API_KEY").rotated_at is not None  # type: ignore[union-attr]

        # Check audit trail
        audit = vault.get_audit_log()
        assert any(log["action"] == "store" for log in audit)
        assert any(log["action"] == "retrieve" for log in audit)
        assert any(log["action"] == "rotate" for log in audit)

        # Delete
        vault.delete_secret("API_KEY")
        assert vault.has_secret("API_KEY") is False


# Run all tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
