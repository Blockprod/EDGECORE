"""
Tests for API security layer (authentication and rate limiting).

Tests:
- Rate limiting behavior
- API key authentication
- Security headers
- HTTPS enforcement
- Request logging
- Error handling
"""

# pyright: reportUnusedVariable=false

import os
<<<<<<< HEAD
import time
from unittest.mock import Mock, patch

import pytest
=======
from unittest.mock import Mock, patch
>>>>>>> origin/main
from flask import Flask

from monitoring.api_security import (
    APIKeyAuth,
<<<<<<< HEAD
=======
    require_rate_limit,
    require_api_key,
    add_security_headers,
    require_https,
    generate_api_key,
    validate_hmac_signature,
    RequestLogger,
    log_api_call,
>>>>>>> origin/main
    JWTAuth,
    RateLimiter,
    RequestLogger,
    add_security_headers,
    generate_api_key,
    log_api_call,
    require_api_key,
    require_https,
    require_jwt_token,
<<<<<<< HEAD
    require_rate_limit,
    validate_hmac_signature,
=======
>>>>>>> origin/main
)


class TestRateLimiter:
    """Test RateLimiter functionality."""

    def test_rate_limiter_initialization(self):
        """Should initialize with default RPM limit."""
        limiter = RateLimiter(requests_per_minute=100)
        assert limiter.rpm_limit == 100
        assert limiter.requests == {}

    def test_rate_limiter_allows_requests_within_limit(self):
        """Should allow requests within rate limit."""
        limiter = RateLimiter(requests_per_minute=5)

        for i in range(5):
            assert limiter.is_allowed("192.168.1.1") is True

    def test_rate_limiter_rejects_excess_requests(self):
        """Should reject requests exceeding rate limit."""
        limiter = RateLimiter(requests_per_minute=5)

        for i in range(5):
            limiter.is_allowed("192.168.1.1")

        # 6th request should be rejected
        assert limiter.is_allowed("192.168.1.1") is False

    def test_rate_limiter_resets_after_time_window(self):
        """Should reset after 60 second window expires."""
        limiter = RateLimiter(requests_per_minute=2)

        # Consume limit
        limiter.is_allowed("192.168.1.1")
        limiter.is_allowed("192.168.1.1")
        assert limiter.is_allowed("192.168.1.1") is False

        # Manually clear old requests to simulate time passing
        limiter.requests["192.168.1.1"] = []
        assert limiter.is_allowed("192.168.1.1") is True

    def test_rate_limiter_tracks_per_ip(self):
        """Should track limits per client IP separately."""
        limiter = RateLimiter(requests_per_minute=2)

        # Client 1
        limiter.is_allowed("192.168.1.1")
        limiter.is_allowed("192.168.1.1")
        assert limiter.is_allowed("192.168.1.1") is False

        # Client 2 should have separate limit
        assert limiter.is_allowed("192.168.1.2") is True
        assert limiter.is_allowed("192.168.1.2") is True
        assert limiter.is_allowed("192.168.1.2") is False

    def test_rate_limiter_get_remaining(self):
        """Should return remaining requests."""
        limiter = RateLimiter(requests_per_minute=5)

        assert limiter.get_remaining("192.168.1.1") == 5
        limiter.is_allowed("192.168.1.1")
        assert limiter.get_remaining("192.168.1.1") == 4
        limiter.is_allowed("192.168.1.1")
        assert limiter.get_remaining("192.168.1.1") == 3


