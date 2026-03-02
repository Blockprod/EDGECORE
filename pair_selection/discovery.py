"""
Pair Discovery Engine — Cointegration-based pair screening.

Encapsulates the full pair discovery pipeline:
    1. Pre-filter candidates (correlation, data quality)
    2. Engle-Granger cointegration test
    3. Bonferroni correction for multiple testing
    4. Johansen confirmation (optional double-screen)
    5. Newey-West HAC consensus (optional)
    6. Half-life filtering
    7. Cache management

Delegates to existing statistical implementations in ``models/``
while providing a clean, composable API for the modular architecture.
"""

from __future__ import annotations

import pickle
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from multiprocessing import cpu_count
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from structlog import get_logger

from models.cointegration import (
    engle_granger_test,
    half_life_mean_reversion,
    newey_west_consensus as _nw_consensus,
)
from models.johansen import JohansenCointegrationTest

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class CointegratedPair:
    """Result of a successful cointegration screen."""
    symbol_1: str
    symbol_2: str
    pvalue: float
    half_life: float
    correlation: float = 0.0
    johansen_confirmed: bool = False
    nw_consensus: bool = False
    discovery_time: datetime = field(default_factory=datetime.now)

    @property
    def pair_key(self) -> str:
        return f"{self.symbol_1}_{self.symbol_2}"

    def as_tuple(self) -> Tuple[str, str, float, float]:
        """Legacy tuple format for backward compatibility."""
        return (self.symbol_1, self.symbol_2, self.pvalue, self.half_life)


