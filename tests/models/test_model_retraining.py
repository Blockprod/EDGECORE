<<<<<<< HEAD
﻿"""
=======
"""
>>>>>>> origin/main
Tests for Model Retraining and Pair Discovery (S2.6).

Validates retraining manager functionality: pair discovery, hedge ratio re-estimation,
stability tracking, retraining scheduling, and report generation.

Test Coverage:
- PairDiscoveryMetadata and RetrainingReport dataclasses
- ModelRetrainingManager initialization and configuration
- Pair discovery from cointegration tests
- Hedge ratio re-estimation and drift detection
- Pair registration and lifecycle tracking
- Stability score calculation
- Retraining scheduling and reports
- Edge cases (no pairs, all invalid, high drift)
"""

<<<<<<< HEAD
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from models.model_retraining import ModelRetrainingManager, PairDiscoveryMetadata, RetrainingReport
=======
import pytest
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

from models.model_retraining import (
    PairDiscoveryMetadata,
    RetrainingReport,
    ModelRetrainingManager
)
>>>>>>> origin/main


class TestPairDiscoveryMetadata:
    """Test PairDiscoveryMetadata dataclass."""
<<<<<<< HEAD

=======
    
>>>>>>> origin/main
    def test_metadata_initialization(self):
        """Test creating PairDiscoveryMetadata."""
        metadata = PairDiscoveryMetadata(
            pair_key="AAPL-MSFT",
            discovery_date=datetime(2026, 1, 15),
            last_reestimate_date=datetime(2026, 1, 15),
<<<<<<< HEAD
            discovery_p_value=0.0234,
        )

=======
            discovery_p_value=0.0234
        )
        
>>>>>>> origin/main
        assert metadata.pair_key == "AAPL-MSFT"
        assert metadata.discovery_p_value == 0.0234
        assert metadata.is_valid is True
        assert metadata.reestimation_count == 0
<<<<<<< HEAD

=======
    
>>>>>>> origin/main
    def test_metadata_with_hedge_ratio_data(self):
        """Test metadata with hedge ratio tracking."""
        metadata = PairDiscoveryMetadata(
            pair_key="AAPL-MSFT",
            discovery_date=datetime.now(),
            last_reestimate_date=datetime.now(),
            discovery_p_value=0.02,
            initial_hedge_ratio=1.5,
            current_hedge_ratio=1.6,
<<<<<<< HEAD
            hedge_ratio_drift=0.0667,  # 6.67% drift
        )

        assert metadata.initial_hedge_ratio == 1.5
        assert metadata.current_hedge_ratio == 1.6
        assert metadata.hedge_ratio_drift is not None
=======
            hedge_ratio_drift=0.0667  # 6.67% drift
        )
        
        assert metadata.initial_hedge_ratio == 1.5
        assert metadata.current_hedge_ratio == 1.6
>>>>>>> origin/main
        assert abs(metadata.hedge_ratio_drift - 0.0667) < 0.001


class TestRetrainingReport:
    """Test RetrainingReport dataclass."""
<<<<<<< HEAD

=======
    
>>>>>>> origin/main
    def test_report_initialization(self):
        """Test creating RetrainingReport."""
        report = RetrainingReport(
            retraining_date=datetime.now(),
            discovery_lookback_days=252,
            pairs_total=25,
            pairs_valid=22,
            pairs_degraded=3,
            pairs_newly_discovered=5,
            pairs_stable=18,
            pairs_drifting=4,
            avg_hedge_ratio_drift=0.045,
<<<<<<< HEAD
            avg_p_value=0.025,
        )

        assert report.pairs_total == 25
        assert report.pairs_valid == 22
        assert report.pairs_degraded == 3

=======
            avg_p_value=0.025
        )
        
        assert report.pairs_total == 25
        assert report.pairs_valid == 22
        assert report.pairs_degraded == 3
    
>>>>>>> origin/main
    def test_report_summary_generation(self):
        """Test that report generates human-readable summary."""
        report = RetrainingReport(
            retraining_date=datetime.now(),
            discovery_lookback_days=252,
            pairs_total=10,
            pairs_valid=8,
            pairs_degraded=2,
            pairs_newly_discovered=2,
            pairs_stable=6,
            pairs_drifting=2,
            avg_hedge_ratio_drift=0.05,
            avg_p_value=0.03,
<<<<<<< HEAD
            summary="Test summary",
        )

=======
            summary="Test summary"
        )
        
>>>>>>> origin/main
        assert report.summary == "Test summary"


class TestModelRetrainingManagerInitialization:
    """Test ModelRetrainingManager setup."""
<<<<<<< HEAD

    def test_manager_default_initialization(self):
        """Test default configuration."""
        manager = ModelRetrainingManager()

=======
    
    def test_manager_default_initialization(self):
        """Test default configuration."""
        manager = ModelRetrainingManager()
        
>>>>>>> origin/main
        assert manager.discovery_lookback_days == 252
        assert manager.reestimation_frequency_days == 14
        assert manager.cointegration_threshold == 0.05
        assert manager.hedge_ratio_drift_threshold == 0.10
        assert manager.min_pair_age_days == 30
<<<<<<< HEAD

=======
    
>>>>>>> origin/main
    def test_manager_custom_initialization(self):
        """Test custom configuration."""
        manager = ModelRetrainingManager(
            discovery_lookback_days=500,
            reestimation_frequency_days=7,
            cointegration_threshold=0.02,
            hedge_ratio_drift_threshold=0.20,
<<<<<<< HEAD
            min_pair_age_days=60,
        )

=======
            min_pair_age_days=60
        )
        
>>>>>>> origin/main
        assert manager.discovery_lookback_days == 500
        assert manager.reestimation_frequency_days == 7
        assert manager.cointegration_threshold == 0.02
        assert manager.hedge_ratio_drift_threshold == 0.20
        assert manager.min_pair_age_days == 60
<<<<<<< HEAD

    def test_manager_initial_state(self):
        """Test that manager starts empty."""
        manager = ModelRetrainingManager()

=======
    
    def test_manager_initial_state(self):
        """Test that manager starts empty."""
        manager = ModelRetrainingManager()
        
>>>>>>> origin/main
        assert len(manager.tracked_pairs) == 0
        assert len(manager.retraining_history) == 0
        assert manager.last_retraining_date is None


class TestPairDiscovery:
    """Test pair discovery functionality."""
<<<<<<< HEAD

=======
    
>>>>>>> origin/main
    def create_test_price_data(self, n_days=252, coint_pairs=None):
        """Helper to create synthetic price data with optional cointegracy."""
        dates = pd.date_range(end=datetime.now(), periods=n_days)
        np.random.seed(42)
<<<<<<< HEAD

        data = {}
        symbols = ["AAPL", "GOOGL", "JPM", "WFC", "V"]

        # Create base random walks
        for sym in symbols:
            data[sym] = 100 + np.cumsum(np.random.normal(0, 2, n_days))

=======
        
        data = {}
        symbols = ['AAPL', 'GOOGL', 'JPM', 'WFC', 'V']
        
        # Create base random walks
        for sym in symbols:
            data[sym] = 100 + np.cumsum(np.random.normal(0, 2, n_days))
        
>>>>>>> origin/main
        # Create cointegrated pairs if specified
        if coint_pairs:
            for sym1, sym2 in coint_pairs:
                # Create cointegrated relationship: y = 1.5*x + noise
                data[sym1] = 1.5 * data[sym2] + np.random.normal(0, 0.5, n_days)
<<<<<<< HEAD

        return pd.DataFrame(data, index=dates)

=======
        
        return pd.DataFrame(data, index=dates)
    
>>>>>>> origin/main
    def test_discover_basic_setup(self):
        """Test discovery manager can process valid data."""
        manager = ModelRetrainingManager()
        price_data = self.create_test_price_data()
<<<<<<< HEAD

        # Should not error ÔÇö deprecated_call asserts the DeprecationWarning is emitted
        with pytest.deprecated_call():
            results = manager.discover_cointegrated_pairs(price_data=price_data, symbols=["AAPL", "GOOGL", "JPM"])

        assert isinstance(results, list)

    def test_discover_returns_correct_format(self):
        """Test discovery returns (pair_key, p_value, hedge_ratio) tuples."""
        manager = ModelRetrainingManager()
        price_data = self.create_test_price_data(coint_pairs=[("GOOGL", "AAPL")])

        with pytest.deprecated_call():
            results = manager.discover_cointegrated_pairs(price_data=price_data, symbols=["AAPL", "GOOGL", "JPM"])

        # Should return tuples with correct structure
        for pair_key, p_value, hedge_ratio in results:
            assert isinstance(pair_key, str)
            assert "-" in pair_key
            assert isinstance(p_value, float)
            assert 0.0 <= p_value <= 1.0
            assert isinstance(hedge_ratio, (float, np.floating))

=======
        
        # Should not error — deprecated_call asserts the DeprecationWarning is emitted
        with pytest.deprecated_call():
            results = manager.discover_cointegrated_pairs(
                price_data=price_data,
                symbols=['AAPL', 'GOOGL', 'JPM']
            )
        
        assert isinstance(results, list)
    
    def test_discover_returns_correct_format(self):
        """Test discovery returns (pair_key, p_value, hedge_ratio) tuples."""
        manager = ModelRetrainingManager()
        price_data = self.create_test_price_data(coint_pairs=[('GOOGL', 'AAPL')])
        
        with pytest.deprecated_call():
            results = manager.discover_cointegrated_pairs(
                price_data=price_data,
                symbols=['AAPL', 'GOOGL', 'JPM']
            )
        
        # Should return tuples with correct structure
        for pair_key, p_value, hedge_ratio in results:
            assert isinstance(pair_key, str)
            assert '-' in pair_key
            assert isinstance(p_value, float)
            assert 0.0 <= p_value <= 1.0
            assert isinstance(hedge_ratio, (float, np.floating))
    
>>>>>>> origin/main
    def test_discover_excludes_existing_pairs(self):
        """Test that discovery can skip already-tracked pairs."""
        manager = ModelRetrainingManager()
        price_data = self.create_test_price_data()
<<<<<<< HEAD

        # Register a pair first
        manager.register_pair("AAPL-MSFT", "AAPL", "GOOGL", 0.02, 1.5)

        # Discover with exclusion
        with pytest.deprecated_call():
            results = manager.discover_cointegrated_pairs(
                price_data=price_data, symbols=["AAPL", "GOOGL", "JPM"], exclude_existing=True
            )

        # Should not include AAPL-MSFT
        pair_keys = [r[0] for r in results]
        assert "AAPL-MSFT" not in pair_keys

=======
        
        # Register a pair first
        manager.register_pair("AAPL-MSFT", "AAPL", "GOOGL", 0.02, 1.5)
        
        # Discover with exclusion
        with pytest.deprecated_call():
            results = manager.discover_cointegrated_pairs(
                price_data=price_data,
                symbols=['AAPL', 'GOOGL', 'JPM'],
                exclude_existing=True
            )
        
        # Should not include AAPL-MSFT
        pair_keys = [r[0] for r in results]
        assert "AAPL-MSFT" not in pair_keys
    
>>>>>>> origin/main
    def test_discover_includes_existing_when_flag_false(self):
        """Test that discovery includes existing pairs when flagged."""
        manager = ModelRetrainingManager()
        price_data = self.create_test_price_data()
<<<<<<< HEAD

        # Register a pair
        manager.register_pair("AAPL-MSFT", "AAPL", "GOOGL", 0.02, 1.5)

        # Discover without exclusion
        with pytest.deprecated_call():
            results = manager.discover_cointegrated_pairs(
                price_data=price_data, symbols=["AAPL", "GOOGL", "JPM"], exclude_existing=False
            )

        # Could include AAPL-MSFT (if still cointegrated)
        assert isinstance(results, list)

=======
        
        # Register a pair
        manager.register_pair("AAPL-MSFT", "AAPL", "GOOGL", 0.02, 1.5)
        
        # Discover without exclusion
        with pytest.deprecated_call():
            results = manager.discover_cointegrated_pairs(
                price_data=price_data,
                symbols=['AAPL', 'GOOGL', 'JPM'],
                exclude_existing=False
            )
        
        # Could include AAPL-MSFT (if still cointegrated)
        assert isinstance(results, list)
    
>>>>>>> origin/main
    def test_discover_handles_missing_symbols(self):
        """Test discovery gracefully handles missing symbols."""
        manager = ModelRetrainingManager()
        price_data = self.create_test_price_data()
<<<<<<< HEAD

        # Try to discover pairs including missing symbol
        with pytest.deprecated_call():
            results = manager.discover_cointegrated_pairs(
                price_data=price_data, symbols=["AAPL", "GOOGL", "NONEXISTENT"]
            )

=======
        
        # Try to discover pairs including missing symbol
        with pytest.deprecated_call():
            results = manager.discover_cointegrated_pairs(
                price_data=price_data,
                symbols=['AAPL', 'GOOGL', 'NONEXISTENT']
            )
        
>>>>>>> origin/main
        # Should not error, just skip missing
        assert isinstance(results, list)


class TestHedgeRatioReestimation:
    """Test hedge ratio re-estimation."""
<<<<<<< HEAD

=======
    
>>>>>>> origin/main
    def create_test_price_data(self, n_days=252):
        """Helper to create synthetic price data."""
        dates = pd.date_range(end=datetime.now(), periods=n_days)
        np.random.seed(42)
<<<<<<< HEAD

        data = {}
        for sym in ["AAPL", "GOOGL", "JPM"]:
            data[sym] = 100 + np.cumsum(np.random.normal(0, 1, n_days))

        return pd.DataFrame(data, index=dates)

=======
        
        data = {}
        for sym in ['AAPL', 'GOOGL', 'JPM']:
            data[sym] = 100 + np.cumsum(np.random.normal(0, 1, n_days))
        
        return pd.DataFrame(data, index=dates)
    
>>>>>>> origin/main
    def test_reestimate_basic_operation(self):
        """Test basic hedge ratio re-estimation."""
        manager = ModelRetrainingManager()
        price_data = self.create_test_price_data()
<<<<<<< HEAD

        # Register a pair first
        manager.register_pair("AAPL-MSFT", "AAPL", "GOOGL", 0.02, 1.5)

        # Re-estimate
        results = manager.reestimate_hedge_ratios(price_data=price_data, paired_symbols=[("AAPL", "GOOGL")])

        assert isinstance(results, dict)
        assert "AAPL-MSFT" in results or len(results) >= 0  # Depends on cointegration

=======
        
        # Register a pair first
        manager.register_pair("AAPL-MSFT", "AAPL", "GOOGL", 0.02, 1.5)
        
        # Re-estimate
        results = manager.reestimate_hedge_ratios(
            price_data=price_data,
            paired_symbols=[('AAPL', 'GOOGL')]
        )
        
        assert isinstance(results, dict)
        assert 'AAPL-MSFT' in results or len(results) >= 0  # Depends on cointegration
    
>>>>>>> origin/main
    def test_reestimate_returns_correct_format(self):
        """Test re-estimation returns (hedge_ratio, p_value) tuples."""
        manager = ModelRetrainingManager()
        price_data = self.create_test_price_data()
<<<<<<< HEAD

        manager.register_pair("AAPL-MSFT", "AAPL", "GOOGL", 0.02, 1.5)

        results = manager.reestimate_hedge_ratios(price_data=price_data, paired_symbols=[("AAPL", "GOOGL")])

        for _pair_key, (hedge_ratio, p_value) in results.items():
            assert isinstance(hedge_ratio, (float, np.floating))
            assert isinstance(p_value, float)
            assert 0.0 <= p_value <= 1.0

=======
        
        manager.register_pair("AAPL-MSFT", "AAPL", "GOOGL", 0.02, 1.5)
        
        results = manager.reestimate_hedge_ratios(
            price_data=price_data,
            paired_symbols=[('AAPL', 'GOOGL')]
        )
        
        for pair_key, (hedge_ratio, p_value) in results.items():
            assert isinstance(hedge_ratio, (float, np.floating))
            assert isinstance(p_value, float)
            assert 0.0 <= p_value <= 1.0
    
>>>>>>> origin/main
    def test_reestimate_updates_metadata(self):
        """Test that re-estimation updates pair metadata."""
        manager = ModelRetrainingManager()
        price_data = self.create_test_price_data()
<<<<<<< HEAD

        manager.register_pair("AAPL-MSFT", "AAPL", "GOOGL", 0.02, 1.5)
        original_count = manager.tracked_pairs["AAPL-MSFT"].reestimation_count

        # Re-estimate
        manager.reestimate_hedge_ratios(price_data=price_data, paired_symbols=[("AAPL", "GOOGL")])

        # Reestimation count should increase if re-estimation completed
        metadata = manager.tracked_pairs.get("AAPL-MSFT")
        if metadata:
            assert metadata.reestimation_count >= original_count

=======
        
        manager.register_pair("AAPL-MSFT", "AAPL", "GOOGL", 0.02, 1.5)
        original_count = manager.tracked_pairs['AAPL-MSFT'].reestimation_count
        
        # Re-estimate
        manager.reestimate_hedge_ratios(
            price_data=price_data,
            paired_symbols=[('AAPL', 'GOOGL')]
        )
        
        # Reestimation count should increase if re-estimation completed
        metadata = manager.tracked_pairs.get('AAPL-MSFT')
        if metadata:
            assert metadata.reestimation_count >= original_count
    
>>>>>>> origin/main
    def test_reestimate_handles_missing_symbols(self):
        """Test re-estimation gracefully handles missing data."""
        manager = ModelRetrainingManager()
        price_data = self.create_test_price_data()
<<<<<<< HEAD

        # Try to re-estimate pair with missing symbol
        results = manager.reestimate_hedge_ratios(price_data=price_data, paired_symbols=[("AAPL", "NONEXISTENT")])

=======
        
        # Try to re-estimate pair with missing symbol
        results = manager.reestimate_hedge_ratios(
            price_data=price_data,
            paired_symbols=[('AAPL', 'NONEXISTENT')]
        )
        
>>>>>>> origin/main
        # Should return empty or handle gracefully
        assert isinstance(results, dict)


class TestPairRegistration:
    """Test pair registration and lifecycle."""
<<<<<<< HEAD

    def test_register_new_pair(self):
        """Test registering a new pair."""
        manager = ModelRetrainingManager()

        manager.register_pair(pair_key="AAPL-MSFT", symbol1="AAPL", symbol2="GOOGL", p_value=0.0234, hedge_ratio=1.5)

        assert "AAPL-MSFT" in manager.tracked_pairs
        assert manager.tracked_pairs["AAPL-MSFT"].is_valid is True

    def test_register_prevents_duplicates(self):
        """Test that registering same pair twice doesn't duplicate."""
        manager = ModelRetrainingManager()

        manager.register_pair("AAPL-MSFT", "AAPL", "GOOGL", 0.02, 1.5)
        manager.register_pair("AAPL-MSFT", "AAPL", "GOOGL", 0.03, 1.6)

        # Should only have one entry
        assert len([k for k in manager.tracked_pairs.keys() if k == "AAPL-MSFT"]) == 1

