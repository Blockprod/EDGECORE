<<<<<<< HEAD
﻿# EDGECORE Backtest Usage Guide
=======
# EDGECORE Backtest Usage Guide
>>>>>>> origin/main

## Quick Start (NEW - Simplified!)

### Default: 46 Major Equity (Configured in code)
```bash
# Just run with NO symbol arguments - uses 46 equities from config/dev.yaml
python main.py --mode backtest
```
<<<<<<< HEAD
Ô£ôÔ£ôÔ£ô **BEST - Simple, practical, no long commands needed!**
=======
✓✓✓ **BEST - Simple, practical, no long commands needed!**
>>>>>>> origin/main

## Advanced Usage

### 1. Override with Custom Symbols
```bash
# Run with just AAPL/MSFT (small universe test)
python main.py --mode backtest --symbols AAPL MSFT
```
<<<<<<< HEAD
ÔØî Too small ÔåÆ Usually 0 trades found
=======
❌ Too small → Usually 0 trades found
>>>>>>> origin/main

### 2. Custom Date Range (uses default 46 symbols)
```bash
python main.py --mode backtest --start-date 2024-01-01 --end-date 2024-12-31
```

### 3. Paper Trading with Default Universe
```bash
python main.py --mode paper
```
Runs paper trading simulation with 46 symbols in real-time

## Configuration

### Editing the Trading Universe

Edit `config/dev.yaml` to modify which equities to trade:

```yaml
trading_universe:
  symbols:
    - "AAPL"
    - "MSFT"
    - "GOOGL"
    # ... add/remove symbols here
```

- Add more symbols for better cointegration discovery
- Remove symbols that don't exist on your broker
- Changes apply immediately next run (no code recompilation needed)

## How It Works

The backtest engine (with 46 default symbols):

1. **Loads data** for all 46 Equity from IBKR
2. **Tests ALL pairs** for cointegration (Engle-Granger test)
   - 46 symbols = 1,035 pair combinations
3. **Filters pairs** with p-value < 0.05 (significant cointegration)
4. **Executes trades** on mean reversion signals (Z-score thresholds)
5. **Force-closes** all open positions at end of period
6. **Reports metrics** (return, Sharpe ratio, win rate, etc.)

## Key Statistics

| Universe Size | Pair Combinations | Expected Trades | Time |
|---------------|------------------|-----------------|------|
| 2 | 1 | ~0 | <10s |
| 5 | 10 | ~0.5 | ~15s |
| 10 | 45 | ~2 | ~30s |
| **46 (default)** | **1,035** | **10-50** | **~3 min** |
| 100 | 4,950 | **250+** | **~10 min** |

## Strategy Rules

- **Entry**: Z-score |z| > 2.0 (default, configurable in `config/dev.yaml`)
- **Exit**: Z-score returns to ~0 (mean reversion complete)
- **Max concurrent positions**: 10 (configurable)
- **Position sizing**: ~1% per pair of capital

## Results Interpretation

### 0 trades found
<<<<<<< HEAD
- Ô£ô Good: Means market has no valid opportunities (strict risk management)
- Ô£ô Strategy correctly rejects false signals
- **Action**: Run with different date range or larger universe

### 1-10 trades found  
- Ô£ô Expected: Shows strategy found and executed trading signals
- Check win rate and metrics for quality

### 10+ trades found
- Ô£ô Excellent: Multiple cointegration opportunities found
=======
- ✓ Good: Means market has no valid opportunities (strict risk management)
- ✓ Strategy correctly rejects false signals
- **Action**: Run with different date range or larger universe

### 1-10 trades found  
- ✓ Expected: Shows strategy found and executed trading signals
- Check win rate and metrics for quality

### 10+ trades found
- ✓ Excellent: Multiple cointegration opportunities found
>>>>>>> origin/main
- Check metrics (Sharpe ratio, win rate) to ensure quality

## Examples

### Quick Test (2023 data, 46 equities)
```bash
python main.py --mode backtest
```

### Specific Year
```bash
python main.py --mode backtest --start-date 2024-01-01 --end-date 2024-12-31
```

### Small Universe for Fast Testing
```bash
python main.py --mode backtest --symbols AAPL MSFT BAC JPM V
```

### Paper Trading (Real-time, simulated)
```bash
python main.py --mode paper
```

## Important: Why 46+ Symbols Matter

**Statistical Arbitrage requires diversity:**

With 46 symbols testing 1,035 pair combinations:
- ~5% cointegration rate = ~50 valid trades per year
- Enough diversity to avoid overfitting
- High probability of finding real opportunities

With just 2 symbols (1 pair):
- Low chance of cointegration
- Strategy has no opportunities to trade

## Architecture

Changes made to support this:

1. **New Section** in `config/dev.yaml`:
   ```yaml
   trading_universe:
     symbols: [46 equities]
   ```

2. **New Class** in `config/settings.py`:
   ```python
   class TradingUniverseConfig:
       symbols: list  # Loaded from YAML
   ```

3. **Updated** `main.py`:
   - Removed hardcoded `["AAPL/SPY", "MSFT/SPY"]`
   - Now loads from config by default
   - CLI override still works with `--symbols`

## Next Steps

1. Run: `python main.py --mode backtest`
2. Monitor backtest results
3. Adjust date ranges to find years with good trading opportunities
4. Consider expanding to 100+ equities for even better coverage
5. Use paper trading to validate live performance

## Configuration Files

| File | Purpose |
|------|---------|
| `config/dev.yaml` | Development config (46 symbols) |
| `config/prod.yaml` | Production config (customize for live trading) |
| `config/settings.py` | Config schema and loading logic |

---

**The new approach is much more practical and scalable!**
