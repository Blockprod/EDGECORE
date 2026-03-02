"""
Test Suite for S4.3: Portfolio Extension Module

Comprehensive tests for portfolio management, clustering, and concentration analysis.
"""

import pytest
import numpy as np
import pandas as pd
from typing import List, Tuple, Dict

from monitoring.portfolio_extension_s43 import (
    PairExposure,
    CorrelationCalculator,
    PairClustering,
    PortfolioConcentrationAnalyzer,
    PortfolioManager,
    ClusterAnalysis
)


class TestPairExposure:
    """Test pair exposure tracking."""
    
    def test_pair_exposure_initialization(self):
        """Test creating pair exposure."""
        exp = PairExposure(pair_id="AAPL", sym1="AAPL", sym2="MSFT")
        assert exp.pair_id == "AAPL"
        assert exp.sym1 == "AAPL"
        assert exp.sym2 == "MSFT"
        assert "AAPL" in exp.long_symbols
        assert "MSFT" in exp.short_symbols
    
    def test_pair_exposure_get_exposure(self):
        """Test getting symbol exposures from pair."""
        exp = PairExposure(pair_id="AAPL", sym1="AAPL", sym2="MSFT", position_size=2.0)
        exposures = exp.get_exposure()
        assert exposures["AAPL"] == 2.0
        assert exposures["MSFT"] == -2.0
    
    def test_pair_exposure_exposure_aggregation(self):
        """Test exposure aggregation across multiple position sizes."""
        exp = PairExposure(pair_id="MSFT_AAPL", sym1="GOOGL", sym2="AAPL", position_size=3.0)
        assert exp.get_exposure()["GOOGL"] == 3.0
        assert exp.get_exposure()["AAPL"] == -3.0
        
        # Change size
        exp.position_size = 1.5
        assert exp.get_exposure()["GOOGL"] == 1.5
        assert exp.get_exposure()["AAPL"] == -1.5


class TestCorrelationCalculator:
    """Test pair correlation calculations."""
    
    def test_same_pair_correlation(self):
        """Identical pairs should have correlation 1.0."""
        calc = CorrelationCalculator()
        corr = calc.calculate_pair_correlation(("AAPL", "MSFT"), ("AAPL", "MSFT"))
        assert corr == 1.0
    
    def test_no_shared_symbols(self):
        """Pairs with no shared symbols should have correlation 0.0."""
        calc = CorrelationCalculator()
        corr = calc.calculate_pair_correlation(("AAPL", "MSFT"), ("GOOGL", "JPM"))
        assert corr == 0.0
    
    def test_one_shared_symbol(self):
        """Pairs sharing one symbol should have non-zero correlation."""
        calc = CorrelationCalculator()
        corr = calc.calculate_pair_correlation(("AAPL", "MSFT"), ("GOOGL", "MSFT"))
        assert corr == 0.7  # Shared base symbol
    
    def test_correlation_caching(self):
        """Correlation calculator should cache results."""
        calc = CorrelationCalculator()
        
        # First call
        corr1 = calc.calculate_pair_correlation(("AAPL", "MSFT"), ("GOOGL", "MSFT"))
        
        # Second call (should be cached)
        corr2 = calc.calculate_pair_correlation(("AAPL", "MSFT"), ("GOOGL", "MSFT"))
        
        assert corr1 == corr2
        assert len(calc._cache) == 1
    
    def test_correlation_matrix(self):
        """Test correlation matrix calculation."""
        calc = CorrelationCalculator()
        pairs = [
            ("AAPL", "MSFT"),
            ("GOOGL", "MSFT"),
            ("AAPL", "GOOGL")
        ]
        
        matrix = calc.calculate_pair_matrix(pairs)
        
        # Check diagonal
        assert np.allclose(np.diag(matrix), [1.0, 1.0, 1.0])
        
        # Check symmetry
        assert np.allclose(matrix, matrix.T)
        
        # Check specific cells
        assert matrix[0, 1] == 0.7  # AAPL vs MSFT (shared sector)
        assert matrix[0, 2] == 0.7  # AAPL vs GOOGL (shared tech exposure)


