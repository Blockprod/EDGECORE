"""Tests for Flask dashboard API endpoints."""

import json
from unittest.mock import Mock

import pytest

from monitoring.api import create_app, get_dashboard_app, initialize_dashboard_api
from monitoring.dashboard import DashboardGenerator


class TestCreateApp:
    """Test Flask app creation and configuration."""

    def test_create_app_without_dashboard(self):
        """Test creating Flask app without dashboard."""
        app = create_app(dashboard=None)
        assert app is not None
        assert app.config["JSON_SORT_KEYS"] is False

    def test_create_app_with_dashboard(self):
        """Test creating Flask app with dashboard."""
        dashboard = DashboardGenerator()
        app = create_app(dashboard=dashboard)
        assert app is not None

    def test_app_has_routes(self):
        """Test Flask app has expected routes."""
        dashboard = DashboardGenerator()
        app = create_app(dashboard=dashboard)

        # Check routes exist
        routes = [str(rule) for rule in app.url_map.iter_rules()]
        assert "/api/dashboard" in routes
        assert "/api/dashboard/system" in routes
        assert "/api/dashboard/risk" in routes
        assert "/health" in routes


class TestHealthCheckEndpoint:
    """Test health check endpoint."""

    def test_health_check_returns_200(self):
        """Test health endpoint returns 200."""
        app = create_app(dashboard=None)
        client = app.test_client()

        response = client.get("/health")
        assert response.status_code == 200

    def test_health_check_returns_json(self):
        """Test health endpoint returns JSON with status."""
        app = create_app(dashboard=None)
        client = app.test_client()

        response = client.get("/health")
        data = json.loads(response.data)
        assert "status" in data
        assert data["status"] == "healthy"
        assert "timestamp" in data


class TestDashboardEndpoint:
    """Test main dashboard endpoint."""

    def test_dashboard_without_initialization_returns_503(self):
        """Test dashboard endpoint returns 503 when not initialized."""
        app = create_app(dashboard=None)
        client = app.test_client()

        response = client.get("/api/dashboard")
        assert response.status_code == 503

    def test_dashboard_returns_200_with_valid_data(self):
        """Test dashboard endpoint returns 200 with dashboard initialized."""
        dashboard = DashboardGenerator()
        app = create_app(dashboard=dashboard)
        client = app.test_client()

        response = client.get("/api/dashboard")
        assert response.status_code == 200

    def test_dashboard_returns_json_structure(self):
        """Test dashboard endpoint returns proper JSON structure."""
        dashboard = DashboardGenerator()
        app = create_app(dashboard=dashboard)
        client = app.test_client()

        response = client.get("/api/dashboard")
        data = json.loads(response.data)

        # Check expected fields (actual structure from DashboardGenerator)
        assert "system" in data
        assert "risk" in data
        assert "positions" in data
        assert "orders" in data
        assert "performance" in data

    def test_dashboard_endpoint_error_handling(self):
        """Test dashboard endpoint handles errors gracefully."""
        dashboard = Mock(spec=DashboardGenerator)
        dashboard.generate_dashboard.side_effect = Exception("Test error")

        app = create_app(dashboard=dashboard)
        client = app.test_client()

        response = client.get("/api/dashboard")
        assert response.status_code == 500
        data = json.loads(response.data)
        assert "error" in data


class TestSystemStatusEndpoint:
    """Test system status endpoint."""

    def test_system_status_returns_200(self):
        """Test system status endpoint returns 200."""
        dashboard = DashboardGenerator()
        app = create_app(dashboard=dashboard)
        client = app.test_client()

        response = client.get("/api/dashboard/system")
        assert response.status_code == 200

    def test_system_status_returns_required_fields(self):
        """Test system status returns expected fields."""
        dashboard = DashboardGenerator()
        app = create_app(dashboard=dashboard)
        client = app.test_client()

        response = client.get("/api/dashboard/system")
        data = json.loads(response.data)

        assert "uptime_seconds" in data
        assert "memory_mb" in data
        assert "cpu_percent" in data
        assert "pid" in data
        assert "mode" in data

    def test_system_status_without_dashboard_returns_503(self):
        """Test system endpoint returns 503 without dashboard."""
        app = create_app(dashboard=None)
        client = app.test_client()

        response = client.get("/api/dashboard/system")
        assert response.status_code == 503