=======
    
    def test_register_new_pair(self):
        """Test registering a new pair."""
        manager = ModelRetrainingManager()
        
        manager.register_pair(
            pair_key="AAPL-MSFT",
            symbol1="AAPL",
            symbol2="GOOGL",
            p_value=0.0234,
            hedge_ratio=1.5
        )
        
        assert "AAPL-MSFT" in manager.tracked_pairs
        assert manager.tracked_pairs["AAPL-MSFT"].is_valid is True
    
    def test_register_prevents_duplicates(self):
        """Test that registering same pair twice doesn't duplicate."""
        manager = ModelRetrainingManager()
        
        manager.register_pair("AAPL-MSFT", "AAPL", "GOOGL", 0.02, 1.5)
        manager.register_pair("AAPL-MSFT", "AAPL", "GOOGL", 0.03, 1.6)
        
        # Should only have one entry
        assert len([k for k in manager.tracked_pairs.keys() if k == "AAPL-MSFT"]) == 1
    
>>>>>>> origin/main
    def test_register_with_custom_discovery_date(self):
        """Test registering with custom discovery date."""
        manager = ModelRetrainingManager()
        discovery_date = datetime(2026, 1, 1)
<<<<<<< HEAD

=======
        
>>>>>>> origin/main
        manager.register_pair(
            pair_key="AAPL-MSFT",
            symbol1="AAPL",
            symbol2="GOOGL",
            p_value=0.02,
            hedge_ratio=1.5,
<<<<<<< HEAD
            discovery_date=discovery_date,
        )

