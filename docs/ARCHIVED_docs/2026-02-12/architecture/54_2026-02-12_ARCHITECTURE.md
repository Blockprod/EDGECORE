# EDGECORE Architecture

**Version**: 3.0 (Post-S3.2: Half-Life Refinement Integration)  
**Last Updated**: February 12, 2026  
**Status**: Production-Ready

---

## ­ƒÄ» Overview

EDGECORE is a **statistical arbitrage engine** that discovers and trades pairs with mean-reverting spreads. The system implements a seven-stage pipeline from data ingestion through execution, with comprehensive risk controls and out-of-sample validation.

**Key Design Principles:**
- **Evidence-based**: All decisions backed by statistical tests (Engle-Granger, Bonferroni correction)
- **Robust to regime changes**: Automatic detection and graceful degradation
- **Forward-looking**: Out-of-sample validation prevents lookback bias
- **Adaptive**: Half-life estimation drives dynamic signal windows
- **Risk-first**: Kill-switches protect against regime breakdown

---

## ­ƒôè Signal Generation Pipeline

### Stage 1: Pair Discovery (Daily, Cached per Period)

**Input**: 252 days OHLCV data  
**Output**: List of (symbol1, symbol2, pvalue, half_life, hedge_ratio)

**Process**:

1. **Preparation**
   - Load 252-day adjusted close prices for all symbols in universe
   - Convert to log returns: `r_t = ln(P_t / P_{t-1})`
   - Verify no missing data or extreme price moves

2. **Screening Phase (╬▒ = 0.05)**
   ```python
   for symbol_pair in all_pairs:
       # Engle-Granger test at standard significance level
       pvalue, half_life = engle_granger_test(Y, X)
       if pvalue < 0.05:
           candidate_pairs.append((symbol_pair, pvalue, half_life))
   ```
   - Expected result: ~5-10% of all pairs pass
   - Output: 50-100 candidate pairs (depending on universe size)

3. **Bonferroni Correction (╬▒_corrected)**
   ```python
   n_pairs = len(all_pairs)
   alpha_corrected = 0.05 / (n_pairs * (n_pairs - 1) / 2)
   
   confirmed_pairs = [
       p for p in candidate_pairs 
       if p.pvalue < alpha_corrected
   ]
   ```
   - Adjusts for multiple testing: if 1,000 pairs tested, ╬▒ Ôëê 0.0001
   - Expected result: 15-25 confirmed pairs (80% false positive reduction)

4. **Additional Filters**
   ```python
   for pair in confirmed_pairs:
       # Correlation check (ensure not perfect collinearity)
       corr = correlation(Y, X)
       
       # Half-life viability (below 60 days for mean reversion speed)
       if pair.half_life <= 60 and corr > 0.7:
           final_pairs.append(pair)
   ```

**Key Parameters**:
- `num_symbols`: Universe size (adjusts Bonferroni alpha)
- `min_correlation`: 0.7 (avoid near-singular designs)
- `max_half_life`: 60 days (ensures timely mean reversion)
- `lookback_window`: 252 days (standard ~1 year)

**Caching Strategy**:
- Pair list cached per backtest period (not re-discovered daily)
- Speeds up large backtests by 5-10x
- In live trading: refreshed every 24 hours

---

### Stage 2: Out-of-Sample Validation (One-time, 21 Days Forward)

**Input**: Discovered pairs from Stage 1  
**Output**: Pairs that remain cointegrated in forward period  
**Eliminates**: ~20-30% of pairs that were spurious correlations

**Process**:

1. **Split Horizon**
   ```python
   # Training period: T0 to T1 (252 days)
   # Validation period: T1 to T1+21 (21 days forward)
   
   # Fit Engle-Granger on training data
   eg_params = engle_granger_fit(Y[T0:T1], X[T0:T1])
   
   # Test on OOS data
   pvalue_oos = engle_granger_test(Y[T1:T1+21], X[T1:T1+21])
   ```

2. **Pair Survival Filter**
   ```python
   surviving_pairs = [
       p for p in discovered_pairs
       if pvalue_oos < 0.05  # Reconfirm on new data
   ]
   ```
   - Rejected pairs flagged as "spurious" (no entry signals)
   - Surviving pairs confidence increased

