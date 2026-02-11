# EDGECORE

**Production-Grade Statistical Arbitrage Trading System**

A robust, enterprise-ready pair trading platform with advanced risk management, comprehensive monitoring, and multi-mode execution (backtest, paper, live).

---

## Features

- **Pair Trading Strategy**: Cointegration-based statistical arbitrage
- **Multi-Mode Execution**: Backtest → Paper Trading → Live (with kill-switches)
- **Risk Management**: 
  - Per-trade limits, position concentration caps
  - Daily drawdown controls, consecutive loss tracking
  - Volatility regime detection
- **Market Connectivity**: 
  - CCXT integration (200+ exchanges)
  - Interactive Brokers support
- **Monitoring & Alerting**:
  - Real-time dashboard API
  - Slack/Email alerting
  - Structured logging with audit trails
  - Prometheus metrics
- **Resilience**:
  - Circuit breaker pattern
  - Exponential backoff retries
  - Order lifecycle tracking
  - Graceful shutdown handling

---

## Quick Start

### Prerequisites

- **Python**: 3.11.9
- **OS**: Windows / Linux / macOS
- **Dependencies**: See `requirements.txt`

### Installation

```bash
# Clone and navigate
git clone <repo>
cd EDGECORE

# Create virtual environment
python -m venv venv
source venv/Scripts/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Configuration

1. **Set environment** (default: `dev`):
   ```bash
   export EDGECORE_ENV=dev  # Load config/dev.yaml
   ```

2. **Create `.env` file**:
   ```env
   # CCXT Exchange API keys (optional for paper mode)
   EXCHANGE_API_KEY=your_key
   EXCHANGE_SECRET=your_secret
   
   # Alerting
   SLACK_WEBHOOK_URL=https://hooks.slack.com/...
   SMTP_PASSWORD=your_password
   ```

3. **Customize parameters** in `config/dev.yaml`:
   ```yaml
   strategy:
     entry_z_score: 2.0      # Entry threshold
     exit_z_score: 0.0       # Exit threshold  
   risk:
     max_daily_loss_pct: 2.0 # Kill-switch at 2% loss
     max_concurrent_positions: 10
   execution:
     exchange: binance       # or other CCXT exchange
     use_sandbox: true       # Force sandbox mode
   ```

### Running

```bash
# Paper Trading (sandbox, no real money)
python main.py --mode paper --symbols BTC/USDT ETH/USDT

# Backtest (historical analysis)
python main.py --mode backtest --symbols BTC/USDT ETH/USDT

# Live Trading (EXTREME CAUTION - requires explicit approval)
python main.py --mode live --symbols BTC/USDT --enable-live-trading
```

---

## Usage

### Paper Trading (Recommended First Step)

Paper trading allows you to test the system with real market data but without risking capital:

```bash
# Start paper trading with BTC/USDT and ETH/USDT
python main.py --mode paper --symbols BTC/USDT ETH/USDT

# This will:
# 1. Start the dashboard API (http://localhost:5000)
# 2. Load real-time price data from your configured exchange
# 3. Execute the pair trading strategy on simulated capital
# 4. Log all trades to audit trail
# 5. Display metrics updates every iteration
```

Monitor via dashboard:
```bash
# Check system health
curl http://localhost:5000/health

# Get dashboard metrics
curl http://localhost:5000/api/dashboard

# View positions
curl http://localhost:5000/api/dashboard/positions
```

### Backtesting

Validate strategy on historical data:

```bash
# Run backtest on BTC/USDT and ETH/USDT for full history
python main.py --mode backtest --symbols BTC/USDT ETH/USDT

# Results include:
# - Walk-forward performance analysis
# - Drawdown, Sharpe ratio, win rate
# - Detailed trade metrics
# - Performance metrics by period
```

### Live Trading

**⚠️ PRODUCTION MODE - EXTREME CAUTION REQUIRED**

```bash
# Deploy live trading (only after Phase 2 & 3 complete)
python main.py --mode live --symbols BTC/USDT ETH/USDT --enable-live-trading

# System will:
# 1. Verify reconciliation with broker
# 2. Activate hard-stop kill-switches
# 3. Begin live capital deployment
# 4. Monitor positions continuously
```

---

## Project Structure

```
EDGECORE/
├── main.py                    # Entry point
├── config/                    # Settings & schemas
├── strategies/                # Trading strategies (pair_trading.py)
├── execution/                 # Order execution engines (CCXT, Interactive Brokers)
├── risk/                      # Risk management & constraints
├── backtests/                 # Backtest engine & metrics
├── data/                      # Market data loading & preprocessing
├── models/                    # ML models for spread prediction
├── monitoring/                # Dashboard API, alerts, logging
├── persistence/               # Audit trails & data persistence
├── research/                  # Pair discovery, parameter optimization
├── common/                    # Shared utilities (errors, validators, circuit breaker)
├── scripts/                   # Dev tools (validation, health checks)
├── examples/                  # Usage examples
├── tests/                     # 1200+ unit & integration tests
└── docs/                      # Technical documentation
```

---

## Development

### Running Tests

```bash
# All tests
pytest tests/ -v

# Specific test class
pytest tests/test_e2e_comprehensive.py::TestDashboardAccuracy -v

# With coverage
pytest tests/ --cov=. --cov-report=html
```

### Validation

```bash
# Type checking
python scripts/validate_types.py

# System health check
python scripts/check_health.py

