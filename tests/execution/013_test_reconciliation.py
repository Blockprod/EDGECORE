"""Tests for broker reconciliation system."""

import pytest
import math
from datetime import datetime
from execution.reconciler import (
    BrokerReconciler,
    ReconciliationStatus,
    ReconciliationDivergence,
    ReconciliationReport
)


class TestReconciliationDivergence:
    """Test divergence record creation and properties."""
    
    def test_create_divergence(self):
        """Test basic divergence creation."""
        div = ReconciliationDivergence(
            type="equity",
            severity="high",
            description="Mismatch",
            broker_value=100000.0,
            internal_value=99000.0
        )
        assert div.type == "equity"
        assert div.severity == "high"
        assert div.broker_value == 100000.0
        assert div.internal_value == 99000.0
        assert div.resolved_at is None
    
    def test_divergence_has_timestamp(self):
        """Test divergence records timestamp."""
        before = datetime.utcnow()
        div = ReconciliationDivergence(
            type="position",
            severity="low",
            description="Test",
            broker_value=1.0,
            internal_value=1.0
        )
        after = datetime.utcnow()
        assert before <= div.detected_at <= after


class TestReconciliationReport:
    """Test reconciliation report creation."""
    
    def test_create_report_ok(self):
        """Test creating OK status report."""
        report = ReconciliationReport(
            status=ReconciliationStatus.OK,
            timestamp=datetime.utcnow(),
            equity_match=True,
            equity_broker=100000.0,
            equity_internal=100000.0,
            equity_diff_pct=0.0,
            positions_match=True,
            positions_count_broker=2,
            positions_count_internal=2,
            orders_match=True,
            divergences=[]
        )
        assert report.status == ReconciliationStatus.OK
        assert len(report.divergences) == 0


class TestBrokerReconcilerInit:
    """Test reconciler initialization."""
    
    def test_init_with_valid_equity(self):
        """Test reconciler with valid equity."""
        reconciler = BrokerReconciler(internal_equity=100000.0)
        assert reconciler.internal_equity == 100000.0
        assert len(reconciler.internal_positions) == 0
        assert len(reconciler.internal_orders) == 0
    
    def test_init_with_positions_and_orders(self):
        """Test reconciler with positions and orders."""
        positions = {"AAPL": {"size": 1.0, "price": 50000}}
        orders = {"order_1": {"symbol": "AAPL", "quantity": 1}}
        
        reconciler = BrokerReconciler(
            internal_equity=100000.0,
            internal_positions=positions,
            internal_orders=orders
        )
        assert len(reconciler.internal_positions) == 1
        assert len(reconciler.internal_orders) == 1
    
    def test_init_with_zero_equity_fails(self):
        """Test that zero equity raises error."""
        with pytest.raises(ValueError):
            BrokerReconciler(internal_equity=0.0)
    
    def test_init_with_negative_equity_fails(self):
        """Test that negative equity raises error."""
        with pytest.raises(ValueError):
            BrokerReconciler(internal_equity=-50000.0)
    
    def test_init_with_invalid_equity_tolerance(self):
        """Test that invalid tolerance raises error."""
        with pytest.raises(ValueError):
            BrokerReconciler(internal_equity=100000.0, equity_tolerance_pct=-1.0)
    
    def test_init_with_equity_tolerance_too_high(self):
        """Test that tolerance > 100% raises error."""
        with pytest.raises(ValueError):
            BrokerReconciler(internal_equity=100000.0, equity_tolerance_pct=101.0)
    
    def test_init_with_negative_position_tolerance(self):
        """Test that negative position tolerance raises error."""
        with pytest.raises(ValueError):
            BrokerReconciler(internal_equity=100000.0, position_tolerance_units=-1.0)


