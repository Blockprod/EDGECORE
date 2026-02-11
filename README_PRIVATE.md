# EDGECORE

**Production-Grade Automated Trading System**

A robust, enterprise-ready trading platform with comprehensive risk management, advanced monitoring, and automated execution capabilities.

---

## Overview

EDGECORE is a private trading system designed for professional deployment. This repository contains the production codebase and is not intended for public distribution or analysis.

**For detailed documentation, see the `/docs` directory.**

---

## Key Features

- **Automated Execution Engine**: Real-time order management and execution
- **Multi-Mode Operation**: Development, testing, and production modes
- **Risk Management**: 
  - Comprehensive position controls
  - Real-time loss monitoring
  - Automated safety mechanisms
- **Exchange Integration**: 
  - Multi-exchange support
  - Multi-broker compatibility
  - Robust API abstractions
- **Monitoring & Operations**:
  - Real-time dashboard and metrics
  - Alert system (Slack, Email)
  - Structured audit logging
- **System Resilience**:
  - Automatic error recovery
  - Failure isolation mechanisms
  - Graceful degradation

---

## Setup

### Prerequisites

- **Python**: 3.11.9+
- **OS**: Windows / Linux / macOS

### Installation

```bash
# Clone repository
git clone https://github.com/Blockprod/EDGECORE.git
cd EDGECORE

# Create and activate virtual environment
python -m venv venv
source venv/Scripts/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Configuration

1. **Set environment**:
   ```bash
   export EDGECORE_ENV=dev  # or prod
   ```

2. **Create `.env` file** with required secrets:
   ```env
   # Exchange/Broker credentials
   API_KEY=your_key
   API_SECRET=your_secret
   
   # Notifications (optional)
   SLACK_WEBHOOK_URL=https://hooks.slack.com/...
   SMTP_PASSWORD=your_password
   
   # Security
   JWT_SECRET=minimum_32_bytes_long_secret_key
   ```

3. **Review configuration** in `config/dev.yaml` or `config/prod.yaml`

---

## Running the System

```bash
# Development mode
python main.py --mode backtest

# Testing mode (simulated execution)
python main.py --mode paper

# Production mode (real execution)
python main.py --mode live
```

Monitor system status via dashboard API:
```bash
curl http://localhost:5000/health
```

---

## Project Structure

```
EDGECORE/
├── main.py                 # Entry point
├── config/                 # Configuration management
├── execution/              # Execution engines
├── risk/                   # Risk controls
├── backtests/              # Analysis tools
├── data/                   # Data management
├── monitoring/             # Dashboard and metrics
├── persistence/            # Data storage
├── common/                 # Shared utilities
├── scripts/                # Operational tools
├── tests/                  # Test suite
└── docs/                   # Technical documentation
```

---

## Testing

Run the comprehensive test suite:

```bash
pytest tests/ -v
```

---

## Security

- All secrets managed via environment variables (`.env` file)
- API authentication and rate limiting
- Structured logging and audit trails
- Safe defaults for all operations

---

## Safety Mechanisms

Critical safeguards are built into the system:

- Automated trading halts on error conditions
- Position and risk limits enforced
- System reconciliation checks
- Complete audit trail of all actions
- Graceful shutdown procedures

**For production deployment, review all safety configurations before going live.**

---

## Documentation

Technical documentation and operational guides are located in `/docs`.

For questions or issues, contact the development team.

---

**Status**: Production-Ready  
**Version**: Phase 4 (2026-02-11)  
**License**: Private - Blockprod Inc.
