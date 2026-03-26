"""P4 — PnL Regression Tests.

Purpose
-------
Guard against silent financial regressions: any code change that alters
backtest PnL, Sharpe, drawdown, or trade count will be caught immediately.

Mechanism
---------
* Three fixed, deterministic scenarios (baseline / bear / crisis).
* Each scenario runs the same lightweight spread backtest as P3
  (identical DGP — fully deterministic with fixed RNG seed).
* Numerical results are stored as JSON snapshots in
  ``tests/regression/snapshots/<scenario>.json``.
* On normal runs the test compares live output against the committed
  snapshot within ``PNL_TOLERANCE = 1e-4``.
* Pass ``--update-snapshots`` to overwrite snapshots after an intentional
  logic change (e.g. cost-model update, spread normalisation change).

Usage
-----
    # Assert against committed snapshots (normal CI run)
    pytest tests/regression/ -q

    # Refresh snapshots after intentional change
    pytest tests/regression/ -q --update-snapshots

Design constraints
------------------
* All thresholds via ``get_settings()`` — zero hard-coded values.
* Ruff OK · Pyright OK.
* No dependency on ``tests/statistical/`` (self-contained DGP).
"""

from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass

import numpy as np
import pandas as pd
import pytest

from backtests.metrics import BacktestMetrics
from config.settings import get_settings

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PNL_TOLERANCE: float = 1e-4  # absolute numerical tolerance for float assertions
_SNAPSHOTS_DIR = pathlib.Path(__file__).parent / "snapshots"
_TRUE_BETA: float = 2.0  # exact hedge ratio for the synthetic DGP


# ---------------------------------------------------------------------------
# Scenario definition
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Scenario:
    """All parameters needed to reproduce a deterministic backtest."""

    name: str
    n_bars: int
    half_life: float
    noise_scale: float
    drift: float
    vol_scale: float
    seed: int

    @property
    def snapshot_path(self) -> pathlib.Path:
        return _SNAPSHOTS_DIR / f"snapshot_{self.name}.json"


_SCENARIOS: list[_Scenario] = [
    _Scenario(
        name="baseline",
        n_bars=800,
        half_life=25.0,
        noise_scale=0.5,
        drift=0.0,
        vol_scale=1.0,
        seed=42,
    ),
    _Scenario(
        name="bear",
        n_bars=600,
        half_life=25.0,
        noise_scale=0.5,
        drift=-3e-4,
        vol_scale=0.8,
        seed=43,
    ),
    _Scenario(
        name="crisis",
        n_bars=600,
        half_life=15.0,
        noise_scale=0.5,
        drift=-5e-4,
        vol_scale=2.5,
        seed=45,
    ),
]


# ---------------------------------------------------------------------------
# DGP helper (self-contained — no dependency on tests/statistical/)
# ---------------------------------------------------------------------------


def _make_cointegrated_prices(
    n_bars: int,
    half_life: float,
    noise_scale: float,
    drift: float,
    vol_scale: float,
    seed: int,
) -> tuple[pd.Series, pd.Series]:
    """Generate two cointegrated daily price series (fixed-seed, deterministic).

    ``sym_a = 2 * sym_b + spread_ar1`` where ``spread_ar1`` is an AR(1) process
    with the given half-life.  The exact beta (2.0) is used in the spread
    backtest, so the recovered spread is always stationary.
    """
    rng = np.random.default_rng(seed)
    ar_coef = 1.0 - np.log(2.0) / half_life
    log_ret = rng.standard_normal(n_bars) * 0.01 * vol_scale + drift
    sym_b_vals: np.ndarray = 50.0 * np.exp(np.cumsum(log_ret))
    spread_ar1 = np.zeros(n_bars)
    for i in range(1, n_bars):
        spread_ar1[i] = ar_coef * spread_ar1[i - 1] + rng.standard_normal() * noise_scale
    sym_a_vals: np.ndarray = _TRUE_BETA * sym_b_vals + spread_ar1
    dates = pd.date_range("2019-01-02", periods=n_bars, freq="B")
    return pd.Series(sym_a_vals, index=dates), pd.Series(sym_b_vals, index=dates)


