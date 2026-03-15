"""Inspecte les symboles retourn├®s par `IBKRUniverseScanner.bootstrap_from_sec()`
et affiche les premiers cas o├╣ `ticker` n'est pas une `str`.
"""
import sys
import os

# Ensure workspace root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from universe import IBKRUniverseScanner


if __name__ == "__main__":
    scanner = IBKRUniverseScanner()
    scanned = scanner.load_cache()
    if scanned is None:
        print("No universe cache found or cache stale; falling back to SEC bootstrap (may fail if network blocked)")
        scanned = scanner.bootstrap_from_sec()
    problematic = []
    for i, s in enumerate(scanned):
        t = s.ticker
        if not isinstance(t, str):
            problematic.append((i, repr(t), type(t).__name__))
    print("total_scanned", len(scanned))
    if problematic:
        print("non-str tickers sample:")
        for p in problematic[:50]:
            print(p)
    else:
        print("no non-str tickers in bootstrap_from_sec() output")
