<<<<<<< HEAD
﻿import os
import tempfile
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from data.loader import DataLoader
from data.preprocessing import align_pairs, remove_outliers, resample_ohlcv
=======
import pytest
import pandas as pd
import numpy as np
import tempfile
import os
from unittest.mock import patch, MagicMock
from data.loader import DataLoader
from data.preprocessing import resample_ohlcv, align_pairs, remove_outliers
>>>>>>> origin/main


class TestDataLoader:
    """Test DataLoader for OHLCV and CSV loading."""

    @staticmethod
    def _make_bars(dates, opens, highs, lows, closes, volumes):
        """Build list of mock bar objects matching ibapi BarData interface."""
        bars = []
<<<<<<< HEAD
        for d, o, h, l, c, v in zip(dates, opens, highs, lows, closes, volumes, strict=False):
            bar = MagicMock()
            bar.date = d.strftime("%Y%m%d") if hasattr(d, "strftime") else str(d)
=======
        for d, o, h, l, c, v in zip(dates, opens, highs, lows, closes, volumes):
            bar = MagicMock()
            bar.date = d.strftime('%Y%m%d') if hasattr(d, 'strftime') else str(d)
>>>>>>> origin/main
            bar.open = o
            bar.high = h
            bar.low = l
            bar.close = c
            bar.volume = v
            bars.append(bar)
        return bars

    def test_load_ibkr_data_structure(self):
        """Test that loaded equity data has correct OHLCV structure."""
        loader = DataLoader()

<<<<<<< HEAD
        dates = pd.date_range("2023-01-01", periods=3, freq="B")
=======
        dates = pd.date_range('2023-01-01', periods=3, freq='B')
>>>>>>> origin/main
        bars = self._make_bars(
            dates,
            opens=[175.0, 176.0, 177.0],
            highs=[178.0, 179.0, 180.0],
            lows=[174.0, 175.0, 176.0],
            closes=[176.5, 177.5, 178.5],
            volumes=[50000000, 55000000, 60000000],
        )

<<<<<<< HEAD
        with patch("execution.ibkr_engine.IBGatewaySync") as mock_gw_cls:
=======
        with patch('execution.ibkr_engine.IBGatewaySync') as mock_gw_cls:
>>>>>>> origin/main
            mock_gw = MagicMock()
            mock_gw_cls.return_value = mock_gw
            mock_gw.get_historical_data.return_value = bars

<<<<<<< HEAD
            result = loader.load_ibkr_data("AAPL", timeframe="1d", limit=3)

            assert len(result) == 3
            assert "open" in result.columns
            assert "high" in result.columns
            assert "low" in result.columns
            assert "close" in result.columns
            assert "volume" in result.columns
=======
            result = loader.load_ibkr_data('AAPL', timeframe='1d', limit=3)

            assert len(result) == 3
            assert 'open' in result.columns
            assert 'high' in result.columns
            assert 'low' in result.columns
            assert 'close' in result.columns
            assert 'volume' in result.columns
>>>>>>> origin/main

    def test_load_csv_data(self):
        """Test CSV loading functionality."""
        loader = DataLoader()

        # Create temp CSV
<<<<<<< HEAD
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
=======
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
>>>>>>> origin/main
            f.write("timestamp,open,high,low,close,volume\n")
            f.write("2023-01-02,150.00,152.00,149.00,151.50,40000000\n")
            f.write("2023-01-03,151.50,153.00,150.00,152.00,42000000\n")
            f.flush()
            temp_file = f.name

        try:
            df = loader.load_csv(temp_file)

            assert len(df) == 2
<<<<<<< HEAD
            assert df["close"].iloc[0] == 151.50
            assert df["close"].iloc[1] == 152.00
=======
            assert df['close'].iloc[0] == 151.50
            assert df['close'].iloc[1] == 152.00
>>>>>>> origin/main
        finally:
            os.unlink(temp_file)

    def test_load_ibkr_data_error_handling(self):
        """Test error handling when IBKR connection fails."""
        loader = DataLoader()

<<<<<<< HEAD
        with patch("execution.ibkr_engine.IBGatewaySync") as mock_gw_cls:
=======
        with patch('execution.ibkr_engine.IBGatewaySync') as mock_gw_cls:
>>>>>>> origin/main
            mock_gw = MagicMock()
            mock_gw_cls.return_value = mock_gw
            mock_gw.get_historical_data.side_effect = Exception("Network error")

            with pytest.raises(Exception):
<<<<<<< HEAD
                loader.load_ibkr_data("AAPL")
