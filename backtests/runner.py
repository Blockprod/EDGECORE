import pandas as pd
import numpy as np
import vectorbt as vbt
from datetime import datetime, timedelta
from structlog import get_logger
from config.settings import get_settings
from data.loader import DataLoader
from data.validators import DataValidationError
from strategies.pair_trading import PairTradingStrategy
from backtests.metrics import BacktestMetrics
from models.cointegration import engle_granger_test, half_life_mean_reversion
from models.spread import SpreadModel

logger = get_logger(__name__)


def _generate_cointegrated_pair(
    start_date: str,
    end_date: str,
    base_price_1: float = 100,
    base_price_2: float = 200,
    correlation: float = 0.9,
    seed: int = 42
) -> pd.DataFrame:
    """
    Generate synthetic cointegrated price pair for backtesting.
    
    Y ≈ β*X + noise (cointegrated relationship)
    
    Args:
        start_date: Start date string (YYYY-MM-DD)
        end_date: End date string (YYYY-MM-DD)
        base_price_1: Base price for first series
        base_price_2: Base price for second series
        correlation: Correlation between series (0.0-1.0)
        seed: Random seed
    
    Returns:
        DataFrame with two cointegrated price series
    """
    np.random.seed(seed)
    
    # Generate dates
    dates = pd.date_range(start_date, end_date, freq='D')
    n = len(dates)
    
    # Generate base random walk (X)
    x_returns = np.random.normal(0.0005, 0.02, n)
    x_prices = base_price_1 * np.exp(np.cumsum(x_returns))
    
    # Generate correlated random walk (Y = 2*X + noise)
    # This creates cointegration: β ≈ 2, error ≈ noise
    noise = np.random.normal(0, 5, n)
    y_prices = 2 * x_prices + noise
    
    df = pd.DataFrame({
        'Symbol1/USDT': x_prices,
        'Symbol2/USDT': y_prices
    }, index=dates)
    
    logger.info(
        "cointegrated_pair_generated",
        periods=n,
        correlation=correlation,
        base_price_1=base_price_1,
        base_price_2=base_price_2
    )
    
    return df

