# EDGECORE MASTER AUDIT V6

**Date:** February 26, 2026  
**Auditor Class:** Senior Quant Developer / Risk Architect  
**Scope:** Full system architecture + deep statistical & strategic audit  
**Method:** Real code analysis only ÔÇö zero assumptions  
**Standard:** Institutional fund-level review for real capital deployment

---

# PART I ÔÇö SYSTEM & ARCHITECTURE AUDIT

---

## 1. Architectural Integrity

### 1.1 Module Map & Data Flow

EDGECORE implements a layered pipeline architecture:

```
Universe ÔåÆ Data ÔåÆ Pair Discovery ÔåÆ Signal Engine ÔåÆ Strategy
    ÔåÆ Risk Engine ÔåÆ Portfolio Engine ÔåÆ Execution ÔåÆ Monitoring
```

| Layer | Modules | LOC (est.) |
|-------|---------|------------|
| Data | `data/`, `universe/` | ~1,200 |
| Models | `models/` (17 files) | ~6,500 |
| Pair Selection | `pair_selection/` | ~600 |
| Signal Engine | `signal_engine/` | ~800 |
| Strategy | `strategies/` | ~800 |
| Risk | `risk/` + `risk_engine/` | ~2,800 |
| Portfolio | `portfolio_engine/` | ~900 |
| Execution | `execution/` + `execution_engine/` | ~6,800 |
| Live Trading | `live_trading/` | ~700 |
| Backtesting | `backtests/` + `backtester/` | ~3,500 |
| Monitoring | `monitoring/` (18 files) | ~4,500 |
| Config | `config/` | ~1,200 |
| Common | `common/` | ~1,000 |
| **Total** | | **~31,300** |

### 1.2 Separation of Concerns

**Strengths:**
- Strategy, risk, and execution are in **separate packages** with no circular imports
- Risk engine is position- and portfolio-aware independently of strategy logic
- Kill switch has **zero dependencies on strategy** (explicitly documented in `risk_engine/kill_switch.py`)
- Configuration is centralized in `config/settings.py` with per-environment YAML overrides
- Monitoring has its own Flask API, dashboard, and alert routing ÔÇö fully independent

**Weaknesses:**

­ƒö┤ **CRITICAL ÔÇö Duplicate Signal Generation Pipeline** (`strategies/pair_trading.py` vs `signal_engine/generator.py`)

Two completely independent signal-generation paths exist:

| Aspect | `PairTradingStrategy.generate_signals()` | `SignalGenerator.generate()` |
|--------|------------------------------------------|------------------------------|
| Spread model | Creates **new** `SpreadModel` every call | **Reuses** existing model, preserves Kalman state |
| Z-score | Hardcoded `lookback=20` | Adaptive lookback from half-life |
| Thresholds | Fixed config values | `AdaptiveThresholdEngine` with regime overlay |
| Stationarity | Not checked | ADF rolling guard |
| Regime | Not considered | `RegimeDetector` overlay |
| Signal class | `strategies.base.Signal(symbol_pair=ÔÇª)` | `signal_engine.generator.Signal(pair_key=ÔÇª)` |

Any backtest using one pipeline and live trading using the other will produce irreconcilable results.

­ƒö┤ **CRITICAL ÔÇö Triple Execution Abstraction**

Three independent, incompatible execution hierarchies coexist:

| Hierarchy | Base Class | Location |
|-----------|-----------|----------|
| A | `BaseExecutionEngine` ABC | `execution/base.py` |
| B | `ExecutionMode` ABC | `execution/modes.py` |
| C | `ExecutionRouter` | `execution_engine/router.py` |

Each defines its own `Order`, `OrderStatus`, and `Position` types. Three separate `OrderStatus` enums exist. Integration between layers requires manual type mapping.

­ƒƒá **MAJOR ÔÇö Dead Code Modules**

| Module | Issue |
|--------|-------|
| `HedgeRatioTracker` | Initialized in `pair_trading.py` L66 but `.reestimate_beta_if_needed()` never called |
| `TrailingStopManager` | Initialized in `pair_trading.py` L77 but never called in `generate_signals()` |
| `ModelRetrainingManager` | Initialized in `pair_trading.py` L86 but never invoked |
| `ConstraintType.SECTOR_CONCENTRATION` | Defined in `risk/constraints.py` but never enforced |
| `BrokerReconciler` | Fully implemented but never instantiated by `LiveTradingRunner` |
| `ShutdownManager` | Implemented but `LiveTradingRunner` uses bare `KeyboardInterrupt` instead |
| `VenueModels` | Realistic fee models exist but are never wired into any execution path |
| `performance_optimizer_s41.py` | Near-duplicate of `performance_optimizer.py` |

### 1.3 Scalability for Multi-Pair (20ÔÇô40 Spreads)

- `PairTradingStrategy.discover_pairs()` uses `ProcessPoolExecutor` for parallel cointegration testing ÔÇö scales well
- `PairDiscoveryEngine.discover()` uses `ThreadPoolExecutor` ÔÇö adequate but GIL-bound
- Portfolio allocator supports up to `max_pairs=10` (configurable) ÔÇö needs increase for 40 spreads
- Spread correlation guard and PCA monitor scale as O(n┬▓) in active spreads ÔÇö manageable for 40
- Kill switch and risk engine are pair-count-agnostic ÔÇö good
- **Gap:** No batch signal generation ÔÇö each pair processes sequentially within `generate_signals()`

### 1.4 CI/CD Readiness

­ƒö┤ **CRITICAL ÔÇö `.github/workflows/main.yml` is empty (whitespace only)**

No CI/CD pipeline exists. No automated tests, linting, security scanning, Docker build, or deployment automation.

### 1.5 Production Readiness Summary

| Component | Production Ready | Notes |
|-----------|-----------------|-------|
| Core strategy logic | ÔØî | Duplicate pipelines, dead code |
| Risk engine | ÔÜá´©Å | Functional but inconsistent thresholds |
| Kill switch | Ô£à | Disk-persistent, callback-enabled |
| Backtest infrastructure | Ô£à | Walk-forward, realistic costs, OOS |
| Execution (backtest) | Ô£à | Solid slippage/commission models |
| Execution (paper) | ÔÜá´©Å | Functional, some gaps |
| Execution (live) | ÔØî | `_live_fill()` is a hard stub |
| IBKR integration | ÔØî | No reconnection, no event callbacks |
| Monitoring | ÔÜá´©Å | Rich infrastructure, partially wired |
| CI/CD | ÔØî | Empty pipeline |

---

## 2. Code Quality & Engineering Standards

### 2.1 Python Best Practices

**Good:**
- Dataclasses for configuration (`@dataclass` throughout)
- ABC inheritance for strategy/execution base classes
- Type hints present in most modules
- `structlog` for structured logging
- Pydantic v2 schemas defined (though disconnected)
- Context managers for resource cleanup

**Issues:**

