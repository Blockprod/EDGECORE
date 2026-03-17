"""
Phase 0.4 ÔÇô Short Borrow Availability Check.

Backtest mode:
    Uses a known HTB (hard-to-borrow) symbol list with typical borrow-fee
    tiers.  Symbols flagged HTB are rejected at entry or incur elevated
    borrowing cost in the cost model.

Live mode:
    Queries ``IBGatewaySync.get_shortable_shares(symbol)`` which uses
    IBKR ``reqMktData`` generic-tick "shortableShares" (tick type 236).

Both modes enforce:
    - Minimum shortable shares threshold (default 1 000)
    - Maximum acceptable borrow fee (default 3% annualised)
"""

from dataclasses import dataclass
from typing import Dict, Optional, Set

from structlog import get_logger

logger = get_logger(__name__)


@dataclass
class BorrowCheckerConfig:
    """Configuration for short-borrow availability checking."""
    max_borrow_fee_pct: float = 3.0        # reject if annual fee > 3%
    min_shortable_shares: int = 1_000      # minimum shares available
    htb_borrow_fee_pct: float = 5.0        # assumed fee for known HTB symbols
    default_borrow_fee_pct: float = 0.5    # general collateral (ETB) rate
    enabled: bool = True


# Symbols historically known to be Hard-To-Borrow or frequently on
# the SHO threshold list.  This is a conservative static list for
# backtesting only; live trading should use real-time IBKR data.
_KNOWN_HTB_SYMBOLS: Set[str] = {
    "GME", "AMC", "BBBY", "KOSS", "EXPR", "BB", "NOK",
    "CLOV", "WISH", "WKHS", "RIDE", "GOEV", "SPCE",
    "MVIS", "SNDL", "TLRY", "BYND",
}


class BorrowChecker:
    """Check short-borrow availability and compute borrow fees.

    Usage in backtest:
        checker = BorrowChecker()
        ok, fee = checker.check_shortable("AAPL", side="long")  # always ok for long
        ok, fee = checker.check_shortable("GME", side="short")  # may reject HTB

    Usage in live:
        checker = BorrowChecker()
        checker.update_live_data("AAPL", shortable_shares=5_000_000, borrow_fee_pct=0.3)
        ok, fee = checker.check_shortable("AAPL", side="short")
    """

    def __init__(self, config: Optional[BorrowCheckerConfig] = None):
        self.config = config or BorrowCheckerConfig()
        # Live data cache: symbol ÔåÆ {shortable_shares, borrow_fee_pct}
        self._live_data: Dict[str, dict] = {}

    def check_shortable(
        self,
        symbol: str,
        side: str = "short",
    ) -> tuple:
        """Check if a symbol can be shorted.

        Args:
            symbol: Ticker symbol for the short leg.
            side: Trade side.  Long legs always pass.

        Returns:
            (allowed: bool, borrow_fee_pct: float)
            If not allowed, borrow_fee_pct is the fee that caused rejection.
        """
        if not self.config.enabled:
            return True, self.config.default_borrow_fee_pct

        # Long legs are never restricted
        if side == "long":
            return True, 0.0

        # Check live data first (populated by IBKR in live mode)
        if symbol in self._live_data:
            data = self._live_data[symbol]
            shares = data.get("shortable_shares", 0)
            fee = data.get("borrow_fee_pct", self.config.default_borrow_fee_pct)

            if shares < self.config.min_shortable_shares:
                logger.debug(
                    "short_rejected_insufficient_shares",
                    symbol=symbol,
                    shortable_shares=shares,
                    min_required=self.config.min_shortable_shares,
                )
                return False, fee

            if fee > self.config.max_borrow_fee_pct:
                logger.debug(
                    "short_rejected_high_borrow_fee",
                    symbol=symbol,
                    borrow_fee_pct=fee,
                    max_allowed=self.config.max_borrow_fee_pct,
                )
                return False, fee

            return True, fee

        # Backtest fallback: use static HTB list
        if symbol in _KNOWN_HTB_SYMBOLS:
            fee = self.config.htb_borrow_fee_pct
            if fee > self.config.max_borrow_fee_pct:
                logger.debug(
                    "short_rejected_htb_symbol",
                    symbol=symbol,
                    borrow_fee_pct=fee,
                )
                return False, fee
            return True, fee

        # General collateral ÔÇö easy to borrow
        return True, self.config.default_borrow_fee_pct

    def get_pair_borrow_fee(
        self,
        sym1: str,
        sym2: str,
        side: str,
    ) -> float:
        """Return the annualised borrow fee for the short leg of a pair.

        In a pair trade, one leg is always short:
        - side="long"  ÔåÆ short sym2
        - side="short" ÔåÆ short sym1
        """
        if not self.config.enabled:
            return self.config.default_borrow_fee_pct

        short_sym = sym2 if side == "long" else sym1
        _, fee = self.check_shortable(short_sym, side="short")
        return fee

    def update_live_data(
        self,
        symbol: str,
        shortable_shares: int,
        borrow_fee_pct: float,
    ) -> None:
        """Update live borrow data from IBKR feed."""
        self._live_data[symbol] = {
            "shortable_shares": shortable_shares,
            "borrow_fee_pct": borrow_fee_pct,
        }