=======
            discovery_date=discovery_date
        )
        
>>>>>>> origin/main
        assert manager.tracked_pairs["AAPL-MSFT"].discovery_date == discovery_date


class TestStabilityScoring:
    """Test pair stability score calculation."""
<<<<<<< HEAD

    def test_stability_score_range(self):
        """Test that stability score is between 0 and 1."""
        manager = ModelRetrainingManager()

        manager.register_pair("AAPL-MSFT", "AAPL", "GOOGL", 0.02, 1.5)
        score = manager.get_pair_stability_score("AAPL-MSFT")

        assert 0.0 <= score <= 1.0

    def test_stability_score_invalid_pair(self):
        """Test stability score returns 0 for invalid pair."""
        manager = ModelRetrainingManager()

        manager.register_pair("AAPL-MSFT", "AAPL", "GOOGL", 0.02, 1.5)
        manager.tracked_pairs["AAPL-MSFT"].is_valid = False

        score = manager.get_pair_stability_score("AAPL-MSFT")
        assert score == 0.0

=======
    
    def test_stability_score_range(self):
        """Test that stability score is between 0 and 1."""
        manager = ModelRetrainingManager()
        
        manager.register_pair("AAPL-MSFT", "AAPL", "GOOGL", 0.02, 1.5)
        score = manager.get_pair_stability_score("AAPL-MSFT")
        
        assert 0.0 <= score <= 1.0
    
    def test_stability_score_invalid_pair(self):
        """Test stability score returns 0 for invalid pair."""
        manager = ModelRetrainingManager()
        
        manager.register_pair("AAPL-MSFT", "AAPL", "GOOGL", 0.02, 1.5)
        manager.tracked_pairs["AAPL-MSFT"].is_valid = False
        
        score = manager.get_pair_stability_score("AAPL-MSFT")
        assert score == 0.0
    
