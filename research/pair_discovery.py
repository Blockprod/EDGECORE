"""
Pair discovery and screening module for identifying potential pairs.
"""

import pandas as pd
from models.cointegration import correlation_matrix, engle_granger_test, half_life_mean_reversion
from structlog import get_logger

from models.cointegration import engle_granger_test, half_life_mean_reversion

logger = get_logger(__name__)


def screen_pairs(price_data: pd.DataFrame, min_corr: float = 0.7, max_half_life: int = 60) -> list:
    """
    Screen price data for cointegrated pairs.

    Args:
        price_data: DataFrame with price series (columns = symbols)
        min_corr: Minimum correlation threshold
        max_half_life: Maximum mean reversion half-life (days)

    Returns:
        List of (symbol1, symbol2, score, half_life) tuples
    """
    corr_matrix = price_data.corr()
    symbols = price_data.columns.tolist()
    pairs: list[tuple[str, str, float]] = [
        (symbols[i], symbols[j], float(str(corr_matrix.iloc[i, j])))
        for i in range(len(symbols))
        for j in range(i + 1, len(symbols))
    ]

    candidates = []
    for sym1, sym2, corr in pairs:
        if abs(corr) < min_corr:
            continue

        try:
            result = engle_granger_test(price_data[sym1], price_data[sym2])
            if result["is_cointegrated"]:
                hl = half_life_mean_reversion(pd.Series(result["residuals"]))
                if hl and hl <= max_half_life:
                    candidates.append(
                        {
                            "sym1": sym1,
                            "sym2": sym2,
                            "correlation": corr,
                            "coint_pvalue": result["adf_pvalue"],
                            "half_life": hl,
                            "beta": result["beta"],
                        }
                    )
                    logger.info("pair_candidate", pair=f"{sym1}_{sym2}", half_life=hl)
        except Exception as e:
            logger.debug("screening_failed", sym1=sym1, sym2=sym2, error=str(e))
            continue

    return sorted(candidates, key=lambda x: x["coint_pvalue"])