| Issue | Location | Severity |
|-------|----------|----------|
| `pickle.load` on untrusted cache files | `pair_trading.py` L230 | ­ƒƒá Security risk |
| `datetime.utcnow()` (deprecated Python 3.12+) | Multiple files | ­ƒƒí |
| `datetime.now()` instead of simulation time | `model_retraining.py` L220 | ­ƒƒá Backtest bias |
| `except Exception: pass` (silent swallow) | `pair_trading.py` L262 | ­ƒƒá |
| Global singleton with TOCTOU race | `config/settings.py` L96-99 | ­ƒƒá Thread safety |
| Global singleton for stop manager | `execution/position_stops.py` L463-472 | ­ƒƒí |
| Class-level mutable state in `ShutdownManager` | `execution/shutdown_manager.py` L33-35 | ­ƒƒá Bug |
| Row-by-row OHLCV iteration (O(n)) | `data/validators.py` L139-150 | ­ƒƒí Performance |

### 2.2 Reproducibility

**Strong:**
- `random_state=42` in HMM fitting
- `np.random.seed(42)` in test fixtures
- Walk-forward backtester creates fresh strategy instances per period
- Backtest simulator disables cache (`disable_cache()`)

**Weak:**
- No global random seed management across the full pipeline
- `ProcessPoolExecutor` workers may produce non-deterministic pair ordering

### 2.3 Test Coverage

**~1,902 tests across 88 files**

| Dimension | Rating |
|-----------|--------|
| Total test count | Strong |
| Core logic coverage | Good ÔÇö models, backtests, execution |
| Statistical rigor | Good ÔÇö false positive rates, Sharpe formulas, Kalman convergence |
| Anti-data-leakage | Excellent ÔÇö dedicated expanding-window tests |
| Integration | Moderate ÔÇö heavily mocked at broker layer |
| Infrastructure | **Poor** ÔÇö signal_engine, portfolio_engine, risk_engine, live_trading all **untested** |

**Critical untested modules:**

| Module | Risk |
|--------|------|
| `signal_engine/` (adaptive, generator, zscore) | Signal correctness unvalidated |
| `portfolio_engine/` (allocator, concentration, hedger) | Allocation logic unvalidated |
| `risk_engine/` (kill_switch, portfolio_risk, position_risk) | Safety-critical code untested |
| `live_trading/` (runner, paper_runner) | Live loop untested |
| `pair_selection/` (discovery, filters) | Pair selection logic untested |
| `execution/partial_profit.py` | Partial profit taking untested |
| `execution/shutdown_manager.py` | Graceful shutdown untested |
| `persistence/audit_trail.py` | Compliance-critical code untested |

**Estimated meaningful code coverage: ~65-70%**

### 2.4 Hardcoded Values (Critical Subset)

| Value | Location | Impact |
|-------|----------|--------|
| `lookback=20` | `pair_trading.py` L579 | Z-score window ignores half-life |
| `/ 3.0` normalization | `pair_trading.py` L591, `generator.py` L199 | Signal strength cap |
| `base_exit_threshold = 0.0` | `adaptive_thresholds.py` L24 | Exit condition unreachable |
| `20.0` (max_drawdown_pct) | `pair_trading.py` L97 | Unit mismatch ÔÇö breaker never fires |
| 5 different slippage rates | Across execution modules | 2.0 to 50.0 bps |
| 5 different commission rates | Across execution modules | 0.005% to 0.10% |
| `delta = 1e-4` | `kalman_hedge.py` L48 | Kalman adaptation speed |
| `kelly_fallback = 10%` | `allocator.py` L170 | Aggressive with no statistical basis |

### 2.5 Config Management

- Dual-layer: dataclass defaults + YAML overrides (`dev.yaml`, `prod.yaml`, `test.yaml`)
- Live trading blocked unless `ENABLE_LIVE_TRADING=true`
- Unknown YAML keys rejected with error
- Symbol hot-reload without restart

­ƒƒá **Pydantic schemas (`config/schemas.py`) are NOT connected to `Settings._load_yaml()`** ÔÇö comprehensive validation layer exists but is unused.

­ƒƒá **`config.yaml` master config is never loaded/merged** ÔÇö effectively documentation.

### 2.6 Logging Quality

Two logging systems coexist:
1. **Simple `structlog`** in `monitoring/logger.py` ÔÇö used by `main.py`
2. **Production logging** in `monitoring/logging_config.py` ÔÇö JSON format, context injection, rotating handlers, per-module files (`trading.log`, `api.log`, `risk.log`, `execution.log`)

­ƒƒá **`main.py` imports the simple logger, not the production one** ÔÇö rich logging infrastructure is unused at the entry point.

­ƒƒí Handler accumulation bug: `monitoring/logger.py` creates a new file handler per call, appending to root logger.

### 2.7 Error Handling

| Module | Quality | Notes |
|--------|---------|-------|
| `models/cointegration.py` | Excellent | NaN/zero-variance/ill-conditioned guards |
| `risk/engine.py` | Excellent | Input validation, custom exceptions, audit trail |
| `signal_engine/generator.py` | Good | Per-pair try/except with structured logging |
| `execution/reconciler.py` | Good | Explicit `ValueError` raises |
| `pair_trading.py` | Mixed | Per-pair try/except good, but `except Exception: pass` in workers |
| `pair_selection/discovery.py` | Mixed | Fail-open on test errors (NW/Johansen) |
| `kill_switch.py` | Weak | State persistence failure silently swallowed |
| `ibkr_engine.py` | Weak | Generic Exception, truncated messages |

---

## 3. Risk & Portfolio Architecture

### 3.1 Risk Architecture Overview

Three-tier defense:

```
Position Level:    5% stop ÔåÆ 10% P&L stop ÔåÆ trailing stop ÔåÆ time stop ÔåÆ stationarity exit
                            Ôåô
Portfolio Level:   2% daily loss ÔåÆ 10% drawdown ÔåÆ heat 95% ÔåÆ concentration 30%
                            Ôåô
Kill Switch:       3% daily loss ÔåÆ 15% drawdown ÔåÆ 5 consec losses ÔåÆ vol spike ÔåÆ data stale
                            Ôåô
                   HALT ALL TRADING ÔåÆ manual reset required
```

### 3.2 Kill Switch

**Implementation:** 5 automated triggers (drawdown ÔëÑ15%, daily loss ÔëÑ3%, consecutive losses ÔëÑ5, data staleness >300s, volatility >3├ù historical mean). Manual activation supported. Disk-persistent via JSON. Crash recovery on startup. Callback hook for Slack/PagerDuty.

**Strengths:**
- Zero strategy dependencies
- Persistent state survives process crashes
- Manual reset required ÔÇö no auto-recovery
- `KillReason` enum for audit trail

**Weaknesses:**
- Activation history is in-memory only ÔÇö lost on restart
- State file save failure silently swallowed (logged but not re-raised)
- `EXCHANGE_ERROR` trigger exists but is never wired automatically

### 3.3 Drawdown Control

­ƒö┤ **CRITICAL ÔÇö Four Different Drawdown Thresholds**