@dataclass
class DiscoveryConfig:
    """Configuration for pair discovery."""
    min_correlation: float = 0.7
    max_half_life: int = 60
    lookback_window: int = 252
    bonferroni_correction: bool = True
    significance_level: float = 0.05
    johansen_confirmation: bool = True
    newey_west_consensus: bool = True
    cache_dir: str = "cache/pairs"
    cache_ttl_hours: int = 12
    num_workers: Optional[int] = None


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class PairDiscoveryEngine:
    """
    Orchestrates cointegration-based pair discovery.

    This engine is the **single entry point** for pair screening.
    It wraps the proven statistical tests in ``models/cointegration``
    and ``models/johansen`` behind a clean API that the rest of the
    system (backtester, live runner) consumes.

    Usage::

        engine = PairDiscoveryEngine()
        pairs = engine.discover(
            price_data=prices_df,
            candidate_pairs=[("AAPL", "MSFT"), ("JPM", "BAC"), ...],
        )
        for p in pairs:
            print(p.pair_key, p.half_life)
    """

    def __init__(self, config: Optional[DiscoveryConfig] = None):
        self.config = config or DiscoveryConfig()
        self._cache_dir = Path(self.config.cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._johansen = JohansenCointegrationTest() if self.config.johansen_confirmation else None

        logger.info(
            "pair_discovery_engine_initialized",
            lookback=self.config.lookback_window,
            bonferroni=self.config.bonferroni_correction,
            johansen=self.config.johansen_confirmation,
            nw_consensus=self.config.newey_west_consensus,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def discover(
        self,
        price_data: pd.DataFrame,
        candidate_pairs: Optional[List[Tuple[str, str]]] = None,
        use_cache: bool = True,
        lookback: Optional[int] = None,
    ) -> List[CointegratedPair]:
        """
        Run the full pair discovery pipeline.

        Args:
            price_data: DataFrame with symbols as columns, DatetimeIndex.
            candidate_pairs: Pre-screened pairs to test.  If *None*, all
                column combinations are tested.
            use_cache: Whether to check/write pair cache.
            lookback: Override lookback window.

        Returns:
            List of CointegratedPair results sorted by half-life.
        """
        lb = lookback or self.config.lookback_window

        # Cache check
        if use_cache:
            cached = self._load_cache()
            if cached is not None:
                return cached

        data = price_data.tail(lb)
        symbols = data.columns.tolist()

        # Generate pairs if not provided
        if candidate_pairs is None:
            candidate_pairs = [
                (symbols[i], symbols[j])
                for i in range(len(symbols))
                for j in range(i + 1, len(symbols))
            ]

        if not candidate_pairs:
            logger.warning("no_candidate_pairs")
            return []

        # Bonferroni-adjusted significance level
        n_tests = len(candidate_pairs)
        alpha = self.config.significance_level
        if self.config.bonferroni_correction and n_tests > 1:
            alpha = alpha / n_tests

        # Build test args
        args_list = [
            (s1, s2, data[s1], data[s2], alpha)
            for s1, s2 in candidate_pairs
            if s1 in data.columns and s2 in data.columns
        ]

        # Parallel execution
        n_workers = self.config.num_workers or max(1, cpu_count() - 1)
        logger.info(
            "pair_discovery_starting",
            candidates=len(args_list),
            workers=n_workers,
            bonferroni_alpha=f"{alpha:.2e}",
        )

        results: List[CointegratedPair] = []
        try:
            with ThreadPoolExecutor(max_workers=n_workers) as pool:
                raw = list(pool.map(self._test_single_pair, args_list))
            results = [r for r in raw if r is not None]
        except Exception as exc:
            logger.error("pair_discovery_failed", error=str(exc))
            return []

        # Sort by half-life (fastest mean-reversion first)
        results.sort(key=lambda p: p.half_life)

        logger.info(
            "pair_discovery_complete",
            discovered=len(results),
            tested=len(args_list),
        )

        # Persist cache
        if use_cache and results:
            self._save_cache(results)

        return results

    # ------------------------------------------------------------------
    # Internal: single-pair test
    # ------------------------------------------------------------------

    def _test_single_pair(
        self,
        args: Tuple,
    ) -> Optional[CointegratedPair]:
        """Test cointegration for one pair (worker function)."""
        sym1, sym2, series1, series2, alpha = args

        try:
            # Fast correlation pre-filter
            corr = float(series1.corr(series2))
            if abs(corr) < self.config.min_correlation:
                return None

            # Engle-Granger test
            eg = engle_granger_test(series1, series2)
            if not eg["is_cointegrated"]:
                return None
            if eg["adf_pvalue"] > alpha:
                return None

            # Half-life filter
            hl = half_life_mean_reversion(pd.Series(eg["residuals"]))
            if hl is None or hl <= 0 or hl > self.config.max_half_life:
                return None

            # Optional: Newey-West consensus
            nw_ok = True
            if self.config.newey_west_consensus:
                try:
                    nw = _nw_consensus(series1, series2)
                    nw_ok = nw.get("consensus", True)
                except Exception:
                    nw_ok = False  # fail-closed: broken robustness check rejects pair
            if not nw_ok:
                return None

            # Optional: Johansen confirmation
            joh_ok = True
            if self._johansen is not None:
                try:
                    jdf = pd.DataFrame({sym1: series1.values, sym2: series2.values})
                    jr = self._johansen.test(jdf)
                    joh_ok = jr.get("is_cointegrated", False)
                except Exception:
                    joh_ok = False  # fail-closed: broken confirmation check rejects pair

            # Johansen hard gate: reject pair if Johansen says no cointegration
            if self._johansen is not None and not joh_ok:
                return None

            return CointegratedPair(
                symbol_1=sym1,
                symbol_2=sym2,
                pvalue=eg["adf_pvalue"],
                half_life=hl,
                correlation=corr,
                johansen_confirmed=joh_ok,
                nw_consensus=nw_ok,
            )
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Cache helpers
    # ------------------------------------------------------------------

    def _cache_path(self) -> Path:
        return self._cache_dir / "discovered_pairs.json"

    def _load_cache(self) -> Optional[List[CointegratedPair]]:
        path = self._cache_path()
        if not path.exists():
            return None
        mod_time = datetime.fromtimestamp(path.stat().st_mtime)
        age = datetime.now() - mod_time
        if age > timedelta(hours=self.config.cache_ttl_hours):
            return None
        try:
            import json
            with open(path, "r") as f:
                raw = json.load(f)
            pairs = [
                CointegratedPair(
                    symbol_1=d["symbol_1"],
                    symbol_2=d["symbol_2"],
                    pvalue=d["pvalue"],
                    half_life=d["half_life"],
                    correlation=d.get("correlation", 0.0),
                    johansen_confirmed=d.get("johansen_confirmed", False),
                    nw_consensus=d.get("nw_consensus", False),
                )
                for d in raw
            ]
            logger.info("pair_cache_loaded", count=len(pairs), age_h=round(age.total_seconds() / 3600, 1))
            return pairs
        except Exception as exc:
            logger.warning("pair_cache_load_failed", error=str(exc))
            return None

    def _save_cache(self, pairs: List[CointegratedPair]) -> None:
        try:
            import json
            path = self._cache_path()
            tmp = path.with_suffix(".tmp")
            raw = [
                {
                    "symbol_1": p.symbol_1,
                    "symbol_2": p.symbol_2,
                    "pvalue": p.pvalue,
                    "half_life": p.half_life,
                    "correlation": p.correlation,
                    "johansen_confirmed": p.johansen_confirmed,
                    "nw_consensus": p.nw_consensus,
                }
                for p in pairs
            ]
            with open(tmp, "w") as f:
                json.dump(raw, f, indent=2)
            tmp.replace(path)
            logger.info("pair_cache_saved", count=len(pairs))
        except Exception as exc:
            logger.warning("pair_cache_save_failed", error=str(exc))

    def clear_cache(self) -> None:
        """Delete cached pair data."""
        import shutil
        if self._cache_dir.exists():
            shutil.rmtree(self._cache_dir)
            self._cache_dir.mkdir(parents=True, exist_ok=True)
            logger.info("pair_cache_cleared")
