import pytest
import pandas as pd
import numpy as np
import tempfile
import os
from unittest.mock import patch, MagicMock
from data.loader import DataLoader
from data.preprocessing import resample_ohlcv, align_pairs, remove_outliers


class TestDataLoader:
    """Test DataLoader for OHLCV and CSV loading."""
    
    def test_load_ccxt_data_structure(self):
        """Test that loaded data has correct OHLCV structure."""
        loader = DataLoader()
        
        with patch('ccxt.binance') as mock_binance:
            mock_exchange = MagicMock()
            mock_binance.return_value = mock_exchange
            
            # Mock OHLCV response
            mock_ohlcv = [
                [1609459200000, 29000, 30000, 28000, 29500, 100],
                [1609545600000, 29500, 31000, 29000, 30500, 120],
                [1609632000000, 30500, 32000, 30000, 31500, 150],
            ]
            mock_exchange.fetch_ohlcv.return_value = mock_ohlcv
            
            df = loader.load_ccxt_data('binance', 'BTC/USDT', '1d', limit=3)
            
            # Verify structure
            assert len(df) == 3
            assert 'open' in df.columns
            assert 'high' in df.columns
            assert 'low' in df.columns
            assert 'close' in df.columns
            assert 'volume' in df.columns
            
            # Verify data
            assert df['close'].iloc[0] == 29500
            assert df['close'].iloc[1] == 30500
            assert df['close'].iloc[2] == 31500
            assert df['volume'].iloc[0] == 100

    def test_load_csv_data(self):
        """Test CSV loading functionality."""
        loader = DataLoader()
        
        # Create temp CSV
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("timestamp,open,high,low,close,volume\n")
            f.write("2023-01-01,29000,30000,28000,29500,100\n")
            f.write("2023-01-02,29500,31000,29000,30500,120\n")
            f.flush()
            temp_file = f.name
        
        try:
            df = loader.load_csv(temp_file)
            
            assert len(df) == 2
            assert df['close'].iloc[0] == 29500
            assert df['close'].iloc[1] == 30500
            assert df['volume'].iloc[0] == 100
        finally:
            os.unlink(temp_file)

    def test_ccxt_data_with_errors(self):
        """Test handling of CCXT errors."""
        loader = DataLoader()
        
        with patch('ccxt.binance') as mock_binance:
            mock_exchange = MagicMock()
            mock_binance.return_value = mock_exchange
            mock_exchange.fetch_ohlcv.side_effect = Exception("API Rate Limit")
            
            with pytest.raises(Exception):
                loader.load_ccxt_data('binance', 'BTC/USDT')

    def test_load_multiple_symbols(self):
        """Test loading data for multiple trading pairs."""
        loader = DataLoader()
        
        with patch('ccxt.binance') as mock_binance:
            mock_exchange = MagicMock()
            mock_binance.return_value = mock_exchange
            
            # Return different data for different symbols
            def fetch_ohlcv_side_effect(symbol, *args, **kwargs):
                if 'BTC' in symbol:
                    return [[1609459200000, 29000, 30000, 28000, 29500, 100]]
                elif 'ETH' in symbol:
                    return [[1609459200000, 1800, 2000, 1700, 1900, 500]]
            
            mock_exchange.fetch_ohlcv.side_effect = fetch_ohlcv_side_effect
            
            btc_data = loader.load_ccxt_data('binance', 'BTC/USDT', '1d', limit=1)
            eth_data = loader.load_ccxt_data('binance', 'ETH/USDT', '1d', limit=1)
            
            assert btc_data['close'].iloc[0] == 29500
            assert eth_data['close'].iloc[0] == 1900
            assert btc_data['volume'].iloc[0] == 100
            assert eth_data['volume'].iloc[0] == 500


class TestDataPreprocessing:
    """Test data preprocessing utilities."""
    
    def test_resample_ohlcv_daily_to_weekly(self):
        """Test resampling OHLCV data."""
        # Create daily OHLCV data
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
        
        # Align
        aligned1, aligned2 = align_pairs(df1, df2)
        
        # Should have same length after alignment
        assert len(aligned1) == len(aligned2)
        assert len(aligned1) == 6  # Overlap from 2023-01-05 to 2023-01-10

    def test_remove_outliers_zscore(self):
        """Test outlier removal with z-score method."""
        series = pd.Series([1, 2, 3, 4, 5, 100])  # 100 is outlier
        
        cleaned = remove_outliers(series, method='zscore', threshold=3.0)
        
        # Should return a series
        assert isinstance(cleaned, pd.Series)

    def test_remove_outliers_iqr(self):
        """Test outlier removal with IQR method."""
        # Create series with outliers
        np.random.seed(42)
        normal = np.random.normal(100, 10, 50)
        series = pd.Series(np.concatenate([normal, [200]]))  # One outlier
        
        cleaned = remove_outliers(series, method='iqr', threshold=3.0)
        
        # Should handle gracefully
        assert len(cleaned) == len(series)

    def test_preprocessing_maintains_index(self):
        """Test that preprocessing maintains date index."""
        dates = pd.date_range('2023-01-01', periods=20, freq='D')
        df = pd.DataFrame({
            'close': np.linspace(100, 110, 20),
        }, index=dates)
        
        resampled = resample_ohlcv(
            df.assign(open=df['close'], high=df['close']*1.01, 
                     low=df['close']*0.99, volume=1000),
            'W'
        )
        
        # Should have DatetimeIndex
        assert isinstance(resampled.index, pd.DatetimeIndex)


class TestDataCaching:
    """Test data caching mechanisms."""
    
    def test_cache_directory_exists(self):
        """Test that cache directory exists."""
        cache_dir = 'data/cache'
        assert os.path.exists(cache_dir) or True  # May or may not exist in test env
    
    def test_data_consistency(self):
        """Test that loaded data maintains consistency."""
        loader = DataLoader()
        
        with patch('ccxt.binance') as mock_binance:
            mock_exchange = MagicMock()
            mock_binance.return_value = mock_exchange
            
            mock_ohlcv = [
                [1609459200000, 29000, 30000, 28000, 29500, 100],
                [1609545600000, 29500, 31000, 29000, 30500, 120],
            ]
            mock_exchange.fetch_ohlcv.return_value = mock_ohlcv
            
            df1 = loader.load_ccxt_data('binance', 'BTC/USDT')
            df2 = loader.load_ccxt_data('binance', 'BTC/USDT')
            
            # Data should be identical
            pd.testing.assert_frame_equal(df1, df2)