| Layer | Threshold | Source |
|-------|-----------|--------|
| RiskEngine (settings) | 10% | `config/settings.py` L58 |
| Kill Switch | 15% | `risk_engine/kill_switch.py` L57 |
| Portfolio Risk Manager | 15% | `risk_engine/portfolio_risk.py` L30 |
| Strategy internal | 20% | `config/settings.py` L41 ÔÇö **effectively disabled** (unit mismatch) |

The strategy-internal drawdown breaker at `pair_trading.py` L188-191 compares a fraction (0.0ÔÇô1.0) against a percentage value (20.0) ÔÇö the condition `0.20 > 20.0` **never fires**.

### 3.4 Position Sizing

Four methods available via `PortfolioAllocator`:
1. **EQUAL_WEIGHT**: `1/max_pairs` capped at `max_allocation_pct` (30%)
2. **VOLATILITY_INVERSE**: Target 2% daily vol budget per pair (**hardcoded**)
3. **KELLY**: Half-Kelly capped at 25% ÔÇö falls back to **hardcoded 10%** when statistics unavailable
4. **SIGNAL_WEIGHTED**: Equal-weight ├ù signal strength

­ƒƒá Pre-trade risk gate: `risk_amount = position_size ├ù volatility`, rejected if `risk_pct > 0.5%` ÔÇö sound logic but unmarked positions contribute zero exposure, creating a leverage bypass window.

### 3.5 Exposure Control

- Leverage check: `total_exposure + new / equity` Ôëñ 2.0├ù (configurable)
- ­ƒƒá Positions where `marked_price Ôëñ 0` contribute zero to total exposure ÔÇö newly opened positions can temporarily bypass leverage limits

### 3.6 Concentration Limits

- Per-symbol cap at 30% default
- ­ƒƒá **Metric is `|net_exposure| / gross_exposure`**, not fraction of portfolio AUM. A symbol with $1M long/$900K short shows 5.3% concentration despite $1.9M gross exposure.
- No pair-count-per-symbol limit

### 3.7 Beta Neutrality

- OLS regression of portfolio returns on benchmark (SPY)
- Hedge triggered when `|beta| > 0.10`
- Hedge capped at 20% of NAV
- ­ƒƒá During market crashes requiring 50%+ hedges, the 20% cap leaves the portfolio significantly exposed
- No hedge cost accounting

### 3.8 Cross-Spread Correlation Risk

**Two layers:**
1. **Pairwise Pearson correlation** ÔÇö rejects entry if `max(|¤ü|) > 0.60` with existing spreads
2. **PCA factor concentration** ÔÇö rejects if PC1 explains ÔëÑ50% of variance and candidate loads >0.70 on PC1

­ƒƒá Checked **at entry only** ÔÇö no ongoing monitoring. Spreads can become correlated post-entry.  
­ƒƒá PCA on unstandardized returns ÔÇö high-vol spreads dominate PC1 regardless of true factor structure.  
­ƒƒí Only PC1 analyzed ÔÇö two equally dangerous factors at 30% each pass all checks.

### 3.9 Does Risk Compensate Strategy Weakness?

| Strategy Risk | Risk Control | Verdict |
|---------------|-------------|---------|
| Mean-reversion failure | Trailing stop + P&L stop + stationarity check | Ô£à Triple coverage |
| Correlated pair blowup | SpreadCorrelation + PCA monitor | Ô£à Both pairwise and factor-level |
| Market beta exposure | BetaNeutralHedger | ÔÜá´©Å Capped at 20%, insufficient in crashes |
| Concentration | ConcentrationLimitManager | ÔÜá´©Å Misleading metric (net/gross) |
| Vol regime change | Kill switch vol check + regime detector | Ô£à Dual coverage |
| Hedge ratio instability | `HedgeRatioTracker` initialized but **never called** | ÔØî Dead code |
| Drawdown spiral | RiskEngine (10%) + PortfolioRisk (15%) + KillSwitch (15%) | Ô£à Layered but inconsistent |

### 3.10 Is Capital Structurally Protected?

**Verdict: YES, with material caveats.**

Capital has multi-layer protection from position-level to system-level halt. However:
1. Strategy-internal drawdown breaker never fires (unit bug)
2. Hedge ratio drift detection is dead code
3. No automatic position reduction ÔÇö binary trade/halt only
4. No liquidity-adjusted sizing
5. No intraday margin monitoring
6. No VaR/CVaR computation

---

## 4. Backtesting Infrastructure

### 4.1 Architecture

Dual-path system:

| Path | Method | Look-Ahead | Status |
|------|--------|------------|--------|
| Legacy | `BacktestRunner.run()` | ­ƒö┤ **YES** ÔÇö discovers pairs on full dataset | Deprecated, but `main.py --mode backtest` still calls it |
| Unified | `BacktestRunner.run_unified()` ÔåÆ `StrategyBacktestSimulator` | Ô£à No ÔÇö bar-by-bar expanding window | Production path via `run_backtest.py` |

­ƒö┤ **CRITICAL: `main.py --mode backtest` uses the legacy path with look-ahead bias.** Only `run_backtest.py` correctly uses `run_unified()`.

### 4.2 Strategy Simulator (Unified Path)

Production-grade 908-line simulator with:
- **Zero code duplication** ÔÇö uses identical `PairTradingStrategy.generate_signals()` as live
- Pair rediscovery at configurable intervals (default: every 5 bars)
- Fresh strategy instance per run with cache disabled
- Quality-weighted allocation (lower p-value, optimal HL ÔåÆ up to 1.5├ù base)
- Inverse-volatility sizing
- Spread correlation guard (>0.60 rejection)
- PCA factor concentration guard
- Portfolio heat limit (95% max)
- RiskEngine gate (same checks as live)
- Time stop (2├ù half-life)
- P&L stop (10% per position)
- Trailing stop (activates at 1.5% profit, trails 1.0%)
- Partial profit-taking (staged exits)
- Portfolio drawdown circuit breaker (15% DD ÔåÆ close all + 10-bar cooldown)
- Mark-to-market accounting (realized + unrealized P&L delta)

### 4.3 Walk-Forward Implementation

- **Expanding windows** (not rolling) ÔÇö each successive training window starts from data beginning
- Per-period fresh `PairTradingStrategy()` instance
- Optional OOS validation within training (80/20 split)
- Frozen pairs during test period
- Aggregate metrics across all periods

### 4.4 Parameter Cross-Validation

- Walk-forward CV grid search with random sampling when >200 combinations
- Per fold: fresh strategy + fresh simulator + pairs from training window only
- Stability analysis of top-5 parameter sets
- **Reports recommendations without auto-applying** ÔÇö correct engineering discipline

### 4.5 Stress Testing

Five synthetic shock scenarios:
1. Flash crash (ÔêÆ20% and ÔêÆ40% variants)
2. Prolonged drawdown (ÔêÆ15%/ÔêÆ20% over 60 bars)
3. Correlation breakdown (noise injection to break cointegration)
4. Volatility spike (3├ù return amplification)
5. Liquidity drought

Each modifies price data and feeds to the standard simulator.