# Run examples
python examples/examples_backtest.py
python examples/examples_pair_discovery.py
```

### Key Scripts

| Script | Purpose |
|--------|---------|
| `scripts/check_health.py` | System environment validation |
| `scripts/validate_types.py` | MyPy type checking |
| `scripts/verify_fix.py` | Test import verification |
| `scripts/quick_test.py` | Critical tests runner |

---

## Dashboard API

Real-time monitoring via REST API:

```bash
# Health check (no auth)
curl http://localhost:5000/health

# Dashboard snapshot (requires API key)
curl -H "X-API-Key: your-key" http://localhost:5000/api/dashboard
curl http://localhost:5000/api/dashboard/system     # System metrics
curl http://localhost:5000/api/dashboard/risk       # Risk metrics
curl http://localhost:5000/api/dashboard/positions  # Open positions
```

---

## Architecture Highlights

### Multi-Mode Execution
- **Backtest**: Walk-forward analysis with configurable rebalancing
- **Paper**: Real-time data, simulated execution (no capital required)
- **Live**: Production execution with kill-switches

### Risk Framework
- Trade-level: Position sizing, entry/exit rules
- Portfolio-level: Correlation caps, concentration limits
- Daily-level: Loss limits, consecutive loss tracking
- Regime-level: Volatility detection, circuit breakers

### Resilience Patterns
- **Circuit Breaker**: Automatic failures isolation
- **Retry Logic**: Exponential backoff for transient errors
- **Order Tracking**: Full lifecycle management
- **Audit Trail**: Immutable trade history

---

## Testing

**1203 tests covering:**
- Unit tests for all components
- Integration tests across layers
- End-to-end trading workflows
- Data integrity & JSON serialization
- Error handling chains
- System stability under load

```bash
# Latest test run: 1203 passed in 207.22s
pytest tests/ -v --tb=short
```

---

## Security

- No hardcoded secrets (uses `.env`)
- API key authentication for dashboard
- Rate limiting on all endpoints
- Structured audit logging
- Safe sandbox defaults

---

## Safety

**EDGECORE includes comprehensive safety mechanisms to protect against catastrophic losses:**

### Hard-Stop Kill Switches
- **2% Daily Loss Limit**: Automatic trading halt if daily loss exceeds 2%
- **15% Maximum Drawdown**: Systematic position closure if equity drawdown exceeds 15%
- **10 Consecutive API Errors**: Automatic trading suspension on repeated API failures

### Trading Safeguards
- All positions tracked with stop-loss orders
- Maximum concurrent positions limited (default: 10)
- Per-trade size limits enforced
- Unusual spread volatility triggers circuit breaker

### Operational Safeguards
- Startup reconciliation (equity verification before trading)
- Periodic reconciliation (hourly validation)
- Graceful shutdown procedures (closes all positions safely)
- Complete audit trail of all trades and decisions

### Production Requirements
**NEVER deploy live trading without:**
1. ✅ 2+ weeks of successful paper trading
2. ✅ All tests passing (80%+ coverage)
3. ✅ Risk limits reviewed by team
4. ✅ Kill-switches tested and verified
5. ✅ Initial capital ≤ $5,000
6. ✅ 24-hour continuous monitoring capability
7. ✅ Disaster recovery procedures in place

---

## Configuration Files

| File | Purpose |
|------|---------|
| `config/dev.yaml` | Development settings |
| `config/prod.yaml` | Production settings |
| `config/schemas.py` | Configuration validation |
| `.env` | Secrets & API keys |

---

## � Deployment

### Docker Deployment

EDGECORE includes production-ready Docker support:

```bash
# Build Docker image
docker build -t edgecore:latest .

# Run container
docker run -e EDGECORE_ENV=prod \
  -v ~/.ssh/id_rsa:/app/.ssh/id_rsa:ro \
  --env-file .env \
  edgecore:latest python main.py --mode paper --symbols BTC/USDT

# Docker Compose (with monitoring/logging)
docker-compose up -d
```

### Docker Compose Services

The included `docker-compose.yml` includes:
- **edgecore**: Main trading system
- **prometheus**: Metrics collection  
- **grafana**: Dashboard visualization
- **loki**: Log aggregation

All services run on isolated `trading-network`.

### Production Checklist

- [ ] Secrets configured in `.env` (API keys, passwords)
- [ ] Database backups enabled
- [ ] Log rotation configured
- [ ] Monitoring alerts set up
- [ ] Kill-switches tested
- [ ] Paper trading validated for 24h+
- [ ] Risk limits reviewed

---

## Troubleshooting

### Import errors
```bash
python scripts/verify_fix.py
```

### Type errors
```bash
python scripts/validate_types.py
```

### Environment issues
```bash
python scripts/check_health.py
```

### Test failures
```bash
pytest tests/ -xvs --tb=long
```

---

## License & Contact

**Status**: Production Ready (Phase 5 Complete)  
**Tested**: 1203 tests passing, E2E workflows validated  
**Docs**: See `docs/2026-02-08/` for technical details

---

## Next Steps

1. Configure exchange API credentials in `.env`
2. Review `config/dev.yaml` for strategy parameters
3. Run paper trading: `python main.py --mode paper`
4. Check dashboard: `curl http://localhost:5000/api/dashboard`
5. Run backtest for validation: `python main.py --mode backtest`

---

**Built with precision. Tested with rigor. Ready for production.**
