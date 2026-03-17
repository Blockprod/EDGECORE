"""
Phase 4 Tests ÔÇö Signaux Avanc├®s & ML.

4.1  EarningsSurpriseSignal (PEAD)
4.2  OptionsFlowSignal
4.3  SentimentSignal
4.4  MLSignalCombiner (walk-forward)
"""

import numpy as np
import pandas as pd
import pytest


# =====================================================================
# 4.1 ÔÇö Earnings Surprise Signal
# =====================================================================
class TestEarningsSurpriseSignal:
    """Tests for signal_engine/earnings_signal.py"""

    def _make_prices(self, n=100, gap_at=50, gap_pct=0.05):
        """Create price data with a gap at a specific bar."""
        dates = pd.date_range("2024-01-01", periods=n, freq="B")
        np.random.seed(42)
        base = 100 + np.cumsum(np.random.randn(n) * 0.5)
        # Insert gap
        if gap_at is not None:
            base[gap_at:] += base[gap_at - 1] * gap_pct
        return pd.DataFrame({"SYM1": base, "SYM2": 100 + np.cumsum(np.random.randn(n) * 0.3)}, index=dates)

    def test_import(self):
        from signal_engine.earnings_signal import EarningsSurpriseSignal
        es = EarningsSurpriseSignal()
        assert es.gap_threshold == 0.03
        assert es.drift_window == 45

    def test_no_events_empty_df(self):
        from signal_engine.earnings_signal import EarningsSurpriseSignal
        es = EarningsSurpriseSignal()
        assert es.compute_score("A", "B") == 0.0

    def test_detect_gap(self):
        from signal_engine.earnings_signal import EarningsSurpriseSignal
        es = EarningsSurpriseSignal(gap_threshold=0.03)
        prices = self._make_prices(n=100, gap_at=50, gap_pct=0.06)
        # Process all bars up to and including the gap
        for i in range(3, 52):
            es.update(prices.iloc[:i+1])
        # Should detect at least one event for SYM1
        assert es.has_active_event("SYM1")

    def test_no_detect_small_gap(self):
        from signal_engine.earnings_signal import EarningsSurpriseSignal
        es = EarningsSurpriseSignal(gap_threshold=0.10)
        prices = self._make_prices(n=100, gap_at=50, gap_pct=0.03)
        for i in range(3, 55):
            es.update(prices.iloc[:i+1])
        assert not es.has_active_event("SYM1")

    def test_pair_score_range(self):
        from signal_engine.earnings_signal import EarningsSurpriseSignal
        es = EarningsSurpriseSignal(gap_threshold=0.03)
        prices = self._make_prices(n=100, gap_at=50, gap_pct=0.08)
        for i in range(3, 55):
            es.update(prices.iloc[:i+1])
        score = es.compute_score("SYM1", "SYM2")
        assert -1.0 <= score <= 1.0

    def test_drift_decay(self):
        from signal_engine.earnings_signal import EarningsSurpriseSignal
        es = EarningsSurpriseSignal(gap_threshold=0.02, drift_window=10)
        prices = self._make_prices(n=80, gap_at=30, gap_pct=0.06)
        # Process up to gap
        for i in range(3, 35):
            es.update(prices.iloc[:i+1])
        score_early = es._symbol_drift_score("SYM1")
        # Continue processing ÔÇö drift should decay
        for i in range(35, 50):
            es.update(prices.iloc[:i+1])
        score_later = es._symbol_drift_score("SYM1")
        assert abs(score_later) <= abs(score_early) + 0.01

    def test_reset(self):
        from signal_engine.earnings_signal import EarningsSurpriseSignal
        es = EarningsSurpriseSignal()
        prices = self._make_prices(n=60, gap_at=30, gap_pct=0.08)
        for i in range(3, 35):
            es.update(prices.iloc[:i+1])
        es.reset()
        assert not es.has_active_event("SYM1")
        assert es.compute_score("SYM1", "SYM2") == 0.0

    def test_invalid_gap_threshold(self):
        from signal_engine.earnings_signal import EarningsSurpriseSignal
        with pytest.raises(ValueError):
            EarningsSurpriseSignal(gap_threshold=-0.01)

    def test_invalid_drift_window(self):
        from signal_engine.earnings_signal import EarningsSurpriseSignal
        with pytest.raises(ValueError):
            EarningsSurpriseSignal(drift_window=2)

    def test_get_events(self):
        from signal_engine.earnings_signal import EarningsSurpriseSignal
        es = EarningsSurpriseSignal(gap_threshold=0.02)
        prices = self._make_prices(n=60, gap_at=30, gap_pct=0.06)
        for i in range(3, 35):
            es.update(prices.iloc[:i+1])
        events = es.get_events("SYM1")
        assert isinstance(events, list)

    def test_max_events_limit(self):
        from signal_engine.earnings_signal import EarningsSurpriseSignal
        es = EarningsSurpriseSignal(gap_threshold=0.01, max_events=2)
        # Create prices with multiple large moves
        dates = pd.date_range("2024-01-01", periods=100, freq="B")
        np.random.seed(99)
        vals = [100.0]
        for i in range(1, 100):
            change = np.random.randn() * 0.3
            if i in (20, 40, 60):
                change = 5.0  # big gap
            vals.append(vals[-1] + change)
        prices = pd.DataFrame({"SYM1": vals, "SYM2": np.linspace(100, 110, 100)}, index=dates)
        for i in range(3, 70):
            es.update(prices.iloc[:i+1])
        events = es.get_events("SYM1")
        assert len(events) <= 2


