# Environment-Specific Configuration & Hot-Reload Guide

## Overview

EDGECORE supports three environment-specific configurations optimized for different workflows:

| Environment | Symbols | Capital | Purpose | Backtest Time |
|---|---|---|---|---|
| **DEV** | 46 | $100K | Active development & experimentation | ~30-60 sec |
| **TEST** | 10 | $50K | Unit tests & CI/CD integration | ~5-10 sec |
| **PROD** | 119 | $1M | Production with maximum coverage | ~3-5 min |

## Environment Detection

The system automatically detects which environment to use via these environment variables (in order of priority):

```bash
# Option 1 (Primary)
export EDGECORE_ENV=prod

# Option 2 (Fallback)
export ENVIRONMENT=prod

# Option 3 (Fallback)
export ENV=prod

# If none set, defaults to 'dev'
```

## Using Different Environments

### Development (46 symbols, fast iteration)
```bash
# Explicit
export EDGECORE_ENV=dev
python main.py --mode backtest

# Or just run (dev is default)
python main.py --mode backtest
```

### Testing (10 symbols, unit tests only)
```bash
export EDGECORE_ENV=test
python main.py --mode backtest --symbols BTC/USDT ETH/USDT BNB/USDT

# Or for CI/CD
EDGECORE_ENV=test pytest tests/
```

### Production (119 symbols, maximum cointegration discovery)
```bash
export EDGECORE_ENV=prod
python main.py --mode backtest
```

## Hot-Reload API

Switch configurations **without restarting** the application:

```python
from config.settings import get_settings

settings = get_settings()

# 1. Reload symbols from current environment's YAML
settings.reload_symbols()
# Result: Current env symbols reloaded from file

# 2. Override symbols dynamically
settings.reload_symbols(["BTC/USDT", "ETH/USDT", "SOL/USDT"])
# Result: Uses only these 3 symbols, no restart needed

# 3. Switch environment
settings.switch_environment('prod')
# Result: Loads all 119 symbols from prod.yaml

# 4. Get current symbols
current_symbols = settings.get_symbols_for_env()
print(f"Trading {len(current_symbols)} symbols in {settings.env} environment")
```

## Configuration Hierarchy

```
config/
├── dev.yaml      # 46 symbols: default for development
├── test.yaml     # 10 symbols: for unit tests
├── prod.yaml     # 119 symbols: production setting
└── settings.py   # Python config loader (auto-loads based on env)
```

## Use Cases

### 1. Quick Development Iteration
```bash
# Fast backtest with 46 symbols (~30 sec)
export EDGECORE_ENV=dev
python main.py --mode backtest --start_date 2024-01-01 --end_date 2024-02-01
```

### 2. Unit Testing (CI/CD Pipeline)
```bash
# Very fast tests with 10 symbols
export EDGECORE_ENV=test
pytest tests/test_backtest.py  # Runs in seconds
```

### 3. Production Research
```bash
# Thorough cointegration discovery with 119 symbols
export EDGECORE_ENV=prod
python main.py --mode backtest --start_date 2022-01-01 --end_date 2024-01-01
```

### 4. Dynamic Universe Testing
```python
# Test different universes without restarts
from config.settings import get_settings

settings = get_settings()

# Test top 5 cryptos
settings.reload_symbols(["BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "ADA/USDT"])
runner.run(settings.trading_universe.symbols, ...)

# Test DeFi only
settings.reload_symbols(["UNI/USDT", "AAVE/USDT", "COMP/USDT", "CRV/USDT", "MKR/USDT"])
runner.run(settings.trading_universe.symbols, ...)

# Revert to production
settings.switch_environment('prod')
runner.run(settings.trading_universe.symbols, ...)
```

## Symbol Optimization Strategy

### DEV (46 symbols)
```yaml
Tier 1:  BTC, ETH                           (2)
Tier 2:  Large cap (>$50B)                  (26)
Tier 3:  Mid cap ($5B-$50B)                 (18)
```

### TEST (10 symbols)
```yaml
- BTC/USDT, ETH/USDT                        (2 mega cap)
- BNB/USDT, SOL/USDT, ADA/USDT              (3 large cap)
- LINK/USDT, XRP/USDT, DOGE/USDT            (3 large cap)
- MATIC/USDT, LTC/USDT                      (2 mid cap)
```

### PROD (119 symbols)
```yaml
Tier 1:  Mega cap (BTC, ETH)                (2)
Tier 2:  Large cap (>$50B)                  (26)
Tier 3:  Mid cap ($5B-$50B)                 (35)
Tier 4:  Emerging/Alt coins                 (10)
Tier 5:  DeFi protocols                     (18)
Tier 6:  Layer 1 alternatives               (13)
Tier 7:  Oracle & Infrastructure            (8)
Tier 8:  Exchange tokens                    (7)
```

## Performance Characteristics

Mean execution time for `python main.py --mode backtest --start_date 2023-01-01 --end_date 2024-01-01`:

```
DEV  (46 symbols):   ~45 seconds  (1,035 pair tests)
TEST (10 symbols):   ~8 seconds   (45 pair tests)
PROD (119 symbols):  ~240 seconds (7,021 pair tests)
```

## Docker & Environment Variables

In Docker/production, pass environment through:

```dockerfile
FROM python:3.11
...
ENV EDGECORE_ENV=prod
ENV ENABLE_LIVE_TRADING=false
CMD ["python", "main.py", "--mode", "backtest"]
```

Or via docker-compose:
```yaml
services:
  backtest:
    environment:
      - EDGECORE_ENV=prod
      - ENABLE_LIVE_TRADING=false
```

## Testing Hot-Reload

```bash
# Test environment detection
python scripts/test_config_environments.py

# Test dynamic reloading
python scripts/test_hot_reload.py
```

## Troubleshooting

### Wrong environment loaded?
```bash
# Check which environment is active
python -c "from config.settings import get_settings; s = get_settings(); print(f'Environment: {s.env}, Symbols: {len(s.trading_universe.symbols)}')"
```

### Symbols not updating?
```bash
# Reload symbols explicitly
python -c "from config.settings import get_settings; s = get_settings(); s.reload_symbols(); print(s.trading_universe.symbols)"
```

### Can't switch environments?
```bash
# Make sure YAML file exists
ls -la config/{dev,test,prod}.yaml
```

## Best Practices

1. **Use TEST for CI/CD** - Keeps pipelines fast
2. **Use DEV for development** - Good balance of speed and discovery
3. **Use PROD for research** - Maximum cointegration opportunities
4. **Override selectively** - Use `reload_symbols()` for quick experiments
5. **Document universe choices** - Log which symbols you're using
6. **Monitor symbol counts** - Ensure you're in the right environment

---

**Related Documentation:**
- [BACKTEST_USAGE.md](../BACKTEST_USAGE.md) - Backtest execution guide
- [API_SECURITY.md](../monitoring/API_SECURITY.md) - API key management
- [DEPLOYMENT_GUIDE.md](../monitoring/DEPLOYMENT_GUIDE.md) - Production deployment
