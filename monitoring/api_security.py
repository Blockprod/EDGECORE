"""
Rate limiting and authentication for EDGECORE Flask API.

Provides:
- Token-based authentication (API keys)
- JWT token generation and verification
- Rate limiting (requests per minute)
- Request/response logging
- Security headers
"""

import os
import time
from functools import wraps
from typing import Dict, Optional, Callable, Any
from flask import request, jsonify, Response
import hashlib
import hmac
import struct
from datetime import datetime, timedelta
from structlog import get_logger

try:
    import jwt
    HAS_JWT = True
except ImportError:
    HAS_JWT = False

logger = get_logger(__name__)


class RateLimiter:
    """Simple in-memory rate limiter by IP address."""
    
    def __init__(self, requests_per_minute: int = 100):
        self.rpm_limit = requests_per_minute
        self.requests: Dict[str, list] = {}
    
    def is_allowed(self, identifier: str) -> bool:
        """Check if request is allowed for identifier (IP address)."""
        now = time.time()
        cutoff = now - 60  # Last 60 seconds
        
        # Initialize if new
        if identifier not in self.requests:
            self.requests[identifier] = []
        
        # Filter old requests
        self.requests[identifier] = [
            req_time for req_time in self.requests[identifier]
            if req_time > cutoff
        ]
        
        # Check limit
        if len(self.requests[identifier]) >= self.rpm_limit:
            return False
        
        # Add current request
        self.requests[identifier].append(now)
        return True
    
    def get_remaining(self, identifier: str) -> int:
        """Get remaining requests for identifier."""
        now = time.time()
        cutoff = now - 60
        
        if identifier not in self.requests:
            return self.rpm_limit
        
        valid_requests = [
            req_time for req_time in self.requests[identifier]
            if req_time > cutoff
        ]
        
        return max(0, self.rpm_limit - len(valid_requests))


class APIKeyAuth:
    """API key authentication."""
    
    def __init__(self, required: bool = False):
        self.required = required
        self.valid_keys = self._load_keys()
    
    def _load_keys(self) -> set:
        """Load valid API keys from environment or config."""
        keys = os.getenv('API_KEYS', '')
        
        if not keys:
            # In production, require API keys
            if os.getenv('EDGECORE_ENV') == 'prod':
                logger.warning(
                    "API_KEYS_NOT_CONFIGURED",
                    message="API_KEYS environment variable not set - dashboard is open!"
                )
                # Optionally raise here to enforce in production
                # raise ValueError("API_KEYS required in production environment")
            return set()
        
        loaded_keys = set(keys.split(','))
        logger.info("api_keys_loaded", count=len(loaded_keys))
        return loaded_keys
    
    def authenticate(self) -> Optional[str]:
        """Authenticate request and return user ID or None."""
        auth_header = request.headers.get('Authorization', '')
        
        if not auth_header:
            if self.required:
                return None
            return 'anonymous'
        
        # Format: "Bearer TOKEN" or "Token TOKEN"
        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() not in ('bearer', 'token'):
            return None
        
        token = parts[1]
        
        # Check if token is valid
        if self.required and token not in self.valid_keys:
            return None
        
        return token[:8] if len(token) > 8 else token