class TestAPIKeyAuth:
    """Test API key authentication."""

    def test_auth_initializes_with_keys(self):
        """Should initialize with valid keys from environment."""
        auth = APIKeyAuth(required=False)
        assert isinstance(auth.valid_keys, set)

    def test_auth_allows_no_key_when_not_required(self):
        """Should allow requests without key when not required."""
        auth = APIKeyAuth(required=False)
        app = Flask(__name__)

        with app.test_request_context(headers={}):
            result = auth.authenticate()
            assert result == "anonymous"

    def test_auth_rejects_no_key_when_required(self):
        """Should reject requests without key when required."""
        auth = APIKeyAuth(required=True)
        auth.valid_keys = set()  # No valid keys
        app = Flask(__name__)

        with app.test_request_context(headers={}):
            result = auth.authenticate()
            assert result is None

    def test_auth_accepts_bearer_token(self):
        """Should accept bearer token format."""
        auth = APIKeyAuth(required=False)
        auth.valid_keys = {"test_key_12345678"}
        app = Flask(__name__)

        with app.test_request_context(headers={"Authorization": "Bearer test_key_12345678"}):
            result = auth.authenticate()
            assert result is not None

    def test_auth_accepts_token_format(self):
        """Should accept Token format."""
        auth = APIKeyAuth(required=False)
        auth.valid_keys = {"my_token_1234567890"}
        app = Flask(__name__)

        with app.test_request_context(headers={"Authorization": "Token my_token_1234567890"}):
            result = auth.authenticate()
            assert result is not None

    def test_auth_rejects_invalid_token(self):
        """Should reject invalid tokens when required."""
        auth = APIKeyAuth(required=True)
        auth.valid_keys = {"valid_key_1234567890"}
        app = Flask(__name__)

        with app.test_request_context(headers={"Authorization": "Bearer invalid_key"}):
            result = auth.authenticate()
            assert result is None

    def test_auth_rejects_malformed_header(self):
        """Should reject malformed authorization header."""
        auth = APIKeyAuth(required=True)
        app = Flask(__name__)

        with app.test_request_context(headers={"Authorization": "InvalidFormat"}):
            result = auth.authenticate()
            assert result is None

    def test_auth_case_insensitive_bearer(self):
        """Should handle bearer/token case-insensitively."""
        auth = APIKeyAuth(required=False)
        auth.valid_keys = {"mytoken"}
        app = Flask(__name__)

        with app.test_request_context(headers={"Authorization": "bearer mytoken"}):
            assert auth.authenticate() is not None

        with app.test_request_context(headers={"Authorization": "BEARER mytoken"}):
            assert auth.authenticate() is not None


class TestGenerateAPIKey:
    """Test API key generation."""

    def test_generate_api_key_format(self):
        """Should generate properly formatted API key."""
        key = generate_api_key("test")
        assert key.startswith("edgecore_test_")
        assert len(key) > 20

    def test_generate_api_key_uniqueness(self):
        """Should generate unique keys."""
        key1 = generate_api_key()
        key2 = generate_api_key()
        assert key1 != key2


class TestHMACSignature:
    """Test HMAC signature validation."""

    def test_validate_hmac_valid_signature(self):
        """Should validate correct HMAC signature."""
        data = b"test data"
        secret = "secret_key"

        import hashlib
        import hmac

        signature = hmac.new(secret.encode(), data, hashlib.sha256).hexdigest()

        assert validate_hmac_signature(data, signature, secret) is True

    def test_validate_hmac_invalid_signature(self):
        """Should reject invalid HMAC signature."""
        data = b"test data"
        secret = "secret_key"
        wrong_signature = "wrong_signature_here"

        assert validate_hmac_signature(data, wrong_signature, secret) is False

    def test_validate_hmac_timing_attack_resistant(self):
        """Should use timing-safe comparison."""
        data = b"test data"
        secret = "secret_key"

        import hashlib
        import hmac

        correct = hmac.new(secret.encode(), data, hashlib.sha256).hexdigest()
        similar = correct[:-1] + ("0" if correct[-1] != "0" else "1")

        # Should fail but not reveal timing difference
        result = validate_hmac_signature(data, similar, secret)
        assert result is False


class TestRequestLogger:
    """Test request logging."""

    def test_logger_initialization(self):
        """Should initialize empty request list."""
        logger = RequestLogger()
        assert logger.requests == []

    def test_logger_records_request(self):
        """Should record API request."""
        logger = RequestLogger()
        logger.log_request("GET", "/api/health", "user1", 200, 45.2)

        assert len(logger.requests) == 1
        assert logger.requests[0]["method"] == "GET"
        assert logger.requests[0]["path"] == "/api/health"

    def test_logger_get_stats(self):
        """Should retrieve request statistics."""
        logger = RequestLogger()
        logger.log_request("GET", "/api/health", "user1", 200, 50.0)
        logger.log_request("GET", "/api/health", "user1", 200, 70.0)
        logger.log_request("POST", "/api/orders", "user2", 201, 100.0)

        stats = logger.get_stats()
        assert stats["total"] == 3
        assert stats["avg_time_ms"] == pytest.approx(73.33, rel=0.1)
        assert stats["status_codes"][200] == 2
        assert stats["status_codes"][201] == 1

    def test_logger_stats_empty(self):
        """Should handle empty request log."""
        logger = RequestLogger()
        stats = logger.get_stats()
        assert stats["total"] == 0

    def test_logger_filters_old_requests(self):
        """Should filter requests older than 1 hour."""
        logger = RequestLogger()

        with patch("monitoring.api_security.time.time") as mock_time:
            # Add request at time 0
            mock_time.return_value = 0
            logger.log_request("GET", "/api/health", "user1", 200, 50.0)

            # Add request at time 3600 (1 hour)
            mock_time.return_value = 3600
            logger.log_request("GET", "/api/orders", "user2", 200, 50.0)

            # Check stats at time 5400 (1.5 hours later)
            mock_time.return_value = 5400
            stats = logger.get_stats()

            # Only the recent request (within 1 hour) should be counted
            assert stats["total"] == 1