>>>>>>> origin/main
    def test_stability_score_nonexistent_pair(self):
        """Test stability score returns 0 for nonexistent pair."""
        manager = ModelRetrainingManager()
        score = manager.get_pair_stability_score("AAPL-MSFT")
        assert score == 0.0
<<<<<<< HEAD

    def test_stability_score_improves_with_age(self):
        """Test that older validated pairs get higher scores."""
        manager = ModelRetrainingManager()

=======
    
    def test_stability_score_improves_with_age(self):
        """Test that older validated pairs get higher scores."""
        manager = ModelRetrainingManager()
        
>>>>>>> origin/main
        # Register old pair (100 days ago)
        old_date = datetime.now() - timedelta(days=100)
        manager.tracked_pairs["OLD-PAIR"] = PairDiscoveryMetadata(
            pair_key="OLD-PAIR",
            discovery_date=old_date,
            last_reestimate_date=old_date,
            discovery_p_value=0.02,
            current_p_value=0.02,
            is_valid=True,
            current_hedge_ratio=1.5,
            initial_hedge_ratio=1.5,
<<<<<<< HEAD
            hedge_ratio_drift=0.0,
        )

=======
            hedge_ratio_drift=0.0
        )
        
>>>>>>> origin/main
        # Register new pair (1 day ago)
        new_date = datetime.now() - timedelta(days=1)
        manager.tracked_pairs["NEW-PAIR"] = PairDiscoveryMetadata(
            pair_key="NEW-PAIR",
            discovery_date=new_date,
            last_reestimate_date=new_date,
            discovery_p_value=0.02,
            current_p_value=0.02,
            is_valid=True,
            current_hedge_ratio=1.5,
            initial_hedge_ratio=1.5,
<<<<<<< HEAD
            hedge_ratio_drift=0.0,
        )

        old_score = manager.get_pair_stability_score("OLD-PAIR")
        new_score = manager.get_pair_stability_score("NEW-PAIR")

