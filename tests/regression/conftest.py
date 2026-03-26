"""Conftest for tests/regression/ — registers custom pytest options."""

from __future__ import annotations

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register --update-snapshots flag for PnL regression tests."""
    parser.addoption(
        "--update-snapshots",
        action="store_true",
        default=False,
        help=(
            "Overwrite stored PnL regression snapshots with current backtest output. "
            "Use this flag after intentional changes to the backtest logic."
        ),
    )