class TestEquityReconciliation:
    """Test equity reconciliation logic."""
    
    def test_equity_match_exact(self):
        """Test perfect equity match."""
        reconciler = BrokerReconciler(internal_equity=100000.0)
        matches, diff_pct = reconciler.reconcile_equity(100000.0)
        
        assert matches
        assert diff_pct == 0.0
    
    def test_equity_match_within_tolerance(self):
        """Test equity match within tolerance."""
        reconciler = BrokerReconciler(internal_equity=100000.0, equity_tolerance_pct=0.01)
        # 0.01% of 100000 = 10
        matches, diff_pct = reconciler.reconcile_equity(100010.0)
        
        assert matches
        assert diff_pct <= 0.01
    
    def test_equity_mismatch_exceeds_tolerance(self):
        """Test equity mismatch beyond tolerance."""
        reconciler = BrokerReconciler(internal_equity=100000.0, equity_tolerance_pct=0.01)
        # Create 1% difference = 1000
        matches, diff_pct = reconciler.reconcile_equity(99000.0)
        
        assert not matches
        assert diff_pct > 0.01
        assert len(reconciler.divergences) == 1
        assert reconciler.divergences[0].type == "equity"
    
    def test_equity_reconcile_with_zero_fails(self):
        """Test that zero broker equity raises error."""
        reconciler = BrokerReconciler(internal_equity=100000.0)
        
        with pytest.raises(ValueError):
            reconciler.reconcile_equity(0.0)
    
    def test_equity_reconcile_with_negative_fails(self):
        """Test that negative broker equity raises error."""
        reconciler = BrokerReconciler(internal_equity=100000.0)
        
        with pytest.raises(ValueError):
            reconciler.reconcile_equity(-50000.0)
    
    def test_equity_reconcile_with_nan_fails(self):
        """Test that NaN broker equity raises error."""
        reconciler = BrokerReconciler(internal_equity=100000.0)
        
        with pytest.raises(ValueError):
            reconciler.reconcile_equity(math.nan)
    
    def test_equity_reconcile_with_inf_fails(self):
        """Test that infinite broker equity raises error."""
        reconciler = BrokerReconciler(internal_equity=100000.0)
        
        with pytest.raises(ValueError):
            reconciler.reconcile_equity(math.inf)


class TestPositionReconciliation:
    """Test position reconciliation logic."""
    
    def test_positions_match_exact(self):
        """Test exact position matches."""
        positions = {"AAPL": {"size": 1.0}, "MSFT": {"size": 10.0}}
        reconciler = BrokerReconciler(
            internal_equity=100000.0,
            internal_positions=positions
        )
        
        broker_positions = {"AAPL": {"size": 1.0}, "MSFT": {"size": 10.0}}
        matches, inconsistencies = reconciler.reconcile_positions(broker_positions)
        
        assert matches
        assert len(inconsistencies) == 0
    
    def test_positions_match_within_tolerance(self):
        """Test position sizes within tolerance."""
        positions = {"AAPL": {"size": 1.0}}
        reconciler = BrokerReconciler(
            internal_equity=100000.0,
            internal_positions=positions,
            position_tolerance_units=0.1
        )
        
        # 0.05 difference should be within 0.1 tolerance
        broker_positions = {"AAPL": {"size": 1.05}}
        matches, inconsistencies = reconciler.reconcile_positions(broker_positions)
        
        assert matches
        assert len(inconsistencies) == 0
    
    def test_positions_mismatch_exceeds_tolerance(self):
        """Test position size mismatch beyond tolerance."""
        positions = {"AAPL": {"size": 1.0}}
        reconciler = BrokerReconciler(
            internal_equity=100000.0,
            internal_positions=positions,
            position_tolerance_units=0.1
        )
        
        # 0.5 difference exceeds 0.1 tolerance
        broker_positions = {"AAPL": {"size": 1.5}}
        matches, inconsistencies = reconciler.reconcile_positions(broker_positions)
        
        assert not matches
        assert len(inconsistencies) > 0
        assert len(reconciler.divergences) > 0
    
    def test_positions_missing_on_broker(self):
        """Test position missing on broker."""
        positions = {"AAPL": {"size": 1.0}}
        reconciler = BrokerReconciler(
            internal_equity=100000.0,
            internal_positions=positions
        )
        
        broker_positions = {}
        matches, inconsistencies = reconciler.reconcile_positions(broker_positions)
        
        assert not matches
        assert len(inconsistencies) > 0
    
    def test_positions_unknown_on_broker(self):
        """Test unknown position on broker."""
        reconciler = BrokerReconciler(internal_equity=100000.0)
        
        broker_positions = {"UNKNOWN/USD": {"size": 1.0}}
        matches, inconsistencies = reconciler.reconcile_positions(broker_positions)
        
        assert not matches
        assert len(inconsistencies) > 0
    
    def test_positions_invalid_input_fails(self):
        """Test that invalid positions input raises error."""
        reconciler = BrokerReconciler(internal_equity=100000.0)
        
        with pytest.raises(ValueError):
            reconciler.reconcile_positions("not a dict")  # type: ignore


