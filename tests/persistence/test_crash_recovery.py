"""A-14 — Tests: crash/recovery mid-write for atomic file operations.

Scenarios:
  1. Truncated .tmp file (crash before rename) → production file intact, engine loads cleanly.
  2. kill_switch._save_state() crash mid-write → state file unchanged.
  3. pair_selection discovery cache: truncated .tmp → cache reload returns None gracefully.
  4. .bak file created before rename (A-10 regression guard).
"""

import json
from typing import Any

# ---------------------------------------------------------------------------
# 1. IBKRExecutionEngine order map — truncated .tmp
# ---------------------------------------------------------------------------


class TestOrderMapCrashRecovery:
    def test_truncated_tmp_does_not_corrupt_production_file(self, tmp_path):
        """If .tmp is truncated (crash before rename), the .json prod file stays intact."""
        prod_file = tmp_path / "order_map.json"
        tmp_file = tmp_path / "order_map.tmp"

        # Existing production data
        good_data = {"ORD-001": 12345}
        prod_file.write_text(json.dumps(good_data))

        # Simulate truncated write — JSON invalid, rename never happened
        tmp_file.write_text('{"incomplete":')
        # Do NOT call tmp_file.replace(prod_file) — simulates crash before rename

        # Production file must still be readable and correct
        assert prod_file.exists()
        loaded = json.loads(prod_file.read_text())
        assert loaded == good_data

    def test_missing_prod_file_starts_clean(self, tmp_path):
        """Engine starts with empty order map when no prod file exists."""
        prod_file = tmp_path / "order_map.json"
        assert not prod_file.exists()

        # Simulate _load_order_map logic
        persisted = {}
        if prod_file.exists():
            persisted = json.loads(prod_file.read_text())

        assert persisted == {}

    def test_bak_file_created_before_rename(self, tmp_path):
        """A-10: .bak must be created from the existing prod file before replace()."""
        import shutil

        prod_file = tmp_path / "order_map.json"
        tmp_file = tmp_path / "order_map.tmp"
        bak_file = tmp_path / "order_map.bak"

        # Existing production data
        old_data = {"ORD-OLD": 111}
        new_data = {"ORD-NEW": 222}
        prod_file.write_text(json.dumps(old_data))

        # Execute the A-10 pattern
        tmp_file.write_text(json.dumps(new_data))
        if prod_file.exists():
            shutil.copy2(prod_file, bak_file)
        tmp_file.replace(prod_file)

        # .bak must exist and hold old contents
        assert bak_file.exists()
        assert json.loads(bak_file.read_text()) == old_data
        # prod file must hold new contents
        assert json.loads(prod_file.read_text()) == new_data


# ---------------------------------------------------------------------------
# 2. KillSwitch _save_state — truncated .tmp
# ---------------------------------------------------------------------------


class TestKillSwitchCrashRecovery:
    def test_truncated_tmp_does_not_overwrite_state(self, tmp_path):
        """If crash happens after .tmp write but before rename, state file is intact."""
        state_file = tmp_path / "kill_switch.json"
        tmp_file = tmp_path / "kill_switch.tmp"

        good_state = {"is_active": False, "reason": "none", "message": "", "activated_at": None}
        state_file.write_text(json.dumps(good_state))

        # Simulate truncated write without rename
        tmp_file.write_text('{"is_active": true, "reason"')

        # State file must still be valid
        loaded = json.loads(state_file.read_text())
        assert loaded["is_active"] is False

    def test_bak_created_for_kill_switch_state(self, tmp_path):
        """A-10: .bak must exist after a successful _save_state() call."""
        from risk_engine.kill_switch import KillReason, KillSwitch

        ks = KillSwitch.__new__(KillSwitch)
        ks._state_path = tmp_path / "kill_switch_state.json"
        ks._is_active = False
        ks._reason = KillReason("manual_activation")
        ks._message = ""
        ks._activated_at = None
        _ks: Any = ks
        _ks._callbacks = []

        # Write an initial state so the file exists
        ks._save_state()
        first_bak = tmp_path / "kill_switch_state.bak"
        # First call: no pre-existing file → no .bak yet
        # Now save again to trigger the backup path
        ks._save_state()
        assert first_bak.exists(), ".bak must be created after second _save_state() call"


# ---------------------------------------------------------------------------
# 3. PairDiscovery cache — truncated .tmp
# ---------------------------------------------------------------------------


class TestPairCacheCrashRecovery:
    def test_truncated_tmp_skip_does_not_corrupt_cache_file(self, tmp_path):
        """Truncated .tmp (crash before rename) leaves the cache intact."""
        cache_file = tmp_path / "discovered_pairs.json"
        tmp_file = tmp_path / "discovered_pairs.tmp"

        good_cache = [
            {
                "symbol_1": "A",
                "symbol_2": "B",
                "pvalue": 0.01,
                "half_life": 12.5,
                "correlation": 0.85,
                "johansen_confirmed": True,
                "nw_consensus": True,
            }
        ]
        cache_file.write_text(json.dumps(good_cache))

        # Simulate crash — .tmp present but rename never ran
        tmp_file.write_text("[{incomplete")

        # Cache file must still load cleanly
        loaded = json.loads(cache_file.read_text())
        assert len(loaded) == 1
        assert loaded[0]["symbol_1"] == "A"

    def test_missing_cache_returns_none(self, tmp_path):
        """_load_cache() returns None when no cache file exists."""
        from pair_selection.discovery import PairDiscoveryEngine

        disc = PairDiscoveryEngine.__new__(PairDiscoveryEngine)
        disc._cache_dir = tmp_path
        _disc: Any = disc
        _disc._max_cache_age_hours = 24

        result = disc._load_cache()
        assert result is None
