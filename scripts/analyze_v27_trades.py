<<<<<<< HEAD
﻿"""Detailed analysis of v27 backtest trades to identify root cause of losses."""

import re
from collections import defaultdict
from typing import Any
=======
"""Detailed analysis of v27 backtest trades to identify root cause of losses."""
import re
import json
from collections import defaultdict
>>>>>>> origin/main

with open("results/bt_v27_output.txt", encoding="utf-16-le") as f:
    text = f.read()

# --- Extract all closed trades ---
pattern = (
    r"simulated_trade_(?:closed|force_closed)\s+"
    r"borrow_cost=([\d.]+)\s+exit_cost=([\d.]+)\s+"
    r"holding_days=(\d+)\s+pair=(\S+)\s+"
    r"pnl_gross=([-\d.]+)\s+side=(\w+)\s+trade_pnl=([-\d.]+)"
)
matches = re.findall(pattern, text)

trades = []
for m in matches:
<<<<<<< HEAD
    trades.append(
        {
            "borrow_cost": float(m[0]),
            "exit_cost": float(m[1]),
            "holding_days": int(m[2]),
            "pair": m[3],
            "pnl_gross": float(m[4]),
            "side": m[5],
            "trade_pnl": float(m[6]),
        }
    )
=======
    trades.append({
        "borrow_cost": float(m[0]),
        "exit_cost": float(m[1]),
        "holding_days": int(m[2]),
        "pair": m[3],
        "pnl_gross": float(m[4]),
        "side": m[5],
        "trade_pnl": float(m[6]),
    })
>>>>>>> origin/main

# Also check for force-closed separately
force_pattern = r"simulated_trade_force_closed"
force_count = len(re.findall(force_pattern, text))

# --- Extract partial profit takes ---
pp_pattern = r"partial_profit_take\s+.*?pair=(\S+).*?pnl=([-\d.]+)"
partial_profits = re.findall(pp_pattern, text)

# --- Extract stop triggers ---
stop_pattern = r"position_stop_triggered\s+.*?pair=(\S+).*?reason=(\w+)"
stops = re.findall(stop_pattern, text)

# --- Extract trailing stops ---
trailing_pattern = r"trailing_stop_position_added\s+.*?pair=(\S+)"
trailing_stops = re.findall(trailing_pattern, text)

print("=" * 80)
print("V27 BACKTEST - DETAILED TRADE ANALYSIS")
print("=" * 80)

# 1. Overall Summary
wins = [t for t in trades if t["trade_pnl"] > 0]
losses = [t for t in trades if t["trade_pnl"] <= 0]
total_pnl = sum(t["trade_pnl"] for t in trades)
total_borrow = sum(t["borrow_cost"] for t in trades)
total_exit_cost = sum(t["exit_cost"] for t in trades)
total_gross = sum(t["pnl_gross"] for t in trades)

<<<<<<< HEAD
print("\n--- OVERALL SUMMARY ---")
print(f"Total trades: {len(trades)}")
print(f"Force-closed trades: {force_count}")
print(f"Winners: {len(wins)} ({len(wins) / len(trades) * 100:.1f}%)")
print(f"Losers: {len(losses)} ({len(losses) / len(trades) * 100:.1f}%)")
=======
print(f"\n--- OVERALL SUMMARY ---")
print(f"Total trades: {len(trades)}")
print(f"Force-closed trades: {force_count}")
print(f"Winners: {len(wins)} ({len(wins)/len(trades)*100:.1f}%)")
print(f"Losers: {len(losses)} ({len(losses)/len(trades)*100:.1f}%)")
>>>>>>> origin/main
print(f"Total Gross PnL: ${total_gross:,.2f}")
print(f"Total Borrow Cost: ${total_borrow:,.2f}")
print(f"Total Exit Cost: ${total_exit_cost:,.2f}")
print(f"Total Net PnL: ${total_pnl:,.2f}")
<<<<<<< HEAD
print(
    f"Transaction cost drag: ${total_borrow + total_exit_cost:,.2f} ({(total_borrow + total_exit_cost) / 100000 * 100:.2f}% of capital)"
)

if wins:
    print(f"\nAvg winner PnL: ${sum(t['trade_pnl'] for t in wins) / len(wins):,.2f}")
    print(f"Max winner: ${max(t['trade_pnl'] for t in wins):,.2f}")
    print(f"Avg winner holding: {sum(t['holding_days'] for t in wins) / len(wins):.1f} days")
