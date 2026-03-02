"""
Realistic cost model for pair trading backtests.

Sprint 1.1 (C-01) – foundation for unified backtest.
Sprint 2.3 (M-03) – extended with borrowing/financing cost for leveraged positions.

Each pair-trading round-trip involves **4 transactions**:
  Entry:  long leg  + short leg
  Exit:   close long + close short

Cost components:
  1. Exchange fees (maker/taker)
  2. Slippage (fixed or volume-adaptive)
  3. Borrowing cost for the short leg (daily accrual)
  4. Financing rate for leveraged/margined positions
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class CostModelConfig:
    """Trading cost parameters for US equities via IBKR."""
    maker_fee_bps: float = 1.5          # IBKR avg execution cost
    taker_fee_bps: float = 2.0          # Taker + exchange fees
    base_slippage_bps: float = 2.0      # Large-cap average slippage
    borrowing_cost_annual_pct: float = 0.5  # General collateral ETB rate
    include_borrowing: bool = True
    slippage_model: str = "volume_adaptive"  # "fixed" or "volume_adaptive"
    include_funding: bool = False         # Not applicable for equities
    funding_rate_daily_bps: float = 0.0   # Not used for equities (kept for API compat)


class CostModel:
    """
    Realistic 4-leg cost model for pair trading.

    Usage::

        model = CostModel()
        entry = model.entry_cost(notional_per_leg=5000)
        exit_ = model.exit_cost(notional_per_leg=5000)
        hold  = model.holding_cost(notional_short_leg=5000, holding_days=7)
        total = model.round_trip_cost(5000, holding_days=7)
    """

    def __init__(self, config: Optional[CostModelConfig] = None):
        self.config = config or CostModelConfig()

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def execution_cost_one_leg(
        self, notional: float, volume_24h: float = 1e7
    ) -> float:
        """Cost for ONE transaction (one leg, one direction).

        Args:
            notional: Order size in USD.
            volume_24h: 24-hour volume in USD for the traded symbol.
                Default is $10M – a conservative estimate for mid-cap
                assets.  Callers should pass real volume data whenever
                available.
        """
        fee = self.config.taker_fee_bps / 10_000
        slip = self._slippage(notional, volume_24h)
        return notional * (fee + slip)

    def entry_cost(
        self,
        notional_per_leg: float,
        volume_24h_sym1: float = 1e7,
        volume_24h_sym2: float = 1e7,
    ) -> float:
        """Cost to ENTER a pair trade (2 legs)."""
        return (
            self.execution_cost_one_leg(notional_per_leg, volume_24h_sym1)
            + self.execution_cost_one_leg(notional_per_leg, volume_24h_sym2)
        )

    def exit_cost(
        self,
        notional_per_leg: float,
        volume_24h_sym1: float = 1e7,
        volume_24h_sym2: float = 1e7,
    ) -> float:
        """Cost to EXIT a pair trade (2 legs)."""
        return self.entry_cost(notional_per_leg, volume_24h_sym1, volume_24h_sym2)

    def holding_cost(
        self, notional_short_leg: float, holding_days: int
    ) -> float:
        """Borrowing cost for the short leg over *holding_days*."""
        if not self.config.include_borrowing or holding_days <= 0:
            return 0.0
        daily_rate = self.config.borrowing_cost_annual_pct / 100.0 / 365.0  # Calendar days
        return notional_short_leg * daily_rate * holding_days

    def funding_cost(
        self, notional_per_leg: float, holding_days: int
    ) -> float:
        """Financing cost for leveraged positions over *holding_days*.
        
        Both legs may be subject to margin financing.
        Conservative approach: charge financing on both legs.
        """
        if not self.config.include_funding or holding_days <= 0:
            return 0.0
        daily_funding_rate = self.config.funding_rate_daily_bps / 10_000
        # Both legs exposed to funding
        return 2 * notional_per_leg * daily_funding_rate * holding_days

    def round_trip_cost(
        self,
        notional_per_leg: float,
        holding_days: int = 0,
        volume_24h_sym1: float = 1e7,
        volume_24h_sym2: float = 1e7,
    ) -> float:
        """Total cost for a complete round-trip (entry + exit + holding + funding)."""
        return (
            self.entry_cost(notional_per_leg, volume_24h_sym1, volume_24h_sym2)
            + self.exit_cost(notional_per_leg, volume_24h_sym1, volume_24h_sym2)
            + self.holding_cost(notional_per_leg, holding_days)
            + self.funding_cost(notional_per_leg, holding_days)
        )

    def round_trip_cost_bps(self, notional_per_leg: float, **kwargs) -> float:
        """Round-trip cost expressed in basis points of total notional (2 legs)."""
        total_notional = 2 * notional_per_leg
        if total_notional <= 0:
            return 0.0
        return self.round_trip_cost(notional_per_leg, **kwargs) / total_notional * 10_000

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _slippage(self, order_size: float, volume_24h: float) -> float:
        """Return slippage as a decimal fraction (not bps)."""
        if self.config.slippage_model == "fixed":
            return self.config.base_slippage_bps / 10_000

        # Volume-adaptive model: base + market-impact component
        if volume_24h <= 0:
            return 50.0 / 10_000  # worst-case: 50 bps

        participation = order_size / volume_24h
        impact_bps = self.config.base_slippage_bps + 100.0 * participation
        return min(impact_bps, 100.0) / 10_000  # cap at 100 bps


# ======================================================================
# Pre-built configurations for different markets
# ======================================================================

def equity_cost_config() -> CostModelConfig:
    """
    Cost model for US equities via Interactive Brokers.

    IBKR Pro tiered pricing:
      - Commission: ~$0.005/share (modelled as ~1.0 bps on average)
      - SEC fee: ~$0.00008 × notional on sells (~0.08 bps)
      - Exchange/clearing: ~0.3 bps
      - Total execution: ~1.5-2.0 bps per leg

    Short borrowing:
      - Easy-to-borrow: ~0.25-1.0% annualised
      - General collateral average: ~0.5% annualised
      - Hard-to-borrow excluded by pre-screening

    Slippage:
      - S&P 500 large-cap: ~1-2 bps
      - Mid-cap: ~3-5 bps
    """
    return CostModelConfig(
        maker_fee_bps=1.5,               # IBKR execution ~1.5 bps avg
        taker_fee_bps=2.0,               # Taker + exchange fees
        base_slippage_bps=2.0,           # Large-cap average
        borrowing_cost_annual_pct=0.5,   # General collateral ETB rate
        include_borrowing=True,
        slippage_model="volume_adaptive",
        funding_rate_daily_bps=0.0,      # Not applicable for equities
        include_funding=False,
    )