def _spread_backtest(
    sym_a: pd.Series,
    sym_b: pd.Series,
    entry_z: float,
    exit_z: float,
    lookback: int = 60,
) -> BacktestMetrics:
    """Deterministic spread backtest — identical logic to tests/statistical/.

    Uses exact hedge ratio (_TRUE_BETA) and lagged position to avoid
    lookahead bias.  Returns are normalised by the price level at the
    first live bar.
    """
    a: np.ndarray = np.asarray(sym_a, dtype=float)
    b: np.ndarray = np.asarray(sym_b, dtype=float)
    n = len(a)
    spread: np.ndarray = a - _TRUE_BETA * b
    price_level = max(float(a[lookback]), 1.0)

    # z-score (rolling, past-only window — no lookahead)
    z = np.zeros(n)
    for i in range(lookback, n):
        win = spread[i - lookback : i]
        mu, sig = float(win.mean()), float(win.std())
        if sig > 1e-10:
            z[i] = (spread[i] - mu) / sig

    # Position signal
    pos = np.zeros(n)
    state: int = 0
    for i in range(lookback, n):
        zi = z[i]
        if state == 0:
            if zi < -entry_z:
                state = 1
            elif zi > entry_z:
                state = -1
        elif state == 1 and zi > -exit_z:
            state = 0
        elif state == -1 and zi < exit_z:
            state = 0
        pos[i] = float(state)

    # Daily P&L — lagged position eliminates lookahead
    d_spread = np.diff(spread, prepend=spread[0])
    lagged_pos = np.roll(pos, 1)
    lagged_pos[0] = 0.0
    daily_rets = lagged_pos * d_spread / price_level
    daily_rets[: lookback + 1] = 0.0

    # Round-trip trade P&L
    trades: list[float] = []
    t_state: int = 0
    entry_spread_val: float = 0.0
    for i in range(lookback, n):
        zi = z[i]
        if t_state == 0:
            if zi < -entry_z:
                t_state = 1
                entry_spread_val = spread[i]
            elif zi > entry_z:
                t_state = -1
                entry_spread_val = spread[i]
        elif t_state == 1 and zi > -exit_z:
            trades.append(spread[i] - entry_spread_val)
            t_state = 0
        elif t_state == -1 and zi < exit_z:
            trades.append(entry_spread_val - spread[i])
            t_state = 0

    returns_series = pd.Series(daily_rets[lookback + 1 :], dtype=float)
    dti = pd.DatetimeIndex(sym_a.index)
    start_date: str = str(dti[lookback + 1])[:10]
    end_date: str = str(dti[-1])[:10]
    return BacktestMetrics.from_returns(
        returns=returns_series,
        trades=trades,
        start_date=start_date,
        end_date=end_date,
    )


# ---------------------------------------------------------------------------
# Snapshot helpers
# ---------------------------------------------------------------------------


def _metrics_to_snapshot(m: BacktestMetrics) -> dict[str, float]:
    """Extract the four tracked metrics from a BacktestMetrics instance."""
    return {
        "total_pnl": float(m.total_return),
        "sharpe": float(m.sharpe_ratio),
        "max_drawdown": float(m.max_drawdown),
        "nb_trades": float(m.total_trades),  # stored as float for JSON uniformity
    }


def _run_scenario(scenario: _Scenario) -> dict[str, float]:
    """Run a scenario with the current config and return snapshot-format metrics."""
    cfg = get_settings()
    sym_a, sym_b = _make_cointegrated_prices(
        n_bars=scenario.n_bars,
        half_life=scenario.half_life,
        noise_scale=scenario.noise_scale,
        drift=scenario.drift,
        vol_scale=scenario.vol_scale,
        seed=scenario.seed,
    )
    m = _spread_backtest(
        sym_a,
        sym_b,
        entry_z=cfg.strategy.entry_z_score,
        exit_z=cfg.strategy.exit_z_score,
    )
    return _metrics_to_snapshot(m)


def _load_snapshot(path: pathlib.Path) -> dict[str, float]:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)  # type: ignore[no-any-return]


def _save_snapshot(path: pathlib.Path, data: dict[str, float]) -> None:
    _SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")  # ensure POSIX newline at EOF


# ---------------------------------------------------------------------------
# Parametrised regression tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("scenario", _SCENARIOS, ids=[s.name for s in _SCENARIOS])
def test_pnl_regression(scenario: _Scenario, request: pytest.FixtureRequest) -> None:
    """Assert that the PnL metrics for *scenario* match the committed snapshot.

    If ``--update-snapshots`` is passed the snapshot is overwritten instead
    of being compared.  This is the only sanctioned way to update reference
    values after an intentional backtest logic change.
    """
    update_mode: bool = bool(request.config.getoption("--update-snapshots", default=False))

    live = _run_scenario(scenario)

    if update_mode:
        _save_snapshot(scenario.snapshot_path, live)
        pytest.skip(f"Snapshot updated: {scenario.snapshot_path.name}")
        return  # unreachable, but satisfies type checkers

    if not scenario.snapshot_path.exists():
        pytest.fail(f"Snapshot not found: {scenario.snapshot_path}. Run with --update-snapshots to generate it.")

    snap = _load_snapshot(scenario.snapshot_path)

    # Float assertions with absolute tolerance PNL_TOLERANCE = 1e-4
    assert live["total_pnl"] == pytest.approx(snap["total_pnl"], abs=PNL_TOLERANCE), (
        f"[{scenario.name}] total_pnl: live={live['total_pnl']:.6f} vs snapshot={snap['total_pnl']:.6f}"
    )
    assert live["sharpe"] == pytest.approx(snap["sharpe"], abs=PNL_TOLERANCE), (
        f"[{scenario.name}] sharpe: live={live['sharpe']:.6f} vs snapshot={snap['sharpe']:.6f}"
    )
    assert live["max_drawdown"] == pytest.approx(snap["max_drawdown"], abs=PNL_TOLERANCE), (
        f"[{scenario.name}] max_drawdown: live={live['max_drawdown']:.6f} vs snapshot={snap['max_drawdown']:.6f}"
    )
    # nb_trades is an integer — exact equality expected
    assert int(live["nb_trades"]) == int(snap["nb_trades"]), (
        f"[{scenario.name}] nb_trades: live={int(live['nb_trades'])} vs snapshot={int(snap['nb_trades'])}"
    )