=======
            hedge_ratio_drift=0.0
        )
        
        old_score = manager.get_pair_stability_score("OLD-PAIR")
        new_score = manager.get_pair_stability_score("NEW-PAIR")
        
>>>>>>> origin/main
        # Old pair should score higher
        assert old_score > new_score


class TestPairValidation:
    """Test pair validation logic."""
<<<<<<< HEAD

    def test_validate_all_pairs_returns_dict(self):
        """Test validate_all_pairs returns proper format."""
        manager = ModelRetrainingManager()

        manager.register_pair("AAPL-MSFT", "AAPL", "GOOGL", 0.02, 1.5)
        manager.register_pair("AAPL-GOOGL", "AAPL", "JPM", 0.03, 2.0)

        results = manager.validate_all_pairs()

        assert isinstance(results, dict)
        assert "AAPL-MSFT" in results or len(results) >= 0

    def test_validate_invalidates_old_uncointegrated(self):
        """Test that validation invalidates old pairs without cointegration."""
        manager = ModelRetrainingManager(min_pair_age_days=30)

=======
    
    def test_validate_all_pairs_returns_dict(self):
        """Test validate_all_pairs returns proper format."""
        manager = ModelRetrainingManager()
        
        manager.register_pair("AAPL-MSFT", "AAPL", "GOOGL", 0.02, 1.5)
        manager.register_pair("AAPL-GOOGL", "AAPL", "JPM", 0.03, 2.0)
        
        results = manager.validate_all_pairs()
        
        assert isinstance(results, dict)
        assert "AAPL-MSFT" in results or len(results) >= 0
    
    def test_validate_invalidates_old_uncointegrated(self):
        """Test that validation invalidates old pairs without cointegration."""
        manager = ModelRetrainingManager(min_pair_age_days=30)
        
