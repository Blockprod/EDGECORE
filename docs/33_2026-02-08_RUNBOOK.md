# EDGECORE Operations Runbook

**Purpose:** Daily operations procedures, alert responses, and incident handling.

**Last Updated:** February 8, 2026

---

## Table of Contents

1. [Daily Operations](#daily-operations)
2. [Alert Response](#alert-response)
3. [Incident Handling](#incident-handling)
4. [Performance Tuning](#performance-tuning)
5. [Maintenance](#maintenance)

---

## Daily Operations

### Pre-Market Checklist (8:00 AM UTC)

```
□ System Status Check
  - Process running: ps aux | grep main.py
  - Memory usage: <50% of available
  - Disk space: >10GB free (for logs/data)

□ Recent Logs Review
  - grep ERROR logs/main_*.log
  - grep HARD_STOP logs/main_*.log  (should be ZERO)
  - grep reconciliation logs/main_*.log  (should show PASS)

□ Equity Verification
  - Current equity stable ±2% from yesterday
  - reconciliation passes 100%
  - No pending orders stuck

□ Configuration Verification
  - API keys active (no expiration)
  - Risk limits correct
  - Symbol list current (no delisted pairs)

□ Alert System Check
  - Slack webhook working (if configured)
  - Email alerts functional
  - Dashboard accessible
```

### Intra-Day Monitoring (Every 2 Hours)

```
□ Trading Activity
  - Orders filling normally (not hanging)
  - Error rate < 1%
  - Latency normal (<500ms for API calls)

□ Equity Trend
  - Tracking expected P&L
  - No unexpected liquidations
  - Reconciliation still passing

□ System Health
  - CPU utilization reasonable
  - Memory not growing (no leaks)
  - Logs not backing up (no read errors)
```

### Post-Market Checklist (20:00 UTC)

```
□ Daily Summary
  - Total P&L for day
  - Trades executed (count)
  - Error count (should be low)

□ Backup Verification
  - Audit trail backed up
  - Logs rotated
  - Configuration saved

□ Next Day Preparation
  - Check upcoming events
  - Verify symbol data freshness
  - Review next day risk limits
```

---

## Alert Response

### HARD_STOP_DAILY_LOSS

**Trigger:** 2% daily loss exceeded  
**Severity:** 🔴 CRITICAL  
**Action:**

1. **Immediate (< 1 minute):**
   ```bash
   # Stop trading immediately
   kill -TERM $(pidof python)
   
   # Verify shutdown
   sleep 5
   ps aux | grep main.py  # Should show no python process
   ```

2. **Diagnosis (1-5 minutes):**
   ```bash
   # Check what happened
   grep "equity" logs/main_*.log | tail -30
   
   # Check positions
   python -c "
   from persistence.audit_trail import AuditTrail
   a = AuditTrail()
   trades = a.load_full_audit_trail()
   print(f'Total trades today: {len([t for t in trades if t[\"type\"] == \"trade\"])}')
   recent = trades[-5:]
   for t in recent:
       print(f'{t[\"timestamp\"]}: {t[\"type\"]} - {t[\"symbol\"]} {t.get(\"quantity\")} @ {t.get(\"entry_price\")}')
   "
   ```

3. **Review (5-15 minutes):**
   - Was this expected (strategy performing poorly)?
   - Were there API errors causing positions to stay open?
   - Check broker for any unexpected fills

4. **Resolution:**
   - **If expected:** Reduce risk limits in config, restart
   - **If API issue:** Verify API keys, check broker status
   - **If bug:** Debug, fix, test in paper mode first

### HARD_STOP_MAX_DRAWDOWN

**Trigger:** 15% equity drawdown from peak  
**Severity:** 🔴 CRITICAL  
**Action:**

1. Similar to daily loss, but indicates extended losing streak
2. Check if strategy parameters need adjustment (z-scores too aggressive?)
3. Monitor position sizes - may need to reduce risk per trade

### HARD_STOP_API_ERRORS

**Trigger:** 10 consecutive API errors  
**Severity:** 🔴 CRITICAL  
**Action:**

1. **Immediate:**
   ```bash
   # Stop system
   kill -TERM $(pidof python)
   
   # Check API connectivity
   curl -I https://api.binance.com  # Should return 200
   ping 8.8.8.8  # Check internet
   ```

2. **Diagnosis:**
   ```bash
   # Check last API errors
   grep "api_error\|API" logs/main_*.log | tail -10
   
   # Check error type
   # - Connection refused? → Network issue
   # - 401 Unauthorized? → Bad API key
   # - 429 Too Many Requests? → Rate limiter hit
   ```

3. **Resolution:**
   - **Network:** Verify internet connectivity, firewall rules
   - **API Key:** Verify key is still valid, not rotated out
   - **Rate Limit:** Reduce polling frequency in config
   - **Broker Down:** Check Binance status page, wait and retry

### Reconciliation Failed

**Trigger:** Equity divergence > 0.5%  
**Severity:** 🟠 WARNING  
**Action:**

1. **Immediate:**
   ```bash
   # Log reconciliation failure
   grep "reconciliation\|equity.*divergence" logs/main_*.log
   
   # Check broker equity directly
   python -c "
   import ccxt
   exchange = ccxt.binance({'apiKey': '...', 'secret': '...'})
   balance = exchange.fetch_balance()
   print(f'Broker equity: {balance[\"total\"][\"USDT\"]}')"
   ```

2. **Diagnosis:**
   - Broker equity vs. internal equity mismatch
   - Check for unexpected fills or partial fills
   - Verify recent trades in audit trail

3. **Resolution:**
   - **If small (<0.1%):** Likely rounding

 error, monitor next cycle
   - **If 0.1%-0.5%:** Reconcile manually and log
   - **If >0.5%:** Stop trading, investigate fully

### Error Rate High (>1%)

**Trigger:** More than 1% of requests fail  
**Severity:** 🟡 WARNING  
**Action:**

1. Check error types:
   ```bash
   grep ERROR logs/main_*.log | sort | uniq -c | sort -rn
   ```

2. Common causes:
   - **Timeout errors:** Network lag, increase timeout
   - **Order rejected:** Risk check failing, reduce position size
   - **API errors:** Broker issue, check status

3. Action:
   - If < 5% errors: Usually acceptable, monitor
   - If 5%-10% errors: Investigate, may need to adjust
   - If > 10% errors: Consider stopping, debug

---

## Incident Handling

### System Crash

**Detection:** Process not running  

**Response:**

```bash
# Step 1: Verify crash
ps aux | grep main.py  # No process

# Step 2: Backup logs
cp logs/main_*.log logs/crashes/main_$(date +%Y%m%d_%H%M%S).log

# Step 3: Check for data corruption
python scripts/disaster_recovery.py --verify

# Step 4: Recover state
python scripts/disaster_recovery.py --recover

# Step 5: Restart
python main.py --mode live --symbols BTC/USDT ETH/USDT

# Step 6: Monitor
tail -f logs/main_*.log
```

### Broker Connection Lost

**Detection:** All API calls timing out or 500 errors  

**Response:**

```bash
# Check broker status
curl -I https://api.binance.com

# Check local network
ping 8.8.8.8

# Wait for connectivity (usually < 5 minutes)

# When restored, system should:
# 1. Reconnect automatically
# 2. Sync latest prices
# 3. Verify positions match
# 4. Resume trading

# If positions diverged:
python scripts/disaster_recovery.py --recover
```

### Unexpected Liquidation

**If position force-closed by broker:**

```bash
# 1. Check audit trail for the liquidation
grep "liquidat\|forced.*close" logs/main_*.log

# 2. Review:
#    - Margin level before liquidation
#    - Price move that triggered it
#    - Why risk engine didn't catch it

# 3. Investigate:
echo "Why did position get liquidated?"
echo "- Was stop-loss price incorrect?"
echo "- Did price gap over stop level?"
echo "- Was margin level monitored?"

# 4. Prevent future:
#    - Adjust stop-loss parameters
#    - Reduce max position size
#    - Increase monitoring frequency
```

---

## Performance Tuning

### Memory Usage Optimization

**Check current usage:**
```bash
ps aux | grep main.py | awk '{print $6}'  # Memory in KB
```

**If memory > 500MB:**
1. Restart system (clears cache)
2. Check for memory leaks:
   ```bash
   # Watch memory over time
   watch -n 5 'ps aux | grep main.py | awk "{print \$6}"'
   # If increasing: likely leak
   ```

3. Suspected leak locations:
   - Order history not being cleaned
   - Audit trail loaded entirely into memory
   - Price cache growing unbounded

### CPU Usage Optimization

**Check current usage:**
```bash
ps aux | grep main.py | awk '{print $3}'  # CPU %
```

**If CPU > 50%:**
1. Check what's consuming:
   ```bash
   # Get process thread count
   ps -eLf | grep main.py | wc -l
   # If high: too many threads
   ```

2. Reduce polling frequency:
   - Edit config.yaml: `paper_trading_loop_interval_seconds: 10` → `20`
   - Less frequent price updates = lower CPU

3. Reduce symbol count:
   - Fewer symbols to process = lower CPU
   - Start with 2-3 pairs (BTC, ETH, LTC)

### Latency Reduction

**Measure latency:**
```bash
# Check average order submission time
grep "order_latency_ms" logs/main_*.log | awk '{s+=$NF; c++} END {print s/c}'
```

**If latency > 1000ms:**
1. Check API latency:
   ```bash
   # Time a test call
   time curl https://api.binance.com/api/v3/time
   ```

2. Reduce batch size:
   - Instead of processing 100 symbols, process 10 at a time
   - Trade throughput for lower latency

3. Consider co-location (advanced):
   - If using cloud, ensure low-latency region
   - Consider dedicated exchange API servers

---

## Maintenance

### Weekly Tasks

```
□ Monday 8:00 AM:
  - Log rotation check (keep last 30 days)
  - Backup verification (backups/ directory size)
  - Dependencies check (pip list --outdated)

□ Friday 18:00 (before weekend):
  - Full system status review
  - Backup full state
  - Plan next week adjustments
```

### Monthly Tasks

```
□ 1st of month:
  - Review full audit trail
  - Reconcile all trades with broker
  - Performance analysis (Sharpe ratio, max drawdown, etc.)
  - Update risk limits if needed

□ 15th of month:
  - Update strategy parameters if needed
  - Review alert thresholds
  - Test disaster recovery
```

### Quarterly Tasks

```
□ Every 3 months:
  - API key rotation (if > 90 days old)
  - Full backup to external storage
  - Review and update documentation
  - Performance profiling (memory, CPU, latency)
  - Strategy evaluation (consider parameter changes)
```

### Annual Tasks

```
□ Year-end:
  - Full audit trail archival
  - Performance review for year
  - Strategy effectiveness analysis
  - Risk limit reassessment
  - System upgrade planning
```

---

## Scripts Reference

```bash
# Verify system health
python scripts/check_health.py

# Test disaster recovery
python scripts/disaster_recovery.py --verify

# Backup audit trail
python scripts/disaster_recovery.py --backup

# Run diagnostics
python scripts/diagnose_backtest.py

# Validate types
python scripts/validate_types.py

# Quick test
python scripts/quick_test.py
```

---

**Operations Team:** Refer to this runbook for daily operations and incident response.

**Last Reviewed:** February 8, 2026