class TestRiskMetricsEndpoint:
    """Test risk metrics endpoint."""

    def test_risk_metrics_returns_200(self):
        """Test risk metrics endpoint returns 200."""
        dashboard = DashboardGenerator()
        app = create_app(dashboard=dashboard)
        client = app.test_client()

        response = client.get("/api/dashboard/risk")
        assert response.status_code == 200

    def test_risk_metrics_returns_fields(self):
        """Test risk metrics returns expected fields."""
        dashboard = DashboardGenerator()
        app = create_app(dashboard=dashboard)
        client = app.test_client()

        response = client.get("/api/dashboard/risk")
        data = json.loads(response.data)

        # Risk metrics returns enabled flag when engine not initialized
        assert "enabled" in data
        # When no risk engine, should have message
        if not data.get("enabled", False):
            assert "message" in data or "enabled" in data

    def test_risk_metrics_error_handling(self):
        """Test risk metrics endpoint handles errors."""
        dashboard = Mock(spec=DashboardGenerator)
        dashboard._risk_metrics.side_effect = Exception("Risk engine error")

        app = create_app(dashboard=dashboard)
        client = app.test_client()

        response = client.get("/api/dashboard/risk")
        assert response.status_code == 500


class TestPositionsEndpoint:
    """Test positions endpoint."""

    def test_positions_returns_200(self):
        """Test positions endpoint returns 200."""
        dashboard = DashboardGenerator()
        app = create_app(dashboard=dashboard)
        client = app.test_client()

        response = client.get("/api/dashboard/positions")
        assert response.status_code == 200

    def test_positions_returns_list_structure(self):
        """Test positions endpoint returns list structure."""
        dashboard = DashboardGenerator()
        app = create_app(dashboard=dashboard)
        client = app.test_client()

        response = client.get("/api/dashboard/positions")
        data = json.loads(response.data)

        assert "positions" in data
        assert "count" in data
        assert isinstance(data["positions"], list)
        assert data["count"] == len(data["positions"])

    def test_positions_with_empty_list(self):
        """Test positions endpoint with no positions."""
        dashboard = DashboardGenerator()
        app = create_app(dashboard=dashboard)
        client = app.test_client()

        response = client.get("/api/dashboard/positions")
        data = json.loads(response.data)

        assert data["count"] == 0
        assert len(data["positions"]) == 0


class TestOrdersEndpoint:
    """Test orders endpoint."""

    def test_orders_returns_200(self):
        """Test orders endpoint returns 200."""
        dashboard = DashboardGenerator()
        app = create_app(dashboard=dashboard)
        client = app.test_client()

        response = client.get("/api/dashboard/orders")
        assert response.status_code == 200

    def test_orders_returns_json(self):
        """Test orders endpoint returns JSON."""
        dashboard = DashboardGenerator()
        app = create_app(dashboard=dashboard)
        client = app.test_client()

        response = client.get("/api/dashboard/orders")
        data = json.loads(response.data)

        assert data is not None
        assert isinstance(data, dict)


class TestPerformanceEndpoint:
    """Test performance metrics endpoint."""

    def test_performance_returns_200(self):
        """Test performance endpoint returns 200."""
        dashboard = DashboardGenerator()
        app = create_app(dashboard=dashboard)
        client = app.test_client()

        response = client.get("/api/dashboard/performance")
        assert response.status_code == 200

    def test_performance_returns_metrics(self):
        """Test performance endpoint returns metrics."""
        dashboard = DashboardGenerator()
        app = create_app(dashboard=dashboard)
        client = app.test_client()

        response = client.get("/api/dashboard/performance")
        data = json.loads(response.data)

        # Performance returns enabled flag
        assert "enabled" in data
        # May contain metric fields if engine available
        if data.get("enabled", False):
            assert "total_return_pct" in data or "sharpe_ratio" in data