### 4.6 Cost Model

Realistic 4-leg model:
- Maker: 1.5 bps, Taker: 2.0 bps
- Slippage: 2.0 bps base + volume-adaptive impact (capped 100 bps)
- Borrowing: 0.5% annual (General Collateral rate) ÔÇö accrued daily
- Well-calibrated for US equities via IBKR

### 4.7 Slippage & Fee Realism

­ƒƒá **Five different slippage rates coexist across modules:**

| Source | Slippage |
|--------|----------|
| `BacktestExecutor` default | 5.0 bps (fixed), up to 50 bps (adaptive) |
| `PaperExecutionEngine` | 5.0 bps |
| `ExecutionRouter` (all modes) | 2.0 bps |
| `BacktestMode` (`modes.py`) | 5.0 bps |
| `CostModel` (`backtests/cost_model.py`) | 2.0 bps + adaptive |

­ƒƒá **Five different commission rates:**

| Source | Commission |
|--------|-----------|
| `BacktestExecutor` | 0.02% |
| `PaperExecutionEngine` | 0.10% (5├ù higher) |
| `ExecutionRouter` | 0.005% |
| `BacktestMode` | 0.10% |
| Venue model (IBKR) | 0.035% |

### 4.8 Bias Detection Summary

| Bias Type | Status | Detail |
|-----------|--------|--------|
| **Look-ahead** | ÔÜá´©Å | Fixed in unified path; legacy path (`main.py --mode backtest`) still has it. Cache reuse risk if `disable_cache()` not called. |
| **Survivorship** | ÔÜá´©Å | `DelistingGuard` and `LiquidityFilter` exist but are **not wired** into `main.py` or backtest pipeline |
| **Data snooping** | Ô£à | Walk-forward CV, parameter stability analysis, OOS validation |
| **Over-optimization** | Ô£à | Bonferroni correction, Newey-West consensus, multi-test gates |
| **Selection bias** | ÔÜá´©Å | Johansen confirmation computed but **never used as gate** |

---

## 5. Monitoring & Alerting

### 5.1 Logging Architecture

| Feature | Status |
|---------|--------|
| Structured JSON logging | Ô£à Implemented in `logging_config.py` |
| Per-module log files (trading, api, risk, execution) | Ô£à Configured |
| Thread-local context (request_id, correlation_id) | Ô£à Via `ContextFilter` |
| Log rotation | Ô£à Timed rotating |
| Production logging used by main entry point | ÔØî `main.py` uses simple logger |

### 5.2 Alert Channels

| Channel | Status | Notes |
|---------|--------|-------|
| Slack | Ô£à | Webhook-based, 30s throttle, color-coded severity |
| Email | Ô£à | SMTP/TLS, ERROR/CRITICAL only |
| AlertManager routing | ÔÜá´©Å | Implemented but never instantiated in trading loop |
| PagerDuty | ÔØî | Kill switch has callback hook but no PagerDuty implementation |

### 5.3 Dashboard

- Flask REST API with endpoints: `/health`, `/api/dashboard/*`
- System metrics (CPU, memory, uptime via `psutil`)
- Risk metrics (equity, drawdown, loss streak)
- Position and order snapshots
- Performance metrics (returns, Sharpe, max drawdown)
- API key + JWT authentication
- Rate limiting (100 RPM)
- OpenAPI/Swagger spec

­ƒƒá Flask development server used in production (started in daemon thread). Should use Gunicorn/uWSGI.  
­ƒƒá Default JWT secret is a hardcoded fallback ÔÇö warning logged but not blocked in prod.

### 5.4 Advanced Monitoring Infrastructure

| Component | Status | Notes |
|-----------|--------|-------|
| Latency tracking (p50/p95/p99) | Ô£à | `monitoring/latency.py` |
| Performance profiler | Ô£à | `monitoring/profiler.py` ÔÇö `@profiler.decorator` |
| Distributed tracing | Ô£à | OpenTelemetry-like spans in `monitoring/tracing.py` |
| Prometheus metrics | ÔÜá´©Å | Manual text format, not `prometheus-client` library |
| Portfolio correlation monitoring | Ô£à | `monitoring/portfolio_extension_s43.py` |
| Advanced caching (LFU/ARC) | Ô£à | `monitoring/cache_advanced_s42.py` |

### 5.5 Missing Monitoring

| Gap | Severity |
|-----|----------|
| Prometheus scraping not functional (`prometheus.yml` missing) | ­ƒƒá |
| Redis configured in Docker but unused by application | ­ƒƒí |
| No real-time spread regime monitoring dashboard | ­ƒƒí |
| No automated anomaly detection on spread behavior | ­ƒƒí |
| Per-pair P&L attribution not in dashboard | ­ƒƒí |

---

# PART II ÔÇö STRATEGIC & STATISTICAL AUDIT (PAIR TRADING)

---

## 6. Nature of the Strategy

### 6.1 Exact Behavior (Inferred from Code)

EDGECORE implements **statistical arbitrage via pairs trading** on US equities through IBKR:

1. **Universe screening** ÔÇö Configurable symbol list (10ÔÇô80 symbols), filtered for liquidity and delisting risk
2. **Pair discovery** ÔÇö Engle-Granger cointegration test with optional Johansen confirmation, Bonferroni correction, half-life filter (5ÔÇô60 days)
3. **Spread construction** ÔÇö OLS regression `Y = ╬▒ + ╬▓X`, spread = residuals
4. **Signal generation** ÔÇö Z-score of spread against rolling mean; entry at |Z| > threshold (default 2.0¤â), exit at |Z| Ôëñ threshold (default 0.0 in signal engine, configurable in strategy)
5. **Risk overlay** ÔÇö Multi-layer position/portfolio/system-level controls
6. **Execution** ÔÇö Through IBKR (live stub) or paper simulation

### 6.2 Economic Rationale

The strategy rests on the premise that cointegrated equity pairs exhibit a stationary spread that mean-reverts after deviations, creating a bounded P&L process. Entry occurs at extreme deviations expecting reversion to mean.

**Economic justification strength:** Moderate. Cointegration between equities can arise from:
- Shared factor exposure (sector, industry, supply chain)
- Fundamental linkage (same underlying business exposure)
- Statistical artifact (spurious regression in finite samples)

The code does not enforce economic rationale ÔÇö any statistically significant pair is tradeable. This increases false-positive risk from spurious cointegration.

### 6.3 True Classification

**Mean-reversion strategy** ÔÇö not true arbitrage. The spread is not guaranteed to converge. There is no contractual or structural mechanism enforcing convergence (unlike bond basis trades or merger arbitrage). The strategy profits if the statistical relationship holds and loses if it breaks.

### 6.4 Structural Coherence

­ƒƒá The presence of two parallel signal pipelines (`generate_signals()` vs `SignalGenerator`) with materially different behavior (fixed vs adaptive thresholds, static vs dynamic Z-score windows, no stationarity check vs ADF guard) undermines structural coherence. It is unclear which pipeline is authoritative.

---

## 7. Statistical Validity

