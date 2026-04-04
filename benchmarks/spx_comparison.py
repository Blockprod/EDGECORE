"""
benchmarks/spx_comparison.py — EDGECORE vs S&P 500 (SPY) comparison.

Loads SPY daily data from data/cache/SPY_1d.parquet (written by the cache-first
loader in data/loader.py — C-02).  Falls back to a synthetic SPY DataFrame built
from bt_v36 period dates when the cache file is absent so the script is always
runnable offline.

Computes SPY metrics over the same trading period as bt_v36_output.json, then
writes benchmarks/results/comparison_YYYY-MM-DD.json.

Usage
-----
    venv/Scripts/python.exe benchmarks/spx_comparison.py
"""

from __future__ import annotations

import json
import math
from datetime import UTC, date, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import structlog

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).parent.parent
CACHE_DIR = ROOT / "data" / "cache"
RESULTS_DIR = ROOT / "results"
BENCHMARK_RESULTS_DIR = ROOT / "benchmarks" / "results"
EDGECORE_BASELINE_PATH = RESULTS_DIR / "bt_v36_output.json"


# ---------------------------------------------------------------------------
# Metrics helpers
# ---------------------------------------------------------------------------


def _annualised_sharpe(returns: pd.Series, trading_days: int = 252) -> float:
    """Annualised Sharpe (risk-free rate = 0)."""
    if returns.std(ddof=1) == 0:
        return 0.0
    return float(returns.mean() / returns.std(ddof=1) * math.sqrt(trading_days))


def _max_drawdown(equity: pd.Series) -> float:
    """Maximum drawdown as a negative percentage (e.g. -0.25 for -25%)."""
    roll_max = equity.cummax()
    drawdown = (equity - roll_max) / roll_max
    return float(drawdown.min())


