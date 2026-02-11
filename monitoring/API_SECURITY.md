# API Security & Rate Limiting

Comprehensive security layer for EDGECORE Flask API with authentication, rate limiting, request logging, and security headers.

## Features

- **Rate Limiting**: Per-IP request throttling (configurable requests per minute)
- **API Key Authentication**: Bearer token-based API key validation
- **Security Headers**: OWASP-recommended HTTP security headers
- **HTTPS Enforcement**: Optional HTTPS-only mode for production
- **Request Logging**: Detailed request/response metrics and statistics
- **Graceful Error Handling**: Proper HTTP status codes and error responses

## Quick Start

### Applying Security to Routes

```python
from flask import Flask
from monitoring.api_security import require_rate_limit, require_api_key, log_api_call

app = Flask(__name__)

@app.route('/api/protected')
@require_rate_limit         # Apply rate limiting (100 req/min by default)
@require_api_key            # Require API key authentication
@log_api_call               # Log all requests and responses
def protected_endpoint():
    return {'data': 'sensitive'}, 200

@app.route('/api/public')
@require_rate_limit         # Rate limit without requiring auth
def public_endpoint():
    return {'data': 'public'}, 200
```

## Configuration

### Environment Variables

```bash
# Rate limiting (requests per minute per IP)
RATE_LIMIT_RPM=100

# API key authentication
API_KEYS=key1,key2,key3          # Comma-separated list of valid API keys
API_AUTH_REQUIRED=false          # Set to 'true' to require auth on all endpoints

# HTTPS enforcement (production only)
REQUIRE_HTTPS=false              # Set to 'true' to reject non-HTTPS requests
```

## API Key Management

### Generating API Keys

```python
from monitoring.api_security import generate_api_key

# Generate a new key
api_key = generate_api_key(name='user1')
# Returns: edgecore_user1_<random_token>
```

### Configuring Valid Keys

```bash
# Set in environment (.env file)
API_KEYS=edgecore_user1_abc123,edgecore_user2_def456

# Or in production, load from secure store (modify _load_keys() in api_security.py)
```

### Using API Keys in Requests

```bash
# Bearer token format (recommended)
curl -H "Authorization: Bearer edgecore_user1_abc123" \
  http://localhost:5000/api/dashboard

# Token format (also supported)
curl -H "Authorization: Token edgecore_user1_abc123" \
  http://localhost:5000/api/dashboard
```

## Rate Limiting

### How It Works

- Requests are tracked per IP address
- Each IP has a configurable limit (default: 100 requests/minute)
- Old requests are automatically removed after 60 seconds
- Excess requests return `429 Too Many Requests`

### Response Headers

```http
HTTP/1.1 429 Too Many Requests
Content-Type: application/json

{
  "error": "Rate limit exceeded",
  "limit": 100,
  "remaining": 0,
  "retry_after": 60
}
```

### Testing Rate Limiting

```python
import pytest
from monitoring.api_security import RateLimiter

def test_rate_limit():
    limiter = RateLimiter(requests_per_minute=2)
    
    # First 2 requests allowed
    assert limiter.is_allowed('192.168.1.1') is True
    assert limiter.is_allowed('192.168.1.1') is True
    
    # 3rd request rejected
    assert limiter.is_allowed('192.168.1.1') is False
    
    # Query remaining requests
    assert limiter.get_remaining('192.168.1.1') == 0
```

## Authentication

### Security Levels

**No Authentication (Default)**
```python
# Development/testing - no auth required
_auth = APIKeyAuth(required=False)

@app.route('/api/public')
def public_endpoint():
    return {'data': 'public'}, 200
```

**Optional Authentication**
```python
# Production - auth not required but available
_auth = APIKeyAuth(required=False)

@app.route('/api/data')
@require_api_key
def data_endpoint():
    # Can be called with or without key
    return {'data': 'data'}, 200
```

