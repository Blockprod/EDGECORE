"""
OpenAPI/Swagger documentation for EDGECORE Flask API.

Provides complete API specification with request/response schemas,
error codes, authentication, and rate limiting documentation.
"""

API_VERSION = "1.0.0"
API_TITLE = "EDGECORE Trading System API"
API_DESCRIPTION = """
Real-time trading system monitoring and metrics API.

# Authentication
All endpoints require an API key (in production):
```
Authorization: Bearer YOUR_API_KEY
```

# Rate Limiting
- Default: 100 requests per minute
- Burst: 200 requests per minute
- Based on IP address

# Response Formats
All responses use JSON format. Each response includes a timestamp.

# Error Handling
- 200: Success
- 400: Bad request (invalid parameters)
- 401: Unauthorized (missing/invalid API key)
- 403: Forbidden (insufficient permissions)
- 429: Too many requests (rate limited)
- 500: Server error
- 503: Service unavailable (dashboard not initialized)
"""

OPENAPI_SPEC = {
    "openapi": "3.0.0",
    "info": {
        "title": API_TITLE,
        "description": API_DESCRIPTION,
        "version": API_VERSION,
        "contact": {
            "name": "EDGECORE Support",
            "url": "https://github.com/edgecore/trading-system"
        },
        "license": {
            "name": "Proprietary"
        }
    },
    "servers": [
        {
            "url": "http://localhost:5000",
            "description": "Development server"
        },
        {
            "url": "https://api.edgecore.example.com",
            "description": "Production server"
        }
    ],
    "paths": {
        "/health": {
            "get": {
                "summary": "Health check",
                "description": "Check if API server is running",
                "operationId": "getHealth",
                "tags": ["System"],
                "responses": {
                    "200": {
                        "description": "Server is healthy",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "status": {
                                            "type": "string",
                                            "example": "healthy"
                                        },
                                        "timestamp": {
                                            "type": "string",
                                            "format": "date-time"
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/api/dashboard": {
            "get": {
                "summary": "Get complete dashboard snapshot",
                "description": "Returns all system metrics: status, risk, positions, orders, performance",
                "operationId": "getDashboard",
                "tags": ["Dashboard"],
                "security": [{"api_key": []}],
                "parameters": [
                    {
                        "name": "include",
                        "in": "query",
                        "description": "Comma-separated list of sections to include (system,risk,positions,orders,performance)",
                        "schema": {"type": "string"},
                        "example": "system,risk,positions"
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Dashboard snapshot",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "timestamp": {"type": "string", "format": "date-time"},
                                        "system": {"$ref": "#/components/schemas/SystemStatus"},
                                        "risk": {"$ref": "#/components/schemas/RiskMetrics"},
                                        "positions": {
                                            "type": "array",
                                            "items": {"$ref": "#/components/schemas/Position"}
                                        },
                                        "orders": {"$ref": "#/components/schemas/Orders"},
                                        "performance": {"$ref": "#/components/schemas/PerformanceMetrics"}
                                    }
                                }
                            }
                        }
                    },
                    "401": {"description": "Unauthorized (missing/invalid API key)"},
                    "429": {"description": "Too many requests"},
                    "503": {"description": "Dashboard not initialized"}
                }
            }
        },
        "/api/dashboard/system": {
            "get": {
                "summary": "Get system status",
                "description": "Process metrics: uptime, memory, CPU, mode",
                "operationId": "getSystemStatus",
                "tags": ["Dashboard"],
                "security": [{"api_key": []}],
                "responses": {
                    "200": {
                        "description": "System status",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/SystemStatus"}
                            }
                        }
                    },
                    "401": {"description": "Unauthorized"},
                    "429": {"description": "Too many requests"},
                    "503": {"description": "Dashboard not initialized"}
                }
            }
        },
        "/api/dashboard/risk": {
            "get": {
                "summary": "Get risk metrics",
                "description": "Equity, drawdown, loss tracking",
                "operationId": "getRiskMetrics",
                "tags": ["Dashboard"],
                "security": [{"api_key": []}],
                "responses": {
                    "200": {
                        "description": "Risk metrics",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/RiskMetrics"}
                            }
                        }
                    },
                    "401": {"description": "Unauthorized"},
                    "429": {"description": "Too many requests"},
                    "503": {"description": "Dashboard not initialized"}
                }
            }
        },
        "/api/dashboard/positions": {
            "get": {
                "summary": "Get open positions",
                "description": "List of all open trading positions",
                "operationId": "getPositions",
                "tags": ["Dashboard"],
                "security": [{"api_key": []}],
                "responses": {
                    "200": {
                        "description": "Open positions",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "positions": {
                                            "type": "array",
                                            "items": {"$ref": "#/components/schemas/Position"}
                                        },
                                        "count": {"type": "integer"}
                                    }
                                }
                            }
                        }
                    },
                    "401": {"description": "Unauthorized"},
                    "429": {"description": "Too many requests"},
                    "503": {"description": "Dashboard not initialized"}
                }
            }
        },
        "/api/dashboard/orders": {
            "get": {
                "summary": "Get open orders",
                "description": "List of all orders submitted to exchange",
                "operationId": "getOrders",
                "tags": ["Dashboard"],
                "security": [{"api_key": []}],
                "responses": {
                    "200": {
                        "description": "Open orders",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/Orders"}
                            }
                        }
                    },
                    "401": {"description": "Unauthorized"},
                    "429": {"description": "Too many requests"},
                    "503": {"description": "Dashboard not initialized"}
                }
            }
        },
        "/api/dashboard/performance": {
            "get": {
                "summary": "Get performance metrics",
                "description": "Returns, Sharpe ratio, max drawdown",
                "operationId": "getPerformance",
                "tags": ["Dashboard"],
                "security": [{"api_key": []}],
                "responses": {
                    "200": {
                        "description": "Performance metrics",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/PerformanceMetrics"}
                            }
                        }
                    },
                    "401": {"description": "Unauthorized"},
                    "429": {"description": "Too many requests"},
                    "503": {"description": "Dashboard not initialized"}
                }
            }
        },
        "/api/dashboard/status": {
            "get": {
                "summary": "Get dashboard status",
                "description": "Dashboard generator status and availability",
                "operationId": "getStatus",
                "tags": ["System"],
                "security": [{"api_key": []}],
                "responses": {
                    "200": {
                        "description": "Dashboard status",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "initialized": {"type": "boolean"},
                                        "risk_engine_available": {"type": "boolean"},
                                        "execution_engine_available": {"type": "boolean"},
                                        "mode": {"type": "string"},
                                        "timestamp": {"type": "string", "format": "date-time"}
                                    }
                                }
                            }
                        }
                    },
                    "401": {"description": "Unauthorized"},
                    "503": {"description": "Dashboard not initialized"}
                }
            }
        }
    },
    "components": {
        "schemas": {
            "SystemStatus": {
                "type": "object",
                "properties": {
                    "uptime_seconds": {"type": "number"},
                    "uptime_readable": {"type": "string"},
                    "memory_mb": {"type": "number"},
                    "cpu_percent": {"type": "number"},
                    "pid": {"type": "integer"},
                    "mode": {"type": "string", "enum": ["paper", "live"]},
                    "version": {"type": "string"}
                }
            },
            "RiskMetrics": {
                "type": "object",
                "properties": {
                    "enabled": {"type": "boolean"},
                    "current_equity": {"type": "number"},
                    "return_pct": {"type": "number"},
                    "drawdown": {"type": "number"},
                    "daily_loss": {"type": "number"},
                    "max_position_size": {"type": "number"},
                    "message": {"type": "string"}
                }
            },
            "Position": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "example": "BTC/USDT"},
                    "side": {"type": "string", "enum": ["long", "short"]},
                    "quantity": {"type": "number"},
                    "entry_price": {"type": "number"},
                    "current_price": {"type": "number"},
                    "pnl": {"type": "number"},
                    "pnl_pct": {"type": "number"},
                    "age_hours": {"type": "number"}
                }
            },
            "Orders": {
                "type": "object",
                "properties": {
                    "enabled": {"type": "boolean"},
                    "orders": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "symbol": {"type": "string"},
                                "side": {"type": "string"},
                                "amount": {"type": "number"},
                                "price": {"type": "number"},
                                "status": {"type": "string"}
                            }
                        }
                    },
                    "count": {"type": "integer"}
                }
            },
            "PerformanceMetrics": {
                "type": "object",
                "properties": {
                    "enabled": {"type": "boolean"},
                    "total_return_pct": {"type": "number"},
                    "sharpe_ratio": {"type": "number"},
                    "max_drawdown_pct": {"type": "number"},
                    "data_points": {"type": "integer"}
                }
            }
        },
        "securitySchemes": {
            "api_key": {
                "type": "apiKey",
                "in": "header",
                "name": "Authorization",
                "description": "API key in format: Bearer YOUR_API_KEY"
            }
        }
    },
    "tags": [
        {
            "name": "System",
            "description": "System health and status endpoints"
        },
        {
            "name": "Dashboard",
            "description": "Dashboard and metrics endpoints"
        }
    ]
}


