"""Models package — exposes CYTHON_AVAILABLE flag at startup (C-14)."""

import structlog as _structlog

_log = _structlog.get_logger(__name__)

try:
    import models.cointegration_fast  # noqa: F401

    CYTHON_AVAILABLE = True
    _log.info("cython_extensions_loaded", module="models.cointegration_fast")
except ImportError:
    CYTHON_AVAILABLE = False
    _log.warning(
        "cython_extensions_unavailable",
        impact="pair_discovery 5-10x slower, half_life 10x slower",
        fix=r"venv\Scripts\python.exe setup.py build_ext --inplace",
    )
