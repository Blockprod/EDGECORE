<<<<<<< HEAD
﻿# Operations Runbook
=======
# Operations Runbook
>>>>>>> origin/main

**Version**: 3.0 (Post-S3.2 Half-Life Refinement)  
**Last Updated**: February 12, 2026  
**Audience**: Operations team, developers, risk managers

---

<<<<<<< HEAD
## ­ƒôï Table of Contents
=======
## 📋 Table of Contents
>>>>>>> origin/main

1. [Quick Diagnostics](#quick-diagnostics)
2. [Common Issues & Solutions](#common-issues--solutions)
3. [Performance Monitoring](#performance-monitoring)
4. [Emergency Procedures](#emergency-procedures)
5. [Daily Operations Checklist](#daily-operations-checklist)
6. [Data Troubleshooting](#data-troubleshooting)

---

<<<<<<< HEAD
## ­ƒöì Quick Diagnostics
=======
## 🔍 Quick Diagnostics
>>>>>>> origin/main

### System Health Check

Run this to verify all systems operational:

```bash
#!/bin/bash
# Run from EDGECORE root directory

echo "=== EDGECORE System Diagnostics ==="

# 1. Python environment
python --version
<<<<<<< HEAD
pip show edgecore 2>/dev/null || echo "ÔÜá´©Å  EDGECORE package not installed"

# 2. Dependencies
python -c "import pandas, numpy, IBKR API, pytest; print('Ô£ô All dependencies installed')"

# 3. Configuration
python -c "from config.settings import get_settings; s = get_settings(); print(f'Ô£ô Config loaded, env={s.env}, symbols={len(s.trading_universe.symbols)}')"

# 4. Data
if [ -d "data" ] && [ -f "data/loader.py" ]; then
    echo "Ô£ô Data module available"
else
    echo "ÔÜá´©Å  Data module missing"
=======
pip show edgecore 2>/dev/null || echo "⚠️  EDGECORE package not installed"

# 2. Dependencies
python -c "import pandas, numpy, IBKR API, pytest; print('✓ All dependencies installed')"

# 3. Configuration
python -c "from config.settings import get_settings; s = get_settings(); print(f'✓ Config loaded, env={s.env}, symbols={len(s.trading_universe.symbols)}')"

# 4. Data
if [ -d "data" ] && [ -f "data/loader.py" ]; then
    echo "✓ Data module available"
else
    echo "⚠️  Data module missing"
>>>>>>> origin/main
fi

# 5. Tests
python -m pytest tests/ --collect-only -q 2>/dev/null | tail -1

# 6. Logs
if [ -d "logs" ]; then
<<<<<<< HEAD
    echo "Ô£ô Logs directory exists"
    tail -5 logs/*.log 2>/dev/null | grep -i error | head -3 || echo "  No recent errors"
else
    echo "ÔÜá´©Å  Logs directory not found"
=======
    echo "✓ Logs directory exists"
    tail -5 logs/*.log 2>/dev/null | grep -i error | head -3 || echo "  No recent errors"
else
    echo "⚠️  Logs directory not found"
>>>>>>> origin/main
fi

echo "=== Diagnostics Complete ==="
```

### Database Connection Check

```python
from config.settings import get_settings
from data.loader import DataLoader

settings = get_settings()
loader = DataLoader(settings)

# Test connection to data store
try:
    symbols = loader.get_symbols()
<<<<<<< HEAD
    print(f"Ô£ô Data connection OK ({len(symbols)} symbols available)")
except Exception as e:
    print(f"Ô£ù Data connection FAILED: {e}")
=======
    print(f"✓ Data connection OK ({len(symbols)} symbols available)")
except Exception as e:
    print(f"✗ Data connection FAILED: {e}")
>>>>>>> origin/main
```

---

<<<<<<< HEAD
## ­ƒÉø Common Issues & Solutions
=======
## 🐛 Common Issues & Solutions
>>>>>>> origin/main

### Issue 1: "No pairs found in discovery"

**Symptoms**:
- Pair discovery returns 0 pairs
- Log says: `pair_discovery_bonferroni: candidates=0, confirmed=0`

**Root Causes** (Check in Order):

1. **Insufficient Data History**
   ```bash
   # Check minimum data points
   python -c "from data.loader import DataLoader; dl = DataLoader(); 
              lengths = {s: len(dl.get_prices(s)) for s in dl.get_symbols()[:3]};
              print(lengths);
              print(f'Min required: 252 bars, Min found: {min(lengths.values())}')"
   ```
   
<<<<<<< HEAD
   **Solution**: Ensure data directory has ÔëÑ252 days of OHLCV data
=======
   **Solution**: Ensure data directory has ≥252 days of OHLCV data
>>>>>>> origin/main
   ```bash
   # Reload fresh data
   python scripts/fetch_data.py --lookback 365
   ```

2. **Bonferroni Alpha Too Strict**
   ```python
   # Current alpha calculation
   n_symbols = 100
   n_pairs = n_symbols * (n_symbols - 1) / 2  # 4,950 pairs
<<<<<<< HEAD
   alpha_corrected = 0.05 / n_pairs  # Ôëê 0.000010 (very strict!)
=======
   alpha_corrected = 0.05 / n_pairs  # ≈ 0.000010 (very strict!)
>>>>>>> origin/main
   ```
   
   **Solution**: Reduce symbol count
   ```yaml
   # config/dev.yaml
   strategy:
<<<<<<< HEAD
     num_symbols: 20  # Reduces pairs to 190, alpha Ôëê 0.0003 (more reasonable)
=======
     num_symbols: 20  # Reduces pairs to 190, alpha ≈ 0.0003 (more reasonable)
>>>>>>> origin/main
   ```

3. **Universe Symbols Missing from Data**
   ```bash
   # Check which symbols have data
   python -c "from data.loader import DataLoader; dl = DataLoader();
              symbols_with_data = [s for s in dl.get_symbols() 
                                  if len(dl.get_prices(s)) > 0];
              print(f'Symbols with data: {len(symbols_with_data)}')"
   ```
   
   **Solution**: Update symbol list
   ```yaml
   # config/test.yaml
   symbols: [AAPL, MSFT, GOOGL, ...]  # Only symbols with data
   ```

4. **Data Quality Issue (NaN, Infinite Values)**
   ```python
   # Detect data quality problems
   from data.validators import DataValidator
   validator = DataValidator()
   
   for symbol in symbols[:5]:
       prices = loader.get_prices(symbol)
       issues = validator.validate(prices)
       if issues:
<<<<<<< HEAD
           print(f"ÔÜá´©Å  {symbol}: {issues}")
=======
           print(f"⚠️  {symbol}: {issues}")
>>>>>>> origin/main
   ```
   
   **Solution**: Clean data
   ```bash
   python scripts/clean_data.py --remove-nulls --remove-inf
   ```

**Quick Fix** (Try First):
```python
# Relax Bonferroni temporarily to test
from strategies.pair_discovery import find_cointegrated_pairs

pairs = find_cointegrated_pairs(symbols, use_bonferroni=False)
print(f"Without Bonferroni: {len(pairs)} pairs found")

pairs = find_cointegrated_pairs(symbols, use_bonferroni=True)
print(f"With Bonferroni: {len(pairs)} pairs found")

# If large difference, data quality likely fine, adjust config instead
```

---

### Issue 2: "Pair trading but losing money"

**Symptoms**:
- Strategy signals are active
- Positions open and close
- P&L negative overall

**Root Causes** (In Order of Likelihood):

1. **Unrealistic Cost Assumptions**
   ```python
   # Check actual execution costs
   from execution.IBKR API_engine import IBKR APIEngine
   
   engine = IBKR APIEngine()
   
   # IBKR spot taker fee: 0.1%
   # Actual slippage: 5-20 bps (depends on volume)
   # Round-trip cost: 40-50 bps
   
   # But backtest assumes only 25 bps!
   ```
   
   **Solution**: Adjust cost assumptions
   ```yaml
   # config/backtest.yaml
   execution:
       slippage_bps: 5        # Change TO 10-15 for realistic
       commission_rate: 0.001 # Reduce TO 0.002 for 0.2% (taker fee)
       # Total: 30-35 bps realistic, not 25 bps
   ```

2. **Regime Detection Killing Profitable Pairs**
   ```python
   # Check if regime is triggering incorrectly
   from monitoring.alerter import RegimeDetector
   
   detector = RegimeDetector()
   regime_history = detector.get_regime_history()
   
   # Should show NORMAL regime >70% of time
   normal_pct = (regime_history == 'NORMAL').sum() / len(regime_history)
   print(f"Normal regime: {normal_pct:.1%}")
   
   if normal_pct < 0.7:
<<<<<<< HEAD
       print("ÔÜá´©Å  Regime detector too sensitive, killing trades")
=======
       print("⚠️  Regime detector too sensitive, killing trades")
>>>>>>> origin/main
   ```
   
   **Solution**: Reduce regime sensitivity
   ```yaml
   strategy:
       regime_detection_enabled: false  # Disable to test
   ```

3. **Z-Score Threshold Too Low (Too Many False Signals)**
   ```python
   # Check signal win rate
   results_df = backtest_results['positions']
   
   winning = results_df[results_df['pnl'] > 0]
   losing = results_df[results_df['pnl'] < 0]
   
   win_rate = len(winning) / (len(winning) + len(losing))
   print(f"Win rate: {win_rate:.1%}")
   
   if win_rate < 0.50:
<<<<<<< HEAD
       print("ÔÜá´©Å  Win rate <50%, threshold too low")
=======
       print("⚠️  Win rate <50%, threshold too low")
>>>>>>> origin/main
   ```
   
   **Solution**: Increase entry threshold
   ```yaml
   strategy:
       entry_z_score: 2.2     # FROM 2.0
   ```

4. **Half-Life Estimation Wrong (Adaptive Window Incorrect)**
   ```python
   # Check if estimated half-lives are reasonable
   from models.half_life_estimator import SpreadHalfLifeEstimator
   
   estimator = SpreadHalfLifeEstimator()
   
   for pair in discovered_pairs:
       spread = compute_spread(pair)
       hl = estimator.estimate_half_life_from_spread(spread)
       
       if hl is None:
<<<<<<< HEAD
           print(f"ÔÜá´©Å  {pair}: No HL (possibly non-stationary)")
       elif hl > 100:
           print(f"ÔÜá´©Å  {pair}: HL={hl}d too slow, high overnight risk")
       else:
           print(f"Ô£ô {pair}: HL={hl}d acceptable")
=======
           print(f"⚠️  {pair}: No HL (possibly non-stationary)")
       elif hl > 100:
           print(f"⚠️  {pair}: HL={hl}d too slow, high overnight risk")
       else:
           print(f"✓ {pair}: HL={hl}d acceptable")
>>>>>>> origin/main
   ```
   
   **Solution**: Adjust half-life bounds
   ```yaml
   strategy:
       discovery:
           max_half_life_days: 50  # FROM 60 (require faster reversion)
   ```

**Comprehensive Diagnosis**:
```python
# Run this to identify root cause
python scripts/diagnose_poor_returns.py --backtest_results results.parquet

# Outputs:
# 1. Win rate analysis (vs threshold sensitivity)
# 2. Cost impact analysis (vs backtest cost)
# 3. Regime kill-switch impact (% of exits due to regime)
# 4. Half-life reversion accuracy (vs estimated HL)
```

---

### Issue 3: "Drawdown exceeding -3%"

**Symptoms**:
- Portfolio down >3%
- Risk engine should have stopped at -2%

**Root Causes**:

1. **Risk Engine Not Configured**
   ```python
   from config.settings import get_settings
   
   settings = get_settings()
   if settings.risk.daily_loss_kill_switch_enabled:
       threshold = settings.risk.max_daily_loss_pct
<<<<<<< HEAD
       print(f"Ô£ô Kill-switch enabled at {threshold:.1%}")
   else:
       print("ÔÜá´©Å  Kill-switch DISABLED - drawdown unprotected!")
=======
       print(f"✓ Kill-switch enabled at {threshold:.1%}")
   else:
       print("⚠️  Kill-switch DISABLED - drawdown unprotected!")
>>>>>>> origin/main
   ```
   
   **Solution**: Enable kill-switch
   ```yaml
   risk:
       daily_loss_kill_switch_enabled: true
       max_daily_loss_pct: -0.02  # -2% (dev) or -0.01 (live)
   ```

2. **Kill-Switch Reset Not Working**
   ```python
   # Check if daily loss is properly reset
   from monitoring.risk_engine import RiskEngine
   
   engine = RiskEngine()
   daily_pnl = engine.get_daily_pnl()
   
   print(f"Daily P&L: {daily_pnl:.2%}")
   print(f"Threshold: {engine.max_daily_loss_pct:.2%}")
   
   if daily_pnl < engine.max_daily_loss_pct:
<<<<<<< HEAD
       print("Ô£ô Kill-switch should be active")
   else:
       print("ÔÜá´©Å  Kill-switch not active (threshold not breached)")
=======
       print("✓ Kill-switch should be active")
   else:
       print("⚠️  Kill-switch not active (threshold not breached)")
>>>>>>> origin/main
   ```
   
   **Solution**: Check reset schedule
   ```python
   # Reset should happen at UTC 00:00
   if pd.Timestamp.utcnow().time() > pd.Timestamp('23:59').time():
       engine.reset_daily_loss()  # Manual reset if needed
   ```

3. **Overnight Gap (Gap Down on Open)**
   ```python
   # Check for large overnight moves
   prices = loader.get_prices('AAPL')
   
   overnight_gaps = prices['open'] - prices['close'].shift(1)
   large_gaps = overnight_gaps[abs(overnight_gaps / prices['close'].shift(1)) > 0.02]
   
   print(f"Large overnight gaps ({len(large_gaps)}): {large_gaps.head()}")
   
   if len(large_gaps) > 0:
<<<<<<< HEAD
       print("ÔÜá´©Å  Large overnight gaps detected - may exceed kill-switch")
=======
       print("⚠️  Large overnight gaps detected - may exceed kill-switch")
>>>>>>> origin/main
   ```
   
   **Solution**: Close positions before market close
   ```yaml
   strategy:
       force_close_before_market_close: true  # Close all before UTC 21:00
   ```

**Emergency Procedure**:
```bash
# If drawdown exceeds -5%, immediately:

# 1. Stop further trading
pkill -f "python main.py --mode live"

# 2. Close all positions manually
python scripts/force_close_all.py

# 3. Review what happened
python scripts/analyze_drawdown.py --last_24_hours

# 4. Post-mortem
# - Check logs for error messages
# - Verify risk configuration
# - Get approval before resuming
```

---

### Issue 4: "Position not closing on mean reversion"

**Symptoms**:
- Z-score falls below exit threshold
- Position remains open
- Large P&L swing afterwards

**Root Causes**:

1. **Z-Score Window Too Large**
   ```python
   # Check if window is capturing mean reversion
   from models.spread import SpreadModel
   
   spread_model = SpreadModel(Y, X)
   print(f"Estimated half-life: {spread_model.half_life}d")
   print(f"Z-score window: {spread_model.z_score_lookback}d")
   
   # Window should be 2x-3x half-life for smooth signals
   if spread_model.z_score_lookback > spread_model.half_life * 3:
<<<<<<< HEAD
       print("ÔÜá´©Å  Window too large, signals laggy")
=======
       print("⚠️  Window too large, signals laggy")
>>>>>>> origin/main
   ```
   
   **Solution**: Use estimated half-life properly
   ```yaml
   # Ensure S3.2 half-life is being used
   strategy:
       half_life:
           z_window_multiplier: 1  # Use actual HL, not fixed window
   ```

2. **Exit Threshold Too Low**
   ```python
   # Check exit frequency
   positions_df = backtest_results['positions']
   exit_reasons = positions_df['exit_reason'].value_counts()
   
   print(exit_reasons)
   
   if 'mean_reversion' in exit_reasons:
       mr_exits = exit_reasons['mean_reversion']
       total_exits = exit_reasons.sum()
       mr_pct = mr_exits / total_exits
       
       if mr_pct < 0.6:
<<<<<<< HEAD
           print(f"ÔÜá´©Å  Only {mr_pct:.0%} exits on mean reversion (should be >60%)")
=======
           print(f"⚠️  Only {mr_pct:.0%} exits on mean reversion (should be >60%)")
>>>>>>> origin/main
   ```
   
   **Solution**: Increase exit threshold
   ```yaml
   strategy:
       exit_z_score: 1.0  # FROM 0.5 (less reactive)
   ```

3. **Spread Not Mean-Reverting (Half-Life Invalid)**
   ```python
   # Validate mean reversion
   from models.half_life_estimator import SpreadHalfLifeEstimator
   
   estimator = SpreadHalfLifeEstimator()
   spread = compute_spread(Y, X)
   
   is_mr = estimator.validate_mean_reversion(spread)
   if not is_mr:
<<<<<<< HEAD
       print(f"ÔÜá´©Å  Spread NOT mean-reverting, HL estimation unreliable")
=======
       print(f"⚠️  Spread NOT mean-reverting, HL estimation unreliable")
>>>>>>> origin/main
   ```
   
   **Solution**: Filter pairs better
   ```yaml
   strategy:
       discovery:
           min_correlation: 0.8  # FROM 0.7 (stronger cointegration)
           max_half_life_days: 50 # FROM 60 (faster mean-reversion)
   ```

---

### Issue 5: "API Connection Timeout"

**Symptoms**:
- logs say: `ConnectionError: [Errno 110] Connection timed out`
- Unable to place or cancel orders

**Root Causes**:

1. **Network Issues**
   ```bash
   # Test connectivity
   ping google.com        # General connectivity
   ping api.IBKR.com   # IBKR API
   curl -I https://api.IBKR.com/api/v3/ping
   ```
   
   **Solution**: Check network
   ```bash
   # Restart network
   sudo systemctl restart networking
   
   # Or check ISP status
   # IBKR status: https://status.IBKR.com/
   ```

2. **IBKR API Rate Limit**
   ```python
   # Check API call frequency
   from common.retry import RateLimitManager
   
   limiter = RateLimitManager()
   print(f"API calls last minute: {limiter.get_call_count()}")
   print(f"Rate limit: {limiter.rate_limit}")
   
   if limiter.get_call_count() > limiter.rate_limit * 0.8:
<<<<<<< HEAD
       print("ÔÜá´©Å  Approaching rate limit")
=======
       print("⚠️  Approaching rate limit")
>>>>>>> origin/main
   ```
   
   **Solution**: Reduce API calls
   ```yaml
   execution:
       order_timeout_seconds: 60  # Increase from 30 (less retries)
       position_cache_ttl: 300    # Cache positions 5 min instead of 1 min
   ```

3. **VPN/Proxy Issue**
   ```bash
   # Check IP (verify not blocked)
   curl ipinfo.io
   
   # If IP in restricted list, change VPN
   ```
   
   **Solution**: Use appropriate networking
   ```bash
   # Run from dedicated server (not home WiFi)
   # Use VPN if IBKR blocks your country
   ```

**Recovery**:
```bash
# Automatic retry (should happen in code)
# If manual restart needed:
python main.py --mode live --resume_from_checkpoint

# Finds last position checkpoint and resumes from there
```

---

<<<<<<< HEAD
## ­ƒôè Performance Monitoring
=======
## 📊 Performance Monitoring
>>>>>>> origin/main

### Daily Metrics Dashboard

```python
#!/usr/bin/env python3
"""Print daily performance summary"""

from monitoring.alerter import StrategyMonitor
from execution.backtest_execution import BacktestRunner
import pandas as pd

monitor = StrategyMonitor()

# Get todays metrics
today_trades = monitor.get_today_trades()
daily_pnl = today_trades['pnl'].sum()
win_count = (today_trades['pnl'] > 0).sum()
total_count = len(today_trades)

print(f"""
<<<<<<< HEAD
ÔòöÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòù
Ôòæ  EDGECORE Daily Summary ({pd.Timestamp.utcnow().date()})         
ÔòáÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòú
Ôòæ  Total Trades:        {total_count:5d}                   
Ôòæ  Winning Trades:      {win_count:5d} ({win_count/total_count*100:5.1f}%)              
Ôòæ  Daily P&L:           ${daily_pnl:10,.2f}         
Ôòæ  Return:              {daily_pnl / monitor.portfolio_value * 100:5.2f}%               
Ôòæ  
Ôòæ  Open Positions:      {len(monitor.get_open_positions()):5d}                   
Ôòæ  Max Drawdown Today:  {monitor.get_daily_drawdown():5.2f}%              
Ôòæ  Sharpe (30-day):     {monitor.get_sharpe_30d():5.2f}                 
ÔòÜÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòØ
=======
╔════════════════════════════════════════════╗
║  EDGECORE Daily Summary ({pd.Timestamp.utcnow().date()})         
╠════════════════════════════════════════════╣
║  Total Trades:        {total_count:5d}                   
║  Winning Trades:      {win_count:5d} ({win_count/total_count*100:5.1f}%)              
║  Daily P&L:           ${daily_pnl:10,.2f}         
║  Return:              {daily_pnl / monitor.portfolio_value * 100:5.2f}%               
║  
║  Open Positions:      {len(monitor.get_open_positions()):5d}                   
║  Max Drawdown Today:  {monitor.get_daily_drawdown():5.2f}%              
║  Sharpe (30-day):     {monitor.get_sharpe_30d():5.2f}                 
╚════════════════════════════════════════════╝
>>>>>>> origin/main
""")

# Alert if issues
if daily_pnl < monitor.max_daily_loss_pct * monitor.portfolio_value:
<<<<<<< HEAD
    print(f"­ƒÜ¿ ALERT: Daily loss limit reached! P&L={daily_pnl:.2f}")

if len(monitor.get_open_positions()) > monitor.max_concurrent_positions:
    print(f"ÔÜá´©Å  WARNING: {len(monitor.get_open_positions())} positions (limit={monitor.max_concurrent_positions})")
=======
    print(f"🚨 ALERT: Daily loss limit reached! P&L={daily_pnl:.2f}")

if len(monitor.get_open_positions()) > monitor.max_concurrent_positions:
    print(f"⚠️  WARNING: {len(monitor.get_open_positions())} positions (limit={monitor.max_concurrent_positions})")
>>>>>>> origin/main
```

### Key Metrics to Monitor

| Metric | Target | Warning | Critical |
|--------|--------|---------|----------|
| Win Rate | 55-65% | <50% | <40% |
| Sharpe (24h) | >1.0 | <0.5 | <0.0 |
| Max Drawdown | <-3% | <-4% | <-5% |
| Avg Trade Duration | 5-15 days | >20 days | >30 days |
<<<<<<< HEAD
| Open Positions | Ôëñ5-10 | >12 | >15 |
=======
| Open Positions | ≤5-10 | >12 | >15 |
>>>>>>> origin/main
| Daily Loss % | -0.5% to +0.5% | <-1% | <-2% |

### Automated Alerts

```bash
# Setup Slack notifications (in config/prod.yaml)
monitoring:
  slack_notification_enabled: true
  slack_webhook: ${SLACK_WEBHOOK_URL}
  
  # Alert on these events:
  alerts:
    - daily_loss_threshold_breach  # When -1% hit
    - position_count_limit         # When >5 positions
    - regime_change_detected       # When decorrelation starts
    - api_connection_failure       # When broker unreachable
    - backtest_completion          # When backtest finishes

# Check Slack channel: #edgecore-trading
```

---

<<<<<<< HEAD
## ­ƒÜ¿ Emergency Procedures
=======
## 🚨 Emergency Procedures
>>>>>>> origin/main

### Scenario 1: Market Crash (-10%+ in 1 hour)

**Immediate (< 1 minute)**:
```bash
# 1. Stop all trading instantly
pkill -f "python main.py --mode live"

# 2. Check status
ps aux | grep edgecore  # Verify process killed
```

**Assessment (1-5 minutes)**:
```bash
# 3. Check current positions
python scripts/emergency_status.py

# Outputs:
# - What positions are open
# - Current P&L estimates
# - Risk limit breaches
```

**Recovery (5-30 minutes)**:
```bash
# 4. Manual position review
python scripts/review_positions.py --manual

# 5. Close positions manually if needed
python scripts/force_close.py --symbol AAPL --amount 0.5

# 6. Resume trading only after approval
python main.py --mode live --dry-run  # Test first
```

**Post-Mortem**:
```bash
# 7. Analyze what happened
python scripts/analyze_incident.py --time_window 1h

# Review logs
tail -100 logs/live_trading.log | grep ERROR
```

### Scenario 2: Data Feed Interrupted (No prices for 30+ min)

**Detection**:
```python
from data.validators import DataValidator

validator = DataValidator()
if not validator.is_data_current(tolerance_minutes=5):
<<<<<<< HEAD
    print("ÔÜá´©Å  Data is stale!")
=======
    print("⚠️  Data is stale!")
>>>>>>> origin/main
```

**Response**:
```bash
# 1. Check data source
curl "https://api.IBKR.com/api/v3/ticker/price?symbol=BTCUSDT" | jq

# 2. Restart data loader
python scripts/restart_data_service.py

# 3. Wait for data to catch up (5 min max)
sleep 300

# 4. Resume trading
python main.py --mode live

# 5. If still down: STOP and investigate
# - Check IBKR status: https://status.IBKR.com/
# - Check network: `ping api.IBKR.com`
# - Check firewall/vpn
```

### Scenario 3: Stuck Position (Won't Close)

**Diagnosis**:
```python
from execution.order_lifecycle import OrderManager

om = OrderManager()
stuck_positions = om.get_stuck_orders(timeout_minutes=30)

for pos in stuck_positions:
    print(f"Position {pos['pair']} stuck for {pos['duration_min']} minutes")
    print(f"Last order ID: {pos['order_id']}")
```

**Recovery**:
```bash
# 1. Cancel order on broker directly
curl -X DELETE "https://api.IBKR.com/api/v3/openOrders" \
  -H "X-MBX-APIKEY: ${IBKR_API_KEY}" \
  -d "symbol=BTCUSDT"

# 2. Close position manually with market order
python scripts/emergency_close.py --position_id 12345 --market_order

# 3. Log incident for review
python scripts/log_incident.py --category stuck_position --position 12345
```

---

<<<<<<< HEAD
## Ô£à Daily Operations Checklist
=======
## ✅ Daily Operations Checklist
>>>>>>> origin/main

### Before Market Open (UTC 23:50 - 00:00)

- [ ] Check system uptime: `uptime`
- [ ] Verify data fresh: `python scripts/check_data_age.py`
- [ ] Review overnight logs for errors: `grep ERROR logs/live_trading.log | tail -5`
- [ ] Check open positions: `python scripts/list_positions.py`
- [ ] Verify risk limits: `python scripts/check_risk_limits.py`
- [ ] Test Slack notifications: Manually send test message
- [ ] Backup data: `tar -czf backup/$(date +%Y%m%d).tar.gz data/`

### During Trading Hours

- [ ] **Hourly**: Check Slack alerts for warnings
- [ ] **Every 4 hours**: Review backtest results
- [ ] **Every 8 hours**: Check system resource usage (disk, CPU, RAM)
- [ ] **Random check**: Verify position P&L matches calculations

### After Market Close (UTC 18:00-19:00)

- [ ] Generate daily report: `python scripts/daily_report.py --date $(date +%Y-%m-%d)`
- [ ] Archive logs: `gzip logs/live_trading.log-$(date +%Y%m%d)`
- [ ] Verify all positions closed: Should be 0 open positions
- [ ] Check kill-switch reset: `python scripts/verify_reset.py`
- [ ] Review P&L vs. model predictions
- [ ] Schedule data refresh: `python scripts/fetch_data.py --schedule tomorrow 02:00`

---

<<<<<<< HEAD
## ­ƒöº Data Troubleshooting
=======
## 🔧 Data Troubleshooting
>>>>>>> origin/main

### Data Missing for a Symbol

```python
from data.loader import DataLoader
loader = DataLoader()

symbol = 'MS'
prices = loader.get_prices(symbol)

if len(prices) == 0 or prices.isnull().all():
<<<<<<< HEAD
    print(f"ÔÜá´©Å  No data for {symbol}")
=======
    print(f"⚠️  No data for {symbol}")
>>>>>>> origin/main
    
    # Solution 1: Fetch from IBKR
    python scripts/fetch_data.py --symbols MS --lookback 365
    
    # Solution 2: Use proxy symbol (similar behavior)
    # Substitute DOGE with BAC if DOGE unavailable
```

### Data Quality Issues (NaN, Inf, Duplicates)

```python
from data.validators import DataValidator

validator = DataValidator()
issues = validator.validate_all_symbols()

for symbol, problems in issues.items():
    if problems:
        print(f"{symbol}: {problems}")
        
        # Fix
        python scripts/clean_data.py --symbol {symbol} \
            --remove-nulls --remove-inf --remove-duplicates
```

### Unusual Price Spikes

```python
from risk.monitors import PriceAnomalyDetector

detector = PriceAnomalyDetector()
anomalies = detector.detect_all()

for symbol, anomaly_list in anomalies.items():
    for anomaly in anomaly_list:
        print(f"{symbol} {anomaly['time']}: {anomaly['type']} " \
              f"({anomaly['magnitude']:.1%} move)")
        
        # Likely causes:
        # 1. broker spike (ignore)
        # 2. Split/dividend (adjust)
        # 3. Data error (remove bar)
```

---

<<<<<<< HEAD
## ­ƒô× Support & Escalation
=======
## 📞 Support & Escalation
>>>>>>> origin/main

### When to Escalate

| Issue | Escalate To | Timeline |
|-------|-------------|----------|
| Single trade loss >1% | Risk Manager | 1 hour |
| Daily loss >2% | Ops Manager + Risk Manager | Immediately |
| Data unavailable >1 hour | DevOps | 30 minutes |
| API connection down | Ops Manager | 15 minutes |
| Unknown error in logs | Engineering | 30 minutes |
| Profit target missed >10% | Product Manager | End of day |

### Contact Tree

```
On-Duty Engineer:
<<<<<<< HEAD
Ôö£ÔöÇ Critical: Page (PagerDuty)
Ôö£ÔöÇ Urgent: Slack #edgecore-ops
ÔööÔöÇ Normal: Email

Risk Manager:
Ôö£ÔöÇ Daily loss breach: Immediate call
Ôö£ÔöÇ Position limit breach: Slack
ÔööÔöÇ P&L review: Email summary

Ops Manager (market hours):
Ôö£ÔöÇ System down: Page
Ôö£ÔöÇ Data unavailable: Call
ÔööÔöÇ Performance degradation: Slack
=======
├─ Critical: Page (PagerDuty)
├─ Urgent: Slack #edgecore-ops
└─ Normal: Email

Risk Manager:
├─ Daily loss breach: Immediate call
├─ Position limit breach: Slack
└─ P&L review: Email summary

Ops Manager (market hours):
├─ System down: Page
├─ Data unavailable: Call
└─ Performance degradation: Slack
>>>>>>> origin/main
```

---

<<<<<<< HEAD
## ­ƒôÜ Related Documentation
=======
## 📚 Related Documentation
>>>>>>> origin/main

- [ARCHITECTURE.md](ARCHITECTURE.md) - System design and signal pipeline
- [CONFIG_GUIDE.md](CONFIG_GUIDE.md) - Configuration and parameter tuning
- [README.md](README.md) - Getting started
- [BACKTEST_USAGE.md](BACKTEST_USAGE.md) - Running backtests

---

**Last Updated**: February 12, 2026  
**Next Review**: March 12, 2026  
**Owner**: Operations Team
