"""
Realistic cost model for pair trading backtests.

Sprint 1.1 (C-01) ÔÇô foundation for unified backtest.
Sprint 2.3 (M-03) ÔÇô extended with borrowing/financing cost for leveraged positions.

Each pair-trading round-trip involves **4 transactions**:
  Entry:  long leg  + short leg
  Exit:   close long + close short

Cost components:
  1. Exchange fees (maker/taker)
  2. Slippage (fixed or volume-adaptive)
  3. Borrowing cost for the short leg (daily accrual)
  4. Financing rate for leveraged/margined positions
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class CostModelConfig:
    """Trading cost parameters for US equities via IBKR."""

    maker_fee_bps: float = 1.5  # IBKR avg execution cost
    taker_fee_bps: float = 2.0  # Taker + exchange fees
    base_slippage_bps: float = 2.0  # Large-cap average bid-ask spread
    borrowing_cost_annual_pct: float = 0.5  # General collateral ETB rate
    include_borrowing: bool = True
    slippage_model: str = "almgren_chriss"  # "fixed", "volume_adaptive", or "almgren_chriss"
    include_funding: bool = False  # Not applicable for equities
    funding_rate_daily_bps: float = 0.0  # Not used for equities (kept for API compat)
    # Almgren-Chriss market impact parameters
    market_impact_eta: float = 0.05  # Temporary impact coefficient (calibrated v32j)
    execution_delay_days: float = 0.01  # Execution delay in trading days (calibrated v32j)
    # Hard-to-borrow (HTB) per-symbol annual borrow rate overrides (decimal %).
    # E.g. {"GME": 20.0, "AMC": 15.0}. Symbols not listed fall back to
    # borrowing_cost_annual_pct (the general-collateral / ETB rate).
    htb_symbols: dict[str, float] = field(default_factory=dict)
    # Default ADV (USD/day) used in Almgren-Chriss slippage when no per-symbol
    # ADV is injected by the caller.  $10M is a conservative mid-cap estimate;
    # StrategyBacktestSimulator overrides this via adv_by_symbol.
    default_adv_usd: float = 10_000_000.0

    @classmethod
    def from_htb_csv(
        cls,
        path: str | Path,
        maker_fee_bps: float = 1.5,
        taker_fee_bps: float = 2.0,
        base_slippage_bps: float = 2.0,
        borrowing_cost_annual_pct: float = 0.5,
        include_borrowing: bool = True,
        slippage_model: str = "almgren_chriss",
        include_funding: bool = False,
        funding_rate_daily_bps: float = 0.0,
        market_impact_eta: float = 0.05,
        execution_delay_days: float = 0.01,
        default_adv_usd: float = 10_000_000.0,
    ) -> CostModelConfig:
        """Build a config loading HTB rates from a two-column CSV file.

        CSV format (no header required but accepted):
            symbol,annual_borrow_pct
            GME,25.0
            AMC,18.5

        All CostModelConfig fields can be overridden via keyword arguments.
        """
        htb: dict[str, float] = {}
        with open(path, newline="", encoding="utf-8") as fh:
            reader = csv.reader(fh)
            for row in reader:
                if len(row) < 2:
                    continue
                sym, rate_str = row[0].strip().upper(), row[1].strip()
                if sym.lower() == "symbol":  # skip header row
                    continue
                try:
                    htb[sym] = float(rate_str)
                except ValueError:
                    continue  # ignore malformed rows
        return cls(
            htb_symbols=htb,
            maker_fee_bps=maker_fee_bps,
            taker_fee_bps=taker_fee_bps,
            base_slippage_bps=base_slippage_bps,
            borrowing_cost_annual_pct=borrowing_cost_annual_pct,
            include_borrowing=include_borrowing,
            slippage_model=slippage_model,
            include_funding=include_funding,
            funding_rate_daily_bps=funding_rate_daily_bps,
            market_impact_eta=market_impact_eta,
            execution_delay_days=execution_delay_days,
            default_adv_usd=default_adv_usd,
        )


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

    def __init__(self, config: CostModelConfig | None = None):
        self.config = config or CostModelConfig()

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def execution_cost_one_leg(
        self,
        notional: float,
        volume_24h: float = 1e7,
        sigma_daily: float = 0.02,
    ) -> float:
        """Cost for ONE transaction (one leg, one direction).

        Args:
            notional: Order size in USD.
            volume_24h: 24-hour volume in USD for the traded symbol.
                Default is $10M ÔÇô a conservative estimate for mid-cap
                assets.  Callers should pass real volume data whenever
                available.
            sigma_daily: Daily return volatility of the symbol (decimal).
                Default is 0.02 (2%).
        """
        fee = self.config.taker_fee_bps / 10_000
        slip = self._slippage(notional, volume_24h, sigma_daily)
        return notional * (fee + slip)

    def entry_cost(
        self,
        notional_per_leg: float,
        volume_24h_sym1: float = 1e7,
        volume_24h_sym2: float = 1e7,
        sigma_sym1: float = 0.02,
        sigma_sym2: float = 0.02,
    ) -> float:
        """Cost to ENTER a pair trade (2 legs)."""
        return self.execution_cost_one_leg(notional_per_leg, volume_24h_sym1, sigma_sym1) + self.execution_cost_one_leg(
            notional_per_leg, volume_24h_sym2, sigma_sym2
        )

    def exit_cost(
        self,
        notional_per_leg: float,
        volume_24h_sym1: float = 1e7,
        volume_24h_sym2: float = 1e7,
        sigma_sym1: float = 0.02,
        sigma_sym2: float = 0.02,
    ) -> float:
        """Cost to EXIT a pair trade (2 legs)."""
        return self.entry_cost(notional_per_leg, volume_24h_sym1, volume_24h_sym2, sigma_sym1, sigma_sym2)

    def holding_cost(
        self,
        notional_short_leg: float,
        holding_days: int,
        symbol: str = "",
    ) -> float:
        """Borrowing cost for the short leg over *holding_days*.

        When *symbol* is provided and present in ``config.htb_symbols``, its
        per-symbol annual rate is used instead of the general-collateral
        ``borrowing_cost_annual_pct``.  This correctly prices hard-to-borrow
        stocks (GME, AMC, squeeze candidates) where borrow can run 5-50×
        the GC rate.
        """
        if not self.config.include_borrowing or holding_days <= 0:
            return 0.0
        annual_pct = self.config.htb_symbols.get(symbol.upper(), self.config.borrowing_cost_annual_pct)
        daily_rate = annual_pct / 100.0 / 365.0  # Calendar days
        return notional_short_leg * daily_rate * holding_days

    def funding_cost(self, notional_per_leg: float, holding_days: int) -> float:
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
        short_symbol: str = "",
    ) -> float:
        """Total cost for a complete round-trip (entry + exit + holding + funding).

        Pass *short_symbol* to apply the correct HTB borrow rate for the
        shorted leg (falls back to GC rate when not in ``htb_symbols``).
        """
        return (
            self.entry_cost(notional_per_leg, volume_24h_sym1, volume_24h_sym2)
            + self.exit_cost(notional_per_leg, volume_24h_sym1, volume_24h_sym2)
            + self.holding_cost(notional_per_leg, holding_days, symbol=short_symbol)
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

    def _slippage(self, order_size: float, volume_24h: float, sigma_daily: float = 0.02) -> float:
        """Return slippage as a decimal fraction (not bps).

        Three models available:
        - "fixed": flat base_slippage_bps
        - "volume_adaptive": legacy linear model
        - "almgren_chriss": 3-component institutional model
        """
        if self.config.slippage_model == "fixed":
            return self.config.base_slippage_bps / 10_000

        if volume_24h <= 0:
            return 50.0 / 10_000

        if self.config.slippage_model == "volume_adaptive":
            # Legacy linear model
            participation = order_size / volume_24h
            impact_bps = self.config.base_slippage_bps + 100.0 * participation
            return min(impact_bps, 100.0) / 10_000

        # Almgren-Chriss 3-component model
        # 1. Spread (bid-ask)
        spread = self.config.base_slippage_bps / 10_000

        # 2. Temporary market impact: ╬À ├ù ¤â ├ù ÔêÜ(Q/ADV)
        eta = self.config.market_impact_eta
        participation = order_size / volume_24h
        market_impact = eta * sigma_daily * (participation**0.5)

        # 3. Timing cost: ¤â ├ù ÔêÜ(T_exec / 252)
        t_exec = self.config.execution_delay_days
        timing_cost = sigma_daily * (t_exec / 252) ** 0.5

        total = spread + market_impact + timing_cost
        return min(total, 100.0 / 10_000)  # cap at 100 bps


# ======================================================================
# Pre-built configurations for different markets
# ======================================================================


def equity_cost_config() -> CostModelConfig:
    """
    Cost model for US equities via Interactive Brokers.

    IBKR Pro tiered pricing:
      - Commission: ~$0.005/share (modelled as ~1.0 bps on average)
      - SEC fee: ~$0.00008 ├ù notional on sells (~0.08 bps)
      - Exchange/clearing: ~0.3 bps
      - Total execution: ~1.5-2.0 bps per leg

    Short borrowing:
      - Easy-to-borrow: ~0.25-1.0% annualised
      - General collateral average: ~0.5% annualised
      - Hard-to-borrow excluded by pre-screening

    Slippage (Almgren-Chriss):
      - Spread: ~2 bps (mega-cap bid-ask)
      - Market impact: ╬À=0.10, ¤â-dependent
      - Timing cost: half-day execution delay
    """
    return CostModelConfig(
        maker_fee_bps=1.5,  # IBKR execution ~1.5 bps avg
        taker_fee_bps=2.0,  # Taker + exchange fees
        base_slippage_bps=2.0,  # Large-cap bid-ask spread
        borrowing_cost_annual_pct=0.5,  # General collateral ETB rate
        include_borrowing=True,
        slippage_model="almgren_chriss",  # Institutional 3-component model
        funding_rate_daily_bps=0.0,  # Not applicable for equities
        include_funding=False,
        market_impact_eta=0.10,  # Temporary impact (mega-caps)
        execution_delay_days=0.5,  # Half-day execution
    )
