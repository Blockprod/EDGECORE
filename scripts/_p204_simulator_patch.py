"""
P2-04 patch: replace method bodies in strategy_simulator.py with delegations
to PositionTracker and BacktestSectorExposureManager.

Run once: venv\\Scripts\\python.exe scripts\\_p204_simulator_patch.py
"""

import re
from pathlib import Path

TARGET = Path("backtests/strategy_simulator.py")
content = TARGET.read_text(encoding="utf-8")

# ─────────────────────────────────────────────
# 1. _close_position  → PositionTracker.close_position
# ─────────────────────────────────────────────
_CLOSE_OLD = re.compile(
    r"    def _close_position\(\r?\n"
    r"        self,\r?\n"
    r"        pos: dict,\r?\n"
    r"        prices_df: pd\.DataFrame,\r?\n"
    r"        bar_idx: int,\r?\n"
    r"    \) -> tuple\[float, float, int\]:.*?"
    r"        return daily_realized, full_trade, holding_days",
    re.DOTALL,
)

_CLOSE_NEW = (
    "    def _close_position(\n"
    "        self,\n"
    "        pos: dict,\n"
    "        prices_df: pd.DataFrame,\n"
    "        bar_idx: int,\n"
    "    ) -> tuple[float, float, int]:\n"
    '        """Close *pos* at *bar_idx* \u2014 delegates to PositionTracker."""\n'
    "        return self._position_tracker.close_position(pos, prices_df, bar_idx)"
)

result = _CLOSE_OLD.sub(_CLOSE_NEW, content, count=1)
assert result != content, "FAIL: _close_position not matched"
print("OK: _close_position replaced")
content = result

# ─────────────────────────────────────────────
# 2. _compute_spread  → PositionTracker.compute_spread
# ─────────────────────────────────────────────
_SPREAD_OLD = re.compile(
    r"    @staticmethod\r?\n"
    r"    def _compute_spread\(\r?\n"
    r"        prices_df: pd\.DataFrame,\r?\n"
    r"        sym1: str,\r?\n"
    r"        sym2: str,\r?\n"
    r"    \) -> pd\.Series \| None:.*?"
    r"        except Exception:\r?\n"
    r"            return None",
    re.DOTALL,
)

_SPREAD_NEW = (
    "    @staticmethod\n"
    "    def _compute_spread(\n"
    "        prices_df: pd.DataFrame,\n"
    "        sym1: str,\n"
    "        sym2: str,\n"
    "    ) -> pd.Series | None:\n"
    '        """Delegates to PositionTracker.compute_spread."""\n'
    "        return PositionTracker.compute_spread(prices_df, sym1, sym2)"
)

result = _SPREAD_OLD.sub(_SPREAD_NEW, content, count=1)
assert result != content, "FAIL: _compute_spread not matched"
print("OK: _compute_spread replaced")
content = result

# ─────────────────────────────────────────────
# 3. _volatility_sizing_multiplier  → BacktestSectorExposureManager.volatility_sizing_multiplier
# ─────────────────────────────────────────────
_VOL_OLD = re.compile(
    r"    @staticmethod\r?\n"
    r"    def _volatility_sizing_multiplier\(\r?\n"
    r"        prices_df: pd\.DataFrame,\r?\n"
    r"        sym1: str,\r?\n"
    r"        sym2: str,\r?\n"
    r"        lookback: int = 60,\r?\n"
    r"    \) -> float:.*?"
    r"        except Exception:\r?\n"
    r"            return 1\.0\r?\n"
    r"\r?\n"
    r"    @staticmethod\r?\n"
    r"    def _estimate_sigma",
    re.DOTALL,
)

_VOL_NEW = (
    "    @staticmethod\n"
    "    def _volatility_sizing_multiplier(\n"
    "        prices_df: pd.DataFrame,\n"
    "        sym1: str,\n"
    "        sym2: str,\n"
    "        lookback: int = 60,\n"
    "    ) -> float:\n"
    '        """Delegates to BacktestSectorExposureManager.volatility_sizing_multiplier."""\n'
    "        return BacktestSectorExposureManager.volatility_sizing_multiplier(\n"
    "            prices_df, sym1, sym2, lookback\n"
    "        )\n"
    "\n"
    "    @staticmethod\n"
    "    def _estimate_sigma"
)