def _cagr(equity: pd.Series, trading_days: int = 252) -> float:
    """Compound annual growth rate."""
    if len(equity) < 2 or equity.iloc[0] == 0:
        return 0.0
    years = len(equity) / trading_days
    return float((equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1)


def compute_metrics(equity: pd.Series, trading_days: int = 252) -> dict:
    """Compute Sharpe, max_dd, CAGR, total_return from an equity curve."""
    returns = equity.pct_change().dropna()
    return {
        "sharpe": round(_annualised_sharpe(returns, trading_days), 4),
        "max_dd_pct": round(_max_drawdown(equity) * 100, 4),
        "cagr_pct": round(_cagr(equity, trading_days) * 100, 4),
        "total_return_pct": round((equity.iloc[-1] / equity.iloc[0] - 1) * 100, 4) if equity.iloc[0] != 0 else 0.0,
        "num_days": len(equity),
    }


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def _load_spy_from_cache(start: str, end: str) -> pd.Series | None:
    """Try to load SPY close prices from the parquet cache.  Returns None if absent."""
    path = CACHE_DIR / "SPY_1d.parquet"
    if not path.exists():
        logger.warning("spy_cache_not_found", path=str(path))
        return None

    try:
        df = pd.read_parquet(path)
        # Normalise column name (cache may store 'close' or 'Close' or 'SPY')
        close_col = None
        for candidate in ["close", "Close", "SPY", "Adj Close", "adj_close"]:
            if candidate in df.columns:
                close_col = candidate
                break
        if close_col is None:
            # Take first numeric column
            numeric_cols = df.select_dtypes(include="number").columns
            if len(numeric_cols) == 0:
                logger.warning("spy_cache_no_numeric_column")
                return None
            close_col = numeric_cols[0]

        series = df[close_col].dropna()
        if not isinstance(series.index, pd.DatetimeIndex):
            series.index = pd.to_datetime(series.index)
        series = series.sort_index()
        series = series.loc[start:end]
        logger.info("spy_loaded_from_cache", rows=len(series), close_col=close_col)
        return series
    except Exception as exc:
        logger.warning("spy_cache_load_error", error=str(exc))
        return None


def _synthetic_spy(start: str, end: str) -> pd.Series:
    """
    Build a synthetic SPY equity curve when cache is unavailable.

    Uses historical SPY annualised Sharpe ~0.72, CAGR ~10.4% (2018-2026 period)
    via a GBM with seed=42 for reproducibility.
    """
    logger.warning("spy_using_synthetic_data", reason="cache not available")
    rng = np.random.default_rng(42)
    dates = pd.bdate_range(start=start, end=end)
    drift = 0.104 / 252  # ~10.4% annualised
    vol = 0.16 / math.sqrt(252)  # ~16% annualised vol
    daily_returns = rng.normal(drift, vol, len(dates))
    equity = 100.0 * np.cumprod(1 + daily_returns)
    return pd.Series(equity, index=dates, name="SPY_synthetic")


# ---------------------------------------------------------------------------
# Main comparison
# ---------------------------------------------------------------------------


def run_comparison(output_path: Path | None = None) -> dict:
    """Run SPY vs EDGECORE comparison and write JSON result."""
    # --- Load EDGECORE baseline ---
    if not EDGECORE_BASELINE_PATH.exists():
        raise FileNotFoundError(f"Baseline not found: {EDGECORE_BASELINE_PATH}")

    with EDGECORE_BASELINE_PATH.open(encoding="utf-8") as f:
        baseline = json.load(f)

    ec_metrics = baseline["metrics"]
    start_date = baseline.get("start_date", "2018-01-01")
    end_date = baseline.get("end_date", "2026-01-01")

    # --- Load SPY ---
    spy_series = _load_spy_from_cache(start_date, end_date)
    if spy_series is None or len(spy_series) < 10:
        spy_series = _synthetic_spy(start_date, end_date)
        data_source = "synthetic"
    else:
        data_source = "cache"

    spy_metrics_raw = compute_metrics(spy_series)

    # --- Build comparison table ---
    edgecore_entry = {
        "sharpe": ec_metrics.get("sharpe"),
        "max_dd_pct": ec_metrics.get("max_dd"),
        "cagr_pct": ec_metrics.get("return_pct"),
        "win_rate_pct": ec_metrics.get("win_rate"),
        "profit_factor": ec_metrics.get("pf"),
        "trades": ec_metrics.get("trades"),
        "calmar": ec_metrics.get("calmar"),
    }
    spy_entry = {
        "sharpe": spy_metrics_raw["sharpe"],
        "max_dd_pct": spy_metrics_raw["max_dd_pct"],
        "cagr_pct": spy_metrics_raw["cagr_pct"],
        "total_return_pct": spy_metrics_raw["total_return_pct"],
        "num_days": spy_metrics_raw["num_days"],
        "data_source": data_source,
    }

    # Alpha over SPY (Sharpe lift)
    sharpe_alpha = (
        round(edgecore_entry["sharpe"] - spy_entry["sharpe"], 4)
        if None not in (edgecore_entry["sharpe"], spy_entry["sharpe"])
        else None
    )

    result = {
        "generated_at": datetime.now(UTC).isoformat(),
        "period": {"start": start_date, "end": end_date},
        "edgecore_version": baseline.get("version", "v36"),
        "comparison": {
            "edgecore": edgecore_entry,
            "spy": spy_entry,
            "sharpe_alpha_vs_spy": sharpe_alpha,
        },
        "interpretation": _interpret(edgecore_entry, spy_entry, sharpe_alpha),
    }

    # --- Write output ---
    BENCHMARK_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    if output_path is None:
        output_path = BENCHMARK_RESULTS_DIR / f"comparison_{today}.json"

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    logger.info("comparison_written", path=str(output_path))
    print(f"\n{'=' * 60}")
    print(f"EDGECORE v{result['edgecore_version']} vs SPY — {start_date} → {end_date}")
    print(f"{'=' * 60}")
    print(f"{'Metric':<25} {'EDGECORE':>10} {'SPY':>10}")
    print(f"{'-' * 47}")
    print(f"{'Sharpe (annualised)':<25} {edgecore_entry['sharpe']:>10.2f} {spy_entry['sharpe']:>10.2f}")
    print(f"{'Max Drawdown (%)':<25} {str(edgecore_entry['max_dd_pct']):>10} {spy_entry['max_dd_pct']:>10.2f}")
    print(f"{'CAGR / Return (%)':<25} {str(edgecore_entry['cagr_pct']):>10} {spy_entry['cagr_pct']:>10.2f}")
    print(f"{'Sharpe alpha vs SPY':<25} {str(sharpe_alpha):>10}")
    print(f"{'=' * 60}")
    print(f"Output: {output_path}")
    print()
    return result


def _interpret(_ec: dict, _spy: dict, sharpe_alpha: float | None) -> str:
    if sharpe_alpha is None:
        return "Unable to compute alpha — missing metrics."
    if sharpe_alpha > 0.5:
        return (
            f"EDGECORE significantly outperforms SPY on a risk-adjusted basis "
            f"(Sharpe alpha = +{sharpe_alpha:.2f}). Strategy provides genuine alpha."
        )
    elif sharpe_alpha > 0.0:
        return (
            f"EDGECORE modestly outperforms SPY (Sharpe alpha = +{sharpe_alpha:.2f}). "
            f"Market-neutral positioning validates stat-arb alpha generation."
        )
    else:
        return (
            f"EDGECORE underperforms SPY on Sharpe basis (alpha = {sharpe_alpha:.2f}). "
            f"Strategy parameter review recommended."
        )


if __name__ == "__main__":
    run_comparison()
