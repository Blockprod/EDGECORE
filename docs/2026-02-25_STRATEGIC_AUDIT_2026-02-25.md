# EDGECORE — Full Strategic Audit Report

**Date:** 2026-02-25  
**Auditor:** Senior Quant Developer & System Architect  
**Scope:** Full codebase audit for real-money production readiness  
**Codebase:** `C:\Users\averr\EDGECORE` — Statistical Arbitrage Pair Trading System  

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Architecture](#2-architecture)
3. [Strategy & Quant Logic](#3-strategy--quant-logic)
4. [Code Quality](#4-code-quality)
5. [Risk & Portfolio Engine](#5-risk--portfolio-engine)
6. [Backtesting & Validation](#6-backtesting--validation)
7. [Monitoring & Logging](#7-monitoring--logging)
8. [Configuration & Security](#8-configuration--security)
9. [Documentation](#9-documentation)
10. [Consolidated Action Items](#10-consolidated-action-items)

---

## 1. Executive Summary

EDGECORE is a well-architected statistical arbitrage platform with comprehensive coverage across pair discovery, cointegration testing, spread modeling, risk management, backtesting, and monitoring. The codebase demonstrates strong quant foundations (Engle-Granger, Johansen, Kalman, Markov HMM, PCA) and mature production concerns (kill switches, circuit breakers, reconciliation, audit trails).

### Overall Ratings

| Domain | Grade | Summary |
|--------|-------|---------|
| Architecture | **B** | Good modularity with domain separation; coupling issues and duplicate subsystems |
| Strategy & Quant Logic | **B+** | Strong foundations; advanced modules built but not wired into production path |
| Code Quality | **B-** | Well-structured individual modules; 3x config duplication, enum proliferation |
| Risk & Portfolio Engine | **A-** | Multi-layered, comprehensive; best-in-class for a pre-production system |
| Backtesting & Validation | **B+** | Walk-forward, OOS, stress tests present; key bugs in pass/fail logic |
| Monitoring & Logging | **A-** | Production-grade structured logging, alerting, dashboard, tracing |
| Configuration & Security | **C+** | Triple config system, Pydantic schemas unused, secrets in-memory only |
| Documentation | **C** | README stale, referenced docs missing, no ADRs |

### Critical Blockers for Production (P0)

| # | Issue | Impact |
|---|-------|--------|
| 1 | IBKR `submit_order()` case-sensitivity bug — all orders route to SELL | **Catastrophic** — every buy order becomes a sell |
| 2 | `live_trading/runner.py` `_tick()` is a stub — no trading logic | Live trading is non-functional |
| 3 | Bonferroni correction disabled by default in main strategy path | >50% false positive rate for 50+ symbols |
| 4 | `ModelRetrainingManager` accesses wrong dict keys — pair lifecycle broken | No pair revalidation in production |
| 5 | `paper_execution.py` inherits IBKR and calls live connection | Paper trading requires live broker connection |
| 6 | `signal.SIGUSR1` on Windows crashes `ShutdownManager` at startup | System won't start on Windows |
| 7 | Dockerfile references deleted `cpp/` directory + wrong env var | Docker builds fail |
| 8 | `WalkForwardEngine` references wrong key — pass/fail always fails | Walk-forward validation broken |

---

## 2. Architecture

### 2.1 Module Map

```
┌─────────────┐     ┌─────────────┐     ┌─────────────────┐
│ pair_select  │────▶│  strategies  │────▶│  signal_engine   │
│  discovery   │     │ pair_trading │     │  generator/zscore │
└─────────────┘     └──────┬──────┘     └────────┬────────┘
                           │                      │
                    ┌──────▼──────┐        ┌──────▼──────┐
                    │   models    │        │  risk_engine │
                    │ coint/spread│        │  kill_switch │
                    │ kalman/hmm  │        │  portfolio   │
                    └─────────────┘        └──────┬──────┘
                                                  │
┌─────────────┐     ┌──────────────┐       ┌──────▼──────┐
│  backtests   │────▶│  execution   │◀──────│ portfolio_  │
│ walk_forward │     │ ibkr/paper   │       │   engine    │
│ stress_test  │     │ stops/recon  │       └─────────────┘
└─────────────┘     └──────────────┘
        │
┌───────▼─────┐     ┌──────────────┐       ┌─────────────┐
│  backtester  │     │  monitoring  │       │    data      │
│   wrapper    │     │  api/alerts  │       │ loader/valid │
└──────────────┘     └──────────────┘       └─────────────┘
```

### 2.2 Strengths

- **Clean domain separation**: 15+ top-level modules with focused responsibilities
- **Strategy pattern** in execution (`PaperTradingMode`, `LiveTradingMode`, `BacktestMode`)
- **Composition over inheritance** in `PortfolioHedger`, `PositionRiskManager`
- **Common utilities** layer (`errors`, `circuit_breaker`, `retry`, `validators`) reduces duplication
- **Multiple entry points**: `main.py` (live/paper), `run_backtest.py`, `backtester/` wrappers

### 2.3 Findings

| ID | Finding | Criticality | Details |
|----|---------|-------------|---------|
| A-1 | **God function: `run_paper_trading()`** | Medium | ~300 lines handling init, reconciliation, crash recovery, trading loop, signal processing, stop-loss, cleanup. Should be decomposed into a `TradingSession` class. |
| A-2 | **Tight coupling in `main.py`** | Medium | Directly imports ~15 concrete classes. No dependency injection or factory pattern. Swapping implementations requires editing this file. |
| A-3 | **Duplicate subsystems** | High | Two risk systems (`risk/engine.py` + `risk_engine/portfolio_risk.py`), two execution hierarchies (`base.py→IBKREngine` + `modes.py`), three stop-management modules, three pair discovery implementations. |
| A-4 | **Hardcoded magic numbers** | Medium | `quantity=10.0`, `volatility=0.02`, `limit_price * 0.99`, `max_attempts=100`, `max_consecutive_errors=10` scattered in `main.py` without config references. |
| A-5 | **Dashboard thread leak** | Low | Flask API runs in a daemon thread with no graceful shutdown; port 5000 may not be released. |
| A-6 | **`run_live_trading` calls `input()`** | Medium | Blocks in headless/Docker environments; not testable. |
| A-7 | **`typed_api.py` unused facade** | Low | Creates new engine instances per call, hardcodes paper mode, imported by nothing. |

### 2.4 Action Items

- [ ] **TODO (A-1):** Refactor `run_paper_trading()` into a `TradingSession` class with `init()`, `reconcile()`, `recover()`, `tick()`, `shutdown()` methods.
- [ ] **TODO (A-2):** Introduce a `ServiceContainer` or factory for dependency injection. At minimum, create `create_execution_engine(mode)`, `create_risk_engine(settings)`.
- [ ] **TODO (A-3):** Consolidate duplicate subsystems: unify `risk/engine.py` and `risk_engine/portfolio_risk.py` under one risk facade; designate a single pair discovery implementation (`PairDiscoveryEngine`).
- [ ] **TODO (A-7):** Delete `common/typed_api.py` or wire it properly.

---

## 3. Strategy & Quant Logic

### 3.1 Pipeline Overview

$$\text{Prices} \xrightarrow[\text{E-G / Johansen}]{\text{Pair Discovery}} \text{Pairs} \xrightarrow[\text{OLS / Kalman}]{\text{Spread}} \xrightarrow[\text{Rolling / EWMA}]{\text{Z-score}} \xrightarrow[\text{Regime}]{\text{Threshold}} \text{Signal}$$

### 3.2 Component Assessment

| Component | File(s) | Grade | Notes |
|-----------|---------|-------|-------|
| Engle-Granger test | `models/cointegration.py` | **A** | Condition-number guard, graceful error handling, Bonferroni available |
| Johansen test | `models/johansen.py` | **A-** | Conservative rank = min(trace, max-eig), clean implementation |
| Newey-West HAC | `models/cointegration.py` | **A** | Dual-test consensus, robust to heteroskedasticity |
| Spread model (OLS) | `models/spread.py` | **B+** | Adaptive lookback by half-life, Z-score clamping ±6 |
| Kalman hedge ratio | `models/kalman_hedge.py` | **B** | Correct scalar filter, but no intercept state; re-runs full history |
| Adaptive thresholds | `models/adaptive_thresholds.py` | **B+** | Vol-percentile + half-life adjustment, ±0.3–0.5σ range |
| Regime detection (percentile) | `models/regime_detector.py` | **B** | Simple and fast; circular threshold issue |
| Regime detection (HMM) | `models/markov_regime.py` | **A-** | Probabilistic transitions, periodic re-fit, label-ordering by mean |
| Half-life estimator | `models/half_life_estimator.py` | **B+** | AR(1) correct but uses full-sample mean (look-ahead) |
| Stationarity monitor | `models/stationarity_monitor.py` | **B** | Rolling ADF with conservative p=0.10, but low power on short windows |
| Structural break detector | `models/structural_break.py` | **A-** | CUSUM + β stability, but **never called from trading path** |
| ML threshold optimizer | `models/ml_threshold_optimizer.py` | **C** | Trained on synthetic-only data; short P&L direction bug; shuffled splits |
| ML threshold validator | `models/ml_threshold_validator.py` | **A-** | Walk-forward OOS gate, auto-disable on degradation >20% |
| Pair discovery | `pair_selection/discovery.py` | **A** | Bonferroni default, Johansen + NW consensus, best discovery impl |

### 3.3 Critical Quant Findings

| ID | Finding | Criticality | Details |
|----|---------|-------------|---------|
| Q-1 | **Bonferroni correction disabled in main strategy** | **High** | `PairTradingStrategy.find_cointegrated_pairs()` sets `apply_bonferroni=False`. With 50 symbols (1,225 tests), expected false positives ≈ 61 at α=0.05. Only `PairDiscoveryEngine` applies it by default. |
| Q-2 | **`SignalGenerator` discards Kalman/DynamicSpreadModel** | High | Creates fresh `SpreadModel` (OLS) every call. All Sprint 4.2 Kalman infrastructure is wired but unused in the production signal path. |
| Q-3 | **`StructuralBreakDetector` is dead code in critical path** | High | Never called from `generate_signals()` or any strategy loop. Structural breaks go undetected. |
| Q-4 | **`I(1)` verification disabled by default** | Medium | `check_integration_order=False` in `engle_granger_test()`. EG can find "cointegration" between two stationary or I(2) series. |
| Q-5 | **ML training uses synthetic data only** | Medium | `ThresholdDataGenerator` creates AR(1) processes without fat tails, regime changes, or microstructure effects. Models cannot generalize to real spreads. |
| Q-6 | **ML trade P&L bug for shorts** | Medium | `simulate_trades()` always computes `pnl = exit_price - entry_price` regardless of direction. Short trade P&L is inverted. |
| Q-7 | **Three separate pair discovery implementations** | Medium | `PairTradingStrategy`, `PairDiscoveryEngine`, `ModelRetrainingManager` — different Bonferroni, key names, filter behavior. |
| Q-8 | **Exit threshold defaults to 0.0** | Medium | Strategy exits at exact mean — maximizes whipsaw and transaction costs. Should default to 0.3–0.5. |
| Q-9 | **Kalman filter lacks intercept state** | Low | Spread = y − βx (no α). Introduces bias when intercept is non-zero. |
| Q-10 | **Half-life estimator uses full-sample mean** | Low | Demeaning step uses complete-history mean — look-ahead bias in rolling context. |

### 3.4 Action Items

- [ ] **TODO (Q-1):** Enable Bonferroni in `PairTradingStrategy` or replace its discovery with `PairDiscoveryEngine.discover()`.
- [ ] **TODO (Q-2):** Route `SignalGenerator` through `DynamicSpreadModel` to leverage Kalman β and adaptive thresholds.
- [ ] **TODO (Q-3):** Add `StructuralBreakDetector.check_from_prices()` call inside `SignalGenerator.generate()` — force exit on detected breaks.
- [ ] **TODO (Q-4):** Set `check_integration_order=True` by default in production pair discovery.
- [ ] **TODO (Q-5):** Train ML threshold models on historical pair spread data, not synthetic AR(1).
- [ ] **TODO (Q-6):** Fix P&L calc: `pnl = (exit - entry) if long else (entry - exit)`.
- [ ] **TODO (Q-7):** Consolidate to single discovery path: `PairDiscoveryEngine`.
- [ ] **TODO (Q-8):** Change default `exit_z_score` from 0.0 to 0.3.

---

## 4. Code Quality

### 4.1 Strengths

- Consistent use of `structlog` for structured logging
- Clean dataclass definitions with `__post_init__` validation
- Type hints on most public APIs
- Good use of Python ABCs (`BaseStrategy`, `BaseExecutionEngine`)
- Comprehensive error taxonomy with category-based handling

### 4.2 Findings

| ID | Finding | Criticality | Details |
|----|---------|-------------|---------|
| C-1 | **Triple config system** | **High** | Dataclasses (`settings.py`), Pydantic v2 models (`schemas.py`), TypedDicts (`types.py`) define the same concepts with different field names. Pydantic schemas are **never invoked**. |
| C-2 | **Enum duplication** | Medium | `OrderSide`, `OrderType`, `OrderStatus`, `ExecutionMode`, `CircuitBreakerState` each have 2–3 definitions across modules. Importing the wrong one causes silent type mismatches. |
| C-3 | **`common/types.py` is 812 lines** | Medium | Single file covers 14 enums + 11 aliases + 40 TypedDicts. Should be split into `types/orders.py`, `types/risk.py`, `types/backtest.py`. |
| C-4 | **`DataError` constructor arg order mismatch** | Medium | `DataError.__init__(message, original_error, category)` swaps order vs parent `TradingError.__init__(message, category, original_error)`. `DataError("msg", ErrorCategory.RETRYABLE)` silently stores the enum as `original_error`. |
| C-5 | **`ConfigError` name collision** | Medium | `common.errors.ConfigError(TradingError)` vs `common.validators.ConfigError(ValidationError)` — different hierarchies, same name. |
| C-6 | **Overlapping retry systems** | Medium | `error_handler.with_error_handling` and `retry.retry_with_backoff` are independent decorators. `with_error_handling` lacks jitter; `retry_with_backoff` has jitter but is less used. Neither composes with circuit breaker. |
| C-7 | **`datetime.utcnow()` deprecated** | Low | Used in `circuit_breaker.py`, `secrets.py`, `order_lifecycle.py`. Should use `datetime.now(timezone.utc)` (Python 3.12+). |
| C-8 | **`validate_symbol` too restrictive** | Low | Regex `^[A-Z]{1,5}$` rejects `BRK.B`, `BF.B`, digit-containing tickers. |
| C-9 | **Dead code modules** | Low | `config/schemas.py` (never imported), `common/typed_api.py` (never imported), `RetryStats` (never instantiated), `config.yaml` sections (`market`, `portfolio`, `validation`, `monitoring`) silently ignored by `Settings`. |
| C-10 | **`settings.py` YAML loading accepts typos** | Medium | `setattr(self.strategy, key, value)` for every YAML key — `entry_z_scroe: 5.0` creates a new attribute silently instead of raising an error. |

### 4.3 Test Coverage

| Subsystem | Test Files | Test Functions | Coverage Assessment |
|-----------|-----------|----------------|---------------------|
| Models | 19 | ~380 | **Strong** — cointegration, Kalman, HMM, thresholds, half-life |
| Backtests | 7 | ~110 | **Good** — cost model, walk-forward, event-driven, look-ahead |
| Monitoring | 0 (in `tests/`) | 0 | **Gap** — no monitoring tests found in `tests/` directory |
| Execution | 3 | ~45 | **Thin** — only concentration, trailing stop, time stop |
| Data | 2 | ~30 | **Thin** — liquidity filter and outlier pipeline only |
| Risk | 1 | ~15 | **Weak** — only spread correlation guard |
| Strategies | 3 | ~50 | **Fair** — cache TTL, internal limits, leg correlation |
| Validation | 1 | ~10 | **Weak** — OOS validator only |
| Config | 1 | ~10 | **Weak** — YAML universe validation only |
| Integration | 1 | ~15 | **Weak** — single integration test file |
| **Total** | **38** | **~774** | **Moderate** — strong on models, weak on risk/execution/integration |

### 4.4 Action Items

- [ ] **TODO (C-1):** Delete `config/schemas.py` or replace dataclasses in `settings.py` with Pydantic models. One config system, not three.
- [ ] **TODO (C-2):** Create a single canonical source for each enum in `common/types.py` and re-export. Deprecate module-local definitions.
- [ ] **TODO (C-3):** Split `common/types.py` into `common/types/` package.
- [ ] **TODO (C-4):** Fix `DataError.__init__` arg order to match parent.
- [ ] **TODO (C-6):** Consolidate retry logic: compose `retry_with_backoff` with `CircuitBreaker`. Delete `with_error_handling`.
- [ ] **TODO:** Add tests for: `risk/engine.py`, `execution/ibkr_engine.py`, `execution/modes.py`, `execution/order_lifecycle.py`, `execution/reconciler.py`, `monitoring/` subsystem.

---

## 5. Risk & Portfolio Engine

### 5.1 Risk Layer Architecture

```
                    ┌──────────────────┐
                    │   KillSwitch     │  ← Emergency halt (5 auto-checks + manual)
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │ PortfolioRiskMgr  │  ← Drawdown, daily loss, heat, circuit breaker
                    └────────┬─────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
    ┌─────────▼───┐  ┌──────▼──────┐  ┌───▼─────────┐
    │ RiskEngine   │  │ Concentration│  │ PortfolioHedger│
    │ (pre-trade)  │  │   Manager    │  │ (β-neutral)    │
    └──────────────┘  └─────────────┘  └───────────────┘
                                            │
                              ┌──────────────┼───────────────┐
                              │              │               │
                    ┌─────────▼──┐  ┌───────▼──────┐  ┌────▼────────┐
                    │ SpreadCorr  │  │ PCASpread    │  │ BetaNeutral │
                    │   Guard     │  │  Monitor     │  │   Hedger    │
                    └────────────┘  └──────────────┘  └─────────────┘
```

### 5.2 Strengths

- **Multi-layered defense**: kill switch → portfolio risk → pre-trade gate → position-level stops
- **KillSwitch requires manual reset** — prevents accidental auto-recovery
- **PCA factor concentration** detection (beyond simple pairwise correlation)
- **Three-layer hedging**: spread correlation + PCA + beta-neutral
- **Four position sizing methods**: equal-weight, vol-inverse, half-Kelly, signal-weighted
- **Comprehensive stop management**: trailing (Z-score based), time stops, P&L stops, partial profit-taking, breakeven protection

### 5.3 Findings

| ID | Finding | Criticality | Details |
|----|---------|-------------|---------|
| R-1 | **Portfolio circuit breaker auto-resumes** | **High** | `PortfolioRiskManager` resumes trading after `circuit_breaker_cooldown_bars` (10 bars). In production, auto-resume after drawdown should require manual confirmation. |
| R-2 | **KillSwitch state not persisted** | **High** | In-memory only. Process crash → restart → trades before kill switch re-triggers. |
| R-3 | **Dual risk state tracking** | Medium | `RiskEngine` and `PortfolioRiskManager` both track drawdown, daily loss, consecutive losses independently. State synchronization risk. |
| R-4 | **`daily_loss` never auto-resets** | Medium | `RiskEngine` requires caller to invoke `reset_daily_stats()`. Missing reset → daily loss accumulates across days → permanent trading halt. |
| R-5 | **No margin monitoring** | Medium | No check against broker margin requirements before sizing. |
| R-6 | **`ConcentrationManager.check_entry()` has side effects** | Medium | Calling `check_entry()` also registers the position. No check-only path. |
| R-7 | **`concentration_pct` metric is misleading** | Medium | Computed as `|net|/gross` — measures hedging, not portfolio concentration. A symbol with 10L+10S = 0% "concentration" but 100% exposure. |
| R-8 | **No minimum position size** | Low | `PortfolioAllocator` can allocate tiny positions that cost more in commissions than they generate. |
| R-9 | **Monte Carlo correlation not implemented** | Low | `create_correlated_simulations()` computes Cholesky matrix but never applies it. Assets simulate independently. |
| R-10 | **Position stops use global singleton** | Low | `_stop_manager` in `position_stops.py` is module-level — not thread-safe, problematic for concurrent strategies. |

### 5.4 Action Items

- [ ] **TODO (R-1):** Change portfolio circuit breaker to require manual reset in production mode.
- [ ] **TODO (R-2):** Persist kill switch state to disk (append to audit trail). On startup, check if kill switch was active before crash.
- [ ] **TODO (R-3):** Unify risk tracking into a single `RiskState` that both systems reference.
- [ ] **TODO (R-4):** Add automatic daily reset based on trading calendar in `RiskEngine`.
- [ ] **TODO (R-5):** Add pre-trade margin check via IBKR `whatIfOrder()` API.
- [ ] **TODO (R-6):** Add `check_only()` method to `ConcentrationManager` that validates without committing.

---

## 6. Backtesting & Validation

### 6.1 Capabilities Matrix

| Feature | Status | Implementation |
|---------|--------|----------------|
| Walk-forward (expanding window) | ✅ Complete | `backtests/walk_forward.py` — per-period retraining, OOS pair validation |
| Out-of-sample validation | ✅ Complete | `validation/oos_validator.py` — cointegration persistence, half-life drift |
| Cost model (4-leg) | ✅ Complete | `backtests/cost_model.py` — maker/taker + slippage + borrow + funding |
| Event-driven simulation | ✅ Complete | `backtests/event_driven.py` — partial fills, market impact |
| Stress testing | ⚠️ Partial | 4/5 scenarios; no liquidity drought, no asymmetric shocks |
| Parameter cross-validation | ✅ Complete | `backtests/parameter_cv.py` — walk-forward CV with stability analysis |
| Look-ahead prevention | ✅ Complete | Unified path via `run_unified()`, cache isolation in WF |
| MtM accounting | ⚠️ Partial | `strategy_simulator.py` has it; `event_driven.py` does not |
| Regime-aware sizing | ✅ Complete | `strategy_simulator.py` — volatility + quality multipliers |

### 6.2 Findings

| ID | Finding | Criticality | Details |
|----|---------|-------------|---------|
| B-1 | **`WalkForwardEngine` wrong key name** | **High** | References `per_period_results` but actual key is `per_period_metrics`. Pass/fail always returns "not passed". |
| B-2 | **Legacy `run()` still functional** | Medium | Legacy path uses 1% allocation vs unified's 30%, 15bps fixed costs vs 4bps. Produces wildly different results. Should be fully blocked. |
| B-3 | **Walk-forward averages `max_drawdown`** | Medium | `_aggregate_metrics()` averages max_drawdown across periods. Drawdowns don't average meaningfully — should report worst period or compute from concatenated equity curve. |
| B-4 | **`strategy_simulator.py` is 908 lines** | Medium | Combines ~8 exit/sizing mechanisms in one file. Hidden interactions between trailing stops, time stops, P&L stops, circuit breaker, regime sizing, quality allocation. |
| B-5 | **Default 30% allocation per pair** | Medium | Single pair consumes 30% of capital — extremely concentrated. Default should be lower (10–15%) for a market-neutral strategy. |
| B-6 | **Cost model uses calendar days for borrow** | Low | `holding_cost()` divides by 365 but system operates on 252 trading days — overstates borrow costs by ~30%. |
| B-7 | **`BacktestMetrics.summary()` shows "EUR"** | Low | System is US equity-focused — should display "USD". |
| B-8 | **OOS validator rejects p ∈ (0.001, 0.05)** | Low | Pairs with p=0.002 classified as "weak" despite being highly significant. Rule is too aggressive. |
| B-9 | **Stress testing `survived` check wrong sign** | Low | `max_drawdown > -1.0` uses wrong sign convention — `max_drawdown` from metrics is already negative. |

### 6.3 Action Items

- [ ] **TODO (B-1):** Fix key reference in `backtester/walk_forward.py` from `per_period_results` to `per_period_metrics`.
- [ ] **TODO (B-2):** Remove or hard-block legacy `run()` in `backtests/runner.py`. Add `raise DeprecationError`.
- [ ] **TODO (B-3):** Compute max_drawdown from concatenated equity curve in `_aggregate_metrics()`.
- [ ] **TODO (B-5):** Reduce default `allocation_per_pair_pct` from 30.0 to 10.0–15.0.
- [ ] **TODO (B-8):** Remove the (0.001, 0.05) "weak p-value" rejection band in `oos_validator.py`.

---

## 7. Monitoring & Logging

### 7.1 Infrastructure Map

| Component | File | Status |
|-----------|------|--------|
| Structured logging | `monitoring/logger.py`, `logging_config.py` | ✅ Production-grade (structlog + JSON + rotation) |
| Alert lifecycle | `monitoring/alerter.py` | ✅ Complete (create → ack → resolve, severity routing) |
| Slack integration | `monitoring/slack_alerter.py` | ✅ Throttled, graceful degradation |
| Email alerter | `monitoring/email_alerter.py` | ⚠️ `MIMEMultipart` usage incorrect |
| REST dashboard | `monitoring/api.py` | ✅ Flask with rate limiting, API key auth |
| Dashboard data | `monitoring/dashboard.py` | ✅ System + risk + positions + orders + performance |
| OpenAPI spec | `monitoring/api_schema.py` | ✅ Full 3.0 spec |
| Latency tracking | `monitoring/latency.py` | ❌ Runtime crash — `numpy` not imported |
| Profiler | `monitoring/profiler.py` | ✅ `perf_counter()` based, bottleneck detection |
| Distributed tracing | `monitoring/tracing.py` | ✅ OpenTelemetry-like spans |
| Cache layer | `monitoring/cache.py` | ✅ Thread-safe LRU with TTL |
| API security | `monitoring/api_security.py` | ⚠️ In-memory rate limiter, hardcoded JWT secret |
| Prometheus metrics | `monitoring/metrics.py` | ❌ Placeholder — no client library integration |

### 7.2 Findings

| ID | Finding | Criticality | Details |
|----|---------|-------------|---------|
| M-1 | **`latency.py` crashes at runtime** | **High** | Uses `np.percentile()` without importing numpy. `NameError` on first latency metric calculation. |
| M-2 | **Logger handler accumulation** | Medium | `setup_logger()` calls `root_logger.addHandler()` every time — duplicate log entries on repeated calls. |
| M-3 | **Prometheus metrics is placeholder** | Medium | `SystemMetrics` exports text format but no `prometheus_client` integration, no histograms, no push gateway. |
| M-4 | **Rate limiter is in-memory only** | Medium | Resets on restart, doesn't work across multiple worker processes. |
| M-5 | **JWT secret hardcoded** | Medium | Default secret in `api_security.py` — production warning present but no enforcement. |
| M-6 | **`email_alerter.py` MIME construction** | Low | `MIMEMultipart('text', 'plain')` is incorrect — should be `MIMEMultipart()` + `MIMEText()` part. |
| M-7 | **Dashboard `cpu_percent(interval=0.1)`** | Low | Blocks 100ms per dashboard call. Use `cpu_percent(interval=None)` for non-blocking. |
| M-8 | **No monitoring tests in `tests/`** | Medium | Zero test files for the monitoring subsystem despite it being one of the largest modules. |

### 7.3 Action Items

- [ ] **TODO (M-1):** Add `import numpy as np` at module level in `monitoring/latency.py`.
- [ ] **TODO (M-2):** Guard against duplicate handler registration: check `if not root_logger.handlers:` before adding.
- [ ] **TODO (M-3):** Integrate `prometheus_client` library for proper metric exposition.
- [ ] **TODO (M-5):** Enforce `JWT_SECRET` from environment variable; fail startup if not set in production.
- [ ] **TODO (M-8):** Add test suite for `monitoring/alerter.py`, `api.py`, `api_security.py`, `latency.py`.

---

## 8. Configuration & Security

### 8.1 Config System Assessment

```
┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
│  settings.py         │    │  schemas.py          │    │  types.py           │
│  @dataclass configs  │    │  Pydantic models     │    │  TypedDicts          │
│  ✅ USED by system   │    │  ❌ NEVER INVOKED    │    │  ❌ NOT ENFORCED     │
│  ⚠️ No validation    │    │  ✅ Has validation   │    │  ⚠️ Structural only  │
└─────────────────────┘    └─────────────────────┘    └─────────────────────┘
                  Three representations. Zero integration.
```

### 8.2 Findings

| ID | Finding | Criticality | Details |
|----|---------|-------------|---------|
| S-1 | **Pydantic schemas never invoked** | **High** | `FullConfigSchema` with excellent field validation exists but is dead code. `Settings` uses raw dataclasses that accept anything. |
| S-2 | **`config.yaml` sections silently ignored** | High | `market`, `portfolio`, `validation`, `monitoring` sections exist in YAML but `Settings._load_yaml()` only processes `strategy`, `trading_universe`, `risk`, `execution`, `backtest`, `secrets`. |
| S-3 | **YAML loading accepts typos** | High | `setattr(self.strategy, key, value)` creates new attributes for misspelled keys instead of raising errors. A config typo could silently disable a risk limit. |
| S-4 | **Settings singleton not thread-safe** | Medium | `__new__` + `__init__` with `_initialized` flag has TOCTOU race in multi-threaded Flask context. |
| S-5 | **Secrets vault is in-memory only** | Medium | No persistence, no encryption at rest. Process death loses all vault state. |
| S-6 | **Secrets `load_from_env` false positives** | Low | Matches any env var containing "key", "token", "password" — captures `PYTEST_CURRENT_TEST`, `PYTHONDONTWRITEBYTECODE`. |
| S-7 | **Dependency version conflicts** | **High** | `pyproject.toml` pins `vectorbt==0.25.0`, `requirements.txt` pins `>=0.26.0`. `pydantic` missing from both. `requires-python = "==3.11.9"` rejects 3.11.10+. |
| S-8 | **Docker `ENVIRONMENT` vs `EDGECORE_ENV`** | High | Dockerfile sets `ENVIRONMENT=production` but Settings reads `EDGECORE_ENV`. Falls back to `dev` config in production container. |
| S-9 | **Redis/Elasticsearch unauthenticated** | Medium | `docker-compose.yml`: Redis runs without `requirepass`, Elasticsearch has `xpack.security.enabled: "false"`. |
| S-10 | **All ports on 0.0.0.0** | Medium | Docker exposes ports on all interfaces — should bind to `127.0.0.1` in production. |
| S-11 | **Grafana default password** | Low | `${GRAFANA_PASSWORD:-admin}` defaults to `admin`. |

### 8.3 Action Items

- [ ] **TODO (S-1):** Replace dataclass configs with Pydantic models from `schemas.py`. One validation system.
- [ ] **TODO (S-3):** Add `__setattr__` guard on config dataclasses that rejects unknown attribute names.
- [ ] **TODO (S-7):** Reconcile `pyproject.toml` and `requirements.txt`. Pin compatible ranges. Add `pydantic>=2.0,<3.0`. Loosen `requires-python` to `>=3.11,<3.13`.
- [ ] **TODO (S-8):** Change Dockerfile to `ENV EDGECORE_ENV=production`.
- [ ] **TODO (S-9):** Add `requirepass` to Redis and enable Elasticsearch security in `docker-compose.yml`.
- [ ] **TODO (S-10):** Bind all ports to `127.0.0.1` in docker-compose; use reverse proxy for external access.

---

## 9. Documentation

### 9.1 Current State

| Document | Status | Issues |
|----------|--------|--------|
| `README.md` | ⚠️ Stale | References non-existent classes (`BacktestEngine`, `BacktestConfig`). API examples don't match code. |
| `ARCHITECTURE.md` | ❌ Missing | Referenced in README but doesn't exist. |
| `CONFIG_GUIDE.md` | ❌ Missing | Referenced in README but doesn't exist. |
| `OPERATIONS_RUNBOOK.md` | ❌ Missing | Referenced in README but doesn't exist. |
| `BACKTEST_USAGE.md` | ❌ Missing | Referenced in README but doesn't exist. |
| `monitoring/API_SECURITY.md` | ✅ Exists | API security documentation. |
| `monitoring/DASHBOARD_CACHING.md` | ✅ Exists | Cache strategy documentation. |
| `monitoring/DEPLOYMENT_GUIDE.md` | ✅ Exists | Deployment instructions. |
| `monitoring/PRODUCTION_LOGGING.md` | ✅ Exists | Logging configuration guide. |
| Module docstrings | ⚠️ Partial | Most modules have docstrings; some lack usage examples. |
| ADRs (Architecture Decision Records) | ❌ Missing | No record of design decisions (why triple config, why two risk engines, etc.). |

### 9.2 Findings

| ID | Finding | Criticality | Details |
|----|---------|-------------|---------|
| D-1 | **README code examples broken** | Medium | Quick-start examples reference `BacktestEngine`, `WalkForwardEngine`, `PaperTradingRunner` — class names don't match code. |
| D-2 | **Four referenced docs missing** | Medium | `ARCHITECTURE.md`, `CONFIG_GUIDE.md`, `OPERATIONS_RUNBOOK.md`, `BACKTEST_USAGE.md` — dead links. |
| D-3 | **No onboarding guide** | Medium | New developer has no clear path from "clone repo" to "running backtest" to "understanding architecture". |
| D-4 | **No ADRs** | Low | Design decisions (triple config system, two risk engines, C++ acceleration attempt) are not documented. |
| D-5 | **"295+ tests, 100% pass rate" claim** | Low | README claims this but actual count is ~774 test functions across 38 files. Claim is outdated and unverified. |

### 9.3 Action Items

- [ ] **TODO (D-1):** Update README quick-start examples to match actual API (`BacktestRunner.run_unified()`, etc.).
- [ ] **TODO (D-2):** Create or remove references to missing docs.
- [ ] **TODO (D-3):** Write `docs/ONBOARDING.md` with step-by-step (install → config → first backtest → architecture overview).
- [ ] **TODO (D-4):** Create `docs/adr/` folder with ADRs for key design decisions.

---

## 10. Consolidated Action Items

### Priority 0 — Must Fix Before Production

| # | Action | Domain | Effort |
|---|--------|--------|--------|
| 1 | Fix IBKR `submit_order()` case-sensitivity: `order.side.value.lower()` or compare uppercase | Execution | 1h |
| 2 | Implement `live_trading/runner.py` `_tick()` with real signal → risk → order flow | Architecture | 3d |
| 3 | Enable Bonferroni correction in `PairTradingStrategy` (or delegate to `PairDiscoveryEngine`) | Quant | 2h |
| 4 | Fix `ModelRetrainingManager` dict keys (`p_value` → `adf_pvalue`, `hedge_ratio` → `beta`) | Quant | 1h |
| 5 | Decouple `PaperExecutionEngine` from `IBKRExecutionEngine` — no live connection needed | Execution | 4h |
| 6 | Guard `signal.SIGUSR1` with `hasattr(signal, 'SIGUSR1')` in `ShutdownManager` | Execution | 30m |
| 7 | Fix Dockerfile: remove `COPY cpp/`, change `ENVIRONMENT` → `EDGECORE_ENV`, add `.dockerignore` | Deployment | 1h |
| 8 | Fix `WalkForwardEngine` key: `per_period_results` → `per_period_metrics` | Backtest | 30m |
| 9 | Add `import numpy as np` to `monitoring/latency.py` | Monitoring | 5m |

### Priority 1 — Required for Robustness

| # | Action | Domain | Effort |
|---|--------|--------|--------|
| 10 | Route `SignalGenerator` through `DynamicSpreadModel` / Kalman | Quant | 1d |
| 11 | Wire `StructuralBreakDetector` into signal generation path | Quant | 4h |
| 12 | Consolidate config to single system (Pydantic) — delete dataclass configs | Config | 2d |
| 13 | Unify `OrderStatus`, `OrderSide`, `ExecutionMode` enums to single canonical source | Code Quality | 4h |
| 14 | Persist kill switch state to audit trail | Risk | 4h |
| 15 | Change portfolio circuit breaker to manual-reset in production | Risk | 2h |
| 16 | Reconcile `pyproject.toml` and `requirements.txt` dependency versions | Build | 2h |
| 17 | Add automatic daily reset to `RiskEngine` | Risk | 2h |
| 18 | Remove legacy `BacktestRunner.run()` or raise `DeprecationError` | Backtest | 1h |
| 19 | Consolidate three pair discovery implementations into one | Quant | 1d |
| 20 | Fix ML threshold training: real data, correct P&L direction, temporal splits | Quant | 2d |

### Priority 2 — Recommended Improvements

| # | Action | Domain | Effort |
|---|--------|--------|--------|
| 21 | Refactor `run_paper_trading()` into `TradingSession` class | Architecture | 1d |
| 22 | Add dependency injection / service container | Architecture | 2d |
| 23 | Split `common/types.py` (812 lines) into package | Code Quality | 4h |
| 24 | Fix `DataError` constructor arg order | Code Quality | 30m |
| 25 | Change exit Z-score default from 0.0 to 0.3 | Quant | 30m |
| 26 | Reduce default `allocation_per_pair_pct` from 30% to 10–15% | Backtest | 30m |
| 27 | Add pre-trade margin check via IBKR `whatIfOrder()` | Risk | 4h |
| 28 | Add `check_only()` to `ConcentrationManager` | Risk | 1h |
| 29 | Integrate proper `prometheus_client` for metrics | Monitoring | 4h |
| 30 | Fix email alerter MIME construction | Monitoring | 30m |
| 31 | Update README with correct API examples | Docs | 2h |
| 32 | Create missing documentation (ARCHITECTURE, CONFIG_GUIDE, ONBOARDING) | Docs | 2d |
| 33 | Enable `check_integration_order=True` by default | Quant | 30m |
| 34 | Add Kalman intercept state | Quant | 4h |
| 35 | Secure Redis/Elasticsearch in docker-compose | Security | 1h |

### Priority 3 — Nice to Have

| # | Action | Domain | Effort |
|---|--------|--------|--------|
| 36 | Add IBKR reconnection logic with exponential backoff | Execution | 4h |
| 37 | Add order rate limiting | Execution | 2h |
| 38 | Implement Monte Carlo correlated simulation (finish Cholesky) | Execution | 2h |
| 39 | Add `omega_ratio`, `information_ratio` to `BacktestMetrics` | Backtest | 2h |
| 40 | Implement asymmetric shock scenarios in stress testing | Backtest | 4h |
| 41 | Add ADR folder for design decisions | Docs | 1d |
| 42 | Fix `validate_symbol` regex for `BRK.B` style tickers | Code Quality | 30m |
| 43 | Replace `datetime.utcnow()` with `datetime.now(timezone.utc)` everywhere | Code Quality | 1h |
| 44 | Thread-safe `Settings` singleton with `threading.Lock` | Config | 1h |
| 45 | Add IBKR connection pooling in `DataLoader` | Data | 4h |

---

## Appendix A: File-Level Risk Heat Map

| Risk Level | Files |
|------------|-------|
| 🔴 **Critical** | `execution/ibkr_engine.py`, `live_trading/runner.py`, `execution/paper_execution.py`, `Dockerfile` |
| 🟠 **High** | `strategies/pair_trading.py` (Bonferroni), `config/settings.py` (typo acceptance), `models/model_retraining.py` (wrong keys), `backtester/walk_forward.py` (wrong key) |
| 🟡 **Medium** | `main.py` (god function), `execution/modes.py` (enum confusion), `risk_engine/portfolio_risk.py` (auto-resume), `models/ml_threshold_optimizer.py` (synthetic-only) |
| 🟢 **Clean** | `models/cointegration.py`, `pair_selection/discovery.py`, `risk_engine/kill_switch.py`, `execution/time_stop.py`, `backtests/cost_model.py`, `monitoring/slack_alerter.py` |

## Appendix B: Dependency Graph Concerns

```
models/ml_threshold_optimizer.py  →  Uses sklearn.ensemble.RandomForestRegressor
                                     But sklearn is NOT in requirements.txt or pyproject.toml
                                     ⚠️ Missing dependency — import will fail on clean install

models/markov_regime.py           →  Uses hmmlearn.hmm.GaussianHMM
                                     But hmmlearn is NOT in requirements.txt or pyproject.toml
                                     ⚠️ Missing dependency

monitoring/api.py                 →  Uses flask
                                     In requirements.txt but NOT in pyproject.toml
                                     ⚠️ Partial dependency declaration
```

---

*End of audit report. Generated: 2026-02-25.*