### 7.1 Engle-Granger Implementation

**Location:** `models/cointegration.py` (532 lines)

- Standard two-step: OLS regression ÔåÆ ADF on residuals
- `adfuller` with `autolag='AIC'` ÔÇö correct
- MacKinnon critical values for regression residuals ÔÇö correct
- Condition number guard (rejects if `cond > 1e10`)
- HAC-robust variant via `sm.OLS.fit(cov_type='HAC')`
- Consensus function requiring **both** standard and HAC-robust to agree ÔÇö excellent practice

­ƒö┤ **CRITICAL ÔÇö ╬▓ Scale Inconsistency:**
- `engle_granger_test()` computes ╬▓ on **z-scored** data (normalized ÔåÆ `(x - x.mean()) / x.std()`)
- `engle_granger_test_robust()` computes ╬▓ on **raw** data via `sm.add_constant(x_arr)`
- `SpreadModel.__init__()` computes ╬▓ on **raw** prices via `np.linalg.lstsq`
- C++ optimized path returns ╬▓ on presumably **raw** scale

The ╬▓ flowing through the system changes scale depending on which code path executed, but downstream consumers are unaware.

­ƒƒá **I(1) pre-check OFF by default** ÔÇö `check_integration_order=False`. Without I(1) verification, two stationary series produce trivially significant ADF results = **spurious cointegration**. The I(1) gate is opt-in, not default.

### 7.2 P-Value Logic

- Default ╬▒ = 0.05 (hardcoded)
- Bonferroni correction available (`╬▒ = 0.05 / C(n,2)`) ÔÇö correctly computes `n(n-1)/2`
- Bonferroni is opt-in in `PairTradingStrategy` (sequential path only) 
- `PairDiscoveryEngine` always applies Bonferroni ÔÇö good

­ƒƒí Without Bonferroni, testing C(100,2) = 4,950 pairs at ╬▒=0.05 yields ~247 expected false positives.

### 7.3 Rolling vs Static Windows

- Cointegration testing: **static** ÔÇö full lookback window, no rolling recalibration by default
- `ModelRetrainingManager` provides periodic re-testing (every 14 days) ÔÇö but has a **KeyError bug** (`eg_result['p_value']` vs actual key `'adf_pvalue'`), making it non-functional
- `HedgeRatioTracker`: time-based reestimation every 7 days + emergency on 3¤â vol spike
- `StationarityMonitor`: rolling ADF on 60-bar window, alert at p > 0.10

### 7.4 Hedge Ratio Stability

Three estimation methods available:
1. **OLS** ÔÇö static, recomputed on `SpreadModel` creation
2. **Kalman Filter** ÔÇö dynamic, bar-by-bar updates (`delta=1e-4`)
3. **`HedgeRatioTracker`** ÔÇö periodic reestimation with drift detection (>10% ÔåÆ deprecate)

­ƒƒá **Kalman filter lacks intercept** ÔÇö models `y = ╬▓x`, ignoring ╬▒. Spread residuals biased if true ╬▒ Ôëá 0.  
­ƒƒá **Kalman R (observation noise) never updated** ÔÇö fixed at initial value forever.  
­ƒƒí **Kalman ╬▓ÔéÇ initialization** ÔÇö `yÔéÇ/xÔéÇ` is fragile. OLS warm-start would be more robust.

### 7.5 Cointegration Durability

The system has mechanisms for durability assessment:
- Rolling ADF stationarity monitoring (60-bar window)
- Structural break detection (CUSUM + recursive ╬▓ stability)
- Hedge ratio drift tolerance (10% threshold)
- OOS validator (ISÔåÆOOS cointegration persistence)

­ƒƒá **CUSUM implementation is non-standard** ÔÇö uses raw OLS residuals instead of recursive residuals. Tabulated critical values may be incorrect for this formulation.  
­ƒƒá **Model retraining has a runtime bug** ÔÇö `KeyError` on `'p_value'` prevents re-discovery and re-estimation from executing.

### 7.6 Regime Sensitivity

Two regime detection systems:
1. **Percentile-based** (`RegimeDetector`) ÔÇö rolling volatility percentiles (33rd/67th) with 20-bar lookback
2. **Markov HMM** (`MarkovRegimeDetector`) ÔÇö 3-state Gaussian HMM, 50 EM iterations, 252-bar lookback

| Regime | Entry Adjustment | Signal Impact |
|--------|-----------------|---------------|
| LOW | ÔêÆ0.3 (more aggressive) | 0.5├ù position multiplier |
| NORMAL | 0.0 | Full position |
| HIGH | +0.5 (more conservative) | 1.2├ù entry threshold |

­ƒƒí LOW regime entry can stack to 1.0¤â minimum (base 2.0 ÔêÆ 0.4 vol ÔêÆ 0.3 HL ÔêÆ 0.3 regime = **1.0**). Entering at 1¤â has very high false-signal rate.  
­ƒƒí HMM uses `abs(return)`, discarding directional information. Limits regime discrimination.  
­ƒƒí EM convergence not enforced ÔÇö unconverged model still used.

### 7.7 False Positive & Overfitting Risk

| Control | Status | Effectiveness |
|---------|--------|---------------|
| Bonferroni correction | Ô£à Available | Good when activated |
| Newey-West HAC consensus | Ô£à Implemented | Excellent ÔÇö requires dual agreement |
| Johansen double-screen | ÔÜá´©Å Computed but **never gates** | Ineffective |
| I(1) pre-check | ÔÜá´©Å Off by default | Absent unless explicitly enabled |
| Fail-open on test errors | ÔØî NW/Johansen errors ÔåÆ assume pass | Degrades false-positive protection |
| Walk-forward OOS | Ô£à | Good for strategy-level validation |
| ML threshold train/test split | ÔØî Random split, not temporal | Look-ahead bias in ML training |

---

## 8. Spread Construction & Z-Score Logic

### 8.1 Spread Formula

```
spread = Y - (╬▒ + ╬▓ ├ù X)
```

Where ╬▓ and ╬▒ from OLS via `np.linalg.lstsq` on raw prices (`SpreadModel`) or normalized data (`engle_granger_test`). The inconsistency in ╬▓ scale between testing and trading is a critical issue (┬º7.1).

### 8.2 Z-Score Computation

Two independent Z-score engines:

| Engine | Lookback | Smoothing | Clip |
|--------|----------|-----------|------|
| `SpreadModel.compute_z_score()` | Adaptive (HL-based), window Ôêê [10, 120] | None | ┬▒6.0 |
| `ZScoreCalculator.compute()` | Adaptive (HL-based), window Ôêê [2, 252] | Optional EWMA | ┬▒10.0 |
| `PairTradingStrategy.generate_signals()` | **Hardcoded 20** | None | Via SpreadModel (┬▒6.0) |

The hardcoded `lookback=20` in `generate_signals()` bypasses the adaptive windowing despite half-life being available in scope.

­ƒƒá **Z-score clip inconsistency** ÔÇö a Z of 8.0 is clipped to 6.0 in one path but kept at 8.0 in another, producing different entry decisions.

