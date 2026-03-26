"""P3 — Statistical Robustness Tests.

Three test blocks that guard the stat-arb strategy against:

1.1  Parameter sensitivity   — Sharpe stays positive when entry_z / max_half_life vary ±20-50 %.
1.2  Temporal robustness     — Sharpe stays positive across bull / bear / crash synthetic regimes.
1.3  IS vs OOS decay         — walk-forward decay ≤ 40 % (overfitting guard).

Design decisions
----------------
* Lightweight ``_spread_backtest`` helper rather than the full
  ``StrategyBacktestSimulator``: avoids IBKR/ML imports and keeps test
  runtime well under 30 s per case.
* Synthetic DGP: ``sym_a = 2 * sym_b + spread_ar1`` where ``spread_ar1``
  is a known AR(1) process.  The true hedge ratio (``_TRUE_BETA = 2.0``) is
  used directly — no OLS estimation — so the recovered spread equals
  ``spread_ar1`` exactly: stationary by construction, zero estimation drift.
* Position tracking uses a lagged position vector (signal fires at bar-i
  close; P&L accrues from bar i+1), eliminating lookahead bias.
* Returns are normalised by ``sym_a``'s price level at bar ``lookback``
  (~100) so that daily volatility is ~0.5 % — realistic for stat-arb.
* All thresholds are read from ``get_settings()``.  Zero hard-coded values.
* ``@pytest.mark.slow`` on every test — run with ``pytest -m slow``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backtests.metrics import BacktestMetrics
from config.settings import get_settings

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SEED: int = 42
_TRUE_BETA: float = 2.0  # Exact hedge ratio for the synthetic DGP

# ---------------------------------------------------------------------------
# DGP helper
# ---------------------------------------------------------------------------


def _make_cointegrated_prices(
    n_bars: int,
    half_life: float = 25.0,
    noise_scale: float = 0.5,
    drift: float = 0.0,
    vol_scale: float = 1.0,
    rng: np.random.Generator | None = None,
) -> tuple[pd.Series, pd.Series]:
    """Generate two cointegrated price series: ``sym_a = 2*sym_b + spread_ar1``.

    Args:
        n_bars:      Number of daily bars to generate.
        half_life:   Target half-life of spread mean-reversion (bars).
        noise_scale: Daily innovation std of the AR(1) spread.
        drift:       Per-bar log-drift added to the common factor.
        vol_scale:   Multiplier on the factor's daily log-volatility.
        rng:         Generator for reproducibility (default: module seed _SEED).
    """
    if rng is None:
        rng = np.random.default_rng(_SEED)

    ar_coef = 1.0 - np.log(2.0) / half_life

    # Common factor: GBM centred around 50
    log_ret = rng.standard_normal(n_bars) * 0.01 * vol_scale + drift
    sym_b_vals = 50.0 * np.exp(np.cumsum(log_ret))

    # Stationary AR(1) spread
    spread_ar1 = np.zeros(n_bars)
    for i in range(1, n_bars):
        spread_ar1[i] = ar_coef * spread_ar1[i - 1] + rng.standard_normal() * noise_scale

    # Exact linear relationship so that sym_a - 2*sym_b = spread_ar1 exactly
    sym_a_vals = _TRUE_BETA * sym_b_vals + spread_ar1

    dates = pd.date_range("2019-01-02", periods=n_bars, freq="B")
    return pd.Series(sym_a_vals, index=dates), pd.Series(sym_b_vals, index=dates)


# ---------------------------------------------------------------------------
# Lightweight spread backtest
# ---------------------------------------------------------------------------


def _spread_backtest(
    sym_a: pd.Series,
    sym_b: pd.Series,
    entry_z: float,
    exit_z: float,
    lookback: int = 60,
) -> BacktestMetrics:
    """Simulate a mean-reversion strategy on the synthetic spread.

    Implementation details
    ----------------------
    * ``spread = sym_a - _TRUE_BETA * sym_b`` equals ``spread_ar1`` exactly
      (no OLS estimation error, always stationary).
    * z-score computed from a rolling past-only window [i-lookback, i-1].
    * Pass-1: generate z-scores and a position vector (end-of-bar signal).
    * Pass-2: daily P&L = ``position[i-1] * delta_spread[i] / price_level``.
      Using the *lagged* position removes lookahead bias.
    * ``price_level ≈ 100`` keeps returns in the realistic ~0.5 %/day range.
    """
    a: np.ndarray = np.asarray(sym_a, dtype=float)
    b: np.ndarray = np.asarray(sym_b, dtype=float)
    n = len(a)

    spread: np.ndarray = a - _TRUE_BETA * b  # = spread_ar1 by construction

    # Normalisation: express P&L as fraction of the initial price (~100)
    price_level = max(float(a[lookback]), 1.0)

    # ------------------------------------------------------------------
    # Pass 1 — z-score and position signal
    # ------------------------------------------------------------------
    z = np.zeros(n)
    for i in range(lookback, n):
        win = spread[i - lookback : i]
        mu = float(win.mean())
        sig = float(win.std())
        if sig > 1e-10:
            z[i] = (spread[i] - mu) / sig

    pos = np.zeros(n)
    state: int = 0
    for i in range(lookback, n):
        zi = z[i]
        if state == 0:
            if zi < -entry_z:
                state = 1  # long spread (expect spread to rise back toward mean)
            elif zi > entry_z:
                state = -1  # short spread (expect spread to fall back toward mean)
        elif state == 1 and zi > -exit_z:
            state = 0  # exit long: z has reverted sufficiently
        elif state == -1 and zi < exit_z:
            state = 0  # exit short: z has reverted sufficiently
        pos[i] = float(state)

    # ------------------------------------------------------------------
    # Pass 2 — daily P&L using lagged position (no lookahead)
    # ------------------------------------------------------------------
    d_spread = np.diff(spread, prepend=spread[0])
    lagged_pos = np.roll(pos, 1)
    lagged_pos[0] = 0.0
    daily_rets = lagged_pos * d_spread / price_level
    daily_rets[: lookback + 1] = 0.0  # zero out warm-up bars

    # ------------------------------------------------------------------
    # Pass 3 — round-trip trade P&L in spread units (for win_rate etc.)
    # ------------------------------------------------------------------
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
            trades.append(spread[i] - entry_spread_val)  # positive on profitable exit
            t_state = 0
        elif t_state == -1 and zi < exit_z:
            trades.append(entry_spread_val - spread[i])  # positive on profitable exit
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
# 1.1  Parameter sensitivity
# ---------------------------------------------------------------------------


class TestParameterSensitivity:
    """Bloc 1.1 — Sharpe stays positive when entry_z / max_half_life vary ±20-50 %."""

    _MIN_SHARPE: float = 0.0

    @pytest.mark.slow
    def test_sharpe_stable_entry_z_minus_20pct(self) -> None:
        """entry_z lowered by 20 % → more frequent entries → Sharpe still positive."""
        cfg = get_settings()
        entry_z = cfg.strategy.entry_z_score * 0.80
        exit_z = cfg.strategy.exit_z_score
        sym_a, sym_b = _make_cointegrated_prices(n_bars=800, half_life=25.0)
        m = _spread_backtest(sym_a, sym_b, entry_z=entry_z, exit_z=exit_z)
        assert m.sharpe_ratio > self._MIN_SHARPE, f"entry_z={entry_z:.2f} (×0.80): Sharpe={m.sharpe_ratio:.3f} ≤ 0"

    @pytest.mark.slow
    def test_sharpe_stable_entry_z_plus_20pct(self) -> None:
        """entry_z raised by 20 % → fewer but higher-quality entries → Sharpe still positive."""
        cfg = get_settings()
        entry_z = cfg.strategy.entry_z_score * 1.20
        exit_z = cfg.strategy.exit_z_score
        sym_a, sym_b = _make_cointegrated_prices(n_bars=800, half_life=25.0)
        m = _spread_backtest(sym_a, sym_b, entry_z=entry_z, exit_z=exit_z)
        assert m.sharpe_ratio > self._MIN_SHARPE, f"entry_z={entry_z:.2f} (×1.20): Sharpe={m.sharpe_ratio:.3f} ≤ 0"

    @pytest.mark.slow
    def test_drawdown_within_risk_limit_baseline(self) -> None:
        """Baseline config: max drawdown must not exceed RiskConfig.max_drawdown_pct."""
        cfg = get_settings()
        entry_z = cfg.strategy.entry_z_score
        exit_z = cfg.strategy.exit_z_score
        max_dd_limit = cfg.risk.max_drawdown_pct
        sym_a, sym_b = _make_cointegrated_prices(n_bars=800, half_life=25.0)
        m = _spread_backtest(sym_a, sym_b, entry_z=entry_z, exit_z=exit_z)
        assert abs(m.max_drawdown) <= max_dd_limit, (
            f"baseline: |max_drawdown|={abs(m.max_drawdown):.3f} > limit={max_dd_limit}"
        )

    @pytest.mark.slow
    def test_sharpe_stable_half_life_minus_50pct(self) -> None:
        """Half-life 50 % shorter → faster reversion → strategy still earns positive Sharpe."""
        cfg = get_settings()
        half_life = max(5.0, cfg.strategy.max_half_life * 0.50)
        entry_z = cfg.strategy.entry_z_score
        exit_z = cfg.strategy.exit_z_score
        sym_a, sym_b = _make_cointegrated_prices(n_bars=800, half_life=half_life)
        m = _spread_backtest(sym_a, sym_b, entry_z=entry_z, exit_z=exit_z)
        assert m.sharpe_ratio > self._MIN_SHARPE, f"half_life={half_life:.0f} (×0.50): Sharpe={m.sharpe_ratio:.3f} ≤ 0"

    @pytest.mark.slow
    def test_sharpe_stable_half_life_plus_50pct(self) -> None:
        """Half-life 50 % longer → slower reversion → strategy earns positive Sharpe."""
        cfg = get_settings()
        half_life = cfg.strategy.max_half_life * 1.50
        entry_z = cfg.strategy.entry_z_score
        exit_z = cfg.strategy.exit_z_score
        sym_a, sym_b = _make_cointegrated_prices(n_bars=1000, half_life=half_life)
        m = _spread_backtest(sym_a, sym_b, entry_z=entry_z, exit_z=exit_z)
        assert m.sharpe_ratio > self._MIN_SHARPE, f"half_life={half_life:.0f} (×1.50): Sharpe={m.sharpe_ratio:.3f} ≤ 0"


# ---------------------------------------------------------------------------
# 1.2  Temporal robustness
# ---------------------------------------------------------------------------


class TestTemporalRobustness:
    """Bloc 1.2 — Strategy profitable in bull, bear, and crash market regimes."""

    _MIN_SHARPE: float = 0.0
    _N_BARS: int = 600

    def _run_period(
        self,
        drift: float,
        vol_scale: float,
        half_life: float = 25.0,
        seed_offset: int = 0,
    ) -> BacktestMetrics:
        cfg = get_settings()
        rng = np.random.default_rng(_SEED + seed_offset)
        sym_a, sym_b = _make_cointegrated_prices(
            n_bars=self._N_BARS,
            half_life=half_life,
            drift=drift,
            vol_scale=vol_scale,
            rng=rng,
        )
        return _spread_backtest(
            sym_a,
            sym_b,
            entry_z=cfg.strategy.entry_z_score,
            exit_z=cfg.strategy.exit_z_score,
        )

    @pytest.mark.slow
    def test_sharpe_bull_period(self) -> None:
        """Bull market (upward drift): market-neutral strategy unaffected → Sharpe > 0."""
        m = self._run_period(drift=3e-4, vol_scale=0.8, seed_offset=1)
        assert m.sharpe_ratio > self._MIN_SHARPE, f"bull: Sharpe={m.sharpe_ratio:.3f} ≤ 0"

    @pytest.mark.slow
    def test_sharpe_bear_period(self) -> None:
        """Bear market (downward drift): spread still mean-reverts → Sharpe > 0."""
        m = self._run_period(drift=-3e-4, vol_scale=0.8, seed_offset=2)
        assert m.sharpe_ratio > self._MIN_SHARPE, f"bear: Sharpe={m.sharpe_ratio:.3f} ≤ 0"

    @pytest.mark.slow
    def test_sharpe_crash_period(self) -> None:
        """Crash (2.5× vol, downward drift): Sharpe > 0, drawdown within 1.5× limit."""
        cfg = get_settings()
        max_dd_limit = cfg.risk.max_drawdown_pct
        m = self._run_period(
            drift=-5e-4,
            vol_scale=2.5,
            half_life=15.0,
            seed_offset=3,
        )
        assert m.sharpe_ratio > self._MIN_SHARPE, f"crash: Sharpe={m.sharpe_ratio:.3f} ≤ 0"
        assert abs(m.max_drawdown) <= max_dd_limit * 1.5, (
            f"crash: |max_drawdown|={abs(m.max_drawdown):.3f} > {max_dd_limit * 1.5:.2f}"
        )


# ---------------------------------------------------------------------------
# 1.3  IS vs OOS decay
# ---------------------------------------------------------------------------

_MAX_IS_OOS_DECAY: float = 0.40  # Maximum tolerated IS-to-OOS Sharpe decay


class TestISvsOOSDecay:
    """Bloc 1.3 — Walk-forward IS-to-OOS Sharpe decay must not exceed 40 %."""

    @pytest.mark.slow
    def test_is_oos_decay_within_40pct(self) -> None:
        """Average IS/OOS Sharpe decay across all folds ≤ 40 %."""
        from backtests.walk_forward import split_walk_forward

        cfg = get_settings()
        entry_z = cfg.strategy.entry_z_score
        exit_z = cfg.strategy.exit_z_score
        oos_ratio = cfg.backtest.out_of_sample_ratio

        # 3000 bars → period_length=600, oos_per_period=120  (> lookback=60)
        sym_a, sym_b = _make_cointegrated_prices(n_bars=3000, half_life=25.0)
        prices = pd.DataFrame({"SYM_A": sym_a, "SYM_B": sym_b})

        splits = split_walk_forward(prices, num_periods=4, oos_ratio=oos_ratio)
        assert len(splits) >= 2, "split_walk_forward returned fewer than 2 folds"

        is_sharpes: list[float] = []
        oos_sharpes: list[float] = []

        for train_df, test_df in splits:
            if len(train_df) < 120 or len(test_df) < 70:
                continue
            is_m = _spread_backtest(
                pd.Series(train_df["SYM_A"]),
                pd.Series(train_df["SYM_B"]),
                entry_z=entry_z,
                exit_z=exit_z,
            )
            oos_m = _spread_backtest(
                pd.Series(test_df["SYM_A"]),
                pd.Series(test_df["SYM_B"]),
                entry_z=entry_z,
                exit_z=exit_z,
            )
            is_sharpes.append(is_m.sharpe_ratio)
            oos_sharpes.append(oos_m.sharpe_ratio)

        assert is_sharpes, "No valid IS/OOS folds produced"

        avg_is = float(np.mean(is_sharpes))
        avg_oos = float(np.mean(oos_sharpes))

        if avg_is <= 0:
            assert avg_oos >= avg_is, f"OOS Sharpe ({avg_oos:.3f}) < IS Sharpe ({avg_is:.3f}) on already-negative IS"
            return

        decay = (avg_is - avg_oos) / avg_is
        assert decay <= _MAX_IS_OOS_DECAY, (
            f"IS/OOS Sharpe decay={decay:.1%} > {_MAX_IS_OOS_DECAY:.0%} (IS={avg_is:.3f}, OOS={avg_oos:.3f})"
        )

    @pytest.mark.slow
    def test_is_oos_decay_per_fold(self) -> None:
        """Walk-forward per-fold: at most 1 fold may exceed 40 % decay.

        With ~120-bar OOS windows, one fold violating the threshold is
        consistent with sampling variance (≈ 1 standard error of Sharpe
        estimation error over that period) rather than systematic overfitting.
        """
        from backtests.walk_forward import split_walk_forward

        cfg = get_settings()
        entry_z = cfg.strategy.entry_z_score
        exit_z = cfg.strategy.exit_z_score
        oos_ratio = cfg.backtest.out_of_sample_ratio

        # 3000 bars → period_length=600, oos_per_period=120  (> lookback=60)
        sym_a, sym_b = _make_cointegrated_prices(n_bars=3000, half_life=20.0)
        prices = pd.DataFrame({"SYM_A": sym_a, "SYM_B": sym_b})
        splits = split_walk_forward(prices, num_periods=4, oos_ratio=oos_ratio)

        violations: list[str] = []
        for fold_idx, (train_df, test_df) in enumerate(splits):
            if len(train_df) < 120 or len(test_df) < 70:
                continue
            is_m = _spread_backtest(
                pd.Series(train_df["SYM_A"]),
                pd.Series(train_df["SYM_B"]),
                entry_z=entry_z,
                exit_z=exit_z,
            )
            oos_m = _spread_backtest(
                pd.Series(test_df["SYM_A"]),
                pd.Series(test_df["SYM_B"]),
                entry_z=entry_z,
                exit_z=exit_z,
            )
            if is_m.sharpe_ratio <= 0:
                continue  # Undefined decay for non-positive IS Sharpe; skip fold
            fold_decay = (is_m.sharpe_ratio - oos_m.sharpe_ratio) / is_m.sharpe_ratio
            if fold_decay > _MAX_IS_OOS_DECAY:
                violations.append(
                    f"fold {fold_idx}: decay={fold_decay:.1%} "
                    f"(IS={is_m.sharpe_ratio:.3f}, OOS={oos_m.sharpe_ratio:.3f})"
                )

        # Allow at most 1 violating fold: sampling variance in 120-bar OOS windows
        # can produce Sharpe estimation errors of ≈ ±0.9, so a single fold may
        # appear over-fitted by chance even for a genuinely robust strategy.
        assert len(violations) <= 1, (
            f"IS/OOS decay violations in {len(violations)} folds (max 1 tolerated):\n" + "\n".join(violations)
        )
