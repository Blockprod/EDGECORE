#!/usr/bin/env python3
r"""EDGECORE — Automatic lessons.md updater.

Analyse le dernier commit git et ajoute une entrée DRAFT dans tasks/lessons.md
si la modification est "lesson-worthy" (heuristiques basées sur le message,
les fichiers modifiés et les anti-patterns détectés dans le diff).

Usage :
  venv\Scripts\python.exe scripts\update_lessons.py           # analyse HEAD
  venv\Scripts\python.exe scripts\update_lessons.py --force   # force l'ajout
  venv\Scripts\python.exe scripts\update_lessons.py --dry-run # affiche sans ecrire
  venv\Scripts\python.exe scripts\update_lessons.py --help

Declenche automatiquement via .githooks/post-commit si
  git config core.hooksPath .githooks
est configure (commande d'installation : voir bas de fichier).
"""

import argparse
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# ─── Chemins ─────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
LESSONS_FILE = ROOT / "tasks" / "lessons.md"

# ─── Heuristiques ─────────────────────────────────────────────────────────────

# Préfixes de messages → jamais lesson-worthy (commits non-fonctionnels)
SKIP_PREFIXES = (
    "docs:", "chore:", "style:", "plan(", "merge ", "merge:",
    "bump ", "release", "wip:", "reformat",
)

# Mots-clés dans le message → probablement lesson-worthy
LESSON_KEYWORDS = (
    "fix", "bug", "error", "patch", "revert", "correct",
    "hotfix", "remove", "replace", "broken", "broken",
)

# Chemins critiques → les fichiers modifiés ici augmentent le score
CRITICAL_PATHS = (
    "config/",
    "execution/",
    "execution_engine/",
    "risk/",
    "risk_engine/",
    "live_trading/",
    "data/loader",
    "data/preprocessing",
    "models/",
    "signal_engine/",
)

# Anti-patterns détectables dans le diff (lignes supprimées "-")
# Format : (regex sur lignes supprimées, description erreur, règle à appliquer)
ANTIPATTERNS = [
    (
        r"utcnow\(\)",
        "datetime.utcnow() utilisé au lieu de datetime.now(timezone.utc)",
        "Toujours utiliser datetime.now(timezone.utc). "
        "datetime.utcnow() est deprecated depuis Python 3.12.",
    ),
    (
        r"from research\.",
        "Import depuis research/ dans un module non-research",
        "Importer depuis pair_selection/, models/, ou signal_engine/ exclusivement. "
        "research/ est hors du pipeline de production.",
    ),
    (
        r"EDGECORE_ENV.*production",
        "EDGECORE_ENV=production (valeur invalide) au lieu de prod",
        "Les valeurs valides sont uniquement : dev, test, prod. "
        "La valeur 'production' tombe silencieusement sur dev.yaml.",
    ),
    (
        r"^\+?.*\bprint\s*\(",
        "print() dans du code de production",
        "Utiliser structlog.get_logger(__name__) partout. "
        "print() interdit hors scripts/, examples/, research/.",
    ),
    (
        r"slippage\s*=\s*[\d.]+(?!\s*\*\s*get_settings)",
        "slippage hardcodé au lieu de lire CostConfig",
        "Toujours lire get_settings().costs.slippage_bps. "
        "La valeur hardcodée diverge des backtests.",
    ),
    (
        r"commission\s*=\s*[\d.]+\s*\*\s*[\d.]+\s*\*\s*0\.",
        "commission hardcodée (0.000xx) au lieu de CostConfig",
        "Toujours lire get_settings().costs.commission_bps / 10_000. "
        "Source de vérité : CostConfig.",
    ),
    (
        r"from execution\.modes import",
        "Import depuis execution/modes.py (archivé en modes_legacy.py)",
        "Importer depuis execution/base.py ou execution/modes_legacy.py. "
        "Le fichier modes.py a été archivé (C-09).",
    ),
    (
        r"TradeOrder\b",
        "TradeOrder utilisé au lieu de Order (B2-01)",
        "Utiliser execution.base.Order exclusivement. "
        "TradeOrder est deprecated et sera supprimé.",
    ),
    (
        r"class OrderStatus",
        "Nouvelle définition de OrderStatus (3ème doublon potentiel)",
        "Ne jamais redéfinir OrderStatus. "
        "Source de vérité unique : execution/base.py::OrderStatus (11 états).",
    ),
]