# =====================================================================
# 4.2 ÔÇö Options Flow Signal
# =====================================================================
class TestOptionsFlowSignal:
    """Tests for signal_engine/options_flow.py"""

    def _make_prices(self, n=100):
        dates = pd.date_range("2024-01-01", periods=n, freq="B")
        np.random.seed(42)
        return pd.DataFrame({
            "AAPL": 150 + np.cumsum(np.random.randn(n) * 0.8),
            "MSFT": 300 + np.cumsum(np.random.randn(n) * 0.6),
            "SPY": 450 + np.cumsum(np.random.randn(n) * 0.3),
        }, index=dates)

    def test_import(self):
        from signal_engine.options_flow import OptionsFlowSignal
        ofs = OptionsFlowSignal()
        assert ofs.pc_lookback == 21
        assert ofs.vol_lookback == 60

    def test_score_range(self):
        from signal_engine.options_flow import OptionsFlowSignal
        ofs = OptionsFlowSignal()
        prices = self._make_prices(n=120)
        ofs.update(prices)
        score = ofs.compute_score("AAPL", "MSFT")
        assert -1.0 <= score <= 1.0

    def test_no_data_returns_zero(self):
        from signal_engine.options_flow import OptionsFlowSignal
        ofs = OptionsFlowSignal()
        assert ofs.compute_score("X", "Y") == 0.0

    def test_snapshot_exists(self):
        from signal_engine.options_flow import OptionsFlowSignal
        ofs = OptionsFlowSignal()
        prices = self._make_prices(n=120)
        ofs.update(prices)
        snap = ofs.get_snapshot("AAPL")
        assert snap is not None
        assert -1.0 <= snap.composite <= 1.0
        assert snap.unusual_activity >= 0

    def test_spy_excluded(self):
        from signal_engine.options_flow import OptionsFlowSignal
        ofs = OptionsFlowSignal()
        prices = self._make_prices(n=120)
        ofs.update(prices)
        assert ofs.get_snapshot("SPY") is None

    def test_reset(self):
        from signal_engine.options_flow import OptionsFlowSignal
        ofs = OptionsFlowSignal()
        prices = self._make_prices(n=120)
        ofs.update(prices)
        ofs.reset()
        assert ofs.get_snapshot("AAPL") is None

    def test_invalid_lookback(self):
        from signal_engine.options_flow import OptionsFlowSignal
        with pytest.raises(ValueError):
            OptionsFlowSignal(pc_lookback=2)

    def test_composite_weights_sum(self):
        from signal_engine.options_flow import OptionsFlowSignal
        total = OptionsFlowSignal.PC_WEIGHT + OptionsFlowSignal.IV_WEIGHT + OptionsFlowSignal.UNUSUAL_WEIGHT
        assert abs(total - 1.0) < 1e-10

    def test_symmetric_difference(self):
        from signal_engine.options_flow import OptionsFlowSignal
        ofs = OptionsFlowSignal()
        prices = self._make_prices(n=120)
        ofs.update(prices)
        s1 = ofs.compute_score("AAPL", "MSFT")
        s2 = ofs.compute_score("MSFT", "AAPL")
        assert abs(s1 + s2) < 1e-10


