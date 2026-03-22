import numpy as np
import pandas as pd


def resample_ohlcv(df: pd.DataFrame, target_freq: str) -> pd.DataFrame:
    """
    Resample OHLCV data to target frequency.

    Args:
        df: DataFrame with OHLCV columns
        target_freq: Target frequency (e.g., "D", "W", "M")

    Returns:
        Resampled DataFrame
    """
    resampled = df.resample(target_freq).agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    )
    return resampled.dropna()


def align_pairs(df1: pd.DataFrame, df2: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Align two time series on common date range.

    Args:
        df1: First DataFrame
        df2: Second DataFrame

    Returns:
        Tuple of aligned DataFrames
    """
    common_index = df1.index.intersection(df2.index)
    return df1.loc[common_index], df2.loc[common_index]


def remove_outliers(series: pd.Series, method: str = "iqr", threshold: float = 3.0) -> pd.Series:
    """
    Remove statistical outliers from series.

    Args:
        series: Input series
        method: "iqr" or "zscore"
        threshold: Outlier threshold

    Returns:
        Cleaned series with NaN for outliers
    """
    if method == "iqr":
        Q1 = series.quantile(0.25)
        Q3 = series.quantile(0.75)
        IQR = Q3 - Q1
        mask = (series < Q1 - 1.5 * IQR) | (series > Q3 + 1.5 * IQR)
    else:  # zscore
        z_scores = np.abs((series - series.mean()) / series.std())
        mask = z_scores > threshold

    return series.where(~mask, np.nan)
