<<<<<<< HEAD
﻿#!/usr/bin/env python
=======
#!/usr/bin/env python
>>>>>>> origin/main
"""
Symbol Universe Scoring Pipeline
=================================
Data-driven selection of the optimal pair trading universe.

Methodology (institutional standard):
1. Load historical data for ALL candidate symbols from IBKR
2. For each rolling window (252d, step 5d), test all intra-sector pairs
3. Score each symbol on 4 axes:
<<<<<<< HEAD
   a) Cointegration Frequency ÔÇö how often it appears in a cointegrated pair
   b) p-Value Quality ÔÇö average Engle-Granger p-value of its best pairs
   c) Half-Life Stability ÔÇö mean & stdev of half-lives across windows
   d) Pair Diversity ÔÇö how many DISTINCT partners it cointegrates with
4. Composite score ÔåÆ rank ÔåÆ select top N per sector
=======
   a) Cointegration Frequency — how often it appears in a cointegrated pair
   b) p-Value Quality — average Engle-Granger p-value of its best pairs
   c) Half-Life Stability — mean & stdev of half-lives across windows
   d) Pair Diversity — how many DISTINCT partners it cointegrates with
4. Composite score → rank → select top N per sector
>>>>>>> origin/main

Output: Ranked table per sector with recommended symbols.

Usage:
    python scripts/score_universe.py
"""

import sys
import os
<<<<<<< HEAD

=======
>>>>>>> origin/main
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from collections import defaultdict
<<<<<<< HEAD
from typing import Any
=======
from typing import Dict, List, Tuple
>>>>>>> origin/main
from structlog import get_logger
from data.loader import DataLoader
from data.validators import DataValidationError
from models.cointegration import engle_granger_test, half_life_mean_reversion

logger = get_logger(__name__)