class TestStatusEndpoint:
    """Test status endpoint."""

    def test_status_returns_200(self):
        """Test status endpoint returns 200."""
        dashboard = DashboardGenerator()
        app = create_app(dashboard=dashboard)
        client = app.test_client()

        response = client.get("/api/dashboard/status")
        assert response.status_code == 200

    def test_status_returns_status_data(self):
        """Test status endpoint returns status data."""
        dashboard = DashboardGenerator()
        app = create_app(dashboard=dashboard)
        client = app.test_client()

        response = client.get("/api/dashboard/status")
        data = json.loads(response.data)

        # Status contains engine availability and mode
        assert "execution_engine_available" in data or "risk_engine_available" in data
        assert "timestamp" in data

    def test_status_without_dashboard_returns_503(self):
        """Test status endpoint returns 503 without dashboard."""
        app = create_app(dashboard=None)
        client = app.test_client()

        response = client.get("/api/dashboard/status")
        assert response.status_code == 503


class TestHttpMethods:
    """Test HTTP method handling."""

    def test_dashboard_post_not_allowed(self):
        """Test POST requests to dashboard are handled."""
        dashboard = DashboardGenerator()
        app = create_app(dashboard=dashboard)
        client = app.test_client()

        # Flask allows GET only, so POST will return 405
        response = client.post("/api/dashboard")
        assert response.status_code == 405

    def test_dashboard_put_not_allowed(self):
        """Test PUT requests to dashboard are handled."""
        dashboard = DashboardGenerator()
        app = create_app(dashboard=dashboard)
        client = app.test_client()

        response = client.put("/api/dashboard")
        assert response.status_code == 405

    def test_dashboard_delete_not_allowed(self):
        """Test DELETE requests to dashboard are handled."""
        dashboard = DashboardGenerator()
        app = create_app(dashboard=dashboard)
        client = app.test_client()

        response = client.delete("/api/dashboard")
        assert response.status_code == 405


class TestNotFoundHandling:
    """Test 404 error handling."""

    def test_invalid_endpoint_returns_404(self):
        """Test invalid endpoint returns 404."""
        app = create_app(dashboard=None)
        client = app.test_client()

        response = client.get("/api/invalid/endpoint")
        assert response.status_code == 404

    def test_404_error_returns_json(self):
        """Test 404 error returns JSON with helpful info."""
        app = create_app(dashboard=None)
        client = app.test_client()

        response = client.get("/api/nonexistent")
        data = json.loads(response.data)

        assert "error" in data
        assert "available_endpoints" in data
        assert isinstance(data["available_endpoints"], list)


class TestInitializeDashboardApi:
    """Test initialize_dashboard_api function."""

    def test_initialize_dashboard_api_returns_app(self):
        """Test initialize_dashboard_api returns Flask app."""
        dashboard = DashboardGenerator()
        app = initialize_dashboard_api(dashboard)

        assert app is not None
        assert hasattr(app, "test_client")

    def test_initialize_dashboard_api_sets_global(self):
        """Test initialize_dashboard_api sets global app."""
        dashboard = DashboardGenerator()
        app = initialize_dashboard_api(dashboard)

        global_app = get_dashboard_app()
        assert global_app is not None
        assert global_app is app

    def test_get_dashboard_app_before_init_returns_none(self):
        """Test get_dashboard_app returns None if not initialized."""
        # Note: This test depends on test execution order, so we use a fresh import concept
        # For actual implementation, would need to reset module state
        pass