# =====================================================================
# 4.3 ÔÇö Sentiment Signal
# =====================================================================
class TestSentimentSignal:
    """Tests for signal_engine/sentiment.py"""

    def _make_prices(self, n=100):
        dates = pd.date_range("2024-01-01", periods=n, freq="B")
        np.random.seed(42)
        return pd.DataFrame({
            "AAPL": 150 + np.cumsum(np.random.randn(n) * 0.8),
            "MSFT": 300 + np.cumsum(np.random.randn(n) * 0.6),
            "GOOGL": 140 + np.cumsum(np.random.randn(n) * 0.7),
            "SPY": 450 + np.cumsum(np.random.randn(n) * 0.3),
        }, index=dates)

    def test_import(self):
        from signal_engine.sentiment import SentimentSignal
        ss = SentimentSignal()
        assert ss.lookback == 20
        assert ss.long_lookback == 60

    def test_score_range(self):
        from signal_engine.sentiment import SentimentSignal
        ss = SentimentSignal()
        prices = self._make_prices(n=120)
        ss.update(prices, sector_map={"AAPL": "tech", "MSFT": "tech", "GOOGL": "tech"})
        score = ss.compute_score("AAPL", "MSFT")
        assert -1.0 <= score <= 1.0

    def test_no_data_returns_zero(self):
        from signal_engine.sentiment import SentimentSignal
        ss = SentimentSignal()
        assert ss.compute_score("X", "Y") == 0.0

    def test_snapshot_content(self):
        from signal_engine.sentiment import SentimentSignal
        ss = SentimentSignal()
        prices = self._make_prices(n=120)
        ss.update(prices)
        snap = ss.get_snapshot("AAPL")
        assert snap is not None
        assert -1.0 <= snap.momentum_divergence <= 1.0
        assert -1.0 <= snap.conviction <= 1.0
        assert -1.0 <= snap.surprise_factor <= 1.0

    def test_with_sector_map(self):
        from signal_engine.sentiment import SentimentSignal
        ss = SentimentSignal()
        prices = self._make_prices(n=120)
        sector_map = {"AAPL": "tech", "MSFT": "tech", "GOOGL": "tech"}
        ss.update(prices, sector_map=sector_map)
        score = ss.compute_score("AAPL", "GOOGL")
        assert -1.0 <= score <= 1.0

    def test_without_sector_map(self):
        from signal_engine.sentiment import SentimentSignal
        ss = SentimentSignal()
        prices = self._make_prices(n=120)
        ss.update(prices)
        score = ss.compute_score("AAPL", "MSFT")
        assert -1.0 <= score <= 1.0

    def test_reset(self):
        from signal_engine.sentiment import SentimentSignal
        ss = SentimentSignal()
        prices = self._make_prices(n=120)
        ss.update(prices)
        ss.reset()
        assert ss.get_snapshot("AAPL") is None

    def test_invalid_lookback(self):
        from signal_engine.sentiment import SentimentSignal
        with pytest.raises(ValueError):
            SentimentSignal(lookback=2)

    def test_weights_sum(self):
        from signal_engine.sentiment import SentimentSignal
        total = SentimentSignal.DIVERGENCE_WEIGHT + SentimentSignal.CONVICTION_WEIGHT + SentimentSignal.SURPRISE_WEIGHT
        assert abs(total - 1.0) < 1e-10

    def test_symmetric(self):
        from signal_engine.sentiment import SentimentSignal
        ss = SentimentSignal()
        prices = self._make_prices(n=120)
        ss.update(prices)
        s1 = ss.compute_score("AAPL", "MSFT")
        s2 = ss.compute_score("MSFT", "AAPL")
        assert abs(s1 + s2) < 1e-10

    def test_smoothing(self):
        from signal_engine.sentiment import SentimentSignal
        ss = SentimentSignal(smoothing=3)
        prices = self._make_prices(n=120)
        # Call update multiple times to accumulate history
        for i in range(70, 120):
            ss.update(prices.iloc[:i+1])
        snap = ss.get_snapshot("AAPL")
        assert snap is not None