def get_openapi_spec():
    """Get OpenAPI specification as dictionary."""
    return OPENAPI_SPEC


def generate_swagger_ui_html():
    """Generate HTML for Swagger UI."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>EDGECORE Trading System API - Swagger UI</title>
        <link rel="stylesheet" type="text/css" 
              href="https://cdnjs.cloudflare.com/ajax/libs/swagger-ui/4.15.5/swagger-ui.min.css">
        <style>
            html {
                box-sizing: border-box;
                overflow: -moz-scrollbars-vertical;
                overflow-y: scroll;
            }
            body {
                margin: 0;
                padding: 0;
            }
        </style>
    </head>
    <body>
        <div id="swagger-ui"></div>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/swagger-ui/4.15.5/swagger-ui.min.js"></script>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/swagger-ui/4.15.5/swagger-ui-bundle.min.js"></script>
        <script>
            SwaggerUIBundle({
                url: "/api/openapi.json",
                dom_id: '#swagger-ui',
                presets: [
                    SwaggerUIBundle.presets.apis,
                    SwaggerUIBundle.SwaggerUIStandalonePreset
                ],
                layout: "BaseLayout",
                deepLinking: true
            })
        </script>
    </body>
    </html>
    """


def generate_redoc_html():
    """Generate HTML for ReDoc."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>EDGECORE Trading System API - ReDoc</title>
        <meta charset="utf-8"/>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://fonts.googleapis.com/css?family=Montserrat:300,400,700|Roboto:300,400,700" rel="stylesheet">
        <style>
            body {
                margin: 0;
                padding: 0;
            }
        </style>
    </head>
    <body>
        <redoc spec-url='/api/openapi.json'></redoc>
        <script src="https://cdn.jsdelivr.net/npm/redoc@latest/bundles/redoc.standalone.js"></script>
    </body>
    </html>
    """