**Required Authentication**
```python
# Strict - auth required for all routes
_auth = APIKeyAuth(required=True)

@app.route('/api/protected')
@require_api_key
def protected_endpoint():
    return {'data': 'sensitive'}, 200
```

### Error Responses

```bash
# Missing API key
curl http://localhost:5000/api/dashboard
# Returns:
# HTTP/1.1 401 Unauthorized
# {"error": "Unauthorized", "message": "Missing or invalid API key"}

# Invalid API key
curl -H "Authorization: Bearer invalid_key" \
  http://localhost:5000/api/dashboard
# Returns 401 (if auth is required)
```

## Security Headers

All responses include OWASP-recommended security headers:

```http
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Strict-Transport-Security: max-age=31536000; includeSubDomains
```

These headers are automatically added by the `@app.after_request` decorator.

## Request Logging & Statistics

### Accessing Statistics

```python
from monitoring.api_security import get_request_stats

# Get API-wide request statistics
stats = get_request_stats()
# Returns:
# {
#   'total': 1234,
#   'avg_time_ms': 45.2,
#   'status_codes': {200: 1200, 429: 34}
# }
```

### Logging Configuration

Requests are logged with:
- HTTP method (GET, POST, etc.)
- URL path
- User ID (or 'anonymous')
- HTTP status code
- Response time (milliseconds)
- Timestamp

### Adding Logging to New Endpoints

```python
@app.route('/api/custom')
@log_api_call                    # Add @ decorator
def custom_endpoint():
    return {'data': 'value'}, 200

# Logs: {"method": "GET", "path": "/api/custom", 
#        "status": 200, "elapsed_ms": 12.5, ...}
```

## HTTPS Enforcement

### Production Mode

```bash
# Force HTTPS in production
REQUIRE_HTTPS=true
```

```python
from monitoring.api_security import require_https

@app.route('/api/data')
@require_https              # Add decorator
def data_endpoint():
    return {'data': 'data'}, 200
```

### Behavior

- **HTTP request**: Returns `403 Forbidden` with message "HTTPS required"
- **HTTPS request**: Allowed and processed normally
- **REQUIRE_HTTPS=false**: HTTP requests allowed (development default)

## Webhook Signature Verification

For webhook security, validate incoming webhooks:

```python
from monitoring.api_security import validate_hmac_signature

# Received webhook data
data = b'{"event": "order", "id": 123}'
signature = 'sha256=abc123...'
secret = 'webhook_secret_key'

# Verify signature
if validate_hmac_signature(data, signature, secret):
    # Process webhook - signature confirmed
    process_webhook(data)
else:
    # Reject webhook - invalid signature
    return {'error': 'Unauthorized'}, 401
```

## Testing Security Decorators

### Unit Tests

```python
import pytest
from flask import Flask
from monitoring.api_security import RateLimiter, APIKeyAuth, require_rate_limit

def test_api_key_auth():
    """Test API key authentication."""
    auth = APIKeyAuth(required=True)
    auth.valid_keys = {'test_key'}
    
    app = Flask(__name__)
    
    with app.test_request_context(
        headers={'Authorization': 'Bearer test_key'}
    ):
        assert auth.authenticate() is not None

def test_rate_limiting():
    """Test rate limiting decorator."""
    app = Flask(__name__)
    limiter = RateLimiter(requests_per_minute=2)
    
    @app.route('/test')
    @require_rate_limit
    def test_route():
        return {'status': 'ok'}, 200
    
    with app.test_client() as client:
        # First 2 requests OK
        assert client.get('/test').status_code == 200
        assert client.get('/test').status_code == 200
        
        # 3rd request rate limited
        assert client.get('/test').status_code == 429
```

### Integration Tests

```python
def test_full_security_flow():
    """Test complete security flow."""
    app = Flask(__name__)
    
    @app.route('/data')
    @require_rate_limit
    @require_api_key
    def data_route():
        return {'data': 'sensitive'}, 200
    
    with app.test_client() as client:
        # No auth - returns 401
        response = client.get('/data')
        assert response.status_code == 401
        
        # With valid token
        response = client.get(
            '/data',
            headers={'Authorization': 'Bearer valid_token'}
        )
        assert response.status_code in [200, 401]
```

