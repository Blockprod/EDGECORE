"""EDGECORE — Web Dashboard API Server (standalone launcher).

Usage:
    python scripts/start_api_server.py [--port 5000] [--host 127.0.0.1]

Starts the Flask API server so the web dashboard is accessible at:
    http://127.0.0.1:5000/dashboard
"""

import argparse
import os
import sys
from pathlib import Path

# Ensure project root is on the path when running from any directory
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Set environment defaults if not already set
os.environ.setdefault("EDGECORE_ENV", "dev")
os.environ.setdefault("EDGECORE_MODE", "paper")


def main() -> None:
    parser = argparse.ArgumentParser(description="EDGECORE Web Dashboard API Server")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=5000, help="Bind port (default: 5000)")
    args = parser.parse_args()

    import structlog

    logger = structlog.get_logger("edgecore.dashboard_api")

    from monitoring.dashboard import DashboardGenerator
    from monitoring.api import initialize_dashboard_api, run_api_server

    mode = os.environ.get("EDGECORE_MODE", "paper")
    dashboard = DashboardGenerator(mode=mode, enable_live_bridge=True)
    initialize_dashboard_api(dashboard)

    logger.info(
        "starting_web_dashboard", host=args.host, port=args.port, url=f"http://{args.host}:{args.port}/dashboard"
    )
    print(f"\n  EDGECORE Web Dashboard → http://{args.host}:{args.port}/dashboard\n")

    run_api_server(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
