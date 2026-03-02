# EDGECORE

**Production-Grade Automated Trading System**

A robust, enterprise-ready trading platform with comprehensive risk management, advanced monitoring, and multi-mode execution (backtest, paper, live).

---

## Features

- **Trading Engine**: Advanced execution with dynamic market analysis
- **Multi-Mode Execution**: Backtest → Paper Trading → Live (with kill-switches)
- **Risk Management**: 
  - Position sizing and concentration controls
  - Dynamic loss monitoring and drawdown protection
  - Automated circuit breakers
- **Market Connectivity**: 
  - Multi-broker support via IBKR API (200+ brokers)
  - Multi-broker integration
- **Monitoring & Alerting**:
  - Real-time dashboard API
  - Slack/Email alerting
  - Structured audit logging
  - Prometheus metrics
- **Resilience**:
  - Circuit breaker pattern with automatic recovery
  - Exponential backoff for transient errors
  - Order lifecycle management
  - Graceful shutdown procedures

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
   # IBKR API broker API keys (optional for paper mode)
   broker_API_KEY=your_key
   broker_SECRET=your_secret
   
   # Alerting
   SLACK_WEBHOOK_URL=https://hooks.slack.com/...
   SMTP_PASSWORD=your_password
   ```

3. **Customize parameters** in `config/dev.yaml`:
   ```yaml
   execution:
     broker: IBKR       # or other IBKR API broker
     use_sandbox: true       # Force sandbox mode
   risk:
     max_daily_loss_pct: 2.0 # Kill-switch at 2% loss
     max_concurrent_positions: 10
   # Additional parameters in config file
   ```

### Running

```bash
# Paper Trading (sandbox, no real money)
python main.py --mode paper --symbols AAPL MSFT

# Backtest (historical analysis)
python main.py --mode backtest --symbols AAPL MSFT

# Live Trading (EXTREME CAUTION - requires explicit approval)
python main.py --mode live --symbols AAPL --enable-live-trading
```

---

## Usage

### Paper Trading (Recommended First Step)

Test the system with real market data without risking capital:

```bash
# Start paper trading with selected instruments
python main.py --mode paper --symbols AAPL MSFT

# This will:
# 1. Start the dashboard API (http://localhost:5000)
# 2. Load market data from your configured broker
# 3. Execute trading logic on simulated capital
# 4. Log all activity to audit trail
# 5. Display metrics updates
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

Validate performance on historical data:

```bash
# Run backtest analysis
python main.py --mode backtest --symbols AAPL MSFT

# Results include:
# - Historical performance analysis
# - Risk metrics (drawdown, volatility)
# - Trade distribution and statistics
# - Period-based performance breakdown
```

### Live Trading

**⚠️ PRODUCTION MODE - EXTREME CAUTION REQUIRED**

```bash
# Deploy live trading (only after Phase 2 & 3 complete)
python main.py --mode live --symbols AAPL MSFT --enable-live-trading

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
├── config/                    # Settings and configuration schemas
├── strategies/                # Trading strategy implementations
├── execution/                 # Order execution engines (IBKR API, brokers)
├── risk/                      # Risk management and constraints
├── backtests/                 # Backtest engine and analytics
├── data/                      # Market data loading and processing
├── models/                    # Analysis models
├── monitoring/                # Dashboard API, alerts, logging
├── persistence/               # Audit trails and data storage
├── research/                  # Analysis and parameter research
├── common/                    # Shared utilities (errors, validators, circuit breaker)
├── scripts/                   # Development tools (validation, health checks)
├── examples/                  # Usage examples
├── tests/                     # Test suite (1200+ tests)
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
- **Backtest**: Historical analysis with walk-forward validation
- **Paper**: Real-time data with simulated execution (no capital required)
- **Live**: Production execution with integrated kill-switches

### Risk Framework
- **Order-level**: Position sizing and risk controls
- **Portfolio-level**: Exposure management and concentration limits
- **Daily-level**: Loss limits and trading halts
- **System-level**: Circuit breakers and automatic recovery

### Resilience Patterns
- **Circuit Breaker**: Automatic failure isolation and recovery
- **Retry Logic**: Exponential backoff for transient failures
- **Order Tracking**: Complete lifecycle management
- **Audit Trail**: Immutable record of all decisions

---

## Testing

Comprehensive test suite covering:
- Unit tests for all components
- Integration tests across system layers
- End-to-end trading workflows
- Data integrity and serialization
- Error handling and recovery
- System stability under load

```bash
# Run all tests
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
  edgecore:latest python main.py --mode paper --symbols AAPL

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

**Status**: Production Ready  
**Tested**: Comprehensive test suite with 1200+ tests  
**Docs**: See `docs/` for technical documentation

---

## Next Steps

1. Configure broker API credentials in `.env`
2. Review `config/dev.yaml` and adjust parameters as needed
3. Run paper trading: `python main.py --mode paper`
4. Verify dashboard: `curl http://localhost:5000/api/dashboard`
5. Run backtest for validation: `python main.py --mode backtest`

---

**Production-ready trading system with enterprise-grade safety and monitoring.**
