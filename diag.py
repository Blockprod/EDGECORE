"""Comprehensive backtest diagnostic — find all trade blockers."""
import re
import collections

# Read log from a pre-existing backtest run
with open('backtest_final.log', 'r', encoding='utf-16') as f:
    data = f.read()

# === SIGNAL GENERATION ===
signals = re.findall(r'pair_signal_generated\s+active_trades=(\d+)\s+pair=(\S+)\s+z_score=([-\d.eE+]+)', data)
print(f'Total signal events: {len(signals)}')

zvals = [abs(float(s[2])) for s in signals]
for thresh in [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]:
    n = sum(1 for z in zvals if z >= thresh)
    print(f'  |z| >= {thresh}: {n} ({100*n/len(zvals):.0f}%)')

# === Entry side signals from strategy ===
side_long = len(re.findall(r"side='long'", data)) + len(re.findall(r'side=long', data))
side_short = len(re.findall(r"side='short'", data)) + len(re.findall(r'side=short', data))
side_exit = len(re.findall(r"side='exit'", data)) + len(re.findall(r'side=exit', data))
print('\nStrategy signal sides:')
print(f'  Long:  {side_long}')
print(f'  Short: {side_short}')
print(f'  Exit:  {side_exit}')

# === REJECTIONS ===
patterns = {
    'spread_correlation_entry_rejected': 'Spread corr guard',
    'entry_rejected_spread_correlation': 'Spread corr (sim)',
    'entry_rejected_pca_factor': 'PCA factor guard',
    'entry_rejected_portfolio_heat': 'Portfolio heat',
    'entry_rejected_risk_engine': 'Risk engine',
    'entry_blocked_by_risk': 'Strategy risk limit',
    'time_stop_exit': 'Time stop exits',
    'pnl_stop_exit': 'PnL stop exits',
    'partial_profit_take': 'Partial takes',
    'partial_profit_remainder_exit': 'Partial remainder',
    'pairs_discovered': 'Discovery windows',
    'correlation_breakdown': 'Corr breakdown',
    '_excluded_pairs_correlation': 'Corr exclusion',
}
print('\n=== REJECTION/EVENT COUNTS ===')
for pat, label in patterns.items():
    c = len(re.findall(pat, data))
    if c > 0:
        print(f'  {label:30s}: {c}')

# === ACTIVE TRADES DISTRIBUTION ===
at = re.findall(r'active_trades=(\d+)', data)
dist = collections.Counter(at)
print('\n=== ACTIVE TRADES DISTRIBUTION ===')
for k in sorted(dist.keys(), key=int):
    print(f'  active={k}: {dist[k]} bars')

# === PAIR DISCOVERY ===
disc = re.findall(r'pairs_found=(\d+)', data)
disc_ints = [int(d) for d in disc]
if disc_ints:
    print('\n=== PAIR DISCOVERY ===')
    print(f'  Windows: {len(disc_ints)}')
    print(f'  Mean pairs/window: {sum(disc_ints)/len(disc_ints):.1f}')
    print(f'  Max: {max(disc_ints)}, Min: {min(disc_ints)}')
    print(f'  Windows with 0 pairs: {sum(1 for d in disc_ints if d==0)}')

# === TRADE P&Ls ===
pnls = re.findall(r'trade_pnl=([-\d.]+)', data)
if pnls:
    print(f'\n=== TRADE PnLs ({len(pnls)} trades) ===')
    wins = [float(p) for p in pnls if float(p) > 0]
    losses = [float(p) for p in pnls if float(p) <= 0]
    for i, p in enumerate(pnls):
        print(f'  Trade {i+1:>2d}: {float(p):>+8.2f} EUR')
    print('  ---')
    print(f'  Total PnL: {sum(float(p) for p in pnls):>+8.2f} EUR')
    print(f'  Avg win:   {sum(wins)/len(wins):>+8.2f} EUR ({len(wins)} trades)' if wins else '  No wins')
    print(f'  Avg loss:  {sum(losses)/len(losses):>+8.2f} EUR ({len(losses)} trades)' if losses else '  No losses')

# === FINAL ===
m = re.search(r'final_portfolio=([\d.]+).*total_return=([\d.]+%?).*total_trades=(\d+)', data)
if m:
    print(f'\nFinal: portfolio={m.group(1)}, return={m.group(2)}, trades={m.group(3)}')

# === KEY INSIGHT ===
print('\n=== KEY INSIGHT ===')
total_qualifying = sum(1 for z in zvals if z >= 1.0)
print(f'  Qualifying z-scores (|z|>=1.0): {total_qualifying}')
print(f'  Actual strategy entries (long+short): {side_long + side_short}')
print(f'  Conversion rate: {100*(side_long+side_short)/total_qualifying:.1f}%' if total_qualifying else '  N/A')
# How many qualifying happened with 0 active trades?
qual_at_0 = sum(1 for at_str, pair, z in signals if int(at_str) == 0 and abs(float(z)) >= 1.0)
print(f'  Qualifying at active=0: {qual_at_0}')
print(f'  => {total_qualifying - qual_at_0} blocked because pair already active')