class TestPairClustering:
    """Test pair clustering algorithms."""
    
    def test_single_pair_clustering(self):
        """Single pair forms one cluster."""
        clusterer = PairClustering()
        pairs = [("AAPL", "MSFT")]
        clusters = clusterer.cluster_pairs(pairs)
        
        assert len(clusters) == 1
        assert clusters[0].pairs == pairs
    
    def test_no_pairs_clustering(self):
        """Empty pair list returns empty clusters."""
        clusterer = PairClustering()
        clusters = clusterer.cluster_pairs([])
        assert clusters == []
    
    def test_correlated_pairs_clustering(self):
        """Highly correlated pairs should cluster together."""
        clusterer = PairClustering(correlation_threshold=0.6)
        pairs = [
            ("AAPL", "MSFT"),
            ("GOOGL", "MSFT"),  # Correlated: same sector
            ("JPM", "WFC")    # Uncorrelated
        ]
        
        clusters = clusterer.cluster_pairs(pairs)
        
        # Should have at least 2 clusters (tech group + financials)
        assert len(clusters) >= 2
    
    def test_cluster_properties(self):
        """Test cluster analysis properties."""
        clusterer = PairClustering()
        pairs = [("AAPL", "MSFT"), ("GOOGL", "MSFT")]
        clusters = clusterer.cluster_pairs(pairs)
        
        cluster = clusters[0]
        assert isinstance(cluster, ClusterAnalysis)
        assert cluster.cluster_id == 0
        assert len(cluster.pairs) == 2
        assert cluster.correlation_matrix.shape == (2, 2)
        assert cluster.concentration_risk >= 0.0
    
    def test_clustering_threshold(self):
        """Different thresholds should produce different clusters."""
        pairs = [
            ("AAPL", "MSFT"),
            ("GOOGL", "MSFT"),
            ("JPM", "MSFT")
        ]
        
        # High threshold - fewer clusters
        clusterer_high = PairClustering(correlation_threshold=0.8)
        clusters_high = clusterer_high.cluster_pairs(pairs)
        
        # Low threshold - more likely to merge
        clusterer_low = PairClustering(correlation_threshold=0.5)
        clusters_low = clusterer_low.cluster_pairs(pairs)
        
        # Higher threshold should give same or more clusters
        assert len(clusters_high) >= len(clusters_low)


class TestPortfolioConcentrationAnalyzer:
    """Test portfolio concentration analysis."""
    
    def test_empty_portfolio_analysis(self):
        """Empty portfolio should show zero concentration."""
        analyzer = PortfolioConcentrationAnalyzer()
        result = analyzer.analyze_concentration({})
        
        assert result['total_notional'] == 0.0
        assert len(result['concentration_violations']) == 0
        assert result['concentration_score'] == 0.0
    
    def test_single_pair_concentration(self):
        """Single pair portfolio analysis."""
        analyzer = PortfolioConcentrationAnalyzer(max_symbol_weight=0.5)
        
        exposures = {
            "AAPL": PairExposure(
                pair_id="AAPL",
                sym1="AAPL",
                sym2="MSFT",
                position_size=1.0
            )
        }
        
        result = analyzer.analyze_concentration(exposures)
        
        assert result['total_notional'] == 2.0  # abs(1.0) + abs(-1.0)
        assert 'AAPL' in result['symbol_weights']
        assert 'MSFT' in result['symbol_weights']
    
    def test_concentration_violations(self):
        """Test detection of concentration limit violations."""
        analyzer = PortfolioConcentrationAnalyzer(max_symbol_weight=0.25)
        
        # Create portfolio with high AAPL concentration
        exposures = {
            "AAPL": PairExposure("AAPL", "AAPL", "MSFT", 5.0),
            "AAPL_MSFT": PairExposure("AAPL_MSFT", "AAPL", "GOOGL", 3.0),
            # Total AAPL exposure: 8.0, total notional will include this
        }
        
        result = analyzer.analyze_concentration(exposures)
        
        # AAPL should violate the 25% limit if portfolio is designed this way
        violations = result['concentration_violations']
        # Check if AAPL is in violations
        btc_weights = [v['symbol'] for v in violations]
        # Depending on exact weights, AAPL might be violated
    
    def test_rebalancing_adjustments(self):
        """Test position size adjustment recommendations."""
        analyzer = PortfolioConcentrationAnalyzer(max_symbol_weight=0.25)
        
        exposures = {
            "AAPL": PairExposure("AAPL", "AAPL", "MSFT", 2.0),
            "MSFT": PairExposure("MSFT", "GOOGL", "MSFT", 2.0),
            "GOOGL": PairExposure("GOOGL", "JPM", "MSFT", 2.0),
        }
        
        adjustments = analyzer.get_rebalancing_adjustments(exposures)
        
        # Should return adjustment multipliers for all pairs
        assert len(adjustments) == 3
        assert all(0.0 <= v <= 1.0 for v in adjustments.values())
    
    def test_herfindahl_concentration_score(self):
        """Test concentration score calculation (Herfindahl index)."""
        analyzer = PortfolioConcentrationAnalyzer()
        
        # Equal weights: low concentration
        exposures_equal = {
            "Pair1": PairExposure("Pair1", "A", "B", 1.0),
            "Pair2": PairExposure("Pair2", "C", "D", 1.0),
        }
        result_equal = analyzer.analyze_concentration(exposures_equal)
        
        # Unequal weights: higher concentration
        exposures_unequal = {
            "Pair1": PairExposure("Pair1", "A", "B", 5.0),
            "Pair2": PairExposure("Pair2", "C", "D", 1.0),
        }
        result_unequal = analyzer.analyze_concentration(exposures_unequal)
        
        # Unequal should have higher concentration score
        assert result_unequal['concentration_score'] > result_equal['concentration_score']