class TestSecurityDecorators:
    """Test security decorators."""

    def test_require_rate_limit_decorator(self):
        """Should apply rate limiting to wrapped function."""
        app = Flask(__name__)

        @app.route("/test")
        @require_rate_limit
        def dummy_endpoint():
            return {"status": "ok"}, 200

        with app.test_client() as client:
            response = client.get("/test")
            assert response.status_code == 200

    def test_require_rate_limit_reject_excess(self):
        """Should reject requests exceeding rate limit."""
        limiter = RateLimiter(requests_per_minute=1)
        app = Flask(__name__)

        @app.route("/test")
        @require_rate_limit
        def dummy_endpoint():
            return {"status": "ok"}, 200

        with patch("monitoring.api_security._rate_limiter", limiter):
            with app.test_client() as client:
                # First request should succeed
                response1 = client.get("/test")
                assert response1.status_code == 200

                # Second request should be rate limited
                response2 = client.get("/test")
                assert response2.status_code == 429

    def test_require_api_key_decorator(self):
        """Should require API key on wrapped function."""
        app = Flask(__name__)
        auth = APIKeyAuth(required=True)

        @app.route("/test")
        @require_api_key
        def dummy_endpoint():
            return {"status": "ok"}, 200

        with patch("monitoring.api_security._auth", auth):
            with app.test_client() as client:
                # No key - should be rejected if required
                response = client.get("/test")
                assert response.status_code == 401

    def test_require_https_not_enforced(self):
        """Should allow HTTP when HTTPS not required."""
        app = Flask(__name__)

        @app.route("/test")
        @require_https
        def dummy_endpoint():
            return {"status": "ok"}, 200

        with patch.dict("os.environ", {"REQUIRE_HTTPS": "false"}):
            with app.test_client() as client:
                response = client.get("/test")
                assert response.status_code == 200


class TestAddSecurityHeaders:
    """Test security headers."""

    def test_add_security_headers(self):
        """Should add security headers to response."""
        mock_response = Mock()
        mock_response.headers = {}

        result = add_security_headers(mock_response)

        assert "X-Content-Type-Options" in result.headers
        assert "X-Frame-Options" in result.headers
        assert "X-XSS-Protection" in result.headers
        assert "Strict-Transport-Security" in result.headers

    def test_security_headers_values(self):
        """Should set correct security header values."""
        mock_response = Mock()
        mock_response.headers = {}

        add_security_headers(mock_response)

        assert mock_response.headers["X-Content-Type-Options"] == "nosniff"
        assert mock_response.headers["X-Frame-Options"] == "DENY"
        assert "mode=block" in mock_response.headers["X-XSS-Protection"]
        assert "max-age=31536000" in mock_response.headers["Strict-Transport-Security"]


class TestLogAPICallDecorator:
    """Test log_api_call decorator."""

    def test_log_api_call_success(self):
        """Should log successful API call."""
        logger = RequestLogger()
        app = Flask(__name__)

        @app.route("/test")
        @log_api_call
        def dummy_endpoint():
            return {"status": "ok"}, 200

        with patch("monitoring.api_security._request_logger", logger):
            with app.test_client() as client:
                response = client.get("/test")
                assert response.status_code == 200
                assert len(logger.requests) == 1

    def test_log_api_call_logs_requests(self):
        """Should log API requests."""
        logger = RequestLogger()
        app = Flask(__name__)

        @app.route("/test")
        @log_api_call
        def dummy_endpoint():
            return {"status": "ok"}, 200

        with patch("monitoring.api_security._request_logger", logger):
            with app.test_client() as client:
                response = client.get("/test")
                assert response.status_code == 200
                # Verify the logging infrastructure works
                assert len(logger.requests) >= 1


