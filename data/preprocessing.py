from typing import cast

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
    return cast(pd.DataFrame, resampled.dropna())


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


def mark_exdates(
    prices_df: pd.DataFrame,
    symbols: list[str] | None = None,
    use_cache: bool = True,
) -> pd.DataFrame:
    """
    Add an ``is_exdate`` boolean column to *prices_df*.

    Delegates to :class:`~data.corporate_actions.CorporateActionsProvider`.
    A bar is marked ``True`` if any symbol has a split or dividend ex-date
    on that date.

    Parameters
    ----------
    prices_df : pd.DataFrame
        Index = DatetimeIndex, columns = symbol names.
    symbols : list[str] or None
        Symbols to check.  Defaults to all columns in *prices_df*.
    use_cache : bool
        Whether to use the disk cache for corporate-action data.

    Returns
    -------
    pd.DataFrame
        The original DataFrame with an additional ``is_exdate`` column.
    """
    from data.corporate_actions import CorporateActionsProvider

    provider = CorporateActionsProvider(use_cache=use_cache)
    return provider.mark_exdates(prices_df, symbols=symbols)