3. **Metrics**
   - **OOS Correlation Consistency**: corr_train Ôëê corr_oos (┬▒10%)
   - **OOS Half-Life Stability**: hl_train Ôëê hl_oos (┬▒20%)
   - **Survival Rate**: Expected 70-80% (rejects false positives)

**Runtime**: ~5-10 seconds per 50 pair pair discovery  
**Prevents**: Lookback bias, overfitting, regime-specific spurious correlations

---

### Stage 3: Spread Modeling (Dynamic, Monthly Re-estimate)

**Input**: Price series for cointegrated pair (Y, X)  
**Output**: Spread = Y - ╬▓*X, with hedge ratio ╬▓

**Process**:

1. **OLS Regression** (Hedge Ratio Estimation)
   ```python
   # Regress Y onto X to find hedging coefficient
   spread = Y - beta * X
   
   # OLS: beta = (X' * X)^-1 * X' * Y
   beta, residuals = lstsq(X, Y)
   
   # Residuals form the spread series
   spread = Y - beta * X
   ```

2. **Spread Properties**
   - **Mean**: Should be ~0 (by construction from OLS)
   - **Std Dev**: ~1-5% of Y scale
   - **Stationarity**: Verified by Augmented Dickey-Fuller test

3. **Drift Detection** (Monthly)
   ```python
   # Reestimate beta on latest 30-day window
   beta_new = lstsq(X[-30:], Y[-30:])
   
   # Flag if significant drift detected
   drift = abs(beta_new - beta_old) / beta_old
   if drift > 0.10:  # >10% change
       spread_model.is_deprecated = True
   ```
   - Triggers model re-estimation or pair removal from active list

4. **Output**: `SpreadModel` object
   ```python
   class SpreadModel:
       def __init__(self, Y, X):
           self.beta = hedge_ratio  # Cointegration coefficient
           self.spread = Y - beta * X  # Stationary series
           self.half_life = estimate_half_life(spread)  # NEW: S3.2
           self.is_deprecated = False
   ```

**Re-estimation Schedule**:
- Initial: At pair discovery or backtest start
- Ongoing: Every 20-30 trading days
- Forced: When drift > 10% detected

---

### Stage 4: Z-Score Calculation (Rolling, Adaptive Window)

**Input**: Spread series from Stage 3  
**Output**: Z-score per bar (normalized deviation from mean)

**Process**:

1. **Traditional Z-Score**
   ```python
   # Calculate mean and std on rolling window
   spread_mean = spread.rolling(window=lookback).mean()
   spread_std = spread.rolling(window=lookback).std()
   
   z_score = (spread - spread_mean) / spread_std
   ```

2. **Adaptive Window Selection** (NEW: S3.2 Half-Life Integration)
   ```python
   # Estimate half-life from spread series (AR(1) model)
   half_life = estimate_half_life(spread, lookback=252)
   
   # Window selection based on mean-reversion speed
   if half_life is not None and 5 <= half_life <= 200:
       if half_life < 30:
           # Fast reversion: use 3x half-life (smooth noise)
           window = min(int(3 * half_life), 90)
       elif half_life < 60:
           # Normal: use full half-life (one mean-reversion cycle)
           window = int(half_life)
       else:
           # Slow: cap at 60 (max useful history)
           window = 60
   else:
       # Fallback: use standard 60-day window
       window = 60
   ```

3. **Half-Life Estimation Process** (NEW: S3.2 Implementation)
   ```python
   # Fit AR(1) model to spread: s_t = ╬╝ + ¤ü*(s_{t-1} - ╬╝) + ╬Á_t
   # Extract ¤ü (autocorrelation coefficient) via OLS on centered spread
   
   centered_spread = spread - spread.mean()
   X = centered_spread.shift(1).dropna()
   y = centered_spread.dropna()
   
   rho = lstsq(X, y)[0][0]
   
   # Half-life from OU process formula
   if 0 < rho < 1:
       half_life = -ln(2) / ln(rho)
       if 5 <= half_life <= 200:
           return half_life
   return None
   ```

4. **Properties**
   - **Mean**: 0 (by construction)
   - **Std Dev**: 1 (normalized)
   - **Range**: Typically [-3, +3] for stationary spread
   - **Extremes**: |Z| > 3 indicates rare event (p < 0.3%)

