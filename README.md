<div align="center">

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

---

## Quick Start

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

```python
from backtester import BacktestEngine, BacktestConfig

result = BacktestEngine().run(BacktestConfig(
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

### Paper Trading

```python
from live_trading import PaperTradingRunner, TradingLoopConfig

PaperTradingRunner(TradingLoopConfig(
    symbols=["AAPL", "MSFT", "GOOGL", "META"],
    bar_interval_seconds=60,
    initial_capital=100_000,
)).start()
```

### Walk-Forward Validation

```python
from backtester import WalkForwardEngine, WalkForwardConfig

result = WalkForwardEngine().run(WalkForwardConfig(
    symbols=["AAPL", "MSFT", "GOOGL", "META"],
    start_date="2020-01-01",
    end_date="2023-12-31",
    num_periods=6,
))
print(f"OOS validated: {result.passed}")
```

---

## Deployment

```bash
# Docker — single container
docker build -t edgecore:latest .
docker run -e EDGECORE_ENV=prod edgecore:latest python main.py

# Docker Compose — full stack (IBKR Gateway + Prometheus + Grafana)
docker-compose up -d
docker-compose logs -f
```

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