## Production Checklist

- [ ] Generate unique API keys per client
- [ ] Store keys securely (environment variables or vault)
- [ ] Enable HTTPS enforcement (`REQUIRE_HTTPS=true`)
- [ ] Set appropriate rate limits (`RATE_LIMIT_RPM=100`)
- [ ] Monitor request statistics for anomalies
- [ ] Review security headers in browser DevTools
- [ ] Test API authentication with curl or Postman
- [ ] Load test under expected traffic
- [ ] Monitor logs for 429 (rate limit) errors
- [ ] Implement key rotation policy

## Common Issues

### 401 Unauthorized on Valid Requests

**Symptom**: Valid API key returns 401

**Solutions**:
1. Verify API key is in `API_KEYS` environment variable
2. Check format: should be `edgecore_*_*` (generated keys)
3. Verify Authorization header format: `Bearer <key>` or `Token <key>`
4. Check if `API_AUTH_REQUIRED=true` is set

### 429 Rate Limited Too Aggressively

**Symptom**: Legitimate requests rejected with 429

**Solutions**:
1. Increase `RATE_LIMIT_RPM` value (default 100)
2. Check if multiple processes share same IP (proxied requests)
3. Verify rate limit is per-IP (not per-user)

### Security Headers Not Appearing

**Symptom**: Missing security headers in responses

**Solutions**:
1. Verify `@app.after_request` decorator is registered
2. Check Flask app initialization includes `add_security_headers`
3. Ensure response goes through standard Flask pipeline

## Performance Impact

**Rate Limiting**: ~0.1ms per request (in-memory tracking)

**Authentication**: ~0.5ms per key lookup

**Security Headers**: Negligible (<0.1ms)

**Logging**: ~1-2ms per request

**Total overhead**: ~2-5ms per request with all features enabled

## Examples

### Secure Dashboard API

```python
from flask import Flask, jsonify
from monitoring.api_security import (
    require_rate_limit,
    require_api_key,
    log_api_call
)

app = Flask(__name__)

# Public endpoint (rate limited, no auth)
@app.route('/health', methods=['GET'])
@require_rate_limit
@log_api_call
def health():
    return {'status': 'healthy'}

# Protected endpoint (rate limited, requires auth, logged)
@app.route('/api/dashboard', methods=['GET'])
@require_rate_limit
@require_api_key
@log_api_call
def dashboard():
    return {
        'equity': 50000,
        'positions': 5,
        'performance': 0.15
    }

# Admin statistics (no rate limit for internal use)
@app.route('/api/stats', methods=['GET'])
@require_api_key
@log_api_call
def stats():
    from monitoring.api_security import get_request_stats
    return get_request_stats()

if __name__ == '__main__':
    app.run()
```

### Client Code

```python
import requests

# API configuration
BASE_URL = 'http://localhost:5000'
API_KEY = 'edgecore_client1_abc123xyz'

headers = {
    'Authorization': f'Bearer {API_KEY}',
    'Content-Type': 'application/json'
}

# Call protected endpoint
response = requests.get(
    f'{BASE_URL}/api/dashboard',
    headers=headers
)

if response.status_code == 200:
    data = response.json()
    print(f"Equity: ${data['equity']}")
elif response.status_code == 429:
    print("Rate limited - try again in 60 seconds")
elif response.status_code == 401:
    print("Invalid or missing API key")
else:
    print(f"Error: {response.status_code}")
```

## See Also

- [API Schema Documentation](./api_schema.py)
- [Flask Security Best Practices](https://flask.palletsprojects.com/security/)
- [OWASP Security Headers](https://owasp.org/www-project-secure-headers/)
- [RFC 6750 - Bearer Token Usage](https://tools.ietf.org/html/rfc6750)
