"""
S4.3: Portfolio Extension Module

Advanced multi-pair portfolio management with correlation clustering and risk aggregation.

Features:
- Correlation-based pair clustering (identify highly-correlated pair groups)
- Cross-symbol concentration detection (avoid portfolio concentration via shared symbols)
- Portfolio-level risk management (aggregate risk across pairs)
- Position sizing optimization (dynamically adjust sizes to manage portfolio risk)
- Symbol exposure tracking (percent notional per symbol)
"""

from collections import defaultdict
from dataclasses import dataclass, field
from threading import RLock
from typing import Any

import numpy as np
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class PairExposure:
    """Track exposure of a pair to underlying symbols."""

    pair_id: str
    sym1: str
    sym2: str
    position_size: float = 1.0  # Base position size
    long_symbols: set[str] = field(default_factory=set)  # Symbols we're long
    short_symbols: set[str] = field(default_factory=set)  # Symbols we're short

    def __post_init__(self):
        """Initialize symbol sets based on pair type."""
        # In pair trading: typically we go spread-neutral (long asset, short base)
        # E.g., in AAPL_MSFT pair: long 1 AAPL, short hedge-ratio * MSFT
        self.long_symbols.add(self.sym1)
        self.short_symbols.add(self.sym2)

    def get_exposure(self) -> dict[str, float]:
        """Get net symbol exposures (positive for long, negative for short)."""
        exposure = {}
        for sym in self.long_symbols:
            exposure[sym] = exposure.get(sym, 0.0) + self.position_size
        for sym in self.short_symbols:
            exposure[sym] = exposure.get(sym, 0.0) - self.position_size
        return exposure


@dataclass
class ClusterAnalysis:
    """Result of portfolio correlation clustering."""

    cluster_id: int
    pairs: list[tuple[str, str]]
    correlation_matrix: np.ndarray
    centroid: np.ndarray
    members_correlation: dict[str, float]  # Member -> avg correlation with others
    concentration_risk: float  # 0.0 = diversified, 1.0 = fully concentrated


class CorrelationCalculator:
    """Calculate correlations between pairs based on shared symbols."""

    def __init__(self):
        """Initialize correlation calculator."""
        self._cache: dict[tuple[tuple[str, ...], ...], float] = {}
        self._lock = RLock()

    def calculate_pair_correlation(self, pair1: tuple[str, str], pair2: tuple[str, str]) -> float:
        """
        Calculate correlation between two pairs based on shared symbols.

        Logic:
        - If pairs share both symbols (same pair): correlation = 1.0
        - If pairs share one symbol: correlation based on how much exposure overlaps
        - If pairs share no symbols: correlation = 0.0

        Args:
            pair1: (sym1, sym2) for first pair
            pair2: (sym3, sym4) for second pair

        Returns:
            Correlation score between 0.0 and 1.0
        """
        # Normalize pair order for caching
        p1_norm = tuple(sorted(pair1))
        p2_norm = tuple(sorted(pair2))
        key = tuple(sorted([p1_norm, p2_norm]))

        with self._lock:
            if key in self._cache:
                return self._cache[key]

        # Count shared symbols
        symbols1 = set(pair1)
        symbols2 = set(pair2)
        shared = symbols1 & symbols2

        if len(shared) == 0:
            correlation = 0.0
        elif len(shared) == 2:
            # Same pair
            correlation = 1.0
        elif len(shared) == 1:
            # One symbol shared - correlation depends on position direction
            # For pair trading: AAPL vs MSFT both use USD
            # So they're positively correlated
            correlation = 0.7  # High correlation for shared base symbol
        else:
            correlation = 0.0

        with self._lock:
            self._cache[key] = correlation

        return correlation

    def calculate_pair_matrix(self, pairs: list[tuple[str, str]]) -> np.ndarray:
        """
        Calculate correlation matrix for list of pairs.

        Args:
            pairs: List of (sym1, sym2) tuples

        Returns:
            NxN correlation matrix
        """
        n = len(pairs)
        matrix = np.zeros((n, n))

        for i in range(n):
            for j in range(n):
                if i == j:
                    matrix[i, j] = 1.0
                else:
                    corr = self.calculate_pair_correlation(pairs[i], pairs[j])
                    matrix[i, j] = corr

        return matrix