### 8.3 Stationarity

- `StationarityMonitor`: rolling ADF on 60 bars, alert at p > 0.10
- `SignalGenerator`: ADF guard before signal generation (good)
- `PairTradingStrategy.generate_signals()`: **no stationarity check** (bad)

­ƒƒí ADF on 60 observations has low power. Type II error (failing to detect non-stationarity) is significant.

### 8.4 Distributional Assumptions

All core models assume **Gaussian innovations**: ADF, KPSS, Johansen, Kalman, HMM, OU half-life. **None validated against actual data distribution.** Equity returns exhibit fat tails and volatility clustering that inflate Type I error in cointegration tests.

---

## 9. Entry / Exit Logic

### 9.1 Entry Conditions

| Path | Entry Condition | Default |
|------|----------------|---------|
| `PairTradingStrategy` | `\|Z\| > config.entry_z_score` | Configurable (default 2.0) |
| `SignalGenerator` | `\|Z\| > adaptive_entry_threshold` | 1.0ÔÇô3.5 (adaptive) |

Entry signal strength: `min(abs(Z) / 3.0, 1.0)` ÔÇö reaches maximum at Z = 3.0¤â.

### 9.2 Exit Conditions

­ƒö┤ **CRITICAL ÔÇö Exit Unreachable in SignalGenerator**

`SignalGenerator` exit condition: `abs(current_z) <= exit_threshold`

Since `base_exit_threshold = 0.0` and **exit threshold is never adjusted** by any adaptation layer, this requires `current_z == 0.0` exactly in floating point ÔÇö essentially **never fires**.

Positions opened via `SignalGenerator` can only exit through:
- Stationarity loss (ADF check)
- External stop/risk management

The `PairTradingStrategy` path uses `config.exit_z_score` ÔÇö likely a configurable non-zero value like 0.5. This is a functional divergence between pipelines.

### 9.3 Threshold Justification

Entry at |Z| > 2.0 is a common baseline. The adaptive system can reduce this to 1.0¤â under favorable conditions (low vol + fast HL + low regime). **1.0¤â entry is statistically aggressive** ÔÇö approximately 32% of observations fall outside ┬▒1¤â for a normal distribution, meaning frequent false signals.

### 9.4 Stop Mechanisms

| Stop Type | Implementation | Default | Integrated? |
|-----------|---------------|---------|-------------|
| Stop-loss (fixed %) | `risk/engine.py` | 5% | Ô£à Yes (RiskEngine) |
| P&L stop | `risk_engine/position_risk.py` | 10% | ÔÜá´©Å Via PositionRiskManager |
| Trailing stop (Z-score) | `execution/trailing_stop.py` | 1.0¤â widening | ÔØî Not called in live loop |
| Time stop | `execution/time_stop.py` | 3├ù half-life, cap 60d | ÔØî Not called in live loop |
| Partial profit | `execution/partial_profit.py` | 1.5% ÔåÆ 50% close | ÔØî Not called in live loop |
| Breakeven protect | `execution/position_stops.py` | After profit threshold | ÔØî Not called in live loop |

­ƒö┤ **CRITICAL: Stop managers exist but are NOT wired into `LiveTradingRunner._tick()`**. In live/paper trading, positions have only RiskEngine stop-loss (5%) and PositionRiskManager checks. The comprehensive trailing/time/partial stops are backtest-only.

### 9.5 Drift Exposure

No explicit spread drift adjustment. If a pair slowly loses cointegration, the Z-score calculation continues assuming stationarity. The `StationarityMonitor` provides an ADF-based alert but:
- Only in the `SignalGenerator` pipeline path
- ADF at 60 observations has borderline power
- No mechanism to reduce position size gradually as confidence decreases

---

## 10. Real-World Stress Scenarios

### 10.1 Analysis by Scenario

| Scenario | System Response | Adequacy |
|----------|----------------|----------|
| **Volatility spike** | Kill switch triggers at 3├ù vol; regime detector shifts to HIGH; entry threshold increases +0.5¤â; position multiplier drops to 0.5├ù | Ô£à Good ÔÇö multi-layer response |
| **Flash crash** | 5% stop-loss fires per position; daily loss breaker at 2-3%; kill switch at 15% portfolio DD; stress test framework validates survivability | ÔÜá´©Å Adequate ÔÇö but beta hedge capped at 20% may be insufficient |
| **Correlation breakdown** | Stationarity monitor detects (60-bar lag); spread correlation guard prevents correlated entries; PCA monitor detects factor concentration | ÔÜá´©Å Detection exists but only at entry; no ongoing position remediation |
| **Liquidity collapse** | `LiquidityFilter` exists but **not wired in**; no liquidity-adjusted sizing; paper engine uses hardcoded market volume 1M | ­ƒö┤ Poor ÔÇö liquidity infrastructure exists but is disconnected |
| **Exchange fee changes** | `VenueModels` has IBKR-specific fees but **not connected** to execution; cost model uses separate hardcoded values | ­ƒƒá Manual update required |
| **Gap risk / overnight** | No overnight exposure management; positions held across sessions; no pre-market risk check | ­ƒƒá Missing |

### 10.2 Stress Test Framework

Backtesting includes five synthetic stress scenarios (flash crash, prolonged drawdown, correlation breakdown, vol spike, liquidity drought). Each injects shocks into historical data and runs the standard simulator. **This is well-designed** ÔÇö the strategy is validated against extreme conditions using the exact same code path as normal operation.

---

## 11. StrategyÔÇôRisk Engine Interaction

### 11.1 Does Strategy Stand Alone?

**No.** Without the risk overlay, the raw strategy has:
- No stop-loss (pure mean-reversion exit only)
- No time limit on positions
- No drawdown protection
- No concentration limits
- Entry at potentially 1.0¤â (high false signal rate)
- Exit at 0.0¤â in SignalGenerator (unreachable)

The raw strategy would hemorrhage capital during any sustained cointegration breakdown.

### 11.2 Is Risk Masking Statistical Fragility?

**Yes, partially.** The multi-layer risk architecture compensates for:
- Missing stop-loss in strategy ÔåÆ 5% position stop in RiskEngine
- No time limit in strategy ÔåÆ time stop in PositionRiskManager (but not wired in live)
- No drawdown control in strategy ÔåÆ 10-15% portfolio drawdown breakers
- Exit at 0.0 ÔåÆ External position management via risk checks

The risk engine transforms a **statistically fragile** mean-reversion signal into a **bounded loss** system. Without it, the strategy is not survivable.

### 11.3 Would Raw Strategy Survive Without Heavy Risk Overlay?

**No.** Key failure modes without risk:
1. Exit threshold of 0.0 means positions never close via mean-reversion in SignalGenerator
2. No maximum divergence guard ÔÇö Z of 5+ held indefinitely
3. No time decay ÔÇö zombie positions accumulate capital charges
4. No concentration control ÔÇö correlated pairs multiply risk
5. Aggressive entry at 1.0¤â generates excessive false signals