class TestOrderReconciliation:
    """Test order reconciliation logic."""
    
    def test_orders_match_exact(self):
        """Test exact order matches."""
        orders = {"order_1": {"symbol": "AAPL"}, "order_2": {"symbol": "MSFT"}}
        reconciler = BrokerReconciler(
            internal_equity=100000.0,
            internal_orders=orders
        )
        
        broker_orders = {"order_1": {"symbol": "AAPL"}, "order_2": {"symbol": "MSFT"}}
        matches, inconsistencies = reconciler.reconcile_orders(broker_orders)
        
        assert matches
        assert len(inconsistencies) == 0
    
    def test_orders_unknown_on_broker(self):
        """Test unknown order on broker."""
        reconciler = BrokerReconciler(internal_equity=100000.0)
        
        broker_orders = {"unknown_order": {"symbol": "AAPL"}}
        matches, inconsistencies = reconciler.reconcile_orders(broker_orders)
        
        assert not matches
        assert len(inconsistencies) > 0
    
    def test_orders_invalid_input_fails(self):
        """Test that invalid orders input raises error."""
        reconciler = BrokerReconciler(internal_equity=100000.0)
        
        with pytest.raises(ValueError):
            reconciler.reconcile_orders("not a dict")  # type: ignore


class TestFullReconciliation:
    """Test complete reconciliation workflow."""
    
    def test_full_reconciliation_all_ok(self):
        """Test full reconciliation with all systems OK."""
        positions = {"AAPL": {"size": 1.0}}
        orders = {"order_1": {"symbol": "AAPL"}}
        
        reconciler = BrokerReconciler(
            internal_equity=100000.0,
            internal_positions=positions,
            internal_orders=orders
        )
        
        broker_positions = {"AAPL": {"size": 1.0}}
        broker_orders = {"order_1": {"symbol": "AAPL"}}
        
        report = reconciler.full_reconciliation(
            broker_equity=100000.0,
            broker_positions=broker_positions,
            broker_orders=broker_orders
        )
        
        assert report.status == ReconciliationStatus.OK
        assert report.equity_match
        assert report.positions_match
        assert report.orders_match
        assert len(report.divergences) == 0
    
    def test_full_reconciliation_equity_mismatch(self):
        """Test full reconciliation with equity mismatch."""
        reconciler = BrokerReconciler(
            internal_equity=100000.0,
            equity_tolerance_pct=0.01
        )
        
        report = reconciler.full_reconciliation(
            broker_equity=99000.0,
            broker_positions={},
            broker_orders={}
        )
        
        assert report.status in [ReconciliationStatus.WARNING, ReconciliationStatus.CRITICAL]
        assert not report.equity_match
        assert report.equity_diff_pct > 0.01
    
    def test_full_reconciliation_critical_status(self):
        """Test that large equity mismatch sets CRITICAL status."""
        reconciler = BrokerReconciler(internal_equity=100000.0)
        
        report = reconciler.full_reconciliation(
            broker_equity=50000.0,  # 50% difference
            broker_positions={},
            broker_orders={}
        )
        
        assert report.status == ReconciliationStatus.CRITICAL
    
    def test_full_reconciliation_stores_report(self):
        """Test that report is stored for later retrieval."""
        reconciler = BrokerReconciler(internal_equity=100000.0)
        
        report = reconciler.full_reconciliation(
            broker_equity=100000.0,
            broker_positions={},
            broker_orders={}
        )
        
        assert reconciler.last_reconciliation == report