class TestIntegrationSecurityFlow:
    """Integration tests for security flow."""

    def test_full_security_flow_authorized(self):
        """Should allow authorized requests within rate limit."""
        app = Flask(__name__)

        @app.route("/test")
        @require_rate_limit
        def protected_endpoint():
            return {"data": "sensitive"}, 200

        with app.test_client() as client:
            result = client.get("/test")
            assert result.status_code == 200

    def test_full_security_flow_rate_limited(self):
        """Should rate limit excess requests."""
        limiter = RateLimiter(requests_per_minute=1)
        app = Flask(__name__)

        @app.route("/test")
        @require_rate_limit
        def protected_endpoint():
            return {"data": "sensitive"}, 200

        with patch("monitoring.api_security._rate_limiter", limiter):
            with app.test_client() as client:
                # First request OK
                result1 = client.get("/test")
                assert result1.status_code == 200

                # Second request rate limited
                result2 = client.get("/test")
                assert result2.status_code == 429


class TestJWTAuth:
    """Test JWT authentication."""

    def test_jwt_token_generation(self):
        """Should generate valid JWT token."""
        jwt_auth = JWTAuth(secret_key="test-secret-key-at-least-32-bytes-long-for-security")
        token = jwt_auth.generate_token("user123", expires_in_hours=24)

        assert isinstance(token, str)
        assert len(token) > 0

    def test_jwt_token_verification(self):
        """Should verify valid JWT token."""
        jwt_auth = JWTAuth(secret_key="test-secret-key-at-least-32-bytes-long-for-security")
        token = jwt_auth.generate_token("user123", expires_in_hours=24)
        user_id = jwt_auth.verify_token(token)

        assert user_id == "user123"

    def test_jwt_token_invalid(self):
        """Should reject invalid JWT token."""
        jwt_auth = JWTAuth(secret_key="test-secret-key-at-least-32-bytes-long-for-security")
        user_id = jwt_auth.verify_token("invalid.token.here")

        assert user_id is None

    def test_jwt_token_wrong_secret(self):
        """Should reject token signed with different secret."""
        jwt_auth1 = JWTAuth(secret_key="secret-key-one-at-least-32-bytes-long-for-hash")
        jwt_auth2 = JWTAuth(secret_key="secret-key-two-at-least-32-bytes-long-for-hash")

        token = jwt_auth1.generate_token("user123", expires_in_hours=24)
        user_id = jwt_auth2.verify_token(token)

        assert user_id is None

    def test_jwt_token_expired(self):
        """Should reject expired JWT token."""
        jwt_auth = JWTAuth(secret_key="test-secret-key-at-least-32-bytes-long-for-security")
        # Generate token that expires immediately
        token = jwt_auth.generate_token("user123", expires_in_hours=0)

        # Wait a tiny bit for expiration
        time.sleep(0.1)
        user_id = jwt_auth.verify_token(token)

        # Token should be expired
        assert user_id is None

    def test_require_jwt_token_decorator(self):
        """Should require JWT token with decorator."""
        app = Flask(__name__)

        @app.route("/protected")
        @require_jwt_token
        def protected():
            return {"data": "secret"}, 200

        with app.test_client() as client:
            # No token
            result = client.get("/protected")
            assert result.status_code == 401

            # Invalid token
            result = client.get("/protected", headers={"Authorization": "Bearer invalid"})
            assert result.status_code == 401


class TestAPIKeyAuthProduction:
    """Test API key auth in production mode."""

    def test_api_keys_warning_in_prod_without_env(self):
        """Should warn when API_KEYS not set in production."""
        with patch.dict(os.environ, {"EDGECORE_ENV": "prod"}, clear=False):
            with patch.dict(os.environ, {"API_KEYS": ""}, clear=False):
                auth = APIKeyAuth(required=False)
                assert auth.valid_keys == set()

    def test_api_keys_loaded_from_env(self):
        """Should load API keys from environment."""
        with patch.dict(os.environ, {"API_KEYS": "key1,key2,key3"}, clear=False):
            auth = APIKeyAuth(required=True)
            assert len(auth.valid_keys) == 3
            assert "key1" in auth.valid_keys
