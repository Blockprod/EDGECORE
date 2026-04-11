"""Temporary diagnostic: find what blocks entry generation in W2."""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from execution.time_stop import TimeStopConfig, TimeStopManager
from risk.spread_correlation import SpreadCorrelationConfig, SpreadCorrelationGuard
from scripts.run_v54_wf3_bl import _apply_settings_v54, WF_SYMBOLS, WF_WINDOWS, WF_SECTOR_MAP
from backtests.runner import BacktestRunner
from strategies import pair_trading as pt

_apply_settings_v54()

_blocked_log: list = []

orig_check = pt.PairTradingStrategy._check_internal_risk_limits


def patched_check(self):
    ok, reason = orig_check(self)
    if not ok and len(_blocked_log) < 20:
        _blocked_log.append(
            f"peak={self.peak_equity:.0f} current={self.current_equity:.0f} "
            f"dd={(self.peak_equity - self.current_equity) / self.peak_equity * 100:.1f}% "
            f"limit={self.max_drawdown_pct * 100:.0f}% reason={reason}"
        )
    return ok, reason


pt.PairTradingStrategy._check_internal_risk_limits = patched_check

window = WF_WINDOWS[1]  # W2
label, train_start, train_end, oos_start, oos_end = window
print(f"Running W2: {label} OOS={oos_start} -> {oos_end}", flush=True)

ts60 = TimeStopManager(TimeStopConfig(half_life_multiplier=2.0, max_days_cap=60, default_max_bars=60))
spread_guard = SpreadCorrelationGuard(SpreadCorrelationConfig(max_correlation=0.80, min_overlap_bars=20))

runner = BacktestRunner()
runner.config.initial_capital = 100_000
t0 = time.time()
result = runner.run_unified(
    symbols=WF_SYMBOLS,
    start_date=train_start,
    end_date=oos_end,
    oos_start_date=oos_start,
    sector_map=WF_SECTOR_MAP,
    pair_rediscovery_interval=2,
    allocation_per_pair_pct=50.0,
    max_position_loss_pct=0.07,
    max_portfolio_heat=3.0,
    time_stop=ts60,
    leverage_multiplier=2.5,
    momentum_filter=None,
    spread_corr_guard=spread_guard,
    validate_data=False,
)
elapsed = int(time.time() - t0)
print(f"OOS trades={result.total_trades} Sharpe={result.sharpe_ratio:.3f} [{elapsed}s]", flush=True)

# Print first/last 10 blocks
total_blocks = len(_blocked_log)
print(f"\nTotal blocked calls captured (cap=20): {total_blocks}", flush=True)
for line in _blocked_log[:10]:
    print(f"  [BLOCK] {line}", flush=True)
print("  ...")
for line in _blocked_log[-5:]:
    print(f"  [BLOCK] {line}", flush=True)