# ─── Git helpers ─────────────────────────────────────────────────────────────


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git"] + list(args),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(ROOT),
    )
    return result.stdout.strip()


def get_commit_info() -> tuple[str, str, str]:
    """Retourne (hash_long, hash_court, message_sujet)."""
    hash_long = _git("log", "-1", "--format=%H")
    hash_short = _git("log", "-1", "--format=%h")
    msg = _git("log", "-1", "--format=%s")
    return hash_long, hash_short, msg


def get_changed_files() -> list[str]:
    out = _git("diff-tree", "--no-commit-id", "-r", "--name-only", "HEAD")
    return [f for f in out.splitlines() if f]


def get_diff() -> str:
    return _git("show", "HEAD", "--unified=3")


# ─── Heuristiques ─────────────────────────────────────────────────────────────


def score_commit(msg: str, files: list[str]) -> tuple[int, str]:
    """
    Retourne (score, raison). Score ≥ 2 → lesson-worthy.
    Score 0 → skip (trop peu d'intérêt).
    """
    score = 0
    reasons = []

    msg_lower = msg.lower()

    # Veto : préfixes non-fonctionnels
    if any(msg_lower.startswith(p) for p in SKIP_PREFIXES):
        return 0, f"veto: préfixe non-fonctionnel ({msg[:30]}...)"

    # Si uniquement des .md modifiés → probablement pas de leçon
    non_md = [f for f in files if not f.endswith(".md")]
    if not non_md:
        return 0, "veto: uniquement des fichiers .md modifiés"

    # Mot-clé "fix" → +2
    if any(kw in msg_lower for kw in LESSON_KEYWORDS):
        score += 2
        reasons.append("mot-clé fix/error/patch")

    # Chemins critiques → +1 par chemin unique
    critical_hits = {
        p for p in CRITICAL_PATHS
        if any(f.startswith(p) for f in non_md)
    }
    if critical_hits:
        score += 1
        reasons.append(f"fichiers critiques: {', '.join(list(critical_hits)[:3])}")

    # Nombre de fichiers Python modifiés (> 2 → +1)
    py_files = [f for f in non_md if f.endswith(".py")]
    if len(py_files) > 2:
        score += 1
        reasons.append(f"{len(py_files)} fichiers .py modifiés")

    reason_str = " · ".join(reasons) if reasons else "aucune raison pertinente"
    return score, reason_str


def detect_antipattern(diff: str) -> tuple[str | None, str | None]:
    """Retourne (erreur, règle) si un anti-pattern connu est détecté dans les lignes supprimées."""
    removed_lines = "\n".join(
        line[1:] for line in diff.splitlines() if line.startswith("-")
    )
    for pattern, erreur, regle in ANTIPATTERNS:
        if re.search(pattern, removed_lines, re.MULTILINE):
            return erreur, regle
    return None, None


# ─── lessons.md helpers ───────────────────────────────────────────────────────


def get_next_lesson_id() -> str:
    if not LESSONS_FILE.exists():
        return "L-01"
    content = LESSONS_FILE.read_text(encoding="utf-8")
    ids = re.findall(r"^## (L-\d+)", content, re.MULTILINE)
    if not ids:
        return "L-01"
    last = max(int(i.split("-")[1]) for i in ids)
    return f"L-{last + 1:02d}"


def is_already_covered(msg: str) -> bool:
    """
    Détection grossière de doublon : si 3+ mots significatifs du message
    apparaissent déjà dans lessons.md → probablement couvert.
    """
    if not LESSONS_FILE.exists():
        return False
    content = LESSONS_FILE.read_text(encoding="utf-8").lower()
    words = [w for w in re.findall(r"\w+", msg.lower()) if len(w) > 4]
    if len(words) < 3:
        return False
    matches = sum(1 for w in words if w in content)
    return matches >= 3


