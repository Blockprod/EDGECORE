#!/usr/bin/env python
"""Quick backtest runner - multi-sector real IBKR data.

v19d - Conditional Prefilter + v18 params.

      NEW IN v19 (from dynamic universe implementation):
        1. Weekly confirmation gate: pairs must pass weekly cointegration
           (p<0.10) AND weekly z-score gate (|z|>1.0) to enter
        2. Correlation prefilter: vectorized O(N┬▓) screening before
           expensive cointegration tests (min_corr=0.65)
        3. MTF composite score: 60% daily + 40% weekly p-value weighting

      STRUCTURAL FIXES (permanent, from v17 series):
        1. Per-sector BH-FDR (m per sector, not pooled)
        2. Simulator-level z-score exit (independent of discovery)
        3. Z-score stop at 3.5¤â (natural stat-arb risk control)
        4. Circuit breaker HWM reset (no infinite loop)
        5. Multi-lookback (252 + 126): diverse discovery

      UNIVERSE (v18 curated, 31 symbols):
        Original 26 + 5 profitable additions (SCHW, RTX, AVGO, SO, EOG)
        7 toxic symbols excluded (AXP, UNP, SLB, COST, INTC, MO, D)

      PARAMS (v17f proven):
        entry_z=2.0 (institutional R:R = 1:1)
        exit_z=0.5, z_stop=3.5
        90% allocation (2x leverage, market-neutral)
        3% pre-signal P&L stop (redundant backup to z_stop)
        400% heat (allows ~4 concurrent leveraged pairs)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from backtests.runner import BacktestRunner

if __name__ == "__main__":

    runner = BacktestRunner()

    # --- Dynamic universe: scan 100% IBKR symbols (with filters) ---
    from universe import IBKRUniverseScanner
    import argparse

    def main():
        parser = argparse.ArgumentParser(description="EDGECORE Backtest CLI")
        parser.add_argument("--start", type=str, default="2020-01-01", help="Date de d├®but du backtest")
        parser.add_argument("--end", type=str, default="2026-01-01", help="Date de fin du backtest")
        parser.add_argument("--capital", type=float, default=100_000, help="Capital initial")
        parser.add_argument("--alloc", type=float, default=90.0, help="Allocation par paire (%)")
        parser.add_argument("--stop", type=float, default=0.03, help="Stop loss par position (%)")
        parser.add_argument("--heat", type=float, default=4.0, help="Portfolio heat limit (x capital)")
        parser.add_argument("--rediscovery", type=int, default=3, help="Intervalle de red├®couverte des paires (bars)")
        parser.add_argument("--batch_size", type=int, default=50, help="Batch size pour scan IBKR")
        parser.add_argument("--weekly_confirmation", action="store_true", help="Activer la confirmation weekly")
        parser.add_argument("--async_scan", action="store_true", help="Activer le scan IBKR en mode async/thread")
        args = parser.parse_args()

        runner = BacktestRunner()

        # --- Dynamic universe: scan 100% IBKR symbols (with filters) ---
        scanner = IBKRUniverseScanner()
        scanner.batch_size = args.batch_size  # type: ignore[attr-defined]
        scanner.async_mode = args.async_scan  # type: ignore[attr-defined]
        scanned = scanner.scan(use_cache=True)  # set False to force fresh scan
        # Defensive: ensure all tickers are str and capture a debug snapshot

        symbols = []
        sector_map = {}
        problematic = []
        for i, s in enumerate(scanned):
            t = s.ticker
            # Strict filter: must be pure string and not a stringified list/tuple
            if not isinstance(t, str) or t.startswith("[") or t.startswith("("):
                problematic.append((i, type(t).__name__, repr(t)))
                continue
            symbols.append(t)
            sector_map[t] = s.sector

        # Write a small debug snapshot to disk for upstream troubleshooting
        try:
            with open(os.path.join(_ROOT, "logs", "debug_symbols_snapshot.txt"), "w", encoding="utf-8") as df:
                df.write("idx\ttype\trepr\tticker\n")
                for i, s in enumerate(scanned[:200]):
                    df.write(f"{i}\t{type(s.ticker).__name__}\t{repr(s.ticker)}\t{str(s.ticker)}\n")
                if problematic:
                    df.write("\n# Problematic (non-str or stringified list/tuple) samples:\n")
                    for p in problematic[:50]:
                        df.write(f"{p[0]}\t{p[1]}\t{p[2]}\n")
        except Exception:
            pass
        print(f"[Dynamic Universe] {len(symbols)} symbols loaded from IBKR scanner.")
        if problematic:
            print(
                f"[WARNING] {len(problematic)} problematic tickers rejected. See debug_symbols_snapshot.txt for details."
            )

        # -- Capital --
        runner.config.initial_capital = args.capital

        # -- Strategy tuning --
        from config.settings import get_settings

        settings = get_settings()
        settings.strategy.lookback_window = 252  # 1 year (proven quality)
        settings.strategy.additional_lookback_windows = [126]  # 6-month secondary
        settings.strategy.fdr_q_level = 0.10  # strict quality
        settings.strategy.min_correlation = 0.65  # strict correlation
        settings.strategy.entry_z_score = 2.0  # institutional (R:R = 1:1 at z_stop=3.5)
        settings.strategy.exit_z_score = 0.5  # comfortable reversion target
        settings.strategy.max_half_life = 90  # accept slower pairs
        settings.strategy.z_score_stop = 3.5  # z-based stop (natural for stat-arb)
        settings.strategy.weekly_confirmation = args.weekly_confirmation

        print("=" * 60)
        print("  EDGECORE BACKTEST v19d - Conditional Prefilter")
        print("=" * 60)
        print(f"  Symbols:  {len(symbols)} across 6 sectors (curated)")
        n_intra = sum(
            1 for i, s1 in enumerate(symbols) for s2 in symbols[i + 1 :] if sector_map.get(s1) == sector_map.get(s2)
        )
        print(f"  Pairs:    {n_intra} intra-sector (BH-FDR per-sector q=0.10)")
        print(f"  Period:   {args.start} -> {args.end}")
        print(f"  Capital:  {args.capital} EUR")
        print(f"  Alloc:    {args.alloc}% per pair (2x leverage)")
        print(f"  Stop:     {args.stop * 100}%  |  Heat limit: {args.heat * 100}%")
        print(f"  Lookback: {settings.strategy.lookback_window} + {settings.strategy.additional_lookback_windows}")
        print(
            f"  Z-score:  entry={settings.strategy.entry_z_score}, "
            f"exit={settings.strategy.exit_z_score}, z_stop={settings.strategy.z_score_stop}"
        )
        print(
            f"  Params:   min_corr={settings.strategy.min_correlation}, "
            f"max_hl={settings.strategy.max_half_life}, "
            f"q={settings.strategy.fdr_q_level}"
        )
        print(f"  Weekly:   confirmation={settings.strategy.weekly_confirmation}")
        print(f"  Rediscovery: every {args.rediscovery} bar(s)")
        print(f"  Batch size: {args.batch_size}")
        print("=" * 60)
        print()

        print("[EDGECORE] Backtest institutionnel en cours...")
        metrics = runner.run_unified(
            symbols=symbols,
            start_date=args.start,
            end_date=args.end,
            sector_map=sector_map,
            pair_rediscovery_interval=args.rediscovery,
            allocation_per_pair_pct=args.alloc,
            max_position_loss_pct=args.stop,
            max_portfolio_heat=args.heat,
            weekly_confirmation=args.weekly_confirmation,
        )

        print("[EDGECORE] Backtest termin├® !")
        print()
        print(metrics.summary())
        print(f"Number of symbols in universe: {metrics.num_symbols}")

        # Sauvegarde des r├®sultats
        import pandas as pd
        import json

        # R├®sum├® principal
        summary = metrics.summary()
        with open(os.path.join(_ROOT, "results", "bt_results_summary.txt"), "w", encoding="utf-8") as f:
            f.write(summary)
        # Sauvegarde des m├®triques en JSON
        metrics_dict = metrics.__dict__ if hasattr(metrics, "__dict__") else {}  # type: ignore[assignment]
        with open(os.path.join(_ROOT, "results", "bt_results_metrics.json"), "w", encoding="utf-8") as f:
            json.dump(metrics_dict, f, indent=2, ensure_ascii=False)
        # Sauvegarde des retours quotidiens en CSV
        if hasattr(metrics, "returns"):
            _attr = "returns"
            _returns_raw = getattr(metrics, _attr)
            returns = _returns_raw if isinstance(_returns_raw, pd.Series) else pd.Series(_returns_raw)
            returns.to_csv(os.path.join(_ROOT, "results", "bt_results_returns.csv"), index=True)

    if __name__ == "__main__":
        main()