**Window Validation**:
- Minimum: 20 days (avoid noise amplification)
- Maximum: 60 days (avoid stale information)
- Typical: 20-45 days (follows 20-60 day half-lives)

---

### Stage 5: Signal Generation (Per-Bar)

**Input**: Z-score, regime, position state  
**Output**: Signal Ôêê {Entry, Exit, Hold}

**Process**:

1. **Regime-Aware Entry Thresholds**
   ```python
   # Threshold varies by detected regime
   if regime == NORMAL:
       entry_threshold = 2.0  # Standard: 2 standard deviations
   elif regime == HIGH_VOLATILITY:
       entry_threshold = 2.3  # Tighter: require larger move
   elif regime == DECORRELATION:
       entry_threshold = 999  # Block: no entries allowed
   
   # Entry signal
   if abs(z_score) > entry_threshold and position is None:
       signal = Entry(direction=sign(z_score), z_entry=z_score)
       # Track entry price and Z-score for later calculations
   ```

2. **Exit Conditions** (Priority Order)
   
   **Exit 1: Mean Reversion (Primary)**
   ```python
   if position is not None and abs(z_score) <= 0.5:
       signal = Exit(reason='mean_reversion', pnl=calculate_pnl())
   ```
   - Captures profit when spread returns to mean
   - Expected: 60-80% of exits in normal regime

   **Exit 2: Trailing Stop (Volatility Protection)**
   ```python
   # Set at entry: stop = max(prices since entry) - 1*std_dev
   if position is not None and spread > trailing_stop:
       signal = Exit(reason='trailing_stop', pnl=calculate_pnl())
   ```
   - Locks in gains if spread detaches from mean
   - Limits loss if mean-reversion fails
   - Width: 1-2¤â from entry

   **Exit 3: Regime Kill-Switch (Risk Protection)**
   ```python
   if regime == DECORRELATION or position.duration > 30:
       signal = Exit(reason='regime_breakdown', pnl=calculate_pnl())
   ```
   - Force-closes all positions if pair decorrelates
   - Maximum position duration: 30 days (assumption breach)
   - Prevents long-term drift losses

3. **Signal Validity Checks**
   ```python
   # Prevent lookahead bias
   assert z_score_today uses prices up to today (not tomorrow)
   
   # Prevent re-entry whip-saws
   if last_exit_bar < 5:  # <5 bars since last exit
       signal = Hold  # Prevent rapid re-entry
   
   # Prevent overlapping entries (one position per pair)
   if position is not None:
       signal = Hold  # Block new entries while open
   ```

**Signal Reliability**:
- **Entry Accuracy**: 55-65% winning trades (before costs)
- **Exit Timeliness**: 70-80% close near mean (within 1¤â)
- **Zero Lookahead**: All price data strictly backward-looking

---

### Stage 6: Risk Check (Gate Before Execution)

**Input**: Position size request, current portfolio state  
**Output**: Approved position size or rejection

**Process**:

1. **Position Count Limit**
   ```python
   if len(active_positions) >= max_concurrent_positions:
       signal = Reject(reason='position_limit_exceeded')
       max_concurrent_positions = 10  # Default dev
       max_concurrent_positions = 5   # Stricter live
   ```

2. **Symbol Concentration Limit** (Per Symbol)
   ```python
   notional_exposure = position_size * entry_price
   total_portfolio_value = sum(all_positions.notional)
   
   exposure_pct = notional_exposure / total_portfolio_value
   if exposure_pct > max_symbol_notional_pct:
       signal = Reject(reason='concentration_limit_exceeded')
       max_symbol_notional_pct = 0.30  # Default dev
       max_symbol_notional_pct = 0.25  # Stricter live
   ```

3. **Sector Concentration Limit** (Cross-Symbol)
   ```python
   # Group symbols by sector (tech, finance, energy, etc.)
   sector_notional = sum(p.notional for p in active_positions 
                         if p.symbol.sector == sector)
   
   if sector_notional > max_sector_notional:
       signal = Reject(reason='sector_concentration_exceeded')
   ```