result = _VOL_OLD.sub(_VOL_NEW, content, count=1)
assert result != content, "FAIL: _volatility_sizing_multiplier not matched"
print("OK: _volatility_sizing_multiplier replaced")
content = result

# ─────────────────────────────────────────────
# 4. _estimate_sigma  → PositionTracker.estimate_sigma
# ─────────────────────────────────────────────
_SIGMA_OLD = re.compile(
    r"    @staticmethod\r?\n"
    r"    def _estimate_sigma\(\r?\n"
    r"        prices_df: pd\.DataFrame,\r?\n"
    r"        symbol: str,\r?\n"
    r"        lookback: int = 60,\r?\n"
    r"    \) -> float:.*?"
    r"        except Exception:\r?\n"
    r"            return 0\.02\r?\n"
    r"\r?\n"
    r"    # ADV estimates",
    re.DOTALL,
)

_SIGMA_NEW = (
    "    @staticmethod\n"
    "    def _estimate_sigma(\n"
    "        prices_df: pd.DataFrame,\n"
    "        symbol: str,\n"
    "        lookback: int = 60,\n"
    "    ) -> float:\n"
    '        """Delegates to PositionTracker.estimate_sigma."""\n'
    "        return PositionTracker.estimate_sigma(prices_df, symbol, lookback)\n"
    "\n"
    "    # ADV estimates"
)

result = _SIGMA_OLD.sub(_SIGMA_NEW, content, count=1)
assert result != content, "FAIL: _estimate_sigma not matched"
print("OK: _estimate_sigma replaced")
content = result

# ─────────────────────────────────────────────
# 5. Remove class-level ADV constants + _MEGA_CAP_SYMBOLS block
#    and replace _estimate_adv with delegation
# ─────────────────────────────────────────────
_ADV_BLOCK_OLD = re.compile(
    r"    # ADV estimates.*?"
    r"    def _estimate_adv\(\r?\n"
    r"        self,\r?\n"
    r"        symbol: str,\r?\n"
    r"        prices_df: pd\.DataFrame,\r?\n"
    r"        notional_per_leg: float,\r?\n"
    r"    \) -> float:.*?"
    r"        return self\._ADV_LARGE_CAP",
    re.DOTALL,
)

_ADV_BLOCK_NEW = (
    "    def _estimate_adv(\n"
    "        self,\n"
    "        symbol: str,\n"
    "        prices_df: pd.DataFrame,\n"
    "        notional_per_leg: float,\n"
    "    ) -> float:\n"
    '        """Delegates to PositionTracker.estimate_adv."""\n'
    "        return self._position_tracker.estimate_adv(symbol, prices_df, notional_per_leg)"
)

result = _ADV_BLOCK_OLD.sub(_ADV_BLOCK_NEW, content, count=1)
assert result != content, "FAIL: _estimate_adv block not matched"
print("OK: _estimate_adv + ADV constants replaced")
content = result

# ─────────────────────────────────────────────
# 6. _compute_sector_exposure  → BacktestSectorExposureManager.compute_sector_exposure
# ─────────────────────────────────────────────
_SECTOR_OLD = re.compile(
    r"    def _compute_sector_exposure\(\r?\n"
    r"        self,\r?\n"
    r"        positions: dict\[str, dict\],\r?\n"
    r"        portfolio_value: float,\r?\n"
    r"    \) -> dict\[str, float\]:.*?"
    r"        return \{s: \(n / portfolio_value\) \* 100\.0 for s, n in sector_notional\.items\(\)\}",
    re.DOTALL,
)

_SECTOR_NEW = (
    "    def _compute_sector_exposure(\n"
    "        self,\n"
    "        positions: dict[str, dict],\n"
    "        portfolio_value: float,\n"
    "    ) -> dict[str, float]:\n"
    '        """Delegates to BacktestSectorExposureManager.compute_sector_exposure."""\n'
    "        return self._sector_exposure_manager.compute_sector_exposure(\n"
    "            positions, portfolio_value\n"
    "        )"
)

result = _SECTOR_OLD.sub(_SECTOR_NEW, content, count=1)
assert result != content, "FAIL: _compute_sector_exposure not matched"
print("OK: _compute_sector_exposure replaced")
content = result

# ─────────────────────────────────────────────
# Write back
# ─────────────────────────────────────────────
TARGET.write_text(content, encoding="utf-8")
print("DONE: backtests/strategy_simulator.py patched.")
