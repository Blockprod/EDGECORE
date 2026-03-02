"""Flask API endpoints for EDGECORE dashboard."""

from typing import Optional, Dict, Any, Tuple
from flask import Flask, request
from datetime import datetime
import structlog

from monitoring.dashboard import DashboardGenerator
from monitoring.api_security import (
    require_rate_limit,
    require_api_key,
    add_security_headers,
    log_api_call,
    get_request_stats
)

logger = structlog.get_logger(__name__)

# Global dashboard instance
_dashboard_instance: Optional[DashboardGenerator] = None
_flask_app: Optional[Flask] = None


def create_app(dashboard: Optional[DashboardGenerator] = None) -> Flask:
    """
    Create and configure Flask app for dashboard API.

    Args:
        dashboard: Optional DashboardGenerator instance

    Returns:
        Configured Flask app
    """
    app = Flask(__name__)
    app.config['JSON_SORT_KEYS'] = False

    # Register routes
    @app.route('/health', methods=['GET'])
    @require_rate_limit
    @log_api_call
    def health() -> Tuple[Dict[str, str], int]:
        """
        Health check endpoint (no auth required).

        Returns:
            Simple OK status
        """
        return {'status': 'healthy', 'timestamp': datetime.now().isoformat()}, 200

    @app.route('/api/dashboard', methods=['GET'])
    @require_rate_limit
    @require_api_key
    @log_api_call
    def api_dashboard() -> Tuple[Dict[str, Any], int]:
        """
        Get complete dashboard snapshot.

        Returns:
            JSON with system status, risk metrics, positions, orders, alerts
        """
        if dashboard is None:
            return {
                'error': 'Dashboard not initialized',
                'timestamp': datetime.now().isoformat()
            }, 503

        try:
            result = dashboard.generate_dashboard()
            return result, 200
        except Exception as e:
            logger.error("dashboard_api_error", error=str(e))
            return {'error': str(e), 'timestamp': datetime.now().isoformat()}, 500

    @app.route('/api/dashboard/system', methods=['GET'])
    @require_rate_limit
    @require_api_key
    @log_api_call
    def api_system_status() -> Tuple[Dict[str, Any], int]:
        """
        Get system status (uptime, mode, memory, CPU).

        Returns:
            JSON with system metrics
        """
        if dashboard is None:
            return {'error': 'Dashboard not initialized'}, 503

        try:
            status = dashboard._system_status()
            return status, 200
        except Exception as e:
            logger.error("system_status_api_error", error=str(e))
            return {'error': str(e)}, 500

    @app.route('/api/dashboard/risk', methods=['GET'])
    @require_rate_limit
    @require_api_key
    @log_api_call
    def api_risk_metrics() -> Tuple[Dict[str, Any], int]:
        """
        Get risk metrics (equity, drawdown, position limits).

        Returns:
            JSON with risk metrics
        """
        if dashboard is None:
            return {'error': 'Dashboard not initialized'}, 503

        try:
            metrics = dashboard._risk_metrics()
            return metrics, 200
        except Exception as e:
            logger.error("risk_metrics_api_error", error=str(e))
            return {'error': str(e)}, 500

    @app.route('/api/dashboard/positions', methods=['GET'])
    @require_rate_limit
    @require_api_key
    @log_api_call
    def api_positions() -> Tuple[Dict[str, Any], int]:
        """
        Get open positions.

        Returns:
            JSON with list of positions
        """
        if dashboard is None:
            return {'error': 'Dashboard not initialized'}, 503

        try:
            positions = dashboard._positions()
            return {'positions': positions, 'count': len(positions)}, 200
        except Exception as e:
            logger.error("positions_api_error", error=str(e))
            return {'error': str(e)}, 500

    @app.route('/api/dashboard/orders', methods=['GET'])
    @require_rate_limit
    @require_api_key
    @log_api_call
    def api_orders() -> Tuple[Dict[str, Any], int]:
        """
        Get open orders.

        Returns:
            JSON with orders data
        """
        if dashboard is None:
            return {'error': 'Dashboard not initialized'}, 503

        try:
            orders = dashboard._orders()
            return orders, 200
        except Exception as e:
            logger.error("orders_api_error", error=str(e))
            return {'error': str(e)}, 500

    @app.route('/api/dashboard/performance', methods=['GET'])
    @require_rate_limit
    @require_api_key
    @log_api_call
    def api_performance() -> Tuple[Dict[str, Any], int]:
        """
        Get performance metrics (returns, Sharpe, drawdown).

        Returns:
            JSON with performance metrics
        """
        if dashboard is None:
            return {'error': 'Dashboard not initialized'}, 503

        try:
            performance = dashboard._performance_metrics()
            return performance, 200
        except Exception as e:
            logger.error("performance_api_error", error=str(e))
            return {'error': str(e)}, 500

    @app.route('/api/dashboard/status', methods=['GET'])
    @require_rate_limit
    @require_api_key
    @log_api_call
    def api_status() -> Tuple[Dict[str, Any], int]:
        """
        Get dashboard generator status.

        Returns:
            JSON with dashboard status
        """
        if dashboard is None:
            return {
                'initialized': False,
                'timestamp': datetime.now().isoformat()
            }, 503

        try:
            status = dashboard.get_status()
            status['timestamp'] = datetime.now().isoformat()
            return status, 200
        except Exception as e:
            logger.error("status_api_error", error=str(e))
            return {'error': str(e)}, 500

    @app.route('/api/stats', methods=['GET'])
    @log_api_call
    def api_stats() -> Tuple[Dict[str, Any], int]:
        """
        Get API request statistics (no auth required).

        Returns:
            JSON with request statistics
        """
        stats = get_request_stats()
        return stats, 200

    @app.route('/metrics', methods=['GET'])
    def prometheus_metrics():
        """
        Prometheus scrape endpoint.

        Returns Prometheus text format metrics for the trading system.
        No auth required — intended for internal Prometheus scraping.
        """
        from monitoring.metrics import SystemMetrics
        from flask import Response

        # Use global metrics instance if available, else default
        metrics = getattr(app, '_system_metrics', None) or SystemMetrics()
        body = metrics.to_prometheus_format()
        return Response(body, mimetype='text/plain; version=0.0.4; charset=utf-8')

    @app.errorhandler(404)
    def not_found(error) -> Tuple[Dict[str, Any], int]:
        """Handle 404 errors."""
        return {
            'error': 'Not found',
            'message': f"Endpoint not found: {request.path}",
            'available_endpoints': [
                '/health',
                '/metrics',
                '/api/dashboard',
                '/api/dashboard/system',
                '/api/dashboard/risk',
                '/api/dashboard/positions',
                '/api/dashboard/orders',
                '/api/dashboard/performance',
                '/api/dashboard/status',
                '/api/stats'
            ]
        }, 404

    @app.errorhandler(500)
    def internal_error(error) -> Tuple[Dict[str, Any], int]:
        """Handle 500 errors."""
        logger.error("internal_server_error", error=str(error))
        return {
            'error': 'Internal server error',
            'timestamp': datetime.now().isoformat()
        }, 500

    @app.after_request
    def apply_security_headers(response):
        """Apply security headers to all responses."""
        return add_security_headers(response)

    logger.info("flask_app_created", routes=len(app.url_map._rules))
    return app