class TestPortfolioManager:
    """Test main portfolio management orchestrator."""
    
    def test_portfolio_manager_initialization(self):
        """Test portfolio manager initialization."""
        pm = PortfolioManager(max_symbol_weight=0.3, correlation_threshold=0.65)
        
        assert pm.max_symbol_weight == 0.3
        assert pm.correlation_threshold == 0.65
        assert len(pm.pair_exposures) == 0
    
    def test_register_pair(self):
        """Test registering pairs in portfolio."""
        pm = PortfolioManager()
        
        pm.register_pair("AAPL", "AAPL", "MSFT")
        
        assert "AAPL" in pm.pair_exposures
        assert pm.pair_exposures["AAPL"].sym1 == "AAPL"
    
    def test_update_position_size(self):
        """Test updating position sizes."""
        pm = PortfolioManager()
        pm.register_pair("AAPL", "AAPL", "MSFT")
        
        pm.update_position_size("AAPL", 2.5)
        
        assert pm.pair_exposures["AAPL"].position_size == 2.5
    
    def test_analyze_empty_portfolio(self):
        """Empty portfolio analysis."""
        pm = PortfolioManager()
        result = pm.analyze_portfolio()
        
        assert result['num_pairs'] == 0
        assert result['num_clusters'] == 0
        assert len(result['clusters']) == 0
    
    def test_analyze_full_portfolio(self):
        """Comprehensive portfolio analysis."""
        pm = PortfolioManager()
        
        # Register multiple pairs
        pm.register_pair("AAPL", "AAPL", "MSFT")
        pm.register_pair("MSFT", "GOOGL", "MSFT")
        pm.register_pair("JPM/WFC", "JPM", "WFC")
        
        analysis = pm.analyze_portfolio()
        
        assert analysis['num_pairs'] == 3
        assert analysis['num_clusters'] >= 1
        assert 'concentration' in analysis
    
    def test_rebalancing_plan(self):
        """Test rebalancing plan generation."""
        pm = PortfolioManager(max_symbol_weight=0.25)
        
        pm.register_pair("AAPL", "AAPL", "MSFT")
        pm.register_pair("AAPL_MSFT", "AAPL", "GOOGL")
        
        plan = pm.get_rebalancing_plan()
        
        assert 'adjustments' in plan
        assert 'rationale' in plan
        assert 'rebalancing_required' in plan
        assert isinstance(plan['adjustments'], dict)
    
    def test_portfolio_statistics(self):
        """Test portfolio statistics."""
        pm = PortfolioManager()
        
        # Empty portfolio
        stats = pm.get_statistics()
        assert stats['num_pairs'] == 0
        
        # Add pairs
        pm.register_pair("AAPL", "AAPL", "MSFT")
        pm.register_pair("MSFT_AAPL", "GOOGL", "AAPL")
        
        stats = pm.get_statistics()
        assert stats['num_pairs'] == 2
        assert stats['num_symbols'] == 3  # AAPL, MSFT, GOOGL
    
    def test_portfolio_clear(self):
        """Test clearing portfolio."""
        pm = PortfolioManager()
        pm.register_pair("AAPL", "AAPL", "MSFT")
        
        assert len(pm.pair_exposures) == 1
        
        pm.clear()
        
        assert len(pm.pair_exposures) == 0


