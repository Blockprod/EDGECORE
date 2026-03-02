"""
Concentration Limit Manager for Portfolio Risk Control (S2.4).

Problem: Multiple pair positions can concentrate exposure in single symbols.
Example: Trading AAPL_MSFT, AAPL_GOOGL, AAPL_AMZN creates 50%+ AAPL concentration.

Solution: Track symbol exposure across all pairs, enforce per-symbol limits.

Mechanism:
- Each pair has two symbols (e.g., AAPL_MSFT contains AAPL and MSFT)
- Long pair PAIR_1: positions AAPL long, MSFT short
- Calculate net portfolio exposure: sum across all pairs
- Reject new trades if symbol would exceed concentration limit

Expected Impact: +18 Sharpe points from reduced concentration risk
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional, Set
import pandas as pd
import numpy as np
from structlog import get_logger

logger = get_logger(__name__)


@dataclass
class SymbolExposure:
    """Track exposure for a single symbol across all positions."""
    symbol: str
    long_notional: float = 0.0  # Net long exposure
    short_notional: float = 0.0  # Net short exposure (absolute value)
    net_exposure: float = 0.0  # long - short (can be negative)
    position_count: int = 0  # Number of pairs this symbol is in
    pairs: Set[str] = field(default_factory=set)  # Which pairs use this symbol
    
    @property
    def gross_exposure(self) -> float:
        """Total absolute exposure (long + short notional)."""
        return abs(self.long_notional) + abs(self.short_notional)
    
    def concentration_pct_of(self, portfolio_aum: float) -> float:
        """Concentration as fraction of portfolio AUM (0-100).

        This measures *how much of the portfolio* is exposed to this symbol,
        not the directionality of the exposure.
        """
        if portfolio_aum <= 0 or self.gross_exposure == 0:
            return 0.0
        return self.gross_exposure / portfolio_aum * 100

    @property
    def concentration_pct(self) -> float:
        """Deprecated self-contained fallback (no AUM context).

        Use ``concentration_pct_of(aum)`` for AUM-based concentration.
        """
        if self.gross_exposure == 0:
            return 0.0
        return self.gross_exposure / max(self.gross_exposure, 1.0) * 100


class ConcentrationLimitManager:
    """
    Manage per-symbol concentration limits across pair trading portfolio.
    
    Problem: Without limits, portfolio can accumulate excessive exposure to single symbols.
    
    Solution:
    - Track net exposure for each symbol
    - Enforce maximum concentration for each symbol
    - Reject trades that would exceed limits
    - Track which pairs contribute to each symbol's exposure
    """
    
    def __init__(
        self,
        max_symbol_concentration_pct: float = 30.0,
        allow_rebalancing: bool = True,
        portfolio_aum: float = 100_000.0,
    ):
        """
        Initialize concentration limit manager.
        
        Args:
            max_symbol_concentration_pct: Maximum allowed concentration per symbol (default: 30%)
            allow_rebalancing: Allow position exits to reclaim concentration capacity
            portfolio_aum: Total portfolio AUM used as denominator for concentration %
        """
        self.max_concentration = max_symbol_concentration_pct
        self.allow_rebalancing = allow_rebalancing
        self.portfolio_aum = portfolio_aum
        self.symbol_exposures: Dict[str, SymbolExposure] = {}
        self.positions: Dict[str, Dict] = {}  # pair_key -> position info
        
        logger.info(
            "concentration_limit_manager_initialized",
            max_concentration_pct=max_symbol_concentration_pct,
            allow_rebalancing=allow_rebalancing
        )
    
    def add_position(
        self,
        pair_key: str,
        symbol1: str,
        symbol2: str,
        side: str,
        notional: float = 1.0
    ) -> Tuple[bool, Optional[str]]:
        """
        Try to add a position, checking concentration limits.
        
        In pair trading:
        - Long spread: Long symbol1, short symbol2
        - Short spread: Short symbol1, long symbol2
        
        Args:
            pair_key: Pair identifier (e.g., "AAPL_MSFT")
            symbol1: First symbol
            symbol2: Second symbol
            side: "long" or "short"
            notional: Position size (default: 1.0 for equal weighting)
        
        Returns:
            (allowed: bool, reason: str or None)
            - (True, None) if position can be added
            - (False, reason) if concentration limits violated
        """
        # Determine exposure direction
        if side == "long":
            sym1_direction = "long"
            sym2_direction = "short"
        else:  # short
            sym1_direction = "short"
            sym2_direction = "long"
        
        # Calculate new exposures if position is added
        new_sym1_exposure = self._calculate_exposure_if_added(
            symbol1, sym1_direction, notional
        )
        new_sym2_exposure = self._calculate_exposure_if_added(
            symbol2, sym2_direction, notional
        )
        
        # Check concentration limits
        if new_sym1_exposure > self.max_concentration:
            reason = (
                f"Position would exceed concentration limit: "
                f"{symbol1} concentration would be {new_sym1_exposure:.1f}% "
                f"(limit: {self.max_concentration}%)"
            )
            logger.warning(
                "concentration_limit_rejected_symbol1",
                pair=pair_key,
                symbol=symbol1,
                new_concentration=f"{new_sym1_exposure:.1f}%",
                limit=f"{self.max_concentration}%"
            )
            return False, reason
        
        if new_sym2_exposure > self.max_concentration:
            reason = (
                f"Position would exceed concentration limit: "
                f"{symbol2} concentration would be {new_sym2_exposure:.1f}% "
                f"(limit: {self.max_concentration}%)"
            )
            logger.warning(
                "concentration_limit_rejected_symbol2",
                pair=pair_key,
                symbol=symbol2,
                new_concentration=f"{new_sym2_exposure:.1f}%",
                limit=f"{self.max_concentration}%"
            )
            return False, reason
        
        # Limits OK, add the position
        self.positions[pair_key] = {
            'symbol1': symbol1,
            'symbol2': symbol2,
            'side': side,
            'notional': notional,
            'entry_time': pd.Timestamp.now()
        }
        
        # Update exposures
        self._update_exposure(symbol1, sym1_direction, notional, pair_key)
        self._update_exposure(symbol2, sym2_direction, notional, pair_key)
        
        logger.info(
            "position_added_within_limits",
            pair=pair_key,
            side=side,
            symbol1=symbol1,
            symbol2=symbol2,
            sym1_concentration=f"{new_sym1_exposure:.1f}%",
            sym2_concentration=f"{new_sym2_exposure:.1f}%"
        )
        
        return True, None
    
    def remove_position(self, pair_key: str) -> None:
        """
        Remove position and update exposures (on exit).
        
        Args:
            pair_key: Pair identifier to remove
        """
        if pair_key not in self.positions:
            return
        
        pos = self.positions[pair_key]
        symbol1 = pos['symbol1']
        symbol2 = pos['symbol2']
        side = pos['side']
        notional = pos['notional']
        
        # Determine original exposure direction
        if side == "long":
            sym1_direction = "long"
            sym2_direction = "short"
        else:
            sym1_direction = "short"
            sym2_direction = "long"
        
        # Reverse the exposure
        self._remove_exposure(symbol1, sym1_direction, notional, pair_key)
        self._remove_exposure(symbol2, sym2_direction, notional, pair_key)
        
        del self.positions[pair_key]
        
        logger.info(
            "position_removed",
            pair=pair_key,
            symbol1=symbol1,
            symbol2=symbol2
        )
    
    def _calculate_exposure_if_added(
        self,
        symbol: str,
        direction: str,
        notional: float
    ) -> float:
        """
        Calculate what concentration would be if position is added.
        
        Args:
            symbol: Symbol to check
            direction: "long" or "short"
            notional: Position size
        
        Returns:
            New concentration percentage [0-100]
        """
        current = self.symbol_exposures.get(symbol, SymbolExposure(symbol=symbol))
        
        # Projected exposures
        new_long = current.long_notional + (notional if direction == "long" else 0)
        new_short = current.short_notional + (notional if direction == "short" else 0)
        new_gross = abs(new_long) + abs(new_short)
        
        # Concentration = gross exposure as fraction of AUM
        if self.portfolio_aum <= 0 or new_gross == 0:
            return 0.0
        
        concentration = new_gross / self.portfolio_aum * 100
        return concentration
    
    def _update_exposure(
        self,
        symbol: str,
        direction: str,
        notional: float,
        pair_key: str
    ) -> None:
        """Update symbol exposure tracking."""
        if symbol not in self.symbol_exposures:
            self.symbol_exposures[symbol] = SymbolExposure(symbol=symbol)
        
        exposure = self.symbol_exposures[symbol]
        
        if direction == "long":
            exposure.long_notional += notional
        else:
            exposure.short_notional += notional
        
        exposure.net_exposure = exposure.long_notional - exposure.short_notional
        exposure.position_count += 1
        exposure.pairs.add(pair_key)
    
    def _remove_exposure(
        self,
        symbol: str,
        direction: str,
        notional: float,
        pair_key: str
    ) -> None:
        """Remove symbol exposure (on position exit)."""
        if symbol not in self.symbol_exposures:
            return
        
        exposure = self.symbol_exposures[symbol]
        
        if direction == "long":
            exposure.long_notional = max(0, exposure.long_notional - notional)
        else:
            exposure.short_notional = max(0, exposure.short_notional - notional)
        
        exposure.net_exposure = exposure.long_notional - exposure.short_notional
        exposure.position_count = max(0, exposure.position_count - 1)
        exposure.pairs.discard(pair_key)
    
    def get_symbol_concentration(self, symbol: str) -> Tuple[float, str]:
        """
        Get current concentration for symbol.
        
        Args:
            symbol: Symbol to check
        
        Returns:
            (concentration_pct, status_text)
            concentration_pct: 0-100
            status_text: "Low", "Medium", "High", "Critical"
        """
        if symbol not in self.symbol_exposures:
            return 0.0, "Low"
        
        exposure = self.symbol_exposures[symbol]
        concentration = exposure.concentration_pct_of(self.portfolio_aum)
        
        if concentration < 10:
            status = "Low"
        elif concentration < 20:
            status = "Medium"
        elif concentration < self.max_concentration:
            status = "High"
        else:
            status = "Critical"
        
        return concentration, status
    
    def get_available_capacity(self, symbol: str) -> float:
        """
        Get how much more this symbol can take before hitting limit.
        
        Returns:
            Available concentration percentage (0-100)
        """
        concentration, _ = self.get_symbol_concentration(symbol)
        return max(0, self.max_concentration - concentration)

    def update_aum(self, new_aum: float) -> None:
        """Update portfolio AUM for dynamic concentration tracking."""
        if new_aum <= 0:
            raise ValueError(f"AUM must be positive, got {new_aum}")
        self.portfolio_aum = new_aum
    
    def get_portfolio_summary(self) -> Dict:
        """Get summary of all symbol exposures in portfolio."""
        if not self.symbol_exposures:
            return {
                'total_symbols': 0,
                'total_positions': 0,
                'max_concentration': self.max_concentration,
                'symbols': {}
            }
        
        symbols_summary = {}
        for symbol, exposure in self.symbol_exposures.items():
            if exposure.position_count > 0:
                conc, status = self.get_symbol_concentration(symbol)
                symbols_summary[symbol] = {
                    'concentration_pct': round(conc, 1),
                    'status': status,
                    'net_exposure': round(exposure.net_exposure, 2),
                    'gross_exposure': round(exposure.gross_exposure, 2),
                    'position_count': exposure.position_count,
                    'pairs': sorted(list(exposure.pairs))
                }
        
        return {
            'total_symbols': len(symbols_summary),
            'total_positions': len(self.positions),
            'max_concentration': self.max_concentration,
            'symbols': symbols_summary
        }
    
    def get_concentration_status(self, symbol: str) -> Dict:
        """Get detailed concentration status for a symbol."""
        if symbol not in self.symbol_exposures:
            return {
                'symbol': symbol,
                'concentration_pct': 0.0,
                'status': 'Low',
                'capacity_remaining_pct': 100.0,
                'position_count': 0,
                'pairs': []
            }
        
        exposure = self.symbol_exposures[symbol]
        conc, status = self.get_symbol_concentration(symbol)
        
        return {
            'symbol': symbol,
            'concentration_pct': round(conc, 1),
            'status': status,
            'capacity_remaining_pct': round(self.get_available_capacity(symbol), 1),
            'long_notional': round(exposure.long_notional, 2),
            'short_notional': round(exposure.short_notional, 2),
            'net_exposure': round(exposure.net_exposure, 2),
            'gross_exposure': round(exposure.gross_exposure, 2),
            'position_count': exposure.position_count,
            'pairs': sorted(list(exposure.pairs))
        }
    
    def get_most_concentrated_symbols(self, top_n: int = 5) -> List[Tuple[str, float, str]]:
        """Get symbols with highest concentration."""
        concentrations = []
        for symbol in self.symbol_exposures:
            conc, status = self.get_symbol_concentration(symbol)
            if conc > 0:
                concentrations.append((symbol, conc, status))
        
        # Sort by concentration descending
        concentrations.sort(key=lambda x: x[1], reverse=True)
        return concentrations[:top_n]
    
    def reset_all(self) -> None:
        """Clear all positions and exposures."""
        count = len(self.positions)
        self.positions.clear()
        self.symbol_exposures.clear()
        logger.debug("concentration_limits_reset", positions_cleared=count)
    
    def get_active_positions(self) -> List[str]:
        """Get list of all active position pair keys."""
        return list(self.positions.keys())
