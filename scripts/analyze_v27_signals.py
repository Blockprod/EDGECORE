"""Analyze entry z-scores, exits, and signal quality for v27."""

import re
from collections import Counter

with open("results/bt_v27_output.txt", encoding="utf-16-le") as f:
    text = f.read()

# 1. Entry z-scores from trailing_stop_position_added
entries = re.findall(
    r"trailing_stop_position_added\s+entry_spread=([\d.-]+)\s+entry_z=([\d.-]+)\s+pair=(\S+)\s+side=(\w+)",
    text,
)
print(f"Trade entries (trailing_stop_position_added): {len(entries)}")
print()
print(f"{'Pair':<15} {'Side':<6} {'Entry Z':>8} {'Entry Spread':>14}")
print("-" * 50)
for spread, z, pair, side in entries:
    print(f"{pair:<15} {side:<6} {float(z):>8.3f} {float(spread):>14.4f}")

zs = [abs(float(z)) for _, z, _, _ in entries]
if zs:
    print()
    print("Entry Z-score |abs| distribution:")
    print(f"  Min: {min(zs):.3f}")
    print(f"  Max: {max(zs):.3f}")
    print(f"  Avg: {sum(zs) / len(zs):.3f}")
    print(f"  Below 1.5: {sum(1 for z in zs if z < 1.5)}")
    print(f"  1.5-2.0: {sum(1 for z in zs if 1.5 <= z < 2.0)}")
    print(f"  2.0-2.5: {sum(1 for z in zs if 2.0 <= z < 2.5)}")
    print(f"  2.5+: {sum(1 for z in zs if z >= 2.5)}")

# 2. Exit type breakdown
print()
print("=" * 60)
print("EXIT TYPE ANALYSIS")
print("=" * 60)

# Z-score exits (mean reversion success)
z_exits = re.findall(r"z_score_exit\s+.*?pair=(\S+)", text)
z_stop_exits = re.findall(r"z_score_stop_exit\s+.*?pair=(\S+)", text)
trailing_exits = re.findall(r"trailing_stop_triggered\s+.*?pair=(\S+)", text)
time_exits = re.findall(r"time_stop_exit\s+.*?pair=(\S+)", text)
partial_profits = re.findall(r"partial_profit_take\s+.*?pair=(\S+)", text)

# Count total exits logged
total_exits = len(z_exits) + len(z_stop_exits) + len(trailing_exits) + len(time_exits)
print(f"Z-score exits (mean reversion): {len(z_exits)} ({z_exits})")
print(f"Z-score STOP exits (adverse): {len(z_stop_exits)} ({z_stop_exits})")
print(f"Trailing stop triggered: {len(trailing_exits)} ({trailing_exits})")
print(f"Time stop exits: {len(time_exits)}")
print(f"Partial profit takes: {len(partial_profits)}")
print(f"Total explicit exits: {total_exits}")
print(f"Unaccounted exits (67 trades - {total_exits} explicit): {67 - total_exits}")

# 3. Spread correlation rejections
spread_rej = re.findall(
    r"(?:spread_correlation_entry_rejected|entry_rejected_spread_correlation)\s+.*?pair=(\S+)",
    text,
)
print()
print(f"Spread correlation rejections: {len(spread_rej)}")
rej_pairs = Counter(spread_rej)
for p, c in rej_pairs.most_common():
    print(f"  {p}: {c} rejections")

# 4. How many unique pairs discovered vs traded
disc_events = re.findall(r"pairs_discovered\s+count=(\d+)", text)
print()
print(f"Pair discovery events: {len(disc_events)}")
if disc_events:
    print(f"  Counts: {disc_events}")

# 5. Sector/FDR pass events
sector_fdr = re.findall(r"sector_fdr_pass\s+.*?pair=(\S+)", text)
print(f"Sector FDR pass events: {len(sector_fdr)}")
fdr_pairs = Counter(sector_fdr)
print(f"  Unique pairs passing FDR: {len(fdr_pairs)}")
for p, c in fdr_pairs.most_common(15):
    print(f"    {p}: {c}")

# 6. Cointegration tests
coint = re.findall(r"eg_test_complete\s+.*?pair=(\S+).*?p_value=([\d.]+).*?result=(\w+)", text)
if coint:
    passed = [(p, pv) for p, pv, r in coint if r in ("pass", "cointegrated", "True", "true")]
    failed = [(p, pv) for p, pv, r in coint if r not in ("pass", "cointegrated", "True", "true")]
    print(f"\nCointegration tests: {len(coint)} total, {len(passed)} passed, {len(failed)} failed")
else:
    # Try without result field
    coint2 = re.findall(r"eg_test_complete\s+.*?pair=(\S+).*?p_value=([\d.e-]+)", text)
    print(f"\nCointegration tests: {len(coint2)}")
    if coint2:
        pvs = [float(pv) for _, pv in coint2]
        passed = sum(1 for pv in pvs if pv < 0.05)
        print(f"  p < 0.05: {passed} ({passed / len(pvs) * 100:.1f}%)")
        print(f"  p >= 0.05: {len(pvs) - passed} ({(len(pvs) - passed) / len(pvs) * 100:.1f}%)")
        print(f"  Avg p-value: {sum(pvs) / len(pvs):.4f}")
        print(f"  Median p-value: {sorted(pvs)[len(pvs) // 2]:.4f}")