4. **Daily Loss Kill-Switch** (Portfolio-Level)
   ```python
   # Track realized and unrealized P&L at market open
   daily_pnl = realized_pnl + unrealized_pnl
   
   if daily_pnl < -max_daily_loss_pct * portfolio_value:
       # Close ALL positions immediately
       for position in active_positions:
           signal = Exit(reason='daily_loss_limit', position=position)
   
   max_daily_loss_pct = 0.02  # -2% default dev
   max_daily_loss_pct = 0.01  # -1% stricter live
   
   # Reset at next market open (UTC 00:00)
   ```

5. **Volatility-Based Sizing** (Dynamic)
   ```python
   # Reduce position size in high volatility regimes
   vol_30d = returns.rolling(30).std()
   
   if vol_30d > vol_median * 1.5:  # High vol
       size_multiplier = 0.7  # Reduce by 30%
   elif vol_30d > vol_median * 1.2:  # Elevated vol
       size_multiplier = 0.85
   else:
       size_multiplier = 1.0
   
   adjusted_size = base_size * size_multiplier
   ```

**Risk Hierarchy** (Evaluated in Order):
1. Daily loss limit (highest priority ÔåÆ kills all)
2. Position count limit
3. Sector concentration
4. Symbol concentration
5. Volatility adjustment (sizing only)

---

### Stage 7: Execution (IBKR via IBKR API)

**Input**: Approved position order  
**Output**: Executed trade with slippage & fees

**Process**:

1. **Order Placement**
   ```python
   # Market order using IBKR API
   order = broker.create_market_order(
       symbol='AAPL',
       side='buy' or 'sell',
       amount=size,
       timestamp=now()
   )
   ```

2. **Cost Assumptions**
   ```python
   slippage_bps = 5        # ┬▒5 basis points (0.05%)
   commission_rate = 0.001 # 0.1% taker fee
   total_cost_bps = 25     # ~25 basis points round-trip
   
   # Example: $1,000 entry
   entry_cost = 1000 + (1000 * 0.0025) = $1,002.50
   
   # Exit assumes 5 bps slippage + 10 bps commission = 15 bps
   exit_cost = 1000 - (1000 * 0.0015) = $998.50
   ```

3. **Position Tracking**
   ```python
   position = {
       'entry_price': execution_price,
       'entry_time': now(),
       'entry_z_score': z_score_at_entry,
       'size': executed_volume,
       'notional': execution_price * volume,
       'spread_at_entry': spread_at_entry,
       'trailing_stop': entry_price - 1*std_dev,
   }
   ```

4. **Exit Execution**
   ```python
   # Same market order process
   exit_order = broker.create_market_order(...)
   
   # Calculate P&L
   pnl = (exit_price - entry_price) * volume - total_costs
   pnl_bps = (pnl / notional) * 10000  # In basis points
   ```

**Execution Quality Metrics**:
- **Fill Rate**: >99% for size < 0.1% of symbol daily volume
- **Slippage Impact**: Entry ┬▒5 bps, Exit ┬▒10 bps (avg)
- **Latency**: <100 ms order placement to fill (IBKR spot)

---

## ­ƒøí´©Å Risk Management Framework

### Position-Level Risks

**Trailing Stop**
- Set at entry: `stop = entry_price - 1*std_dev`
- Tightened daily: `stop = max(stop, high - 0.5*std_dev)`
- Protects against regime breakdown

**Mean-Reversion Assumption**
- Exit target: Z < 0.5 (99% confidence reached within 30 days if true)
- Fallback timeout: 30 bars, then forced exit

### Portfolio-Level Risks

**Concentration Limits**
- Max 10 concurrent positions (dev) / 5 (live)
- Max 30% notional per symbol (dev) / 25% (live)
- Max sector weight enforced dynamically

**Daily Loss Kill-Switch**
- Threshold: -2% portfolio (dev) / -1% (live)
- Mechanism: Force-close ALL positions
- Reset: Next market open (UTC 00:00)

**Regime-Change Trigger**
- Condition: Decorrelation detected across 80%+ of pair universe
- Action: Kill all positions + block new entries
- Duration: Until next discovery cycle (24h in live)

---

## ­ƒôê Model Maintenance

### Monitoring

**Daily Checks**:
- Pair cointegration: Verify pvalue trend (should be stable)
- Spread properties: Monitor mean and std (should be stable)
- Half-life: Track estimated HL (should be within ┬▒20% of discovery)