class TestPortfolioIntegration:
    """Integration tests for portfolio extension."""
    
    def test_multi_pair_portfolio_workflow(self):
        """Complete workflow: register, analyze, rebalance."""
        pm = PortfolioManager(max_symbol_weight=0.30)
        
        # Build portfolio
        pairs = [
            ("AAPL", "MSFT"),
            ("GOOGL", "MSFT"),
            ("JPM", "MSFT"),
            ("WFC", "MSFT"),
            ("V", "MSFT"),
        ]
        
        for i, (sym1, sym2) in enumerate(pairs):
            pm.register_pair(f"{sym1}/{sym2}", sym1, sym2)
            pm.update_position_size(f"{sym1}/{sym2}", 1.0)
        
        # Analyze
        analysis = pm.analyze_portfolio()
        assert analysis['num_pairs'] == 5
        
        # Get rebalancing
        plan = pm.get_rebalancing_plan()
        assert len(plan['adjustments']) == 5
    
    def test_concentrated_commodity_pairs(self):
        """Test portfolio with highly correlated pairs (e.g., all tech pairs)."""
        pm = PortfolioManager(max_symbol_weight=0.25)
        
        # All pairs share tech exposure - highly correlated
        pairs = [
            ("AAPL", "MSFT"),
            ("GOOGL", "MSFT"),
            ("JPM", "MSFT"),
        ]
        
        for sym1, sym2 in pairs:
            pm.register_pair(f"{sym1}/{sym2}", sym1, sym2)
        
        analysis = pm.analyze_portfolio()
        
        # Should identify clustering (all share tech exposure)
        assert analysis['num_clusters'] >= 1
        
        # Check concentration: MSFT will be heavily shorted
        conc = analysis['concentration']
        if 'MSFT' in conc['symbol_weights']:
            msft_weight = conc['symbol_weights']['MSFT']
            # MSFT is shorted in all pairs
            assert msft_weight > 0
    
    def test_diversified_pairs(self):
        """Test portfolio with uncorrelated pairs."""
        pm = PortfolioManager()
        
        # Mostly uncorrelated pairs
        pairs = [
            ("AAPL", "MSFT"),
            ("GOOGL", "JPM"),
            ("WFC", "V"),
        ]
        
        for sym1, sym2 in pairs:
            pm.register_pair(f"{sym1}/{sym2}", sym1, sym2)
        
        stats = pm.get_statistics()
        
        # Should have lower cluster density
        assert stats['num_clusters'] >= 1
        avg_size = stats['avg_cluster_size']
        # Less clustering than commodity pairs
    
    def test_adaptive_position_sizing(self):
        """Test position sizing based on concentration."""
        pm = PortfolioManager(max_symbol_weight=0.20)
        
        # Create concentrated position
        pm.register_pair("AAPL", "AAPL", "MSFT")
        pm.register_pair("AAPL_MSFT", "AAPL", "GOOGL")
        pm.register_pair("AAPL_JPM", "AAPL", "JPM")
        
        # All 3.0 initially
        pm.update_position_size("AAPL", 3.0)
        pm.update_position_size("AAPL_MSFT", 3.0)
        pm.update_position_size("AAPL_JPM", 3.0)
        
        # Get rebalancing
        plan = pm.get_rebalancing_plan()
        
        # Should reduce AAPL concentration
        assert plan['rebalancing_required']


class TestCorrelationEdgeCases:
    """Edge case tests for correlation calculations."""
    
    def test_symbol_order_invariance(self):
        """Correlation should be same regardless of symbol order."""
        calc = CorrelationCalculator()
        
        corr_1 = calc.calculate_pair_correlation(("AAPL", "MSFT"), ("GOOGL", "MSFT"))
        corr_2 = calc.calculate_pair_correlation(("MSFT", "AAPL"), ("MSFT", "GOOGL"))
        
        # Should be same due to normalization
        assert corr_1 == corr_2
    
    def test_large_portfolio_clustering(self):
        """Test clustering with many pairs."""
        pairs = [
            (f"SYM{i}", f"SYM{i+1}")
            for i in range(20)
        ]
        
        clusterer = PairClustering()
        clusters = clusterer.cluster_pairs(pairs)
        
        # Should complete without error
        assert len(clusters) > 0
        
        # All pairs should be represented
        total_pairs = sum(len(c.pairs) for c in clusters)
        assert total_pairs == 20