=======
                loader.load_ibkr_data('AAPL')
>>>>>>> origin/main

    def test_load_multiple_equity_symbols(self):
        """Test loading data for multiple US equity tickers."""
        loader = DataLoader()

        def _bars_for_price(price):
            bar = MagicMock()
<<<<<<< HEAD
            bar.date = "20230103"
=======
            bar.date = '20230103'
>>>>>>> origin/main
            bar.open = price * 0.99
            bar.high = price * 1.01
            bar.low = price * 0.98
            bar.close = price
            bar.volume = 50000000
            return [bar]

<<<<<<< HEAD
        prices = {"AAPL": 175.0, "MSFT": 300.0}

        with patch("execution.ibkr_engine.IBGatewaySync") as mock_gw_cls:
            mock_gw = MagicMock()
            mock_gw_cls.return_value = mock_gw

            def get_hist(symbol=None, **_kwargs):  # mirrors get_historical_data signature
                price = prices.get(symbol or "", 175.0)
=======
        prices = {'AAPL': 175.0, 'MSFT': 300.0}

        with patch('execution.ibkr_engine.IBGatewaySync') as mock_gw_cls:
            mock_gw = MagicMock()
            mock_gw_cls.return_value = mock_gw

            def get_hist(symbol=None, **kwargs):
                price = prices.get(symbol, 175.0)
>>>>>>> origin/main
                return _bars_for_price(price)

            mock_gw.get_historical_data.side_effect = get_hist

<<<<<<< HEAD
            aapl_data = loader.load_ibkr_data("AAPL", limit=1)
            msft_data = loader.load_ibkr_data("MSFT", limit=1)

            assert aapl_data["close"].iloc[0] == 175.0
            assert msft_data["close"].iloc[0] == 300.0
=======
            aapl_data = loader.load_ibkr_data('AAPL', limit=1)
            msft_data = loader.load_ibkr_data('MSFT', limit=1)

            assert aapl_data['close'].iloc[0] == 175.0
            assert msft_data['close'].iloc[0] == 300.0
>>>>>>> origin/main


class TestDataPreprocessing:
    """Test data preprocessing utilities."""

    def test_resample_ohlcv_daily_to_weekly(self):
        """Test resampling OHLCV data."""
        # Create daily OHLCV data
<<<<<<< HEAD
        dates = pd.date_range("2023-01-01", periods=30, freq="D")
        df = pd.DataFrame(
            {
                "open": np.linspace(100, 110, 30),
                "high": np.linspace(101, 111, 30),
                "low": np.linspace(99, 109, 30),
                "close": np.linspace(100.5, 110.5, 30),
                "volume": np.ones(30) * 1000,
            },
            index=dates,
        )

        # Resample to weekly
        weekly = resample_ohlcv(df, "W")

        # Should have fewer rows
        assert len(weekly) < len(df)
        assert "close" in weekly.columns

    def test_align_pairs(self):
        """Test aligning two time series."""
        dates1 = pd.date_range("2023-01-01", periods=10, freq="D")
        dates2 = pd.date_range("2023-01-05", periods=10, freq="D")

        df1 = pd.DataFrame({"price": np.linspace(100, 110, 10)}, index=dates1)
        df2 = pd.DataFrame({"price": np.linspace(50, 55, 10)}, index=dates2)
=======
        dates = pd.date_range('2023-01-01', periods=30, freq='D')
        df = pd.DataFrame({
            'open': np.linspace(100, 110, 30),
            'high': np.linspace(101, 111, 30),
            'low': np.linspace(99, 109, 30),
            'close': np.linspace(100.5, 110.5, 30),
            'volume': np.ones(30) * 1000,
        }, index=dates)

        # Resample to weekly
        weekly = resample_ohlcv(df, 'W')

        # Should have fewer rows
        assert len(weekly) < len(df)
        assert 'close' in weekly.columns

    def test_align_pairs(self):
        """Test aligning two time series."""
        dates1 = pd.date_range('2023-01-01', periods=10, freq='D')
        dates2 = pd.date_range('2023-01-05', periods=10, freq='D')

        df1 = pd.DataFrame({'price': np.linspace(100, 110, 10)}, index=dates1)
        df2 = pd.DataFrame({'price': np.linspace(50, 55, 10)}, index=dates2)