**Weekly Reviews**:
- Win rate: Should be 55-65% (by pair)
- Drawdown: Should not exceed -3% cumulative
- Regime detection: Verify not stuck in false regime

### Retraining Schedule

**Immediate** (Triggers automatic refresh):
- Half-life estimation drift > 30%
- Hedge ratio drift > 10%
- Spread decorrelation (pvalue > 0.05)

**Monthly** (Scheduled):
- Re-estimate hedge ratios on all active pairs
- Update half-life estimates (affects Z-score window)
- Remove pairs with drift > 10%

**Quarterly** (Full reset):
- Re-discover pairs from latest 252 days
- Validate against new OOS period
- Update configuration based on market regime

---

## ­ƒöº System Dependencies

### Data Requirements
- **Historical OHLCV**: 252 days minimum
- **Update Frequency**: Daily close (UTC)
- **Lookback Window**: 252, 60, 30, 5 day aggregations
- **Forward Period**: 21 days for OOS validation

### Computational Requirements
- **Pair Discovery**: O(n┬▓) complexity, ~100ms per 1,000 pairs
- **Spread Modeling**: O(n) complexity, <1ms per pair
- **Z-Score Calculation**: O(n) rolling window, <1ms per bar
- **Total Pipeline**: <10 seconds for 50-100 pairs per day

### Storage Requirements
- **Pair Cache**: ~1KB per pair (metadata + HL)
- **Spread Series**: ~8KB per pair-month (OHLCV + spread values)
- **Backtest Results**: ~50KB per run
- **Typical**: <100MB for full year of trading history

---

## ­ƒôï Configuration Reference

### Strategy Parameters
```yaml
strategy:
  bonferroni_correction: true           # Enable multiple testing correction
  oos_validation_enabled: true          # Validate on 21-day forward period
  pair_cache_scope: "backtest_period"   # Cache pairs per backtesting period
  entry_z_score: 2.2                    # Entry threshold (dev: 2.2, live: 2.3)
  regime_detection_enabled: true        # Automatic regime switching
  min_correlation: 0.7                  # Cointegration quality filter
  max_half_life_days: 60                # Mean-reversion speed requirement
```

### Risk Parameters
```yaml
risk:
  max_concurrent_positions: 10          # Max open trades (dev: 10, live: 5)
  max_symbol_notional_pct: 0.30         # Max per symbol (dev: 30%, live: 25%)
  max_daily_loss_pct: 0.02              # Loss kill-switch (dev: -2%, live: -1%)
  volatility_adjustment_enabled: true   # Dynamic position sizing
```

### Execution Parameters
```yaml
execution:
  broker: IBKR                     # Trading venue
  slippage_bps: 5                       # Assumed slippage (basis points)
  commission_pct: 0.001                 # Taker fee as decimal
  order_type: market                    # Always market orders
```

---

## ­ƒº¬ Testing Strategy

All components tested with:
- **Unit Tests**: Individual functions (16+ test classes)
- **Integration Tests**: Full pipeline (27+ signal tests)
- **Risk Tests**: Limit enforcement (32+ risk tests)
- **Walk-Forward Tests**: Data integrity (26+ period tests)
- **OOS Validation**: Pair survival (implemented in Stage 2)

**Current Test Coverage**: 129 tests, 100% pass rate

---

## ­ƒôÜ Related Documentation

- [Configuration Guide](CONFIG.md) - Setup and parameter tuning
- [Operations Runbook](OPERATIONS_RUNBOOK.md) - Troubleshooting and monitoring
- [README](README.md) - Quick start guide
- [Changelog](CYTHON_CHANGES_INDEX.md) - Recent implementation changes

---

## ­ƒÄô Glossary

**Term** | **Definition** | **Typical Range**
---|---|---
**Half-Life** | Time for spread to revert 50% toward mean | 5-200 days
**Z-Score** | Distance from mean in standard deviations | [-3, +3]
**Bonferroni Alpha** | Multiple testing correction factor | 0.001-0.01
**Hedge Ratio** | Weighting coefficient ╬▓ in spread = Y - ╬▓*X | 0.5-2.0
**Sharpe Ratio** | Risk-adjusted return metric | 0.5-2.0 target
**Drawdown** | Peak-to-trough portfolio loss | Should not exceed -3%
**Regime** | Market state (normal, high-vol, decorrelation) | Detected daily