# =====================================================================
# 4.4 ÔÇö ML Signal Combiner
# =====================================================================
class TestMLSignalCombiner:
    """Tests for signal_engine/ml_combiner.py"""

    def _make_features(self, score=0.5):
        return {
            "zscore": score,
            "momentum": score * 0.8,
            "ou": score * 0.6,
            "vol_regime": score * 0.3,
            "cross_sectional": score * 0.2,
            "intraday_mr": score * 0.4,
            "earnings": score * 0.1,
            "options_flow": score * 0.15,
            "sentiment": score * 0.25,
        }

    def test_import(self):
        from signal_engine.ml_combiner import MLSignalCombiner
        ml = MLSignalCombiner()
        assert ml.min_samples == 30
        assert ml.retrain_interval == 63

    def test_backend(self):
        from signal_engine.ml_combiner import MLSignalCombiner, _ML_BACKEND
        ml = MLSignalCombiner()
        assert ml.backend in ("lightgbm", "sklearn")
        assert ml.backend == _ML_BACKEND

    def test_fallback_no_data(self):
        from signal_engine.ml_combiner import MLSignalCombiner
        ml = MLSignalCombiner()
        result = ml.predict(self._make_features(0.5))
        assert -1.0 <= result.composite_score <= 1.0
        assert result.model_trained is False

    def test_fallback_direction(self):
        from signal_engine.ml_combiner import MLSignalCombiner
        ml = MLSignalCombiner(entry_threshold=0.3)
        # Strong positive signals ÔåÆ long
        result = ml.predict(self._make_features(0.8))
        assert result.direction == "long"
        # Strong negative signals ÔåÆ short
        result = ml.predict(self._make_features(-0.8))
        assert result.direction == "short"

    def test_record_trade(self):
        from signal_engine.ml_combiner import MLSignalCombiner
        ml = MLSignalCombiner()
        ml.record_trade(bar_idx=10, features=self._make_features(0.5), outcome=0.02)
        ml.record_trade(bar_idx=20, features=self._make_features(-0.3), outcome=-0.01)
        assert len(ml._training_data) == 2

    def test_retrain_with_enough_data(self):
        from signal_engine.ml_combiner import MLSignalCombiner
        ml = MLSignalCombiner(min_samples=10, retrain_interval=5)
        np.random.seed(42)
        # Generate enough training data
        for i in range(30):
            score = np.random.randn() * 0.5
            outcome = 0.01 if score > 0 else -0.01
            ml.record_trade(bar_idx=i, features=self._make_features(score), outcome=outcome)
        # Force retrain
        success = ml._retrain(current_bar=100)
        assert success
        assert ml.n_trainings == 1

    def test_predict_with_model(self):
        from signal_engine.ml_combiner import MLSignalCombiner
        ml = MLSignalCombiner(min_samples=10, retrain_interval=5)
        np.random.seed(42)
        for i in range(30):
            score = np.random.randn() * 0.5
            outcome = 0.01 if score > 0 else -0.01
            ml.record_trade(bar_idx=i, features=self._make_features(score), outcome=outcome)
        ml._retrain(current_bar=100)
        result = ml.predict(self._make_features(0.5), current_bar=100)
        assert -1.0 <= result.composite_score <= 1.0
        assert result.model_trained is True
        assert result.confidence > 0

    def test_feature_importance(self):
        from signal_engine.ml_combiner import MLSignalCombiner
        ml = MLSignalCombiner(min_samples=10, retrain_interval=5)
        np.random.seed(42)
        for i in range(30):
            score = np.random.randn() * 0.5
            outcome = 0.01 if score > 0 else -0.01
            ml.record_trade(bar_idx=i, features=self._make_features(score), outcome=outcome)
        ml._retrain(current_bar=100)
        fi = ml.feature_importance
        assert len(fi) == len(ml.FEATURE_NAMES)
        assert all(v >= 0 for v in fi.values())

    def test_auto_retrain(self):
        from signal_engine.ml_combiner import MLSignalCombiner
        ml = MLSignalCombiner(min_samples=10, retrain_interval=5)
        np.random.seed(42)
        for i in range(20):
            score = np.random.randn() * 0.5
            outcome = 0.01 if score > 0 else -0.01
            ml.record_trade(bar_idx=i, features=self._make_features(score), outcome=outcome)
        # Should trigger auto-retrain
        result = ml.predict(self._make_features(0.3), current_bar=100)
        assert ml.n_trainings >= 1

    def test_combine_interface(self):
        from signal_engine.ml_combiner import MLSignalCombiner
        ml = MLSignalCombiner()
        result = ml.combine(self._make_features(0.5))
        assert hasattr(result, 'composite_score')
        assert hasattr(result, 'direction')
        assert hasattr(result, 'confidence')
        assert hasattr(result, 'source_scores')

    def test_reset(self):
        from signal_engine.ml_combiner import MLSignalCombiner
        ml = MLSignalCombiner(min_samples=10)
        for i in range(15):
            ml.record_trade(bar_idx=i, features=self._make_features(0.1 * i), outcome=0.01)
        ml._retrain(current_bar=100)
        ml.reset()
        assert ml._model is None
        assert ml.n_trainings == 0
        assert len(ml._training_data) == 0

    def test_disabled_mode(self):
        from signal_engine.ml_combiner import MLSignalCombiner
        ml = MLSignalCombiner(enabled=False, min_samples=5)
        for i in range(15):
            score = 0.5 if i % 2 == 0 else -0.5
            ml.record_trade(bar_idx=i, features=self._make_features(score), outcome=0.01 if score > 0 else -0.01)
        result = ml.predict(self._make_features(0.5), current_bar=100)
        assert result.model_trained is False

    def test_purge_gap(self):
        from signal_engine.ml_combiner import MLSignalCombiner
        ml = MLSignalCombiner(min_samples=10, purge_gap=20)
        np.random.seed(42)
        # Record all data at bars 90-99 (very recent)
        for i in range(10):
            ml.record_trade(bar_idx=90+i, features=self._make_features(0.3), outcome=0.01)
        # Try to retrain at bar 100 ÔÇö purge_gap=20 means only bars < 80 are used
        success = ml._retrain(current_bar=100)
        assert not success  # all data is too recent

    def test_class_balance_check(self):
        from signal_engine.ml_combiner import MLSignalCombiner
        ml = MLSignalCombiner(min_samples=5)
        # All wins ÔÇö no class balance
        for i in range(10):
            ml.record_trade(bar_idx=i, features=self._make_features(0.5), outcome=0.05)
        # Should fail due to insufficient negative class
        success = ml._retrain(current_bar=100)
        assert not success


