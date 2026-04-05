<<<<<<< HEAD
﻿"""
=======
"""
>>>>>>> origin/main
Diagnostic script to identify backtest issues.
Tests each component independently.
"""

<<<<<<< HEAD
from typing import Any

import numpy as np
import pandas as pd
=======
import pandas as pd
import numpy as np
>>>>>>> origin/main
import sys
from structlog import get_logger

logger = get_logger(__name__)

<<<<<<< HEAD
print("\n" + "=" * 70)
print("EDGECORE BACKTEST DIAGNOSTIC")
print("=" * 70)
=======
print("\n" + "="*70)
print("EDGECORE BACKTEST DIAGNOSTIC")
print("="*70)
>>>>>>> origin/main

# Step 1: Test data loading
print("\n[STEP 1] Testing DataLoader...")
try:
    from data.loader import DataLoader
<<<<<<< HEAD

    loader = DataLoader()
    print("Ô£à DataLoader imported successfully")

    # Try to load AAPL data
    print("   Loading AAPL data via IBKR (2023-06-01 to 2024-06-01)...")
    df_aapl = loader.load_ibkr_data(symbol="AAPL", timeframe="1d", since="2023-06-01", limit=500, validate=False)

    if df_aapl is not None and len(df_aapl) > 0:
        print(f"Ô£à AAPL data loaded: {len(df_aapl)} rows")
        print(f"   Date range: {df_aapl.index[0]} to {df_aapl.index[-1]}")
        print(f"   Price range: ${df_aapl['close'].min():.2f} - ${df_aapl['close'].max():.2f}")
    else:
        print("ÔØî AAPL data is None or empty!")

except Exception as e:
    print(f"ÔØî DataLoader failed: {e}")
=======
    loader = DataLoader()
    print("✅ DataLoader imported successfully")
    
    # Try to load AAPL data
    print("   Loading AAPL data via IBKR (2023-06-01 to 2024-06-01)...")
    df_aapl = loader.load_ibkr_data(symbol='AAPL', timeframe='1d', since='2023-06-01', limit=500, validate=False)
    
    if df_aapl is not None and len(df_aapl) > 0:
        print(f"✅ AAPL data loaded: {len(df_aapl)} rows")
        print(f"   Date range: {df_aapl.index[0]} to {df_aapl.index[-1]}")
        print(f"   Price range: ${df_aapl['close'].min():.2f} - ${df_aapl['close'].max():.2f}")
    else:
        print("❌ AAPL data is None or empty!")
        
except Exception as e:
    print(f"❌ DataLoader failed: {e}")
>>>>>>> origin/main
    sys.exit(1)

# Step 2: Try loading multiple symbols
print("\n[STEP 2] Testing multiple symbol loading...")
<<<<<<< HEAD
symbols = ["AAPL", "MSFT", "JPM"]
=======
symbols = ['AAPL', 'MSFT', 'JPM']
>>>>>>> origin/main
price_data = {}

try:
    for sym in symbols:
        try:
<<<<<<< HEAD
            df = loader.load_ibkr_data(symbol=sym, timeframe="1d", since="2023-06-01", limit=500, validate=False)
            if df is not None and len(df) > 0:
                price_data[sym] = df["close"]
                print(f"Ô£à {sym}: {len(df)} rows")
            else:
                print(f"ÔÜá´©Å  {sym}: No data returned")
        except Exception as e:
            print(f"ÔØî {sym}: {e}")

    if len(price_data) == 0:
        print("ÔØî No symbols loaded successfully!")
        sys.exit(1)

except Exception as e:
    print(f"ÔØî Multi-symbol loading failed: {e}")
=======
            df = loader.load_ibkr_data(symbol=sym, timeframe='1d', since='2023-06-01', limit=500, validate=False)
            if df is not None and len(df) > 0:
                price_data[sym] = df['close']
                print(f"✅ {sym}: {len(df)} rows")
            else:
                print(f"⚠️  {sym}: No data returned")
        except Exception as e:
            print(f"❌ {sym}: {e}")
    
    if len(price_data) == 0:
        print("❌ No symbols loaded successfully!")
        sys.exit(1)
        
except Exception as e:
    print(f"❌ Multi-symbol loading failed: {e}")
>>>>>>> origin/main
    sys.exit(1)

# Step 3: Test cointegration detection
print("\n[STEP 3] Testing cointegration detection...")
<<<<<<< HEAD
engle_granger_test_cpp_optimized: Any = None  # pre-init; overwritten in Step 3 try block
try:
    from models.cointegration import engle_granger_test_cpp_optimized

    prices_df = pd.DataFrame(price_data)
    symbols_loaded = list(prices_df.columns)

    print(f"   Testing {len(symbols_loaded)} symbols...")
    cointegrated_pairs = []

    for i, sym1 in enumerate(symbols_loaded):
        for sym2 in symbols_loaded[i + 1 :]:
            series1 = pd.Series(prices_df[sym1])
            series2 = pd.Series(prices_df[sym2])

            result = engle_granger_test_cpp_optimized(series1, series2)
            pvalue = result["adf_pvalue"]
            is_cointegrated = result["is_cointegrated"]

            print(f"   {sym1} vs {sym2}: p-value={pvalue:.4f}, cointegrated={is_cointegrated}")

            if is_cointegrated:
                cointegrated_pairs.append((sym1, sym2, pvalue))

    print("Ô£à Cointegration test completed")
    print(f"   Found {len(cointegrated_pairs)} cointegrated pairs: {cointegrated_pairs}")

except Exception as e:
    print(f"ÔØî Cointegration test failed: {e}")
    import traceback

=======
try:
    from models.cointegration import engle_granger_test_cpp_optimized
    
    prices_df = pd.DataFrame(price_data)
    symbols_loaded = list(prices_df.columns)
    
    print(f"   Testing {len(symbols_loaded)} symbols...")
    cointegrated_pairs = []
    
    for i, sym1 in enumerate(symbols_loaded):
        for sym2 in symbols_loaded[i+1:]:
            series1 = prices_df[sym1]
            series2 = prices_df[sym2]
            
            result = engle_granger_test_cpp_optimized(series1, series2)
            pvalue = result['adf_pvalue']
            is_cointegrated = result['is_cointegrated']
            
            print(f"   {sym1} vs {sym2}: p-value={pvalue:.4f}, cointegrated={is_cointegrated}")
            
            if is_cointegrated:
                cointegrated_pairs.append((sym1, sym2, pvalue))
    
    print("✅ Cointegration test completed")
    print(f"   Found {len(cointegrated_pairs)} cointegrated pairs: {cointegrated_pairs}")
    
except Exception as e:
    print(f"❌ Cointegration test failed: {e}")
    import traceback
>>>>>>> origin/main
    traceback.print_exc()

# Step 4: Test synthetic cointegrated pair generation
print("\n[STEP 4] Testing synthetic data generation...")
try:
    np.random.seed(42)
<<<<<<< HEAD
    dates = pd.date_range("2023-01-01", "2024-01-01", freq="D")
    n = len(dates)

    # Generate base price series
    x_returns = np.random.normal(0.0005, 0.02, n)
    x_prices = 100 * np.exp(np.cumsum(x_returns))

    # Generate cointegrated series
    noise = np.random.normal(0, 5, n)
    y_prices = 2 * x_prices + noise

    synthetic_df = pd.DataFrame({"Symbol1": x_prices, "Symbol2": y_prices}, index=dates)

    print(f"Ô£à Synthetic data generated: {len(synthetic_df)} rows")
    print(f"   Symbol1 price range: ${synthetic_df['Symbol1'].min():.2f} - ${synthetic_df['Symbol1'].max():.2f}")
    print(f"   Symbol2 price range: ${synthetic_df['Symbol2'].min():.2f} - ${synthetic_df['Symbol2'].max():.2f}")

    # Test cointegration on synthetic pair
    result = engle_granger_test_cpp_optimized(pd.Series(synthetic_df["Symbol1"]), pd.Series(synthetic_df["Symbol2"]))
    print(f"   Cointegration test: p-value={result['adf_pvalue']:.4f}, is_cointegrated={result['is_cointegrated']}")

except Exception as e:
    print(f"ÔØî Synthetic data generation failed: {e}")
    import traceback

=======
    dates = pd.date_range('2023-01-01', '2024-01-01', freq='D')
    n = len(dates)
    
    # Generate base price series
    x_returns = np.random.normal(0.0005, 0.02, n)
    x_prices = 100 * np.exp(np.cumsum(x_returns))
    
    # Generate cointegrated series
    noise = np.random.normal(0, 5, n)
    y_prices = 2 * x_prices + noise
    
    synthetic_df = pd.DataFrame({
        'Symbol1': x_prices,
        'Symbol2': y_prices
    }, index=dates)
    
    print(f"✅ Synthetic data generated: {len(synthetic_df)} rows")
    print(f"   Symbol1 price range: ${synthetic_df['Symbol1'].min():.2f} - ${synthetic_df['Symbol1'].max():.2f}")
    print(f"   Symbol2 price range: ${synthetic_df['Symbol2'].min():.2f} - ${synthetic_df['Symbol2'].max():.2f}")
    
    # Test cointegration on synthetic pair
    result = engle_granger_test_cpp_optimized(synthetic_df['Symbol1'], synthetic_df['Symbol2'])
    print(f"   Cointegration test: p-value={result['adf_pvalue']:.4f}, is_cointegrated={result['is_cointegrated']}")
    
except Exception as e:
    print(f"❌ Synthetic data generation failed: {e}")
    import traceback
>>>>>>> origin/main
    traceback.print_exc()

# Step 5: Test spread and Z-score calculation
print("\n[STEP 5] Testing spread/Z-score calculation...")
try:
    from models.spread import SpreadModel
<<<<<<< HEAD

    sym1, sym2 = list(price_data.keys())[:2]
    y = price_data[sym1]
    x = price_data[sym2]

    model = SpreadModel(y, x)
    spread = model.compute_spread(y, x)
    z_scores = model.compute_z_score(spread, lookback=20)

    print("Ô£à Spread/Z-score calculated:")
    print(f"   Spread - min: {spread.min():.2f}, max: {spread.max():.2f}")
    print(f"   Z-scores - min: {z_scores.min():.2f}, max: {z_scores.max():.2f}")
    print(f"   Current Z-score: {z_scores.iloc[-1]:.2f}")

except Exception as e:
    print(f"ÔØî Spread/Z-score calculation failed: {e}")
    import traceback

=======
    
    sym1, sym2 = list(price_data.keys())[:2]
    y = price_data[sym1]
    x = price_data[sym2]
    
    model = SpreadModel(y, x)
    spread = model.compute_spread(y, x)
    z_scores = model.compute_z_score(spread, lookback=20)
    
    print("✅ Spread/Z-score calculated:")
    print(f"   Spread - min: {spread.min():.2f}, max: {spread.max():.2f}")
    print(f"   Z-scores - min: {z_scores.min():.2f}, max: {z_scores.max():.2f}")
    print(f"   Current Z-score: {z_scores.iloc[-1]:.2f}")
    
except Exception as e:
    print(f"❌ Spread/Z-score calculation failed: {e}")
    import traceback
>>>>>>> origin/main
    traceback.print_exc()

# Step 6: Run mini backtest with synthetic data
print("\n[STEP 6] Running mini backtest with synthetic cointegrated pair...")
try:
    from backtests.runner import BacktestRunner
<<<<<<< HEAD

    runner = BacktestRunner()

    # Use synthetic option if available
    metrics = runner.run(
        symbols=["AAPL", "MSFT"],
        start_date="2023-06-01",
        end_date="2024-01-01",
        use_synthetic=True,  # Force synthetic data
    )

    print("Ô£à Synthetic backtest completed:")
    print(metrics.summary())

except Exception as e:
    print(f"ÔØî Mini backtest failed: {e}")
    import traceback

    traceback.print_exc()

print("\n" + "=" * 70)
print("DIAGNOSTIC COMPLETE")
print("=" * 70 + "\n")
=======
    
    runner = BacktestRunner()
    
    # Use synthetic option if available
    metrics = runner.run(
        symbols=['AAPL', 'MSFT'],
        start_date='2023-06-01',
        end_date='2024-01-01',
        use_synthetic=True  # Force synthetic data
    )
    
    print("✅ Synthetic backtest completed:")
    print(metrics.summary())
    
except Exception as e:
    print(f"❌ Mini backtest failed: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*70)
print("DIAGNOSTIC COMPLETE")
print("="*70 + "\n")
>>>>>>> origin/main
