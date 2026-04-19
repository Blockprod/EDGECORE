"""Diagnostic rapide : tester la pair discovery v49 sur un sous-ensemble.

Objectif : confirmer que les paramètres v49 trouvent des paires sur la fenêtre
training 2023H1-2024H1 avant de lancer le backtest complet (~30 min).

Exécution : ~5 min (10 symboles, 2 secteurs)
"""

import os
import sys
import time
from typing import cast

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import get_settings
from strategies.pair_trading import PairTradingStrategy

# Sous-ensemble représentatif : technologie + finance
TEST_SYMBOLS = [
    "AAPL",
    "MSFT",
    "NVDA",
    "AMD",
    "INTC",
    "QCOM",  # tech
    "JPM",
    "BAC",
    "GS",
    "MS",
    "WFC",
    "C",  # finance
]
SECTOR_MAP = {
    "AAPL": "technology",
    "MSFT": "technology",
    "NVDA": "technology",
    "AMD": "technology",
    "INTC": "technology",
    "QCOM": "technology",
    "JPM": "financials",
    "BAC": "financials",
    "GS": "financials",
    "MS": "financials",
    "WFC": "financials",
    "C": "financials",
}
TRAIN_START = "2023-01-03"
TRAIN_END = "2024-07-01"


def apply_v49_params():
    s = get_settings()
    s.strategy.lookback_window = 120
    s.strategy.entry_z_score = 1.3  # v49: was 1.6
    s.strategy.exit_z_score = 0.5
    s.strategy.min_correlation = 0.65
    s.strategy.max_half_life = 60
    s.strategy.bonferroni_correction = True
    s.strategy.johansen_confirmation = True
    s.strategy.newey_west_consensus = True
    if hasattr(s.strategy, "fdr_q_level"):
        s.strategy.fdr_q_level = 0.50  # v49: was 0.30
    return s


def main():
    print("=" * 60)
    print("  Diagnostic pair discovery v49 params")
    print(f"  Symbols : {len(TEST_SYMBOLS)} ({','.join(TEST_SYMBOLS[:4])}...)")
    print(f"  Window  : {TRAIN_START} -> {TRAIN_END}")
    print("=" * 60)

    s = apply_v49_params()
    print(f"\n  entry_z_score    = {s.strategy.entry_z_score}")
    print(f"  fdr_q_level      = {getattr(s.strategy, 'fdr_q_level', 'N/A (attr absent)')}")
    print(f"  johansen         = {s.strategy.johansen_confirmation}")
    print(f"  newey_west       = {s.strategy.newey_west_consensus}")
    print(f"  bonferroni       = {s.strategy.bonferroni_correction}")

    # 1. Load data
    print("\n[1] Chargement données IBKR...")
    t0 = time.time()
    from data.loader import load_price_data

    try:
        prices = load_price_data(
            symbols=TEST_SYMBOLS,
            timeframe="1d",
            limit=400,  # ~400 jours de trading ≈ 2023-01-03 → 2024-07-01
        )
    except Exception as e:
        print(f"  ❌ Erreur chargement : {e}")
        return

    elapsed_load = time.time() - t0
    print(f"  ✅ Données chargées : {prices.shape} en {elapsed_load:.0f}s")
    print(f"  Symboles dispo      : {list(prices.columns)}")
    first_dt = cast(pd.Timestamp, prices.index[0])
    last_dt = cast(pd.Timestamp, prices.index[-1])
    print(f"  Période             : {first_dt.date()} → {last_dt.date()}")

    # 2. Pair discovery
    print("\n[2] Pair discovery (intra-secteur)...")
    t1 = time.time()
    strategy = PairTradingStrategy()
    try:
        pairs = strategy.find_cointegrated_pairs_parallel(
            price_data=prices,
            lookback=120,
            sector_map=SECTOR_MAP,
        )
    except Exception as e:
        print(f"  ❌ Erreur discovery : {e}")
        return

    elapsed_discovery = time.time() - t1
    print(f"  Durée discovery : {elapsed_discovery:.0f}s")
    print(f"  Paires trouvées : {len(pairs)}")

    if pairs:
        print("\n  Paires :")
        for sym1, sym2, pval, hl in sorted(pairs, key=lambda x: x[2]):
            print(f"    {sym1}-{sym2}  p={pval:.4f}  hl={hl:.1f}d")
        print("\n  ✅ VERDICT : paramètres v49 OK — lancer le backtest complet")
    else:
        print("\n  ❌ VERDICT : 0 paires — paramètres encore trop restrictifs")
        print("  Suggestions:")
        print("    → Baisser min_correlation: 0.65 → 0.55")
        print("    → Désactiver johansen_confirmation")
        print("    → Désactiver newey_west_consensus")

    print(f"\n  Total : {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