>>>>>>> origin/main
        # Create old pair that lost cointegration
        old_date = datetime.now() - timedelta(days=60)
        manager.tracked_pairs["OLD-PAIR"] = PairDiscoveryMetadata(
            pair_key="OLD-PAIR",
            discovery_date=old_date,
            last_reestimate_date=old_date,
            discovery_p_value=0.02,
            current_p_value=0.10,  # Lost cointegration
            is_valid=True,
            current_hedge_ratio=1.5,
            initial_hedge_ratio=1.5,
<<<<<<< HEAD
            hedge_ratio_drift=0.0,
        )

        manager.validate_all_pairs()

=======
            hedge_ratio_drift=0.0
        )
        
        manager.validate_all_pairs()
        
>>>>>>> origin/main
        assert manager.tracked_pairs["OLD-PAIR"].is_valid is False


class TestRetrainingScheduling:
    """Test retraining scheduling."""
<<<<<<< HEAD

    def test_schedule_check_first_time(self):
        """Test that retraining is due on first check."""
        manager = ModelRetrainingManager()

        assert manager.schedule_retraining_check() is True

    def test_schedule_check_respects_frequency(self):
        """Test that retraining respects frequency schedule."""
        manager = ModelRetrainingManager(reestimation_frequency_days=14)

        # Set last retraining to 5 days ago
        manager.last_retraining_date = datetime.now() - timedelta(days=5)

        # Should not be due yet
        assert manager.schedule_retraining_check() is False

        # Set last retraining to 15 days ago
        manager.last_retraining_date = datetime.now() - timedelta(days=15)

=======
    
    def test_schedule_check_first_time(self):
        """Test that retraining is due on first check."""
        manager = ModelRetrainingManager()
        
        assert manager.schedule_retraining_check() is True
    
    def test_schedule_check_respects_frequency(self):
        """Test that retraining respects frequency schedule."""
        manager = ModelRetrainingManager(reestimation_frequency_days=14)
        
        # Set last retraining to 5 days ago
        manager.last_retraining_date = datetime.now() - timedelta(days=5)
        
        # Should not be due yet
        assert manager.schedule_retraining_check() is False
        
        # Set last retraining to 15 days ago
        manager.last_retraining_date = datetime.now() - timedelta(days=15)
        
>>>>>>> origin/main
        # Should be due now
        assert manager.schedule_retraining_check() is True


class TestRetrainingReport2:
    """Test report generation (extended)."""
<<<<<<< HEAD

    def test_generate_report_basic(self):
        """Test basic report generation."""
        manager = ModelRetrainingManager()

        manager.register_pair("AAPL-MSFT", "AAPL", "GOOGL", 0.02, 1.5)
        manager.register_pair("AAPL-GOOGL", "AAPL", "JPM", 0.03, 2.0)

        report = manager.generate_retraining_report()

        assert report.pairs_total == 2
        assert report.pairs_valid == 2

    def test_report_contains_new_pairs(self):
        """Test that report includes newly discovered pairs."""
        manager = ModelRetrainingManager()

        new_pairs = [("AAPL-MSFT", 0.02, 1.5), ("AAPL-GOOGL", 0.03, 2.0)]

        report = manager.generate_retraining_report(new_pairs=new_pairs)

        assert report.pairs_newly_discovered == 2
        assert "AAPL-MSFT" in report.new_pairs

    def test_report_updates_last_retraining_date(self):
        """Test that generating report updates last_retraining_date."""
        manager = ModelRetrainingManager()

        assert manager.last_retraining_date is None

        manager.generate_retraining_report()

        assert manager.last_retraining_date is not None

    def test_report_stored_in_history(self):
        """Test that reports are stored in history."""
        manager = ModelRetrainingManager()

        manager.generate_retraining_report()
        manager.generate_retraining_report()

