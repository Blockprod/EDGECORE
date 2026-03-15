# EDGECORE

**Modular Statistical Arbitrage System ÔÇö Blockprod Inc.**

---

## CONFIDENTIAL

Private repository. Contents are confidential and proprietary to Blockprod Inc.
Unauthorized access or distribution is strictly prohibited.

---

## Architecture Overview

EDGECORE is a production-grade statistical arbitrage (pair trading) system
for US equities via Interactive Brokers. The codebase is organized into
**9 composable modules** that form a clean pipeline from data ingestion to
order execution.

```
Market Data
    |
    v
+------------------+     +--------------------+     +------------------+
|  universe/       | --> |  pair_selection/    | --> |  signal_engine/  |
|  UniverseManager |     |  PairDiscoveryEngine|     |  SignalGenerator |
+------------------+     +--------------------+     +------------------+
                                                            |
                                                            v
+------------------+     +--------------------+     +------------------+
|  execution_engine| <-- |  portfolio_engine/  | <-- |  risk_engine/    |
|  ExecutionRouter |     |  PortfolioAllocator |     |  KillSwitch      |
+------------------+     +--------------------+     +------------------+
        |
        v
+------------------+     +--------------------+
|  backtester/     |     |  live_trading/     |
|  BacktestEngine  |     |  LiveTradingRunner |
+------------------+     +--------------------+
```

### Module Map

| Module | Purpose | Key Classes |
|--------|---------|-------------|
| `universe/` | Symbol universe, sector classification, liquidity filtering | `UniverseManager`, `Sector` |
| `pair_selection/` | Cointegration testing, Johansen confirmation, Bonferroni correction | `PairDiscoveryEngine`, `PairFilters` |
| `signal_engine/` | Z-score computation, adaptive thresholds, regime-aware signals | `SignalGenerator`, `ZScoreCalculator` |
| `risk_engine/` | Position risk, portfolio risk, emergency kill-switch | `PositionRiskManager`, `KillSwitch` |
| `portfolio_engine/` | Position sizing, concentration limits, beta-neutral hedging | `PortfolioAllocator`, `PortfolioHedger` |
| `execution_engine/` | Order routing: IBKR (live), paper, backtest modes | `ExecutionRouter`, `ExecutionMode` |
| `backtester/` | Backtest runner, walk-forward validation, OOS validation | `BacktestEngine`, `WalkForwardEngine` |
| `live_trading/` | Production + paper trading loops | `LiveTradingRunner`, `PaperTradingRunner` |
| `monitoring/` | Structured logging, Slack/email alerts, dashboard | ÔÇö |

### Internal (Implementation) Packages

These packages contain the proven implementations that the modules above compose:

| Package | Contains |
|---------|----------|
| `strategies/` | `PairTradingStrategy` ÔÇö core bar-by-bar signal logic |
| `models/` | Cointegration (EG, Johansen, NW), spread model, Kalman, regime detection |
| `risk/` | Beta-neutral hedger, PCA monitor, correlation guard, factor risk |
| `execution/` | IBKR engine, paper engine, trailing/time stops, order lifecycle |
| `backtests/` | Strategy simulator, event-driven, walk-forward, cost model, metrics |
| `validation/` | OOS validator, data validators |
| `data/` | DataLoader, liquidity filter, delisting guard, preprocessing |
| `config/` | Settings singleton, YAML loader, schema validation |
| `common/` | Error handling, retry, circuit breaker, typed API |

---

## Documentation

- [**ARCHITECTURE.md**](./ARCHITECTURE.md) ÔÇö Full 7-stage signal pipeline design
- [CONFIG_GUIDE.md](./CONFIG_GUIDE.md) ÔÇö Parameter tuning guide
- [OPERATIONS_RUNBOOK.md](./OPERATIONS_RUNBOOK.md) ÔÇö Troubleshooting & ops
- [BACKTEST_USAGE.md](./BACKTEST_USAGE.md) ÔÇö Backtesting guide

---

## Quick Start

### 1. Install

```bash
# Python 3.11.9 required
pip install -e ".[dev]"
cp .env.example .env       # fill in IBKR credentials
```

### 2. Configure

Edit `config/config.yaml` (unified config) or per-environment files:
- `config/dev.yaml` ÔÇö development defaults
- `config/prod.yaml` ÔÇö production settings
- `config/test.yaml` ÔÇö test overrides

### 3. Backtest

```python
from backtester import BacktestEngine, BacktestConfig

engine = BacktestEngine()
result = engine.run(BacktestConfig(
    symbols=["AAPL", "MSFT", "GOOGL", "META"],
    start_date="2022-01-01",
    end_date="2023-12-31",
))
print(result.summary())
```

Or via CLI:
```bash
python main.py --mode backtest --start 2022-01-01 --end 2024-01-01
```

### 4. Paper Trading

```python
from live_trading import PaperTradingRunner, TradingLoopConfig

runner = PaperTradingRunner(TradingLoopConfig(
    symbols=["AAPL", "MSFT", "GOOGL", "META"],
    bar_interval_seconds=60,
    initial_capital=100_000,
))
runner.start()
```

### 5. Walk-Forward Validation

```python
from backtester import WalkForwardEngine, WalkForwardConfig

engine = WalkForwardEngine()
result = engine.run(WalkForwardConfig(
    symbols=["AAPL", "MSFT", "GOOGL", "META"],
    start_date="2020-01-01",
    end_date="2023-12-31",
    num_periods=6,
))
print(f"Validated: {result.passed}")
```

---

## Deployment

### Docker

```bash
docker build -t edgecore:latest .
docker run -e EDGECORE_ENV=prod edgecore:latest python main.py
```

### Docker Compose

```bash
docker-compose up -d
docker-compose logs -f
```

See [OPERATIONS_RUNBOOK.md](./OPERATIONS_RUNBOOK.md) for production deployment.

---

## Sprint History

| Sprint | Focus | Tests | Status |
|--------|-------|-------|--------|
| S1 | Audit remediation (Bonferroni, OOS, costs) | ÔÇö | Done |
| S2 | Core features (hedge ratio, stops, regime) | 166 | Done |
| S3.1 | Comprehensive test suite | 101 | Done |
| S3.2 | Half-life refinement (AR(1) adaptive z-score) | 28 | Done |
| S3.3 | Architecture & operations docs | ÔÇö | Done |
| S4 | Modular migration (this README) | ÔÇö | Done |

**Total**: 295+ tests, 100% pass rate

---

## Key Features

### Statistical Rigor
- **Bonferroni correction** for multiple testing (70-80% FP reduction)
- **OOS validation**: 21-day forward test prevents overfitting
- **Johansen confirmation** + **Newey-West HAC consensus** (triple-gate)
- **Half-life filtering**: only pairs with HL < 60 days

### Risk Management
- **Kill-switch**: 6 independent halt conditions (drawdown, daily loss, consecutive losses, volatility, data staleness, manual)
- **Trailing stops**: volatility-adaptive (1-sigma)
- **Time stops**: 60-day max holding period
- **Concentration limits**: max 20% per pair, 40% per sector
- **Beta-neutral hedging** + PCA factor monitoring

### Adaptive Intelligence
- **Regime detection**: percentile + HMM Markov-switching
- **Kalman filter**: dynamic hedge ratio estimation
- **Adaptive thresholds**: entry/exit adjust by regime
- **Adaptive z-score window**: sized by half-life (AR(1))

---

**Status**: Production-Ready  
**Python**: 3.11.9  
**License**: Private ÔÇö Blockprod Inc.