class JWTAuth:
    """JWT token authentication and generation."""
    
    def __init__(self, secret_key: Optional[str] = None):
        """
        Initialize JWT authenticator.
        
        Args:
            secret_key: Secret key for signing tokens. If None, uses JWT_SECRET env var.
        """
        if not HAS_JWT:
            raise ImportError("PyJWT not installed. Install with: pip install PyJWT")
        
        self.secret_key = secret_key or os.getenv('JWT_SECRET', 'edgecore-default-secret-key-32-bytes-minimum')
        if self.secret_key == 'edgecore-default-secret-key-32-bytes-minimum':
            logger.warning(
                "using_default_jwt_secret",
                message="Using default JWT secret - set JWT_SECRET environment variable in production"
            )
    
    def generate_token(self, user_id: str, expires_in_hours: int = 24) -> str:
        """
        Generate JWT token.
        
        Args:
            user_id: User identifier to encode in token
            expires_in_hours: Token expiration time in hours
        
        Returns:
            JWT token string
        """
        payload = {
            'user_id': user_id,
            'iat': datetime.utcnow(),
            'exp': datetime.utcnow() + timedelta(hours=expires_in_hours)
        }
        token = jwt.encode(payload, self.secret_key, algorithm='HS256')
        logger.info("jwt_token_generated", user_id=user_id, expires_in_hours=expires_in_hours)
        return token
    
    def verify_token(self, token: str) -> Optional[str]:
        """
        Verify JWT token and return user_id if valid.
        
        Args:
            token: JWT token string to verify
        
        Returns:
            User ID if token is valid, None if expired or invalid
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=['HS256'])
            return payload.get('user_id')
        except jwt.ExpiredSignatureError:
            logger.warning("jwt_token_expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning("jwt_token_invalid", error=str(e))
            return None


# Global instances
_rate_limiter = RateLimiter(
    requests_per_minute=int(os.getenv('RATE_LIMIT_RPM', '100'))
)

_auth = APIKeyAuth(
    required=os.getenv('API_AUTH_REQUIRED', 'false').lower() == 'true'
)

# JWT auth (optional, only initialized if JWT_SECRET is set)
_jwt_auth = None
if HAS_JWT and os.getenv('JWT_SECRET'):
    _jwt_auth = JWTAuth(secret_key=os.getenv('JWT_SECRET'))


def require_rate_limit(func: Callable) -> Callable:
    """Decorator to add rate limiting to Flask route."""
    @wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        client_ip = request.remote_addr or 'unknown'
        
        if not _rate_limiter.is_allowed(client_ip):
            remaining = _rate_limiter.get_remaining(client_ip)
            return jsonify({
                'error': 'Rate limit exceeded',
                'limit': _rate_limiter.rpm_limit,
                'remaining': remaining,
                'retry_after': 60
            }), 429
        
        # Add rate limit headers to response
        response = func(*args, **kwargs)
        if isinstance(response, tuple):
            resp_data, status_code = response[0], response[1] if len(response) > 1 else 200
            remaining = _rate_limiter.get_remaining(client_ip)
            # Headers will be added by Flask
        
        return response
    
    return wrapper


def require_api_key(func: Callable) -> Callable:
    """Decorator to require API key authentication."""
    @wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        user_id = _auth.authenticate()
        
        if user_id is None:
            return jsonify({
                'error': 'Unauthorized',
                'message': 'Missing or invalid API key'
            }), 401
        
        # Store in request context for logging
        request.user_id = user_id
        
        return func(*args, **kwargs)
    
    return wrapper


def require_jwt_token(func: Callable) -> Callable:
    """Decorator to require JWT token authentication."""
    @wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        if not _jwt_auth:
            return jsonify({
                'error': 'JWT not configured',
                'message': 'JWT authentication not available'
            }), 401
        
        auth_header = request.headers.get('Authorization', '')
        if not auth_header:
            return jsonify({
                'error': 'Unauthorized',
                'message': 'Missing JWT token'
            }), 401
        
        # Format: "Bearer TOKEN"
        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != 'bearer':
            return jsonify({
                'error': 'Invalid authorization header',
                'message': 'Expected "Bearer TOKEN"'
            }), 401
        
        token = parts[1]
        user_id = _jwt_auth.verify_token(token)
        
        if user_id is None:
            return jsonify({
                'error': 'Unauthorized',
                'message': 'Invalid or expired JWT token'
            }), 401
        
        # Store in request context
        request.user_id = user_id
        return func(*args, **kwargs)
    
    return wrapper


def add_security_headers(response: Response) -> Response:
    """Add security headers to response."""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response


def require_https(func: Callable) -> Callable:
    """Decorator to require HTTPS (production only)."""
    @wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        if os.getenv('REQUIRE_HTTPS', 'false').lower() == 'true':
            if not request.is_secure:
                return jsonify({
                    'error': 'HTTPS required',
                    'message': 'This endpoint requires HTTPS'
                }), 403
        
        return func(*args, **kwargs)
    
    return wrapper


def generate_api_key(name: str = 'default') -> str:
    """Generate a new API key."""
    import secrets
    random_bytes = secrets.token_bytes(32)
    key = secrets.token_urlsafe(32)
    return f"edgecore_{name}_{key}"


def validate_hmac_signature(data: bytes, signature: str, secret: str) -> bool:
    """Validate HMAC signature for webhook verification."""
    expected_signature = hmac.new(
        secret.encode(),
        data,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(signature, expected_signature)


class RequestLogger:
    """Log API requests and responses."""
    
    def __init__(self):
        self.requests = []
    
    def log_request(self, method: str, path: str, user_id: str, status: int, elapsed_ms: float):
        """Log API request."""
        self.requests.append({
            'timestamp': time.time(),
            'method': method,
            'path': path,
            'user_id': user_id,
            'status': status,
            'elapsed_ms': elapsed_ms
        })
    
    def get_stats(self) -> dict:
        """Get request statistics."""
        if not self.requests:
            return {'total': 0}
        
        now = time.time()
        recent = [r for r in self.requests if now - r['timestamp'] < 3600]  # Last hour
        
        total_requests = len(recent)
        avg_time = sum(r['elapsed_ms'] for r in recent) / total_requests if recent else 0
        
        status_counts = {}
        for r in recent:
            status = r['status']
            status_counts[status] = status_counts.get(status, 0) + 1
        
        return {
            'total': total_requests,
            'avg_time_ms': avg_time,
            'status_codes': status_counts
        }


_request_logger = RequestLogger()


def log_api_call(func: Callable) -> Callable:
    """Decorator to log API calls."""
    @wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        start_time = time.time()
        user_id = getattr(request, 'user_id', 'anonymous')
        
        try:
            result = func(*args, **kwargs)
            elapsed_ms = (time.time() - start_time) * 1000
            
            status_code = 200
            if isinstance(result, tuple):
                status_code = result[1] if len(result) > 1 else 200
            
            _request_logger.log_request(
                request.method,
                request.path,
                user_id,
                status_code,
                elapsed_ms
            )
            
            return result
        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            _request_logger.log_request(
                request.method,
                request.path,
                user_id,
                500,
                elapsed_ms
            )
            raise
    
    return wrapper


def get_request_stats() -> dict:
    """Get API request statistics."""
    return _request_logger.get_stats()


def get_jwt_auth() -> Optional[JWTAuth]:
    """Get JWT auth instance (if configured)."""
    return _jwt_auth


def generate_jwt_token(user_id: str, expires_in_hours: int = 24) -> Optional[str]:
    """
    Generate JWT token for user.
    
    Args:
        user_id: User identifier
        expires_in_hours: Token expiration in hours
    
    Returns:
        JWT token string or None if JWT not configured
    """
    if not _jwt_auth:
        logger.warning("jwt_not_configured")
        return None
    
    return _jwt_auth.generate_token(user_id, expires_in_hours)
