import pandas as pd
import numpy as np
from typing import Tuple, Dict, List, Optional
from pathlib import Path
import json
from datetime import datetime, timedelta
from structlog import get_logger
from data.validators import OHLCVValidator, ValidationResult, DataValidationError

logger = get_logger(__name__)

class DataLoader:
    """Load and cache OHLCV data from multiple sources with validation."""
    
    def __init__(self, cache_dir: str = "data/cache", validator: Optional[OHLCVValidator] = None):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        # PHASE 2 FEATURE 3: Inject validator (default to OHLCVValidator if not provided)
        self.validator = validator or OHLCVValidator()
    
    def load_ccxt_data(
        self,
        exchange_name: str,
        symbol: str,
        timeframe: str = "1d",
        since: str = None,
        limit: int = 1000,
        validate: bool = True
    ) -> pd.DataFrame:
        """
        Load OHLCV data from CCXT exchange (Binance, etc.).
        
        PHASE 2 FEATURE 3: Validate data after loading.
        
        Args:
            exchange_name: CCXT exchange name
            symbol: Trading pair (e.g., "BTC/USDC")
            timeframe: Candle interval ("1d", "4h", etc.)
            since: ISO 8601 start date
            limit: Number of candles
            validate: If True, validate OHLCV data (raises DataValidationError on failure)
        
        Returns:
            DataFrame with OHLCV data (validated if validate=True)
        
        Raises:
            DataValidationError: If validation fails and validate=True
        """
        try:
            import ccxt
            exchange_class = getattr(ccxt, exchange_name)
            exchange = exchange_class({'enableRateLimit': True})
            
            if since:
                since_ms = int(datetime.fromisoformat(since).timestamp() * 1000)
            else:
                since_ms = int((datetime.now() - timedelta(days=730)).timestamp() * 1000)
            
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=since_ms, limit=limit)
            
            df = pd.DataFrame(
                ohlcv,
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
            )
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            # PHASE 2 FEATURE 3: Validate loaded data
            if validate:
                validation_result = self.validator.validate(df, raise_on_error=True)
                logger.info(
                    "data_loaded_and_validated",
                    exchange=exchange_name,
                    symbol=symbol,
                    rows=len(df),
                    checks_passed=validation_result.checks_passed,
                    checks_failed=validation_result.checks_failed
                )
            else:
                logger.info(
                    "data_loaded_no_validation",
                    exchange=exchange_name,
                    symbol=symbol,
                    rows=len(df)
                )
            
            return df
        
        except DataValidationError as e:
            # Validation failed - log and re-raise
            logger.error(
                "data_validation_failed",
                exchange=exchange_name,
                symbol=symbol,
                error=str(e)
            )
            raise
        except Exception as e:
            logger.error(
                "data_load_failed",
                exchange=exchange_name,
                symbol=symbol,
                error=str(e)
            )
            raise
    
    def load_csv(self, filepath: str) -> pd.DataFrame:
        """Load OHLCV data from CSV file."""
        df = pd.read_csv(filepath, index_col=0, parse_dates=True)
        logger.info("csv_loaded", filepath=filepath, rows=len(df))
        return df
    
    def cache_data(self, df: pd.DataFrame, symbol: str, timeframe: str) -> None:
        """Cache DataFrame to disk."""
        cache_file = self.cache_dir / f"{symbol}_{timeframe}.parquet"
        df.to_parquet(cache_file)
        logger.info("data_cached", symbol=symbol, timeframe=timeframe, path=str(cache_file))
    
    def load_cached(self, symbol: str, timeframe: str) -> pd.DataFrame:
        """Load cached data if available."""
        cache_file = self.cache_dir / f"{symbol}_{timeframe}.parquet"
        if cache_file.exists():
            df = pd.read_parquet(cache_file)
            logger.info("cache_hit", symbol=symbol, timeframe=timeframe)
            return df
        logger.info("cache_miss", symbol=symbol, timeframe=timeframe)
        return None