**The risk engine IS the strategy.**

---

# PART III ÔÇö CRITICAL SYNTHESIS

---

## 12. Critical Issues (Ranked)

### ­ƒö┤ Critical ÔÇö Capital Endangerment / Statistical Illusion / Structural Invalidity

| # | Issue | Location | Impact |
|---|-------|----------|--------|
| C1 | **Exit threshold unreachable (0.0)** in `SignalGenerator` ÔÇö positions never close via mean-reversion | `adaptive_thresholds.py` L24, `generator.py` L184-193 | Positions held until external stop fires. P&L decay from carry/borrow. |
| C2 | **Drawdown breaker unit mismatch** ÔÇö compares fraction (0ÔÇô1) against percentage (20.0) ÔÇö never fires | `pair_trading.py` L188-191 | Strategy-level capital protection disabled |
| C3 | **Duplicate signal pipelines** with materially different behavior (fixed vs adaptive Z-score, stationarity check, regime overlay) | `strategies/pair_trading.py` vs `signal_engine/generator.py` | Backtest/live divergence guaranteed |
| C4 | **╬▓ scale inconsistency** ÔÇö normalized in EG test, raw in SpreadModel, raw in HAC-robust, unknown in C++ | `cointegration.py` L188-253, `spread.py` L33 | Spread construction may use wrong hedge ratio |
| C5 | **Model retraining runtime crash** ÔÇö `KeyError: 'p_value'` (actual key is `'adf_pvalue'`) | `model_retraining.py` L231, L319 | Pair re-discovery and re-estimation are non-functional |
| C6 | **Stop managers not wired into live trading loop** ÔÇö trailing/time/partial stops only work in backtest | `live_trading/runner.py` L147-215 | Live positions have no stop protection beyond basic 5% RiskEngine stop |
| C7 | **Live execution is a hard stub** ÔÇö `_live_fill()` raises `RuntimeError` | `execution_engine/router.py` L162-178 | System cannot execute live trades |
| C8 | **Empty CI/CD pipeline** ÔÇö no automated testing or deployment | `.github/workflows/main.yml` | No safety net for regressions |

### ­ƒƒá Major ÔÇö Severe Fragility

| # | Issue | Location |
|---|-------|----------|
| M1 | Triple execution abstraction (3 independent `OrderStatus` enums, 3 `Order` types) | `execution/` |
| M2 | I(1) pre-check off by default ÔÇö spurious cointegration when both series are I(0) | `cointegration.py` L101 |
| M3 | Johansen confirmation computed but **never gates** pair selection | `discovery.py` L194-202 |
| M4 | Four different drawdown thresholds (10%, 15%, 15%, 20%) ÔÇö unclear authority | `settings.py`, `kill_switch.py`, `portfolio_risk.py` |
| M5 | `HedgeRatioTracker` initialized but never called ÔÇö hedge ratio drift is unmonitored | `pair_trading.py` L66 |
| M6 | Fail-open on NW/Johansen errors ÔÇö broken robustness checks silently pass pairs | `discovery.py` L190, L198 |
| M7 | ML threshold train/test split is random, not temporal ÔÇö look-ahead bias | `ml_threshold_optimizer.py` L556 |
| M8 | IBKR engine: no reconnection logic, no event callbacks, no rate limiting | `ibkr_engine.py` |
| M9 | Pydantic config schemas disconnected from settings loader | `schemas.py` vs `settings.py` |
| M10 | `main.py --mode backtest` uses legacy path with look-ahead bias | `main.py` L697 |
| M11 | `DelistingGuard` and `LiquidityFilter` exist but not wired into pipeline | Not called in `main.py` |
| M12 | CUSUM uses raw OLS residuals instead of recursive residuals ÔÇö critical values may be incorrect | `structural_break.py` L172-176 |
| M13 | Concentration metric uses net/gross ratio, not fraction of AUM ÔÇö misleading | `concentration_limits.py` L41-45 |
| M14 | `BrokerReconciler` implemented but never instantiated by live runner | `live_trading/runner.py` |
| M15 | Kalman filter: no intercept, fixed R forever, fragile ╬▓ÔéÇ initialization | `kalman_hedge.py` |

### ­ƒƒí Minor ÔÇö Optimization / Engineering Improvements

| # | Issue | Location |
|---|-------|----------|
| m1 | Z-score clip inconsistency (┬▒6.0 vs ┬▒10.0 across paths) | `spread.py` L221, `zscore.py` L75 |
| m2 | Hardcoded `lookback=20` bypasses adaptive Z-score | `pair_trading.py` L579 |
| m3 | Silent `except Exception: pass` in parallel worker | `pair_trading.py` L262 |
| m4 | `pickle.load` on untrusted cache files ÔÇö security risk | `pair_trading.py` L230 |
| m5 | `datetime.utcnow()` deprecated in Python 3.12+ | Multiple files |
| m6 | `datetime.now()` used instead of simulation time in backtesting | `model_retraining.py` L220 |
| m7 | Python version mismatch: Dockerfile uses 3.14 vs `pyproject.toml` requires 3.11.9 | `Dockerfile` L2, `pyproject.toml` L13 |
| m8 | Flask dev server in production | `main.py` L265-268 |
| m9 | Default JWT secret not blocked in prod mode | `api_security.py` L139 |
| m10 | Handler accumulation in simple logger | `monitoring/logger.py` L22-25 |
| m11 | `performance_optimizer_s41.py` is near-duplicate | `models/` |
| m12 | HMM uses abs(return), discarding sign information | `markov_regime.py` L168 |
| m13 | `min_regime_duration=1` ÔÇö no hysteresis filtering | `regime_detector.py` L95 |
| m14 | ML trade simulator ignores direction (long/short) | `ml_threshold_optimizer.py` L262 |
| m15 | `LiquidityFilter.strict_mode` defaults to `False` ÔÇö unknown symbols pass | `liquidity_filter.py` L27 |
| m16 | Missing `requests` in `requirements.txt` | SlackAlerter dependency |
| m17 | Version conflicts between `pyproject.toml` and `requirements.txt` | numpy, vectorbt |
| m18 | ADF on 60 observations has low power for unit root detection | `stationarity_monitor.py` |
| m19 | Volatility percentile-of-percentile calculation produces meaningless value | `adaptive_thresholds.py` L140-141 |
| m20 | `ShutdownManager` class-level mutable state bug ÔÇö shared across instances | `shutdown_manager.py` L33-35 |

---

## 13. Priority Action Plan

### Tier 1: Mandatory Before Paper Trading

| Priority | Action | Effort |
|----------|--------|--------|
| **P0-1** | Set `base_exit_threshold = 0.5` (or configurable non-zero value) | 1 hour |
| **P0-2** | Fix drawdown unit mismatch: store as fraction `0.20` or compare `dd_frac * 100` | 30 min |
| **P0-3** | Consolidate to single signal pipeline ÔÇö deprecate `PairTradingStrategy.generate_signals()` in favor of `SignalGenerator` | 2ÔÇô3 days |
| **P0-4** | Fix `model_retraining.py` KeyError: `'p_value'` ÔåÆ `'adf_pvalue'` | 15 min |
| **P0-5** | Wire stop managers into `LiveTradingRunner._tick()`: trailing stop, time stop, partial profit | 1ÔÇô2 days |