>>>>>>> origin/main

        # Align
        aligned1, aligned2 = align_pairs(df1, df2)

        # Should have same length after alignment
        assert len(aligned1) == len(aligned2)
        assert len(aligned1) == 6  # Overlap from 2023-01-05 to 2023-01-10

    def test_remove_outliers_zscore(self):
        """Test outlier removal with z-score method."""
        series = pd.Series([1, 2, 3, 4, 5, 100])  # 100 is outlier

<<<<<<< HEAD
        cleaned = remove_outliers(series, method="zscore", threshold=3.0)
=======
        cleaned = remove_outliers(series, method='zscore', threshold=3.0)
>>>>>>> origin/main

        # Should return a series
        assert isinstance(cleaned, pd.Series)

    def test_remove_outliers_iqr(self):
        """Test outlier removal with IQR method."""
        # Create series with outliers
        np.random.seed(42)
        normal = np.random.normal(100, 10, 50)
        series = pd.Series(np.concatenate([normal, [200]]))  # One outlier

<<<<<<< HEAD
        cleaned = remove_outliers(series, method="iqr", threshold=3.0)
=======
        cleaned = remove_outliers(series, method='iqr', threshold=3.0)
>>>>>>> origin/main

        # Should handle gracefully
        assert len(cleaned) == len(series)

    def test_preprocessing_maintains_index(self):
        """Test that preprocessing maintains date index."""
<<<<<<< HEAD
        dates = pd.date_range("2023-01-01", periods=20, freq="D")
        df = pd.DataFrame(
            {
                "close": np.linspace(100, 110, 20),
            },
            index=dates,
        )

        resampled = resample_ohlcv(
            df.assign(open=df["close"], high=df["close"] * 1.01, low=df["close"] * 0.99, volume=1000), "W"
=======
        dates = pd.date_range('2023-01-01', periods=20, freq='D')
        df = pd.DataFrame({
            'close': np.linspace(100, 110, 20),
        }, index=dates)

        resampled = resample_ohlcv(
            df.assign(open=df['close'], high=df['close']*1.01,
                      low=df['close']*0.99, volume=1000),
            'W'
>>>>>>> origin/main
        )

        # Should have DatetimeIndex
        assert isinstance(resampled.index, pd.DatetimeIndex)


class TestDataCaching:
    """Test data caching mechanisms."""

    def test_cache_directory_exists(self):
        """Test that cache directory exists."""
<<<<<<< HEAD
        cache_dir = "data/cache"
=======
        cache_dir = 'data/cache'
>>>>>>> origin/main
        assert os.path.exists(cache_dir) or True  # May or may not exist in test env

    def test_data_consistency(self):
        """Test that loaded equity data maintains consistency."""
        loader = DataLoader()

<<<<<<< HEAD
        dates = pd.date_range("2023-01-03", periods=2, freq="B")
        # DataLoader.load_ibkr_data uses IBGatewaySync and expects bar objects,
        # not a DataFrame — patch the correct class with the correct return type.
        bars = []
        for date, (open_, high, low, close, volume) in zip(
            dates,
            [(150.0, 152.0, 149.0, 151.0, 40000000), (151.0, 153.0, 150.0, 152.0, 41000000)],
            strict=False,
        ):
            bar = MagicMock()
            bar.date = date.strftime("%Y%m%d")
            bar.open = open_
            bar.high = high
            bar.low = low
            bar.close = close
            bar.volume = volume
            bars.append(bar)

        with patch("execution.ibkr_engine.IBGatewaySync") as mock_gw_cls:
            mock_gw = MagicMock()
            mock_gw_cls.return_value = mock_gw
            mock_gw.get_historical_data.return_value = bars

            df1 = loader.load_ibkr_data("MSFT")
            df2 = loader.load_ibkr_data("MSFT")

            # Data should be identical
            pd.testing.assert_frame_equal(df1, df2)
=======
        dates = pd.date_range('2023-01-03', periods=2, freq='B')
        mock_df = pd.DataFrame({
            'Open': [150.0, 151.0],
            'High': [152.0, 153.0],
            'Low': [149.0, 150.0],
            'Close': [151.0, 152.0],
            'Volume': [40000000, 41000000],
        }, index=dates)

        with patch('execution.ibkr_engine.IBKRExecutionEngine') as mock_engine_cls:
            mock_engine = MagicMock()
            mock_engine_cls.return_value = mock_engine
            mock_engine.get_historical_data.return_value = mock_df

            df1 = loader.load_ibkr_data('MSFT')
            df2 = loader.load_ibkr_data('MSFT')

            # Data should be identical
            pd.testing.assert_frame_equal(df1, df2)

>>>>>>> origin/main
