#!/usr/bin/env python3
"""
Daily Universe Scan ÔÇö Production entry point for dynamic pair discovery.

This script runs the full pipeline:
  1. Scan universe (SEC EDGAR + optional IBKR validation)
  2. Load daily prices for all symbols (with rate limiting)
  3. Resample to weekly (zero API cost)
  4. Discover cointegrated pairs (vectorized prefilter + BH-FDR)
  5. Apply weekly MTF confirmation
  6. Output results to JSON for live trading consumption

Designed to run as a scheduled daily task (cron, Task Scheduler, etc.)
at market open -1h (e.g. 08:30 EST / 13:30 UTC).

Usage::

    # Full pipeline (requires IBKR connection)
    python scripts/daily_scan.py

    # SEC-only scan (no IBKR ÔÇö for testing/development)
    python scripts/daily_scan.py --sec-only

    # Use cached universe (skip IBKR validation)
    python scripts/daily_scan.py --use-cache

    # Specify output file
    python scripts/daily_scan.py --output results/daily_pairs.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from structlog import get_logger

logger = get_logger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(description="EDGECORE Daily Universe Scan")
    parser.add_argument(
        "--sec-only", action="store_true",
        help="Use SEC EDGAR only (no IBKR connection required)",
    )
    parser.add_argument(
        "--use-cache", action="store_true",
        help="Use cached universe if available and fresh",
    )
    parser.add_argument(
        "--no-weekly", action="store_true",
        help="Skip weekly MTF confirmation",
    )
    parser.add_argument(
        "--sector-map", type=str, default=None,
        help="Path to JSON sector map file (overrides scanner)",
    )
    parser.add_argument(
        "--output", type=str, default="cache/daily_scan_result.json",
        help="Output JSON file path",
    )
    parser.add_argument(
        "--max-symbols", type=int, default=0,
        help="Limit number of symbols (0 = no limit, for dev/testing)",
    )
    parser.add_argument(
        "--lookback", type=int, default=252,
        help="Daily lookback window for cointegration",
    )
    parser.add_argument(
        "--min-correlation", type=float, default=0.60,
        help="Minimum correlation for pre-filter",
    )
    parser.add_argument(
        "--fdr-q", type=float, default=0.10,
        help="BH-FDR q-level for significance",
    )
    return parser.parse_args()


def run_daily_scan(args) -> Dict:
    """
    Execute the full daily scan pipeline.

    Returns:
        Dict with scan results (symbols, pairs, statistics).
    """
    from universe.scanner import IBKRUniverseScanner, ScannerConfig
    from universe.rate_limiter import IBKRRateLimiter
    from data.loader import DataLoader
    from data.multi_timeframe import MultiTimeframeEngine
    from strategies.pair_trading import PairTradingStrategy
    from config.settings import get_settings

    t0 = time.monotonic()
    settings = get_settings()

    # ÔöÇÔöÇ Phase 1: Universe scan ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
    logger.info("phase_1_universe_scan_starting")
    scanner = IBKRUniverseScanner(ScannerConfig(
        min_market_cap_usd=settings.scanner.min_market_cap_usd,
        min_avg_volume_usd=settings.scanner.min_avg_volume_usd,
    ))

    if args.sec_only:
        symbols = scanner.scan_sec_only()
    elif args.use_cache:
        cached = scanner.load_cache()
        if cached is not None:
            symbols = cached
        else:
            logger.info("cache_miss_falling_back_to_sec")
            symbols = scanner.scan_sec_only()
    else:
        symbols = scanner.scan()

    # Apply max_symbols limit (for dev/testing)
    if args.max_symbols > 0:
        symbols = symbols[:args.max_symbols]
        logger.info("symbols_limited", count=len(symbols))

    tickers = [s.ticker for s in symbols]
    sector_map = {s.ticker: s.sector for s in symbols}

    # Override sector map if provided
    if args.sector_map:
        with open(args.sector_map) as f:
            sector_map = json.load(f)
        tickers = list(sector_map.keys())

    logger.info(
        "phase_1_complete",
        symbols=len(tickers),
        sectors=len(set(sector_map.values())),
        elapsed=round(time.monotonic() - t0, 1),
    )

    # ÔöÇÔöÇ Phase 2: Load daily prices ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
    logger.info("phase_2_loading_prices", symbols=len(tickers))
    rate_limiter = IBKRRateLimiter()
    loader = DataLoader()

    prices_data = loader.bulk_load(
        tickers,
        timeframe="1d",
        limit=args.lookback + 60,  # extra buffer
        max_workers=3,
        use_cache=True,
        rate_limiter=rate_limiter,
    )

    # Build prices DataFrame
    prices_df = pd.DataFrame({
        sym: df["close"] for sym, df in prices_data.items()
        if df is not None and not df.empty and "close" in df.columns
    })

    # Drop symbols with insufficient data
    min_points = args.lookback // 2
    valid_cols = [c for c in prices_df.columns if prices_df[c].dropna().shape[0] >= min_points]
    prices_df = prices_df[valid_cols]

    logger.info(
        "phase_2_complete",
        symbols_loaded=len(prices_df.columns),
        bars=len(prices_df),
        elapsed=round(time.monotonic() - t0, 1),
    )

    # ÔöÇÔöÇ Phase 3: Resample to weekly ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
    weekly_prices = None
    if not args.no_weekly:
        logger.info("phase_3_resampling_to_weekly")
        mtf = MultiTimeframeEngine()
        weekly_prices = mtf.resample_to_weekly(prices_df)
        logger.info(
            "phase_3_complete",
            weekly_bars=len(weekly_prices),
            elapsed=round(time.monotonic() - t0, 1),
        )

    # ÔöÇÔöÇ Phase 4: Pair discovery ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
    logger.info("phase_4_pair_discovery_starting")
    strategy = PairTradingStrategy()

    # Override config for scan
    strategy.config.lookback_window = args.lookback
    strategy.config.min_correlation = args.min_correlation
    strategy.config.fdr_q_level = args.fdr_q

    # Update sector map
    strategy.sector_map = {
        k: v for k, v in sector_map.items()
        if k in prices_df.columns
    }

    pairs = strategy.find_cointegrated_pairs(
        prices_df,
        lookback=args.lookback,
        use_cache=False,
        weekly_prices=weekly_prices,
    )

    elapsed = time.monotonic() - t0
    logger.info(
        "phase_4_complete",
        pairs_found=len(pairs),
        total_elapsed=round(elapsed, 1),
    )

    # ÔöÇÔöÇ Phase 5: Format results ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
    result = {
        "timestamp": datetime.now().isoformat(),
        "scan_type": "sec_only" if args.sec_only else "full",
        "universe_size": len(tickers),
        "symbols_with_data": len(prices_df.columns),
        "daily_bars": len(prices_df),
        "weekly_bars": len(weekly_prices) if weekly_prices is not None else 0,
        "weekly_confirmation": not args.no_weekly,
        "lookback": args.lookback,
        "min_correlation": args.min_correlation,
        "fdr_q": args.fdr_q,
        "pairs_discovered": len(pairs),
        "elapsed_seconds": round(elapsed, 1),
        "pairs": [
            {
                "sym1": p[0],
                "sym2": p[1],
                "pvalue": round(float(p[2]), 6),
                "half_life": round(float(p[3]), 2),
                "sector": sector_map.get(p[0], "unknown"),
            }
            for p in pairs
        ],
        "sector_distribution": _sector_pair_distribution(pairs, sector_map),
    }

    # Save output
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)
    logger.info("results_saved", path=str(output_path))

    return result


def _sector_pair_distribution(
    pairs: List[Tuple], sector_map: Dict[str, str]
) -> Dict[str, int]:
    """Count pairs per sector."""
    counts: Dict[str, int] = {}
    for p in pairs:
        sec = sector_map.get(p[0], "unknown")
        counts[sec] = counts.get(sec, 0) + 1
    return counts


def main():
    args = parse_args()

    logger.info(
        "daily_scan_starting",
        sec_only=args.sec_only,
        use_cache=args.use_cache,
        weekly=not args.no_weekly,
        max_symbols=args.max_symbols,
    )

    try:
        result = run_daily_scan(args)
        print(f"\n{'='*60}")
        print("  EDGECORE Daily Scan Complete")
        print(f"{'='*60}")
        print(f"  Universe:   {result['universe_size']} scanned ÔåÆ {result['symbols_with_data']} with data")
        print(f"  Pairs:      {result['pairs_discovered']} cointegrated pairs found")
        print(f"  Weekly MTF: {'enabled' if result['weekly_confirmation'] else 'disabled'}")
        print(f"  Elapsed:    {result['elapsed_seconds']}s")
        print(f"  Output:     {args.output}")
        print(f"{'='*60}\n")

        if result["pairs"]:
            print("  Top 10 pairs by p-value:")
            sorted_pairs = sorted(result["pairs"], key=lambda x: x["pvalue"])
            for i, p in enumerate(sorted_pairs[:10], 1):
                print(
                    f"    {i:2d}. {p['sym1']:5s}-{p['sym2']:5s}  "
                    f"p={p['pvalue']:.4f}  hl={p['half_life']:5.1f}  "
                    f"[{p['sector']}]"
                )
            print()

    except Exception as exc:
        logger.error("daily_scan_failed", error=str(exc))
        print(f"\nERROR: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
