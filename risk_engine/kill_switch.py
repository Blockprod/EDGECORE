"""
Kill Switch ÔÇö Emergency trading halt mechanism.

The kill switch is the **last line of defense** for a production trading
system.  It monitors multiple risk dimensions and **immediately halts
all trading** when any critical threshold is breached.

Kill conditions:
    1. Portfolio drawdown exceeds hard limit
    2. Daily loss exceeds limit
    3. Consecutive loss streak exceeds limit
    4. Extreme market volatility (regime = HIGH + vol spike)
    5. Data staleness (no fresh data for > N seconds)
    6. Manual kill via ``activate()``

Once triggered:
    - Global ``is_active`` flag is set to True
    - All new entries are blocked
    - Close-all-positions order is recommended
    - Alert is emitted via configured channels
    - **Manual reset** is required before trading resumes

This module is intentionally simple and has NO dependencies on
strategy logic ÔÇö it only reads portfolio-level metrics.
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Callable

from structlog import get_logger

logger = get_logger(__name__)


class KillReason(Enum):
    """Reason codes for kill switch activation."""

    DRAWDOWN = "drawdown_breach"
    DAILY_LOSS = "daily_loss_breach"
    CONSECUTIVE_LOSSES = "consecutive_loss_streak"
    VOLATILITY_EXTREME = "extreme_volatility"
    DATA_STALE = "data_staleness"
    MANUAL = "manual_activation"
    EXCHANGE_ERROR = "exchange_error"
    UNKNOWN = "unknown"


@dataclass
class KillSwitchConfig:
    """Kill switch thresholds — intentionally conservative."""

    max_drawdown_pct: float = 0.15
    max_daily_loss_pct: float = 0.03
    max_consecutive_losses: int = 5
    max_data_stale_seconds: int = 300
    extreme_vol_multiplier: float = 3.0
    alert_on_activation: bool = True
    cooldown_seconds: int = 0
    """Minimum seconds between activation and reset (C-15).
    Default 0 disables the cooldown (backwards-compatible).
    Set to 300 in production to enforce a 5-minute review period."""


@dataclass
class KillSwitchState:
    """Snapshot of kill switch status."""

    is_active: bool
    reason: KillReason
    message: str
    activated_at: datetime | None
    checks_passed: int
    checks_failed: int


class KillSwitch:
    """
    Emergency trading halt mechanism.

    Usage::

        ks = KillSwitch()

        # Each bar ÔÇö run health checks:
        ks.check(
            drawdown_pct=0.12,
            daily_loss_pct=0.01,
            consecutive_losses=2,
            seconds_since_last_data=30,
            current_vol=0.02,
            historical_vol_mean=0.01,
        )

        # Before any order:
        if ks.is_active:
            # HALT ÔÇö do not trade
            ...

        # Manual activation:
        ks.activate(KillReason.MANUAL, "Operator initiated shutdown")

        # Manual reset (requires explicit operator action):
        ks.reset()
    """

    def __init__(
        self,
        config: KillSwitchConfig | None = None,
        on_activate: Callable[[KillReason, str], None] | None = None,
        state_file: str | None = None,
    ):
        """
        Args:
            config: Kill switch thresholds.
            on_activate: Optional callback invoked on activation.
                Signature: ``(reason, message) -> None``.
                Use this to wire alert channels (Slack, email, PagerDuty).
            state_file: Path to persist kill switch state (survives crashes).
                Defaults to ``data/kill_switch_state.json``.
        """
        self.config = config or KillSwitchConfig()
        self._on_activate = on_activate
        self._state_path = Path(state_file or "data/kill_switch_state.json")
        self._state_path.parent.mkdir(parents=True, exist_ok=True)

        self._is_active: bool = False
        self._reason: KillReason = KillReason.UNKNOWN
        self._message: str = ""
        self._activated_at: datetime | None = None
        self._check_count: int = 0
        self._fail_count: int = 0
        self._activation_history: list[dict] = []
        self._activation_lock = threading.Lock()  # A-16: makes check-then-set atomic

        # Restore state from disk (crash recovery)
        self._load_state()

        logger.info(
            "kill_switch_initialized",
            max_dd=f"{self.config.max_drawdown_pct:.0%}",
            max_daily_loss=f"{self.config.max_daily_loss_pct:.0%}",
            max_consec=self.config.max_consecutive_losses,
        )

    # ------------------------------------------------------------------
    # Main check (called every bar / heartbeat)
    # ------------------------------------------------------------------

    def check(
        self,
        drawdown_pct: float = 0.0,
        daily_loss_pct: float = 0.0,
        consecutive_losses: int = 0,
        seconds_since_last_data: float = 0.0,
        current_vol: float = 0.0,
        historical_vol_mean: float = 0.0,
    ) -> bool:
        """
        Run all kill switch checks.

        Args:
            drawdown_pct: Current portfolio drawdown (0.0 ÔÇô 1.0).
            daily_loss_pct: Today's cumulative loss as fraction of equity.
            consecutive_losses: Current consecutive loss streak count.
            seconds_since_last_data: Seconds since last fresh market data.
            current_vol: Current realized volatility.
            historical_vol_mean: Historical mean volatility.

        Returns:
            True if kill switch is (now) active.
        """
        if self._is_active:
            return True

        self._check_count += 1

        # Check 1: Drawdown
        if drawdown_pct >= self.config.max_drawdown_pct:
            self.activate(
                KillReason.DRAWDOWN,
                f"Drawdown {drawdown_pct:.2%} >= {self.config.max_drawdown_pct:.0%}",
            )
            return True

        # Check 2: Daily loss
        if daily_loss_pct >= self.config.max_daily_loss_pct:
            self.activate(
                KillReason.DAILY_LOSS,
                f"Daily loss {daily_loss_pct:.2%} >= {self.config.max_daily_loss_pct:.0%}",
            )
            return True

        # Check 3: Consecutive losses
        if consecutive_losses >= self.config.max_consecutive_losses:
            self.activate(
                KillReason.CONSECUTIVE_LOSSES,
                f"{consecutive_losses} consecutive losses >= {self.config.max_consecutive_losses}",
            )
            return True

        # Check 4: Data staleness
        if seconds_since_last_data > self.config.max_data_stale_seconds:
            self.activate(
                KillReason.DATA_STALE,
                f"No fresh data for {seconds_since_last_data:.0f}s (limit: {self.config.max_data_stale_seconds}s)",
            )
            return True

        # Check 5: Extreme volatility
        if historical_vol_mean > 0 and current_vol > historical_vol_mean * self.config.extreme_vol_multiplier:
            self.activate(
                KillReason.VOLATILITY_EXTREME,
                f"Vol {current_vol:.4f} > {self.config.extreme_vol_multiplier}├ù "
                f"historical mean {historical_vol_mean:.4f}",
            )
            return True

        return False

    # ------------------------------------------------------------------
    # Activation / Reset
    # ------------------------------------------------------------------

    def activate(self, reason: KillReason, message: str) -> None:
        """Activate the kill switch (halt all trading)."""
        # A-16: check-then-set is atomic under the lock
        with self._activation_lock:
            if self._is_active:
                return  # already active
            self._is_active = True
            self._reason = reason
            self._message = message
            self._activated_at = datetime.now()
            self._fail_count += 1
            self._activation_history.append(
                {
                    "reason": reason.value,
                    "message": message,
                    "timestamp": self._activated_at.isoformat(),
                }
            )

        logger.critical(
            "KILL_SWITCH_ACTIVATED",
            reason=reason.value,
            message=message,
        )

        self._save_state()

        if self._on_activate:
            try:
                self._on_activate(reason, message)
            except Exception as exc:
                logger.error("kill_switch_callback_failed", error=str(exc))

    def reset(self) -> None:
        """
        Reset the kill switch (manual operator action).

        This should ONLY be called after the operator has reviewed
        the situation and confirmed it is safe to resume trading.
        """
        # A-16: reset under lock so it never races with activate()
        with self._activation_lock:
            if not self._is_active:
                return
            # C-15: enforce cooldown — warn and abort if not enough time has elapsed
            if self.config.cooldown_seconds > 0 and self._activated_at is not None:
                elapsed = (datetime.now() - self._activated_at).total_seconds()
                if elapsed < self.config.cooldown_seconds:
                    remaining = self.config.cooldown_seconds - elapsed
                    logger.warning(
                        "kill_switch_reset_blocked_cooldown",
                        cooldown_seconds=self.config.cooldown_seconds,
                        elapsed_seconds=round(elapsed, 1),
                        remaining_seconds=round(remaining, 1),
                    )
                    return
            self._is_active = False
            prev_reason = self._reason
            prev_message = self._message
            prev_activated_at = self._activated_at
            self._reason = KillReason.UNKNOWN
            self._message = ""
            self._activated_at = None

        logger.warning(
            "KILL_SWITCH_RESET",
            was_reason=prev_reason.value,
            was_message=prev_message,
            duration_seconds=((datetime.now() - prev_activated_at).total_seconds() if prev_activated_at else 0),
        )

        self._save_state()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _save_state(self) -> None:
        """Persist current activation state to disk.

        RISK-4: If persistence fails the kill-switch enters a
        fail-safe *active* state to prevent trading without an
        accurate on-disk record.
        """
        state = {
            "is_active": self._is_active,
            "reason": self._reason.value,
            "message": self._message,
            "activated_at": self._activated_at.isoformat() if self._activated_at else None,
        }
        try:
            # Atomic write: .tmp ÔåÆ rename
            tmp_path = self._state_path.with_suffix(".tmp")
            tmp_path.write_text(json.dumps(state, indent=2))
            # A-10: backup existing state file before overwrite
            if self._state_path.exists():
                import shutil

                shutil.copy2(self._state_path, self._state_path.with_suffix(".bak"))
            tmp_path.replace(self._state_path)
        except Exception as exc:
            logger.critical(
                "kill_switch_state_save_failed_activating_fail_safe",
                error=str(exc)[:120],
            )
            # Fail-safe: force active so we never trade without persisted state
            self._is_active = True
            self._message = f"FAIL-SAFE: state save failed ({exc})"
            raise

    def _load_state(self) -> None:
        """Restore activation state from disk (if file exists).

        RISK-4: If the state file is corrupted the kill-switch
        activates in fail-safe mode ÔÇö refusing to trade until
        an operator manually clears the state.
        """
        if not self._state_path.exists():
            return
        try:
            data = json.loads(self._state_path.read_text())
            if data.get("is_active"):
                self._is_active = True
                self._reason = KillReason(data.get("reason", "unknown"))
                self._message = data.get("message", "restored from disk")
                ts = data.get("activated_at")
                self._activated_at = datetime.fromisoformat(ts) if ts else datetime.now()
                logger.critical(
                    "KILL_SWITCH_RESTORED_FROM_DISK",
                    reason=self._reason.value,
                    message=self._message,
                )
        except Exception as exc:
            logger.critical(
                "kill_switch_state_load_failed_activating_fail_safe",
                error=str(exc)[:120],
            )
            # Fail-safe: activate kill-switch if state is unreadable
            self._is_active = True
            self._message = f"FAIL-SAFE: corrupt state file ({exc})"

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------

    @property
    def is_active(self) -> bool:
        """True if trading is halted."""
        # A-16: read under lock for happens-before guarantee
        with self._activation_lock:
            return self._is_active

    @property
    def reason(self) -> KillReason:
        return self._reason

    def get_state(self) -> KillSwitchState:
        """Return a state snapshot."""
        return KillSwitchState(
            is_active=self._is_active,
            reason=self._reason,
            message=self._message,
            activated_at=self._activated_at,
            checks_passed=self._check_count - self._fail_count,
            checks_failed=self._fail_count,
        )

    @property
    def activation_history(self) -> list[dict]:
        """Return full activation history (for audit)."""
        return list(self._activation_history)
