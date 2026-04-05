"""CERT-03 regression — Single drawdown source-of-truth.

Verifies that PortfolioRiskManager is the unique source of truth for the
drawdown percentage fed into the KillSwitch via RiskFacade.

Before CERT-03, RiskFacade.can_enter_trade() was called with drawdown_pct=0.0
(hardcoded default in live_trading/runner.py), meaning the KillSwitch never
fired on drawdown events — only PortfolioRiskManager.can_open_position() blocked.

After CERT-03, the runner passes portfolio_risk.drawdown_pct explicitly, giving
the KillSwitch access to the real drawdown figure.
"""

import pytest

from risk.facade import RiskFacade
from risk_engine.kill_switch import KillSwitch, KillSwitchConfig
from risk_engine.portfolio_risk import PortfolioRiskConfig, PortfolioRiskManager


@pytest.fixture
def portfolio_risk() -> PortfolioRiskManager:
    """PortfolioRiskManager with a 10% max-drawdown threshold (T1)."""
    return PortfolioRiskManager(
        initial_equity=100_000.0,
        config=PortfolioRiskConfig(max_drawdown_pct=0.10),
    )


@pytest.fixture
def risk_facade(tmp_path) -> RiskFacade:
    """RiskFacade with KillSwitch at 15% drawdown (T2).

    Uses an isolated state_file (tmp_path) so no on-disk KS state pollutes tests.
    """
    ks = KillSwitch(
        config=KillSwitchConfig(max_drawdown_pct=0.15),
        state_file=str(tmp_path / "ks_test.json"),
    )
    return RiskFacade(initial_equity=100_000.0, kill_switch=ks)


class TestDrawdownSingleSource:
    """PortfolioRiskManager.drawdown_pct is the canonical DD figure."""

    def test_drawdown_zero_when_no_loss(self, portfolio_risk: PortfolioRiskManager) -> None:
        portfolio_risk.update_equity(100_000.0)
        assert portfolio_risk.drawdown_pct == 0.0

    def test_drawdown_computed_correctly(self, portfolio_risk: PortfolioRiskManager) -> None:
        """Drawdown = (peak - current) / peak."""
        portfolio_risk.update_equity(90_000.0)
        assert abs(portfolio_risk.drawdown_pct - 0.10) < 1e-9

    def test_portfolio_risk_blocks_at_threshold(self, portfolio_risk: PortfolioRiskManager) -> None:
        """can_open_position returns False once drawdown >= max_drawdown_pct."""
        portfolio_risk.update_equity(89_999.0)  # 10.001% DD
        ok, reason = portfolio_risk.can_open_position()
        assert not ok
        assert "Drawdown" in reason

    def test_portfolio_risk_allows_below_threshold(self, portfolio_risk: PortfolioRiskManager) -> None:
        portfolio_risk.update_equity(95_000.0)  # 5% DD
        ok, _ = portfolio_risk.can_open_position()
        assert ok

    def test_kill_switch_fires_when_dd_passed(self, risk_facade: RiskFacade) -> None:
        """KillSwitch activates when drawdown_pct >= its threshold is forwarded."""
        # 20% DD exceeds KillSwitch T2 = 15%
        ok, reason = risk_facade.can_enter_trade(
            symbol_pair="A:B",
            position_size=0.0,
            current_equity=80_000.0,
            volatility=0.01,
            drawdown_pct=0.20,
        )
        assert not ok
        assert reason is not None and "Kill-switch" in reason

    def test_kill_switch_silent_below_t2(self, risk_facade: RiskFacade) -> None:
        """KillSwitch (T2=15%) stays silent when drawdown < 15%."""
        ok, _ = risk_facade.can_enter_trade(
            symbol_pair="A:B",
            position_size=1000.0,
            current_equity=100_000.0,
            volatility=0.01,
            drawdown_pct=0.05,
        )
        assert ok

    def test_single_halt_not_double(
        self,
        portfolio_risk: PortfolioRiskManager,
        risk_facade: RiskFacade,
    ) -> None:
        """T1 breach (11%) blocks PRM but NOT KillSwitch (T2=15%).

        Each gate fires at its own threshold — no double-counting.
        """
        portfolio_risk.update_equity(89_000.0)  # 11% DD — above T1 (10%)
        dd = portfolio_risk.drawdown_pct
        assert dd > 0.10

        # PRM blocks at T1
        prm_ok, _ = portfolio_risk.can_open_position()
        assert not prm_ok, "PRM must block at T1"

        # KillSwitch (T2=15%) should NOT fire at 11%
        facade_ok, _ = risk_facade.can_enter_trade(
            symbol_pair="X:Y",
            position_size=1.0,
            current_equity=89_000.0,
            volatility=0.001,
            drawdown_pct=dd,
        )
        assert facade_ok, "KillSwitch (T2=15%) must NOT fire at 11% DD"

    def test_kill_switch_fires_at_t2(
        self,
        portfolio_risk: PortfolioRiskManager,
        risk_facade: RiskFacade,
    ) -> None:
        """T2 breach (16%) triggers both PRM halt and KillSwitch."""
        portfolio_risk.update_equity(84_000.0)  # 16% DD — above T2
        dd = portfolio_risk.drawdown_pct
        assert dd > 0.15

        # PRM halted (auto-halt via update_equity at >= 10%)
        prm_ok, _ = portfolio_risk.can_open_position()
        assert not prm_ok

        # KillSwitch also fires
        ks_ok, ks_reason = risk_facade.can_enter_trade(
            symbol_pair="X:Y",
            position_size=0.0,
            current_equity=84_000.0,
            volatility=0.01,
            drawdown_pct=dd,
        )
        assert not ks_ok
        assert ks_reason is not None and "Kill-switch" in ks_reason