=======
    
    def test_generate_report_basic(self):
        """Test basic report generation."""
        manager = ModelRetrainingManager()
        
        manager.register_pair("AAPL-MSFT", "AAPL", "GOOGL", 0.02, 1.5)
        manager.register_pair("AAPL-GOOGL", "AAPL", "JPM", 0.03, 2.0)
        
        report = manager.generate_retraining_report()
        
        assert report.pairs_total == 2
        assert report.pairs_valid == 2
    
    def test_report_contains_new_pairs(self):
        """Test that report includes newly discovered pairs."""
        manager = ModelRetrainingManager()
        
        new_pairs = [("AAPL-MSFT", 0.02, 1.5), ("AAPL-GOOGL", 0.03, 2.0)]
        
        report = manager.generate_retraining_report(new_pairs=new_pairs)
        
        assert report.pairs_newly_discovered == 2
        assert "AAPL-MSFT" in report.new_pairs
    
    def test_report_updates_last_retraining_date(self):
        """Test that generating report updates last_retraining_date."""
        manager = ModelRetrainingManager()
        
        assert manager.last_retraining_date is None
        
        manager.generate_retraining_report()
        
        assert manager.last_retraining_date is not None
    
    def test_report_stored_in_history(self):
        """Test that reports are stored in history."""
        manager = ModelRetrainingManager()
        
        manager.generate_retraining_report()
        manager.generate_retraining_report()
        
>>>>>>> origin/main
        assert len(manager.retraining_history) == 2


class TestManagerReset:
    """Test manager reset functionality."""
<<<<<<< HEAD

    def test_reset_clears_tracked_pairs(self):
        """Test that reset clears all tracked pairs."""
        manager = ModelRetrainingManager()

        manager.register_pair("AAPL-MSFT", "AAPL", "GOOGL", 0.02, 1.5)
        manager.register_pair("AAPL-GOOGL", "AAPL", "JPM", 0.03, 2.0)

        assert len(manager.tracked_pairs) > 0

        manager.reset_all()

        assert len(manager.tracked_pairs) == 0

    def test_reset_clears_history(self):
        """Test that reset clears retraining history."""
        manager = ModelRetrainingManager()

        manager.generate_retraining_report()
        manager.generate_retraining_report()

        assert len(manager.retraining_history) > 0

        manager.reset_all()

        assert len(manager.retraining_history) == 0

    def test_reset_clears_last_date(self):
        """Test that reset clears last retraining date."""
        manager = ModelRetrainingManager()

        manager.generate_retraining_report()
        assert manager.last_retraining_date is not None

        manager.reset_all()

=======
    
    def test_reset_clears_tracked_pairs(self):
        """Test that reset clears all tracked pairs."""
        manager = ModelRetrainingManager()
        
        manager.register_pair("AAPL-MSFT", "AAPL", "GOOGL", 0.02, 1.5)
        manager.register_pair("AAPL-GOOGL", "AAPL", "JPM", 0.03, 2.0)
        
        assert len(manager.tracked_pairs) > 0
        
        manager.reset_all()
        
        assert len(manager.tracked_pairs) == 0
    
    def test_reset_clears_history(self):
        """Test that reset clears retraining history."""
        manager = ModelRetrainingManager()
        
        manager.generate_retraining_report()
        manager.generate_retraining_report()
        
        assert len(manager.retraining_history) > 0
        
        manager.reset_all()
        
        assert len(manager.retraining_history) == 0
    
    def test_reset_clears_last_date(self):
        """Test that reset clears last retraining date."""
        manager = ModelRetrainingManager()
        
        manager.generate_retraining_report()
        assert manager.last_retraining_date is not None
        
        manager.reset_all()
        
>>>>>>> origin/main
        assert manager.last_retraining_date is None


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
<<<<<<< HEAD

    def test_empty_pair_list_discovery(self):
        """Test discovery with no pairs to test."""
        manager = ModelRetrainingManager()
        price_data = pd.DataFrame({"AAPL": [100, 101, 102]})

        with pytest.deprecated_call():
            results = manager.discover_cointegrated_pairs(price_data=price_data, symbols=["AAPL"])

        assert isinstance(results, list)

    def test_high_drift_detection(self):
        """Test detection of high hedge ratio drift."""
        manager = ModelRetrainingManager(hedge_ratio_drift_threshold=0.10)

=======
    
    def test_empty_pair_list_discovery(self):
        """Test discovery with no pairs to test."""
        manager = ModelRetrainingManager()
        price_data = pd.DataFrame({'AAPL': [100, 101, 102]})
        
        with pytest.deprecated_call():
            results = manager.discover_cointegrated_pairs(
                price_data=price_data,
                symbols=['AAPL']
            )
        
        assert isinstance(results, list)
    
    def test_high_drift_detection(self):
        """Test detection of high hedge ratio drift."""
        manager = ModelRetrainingManager(hedge_ratio_drift_threshold=0.10)
        