### Tier 2: Mandatory Before Live Deployment

| Priority | Action | Effort |
|----------|--------|--------|
| **P1-1** | Implement live execution in `ExecutionRouter._live_fill()` ÔÇö wire `IBKRExecutionEngine` | 3ÔÇô5 days |
| **P1-2** | Add IBKR reconnection logic, event callbacks, rate limiting | 2ÔÇô3 days |
| **P1-3** | Unify drawdown thresholds to single authoritative value across all layers | 2 hours |
| **P1-4** | Enable I(1) pre-check by default in EG test | 30 min |
| **P1-5** | Make Johansen confirmation a hard gate when enabled | 30 min |
| **P1-6** | Wire `BrokerReconciler` into `LiveTradingRunner` (startup + periodic) | 1 day |
| **P1-7** | Wire `ShutdownManager` into live runner ÔÇö replace bare `KeyboardInterrupt` | 4 hours |
| **P1-8** | Create CI/CD pipeline: test ÔåÆ lint ÔåÆ build ÔåÆ deploy | 1ÔÇô2 days |
| **P1-9** | Wire `DelistingGuard` and `LiquidityFilter` into data pipeline | 4 hours |
| **P1-10** | Fix Dockerfile Python version to match `pyproject.toml` (3.11.x) | 15 min |

### Tier 3: Medium-Term Structural Upgrades

| Priority | Action | Effort |
|----------|--------|--------|
| **P2-1** | Unify execution abstraction ÔÇö pick `ExecutionRouter` as canonical, remove `modes.py` | 3ÔÇô5 days |
| **P2-2** | Standardize cost model ÔÇö single source of truth for slippage/commission | 1 day |
| **P2-3** | Normalize ╬▓ consistently: raw-scale throughout or normalized throughout | 2 days |
| **P2-4** | Connect Pydantic schemas to `Settings._load_yaml()` | 1 day |
| **P2-5** | Switch to production WSGI server (Gunicorn) for monitoring API | 2 hours |
| **P2-6** | Add tests for untested critical modules (signal_engine, portfolio_engine, risk_engine, live_trading) | 5ÔÇô10 days |
| **P2-7** | Replace `pickle.load` with JSON-based cache | 2 hours |
| **P2-8** | Use `main.py --mode backtest` unified path instead of legacy | 1 hour |
| **P2-9** | Fix fail-open defaults to fail-closed for NW/Johansen | 1 hour |
| **P2-10** | Implement ongoing spread correlation monitoring (not just at entry) | 2 days |

### Tier 4: Advanced Quantitative Improvements

| Priority | Action | Effort |
|----------|--------|--------|
| **P3-1** | Add intercept to Kalman state-space model | 4 hours |
| **P3-2** | Implement adaptive R (observation noise) in Kalman filter | 1 day |
| **P3-3** | Replace CUSUM with proper recursive-residual formulation | 1 day |
| **P3-4** | Fix ML threshold optimizer: temporal train/test split, direction-aware PnL | 1 day |
| **P3-5** | PCA on standardized returns, analyze PC2+ | 4 hours |
| **P3-6** | Add VaR/CVaR to portfolio risk monitoring | 1 day |
| **P3-7** | Liquidity-adjusted position sizing (order book depth / ADV) | 2 days |
| **P3-8** | Economic rationale filter (sector, industry, supply chain validation) | 3 days |
| **P3-9** | Fat-tail robustness: Student-t innovations, robust regression for ╬▓ | 2 days |
| **P3-10** | Gradual position reduction as cointegration confidence decays | 2 days |

---

## 14. Scoring & Final Verdict

### Scores

| Dimension | Score | Rationale |
|-----------|-------|-----------|
| **System Architecture** | **5.5 / 10** | Solid module separation and layering, but duplicate signal pipelines, triple execution abstraction, dead code modules, empty CI/CD, and disconnected infrastructure (Pydantic schemas, liquidity filter, reconciler) significantly undermine architectural integrity. |
| **Statistical Robustness** | **5.0 / 10** | Core statistical methods are correctly implemented (EG, Johansen, Kalman, HMM). Bonferroni and NW consensus are excellent. However: ╬▓ scale inconsistency across paths, exit threshold unreachable, I(1) check off by default, Johansen doesn't gate, fail-open on test errors, CUSUM non-standard, ML has look-ahead bias. The statistical foundation is **present but undermined by integration bugs.** |
| **Production Readiness** | **3.0 / 10** | Live execution is a stub. No CI/CD. Stop managers not wired. IBKR integration is minimal. Reconciler not used. Shutdown manager not used. Flask dev server. Default JWT secret. Docker Python version mismatch. Missing requirements. The system can run backtests; it cannot safely trade real capital. |
| **Probability of Surviving 12 Months Live** | **25%** | With current bugs (exit never fires, drawdown breaker disabled, stops not wired, live execution stubbed), the system would experience uncontrolled losses during any sustained cointegration breakdown. The risk engine provides meaningful protection, but the gaps in strategy-level controls and the non-functional model retraining pipeline make long-term survival unlikely without the fixes outlined above. After Tier 1 + Tier 2 fixes, probability rises to ~55-65%. |

### Final Verdict

## **STRUCTURALLY FRAGILE**

EDGECORE demonstrates serious quantitative engineering ambition. The breadth of components ÔÇö from Kalman filters to PCA monitoring, from walk-forward CV to stress testing, from Markov regime detection to ML threshold optimization ÔÇö reflects institutional-grade design intent. The backtesting infrastructure (unified path) is genuinely well-built.

However, the system is in a **pre-production integration crisis**:

1. **Two signal pipelines** produce different signals for the same data
2. **Three execution abstractions** prevent clean order flow
3. **Critical safety code is dead** (HedgeRatioTracker, TrailingStopManager, BrokerReconciler, ShutdownManager ÔÇö all initialized, never called)
4. **The exit condition doesn't work** in one of the two signal paths
5. **The drawdown breaker doesn't work** due to a unit mismatch
6. **Model retraining crashes** on a KeyError
7. **Live execution doesn't exist** (stub raises RuntimeError)

The core statistical research is solid. The architecture has good bones. But the system has the unmistakable signature of **rapid feature development without integration testing** ÔÇö each component works in isolation, but the wiring between components is incomplete or broken.

**Bottom line:** EDGECORE is approximately 60% of the way to a deployable pair trading system. The remaining 40% is integration, testing, and production hardening ÔÇö which is where institutional systems live or die. The Tier 1 fixes (5 items, ~1 week) would address the immediate capital-endangering bugs. The Tier 2 fixes (~2-3 weeks) would bring the system to paper-trading readiness. Full live deployment requires all four tiers.

---

*Audit generated from real code analysis. No assumptions made. All findings traceable to specific file locations.*