def build_draft(
    lesson_id: str,
    msg: str,
    files: list[str],
    short_hash: str,
    erreur: str | None = None,
    regle: str | None = None,
) -> str:
    date = datetime.now().strftime("%Y-%m-%d")
    py_files = [f for f in files if f.endswith(".py")]
    ref_files = (py_files or files)[:3]
    ref_str = ", ".join(f"`{f}`" for f in ref_files)

    erreur_text = erreur or "[À COMPLÉTER — décrire le problème exact]"
    regle_text = regle or "[À COMPLÉTER — décrire la règle à appliquer]"

    # Contexte minimal auto-généré
    contexte_parts = [f"Commit `{short_hash}` : {msg}"]
    if ref_files:
        contexte_parts.append(f"Fichiers : {', '.join(ref_files[:2])}")
    contexte = ". ".join(contexte_parts)

    return (
        f"\n## {lesson_id} · {msg} [DRAFT — À COMPLÉTER]\n\n"
        f"**Contexte** : {contexte}\n"
        f"**Erreur** : {erreur_text}\n"
        f"**Règle** : {regle_text}\n"
        f"**Ref** : {ref_str} — commit `{short_hash}` ({date})\n\n"
        "---\n"
    )


def append_lesson(draft: str) -> None:
    if not LESSONS_FILE.exists():
        LESSONS_FILE.parent.mkdir(parents=True, exist_ok=True)
        LESSONS_FILE.write_text("# EDGECORE — Leçons apprises\n\n---\n", encoding="utf-8")
    with LESSONS_FILE.open("a", encoding="utf-8") as f:
        f.write(draft)


# ─── Main ─────────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description="EDGECORE lessons.md auto-updater")
    parser.add_argument("--force", action="store_true", help="Ajouter une leçon même si le score est faible")
    parser.add_argument("--dry-run", action="store_true", help="Afficher le draft sans écrire dans lessons.md")
    args = parser.parse_args()

    # 1. Récupère les infos du dernier commit
    _, short_hash, msg = get_commit_info()
    files = get_changed_files()

    if not msg:
        print("[update_lessons] Impossible de lire le dernier commit. Abort.")
        return 1

    print(f"[update_lessons] Commit analysé : {short_hash} — {msg}")
    print(f"[update_lessons] Fichiers modifiés : {len(files)} ({', '.join(files[:4])}{'...' if len(files) > 4 else ''})")

    # 2. Évalue si la leçon est pertinente
    score, reason = score_commit(msg, files)
    print(f"[update_lessons] Score : {score}/4 — {reason}")

    if score < 2 and not args.force:
        print("[update_lessons] Score insuffisant -> aucune lecon ajoutee.")
        return 0

    # 3. Vérifie les doublons
    if is_already_covered(msg) and not args.force:
        print("[update_lessons] Lecon probablement deja couverte -> skip.")
        return 0

    # 4. Détecte un anti-pattern dans le diff
    diff = get_diff()
    erreur, regle = detect_antipattern(diff)
    if erreur:
        print(f"[update_lessons] Anti-pattern détecté : {erreur}")

    # 5. Génère le draft
    lesson_id = get_next_lesson_id()
    draft = build_draft(lesson_id, msg, files, short_hash, erreur, regle)

    print(f"\n[update_lessons] Draft généré :\n{'─' * 60}")
    print(draft.strip())
    print("─" * 60)

    # 6. Écrit (ou dry-run)
    if args.dry_run:
        print("\n[update_lessons] --dry-run : rien écrit.")
        return 0

    append_lesson(draft)
    print(f"\n[update_lessons] ✅ {lesson_id} ajouté dans tasks/lessons.md (DRAFT — à réviser).")
    return 0


if __name__ == "__main__":
    sys.exit(main())


# ─────────────────────────────────────────────────────────────────────────────
# INSTALLATION DU HOOK GIT (une seule fois par machine)
# ─────────────────────────────────────────────────────────────────────────────
# Commande a lancer depuis la racine du projet :
#
#   git config core.hooksPath .githooks
#
# Verification :
#
#   git config core.hooksPath
#   # Attendu : .githooks
#
# Le hook .githooks/post-commit appelle ce script automatiquement
# apres chaque `git commit`.
# ─────────────────────────────────────────────────────────────────────────────