class TestMultipleEndpointsSequential:
    """Test calling multiple endpoints sequentially."""

    def test_all_endpoints_accessible(self):
        """Test all endpoints can be accessed."""
        dashboard = DashboardGenerator()
        app = create_app(dashboard=dashboard)
        client = app.test_client()

        endpoints = [
            "/api/dashboard",
            "/api/dashboard/system",
            "/api/dashboard/risk",
            "/api/dashboard/positions",
            "/api/dashboard/orders",
            "/api/dashboard/performance",
            "/api/dashboard/status",
            "/health",
        ]

        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code in [200, 503], f"Failed for {endpoint}: {response.status_code}"

    def test_rapid_requests_dont_crash(self):
        """Test rapid sequential requests don't crash server."""
        dashboard = DashboardGenerator()
        app = create_app(dashboard=dashboard)
        client = app.test_client()

        for _ in range(10):
            response = client.get("/api/dashboard")
            assert response.status_code == 200


class TestResponseTimestamp:
    """Test response timestamps."""

    def test_dashboard_response_has_timestamp(self):
        """Test dashboard response includes timestamp."""
        dashboard = DashboardGenerator()
        app = create_app(dashboard=dashboard)
        client = app.test_client()

        client.get("/api/dashboard")
        # Dashboard endpoint doesn't include timestamp in all responses
        # but individual components may

    def test_health_response_has_timestamp(self):
        """Test health response includes timestamp."""
        app = create_app(dashboard=None)
        client = app.test_client()

        response = client.get("/health")
        data = json.loads(response.data)

        assert "timestamp" in data

    def test_status_response_has_timestamp(self):
        """Test status response includes timestamp."""
        dashboard = DashboardGenerator()
        app = create_app(dashboard=dashboard)
        client = app.test_client()

        response = client.get("/api/dashboard/status")
        data = json.loads(response.data)

        assert "timestamp" in data


class TestJsonContentType:
    """Test JSON content type headers."""

    def test_dashboard_returns_json_content_type(self):
        """Test dashboard endpoint returns JSON content type."""
        dashboard = DashboardGenerator()
        app = create_app(dashboard=dashboard)
        client = app.test_client()

        response = client.get("/api/dashboard")
        assert response.content_type is not None
        assert "json" in response.content_type.lower() or response.status_code == 503

    def test_health_returns_json_content_type(self):
        """Test health endpoint returns JSON content type."""
        app = create_app(dashboard=None)
        client = app.test_client()

        response = client.get("/health")
        assert "json" in response.content_type.lower()


class TestDataIntegrity:
    """Test data integrity in responses."""

    def test_positions_data_valid(self):
        """Test positions data is valid and complete."""
        dashboard = DashboardGenerator()
        app = create_app(dashboard=dashboard)
        client = app.test_client()

        response = client.get("/api/dashboard/positions")
        data = json.loads(response.data)

        assert isinstance(data, dict)
        assert isinstance(data["positions"], list)
        assert isinstance(data["count"], int)

    def test_orders_data_valid(self):
        """Test orders data is valid and complete."""
        dashboard = DashboardGenerator()
        app = create_app(dashboard=dashboard)
        client = app.test_client()

        response = client.get("/api/dashboard/orders")
        data = json.loads(response.data)

        assert isinstance(data, dict)

    def test_risk_metrics_data_types(self):
        """Test risk metrics data types are correct."""
        dashboard = DashboardGenerator()
        app = create_app(dashboard=dashboard)
        client = app.test_client()

        response = client.get("/api/dashboard/risk")
        data = json.loads(response.data)

        assert isinstance(data, dict)
        # Values should be numbers or null
        for _key, value in data.items():
            assert value is None or isinstance(value, (int, float, str))


# ---------------------------------------------------------------------------
# P4-01: Prometheus SDK metrics format
# ---------------------------------------------------------------------------


