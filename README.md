<div align="center">

<<<<<<< HEAD
```
╔═══════════════════════════════════════════════════════════╗
║                       E D G E C O R E                     ║
║          Statistical Arbitrage System — US Equities       ║
╚═══════════════════════════════════════════════════════════╝
```

![Python](https://img.shields.io/badge/Python-3.11.9-3776AB?style=flat-square&logo=python&logoColor=white)
![Broker](https://img.shields.io/badge/Broker-Interactive%20Brokers-E8312A?style=flat-square)
![Tests](https://img.shields.io/badge/Tests-2808%20passing-2ea44f?style=flat-square&logo=pytest&logoColor=white)
![Status](https://img.shields.io/badge/Status-Production--Ready-success?style=flat-square)
![License](https://img.shields.io/badge/License-Proprietary-lightgrey?style=flat-square)

*Production-grade pair trading engine — 9 composable modules — Blockprod Inc.*

</div>

---

> **CONFIDENTIAL** — Private repository. Contents are proprietary to Blockprod Inc.
> Unauthorized access or distribution is strictly prohibited.

---

## Architecture

EDGECORE implements a **unidirectional pipeline** from raw market data to broker execution.
Each stage is isolated, testable and replaceable — no shared mutable state across modules.

```
                        ┌────────────────────────────────┐
                        │         EDGECORE PIPELINE       │
                        └────────────────────────────────┘

                              [ Market Data / IBKR ]
                                        │
                          ┌─────────────▼────────────┐
                          │       universe/           │   Symbol filtering,
                          │     UniverseManager       │   liquidity, sectors
                          └─────────────┬─────────────┘
                                        │
                          ┌─────────────▼────────────┐
                          │     pair_selection/       │   Cointegration (EG +
                          │   PairDiscoveryEngine     │   Johansen + Bonferroni)
                          └─────────────┬─────────────┘
                                        │
                          ┌─────────────▼────────────┐
                          │     signal_engine/        │   Z-score × 0.70
                          │  SignalGenerator          │   + momentum × 0.30
                          └─────────────┬─────────────┘
                                        │
                          ┌─────────────▼────────────┐
                          │      risk_engine/         │   3-tier kill-switch,
                          │  KillSwitch · PortfolioRM │   drawdown, stops
                          └─────────────┬─────────────┘
                                        │
                          ┌─────────────▼────────────┐
                          │    portfolio_engine/      │   Sizing, concentration
                          │    PortfolioAllocator     │   limits, beta-neutral
                          └─────────────┬─────────────┘
                                        │
                          ┌─────────────▼────────────┐
                          │   execution_engine/       │   Routes to IBKR live,
                          │    ExecutionRouter        │   paper or backtest
                          └────────┬──────────┬───────┘
                                   │          │
                            ┌──────▼──┐  ┌───▼──────┐
                            │  live/  │  │backtest/ │
                            └─────────┘  └──────────┘
```

---

## Modules

| Module | Role | Key Classes |
|:---|:---|:---|
| `universe/` | Symbol universe, liquidity filter, sector classification | `UniverseManager` |
| `pair_selection/` | Cointegration testing, Johansen, Bonferroni | `PairDiscoveryEngine` |
| `signal_engine/` | Z-score, adaptive thresholds, regime-aware alpha | `SignalGenerator`, `SignalCombiner` |
| `risk_engine/` | Position & portfolio risk, 3-tier emergency halt | `PositionRiskManager`, `KillSwitch` |
| `portfolio_engine/` | Position sizing, concentration limits, beta-neutral | `PortfolioAllocator` |
| `execution_engine/` | Order routing — IBKR live / paper / backtest | `ExecutionRouter` |
| `backtester/` | Walk-forward, OOS validation | `BacktestEngine`, `WalkForwardEngine` |
| `live_trading/` | Production & paper trading loops | `LiveTradingRunner` |
| `monitoring/` | Structured logs, Slack/email, Prometheus/Grafana | — |

<details>
<summary>▸ Internal implementation packages</summary>
<br>

| Package | Contents |
|:---|:---|
| `strategies/` | `PairTradingStrategy` — bar-by-bar signal logic |
| `models/` | Cointegration (EG, Johansen, NW-HAC), Kalman filter, regime detection |
| `risk/` | Beta-neutral hedger, PCA monitor, correlation guard, factor risk |
| `execution/` | IBKR engine, paper engine, trailing/time stops, order lifecycle |
| `backtests/` | Event-driven simulator, cost model, stress testing, metrics |
| `validation/` | OOS validator, data integrity validators |
| `data/` | DataLoader, liquidity filter, delisting guard, corporate actions (IBKR-native) |
| `config/` | Settings singleton, YAML loader, schema validation |
| `common/` | Retry + backoff, circuit breaker, IBKR rate limiter, typed API |

</details>

---

## Key Features

<table>
<tr>
<td width="33%" valign="top">

**Statistical Rigor**
- Bonferroni correction — 70% FP reduction
- Triple-gate: EG + Johansen + Newey-West HAC
- OOS forward test — 21-day validation window
- Half-life filter — pairs with HL < 60 days only

</td>
<td width="33%" valign="top">

**Risk Architecture**
- 3-tier kill-switch (T1 10% · T2 15% · T3 20%)
- 6 independent halt conditions
- Volatility-adaptive trailing stops (1σ)
- 60-day maximum holding period
- Concentration limits: 20% / pair, 40% / sector

</td>
<td width="33%" valign="top">

**Adaptive Intelligence**
- Kalman filter — dynamic hedge ratio
- HMM Markov-switching regime detection
- Regime-aware entry/exit thresholds
- Adaptive z-score window sized by AR(1) half-life
- Momentum overlay (30% weight)

</td>
</tr>
</table>
=======
**Modular Statistical Arbitrage System — Blockprod Inc.**

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
| `monitoring/` | Structured logging, Slack/email alerts, dashboard | — |

### Internal (Implementation) Packages

These packages contain the proven implementations that the modules above compose:

| Package | Contains |
|---------|----------|
| `strategies/` | `PairTradingStrategy` — core bar-by-bar signal logic |
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

- [**ARCHITECTURE.md**](./ARCHITECTURE.md) — Full 7-stage signal pipeline design
- [CONFIG_GUIDE.md](./CONFIG_GUIDE.md) — Parameter tuning guide
- [OPERATIONS_RUNBOOK.md](./OPERATIONS_RUNBOOK.md) — Troubleshooting & ops
- [BACKTEST_USAGE.md](./BACKTEST_USAGE.md) — Backtesting guide
>>>>>>> origin/main

---

## Quick Start

<<<<<<< HEAD
**Requirements**: Python 3.11.9 · Interactive Brokers TWS/Gateway · Docker (optional)

### Install

```bash
git clone <repo>
cd EDGECORE_V1
python -m venv venv && venv\Scripts\activate   # Windows
pip install -r requirements.txt
cp .env.example .env                            # fill in IBKR credentials
```

### Configure

```
config/dev.yaml    ← development defaults
config/prod.yaml   ← production settings (EDGECORE_ENV=prod)
config/test.yaml   ← test overrides
```

### Run a Backtest
=======
### 1. Install

```bash
# Python 3.11.9 required
pip install -e ".[dev]"
cp .env.example .env       # fill in IBKR credentials
```

### 2. Configure

Edit `config/config.yaml` (unified config) or per-environment files:
- `config/dev.yaml` — development defaults
- `config/prod.yaml` — production settings
- `config/test.yaml` — test overrides

### 3. Backtest
>>>>>>> origin/main

```python
from backtester import BacktestEngine, BacktestConfig

<<<<<<< HEAD
result = BacktestEngine().run(BacktestConfig(
=======
engine = BacktestEngine()
result = engine.run(BacktestConfig(
>>>>>>> origin/main
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

<<<<<<< HEAD
### Paper Trading
=======
### 4. Paper Trading
>>>>>>> origin/main

```python
from live_trading import PaperTradingRunner, TradingLoopConfig

<<<<<<< HEAD
PaperTradingRunner(TradingLoopConfig(
    symbols=["AAPL", "MSFT", "GOOGL", "META"],
    bar_interval_seconds=60,
    initial_capital=100_000,
)).start()
```

### Walk-Forward Validation
=======
runner = PaperTradingRunner(TradingLoopConfig(
    symbols=["AAPL", "MSFT", "GOOGL", "META"],
    bar_interval_seconds=60,
    initial_capital=100_000,
))
runner.start()
```

### 5. Walk-Forward Validation
>>>>>>> origin/main

```python
from backtester import WalkForwardEngine, WalkForwardConfig

<<<<<<< HEAD
result = WalkForwardEngine().run(WalkForwardConfig(
=======
engine = WalkForwardEngine()
result = engine.run(WalkForwardConfig(
>>>>>>> origin/main
    symbols=["AAPL", "MSFT", "GOOGL", "META"],
    start_date="2020-01-01",
    end_date="2023-12-31",
    num_periods=6,
))
<<<<<<< HEAD
print(f"OOS validated: {result.passed}")
=======
print(f"Validated: {result.passed}")
>>>>>>> origin/main
```

---

## Deployment
<<<<<<< HEAD

```bash
# Docker — single container
docker build -t edgecore:latest .
docker run -e EDGECORE_ENV=prod edgecore:latest python main.py

# Docker Compose — full stack (IBKR Gateway + Prometheus + Grafana)
=======

### Docker

```bash
docker build -t edgecore:latest .
docker run -e EDGECORE_ENV=prod edgecore:latest python main.py
```

### Docker Compose

```bash
>>>>>>> origin/main
docker-compose up -d
docker-compose logs -f
```

<<<<<<< HEAD
### Validation commands

```powershell
# Full test suite (Python 3.11)
venv\Scripts\python.exe -m pytest tests/ -q

# Risk tier coherence check
venv\Scripts\python.exe -c "from config.settings import get_settings; get_settings()._assert_risk_tier_coherence(); print('OK')"
```

---

## Test Suite

| Scope | Files | Status |
|:---|:---:|:---:|
| Unit — models, signals, risk | 60+ | ✅ |
| Integration — pipeline E2E | 12+ | ✅ |
| Execution — IBKR mock, reconciliation | 15+ | ✅ |
| Regression — equity curve, PnL | 2 | ✅ |
| **Total** | **2 808 tests** | **100% passing** |

---

## Documentation

| Document | Description |
|:---|:---|
| [ARCHITECTURE.md](./ARCHITECTURE.md) | 7-stage signal pipeline design |
| [CONFIG_GUIDE.md](./CONFIG_GUIDE.md) | Parameter tuning reference |
| [OPERATIONS_RUNBOOK.md](./OPERATIONS_RUNBOOK.md) | Production ops & troubleshooting |
| [BACKTEST_USAGE.md](./BACKTEST_USAGE.md) | Backtesting guide |

---

<div align="center">

`Python 3.11.9` &nbsp;·&nbsp; `Interactive Brokers` &nbsp;·&nbsp; `Cython` &nbsp;·&nbsp; `Prometheus` &nbsp;·&nbsp; `Grafana` &nbsp;·&nbsp; `Docker`

*© Blockprod Inc. — All rights reserved. Private & Confidential.*

</div>
=======
See [OPERATIONS_RUNBOOK.md](./OPERATIONS_RUNBOOK.md) for production deployment.

---

## Sprint History

| Sprint | Focus | Tests | Status |
|--------|-------|-------|--------|
| S1 | Audit remediation (Bonferroni, OOS, costs) | — | Done |
| S2 | Core features (hedge ratio, stops, regime) | 166 | Done |
| S3.1 | Comprehensive test suite | 101 | Done |
| S3.2 | Half-life refinement (AR(1) adaptive z-score) | 28 | Done |
| S3.3 | Architecture & operations docs | — | Done |
| S4 | Modular migration (this README) | — | Done |

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
**License**: Private — Blockprod Inc.
>>>>>>> origin/main