if losses:
    print(f"\nAvg loser PnL: ${sum(t['trade_pnl'] for t in losses) / len(losses):,.2f}")
    print(f"Max loser: ${min(t['trade_pnl'] for t in losses):,.2f}")
    print(f"Avg loser holding: {sum(t['holding_days'] for t in losses) / len(losses):.1f} days")
=======
print(f"Transaction cost drag: ${total_borrow + total_exit_cost:,.2f} ({(total_borrow + total_exit_cost)/100000*100:.2f}% of capital)")

if wins:
    print(f"\nAvg winner PnL: ${sum(t['trade_pnl'] for t in wins)/len(wins):,.2f}")
    print(f"Max winner: ${max(t['trade_pnl'] for t in wins):,.2f}")
    print(f"Avg winner holding: {sum(t['holding_days'] for t in wins)/len(wins):.1f} days")
if losses:
    print(f"\nAvg loser PnL: ${sum(t['trade_pnl'] for t in losses)/len(losses):,.2f}")
    print(f"Max loser: ${min(t['trade_pnl'] for t in losses):,.2f}")
    print(f"Avg loser holding: {sum(t['holding_days'] for t in losses)/len(losses):.1f} days")
>>>>>>> origin/main

# Win/Loss ratio
if wins and losses:
    avg_win = sum(t["trade_pnl"] for t in wins) / len(wins)
    avg_loss = abs(sum(t["trade_pnl"] for t in losses) / len(losses))
<<<<<<< HEAD
    print(f"\nPayoff ratio (avg win/avg loss): {avg_win / avg_loss:.2f}")
    print(f"Expected value per trade: ${total_pnl / len(trades):,.2f}")

# 2. By Pair Analysis
print(f"\n{'=' * 80}")
print("--- BY PAIR ANALYSIS ---")
pair_stats: dict[str, Any] = defaultdict(
    lambda: {"trades": 0, "wins": 0, "pnl": 0.0, "gross": 0.0, "costs": 0.0, "days": []}
)
=======
    print(f"\nPayoff ratio (avg win/avg loss): {avg_win/avg_loss:.2f}")
    print(f"Expected value per trade: ${total_pnl/len(trades):,.2f}")

# 2. By Pair Analysis
print(f"\n{'=' * 80}")
print(f"--- BY PAIR ANALYSIS ---")
pair_stats = defaultdict(lambda: {"trades": 0, "wins": 0, "pnl": 0.0, "gross": 0.0, "costs": 0.0, "days": []})
>>>>>>> origin/main
for t in trades:
    p = pair_stats[t["pair"]]
    p["trades"] += 1
    if t["trade_pnl"] > 0:
        p["wins"] += 1
    p["pnl"] += t["trade_pnl"]
    p["gross"] += t["pnl_gross"]
    p["costs"] += t["borrow_cost"] + t["exit_cost"]
    p["days"].append(t["holding_days"])

# Sort by PnL
sorted_pairs = sorted(pair_stats.items(), key=lambda x: x[1]["pnl"])
print(f"\n{'Pair':<15} {'Trades':>6} {'WinRate':>8} {'Gross PnL':>12} {'Costs':>10} {'Net PnL':>12} {'Avg Days':>9}")
print("-" * 75)
for pair, s in sorted_pairs:
    wr = s["wins"] / s["trades"] * 100
    avg_days = sum(s["days"]) / len(s["days"])
<<<<<<< HEAD
    print(
        f"{pair:<15} {s['trades']:>6} {wr:>7.1f}% ${s['gross']:>10,.2f} ${s['costs']:>8,.2f} ${s['pnl']:>10,.2f} {avg_days:>8.1f}"
    )

# 3. By Side Analysis
print(f"\n{'=' * 80}")
print("--- BY SIDE ANALYSIS ---")
=======
    print(f"{pair:<15} {s['trades']:>6} {wr:>7.1f}% ${s['gross']:>10,.2f} ${s['costs']:>8,.2f} ${s['pnl']:>10,.2f} {avg_days:>8.1f}")