# =====================================================================
# Integration: Combiner wiring
# =====================================================================
class TestPhase4Integration:
    """Integration tests for Phase 4 wiring."""

    def test_simulator_has_phase4_signals(self):
        """Check that the simulator initializes Phase 4 signal generators."""
        # We test that imports exist without running the full sim
        from signal_engine.earnings_signal import EarningsSurpriseSignal
        from signal_engine.options_flow import OptionsFlowSignal
        from signal_engine.sentiment import SentimentSignal
        from signal_engine.ml_combiner import MLSignalCombiner
        # All classes instantiate cleanly
        assert EarningsSurpriseSignal()
        assert OptionsFlowSignal()
        assert SentimentSignal()
        assert MLSignalCombiner()

    def test_strategy_has_phase4_sources(self):
        """Verify PairTradingStrategy creates Phase 4 signal instances."""
        from unittest.mock import patch, MagicMock
        # Mock get_settings to provide required config
        mock_settings = MagicMock()
        mock_settings.strategy.lookback_window = 120
        mock_settings.strategy.entry_z_score = 2.0
        mock_settings.strategy.exit_z_score = 0.5
        mock_settings.strategy.regime_lookback_window = 20
        mock_settings.strategy.regime_min_duration = 1
        mock_settings.strategy.instant_transition_percentile = 99.0
        mock_settings.strategy.hedge_ratio_reestimation_days = 7
        mock_settings.strategy.emergency_vol_threshold_sigma = 3.0
        mock_settings.strategy.trailing_stop_widening = 1.0
        mock_settings.strategy.max_symbol_concentration_pct = 30.0
        mock_settings.strategy.retraining_frequency_days = 30
        mock_settings.strategy.retraining_lookback = 252
        mock_settings.strategy.leg_correlation_window = 30
        mock_settings.strategy.leg_correlation_decay_threshold = 0.3
        mock_settings.strategy.internal_max_positions = 10
        mock_settings.strategy.internal_max_daily_trades = 50
        mock_settings.strategy.internal_max_drawdown_pct = 20.0
        mock_settings.strategy.initial_capital = 100000
        mock_settings.strategy.weekly_zscore_entry_gate = 0.0
        mock_settings.strategy.regime_directional_filter = False
        mock_settings.strategy.trend_long_sizing = 0.75
        mock_settings.strategy.disable_shorts_in_bull_trend = False
        mock_settings.strategy.short_sizing_multiplier = 0.50
        mock_settings.momentum.enabled = False
        mock_settings.momentum.lookback = 20
        mock_settings.momentum.weight = 0.30
        mock_settings.momentum.min_strength = 0.30
        mock_settings.momentum.max_boost = 1.0

        with patch('strategies.pair_trading.get_settings', return_value=mock_settings):
            with patch('config.settings.get_settings', return_value=mock_settings):
                from strategies.pair_trading import PairTradingStrategy
                strategy = PairTradingStrategy()
                assert hasattr(strategy, '_earnings_signal')
                assert hasattr(strategy, '_options_flow')
                assert hasattr(strategy, '_sentiment_signal')

    def test_ml_prediction_compatible_with_composite(self):
        """MLPrediction has same interface as CompositeSignal."""
        from signal_engine.ml_combiner import MLPrediction
        pred = MLPrediction(composite_score=0.5, direction="long", confidence=0.8)
        assert pred.composite_score == 0.5
        assert pred.direction == "long"
        assert pred.confidence == 0.8
        assert isinstance(pred.source_scores, dict)

    def test_feature_names_complete(self):
        """All 9 signal sources present in FEATURE_NAMES."""
        from signal_engine.ml_combiner import MLSignalCombiner
        expected = {"zscore", "momentum", "ou", "vol_regime",
                    "cross_sectional", "intraday_mr",
                    "earnings", "options_flow", "sentiment"}
        assert set(MLSignalCombiner.FEATURE_NAMES) == expected