class TestRecoveryActions:
    """Test recovery action suggestions."""
    
    def test_recovery_actions_empty_no_divergences(self):
        """Test no recovery actions when no divergences."""
        reconciler = BrokerReconciler(internal_equity=100000.0)
        
        reconciler.full_reconciliation(
            broker_equity=100000.0,
            broker_positions={},
            broker_orders={}
        )
        
        actions = reconciler.get_recovery_actions()
        assert len(actions) == 0
    
    def test_recovery_actions_equity_high_severity(self):
        """Test recovery action for high severity equity mismatch."""
        reconciler = BrokerReconciler(internal_equity=100000.0)
        
        # Trigger large equity divergence
        reconciler.full_reconciliation(
            broker_equity=50000.0,
            broker_positions={},
            broker_orders={}
        )
        
        actions = reconciler.get_recovery_actions()
        assert len(actions) > 0
        assert any("HALT" in action for action in actions)
    
    def test_recovery_actions_position_mismatch(self):
        """Test recovery action for position mismatch."""
        positions = {"AAPL": {"size": 1.0}}
        reconciler = BrokerReconciler(
            internal_equity=100000.0,
            internal_positions=positions
        )
        
        # Position missing on broker
        reconciler.full_reconciliation(
            broker_equity=100000.0,
            broker_positions={},
            broker_orders={}
        )
        
        actions = reconciler.get_recovery_actions()
        assert len(actions) > 0


class TestReconciliationIntegration:
    """Integration tests for complete workflows."""
    
    def test_daily_startup_reconciliation(self):
        """Test typical daily startup reconciliation workflow."""
        # Internal state from last session
        internal_positions = {
            "AAPL": {"size": 2.5, "entry_price": 40000},
            "MSFT": {"size": 50.0, "entry_price": 2000}
        }
        internal_orders = {
            "pending_1": {"symbol": "AAPL", "status": "pending"}
        }
        
        reconciler = BrokerReconciler(
            internal_equity=250000.0,
            internal_positions=internal_positions,
            internal_orders=internal_orders,
            equity_tolerance_pct=0.1  # 0.1% tolerance
        )
        
        # Actual broker state
        broker_positions = {
            "AAPL": {"size": 2.5, "entry_price": 40000},
            "MSFT": {"size": 50.0, "entry_price": 2000}
        }
        broker_orders = {}  # Order filled overnight
        
        report = reconciler.full_reconciliation(
            broker_equity=250100.0,  # Slight profit, within 0.1% tolerance
            broker_positions=broker_positions,
            broker_orders=broker_orders
        )
        
        # Equity should match within tolerance, but order is missing
        assert report.equity_match
        assert report.positions_match
        # Order is expected to be gone (filled, cancelled, or executed)
        assert len(report.divergences) <= 1  # May have order divergence
    
    def test_gap_detection_scenario(self):
        """Test detection of overnight gap/divergence."""
        # Internal thinks we have 200 shares
        internal_positions = {"AAPL": {"size": 2.0}}
        
        reconciler = BrokerReconciler(
            internal_equity=100000.0,
            internal_positions=internal_positions,
            position_tolerance_units=0.1
        )
        
        # But broker actually has 150 shares (partial fill unknown to system)
        broker_positions = {"AAPL": {"size": 1.5}}
        
        report = reconciler.full_reconciliation(
            broker_equity=100000.0,
            broker_positions=broker_positions,
            broker_orders={}
        )
        
        assert not report.positions_match
        assert len(report.divergences) > 0
