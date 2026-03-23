"""
Singleton global du rate-limiter IBKR partagé entre tous les modules.

Hard cap TWS : 50 req/s → déconnexion automatique si dépassé.
On opère à 40/s (burst 8) pour garantir une marge en cas d'accès simultané
depuis ibkr_sync_gateway, ibkr_engine et execution_engine/router.

Usage::

    from common.ibkr_rate_limiter import GLOBAL_IBKR_RATE_LIMITER as _ibkr_rate_limiter

    _ibkr_rate_limiter.acquire()  # avant tout appel API IBKR
    ib.reqHistoricalData(...)
"""

from execution.rate_limiter import TokenBucketRateLimiter

GLOBAL_IBKR_RATE_LIMITER: TokenBucketRateLimiter = TokenBucketRateLimiter(rate=40, burst=8)
