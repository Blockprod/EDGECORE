#!/usr/bin/env python
"""Quick backtest runner - multi-sector real IBKR data.

v18 - Curated Universe + All Structural Fixes.
      
      STRUCTURAL FIXES (permanent, from v17 series):
        1. Per-sector BH-FDR (m per sector, not pooled)
        2. Simulator-level z-score exit (independent of discovery)
        3. Z-score stop at 3.5σ (natural stat-arb risk control)
        4. Circuit breaker HWM reset (no infinite loop)
        5. Multi-lookback (252 + 126): diverse discovery

      UNIVERSE CURATION (from v17g pair-level analysis):
        Original 26 + 5 profitable additions:
          SCHW (+5,866€), RTX (+8,591€), AVGO (+1,849€),
          SO (+1,949€), EOG (+545€)
        7 toxic symbols excluded (net -33,734€):
          AXP, UNP, SLB, COST, INTC, MO, D
        
      PARAMS (v17f proven):
        entry_z=2.0 (institutional R:R = 1:1)
        exit_z=0.5, z_stop=3.5
        90% allocation (2x leverage, market-neutral)
        3% pre-signal P&L stop (redundant backup to z_stop)
        400% heat (allows ~4 concurrent leveraged pairs)
"""

from backtests.runner import BacktestRunner

if __name__ == "__main__":
    runner = BacktestRunner()

    symbols = [
        # Technology (7 -> 21 intra-sector pairs)
        "AAPL", "MSFT", "GOOGL", "META", "NVDA", "AMD", "AVGO",
        # Financials (7 -> 21 pairs)
        "JPM", "GS", "BAC", "MS", "WFC", "C", "SCHW",
        # Energy (4 -> 6 pairs)
        "XOM", "CVX", "COP", "EOG",
        # Consumer Staples (5 -> 10 pairs)
        "KO", "PEP", "PG", "CL", "WMT",
        # Industrials (5 -> 10 pairs)
        "CAT", "HON", "DE", "GE", "RTX",
        # Utilities (3 -> 3 pairs)
        "NEE", "DUK", "SO",
    ]

    sector_map = {
        "AAPL": "Tech", "MSFT": "Tech", "GOOGL": "Tech",
        "META": "Tech", "NVDA": "Tech", "AMD": "Tech", "AVGO": "Tech",
        "JPM": "Financials", "GS": "Financials", "BAC": "Financials",
        "MS": "Financials", "WFC": "Financials", "C": "Financials",
        "SCHW": "Financials",
        "XOM": "Energy", "CVX": "Energy", "COP": "Energy", "EOG": "Energy",
        "KO": "Consumer", "PEP": "Consumer", "PG": "Consumer",
        "CL": "Consumer", "WMT": "Consumer",
        "CAT": "Industrials", "HON": "Industrials",
        "DE": "Industrials", "GE": "Industrials", "RTX": "Industrials",
        "NEE": "Utilities", "DUK": "Utilities", "SO": "Utilities",
    }

    # -- Capital --
    runner.config.initial_capital = 100_000

    # -- Strategy tuning --
    from config.settings import get_settings
    settings = get_settings()
    settings.strategy.lookback_window = 252            # 1 year (proven quality)
    settings.strategy.additional_lookback_windows = [126]  # 6-month secondary
    settings.strategy.fdr_q_level = 0.10               # strict quality
    settings.strategy.min_correlation = 0.65            # strict correlation
    settings.strategy.entry_z_score = 2.0               # institutional (R:R = 1:1 at z_stop=3.5)
    settings.strategy.exit_z_score = 0.5                # comfortable reversion target
    settings.strategy.max_half_life = 90                # accept slower pairs
    settings.strategy.z_score_stop = 3.5                # z-based stop (natural for stat-arb)

    ALLOC_PCT = 90.0     # 2x leverage (amplify PF 1.22 edge)
    STOP_PCT = 0.03      # 3% stop on position notional
    HEAT_LIMIT = 4.0     # allow up to 400% notional (more concurrent pairs)
    REDISCOVERY = 3      # every 3 bars

    print("=" * 60)
    print("  EDGECORE BACKTEST v18 - Curated Universe")
    print("=" * 60)
    print(f"  Symbols:  {len(symbols)} across 6 sectors (curated)")
    n_intra = sum(1 for i, s1 in enumerate(symbols)
                  for s2 in symbols[i+1:]
                  if sector_map.get(s1) == sector_map.get(s2))
    print(f"  Pairs:    {n_intra} intra-sector (BH-FDR per-sector q=0.10)")
    print(f"  Period:   2020-01-01 -> 2026-01-01  (6 years)")
    print(f"  Capital:  100 000 EUR")
    print(f"  Alloc:    {ALLOC_PCT}% per pair (2x leverage)")
    print(f"  Stop:     {STOP_PCT*100}%  |  Heat limit: {HEAT_LIMIT*100}%")
    print(f"  Lookback: {settings.strategy.lookback_window} + {settings.strategy.additional_lookback_windows}")
    print(f"  Z-score:  entry={settings.strategy.entry_z_score}, "
          f"exit={settings.strategy.exit_z_score}, z_stop={settings.strategy.z_score_stop}")
    print(f"  Params:   min_corr={settings.strategy.min_correlation}, "
          f"max_hl={settings.strategy.max_half_life}, "
          f"q={settings.strategy.fdr_q_level}")
    print(f"  Rediscovery: every {REDISCOVERY} bar(s)")
    print("=" * 60)
    print()

    metrics = runner.run_unified(
        symbols=symbols,
        start_date="2020-01-01",
        end_date="2026-01-01",
        sector_map=sector_map,
        pair_rediscovery_interval=REDISCOVERY,
        allocation_per_pair_pct=ALLOC_PCT,
        max_position_loss_pct=STOP_PCT,
        max_portfolio_heat=HEAT_LIMIT,
    )

    print()
    print(metrics.summary())
