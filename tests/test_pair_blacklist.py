<<<<<<< HEAD
﻿"""Tests for ├ëtape 3 ÔÇö Dynamic Pair Blacklist.
=======
"""Tests for Étape 3 — Dynamic Pair Blacklist.
>>>>>>> origin/main

Validates:
- Consecutive loss tracking
- Blacklist triggers after N losses
- Cooldown expiry rehabilitates pairs
- Win resets loss counter
- JSON persistence
- Config integration
- Disabled mode
"""

<<<<<<< HEAD
from datetime import date
from pathlib import Path

from pair_selection.blacklist import PairBlacklist

# ÔöÇÔöÇ Core blacklist logic ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ

=======
import pytest
from datetime import date, timedelta
from pathlib import Path
import json

from pair_selection.blacklist import PairBlacklist


# ── Core blacklist logic ─────────────────────────────────────────────
>>>>>>> origin/main

class TestBlacklistCoreLoss:
    """Consecutive loss tracking and blacklisting."""

    def test_no_block_after_one_loss(self):
        bl = PairBlacklist(max_consecutive_losses=2, cooldown_days=30)
        bl.record_outcome("A_B", pnl=-100.0, trade_date=date(2025, 1, 10))
        assert bl.is_blocked("A_B", date(2025, 1, 11)) is False

    def test_blocked_after_two_losses(self):
        bl = PairBlacklist(max_consecutive_losses=2, cooldown_days=30)
        bl.record_outcome("A_B", pnl=-100.0, trade_date=date(2025, 1, 10))
        bl.record_outcome("A_B", pnl=-50.0, trade_date=date(2025, 1, 15))
        assert bl.is_blocked("A_B", date(2025, 1, 16)) is True

    def test_blocked_after_three_losses(self):
        bl = PairBlacklist(max_consecutive_losses=2, cooldown_days=30)
        bl.record_outcome("A_B", pnl=-100.0, trade_date=date(2025, 1, 1))
        bl.record_outcome("A_B", pnl=-50.0, trade_date=date(2025, 1, 5))
        bl.record_outcome("A_B", pnl=-25.0, trade_date=date(2025, 1, 10))
        assert bl.is_blocked("A_B", date(2025, 1, 11)) is True

    def test_win_resets_counter(self):
        bl = PairBlacklist(max_consecutive_losses=2, cooldown_days=30)
        bl.record_outcome("A_B", pnl=-100.0, trade_date=date(2025, 1, 1))
        bl.record_outcome("A_B", pnl=200.0, trade_date=date(2025, 1, 5))
        bl.record_outcome("A_B", pnl=-50.0, trade_date=date(2025, 1, 10))
        # Only 1 consecutive loss (the win reset the counter)
        assert bl.is_blocked("A_B", date(2025, 1, 11)) is False

    def test_zero_pnl_is_not_a_loss(self):
        bl = PairBlacklist(max_consecutive_losses=2, cooldown_days=30)
        bl.record_outcome("A_B", pnl=-100.0, trade_date=date(2025, 1, 1))
        bl.record_outcome("A_B", pnl=0.0, trade_date=date(2025, 1, 5))
        # 0 P&L counts as a win (resets counter)
        assert bl.is_blocked("A_B", date(2025, 1, 6)) is False


<<<<<<< HEAD
# ÔöÇÔöÇ Cooldown expiry ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ

=======
# ── Cooldown expiry ──────────────────────────────────────────────────
>>>>>>> origin/main

class TestBlacklistCooldown:
    """Pairs unblocked after cooldown expires."""

    def test_cooldown_expires_after_30_days(self):
        bl = PairBlacklist(max_consecutive_losses=2, cooldown_days=30)
        bl.record_outcome("A_B", pnl=-100.0, trade_date=date(2025, 1, 1))
        bl.record_outcome("A_B", pnl=-50.0, trade_date=date(2025, 1, 5))
        # Blocked during cooldown
        assert bl.is_blocked("A_B", date(2025, 1, 20)) is True
        # Not blocked after 30 days from blacklist date
        assert bl.is_blocked("A_B", date(2025, 2, 5)) is False

    def test_cooldown_exact_boundary(self):
        bl = PairBlacklist(max_consecutive_losses=2, cooldown_days=30)
        bl.record_outcome("A_B", pnl=-10.0, trade_date=date(2025, 3, 1))
        bl.record_outcome("A_B", pnl=-10.0, trade_date=date(2025, 3, 1))
        # Cooldown until 2025-03-31
        assert bl.is_blocked("A_B", date(2025, 3, 30)) is True
        assert bl.is_blocked("A_B", date(2025, 3, 31)) is False  # exact end

    def test_can_be_re_blacklisted_after_cooldown(self):
        bl = PairBlacklist(max_consecutive_losses=2, cooldown_days=10)
        bl.record_outcome("A_B", pnl=-10.0, trade_date=date(2025, 1, 1))
        bl.record_outcome("A_B", pnl=-10.0, trade_date=date(2025, 1, 2))
        # Cooldown expires
        assert bl.is_blocked("A_B", date(2025, 1, 12)) is False
<<<<<<< HEAD
        # 2 more losses after cooldown ÔåÆ re-blacklisted
=======
        # 2 more losses after cooldown → re-blacklisted
>>>>>>> origin/main
        bl.record_outcome("A_B", pnl=-10.0, trade_date=date(2025, 1, 15))
        bl.record_outcome("A_B", pnl=-10.0, trade_date=date(2025, 1, 18))
        assert bl.is_blocked("A_B", date(2025, 1, 19)) is True


<<<<<<< HEAD
# ÔöÇÔöÇ Multiple pairs ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ

=======
# ── Multiple pairs ───────────────────────────────────────────────────
>>>>>>> origin/main

class TestBlacklistMultiplePairs:
    """Each pair tracked independently."""

    def test_different_pairs_independent(self):
        bl = PairBlacklist(max_consecutive_losses=2, cooldown_days=30)
        bl.record_outcome("A_B", pnl=-10.0, trade_date=date(2025, 1, 1))
        bl.record_outcome("A_B", pnl=-10.0, trade_date=date(2025, 1, 2))
        bl.record_outcome("C_D", pnl=-10.0, trade_date=date(2025, 1, 1))
        assert bl.is_blocked("A_B", date(2025, 1, 3)) is True
        assert bl.is_blocked("C_D", date(2025, 1, 3)) is False

    def test_unknown_pair_not_blocked(self):
        bl = PairBlacklist(max_consecutive_losses=2, cooldown_days=30)
        assert bl.is_blocked("UNKNOWN_PAIR", date(2025, 1, 1)) is False

    def test_get_blocked_pairs(self):
        bl = PairBlacklist(max_consecutive_losses=2, cooldown_days=30)
        bl.record_outcome("A_B", pnl=-10.0, trade_date=date(2025, 1, 1))
        bl.record_outcome("A_B", pnl=-10.0, trade_date=date(2025, 1, 2))
        bl.record_outcome("C_D", pnl=-10.0, trade_date=date(2025, 1, 1))
        bl.record_outcome("C_D", pnl=-10.0, trade_date=date(2025, 1, 2))
        blocked = bl.get_blocked_pairs(date(2025, 1, 3))
        assert sorted(blocked) == ["A_B", "C_D"]


<<<<<<< HEAD
# ÔöÇÔöÇ Persistence ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ

=======
# ── Persistence ──────────────────────────────────────────────────────
>>>>>>> origin/main

class TestBlacklistPersistence:
    """JSON persistence survives reload."""

    def test_save_and_load(self, tmp_path):
        json_path = tmp_path / "blacklist.json"
<<<<<<< HEAD
        bl = PairBlacklist(max_consecutive_losses=2, cooldown_days=30, persist_path=str(json_path))
=======
        bl = PairBlacklist(max_consecutive_losses=2, cooldown_days=30,
                           persist_path=str(json_path))
>>>>>>> origin/main
        bl.record_outcome("A_B", pnl=-10.0, trade_date=date(2025, 1, 1))
        bl.record_outcome("A_B", pnl=-10.0, trade_date=date(2025, 1, 2))
        assert json_path.exists()

        # Reload from file
<<<<<<< HEAD
        bl2 = PairBlacklist(max_consecutive_losses=2, cooldown_days=30, persist_path=str(json_path))
=======
        bl2 = PairBlacklist(max_consecutive_losses=2, cooldown_days=30,
                            persist_path=str(json_path))
>>>>>>> origin/main
        assert bl2.is_blocked("A_B", date(2025, 1, 3)) is True

    def test_reset_clears_state(self, tmp_path):
        json_path = tmp_path / "blacklist.json"
<<<<<<< HEAD
        bl = PairBlacklist(max_consecutive_losses=2, cooldown_days=30, persist_path=str(json_path))
=======
        bl = PairBlacklist(max_consecutive_losses=2, cooldown_days=30,
                           persist_path=str(json_path))
>>>>>>> origin/main
        bl.record_outcome("A_B", pnl=-10.0, trade_date=date(2025, 1, 1))
        bl.record_outcome("A_B", pnl=-10.0, trade_date=date(2025, 1, 2))
        bl.reset()
        assert bl.is_blocked("A_B", date(2025, 1, 3)) is False
        assert not json_path.exists()


<<<<<<< HEAD
# ÔöÇÔöÇ Disabled mode ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ

=======
# ── Disabled mode ────────────────────────────────────────────────────
>>>>>>> origin/main

class TestBlacklistDisabled:
    """When disabled, never blocks."""

    def test_disabled_never_blocks(self):
        bl = PairBlacklist(max_consecutive_losses=2, cooldown_days=30, enabled=False)
        bl.record_outcome("A_B", pnl=-10.0, trade_date=date(2025, 1, 1))
        bl.record_outcome("A_B", pnl=-10.0, trade_date=date(2025, 1, 2))
        assert bl.is_blocked("A_B", date(2025, 1, 3)) is False

    def test_disabled_record_is_noop(self):
        bl = PairBlacklist(max_consecutive_losses=2, cooldown_days=30, enabled=False)
        bl.record_outcome("A_B", pnl=-10.0, trade_date=date(2025, 1, 1))
        assert bl.get_stats() == {}  # nothing recorded


<<<<<<< HEAD
# ÔöÇÔöÇ Config integration ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ

=======
# ── Config integration ───────────────────────────────────────────────
>>>>>>> origin/main

class TestBlacklistConfig:
    """BlacklistConfig in settings.py and config.yaml."""

    def test_config_exists(self):
        from config.settings import BlacklistConfig
<<<<<<< HEAD

=======
>>>>>>> origin/main
        cfg = BlacklistConfig()
        assert cfg.max_consecutive_losses == 2
        assert cfg.cooldown_days == 30
        assert cfg.enabled is True

    def test_yaml_has_section(self):
<<<<<<< HEAD
        import yaml

=======
        from pathlib import Path
        import yaml
>>>>>>> origin/main
        cfg_path = Path(__file__).resolve().parents[1] / "config" / "config.yaml"
        with open(cfg_path, encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        assert "pair_blacklist" in raw
        assert raw["pair_blacklist"]["max_consecutive_losses"] == 6
        assert raw["pair_blacklist"]["cooldown_days"] == 7

    def test_settings_loads_blacklist(self):
<<<<<<< HEAD
        from config.settings import Settings, get_settings

        # Force reload
        Settings._initialized = False  # type: ignore[attr-defined]
        Settings._instance = None
        s = get_settings()
        assert hasattr(s, "pair_blacklist")
        assert s.pair_blacklist.max_consecutive_losses == 2


# ÔöÇÔöÇ GE_RTX scenario ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ

=======
        from config.settings import get_settings, Settings
        # Force reload
        Settings._initialized = False
        Settings._instance = None
        s = get_settings()
        assert hasattr(s, 'pair_blacklist')
        assert s.pair_blacklist.max_consecutive_losses == 2


# ── GE_RTX scenario ─────────────────────────────────────────────────
>>>>>>> origin/main

class TestGERTXScenario:
    """Simulate the v27 GE_RTX case: 6 trades, 0 wins."""

    def test_ge_rtx_blocked_after_2nd_loss(self):
        bl = PairBlacklist(max_consecutive_losses=2, cooldown_days=30)
        # Trade 1: loss
        bl.record_outcome("GE_RTX", pnl=-1097.0, trade_date=date(2024, 3, 15))
        assert bl.is_blocked("GE_RTX", date(2024, 3, 16)) is False
<<<<<<< HEAD
        # Trade 2: loss ÔåÆ blacklisted
=======
        # Trade 2: loss → blacklisted
>>>>>>> origin/main
        bl.record_outcome("GE_RTX", pnl=-1097.0, trade_date=date(2024, 5, 10))
        assert bl.is_blocked("GE_RTX", date(2024, 5, 11)) is True
        # Trades 3-6 would be blocked
        assert bl.is_blocked("GE_RTX", date(2024, 5, 20)) is True
        assert bl.is_blocked("GE_RTX", date(2024, 6, 1)) is True

    def test_ge_rtx_savings(self):
        """With blacklist, only 2 of 6 trades go through (within 30-day cooldown)."""
        losses = [-1097, -1097, -1097, -1097, -1097, -1097]
        bl = PairBlacklist(max_consecutive_losses=2, cooldown_days=30)
        executed = 0
        # All 6 trades within 30-day window so cooldown doesn't expire
        trade_dates = [
<<<<<<< HEAD
            date(2024, 3, 1),
            date(2024, 3, 5),
            date(2024, 3, 10),
            date(2024, 3, 15),
            date(2024, 3, 20),
            date(2024, 3, 25),
        ]
        for _i, (pnl, d) in enumerate(zip(losses, trade_dates, strict=False)):
=======
            date(2024, 3, 1), date(2024, 3, 5), date(2024, 3, 10),
            date(2024, 3, 15), date(2024, 3, 20), date(2024, 3, 25),
        ]
        for i, (pnl, d) in enumerate(zip(losses, trade_dates)):
>>>>>>> origin/main
            if not bl.is_blocked("GE_RTX", d):
                executed += 1
                bl.record_outcome("GE_RTX", pnl=pnl, trade_date=d)
        assert executed == 2  # Only first 2 trades go through


<<<<<<< HEAD
# ÔöÇÔöÇ Stats ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ

=======
# ── Stats ────────────────────────────────────────────────────────────
>>>>>>> origin/main

class TestBlacklistStats:
    """get_stats() returns monitoring-friendly data."""

    def test_stats_after_trades(self):
        bl = PairBlacklist(max_consecutive_losses=2, cooldown_days=30)
        bl.record_outcome("A_B", pnl=-10.0, trade_date=date(2025, 1, 1))
        bl.record_outcome("A_B", pnl=50.0, trade_date=date(2025, 1, 5))
        bl.record_outcome("A_B", pnl=-10.0, trade_date=date(2025, 1, 10))
        stats = bl.get_stats()
        assert stats["A_B"]["total_losses"] == 2
        assert stats["A_B"]["total_wins"] == 1
        assert stats["A_B"]["consecutive_losses"] == 1