# 3. By Side Analysis
print(f"\n{'=' * 80}")
print(f"--- BY SIDE ANALYSIS ---")
>>>>>>> origin/main
for side in ["long", "short"]:
    side_trades = [t for t in trades if t["side"] == side]
    if not side_trades:
        continue
    side_wins = [t for t in side_trades if t["trade_pnl"] > 0]
    side_pnl = sum(t["trade_pnl"] for t in side_trades)
<<<<<<< HEAD
    print(
        f"\n{side.upper()}: {len(side_trades)} trades, {len(side_wins)} wins ({len(side_wins) / len(side_trades) * 100:.1f}%), PnL: ${side_pnl:,.2f}"
    )

# 4. Holding Period Analysis
print(f"\n{'=' * 80}")
print("--- HOLDING PERIOD ANALYSIS ---")
=======
    print(f"\n{side.upper()}: {len(side_trades)} trades, {len(side_wins)} wins ({len(side_wins)/len(side_trades)*100:.1f}%), PnL: ${side_pnl:,.2f}")

# 4. Holding Period Analysis
print(f"\n{'=' * 80}")
print(f"--- HOLDING PERIOD ANALYSIS ---")
>>>>>>> origin/main
buckets = [(0, 3, "0-3 days"), (4, 7, "4-7 days"), (8, 14, "8-14 days"), (15, 30, "15-30 days"), (31, 999, "31+ days")]
for lo, hi, label in buckets:
    bucket_trades = [t for t in trades if lo <= t["holding_days"] <= hi]
    if not bucket_trades:
        continue
    bt_wins = [t for t in bucket_trades if t["trade_pnl"] > 0]
    bt_pnl = sum(t["trade_pnl"] for t in bucket_trades)
<<<<<<< HEAD
    print(
        f"{label:<12}: {len(bucket_trades):>3} trades, WR={len(bt_wins) / len(bucket_trades) * 100:>5.1f}%, PnL=${bt_pnl:>10,.2f}"
    )

# 5. Cost Analysis
print(f"\n{'=' * 80}")
print("--- COST IMPACT ANALYSIS ---")
=======
    print(f"{label:<12}: {len(bucket_trades):>3} trades, WR={len(bt_wins)/len(bucket_trades)*100:>5.1f}%, PnL=${bt_pnl:>10,.2f}")

# 5. Cost Analysis
print(f"\n{'=' * 80}")
print(f"--- COST IMPACT ANALYSIS ---")
>>>>>>> origin/main
# How many trades were profitable gross but unprofitable net?
cost_killed = [t for t in trades if t["pnl_gross"] > 0 and t["trade_pnl"] <= 0]
print(f"Trades profitable gross but killed by costs: {len(cost_killed)}")
for t in cost_killed:
<<<<<<< HEAD
    print(
        f"  {t['pair']} ({t['side']}): gross=${t['pnl_gross']:.2f}, costs=${t['borrow_cost'] + t['exit_cost']:.2f}, net=${t['trade_pnl']:.2f}"
    )

# 6. Top 10 Worst Trades
print(f"\n{'=' * 80}")
print("--- TOP 10 WORST TRADES ---")
worst = sorted(trades, key=lambda t: t["trade_pnl"])[:10]
for i, t in enumerate(worst, 1):
    print(
        f"{i}. {t['pair']} ({t['side']}): PnL=${t['trade_pnl']:,.2f} (gross=${t['pnl_gross']:,.2f}, borrow=${t['borrow_cost']:.2f}, exit=${t['exit_cost']:.2f}, {t['holding_days']}d)"
    )

# 7. Top 10 Best Trades
print("\n--- TOP 10 BEST TRADES ---")
best = sorted(trades, key=lambda t: t["trade_pnl"], reverse=True)[:10]
for i, t in enumerate(best, 1):
    print(
        f"{i}. {t['pair']} ({t['side']}): PnL=${t['trade_pnl']:,.2f} (gross=${t['pnl_gross']:,.2f}, borrow=${t['borrow_cost']:.2f}, exit=${t['exit_cost']:.2f}, {t['holding_days']}d)"
    )

# 8. Concentration Risk
print(f"\n{'=' * 80}")
print("--- CONCENTRATION RISK ---")
=======
    print(f"  {t['pair']} ({t['side']}): gross=${t['pnl_gross']:.2f}, costs=${t['borrow_cost']+t['exit_cost']:.2f}, net=${t['trade_pnl']:.2f}")

