# EDGECORE

**Private Trading System - Blockprod Inc.**

---

## ⚠️ CONFIDENTIAL

This is a private repository. Contents are confidential and proprietary to Blockprod Inc.

**Unauthorized access or distribution is strictly prohibited.**

---

## Setup

### Prerequisites

- **Python**: 3.11.9+
- **OS**: Windows / Linux / macOS

### Installation

```bash
git clone https://github.com/Blockprod/EDGECORE.git
cd EDGECORE

python -m venv venv
source venv/Scripts/activate  # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

### Configuration

Create `.env` file with required credentials:

```env
API_KEY=your_key
API_SECRET=your_secret
SLACK_WEBHOOK_URL=https://hooks.slack.com/...
JWT_SECRET=your_secret_key_minimum_32_bytes
```

Set environment:
```bash
export EDGECORE_ENV=dev  # or prod
```

---

## Running

```bash
# Development mode
python main.py --mode backtest

# Testing mode (simulated execution)
python main.py --mode paper

# Production mode (real execution)
python main.py --mode live
```

Check system health:
```bash
curl http://localhost:5000/health
```

---

## Testing

```bash
pytest tests/ -v
```

---

## Documentation

For detailed technical documentation, see the `/docs` directory.

---

**Status**: Production-Ready  
**License**: Private - Blockprod Inc.