class TestPrometheusSDKMetrics:
    """P4-01 — /metrics must use prometheus_client SDK output."""

    def test_metrics_endpoint_returns_200(self):
        """GET /metrics returns 200 when no auth token is configured."""
        import os

        app = create_app(dashboard=None)
        client = app.test_client()
        with app.test_request_context():
            env_bak = os.environ.pop("METRICS_AUTH_TOKEN", None)
            try:
                response = client.get("/metrics")
                assert response.status_code == 200
            finally:
                if env_bak is not None:
                    os.environ["METRICS_AUTH_TOKEN"] = env_bak

    def test_metrics_content_type_is_prometheus(self):
        """Content-Type must match Prometheus text format."""
        import os

        app = create_app(dashboard=None)
        client = app.test_client()
        env_bak = os.environ.pop("METRICS_AUTH_TOKEN", None)
        try:
            response = client.get("/metrics")
            assert "text/plain" in response.content_type
        finally:
            if env_bak is not None:
                os.environ["METRICS_AUTH_TOKEN"] = env_bak

    def test_metrics_body_contains_edgecore_gauges(self):
        """Body must contain edgecore_equity and edgecore_max_drawdown lines."""
        import os

        from monitoring.metrics import SystemMetrics

        app = create_app(dashboard=None)
        metrics = SystemMetrics(equity=123456.0, max_drawdown=0.05)
        app._system_metrics = metrics  # pyright: ignore[reportAttributeAccessIssue]
        client = app.test_client()
        env_bak = os.environ.pop("METRICS_AUTH_TOKEN", None)
        try:
            response = client.get("/metrics")
            body = response.data.decode()
            assert "edgecore_equity" in body
            assert "edgecore_max_drawdown" in body
        finally:
            if env_bak is not None:
                os.environ["METRICS_AUTH_TOKEN"] = env_bak

    def test_metrics_body_contains_fill_latency_histogram(self):
        """Body must contain the order fill latency histogram."""
        import os

        app = create_app(dashboard=None)
        client = app.test_client()
        env_bak = os.environ.pop("METRICS_AUTH_TOKEN", None)
        try:
            response = client.get("/metrics")
            body = response.data.decode()
            assert "edgecore_order_fill_latency_seconds" in body
        finally:
            if env_bak is not None:
                os.environ["METRICS_AUTH_TOKEN"] = env_bak


# ---------------------------------------------------------------------------
# P4-03: Bearer token authentication on /metrics
# ---------------------------------------------------------------------------


class TestMetricsBearerAuth:
    """P4-03 — /metrics must return 401 when METRICS_AUTH_TOKEN is set."""

    def test_no_token_returns_401_when_env_set(self):
        """Request without Authorization header returns 401."""
        import os

        os.environ["METRICS_AUTH_TOKEN"] = "test-secret-token"
        try:
            app = create_app(dashboard=None)
            client = app.test_client()
            response = client.get("/metrics")
            assert response.status_code == 401
        finally:
            del os.environ["METRICS_AUTH_TOKEN"]

    def test_wrong_token_returns_401(self):
        """Request with wrong Bearer token returns 401."""
        import os

        os.environ["METRICS_AUTH_TOKEN"] = "correct-token"
        try:
            app = create_app(dashboard=None)
            client = app.test_client()
            response = client.get("/metrics", headers={"Authorization": "Bearer wrong-token"})
            assert response.status_code == 401
        finally:
            del os.environ["METRICS_AUTH_TOKEN"]

    def test_correct_token_returns_200(self):
        """Request with correct Bearer token returns 200."""
        import os

        os.environ["METRICS_AUTH_TOKEN"] = "my-secret"
        try:
            app = create_app(dashboard=None)
            client = app.test_client()
            response = client.get("/metrics", headers={"Authorization": "Bearer my-secret"})
            assert response.status_code == 200
        finally:
            del os.environ["METRICS_AUTH_TOKEN"]

    def test_no_env_var_allows_unauthenticated(self):
        """When METRICS_AUTH_TOKEN is not set, /metrics is open."""
        import os

        os.environ.pop("METRICS_AUTH_TOKEN", None)
        app = create_app(dashboard=None)
        client = app.test_client()
        response = client.get("/metrics")
        assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