class PairClustering:
    """Cluster pairs based on correlation structure."""

    def __init__(self, correlation_threshold: float = 0.6):
        """
        Initialize pair clustering.

        Args:
            correlation_threshold: Min correlation to group pairs together
        """
        self.correlation_threshold = correlation_threshold
        self.calculator = CorrelationCalculator()

    def cluster_pairs(self, pairs: list[tuple[str, str]]) -> list[ClusterAnalysis]:
        """
        Cluster pairs into groups based on correlation.

        Uses simple greedy clustering:
        1. Start with highest correlation pair
        2. Add pairs correlated to cluster
        3. Move to next unclustered pair

        Args:
            pairs: List of (sym1, sym2) tuples

        Returns:
            List of ClusterAnalysis objects
        """
        if not pairs:
            return []

        # Calculate correlation matrix
        corr_matrix = self.calculator.calculate_pair_matrix(pairs)

        # Greedy clustering
        unclustered = set(range(len(pairs)))
        clusters = []
        cluster_id = 0

        while unclustered:
            # Start with highest unclustered index
            seed = max(unclustered)
            cluster_indices = {seed}
            queue = [seed]
            unclustered.remove(seed)

            # Find all similar pairs
            while queue:
                current = queue.pop(0)

                for other in list(unclustered):
                    if corr_matrix[current, other] >= self.correlation_threshold:
                        cluster_indices.add(other)
                        queue.append(other)
                        unclustered.remove(other)

            # Create cluster
            cluster_pairs = [pairs[i] for i in cluster_indices]
            cluster_corr_matrix = corr_matrix[np.ix_(list(cluster_indices), list(cluster_indices))]

            cluster = ClusterAnalysis(
                cluster_id=cluster_id,
                pairs=cluster_pairs,
                correlation_matrix=cluster_corr_matrix,
                centroid=np.mean(cluster_corr_matrix, axis=0),
                members_correlation={
                    str(pairs[i]): float(np.mean(cluster_corr_matrix[j])) for j, i in enumerate(cluster_indices)
                },
                concentration_risk=float(np.mean(cluster_corr_matrix)),
            )

            clusters.append(cluster)
            cluster_id += 1

        return clusters


class PortfolioConcentrationAnalyzer:
    """Analyze portfolio concentration risk across symbols."""

    def __init__(self, max_symbol_weight: float = 0.25):
        """
        Initialize concentration analyzer.

        Args:
            max_symbol_weight: Max % of portfolio notional per symbol (0.25 = 25%)
        """
        self.max_symbol_weight = max_symbol_weight

    def analyze_concentration(self, pair_exposures: dict[str, PairExposure]) -> dict[str, Any]:
        """
        Analyze portfolio-level concentration risk.

        Args:
            pair_exposures: Dict mapping pair_id -> PairExposure

        Returns:
            Dict with concentration metrics
        """
        # Aggregate exposures
        total_exposure: dict[str, float] = defaultdict(float)
        total_notional = 0.0

        for _pair_id, exposure in pair_exposures.items():
            exp_dict = exposure.get_exposure()
            for sym, exp_amt in exp_dict.items():
                total_exposure[sym] += abs(exp_amt)
            total_notional += sum(abs(v) for v in exp_dict.values())

        if total_notional == 0:
            return {
                "total_notional": 0.0,
                "symbol_weights": {},
                "concentration_violations": [],
                "concentration_score": 0.0,
            }

        # Calculate weights
        symbol_weights = {sym: abs(exp) / total_notional for sym, exp in total_exposure.items()}

        # Find violations
        violations = [
            {"symbol": sym, "weight": weight, "max_allowed": self.max_symbol_weight}
            for sym, weight in symbol_weights.items()
            if weight > self.max_symbol_weight
        ]

        # Concentration score: Herfindahl index
        herfindahl = sum(w**2 for w in symbol_weights.values())
        concentration_score = herfindahl / len(symbol_weights) if symbol_weights else 0.0

        return {
            "total_notional": total_notional,
            "symbol_weights": symbol_weights,
            "concentration_violations": violations,
            "concentration_score": concentration_score,
            "num_violations": len(violations),
            "top_symbols": sorted(symbol_weights.items(), key=lambda x: x[1], reverse=True)[:5],
        }

    def get_rebalancing_adjustments(self, pair_exposures: dict[str, PairExposure]) -> dict[str, float]:
        """
        Calculate position size adjustments to fix concentration violations.

        Args:
            pair_exposures: Dict mapping pair_id -> PairExposure

        Returns:
            Dict mapping pair_id -> adjustment_multiplier (0.0-1.0)
        """
        conc = self.analyze_concentration(pair_exposures)

        if not conc["concentration_violations"]:
            # No violations - return neutral multipliers
            return {pair_id: 1.0 for pair_id in pair_exposures.keys()}

        # Find pairs that contribute most to violations
        adjustments = {}
        violation_symbols = {v["symbol"] for v in conc["concentration_violations"]}

        for pair_id, exposure in pair_exposures.items():
            exp_dict = exposure.get_exposure()

            # Check if this pair contributes to violations
            contributes_to_violation = any(sym in violation_symbols for sym in exp_dict.keys())

            if contributes_to_violation:
                # Reduce this pair by 50%
                adjustments[pair_id] = 0.5
            else:
                # Keep as is
                adjustments[pair_id] = 1.0

        return adjustments


