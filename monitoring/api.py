"""Flask API endpoints for EDGECORE dashboard."""

<<<<<<< HEAD
=======
from typing import Optional, Dict, Any, Tuple
from flask import Flask, request
>>>>>>> origin/main
from datetime import datetime
from typing import Any

import structlog
from flask import Flask, render_template_string, request

from monitoring.api_security import (
    add_security_headers,
<<<<<<< HEAD
    get_request_stats,
    log_api_call,
    require_api_key,
    require_rate_limit,
=======
    log_api_call,
    get_request_stats
>>>>>>> origin/main
)
from monitoring.dashboard import DashboardGenerator

logger = structlog.get_logger(__name__)

# Global dashboard instance
_dashboard_instance: DashboardGenerator | None = None
_flask_app: Flask | None = None


def create_app(dashboard: DashboardGenerator | None = None) -> Flask:
    """
    Create and configure Flask app for dashboard API.

    Args:
        dashboard: Optional DashboardGenerator instance

    Returns:
        Configured Flask app
    """
    app = Flask(__name__)
    app.config["JSON_SORT_KEYS"] = False

    # Register routes
    @app.route("/health", methods=["GET"])
    @require_rate_limit
    @log_api_call
    def health() -> tuple[dict[str, str], int]:
        """
        Health check endpoint (no auth required).

        Returns:
            Simple OK status
        """
        return {"status": "healthy", "timestamp": datetime.now().isoformat()}, 200

    @app.route("/api/dashboard", methods=["GET"])
    @require_rate_limit
    @require_api_key
    @log_api_call
    def api_dashboard() -> tuple[dict[str, Any], int]:
        """
        Get complete dashboard snapshot.

        Returns:
            JSON with system status, risk metrics, positions, orders, alerts
        """
        if dashboard is None:
            return {"error": "Dashboard not initialized", "timestamp": datetime.now().isoformat()}, 503

        try:
            result = dashboard.generate_dashboard()
            return result, 200
        except Exception as e:
            logger.error("dashboard_api_error", error=str(e))
            return {"error": str(e), "timestamp": datetime.now().isoformat()}, 500

    @app.route("/api/dashboard/system", methods=["GET"])
    @require_rate_limit
    @require_api_key
    @log_api_call
    def api_system_status() -> tuple[dict[str, Any], int]:
        """
        Get system status (uptime, mode, memory, CPU).

        Returns:
            JSON with system metrics
        """
        if dashboard is None:
            return {"error": "Dashboard not initialized"}, 503

        try:
            status = dashboard._system_status()
            return status, 200
        except Exception as e:
            logger.error("system_status_api_error", error=str(e))
            return {"error": str(e)}, 500

    @app.route("/api/dashboard/risk", methods=["GET"])
    @require_rate_limit
    @require_api_key
    @log_api_call
    def api_risk_metrics() -> tuple[dict[str, Any], int]:
        """
        Get risk metrics (equity, drawdown, position limits).

        Returns:
            JSON with risk metrics
        """
        if dashboard is None:
            return {"error": "Dashboard not initialized"}, 503

        try:
            metrics = dashboard._risk_metrics()
            return metrics, 200
        except Exception as e:
            logger.error("risk_metrics_api_error", error=str(e))
            return {"error": str(e)}, 500

    @app.route("/api/dashboard/positions", methods=["GET"])
    @require_rate_limit
    @require_api_key
    @log_api_call
    def api_positions() -> tuple[dict[str, Any], int]:
        """
        Get open positions.

        Returns:
            JSON with list of positions
        """
        if dashboard is None:
            return {"error": "Dashboard not initialized"}, 503

        try:
            positions = dashboard._positions()
            return {"positions": positions, "count": len(positions)}, 200
        except Exception as e:
            logger.error("positions_api_error", error=str(e))
            return {"error": str(e)}, 500

    @app.route("/api/dashboard/orders", methods=["GET"])
    @require_rate_limit
    @require_api_key
    @log_api_call
    def api_orders() -> tuple[dict[str, Any], int]:
        """
        Get open orders.

        Returns:
            JSON with orders data
        """
        if dashboard is None:
            return {"error": "Dashboard not initialized"}, 503

        try:
            orders = dashboard._orders()
            return orders, 200
        except Exception as e:
            logger.error("orders_api_error", error=str(e))
            return {"error": str(e)}, 500

    @app.route("/api/dashboard/performance", methods=["GET"])
    @require_rate_limit
    @require_api_key
    @log_api_call
    def api_performance() -> tuple[dict[str, Any], int]:
        """
        Get performance metrics (returns, Sharpe, drawdown).

        Returns:
            JSON with performance metrics
        """
        if dashboard is None:
            return {"error": "Dashboard not initialized"}, 503

        try:
            performance = dashboard._performance_metrics()
            return performance, 200
        except Exception as e:
            logger.error("performance_api_error", error=str(e))
            return {"error": str(e)}, 500

    @app.route("/api/dashboard/status", methods=["GET"])
    @require_rate_limit
    @require_api_key
    @log_api_call
    def api_status() -> tuple[dict[str, Any], int]:
        """
        Get dashboard generator status.

        Returns:
            JSON with dashboard status
        """
        if dashboard is None:
            return {"initialized": False, "timestamp": datetime.now().isoformat()}, 503

        try:
            status = dashboard.get_status()
            status["timestamp"] = datetime.now().isoformat()
            return status, 200
        except Exception as e:
            logger.error("status_api_error", error=str(e))
            return {"error": str(e)}, 500

    @app.route("/api/stats", methods=["GET"])
    @log_api_call
    def api_stats() -> tuple[dict[str, Any], int]:
        """
        Get API request statistics (no auth required).

        Returns:
            JSON with request statistics
        """
        stats = get_request_stats()
        return stats, 200