def initialize_dashboard_api(dashboard: DashboardGenerator) -> Flask:
    """
    Initialize and return configured Flask app with dashboard.

    Args:
        dashboard: DashboardGenerator instance

    Returns:
        Configured Flask app
    """
    global _dashboard_instance, _flask_app

    _dashboard_instance = dashboard
    _flask_app = create_app(dashboard)

    logger.info("dashboard_api_initialized",
               risk_engine_available=dashboard.risk_engine is not None,
               execution_engine_available=dashboard.execution_engine is not None)

    return _flask_app


def get_dashboard_app() -> Optional[Flask]:
    """
    Get the global Flask app instance.

    Returns:
        Flask app or None if not initialized
    """
    return _flask_app


def run_api_server(host: str = "127.0.0.1", port: int = 5000, debug: bool = False) -> None:
    """
    Run the Flask API server.

    Args:
        host: Server host (default: localhost)
        port: Server port (default: 5000)
        debug: Enable debug mode (default: False)
    """
    if _flask_app is None:
        logger.error("dashboard_api_not_initialized")
        raise RuntimeError("Dashboard API not initialized. Call initialize_dashboard_api() first.")

    logger.info("starting_dashboard_api_server",
               host=host,
               port=port,
               debug=debug)

    _flask_app.run(host=host, port=port, debug=debug, use_reloader=False)