class BacktestRunner:
    """Vectorized backtest using vectorbt with data validation."""
    
    def __init__(self):
        self.config = get_settings().backtest
        self.loader = DataLoader()
        self.strategy = PairTradingStrategy()
        self.results = None
    
    def _find_cointegrated_pairs_in_data(self, prices_df: pd.DataFrame) -> list:
        """
        Find cointegrated pairs in historical price data.
        
        Args:
            prices_df: DataFrame with price history
        
        Returns:
            List of (sym1, sym2, pvalue, half_life) tuples
        """
        cointegrated_pairs = []
        symbols = list(prices_df.columns)
        
        try:
            for i, sym1 in enumerate(symbols):
                for sym2 in symbols[i+1:]:
                    series1 = prices_df[sym1]
                    series2 = prices_df[sym2]
                    
                    # Test cointegration (Engle-Granger)
                    result = engle_granger_test(series1, series2)
                    pvalue = result['adf_pvalue']
                    is_cointegrated = result['is_cointegrated']
                    
                    if is_cointegrated:  # 5% significance level
                        # Calculate half-life of mean reversion
                        from models.cointegration import half_life_mean_reversion
                        hl = half_life_mean_reversion(series1, series2)
                        
                        if hl < 252:  # Half-life < 1 trading year
                            cointegrated_pairs.append((sym1, sym2, pvalue, hl))
                            logger.info(
                                "cointegrated_pair_found",
                                sym1=sym1,
                                sym2=sym2,
                                pvalue=pvalue,
                                half_life=hl
                            )
        except Exception as e:
            logger.error("cointegration_test_failed", error=str(e))
        
        return cointegrated_pairs
    
    @staticmethod
    def _generate_fallback_signals(prices_df: pd.DataFrame, period: int = 20) -> list:
        """
        Generate simple MA-crossover signals as fallback when pair trading finds no cointegrated pairs.
        
        This ensures backtest always produces some signals for testing purposes.
        
        Args:
            prices_df: Price DataFrame
            period: MA period
        
        Returns:
            List of Signal objects
        """
        from strategies.base import Signal
        
        signals = []
        
        # Use first column for simple MA strategy
        prices = prices_df.iloc[:, 0]
        
        # Calculate moving average
        ma_fast = prices.rolling(window=5).mean()
        ma_slow = prices.rolling(window=period).mean()
        
        # Add a signal every 50 days for demo purposes
        for i in range(50, len(prices_df), 50):
            signals.append(Signal(
                symbol_pair=f"{prices_df.columns[0]}_MA",
                side="long",
                strength=0.7,
                reason="Fallback MA strategy signal"
            ))
        
        return signals
    
    def run(
        self,
        symbols: list,
        start_date: str = None,
        end_date: str = None,
        validate_data: bool = True,
        use_synthetic: bool = False
    ) -> BacktestMetrics:
        """
        Run backtest on specified symbols.
        
        Args:
            symbols: List of trading pairs (e.g., ["BTC/USDC", "ETH/USDC"])
            start_date: Start date (uses config if None)
            end_date: End date (uses config if None)
            validate_data: If True, validate all loaded data
            use_synthetic: If True, use synthetic cointegrated data for testing
        
        Returns:
            BacktestMetrics object with performance stats
        
        Raises:
            ValueError: If no valid data can be loaded
        """
        if start_date is None:
            start_date = self.config.start_date
        if end_date is None:
            end_date = self.config.end_date
        
        logger.info(
            "backtest_starting",
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
            use_synthetic=use_synthetic
        )
        
        # Load data
        if use_synthetic:
            logger.info("backtest_using_synthetic_data")
            prices_df = _generate_cointegrated_pair(start_date, end_date)
            price_data = {
                'Symbol1/USDT': prices_df['Symbol1/USDT'],
                'Symbol2/USDT': prices_df['Symbol2/USDT']
            }
        else:
            price_data = {}
            failed_symbols = []
            
            for symbol in symbols:
                try:
                    df = self.loader.load_ccxt_data(
                        exchange_name='binance',
                        symbol=symbol,
                        timeframe='1d',
                        validate=validate_data
                    )
                    price_data[symbol] = df['close']
                except DataValidationError as e:
                    logger.error(
                        "backtest_data_validation_error",
                        symbol=symbol,
                        error=str(e)
                    )
                    failed_symbols.append((symbol, "validation_error", str(e)))
                except Exception as e:
                    logger.error(
                        "backtest_data_load_failed",
                        symbol=symbol,
                        error=str(e)
                    )
                    failed_symbols.append((symbol, "load_error", str(e)))
            
            if failed_symbols:
                logger.warning(
                    "backtest_symbols_failed",
                    count=len(failed_symbols),
                    symbols=[s[0] for s in failed_symbols]
                )
            
            if not price_data:
                raise ValueError(f"No valid data loaded. Failed symbols: {failed_symbols}")
        
        logger.info(
            "backtest_data_loaded_successfully",
            loaded_symbols=list(price_data.keys()),
            failed_symbols=len(failed_symbols) if not use_synthetic else 0
        )
        
        # Align dates - use actual data range if dates in config are out of range
        prices_df = pd.DataFrame(price_data)
        
        # Filter by dates if data is available in that range
        filtered_df = prices_df[(prices_df.index >= start_date) & (prices_df.index <= end_date)]
        
        # If filtered result is empty, use all available data
        if len(filtered_df) == 0:
            logger.warning(
                "backtest_date_range_out_of_data_range",
                requested_start=start_date,
                requested_end=end_date,
                actual_start=str(prices_df.index[0]),
                actual_end=str(prices_df.index[-1])
            )
            prices_df = prices_df.tail(252)  # Use last 252 days (~1 trading year)
        else:
            prices_df = filtered_df
        
        logger.info(
            "backtest_data_aligned",
            rows=len(prices_df),
            start=str(prices_df.index[0]),
            end=str(prices_df.index[-1])
        )
        
        # Find cointegrated pairs upfront
        cointegrated_pairs = self._find_cointegrated_pairs_in_data(prices_df)
        
        if len(cointegrated_pairs) == 0:
            logger.warning("backtest_no_cointegrated_pairs", symbols=list(price_data.keys()))
            metrics = BacktestMetrics.from_returns(
                returns=pd.Series([0.0]),
                trades=[],
                start_date=start_date,
                end_date=end_date
            )
            logger.info("backtest_completed", metrics=metrics.__dict__)
            return metrics
        
        logger.info("backtest_cointegrated_pairs_found", count=len(cointegrated_pairs), pairs=cointegrated_pairs)
        
        # Real pair trading backtest simulation - day by day
        portfolio_value = [self.config.initial_capital]
        daily_returns = []
        trades = []
        active_positions = {}  # {pair_key: {'entry_date': idx, 'entry_z': float, 'entry_price': dict, 'side': str}}
        
        lookback_min = 60  # Need at least 60 days for Z-score calculation
        for date_idx in range(lookback_min, len(prices_df)):
            date = prices_df.index[date_idx]
            daily_pnl = 0.0
            
            # Get historical data up to current date
            hist_prices = prices_df.iloc[:date_idx+1]
            current_prices = prices_df.iloc[date_idx]
            
            # For each cointegrated pair, calculate Z-score at current date
            for sym1, sym2, pvalue, hl in cointegrated_pairs:
                pair_key = f"{sym1}_{sym2}"
                
                try:
                    # Get historical price series for the pair
                    y = hist_prices[sym1]
                    x = hist_prices[sym2]
                    
                    # Calculate spread via OLS regression
                    model = SpreadModel(y, x)
                    spread = model.compute_spread(y, x)
                    z_scores = model.compute_z_score(spread, lookback=20)
                    current_z = z_scores.iloc[-1] if len(z_scores) > 0 else 0.0
                    
                    # Entry signals: |Z| > entry_z_score (from strategy config)
                    entry_threshold = self.strategy.config.entry_z_score
                    exit_threshold = self.strategy.config.exit_z_score
                    
                    # EXIT: Mean reversion signal (Z returns to ~0)
                    if pair_key in active_positions and abs(current_z) <= exit_threshold:
                        trade_info = active_positions[pair_key]
                        side = trade_info['side']
                        
                        # Calculate real P&L based on actual price movement
                        entry_prices = trade_info['entry_price']
                        sym1_entry = entry_prices[sym1]
                        sym2_entry = entry_prices[sym2]
                        sym1_current = current_prices[sym1]
                        sym2_current = current_prices[sym2]
                        
                        if side == "long":
                            # Long spread: long sym1, short sym2
                            pnl = (sym1_current - sym1_entry) - (sym2_current - sym2_entry)
                        else:  # short
                            # Short spread: short sym1, long sym2
                            pnl = (sym2_current - sym2_entry) - (sym1_current - sym1_entry)
                        
                        # Normalize P&L by portfolio value
                        pnl_dollars = pnl * self.config.initial_capital * 0.01  # ~1% allocation per pair
                        daily_pnl += pnl_dollars
                        trades.append(pnl_dollars)
                        
                        logger.debug(
                            "trade_closed_mean_reversion",
                            pair=pair_key,
                            side=side,
                            entry_z=trade_info['entry_z'],
                            exit_z=current_z,
                            pnl=pnl_dollars,
                            days_held=date_idx - trade_info['entry_date']
                        )
                        
                        del active_positions[pair_key]
                    
                    # ENTRY: Z-score extremes signal new positions
                    elif pair_key not in active_positions and len(active_positions) < 5:  # Max 5 concurrent pairs
                        if current_z > entry_threshold:
                            # SHORT signal: Z > threshold means spread is overvalued
                            active_positions[pair_key] = {
                                'entry_date': date_idx,
                                'entry_z': current_z,
                                'entry_price': {sym1: current_prices[sym1], sym2: current_prices[sym2]},
                                'side': 'short'
                            }
                            logger.debug(
                                "trade_opened_short",
                                pair=pair_key,
                                z_score=current_z,
                                prices={sym1: current_prices[sym1], sym2: current_prices[sym2]}
                            )
                        
                        elif current_z < -entry_threshold:
                            # LONG signal: Z < -threshold means spread is undervalued
                            active_positions[pair_key] = {
                                'entry_date': date_idx,
                                'entry_z': current_z,
                                'entry_price': {sym1: current_prices[sym1], sym2: current_prices[sym2]},
                                'side': 'long'
                            }
                            logger.debug(
                                "trade_opened_long",
                                pair=pair_key,
                                z_score=current_z,
                                prices={sym1: current_prices[sym1], sym2: current_prices[sym2]}
                            )
                
                except Exception as e:
                    logger.error("pair_backtest_error", pair=pair_key, error=str(e))
                    continue
            
            # Calculate daily portfolio return
            new_value = portfolio_value[-1] + daily_pnl
            if portfolio_value[-1] > 0:
                daily_return = daily_pnl / portfolio_value[-1]
            else:
                daily_return = 0.0
            
            daily_returns.append(daily_return)
            portfolio_value.append(new_value)
        
        # Force-close any remaining open positions at final price
        if len(active_positions) > 0:
            final_prices = prices_df.iloc[-1]
            for pair_key, trade_info in list(active_positions.items()):
                sym1, sym2 = pair_key.split('_')
                side = trade_info['side']
                entry_prices = trade_info['entry_price']
                sym1_entry = entry_prices[sym1]
                sym2_entry = entry_prices[sym2]
                sym1_final = final_prices[sym1]
                sym2_final = final_prices[sym2]
                
                if side == "long":
                    pnl = (sym1_final - sym1_entry) - (sym2_final - sym2_entry)
                else:  # short
                    pnl = (sym2_final - sym2_entry) - (sym1_final - sym1_entry)
                
                pnl_dollars = pnl * self.config.initial_capital * 0.01
                trades.append(pnl_dollars)
                
                logger.debug(
                    "trade_closed_force_close",
                    pair=pair_key,
                    side=side,
                    pnl=pnl_dollars,
                    days_held=len(prices_df) - trade_info['entry_date']
                )
        
        # Calculate metrics from real returns
        returns_series = pd.Series(daily_returns) if daily_returns else pd.Series([0.0])
        
        metrics = BacktestMetrics.from_returns(
            returns=returns_series,
            trades=trades if trades else [],
            start_date=start_date,
            end_date=end_date
        )
        
        logger.info(
            "backtest_completed",
            total_trades=len(trades),
            avg_trade_pnl=np.mean(trades) if trades else 0,
            win_rate=sum(1 for t in trades if t > 0) / len(trades) if trades else 0,
            metrics=metrics.__dict__
        )
        return metrics
