"""Réinitialise manuellement le kill-switch après résolution d'un incident.

Usage::

    venv\\Scripts\\python.exe scripts\\reset_kill_switch.py
    venv\\Scripts\\python.exe scripts\\reset_kill_switch.py --force   # bypass confirmation
    venv\\Scripts\\python.exe scripts\\reset_kill_switch.py --status  # afficher l'état seulement

Le script est idempotent : si le kill-switch est inactif, il retourne sans erreur.
Un cooldown est appliqué si ``KillSwitchConfig.cooldown_seconds > 0``.
"""

import sys
from pathlib import Path

# Ajouter la racine du projet au PYTHONPATH pour un appel direct depuis n'importe où
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import UTC, datetime

from structlog import get_logger

logger = get_logger(__name__)


def main() -> None:
    from risk_engine.kill_switch import KillSwitch

    ks = KillSwitch()

    # ------------------------------------------------------------------
    # Mode --status : afficher l'état et quitter
    # ------------------------------------------------------------------
    if "--status" in sys.argv:
        if ks.is_active:
            _state = ks.get_state()
            print(f"[ACTIF]  Raison   : {_state.reason.value}")
            print(f"         Message  : {_state.message or '(aucun)'}")
            if _state.activated_at:
                print(f"         Activé à : {_state.activated_at}")
        else:
            print("[INACTIF] Kill-switch inactif — trading autorisé.")
        return

    # ------------------------------------------------------------------
    # Kill-switch inactif ?
    # ------------------------------------------------------------------
    if not ks.is_active:
        print("Kill-switch inactif — aucune action requise.")
        logger.info("kill_switch_reset_noop", status="already_inactive")
        return

    # ------------------------------------------------------------------
    # Afficher l'état courant
    # ------------------------------------------------------------------
    print("=" * 60)
    print("  ⚠️  KILL-SWITCH ACTIF — TRADING SUSPENDU")
    print("=" * 60)
    _state = ks.get_state()
    print(f"  Raison   : {_state.reason.value}")
    print(f"  Message  : {_state.message or '(aucun)'}")
    if _state.activated_at:
        _activated = _state.activated_at
        _now = datetime.now(UTC)
        _ts = _activated if _activated.tzinfo is not None else _activated.replace(tzinfo=UTC)
        age_s = (_now - _ts).total_seconds()
        print(f"  Activé depuis : {int(age_s // 60)} min {int(age_s % 60)} s")
    print("=" * 60)

    # ------------------------------------------------------------------
    # Confirmation interactive (sauf --force)
    # ------------------------------------------------------------------
    if "--force" not in sys.argv:
        print()
        print("Confirmez que l'incident est résolu avant de reprendre le trading.")
        confirm = input("Réinitialiser le kill-switch ? (oui/non) : ").strip().lower()
        if confirm != "oui":
            print("Annulé. Kill-switch toujours actif.")
            return

    # ------------------------------------------------------------------
    # Réinitialisation
    # ------------------------------------------------------------------
    ks.reset()

    if not ks.is_active:
        print()
        print("✅ Kill-switch réinitialisé. Le trading peut reprendre.")
        logger.warning(
            "kill_switch_reset_manual",
            operator="cli",
            forced="--force" in sys.argv,
        )
    else:
        # reset() peut être bloqué par le cooldown
        print()
        print("⛔ Réinitialisation bloquée (cooldown actif). Réessayez plus tard.")
        logger.warning("kill_switch_reset_blocked_by_cooldown")
        sys.exit(1)


if __name__ == "__main__":
    main()
