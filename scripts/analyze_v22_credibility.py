"""Analyse de cr├®dibilit├® du backtest v22"""

import os
import re
import statistics

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

with open(os.path.join(_ROOT, "results", "bt_results_v22.txt"), encoding="utf-16-le", errors="replace") as f:
    text = f.read()

# 1. Year-by-year equity
portfolio_vals = re.findall(r"date=(\d{4}-\d{2}-\d{2}).*?portfolio_value=([\d.]+)", text)
years = {}
for date, val in portfolio_vals:
    yr = date[:4]
    if yr not in years:
        years[yr] = []
    years[yr].append(float(val.replace(",", "")))

print("=== YEAR-BY-YEAR EQUITY ===")
prev_end = 100000
for yr in sorted(years.keys()):
    start_val = years[yr][0]
    end_val = years[yr][-1]
    yr_return = (end_val - prev_end) / prev_end * 100
    print(f"  {yr}: start={start_val:,.0f}  end={end_val:,.0f}  return={yr_return:+.1f}%")
    prev_end = end_val

# 2. Trade PnL distribution
trade_pnls = [float(m) for m in re.findall(r"trade_pnl=np\.float64\(([^)]+)\)", text)]
if not trade_pnls:
    trade_pnls = [float(m) for m in re.findall(r"trade_pnl=(-?[\d.]+)", text)]

mean_pnl: float = 0.0
total_profit: float = 0.0
if trade_pnls:
    sorted_pnls = sorted(trade_pnls, reverse=True)
    total_profit = sum(p for p in trade_pnls if p > 0)
    total_loss = sum(p for p in trade_pnls if p < 0)

    print("\n=== CONCENTRATION RISK ===")
    print(f"  Top 5 trades:    {[round(p) for p in sorted_pnls[:5]]}")
    print(f"  Bottom 5 trades: {[round(p) for p in sorted_pnls[-5:]]}")
    if total_profit > 0:
        top5_pct = sum(sorted_pnls[:5]) / total_profit * 100
        top10_pct = sum(sorted_pnls[:10]) / total_profit * 100
        print(f"  Top 5 = {top5_pct:.1f}% of total profit")
        print(f"  Top 10 = {top10_pct:.1f}% of total profit")

    # Outlier analysis
    mean_pnl = statistics.mean(trade_pnls)
    std_pnl = statistics.stdev(trade_pnls)
    outliers_3s = [p for p in trade_pnls if abs(p - mean_pnl) > 3 * std_pnl]
    print("\n=== STATISTICAL PROFILE ===")
    print(f"  Mean PnL: {mean_pnl:,.0f} EUR")
    print(f"  Median PnL: {statistics.median(trade_pnls):,.0f} EUR")
    print(f"  Std PnL: {std_pnl:,.0f} EUR")
    print(f"  3-sigma outliers: {len(outliers_3s)}")
    if outliers_3s:
        print(f"  Outlier values: {[round(o) for o in outliers_3s]}")

    # Profit without outliers
    non_outlier = [p for p in trade_pnls if abs(p - mean_pnl) <= 3 * std_pnl]
    print(f"  PnL sans outliers: {sum(non_outlier):,.0f} EUR ({len(non_outlier)} trades)")

    # Win/loss streaks
    streaks = []
    current = 0
    for p in trade_pnls:
        if p > 0:
            current = max(0, current) + 1
        else:
            current = min(0, current) - 1
        streaks.append(current)
    print("\n=== STREAKS ===")
    print(f"  Max win streak: {max(streaks)}")
    print(f"  Max loss streak: {abs(min(streaks))}")

# 3. Monthly trade distribution
trade_dates = re.findall(r"(\d{4}-\d{2}-\d{2}).*?trade_pnl", text)
months = {}
for d in trade_dates:
    m = d[:7]
    months[m] = months.get(m, 0) + 1
print("\n=== TRADE DISTRIBUTION ===")
print(f"  Active months: {len(months)}/60 ({100 * len(months) / 60:.0f}%)")
if months:
    print(f"  Max trades/month: {max(months.values())}")
    print(f"  Avg trades/active month: {sum(months.values()) / len(months):.1f}")

# 4. Pair diversity - which pairs generated trades?
pair_trades = re.findall(r"pair=([A-Z]+)/([A-Z]+)", text)
pair_counts = {}
for a, b in pair_trades:
    key = f"{a}/{b}"
    pair_counts[key] = pair_counts.get(key, 0) + 1
print("\n=== PAIR DIVERSITY ===")
print(f"  Unique pairs traded: {len(pair_counts)}")
for pair, count in sorted(pair_counts.items(), key=lambda x: -x[1])[:10]:
    print(f"    {pair}: {count} trades")

# 5. Holding period analysis
hold_days = [int(m) for m in re.findall(r"holding_days=(\d+)", text)]
if not hold_days:
    hold_days = [int(m) for m in re.findall(r"duration=(\d+)", text)]
if hold_days:
    print("\n=== HOLDING PERIODS ===")
    print(f"  Mean: {statistics.mean(hold_days):.1f} days")
    print(f"  Median: {statistics.median(hold_days):.0f} days")
    print(f"  Min: {min(hold_days)}, Max: {max(hold_days)}")

# 6. Key risk metrics check
print("\n=== CREDIBILITY CHECKLIST ===")
wins = [p for p in trade_pnls if p > 0]
losses = [p for p in trade_pnls if p < 0]
wr = len(wins) / len(trade_pnls) * 100 if trade_pnls else 0
wl_ratio = abs(statistics.mean(wins) / statistics.mean(losses)) if wins and losses else 0
annual_return = 62.44 / 5  # 5 years
print(f"  Annual return: ~{annual_return:.1f}%")
print(f"  Win rate: {wr:.1f}%")
print(f"  W/L ratio: {wl_ratio:.2f}")
print(f"  Expectancy/trade: {mean_pnl:,.0f} EUR")
print(f"  Total trades: {len(trade_pnls)} ({len(trade_pnls) / 60:.1f}/month)")
if total_profit > 0:
    edge = mean_pnl / abs(statistics.mean(losses)) if losses else 0
    print(f"  Edge ratio: {edge:.2f}")