# 6. Top 10 Worst Trades
print(f"\n{'=' * 80}")
print(f"--- TOP 10 WORST TRADES ---")
worst = sorted(trades, key=lambda t: t["trade_pnl"])[:10]
for i, t in enumerate(worst, 1):
    print(f"{i}. {t['pair']} ({t['side']}): PnL=${t['trade_pnl']:,.2f} (gross=${t['pnl_gross']:,.2f}, borrow=${t['borrow_cost']:.2f}, exit=${t['exit_cost']:.2f}, {t['holding_days']}d)")

# 7. Top 10 Best Trades
print(f"\n--- TOP 10 BEST TRADES ---")
best = sorted(trades, key=lambda t: t["trade_pnl"], reverse=True)[:10]
for i, t in enumerate(best, 1):
    print(f"{i}. {t['pair']} ({t['side']}): PnL=${t['trade_pnl']:,.2f} (gross=${t['pnl_gross']:,.2f}, borrow=${t['borrow_cost']:.2f}, exit=${t['exit_cost']:.2f}, {t['holding_days']}d)")

# 8. Concentration Risk
print(f"\n{'=' * 80}")
print(f"--- CONCENTRATION RISK ---")
>>>>>>> origin/main
pair_pnl_sorted = sorted(pair_stats.items(), key=lambda x: x[1]["pnl"])
total_loss = sum(s["pnl"] for _, s in pair_pnl_sorted if s["pnl"] < 0)
top3_loss = sum(s["pnl"] for _, s in pair_pnl_sorted[:3])
print(f"Total loss from all losing pairs: ${total_loss:,.2f}")
<<<<<<< HEAD
print(
    f"Loss from 3 worst pairs: ${top3_loss:,.2f} ({top3_loss / total_loss * 100:.1f}% of total losses)"
    if total_loss != 0
    else ""
)

# 9. Partial profits and stops
print(f"\n{'=' * 80}")
print("--- RISK MANAGEMENT EVENTS ---")
=======
print(f"Loss from 3 worst pairs: ${top3_loss:,.2f} ({top3_loss/total_loss*100:.1f}% of total losses)" if total_loss != 0 else "")

# 9. Partial profits and stops
print(f"\n{'=' * 80}")
print(f"--- RISK MANAGEMENT EVENTS ---")
>>>>>>> origin/main
print(f"Partial profit takes: {len(partial_profits)}")
print(f"Stop triggers: {len(stops)}")
print(f"Trailing stops added: {len(trailing_stops)}")
if stops:
    stop_reasons = defaultdict(int)
    for _, reason in stops:
        stop_reasons[reason] += 1
    for reason, count in sorted(stop_reasons.items(), key=lambda x: -x[1]):
        print(f"  Stop reason '{reason}': {count}")

# 10. Repeat pair trading
print(f"\n{'=' * 80}")
<<<<<<< HEAD
print("--- REPEAT TRADING PATTERNS ---")
=======
print(f"--- REPEAT TRADING PATTERNS ---")
>>>>>>> origin/main
for pair, s in sorted_pairs:
    if s["trades"] >= 3:
        pair_trades = [t for t in trades if t["pair"] == pair]
        print(f"\n{pair} ({s['trades']} trades, net PnL=${s['pnl']:,.2f}):")
        for t in pair_trades:
            print(f"  {t['side']}: {t['holding_days']}d, gross=${t['pnl_gross']:,.2f}, net=${t['trade_pnl']:,.2f}")

# 11. Gross PnL distribution
print(f"\n{'=' * 80}")
<<<<<<< HEAD
print("--- GROSS PNL DISTRIBUTION ---")
gross_buckets = [
    (-10000, -5000),
    (-5000, -2000),
    (-2000, -1000),
    (-1000, 0),
    (0, 1000),
    (1000, 2000),
    (2000, 5000),
    (5000, 10000),
]
=======
print(f"--- GROSS PNL DISTRIBUTION ---")
gross_buckets = [(-10000, -5000), (-5000, -2000), (-2000, -1000), (-1000, 0), (0, 1000), (1000, 2000), (2000, 5000), (5000, 10000)]
>>>>>>> origin/main
for lo, hi in gross_buckets:
    count = len([t for t in trades if lo <= t["pnl_gross"] < hi])
    if count > 0:
        print(f"  ${lo:>7,} to ${hi:>7,}: {count} trades")

print(f"\n{'=' * 80}")
print("ANALYSIS COMPLETE")