class PortfolioManager:
    """Main portfolio management orchestrator."""

    def __init__(self, max_symbol_weight: float = 0.25, correlation_threshold: float = 0.6):
        """
        Initialize portfolio manager.

        Args:
            max_symbol_weight: Max portfolio weight per symbol
            correlation_threshold: Min correlation for clustering
        """
        self.max_symbol_weight = max_symbol_weight
        self.correlation_threshold = correlation_threshold

        self.pair_exposures: dict[str, PairExposure] = {}
        self.clustering = PairClustering(correlation_threshold)
        self.concentration = PortfolioConcentrationAnalyzer(max_symbol_weight)
        self._lock = RLock()

        logger.info(
            "portfolio_manager_initialized",
            max_symbol_weight=max_symbol_weight,
            correlation_threshold=correlation_threshold,
        )

    def register_pair(self, pair_id: str, sym1: str, sym2: str) -> None:
        """
        Register a trading pair in the portfolio.

        Args:
            pair_id: Unique identifier for pair (e.g., "AAPL_MSFT")
            sym1: First symbol
            sym2: Second symbol
        """
        with self._lock:
            if pair_id not in self.pair_exposures:
                self.pair_exposures[pair_id] = PairExposure(pair_id=pair_id, sym1=sym1, sym2=sym2)
                logger.info("pair_registered", pair_id=pair_id, sym1=sym1, sym2=sym2)

    def update_position_size(self, pair_id: str, size: float) -> None:
        """Update position size for a pair."""
        with self._lock:
            if pair_id in self.pair_exposures:
                self.pair_exposures[pair_id].position_size = size

    def analyze_portfolio(self) -> dict[str, Any]:
        """
        Comprehensive portfolio analysis.

        Returns:
            Dict with clustering, concentration, and risk metrics
        """
        with self._lock:
            if not self.pair_exposures:
                return {
                    "num_pairs": 0,
                    "num_clusters": 0,
                    "clusters": [],
                    "concentration": {},
                    "rebalancing_needed": False,
                }

            # Get pairs
            pairs = [(exp.sym1, exp.sym2) for exp in self.pair_exposures.values()]

            # Perform clustering
            clusters = self.clustering.cluster_pairs(pairs)

            # Analyze concentration
            concentration = self.concentration.analyze_concentration(self.pair_exposures)

            return {
                "num_pairs": len(self.pair_exposures),
                "num_clusters": len(clusters),
                "clusters": clusters,
                "concentration": concentration,
                "rebalancing_needed": len(concentration["concentration_violations"]) > 0,
                "total_notional": concentration["total_notional"],
            }

    def get_rebalancing_plan(self) -> dict[str, Any]:
        """
        Get position sizing adjustments to manage portfolio risk.

        Returns:
            Dict with recommended adjustments and rationale
        """
        with self._lock:
            adjustments = self.concentration.get_rebalancing_adjustments(self.pair_exposures)

            analysis = self.analyze_portfolio()

            return {
                "adjustments": adjustments,
                "rationale": "Reduce positions that violate concentration limits",
                "analysis": analysis,
                "rebalancing_required": any(v < 1.0 for v in adjustments.values()),
            }

    def get_statistics(self) -> dict[str, Any]:
        """Get portfolio statistics."""
        with self._lock:
            if not self.pair_exposures:
                return {"num_pairs": 0, "num_symbols": 0, "avg_cluster_size": 0.0}

            pairs = [(exp.sym1, exp.sym2) for exp in self.pair_exposures.values()]

            clusters = self.clustering.cluster_pairs(pairs)

            all_symbols = set()
            for sym1, sym2 in pairs:
                all_symbols.add(sym1)
                all_symbols.add(sym2)

            avg_cluster_size = sum(len(c.pairs) for c in clusters) / len(clusters) if clusters else 0.0

            return {
                "num_pairs": len(self.pair_exposures),
                "num_symbols": len(all_symbols),
                "num_clusters": len(clusters),
                "avg_cluster_size": avg_cluster_size,
                "max_symbol_weight": self.max_symbol_weight,
                "correlation_threshold": self.correlation_threshold,
            }

    def clear(self) -> None:
        """Clear all registered pairs and reset portfolio."""
        with self._lock:
            self.pair_exposures.clear()
            logger.info("portfolio_cleared")