<<<<<<< HEAD
    @app.route("/api/public/summary", methods=["GET"])
    @require_rate_limit
    @log_api_call
    def api_public_summary() -> tuple[dict[str, Any], int]:
        """
        Public summary endpoint — no auth required.

        Returns a minimal subset of metrics safe for unauthenticated access:
        mode, equity, daily_return, sharpe_ratio, trades_today, system status.
        Intended for the /dashboard HTML page and internal Prometheus scraping.
        """
        from monitoring.metrics import SystemMetrics

        metrics: SystemMetrics = getattr(app, "_system_metrics", None) or SystemMetrics()
        mode = "unknown"
        status = "running"

        if dashboard is not None:
            try:
                sys_status = dashboard._system_status()
                mode = sys_status.get("mode", "unknown")
                status = sys_status.get("status", "running")
            except Exception:
                pass

        return {
            "timestamp": datetime.now().isoformat(),
            "status": status,
            "mode": mode,
            "equity": metrics.equity,
            "daily_return_pct": round(metrics.daily_return * 100, 4),
            "max_drawdown_pct": round(metrics.max_drawdown * 100, 4),
            "sharpe_ratio": round(metrics.sharpe_ratio, 4),
            "trades_total": metrics.trades_total,
            "trades_today": metrics.trades_today,
            "risk_violations": metrics.risk_violations,
        }, 200

    _DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta http-equiv="refresh" content="10">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>EDGECORE — Live Dashboard</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: 'Courier New', monospace; background: #0d1117; color: #c9d1d9; padding: 24px; }
    h1 { font-size: 1.4rem; color: #58a6ff; margin-bottom: 4px; }
    .subtitle { font-size: 0.8rem; color: #6e7681; margin-bottom: 24px; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 32px; }
    .card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px; }
    .card .label { font-size: 0.72rem; color: #8b949e; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 6px; }
    .card .value { font-size: 1.6rem; font-weight: bold; color: #f0f6fc; }
    .card .value.positive { color: #3fb950; }
    .card .value.negative { color: #f85149; }
    .card .value.neutral { color: #58a6ff; }
    .badge { display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: 0.75rem; font-weight: bold; }
    .badge.live { background: #1f3d2e; color: #3fb950; border: 1px solid #3fb950; }
    .badge.paper { background: #1e2d3d; color: #58a6ff; border: 1px solid #58a6ff; }
    .badge.unknown { background: #2d2d2d; color: #8b949e; border: 1px solid #8b949e; }
    .footer { font-size: 0.72rem; color: #484f58; text-align: center; margin-top: 16px; }
    .error { color: #f85149; background: #1f1b1b; border: 1px solid #f85149; border-radius: 6px; padding: 12px; margin-top: 16px; }
  </style>
</head>
<body>
  <h1>EDGECORE &mdash; Live Dashboard</h1>
  <p class="subtitle">Auto-refresh every 10s &bull; Source: <code>/api/public/summary</code></p>
  <div class="grid" id="grid">
    <div class="card"><div class="label">Loading&hellip;</div><div class="value neutral">&mdash;</div></div>
  </div>
  <div class="footer" id="footer">Last update: &mdash;</div>
  <div id="error-box"></div>

  <script>
    function colorClass(label, value) {
      if (label.includes('return') || label.includes('sharpe')) return value >= 0 ? 'positive' : 'negative';
      if (label.includes('drawdown') || label.includes('violations')) return value > 0 ? 'negative' : 'positive';
      return 'neutral';
    }

    function fmt(label, value) {
      if (label.includes('equity')) return '$' + value.toLocaleString('en-US', {maximumFractionDigits: 0});
      if (label.includes('pct') || label.includes('return') || label.includes('drawdown')) return value.toFixed(2) + '%';
      if (label.includes('sharpe')) return value.toFixed(3);
      return value;
    }

    const LABELS = {
      equity: 'Equity',
      daily_return_pct: 'Daily Return',
      max_drawdown_pct: 'Max Drawdown',
      sharpe_ratio: 'Sharpe Ratio',
      trades_total: 'Trades (Total)',
      trades_today: 'Trades (Today)',
      risk_violations: 'Risk Violations',
    };

    async function refresh() {
      const errBox = document.getElementById('error-box');
      try {
        const r = await fetch('/api/public/summary');
        if (!r.ok) throw new Error('HTTP ' + r.status);
        const d = await r.json();
        errBox.innerHTML = '';

        const mode = d.mode || 'unknown';
        const modeClass = ['live','paper'].includes(mode) ? mode : 'unknown';
        let html = `<div class="card"><div class="label">Mode</div><div class="value"><span class="badge ${modeClass}">${mode.toUpperCase()}</span></div></div>`;
        html += `<div class="card"><div class="label">Status</div><div class="value neutral">${d.status || '?'}</div></div>`;
        for (const [key, label] of Object.entries(LABELS)) {
          const v = d[key];
          if (v === undefined) continue;
          const cls = colorClass(key, v);
          html += `<div class="card"><div class="label">${label}</div><div class="value ${cls}">${fmt(key, v)}</div></div>`;
        }
        document.getElementById('grid').innerHTML = html;
        document.getElementById('footer').textContent = 'Last update: ' + new Date(d.timestamp).toLocaleTimeString();
      } catch(e) {
        errBox.innerHTML = '<div class="error">&#9888; Failed to fetch summary: ' + e.message + '</div>';
      }
    }
    refresh();
  </script>
</body>
</html>"""

    @app.route("/dashboard", methods=["GET"])
    @require_rate_limit
    @log_api_call
    def dashboard_ui():
        """
        Browser-accessible live dashboard (G3-01).

        No auth required. Pulls live metrics from /api/public/summary
        via JavaScript and auto-refreshes every 10 seconds.
        """
        return render_template_string(_DASHBOARD_HTML)

    @app.route("/metrics", methods=["GET"])
    def prometheus_metrics():
        """
        Prometheus scrape endpoint.

        Returns Prometheus text format metrics for the trading system.
        No auth required ÔÇö intended for internal Prometheus scraping.
        """
        from flask import Response

        from monitoring.metrics import SystemMetrics

        # Use global metrics instance if available, else default
        metrics = getattr(app, "_system_metrics", None) or SystemMetrics()
        body = metrics.to_prometheus_format()
        return Response(body, mimetype="text/plain; version=0.0.4; charset=utf-8")

    @app.errorhandler(404)
    def not_found(error) -> tuple[dict[str, Any], int]:
        """Handle 404 errors."""
        logger.warning("not_found", error=str(error), path=request.path)
        return {
            "error": "Not found",
            "message": f"Endpoint not found: {request.path}",
            "available_endpoints": [
                "/health",
                "/metrics",
                "/dashboard",
                "/api/public/summary",
                "/api/dashboard",
                "/api/dashboard/system",
                "/api/dashboard/risk",
                "/api/dashboard/positions",
                "/api/dashboard/orders",
                "/api/dashboard/performance",
                "/api/dashboard/status",
                "/api/stats",
            ],
=======
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
>>>>>>> origin/main
        }, 404

    @app.errorhandler(500)
    def internal_error(error) -> tuple[dict[str, Any], int]:
        """Handle 500 errors."""
        logger.error("internal_server_error", error=str(error))
        return {"error": "Internal server error", "timestamp": datetime.now().isoformat()}, 500

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

    logger.info(
        "dashboard_api_initialized",
        risk_engine_available=dashboard.risk_engine is not None,
        execution_engine_available=dashboard.execution_engine is not None,
    )

    return _flask_app


def get_dashboard_app() -> Flask | None:
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

    logger.info("starting_dashboard_api_server", host=host, port=port, debug=debug)

    _flask_app.run(host=host, port=port, debug=debug, use_reloader=False)