<<<<<<< HEAD
# ÔöÇÔöÇ Full candidate universe (53 symbols across 8 sectors) ÔöÇÔöÇ
CANDIDATES = {
    "Tech": [
        "AAPL",
        "MSFT",
        "GOOGL",
        "META",
        "NVDA",
        "AMD",
        "INTC",
        "AVGO",
        "CRM",
        "ADBE",
    ],
    "Financials": [
        "JPM",
        "GS",
        "BAC",
        "MS",
        "WFC",
        "C",
        "BLK",
        "SCHW",
    ],
    "Healthcare": [
        "JNJ",
        "PFE",
        "UNH",
        "MRK",
        "ABBV",
        "LLY",
        "TMO",
        "ABT",
    ],
    "Consumer": [
        "KO",
        "PEP",
        "PG",
        "CL",
        "WMT",
        "COST",
    ],
    "Energy": [
        "XOM",
        "CVX",
        "COP",
        "SLB",
        "EOG",
    ],
    "Industrials": [
        "CAT",
        "DE",
        "HON",
        "GE",
        "RTX",
        "LMT",
    ],
    "Utilities": [
        "NEE",
        "DUK",
        "SO",
        "D",
    ],
    "REITs": [
        "PLD",
        "AMT",
        "SPG",
=======
# ── Full candidate universe (53 symbols across 8 sectors) ──
CANDIDATES = {
    "Tech": [
        "AAPL", "MSFT", "GOOGL", "META", "NVDA", "AMD",
        "INTC", "AVGO", "CRM", "ADBE",
    ],
    "Financials": [
        "JPM", "GS", "BAC", "MS", "WFC", "C", "BLK", "SCHW",
    ],
    "Healthcare": [
        "JNJ", "PFE", "UNH", "MRK", "ABBV", "LLY", "TMO", "ABT",
    ],
    "Consumer": [
        "KO", "PEP", "PG", "CL", "WMT", "COST",
    ],
    "Energy": [
        "XOM", "CVX", "COP", "SLB", "EOG",
    ],
    "Industrials": [
        "CAT", "DE", "HON", "GE", "RTX", "LMT",
    ],
    "Utilities": [
        "NEE", "DUK", "SO", "D",
    ],
    "REITs": [
        "PLD", "AMT", "SPG",
>>>>>>> origin/main
    ],
}


def load_all_data(
<<<<<<< HEAD
    candidates: dict[str, list[str]],
    start_date: str = "2019-06-01",  # buffer before 2020
    end_date: str = "2026-01-01",
) -> tuple[pd.DataFrame, list[str]]:
=======
    candidates: Dict[str, List[str]],
    start_date: str = "2019-06-01",  # buffer before 2020
    end_date: str = "2026-01-01",
) -> Tuple[pd.DataFrame, List[str]]:
>>>>>>> origin/main
    """Load close prices for all candidate symbols from IBKR."""
    loader = DataLoader()
    all_symbols = [s for syms in candidates.values() for s in syms]
    price_data = {}
    failed = []

    for sym in all_symbols:
        try:
            df = loader.load_ibkr_data(
<<<<<<< HEAD
                symbol=sym,
                timeframe="1d",
                since=start_date,
                limit=3000,
                validate=True,
=======
                symbol=sym, timeframe="1d",
                since=start_date, limit=3000, validate=True,
>>>>>>> origin/main
            )
            price_data[sym] = df["close"]
            print(f"  [OK] {sym}: {len(df)} rows")
        except (DataValidationError, Exception) as e:
            print(f"  [FAIL] {sym}: {e}")
            failed.append(sym)

    if not price_data:
        raise ValueError("No data loaded!")

    prices_df = pd.DataFrame(price_data)
    # Filter to requested date range
<<<<<<< HEAD
    prices_df = prices_df[(prices_df.index >= start_date) & (prices_df.index <= end_date)]
=======
    prices_df = prices_df[
        (prices_df.index >= start_date) & (prices_df.index <= end_date)
    ]
>>>>>>> origin/main
    print(f"\nLoaded {len(prices_df)} bars for {len(prices_df.columns)} symbols")
    if failed:
        print(f"Failed: {failed}")

    return prices_df, failed


def score_symbols(
    prices_df: pd.DataFrame,
<<<<<<< HEAD
    candidates: dict[str, list[str]],
    window: int = 252,
    step: int = 21,  # ~monthly steps (faster than daily)
=======
    candidates: Dict[str, List[str]],
    window: int = 252,
    step: int = 21,       # ~monthly steps (faster than daily)
>>>>>>> origin/main
    max_half_life: int = 120,
) -> pd.DataFrame:
    """
    Score each symbol by its pair-trading suitability.

    Returns DataFrame with columns:
        symbol, sector, coint_frequency, avg_pvalue, avg_half_life,
        hl_stability, n_distinct_partners, composite_score
    """
    available = set(prices_df.columns)
    n_bars = len(prices_df)

    # Per-symbol accumulators
<<<<<<< HEAD
    stats: dict[str, Any] = defaultdict(
        lambda: {
            "sector": "",
            "coint_count": 0,  # how many (window, partner) pairs are cointegrated
            "total_tests": 0,  # total pair tests involving this symbol
            "pvalues": [],  # raw p-values when cointegrated
            "half_lives": [],  # half-lives when cointegrated
            "partners": set(),  # distinct cointegrating partners
        }
    )
=======
    stats = defaultdict(lambda: {
        "sector": "",
        "coint_count": 0,        # how many (window, partner) pairs are cointegrated
        "total_tests": 0,        # total pair tests involving this symbol
        "pvalues": [],           # raw p-values when cointegrated
        "half_lives": [],        # half-lives when cointegrated
        "partners": set(),       # distinct cointegrating partners
    })
>>>>>>> origin/main

    # Assign sectors
    for sector, syms in candidates.items():
        for s in syms:
            if s in available:
                stats[s]["sector"] = sector

    # Rolling windows
    n_windows = 0
    for end_idx in range(window, n_bars, step):
        window_data = prices_df.iloc[end_idx - window : end_idx]
        n_windows += 1

        # Test all intra-sector pairs in this window
        for sector, syms in candidates.items():
            sector_syms = [s for s in syms if s in available]
            for i, sym1 in enumerate(sector_syms):
                for sym2 in sector_syms[i + 1 :]:
                    s1 = window_data[sym1].dropna()
                    s2 = window_data[sym2].dropna()
                    if len(s1) < 60 or len(s2) < 60:
                        continue

                    stats[sym1]["total_tests"] += 1
                    stats[sym2]["total_tests"] += 1

                    try:
<<<<<<< HEAD
                        result = engle_granger_test(s1, s2, apply_bonferroni=False)
                        pval = result.get("adf_pvalue", 1.0)
                        if pval < 0.05 and not np.isnan(pval):
                            hl = half_life_mean_reversion(pd.Series(result["residuals"]))
=======
                        result = engle_granger_test(
                            s1, s2, apply_bonferroni=False
                        )
                        pval = result.get("adf_pvalue", 1.0)
                        if pval < 0.05 and not np.isnan(pval):
                            hl = half_life_mean_reversion(
                                pd.Series(result["residuals"])
                            )
>>>>>>> origin/main
                            if hl and 0 < hl <= max_half_life:
                                stats[sym1]["coint_count"] += 1
                                stats[sym2]["coint_count"] += 1
                                stats[sym1]["pvalues"].append(pval)
                                stats[sym2]["pvalues"].append(pval)
                                stats[sym1]["half_lives"].append(hl)
                                stats[sym2]["half_lives"].append(hl)
                                stats[sym1]["partners"].add(sym2)
                                stats[sym2]["partners"].add(sym1)
                    except Exception:
                        pass

        if n_windows % 10 == 0:
            print(f"  Window {n_windows}: bar {end_idx}/{n_bars}")

    print(f"\nScored {n_windows} windows")

    # Build results DataFrame
    rows = []
    for sym, s in stats.items():
        if s["total_tests"] == 0:
            continue
        coint_freq = s["coint_count"] / s["total_tests"] if s["total_tests"] > 0 else 0
        avg_pval = np.mean(s["pvalues"]) if s["pvalues"] else 1.0
        avg_hl = np.mean(s["half_lives"]) if s["half_lives"] else 999
        hl_std = np.std(s["half_lives"]) if len(s["half_lives"]) > 1 else 999
        hl_stability = 1.0 / (1.0 + hl_std)  # higher is better (lower variance)
        n_partners = len(s["partners"])

        # Composite score (weighted):
        #   40% cointegration frequency (most important)
<<<<<<< HEAD
        #   20% p-value quality (lower is better ÔåÆ invert)
=======
        #   20% p-value quality (lower is better → invert)
>>>>>>> origin/main
        #   20% half-life stability
        #   20% partner diversity (normalized by sector size)
        sector_size = len([x for x in candidates.get(s["sector"], []) if x in available])
        max_partners = max(sector_size - 1, 1)
        partner_diversity = n_partners / max_partners

        composite = (
            0.40 * coint_freq
<<<<<<< HEAD
            + 0.20 * (1.0 - min(avg_pval / 0.05, 1.0))  # 0ÔåÆ1 scale
=======
            + 0.20 * (1.0 - min(avg_pval / 0.05, 1.0))  # 0→1 scale
>>>>>>> origin/main
            + 0.20 * hl_stability
            + 0.20 * partner_diversity
        )

<<<<<<< HEAD
        rows.append(
            {
                "symbol": sym,
                "sector": s["sector"],
                "coint_frequency": round(coint_freq, 4),
                "avg_pvalue": round(avg_pval, 6),
                "avg_half_life": round(avg_hl, 1),
                "hl_stability": round(hl_stability, 4),
                "n_partners": n_partners,
                "n_tests": s["total_tests"],
                "n_cointegrated": s["coint_count"],
                "composite_score": round(composite, 4),
            }
        )
=======
        rows.append({
            "symbol": sym,
            "sector": s["sector"],
            "coint_frequency": round(coint_freq, 4),
            "avg_pvalue": round(avg_pval, 6),
            "avg_half_life": round(avg_hl, 1),
            "hl_stability": round(hl_stability, 4),
            "n_partners": n_partners,
            "n_tests": s["total_tests"],
            "n_cointegrated": s["coint_count"],
            "composite_score": round(composite, 4),
        })
>>>>>>> origin/main

    df = pd.DataFrame(rows)
    df.sort_values(["sector", "composite_score"], ascending=[True, False], inplace=True)
    return df


def recommend_universe(
    scores_df: pd.DataFrame,
<<<<<<< HEAD
    max_per_sector: dict[str, int] | None = None,
=======
    max_per_sector: Dict[str, int] = None,
>>>>>>> origin/main
) -> pd.DataFrame:
    """Select top symbols per sector based on composite score."""
    if max_per_sector is None:
        # Default: keep top symbols with enough partners
        max_per_sector = {
            "Tech": 6,
            "Financials": 6,
            "Healthcare": 5,
            "Consumer": 5,
            "Energy": 3,
            "Industrials": 4,
            "Utilities": 2,
            "REITs": 3,
        }

    selected = []
    for sector, n in max_per_sector.items():
        sector_df = scores_df[scores_df["sector"] == sector].head(n)
        selected.append(sector_df)

    result = pd.concat(selected, ignore_index=True)
    return result


def main():
    print("=" * 60)
<<<<<<< HEAD
    print("  EDGECORE ÔÇö Symbol Universe Scoring Pipeline")
=======
    print("  EDGECORE — Symbol Universe Scoring Pipeline")
>>>>>>> origin/main
    print("=" * 60)
    print()

    # Step 1: Load data
    print("[1/3] Loading IBKR data for all candidates...")
    prices_df, failed = load_all_data(CANDIDATES)

    # Remove failed symbols from candidates
    clean_candidates = {}
    for sector, syms in CANDIDATES.items():
        clean = [s for s in syms if s not in failed and s in prices_df.columns]
        if clean:
            clean_candidates[sector] = clean
    print()

    # Step 2: Score
    print("[2/3] Scoring symbols across rolling windows...")
    scores = score_symbols(prices_df, clean_candidates)
    print()

    # Step 3: Display results
    print("[3/3] Results")
    print("=" * 60)

    for sector in sorted(scores["sector"].unique()):
        sector_df = scores[scores["sector"] == sector].copy()
<<<<<<< HEAD
        print(f"\n{'ÔöÇ' * 55}")
        print(f"  {sector.upper()}")
        print(f"{'ÔöÇ' * 55}")
        print(f"{'Symbol':<8} {'Score':>6} {'Freq':>6} {'AvgP':>8} {'AvgHL':>6} {'HLStab':>6} {'Partners':>8}")
        print(f"{'ÔöÇ' * 55}")
        for _, row in sector_df.iterrows():
            marker = " ***" if row["composite_score"] >= 0.20 else ""
            print(
                f"{row['symbol']:<8} {row['composite_score']:>6.3f} "
                f"{row['coint_frequency']:>6.3f} {row['avg_pvalue']:>8.5f} "
                f"{row['avg_half_life']:>6.1f} {row['hl_stability']:>6.3f} "
                f"{row['n_partners']:>4}/{len(clean_candidates.get(row['sector'], [])) - 1}"
                f"{marker}"
            )
=======
        print(f"\n{'─' * 55}")
        print(f"  {sector.upper()}")
        print(f"{'─' * 55}")
        print(f"{'Symbol':<8} {'Score':>6} {'Freq':>6} {'AvgP':>8} "
              f"{'AvgHL':>6} {'HLStab':>6} {'Partners':>8}")
        print(f"{'─' * 55}")
        for _, row in sector_df.iterrows():
            marker = " ***" if row["composite_score"] >= 0.20 else ""
            print(f"{row['symbol']:<8} {row['composite_score']:>6.3f} "
                  f"{row['coint_frequency']:>6.3f} {row['avg_pvalue']:>8.5f} "
                  f"{row['avg_half_life']:>6.1f} {row['hl_stability']:>6.3f} "
                  f"{row['n_partners']:>4}/{len(clean_candidates.get(row['sector'], []))-1}"
                  f"{marker}")
>>>>>>> origin/main

    # Recommendation
    recommended = recommend_universe(scores)
    print(f"\n{'=' * 60}")
    print(f"  RECOMMENDED UNIVERSE ({len(recommended)} symbols)")
    print(f"{'=' * 60}")
    for sector in sorted(recommended["sector"].unique()):
        syms = recommended[recommended["sector"] == sector]["symbol"].tolist()
        print(f"  {sector:<14}: {', '.join(syms)}")

    total_pairs = sum(
<<<<<<< HEAD
        len(recommended[recommended["sector"] == s]) * (len(recommended[recommended["sector"] == s]) - 1) // 2
=======
        len(recommended[recommended["sector"] == s]) *
        (len(recommended[recommended["sector"] == s]) - 1) // 2
>>>>>>> origin/main
        for s in recommended["sector"].unique()
    )
    print(f"\n  Total intra-sector pairs: {total_pairs}")
    print(f"{'=' * 60}")

    # Save to CSV
    scores.to_csv("data/audit/symbol_scores.csv", index=False)
    print("\nFull scores saved to data/audit/symbol_scores.csv")


if __name__ == "__main__":
    main()