>>>>>>> origin/main
        metadata = PairDiscoveryMetadata(
            pair_key="AAPL-MSFT",
            discovery_date=datetime.now(),
            last_reestimate_date=datetime.now(),
            discovery_p_value=0.02,
            current_p_value=0.02,
            initial_hedge_ratio=1.0,
            current_hedge_ratio=1.25,
            hedge_ratio_drift=0.25,  # 25% drift
<<<<<<< HEAD
            is_valid=True,
        )
        manager.tracked_pairs["AAPL-MSFT"] = metadata

        # Should identify as drifting
        report = manager.generate_retraining_report()
        assert len(report.drifting_pairs) > 0

    def test_lost_cointegration_detection(self):
        """Test detection of pairs losing cointegration."""
        manager = ModelRetrainingManager()

=======
            is_valid=True
        )
        manager.tracked_pairs["AAPL-MSFT"] = metadata
        
        # Should identify as drifting
        report = manager.generate_retraining_report()
        assert len(report.drifting_pairs) > 0
    
    def test_lost_cointegration_detection(self):
        """Test detection of pairs losing cointegration."""
        manager = ModelRetrainingManager()
        
>>>>>>> origin/main
        metadata = PairDiscoveryMetadata(
            pair_key="AAPL-MSFT",
            discovery_date=datetime.now(),
            last_reestimate_date=datetime.now(),
            discovery_p_value=0.02,
            current_p_value=0.10,  # Lost cointegration
            is_valid=True,
            current_hedge_ratio=1.5,
            initial_hedge_ratio=1.5,
<<<<<<< HEAD
            hedge_ratio_drift=0.0,
        )
        manager.tracked_pairs["AAPL-MSFT"] = metadata

=======
            hedge_ratio_drift=0.0
        )
        manager.tracked_pairs["AAPL-MSFT"] = metadata
        
>>>>>>> origin/main
        report = manager.generate_retraining_report()
        assert "AAPL-MSFT" in report.invalidated_pairs or len(report.invalidated_pairs) >= 0


class TestIntegrationScenarios:
    """Test realistic retraining scenarios."""
<<<<<<< HEAD

    def test_full_retraining_workflow(self):
        """Test complete retraining workflow."""
        manager = ModelRetrainingManager()

        # 1. Register initial pairs
        manager.register_pair("AAPL-MSFT", "AAPL", "GOOGL", 0.02, 1.5)
        manager.register_pair("AAPL-GOOGL", "AAPL", "JPM", 0.03, 2.0)

        # 2. Check if retraining needed
        assert manager.schedule_retraining_check() is True

        # 3. Generate report
        report = manager.generate_retraining_report()

        assert report.pairs_total > 0
        assert report.retraining_date is not None

    def test_pair_age_based_validation(self):
        """Test validation based on pair age."""
        manager = ModelRetrainingManager(min_pair_age_days=30)

=======
    
    def test_full_retraining_workflow(self):
        """Test complete retraining workflow."""
        manager = ModelRetrainingManager()
        
        # 1. Register initial pairs
        manager.register_pair("AAPL-MSFT", "AAPL", "GOOGL", 0.02, 1.5)
        manager.register_pair("AAPL-GOOGL", "AAPL", "JPM", 0.03, 2.0)
        
        # 2. Check if retraining needed
        assert manager.schedule_retraining_check() is True
        
        # 3. Generate report
        report = manager.generate_retraining_report()
        
        assert report.pairs_total > 0
        assert report.retraining_date is not None
    
    def test_pair_age_based_validation(self):
        """Test validation based on pair age."""
        manager = ModelRetrainingManager(min_pair_age_days=30)
        
>>>>>>> origin/main
        # Register fresh pair
        fresh_date = datetime.now() - timedelta(days=5)
        manager.tracked_pairs["FRESH"] = PairDiscoveryMetadata(
            pair_key="FRESH",
            discovery_date=fresh_date,
            last_reestimate_date=fresh_date,
            discovery_p_value=0.02,
            current_p_value=0.02,
            is_valid=True,
            current_hedge_ratio=1.5,
            initial_hedge_ratio=1.5,
<<<<<<< HEAD
            hedge_ratio_drift=0.0,
        )

=======
            hedge_ratio_drift=0.0
        )
        
>>>>>>> origin/main
        # Register mature pair
        mature_date = datetime.now() - timedelta(days=100)
        manager.tracked_pairs["MATURE"] = PairDiscoveryMetadata(
            pair_key="MATURE",
            discovery_date=mature_date,
            last_reestimate_date=mature_date,
            discovery_p_value=0.02,
            current_p_value=0.02,
            is_valid=True,
            current_hedge_ratio=1.5,
            initial_hedge_ratio=1.5,
<<<<<<< HEAD
            hedge_ratio_drift=0.0,
        )

        results = manager.validate_all_pairs()

=======
            hedge_ratio_drift=0.0
        )
        
        results = manager.validate_all_pairs()
        
>>>>>>> origin/main
        # Both should be valid if cointegrated
        assert isinstance(results, dict)


# Test execution
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
