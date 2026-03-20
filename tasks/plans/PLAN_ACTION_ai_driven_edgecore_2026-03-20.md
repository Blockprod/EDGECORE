# Plan de migration priorisé — AI-Driven File Engineering
*EDGECORE V1 — 2026-03-20*

---

## ÉTAPE 0 — État des lieux (résultat)

| Fichier | Statut | Action effectuée |
|---------|--------|-----------------|
| `.github/copilot-instructions.md` | ✅ COMPLET | — |
| `.claude/context.md` | ✅ MIS À JOUR | Dettes B5-01 et B4-05 marquées CORRIGÉ |
| `.claude/rules.md` | ✅ MIS À JOUR | Compteur tests 2654 → 2659 |
| `architecture/decisions.md` | ✅ COMPLET | — |
| `architecture/system_design.md` | ✅ CRÉÉ | Nouveau fichier — architecture complète |
| `knowledge/ibkr_constraints.md` | ✅ COMPLET | — |
| `knowledge/trading_constraints.md` | ✅ CRÉÉ | Nouveau fichier — contraintes trading |
| `agents/quant_researcher.md` | ✅ COMPLET | — |
| `agents/risk_manager.md` | ✅ COMPLET | — |
| `agents/code_auditor.md` | ✅ MIS À JOUR | Compteur tests 2654 → 2659 |
| `agents/dev_engineer.md` | ✅ COMPLET | — |

---

## ÉTAPE 1 — Nettoyage (résultat)

**Rien à faire.** Le workspace était déjà propre :
- `CMakeLists.txt` → absent ✅
- `debug_*.txt` / `bt_out*.txt` à la racine → absent ✅
- `scripts/run_backtest_v*.py` (versionnés) → absent ✅
- `ARCHIVED_cpp_sources/`, `ARCHIVED_crypto/` → absent ✅

---

## ÉTAPE 2 — Arborescence cible (état final)

```
.github/
  copilot-instructions.md    ✅ COMPLET

.claude/
  context.md                 ✅ COMPLET (B5-01 + B4-05 marqués CORRIGÉ)
  rules.md                   ✅ COMPLET (baseline 2659)

architecture/
  decisions.md               ✅ COMPLET (ADR-001 à ADR-007+)
  system_design.md           ✅ CRÉÉ   (architecture complète)

knowledge/
  ibkr_constraints.md        ✅ COMPLET
  trading_constraints.md     ✅ CRÉÉ   (contraintes trading)

agents/
  quant_researcher.md        ✅ COMPLET
  risk_manager.md            ✅ COMPLET
  code_auditor.md            ✅ COMPLET (baseline 2659)
  dev_engineer.md            ✅ COMPLET
```

---

## ÉTAPE 4 — Migrations restantes (priorité décroissante)

### Priorité HAUTE — Dettes techniques ouvertes (bloquant prod)

| ID | Fichier | Action | Effort |
|----|---------|--------|--------|
| B5-02 | `execution_engine/router.py:~162,~189` | Remplacer `slippage = 2.0` hardcodé par `get_settings().costs.slippage_bps` | 0.5j |
| B2-01 | `execution_engine/router.py` | Unifier `TradeOrder` avec `Order` de `execution/base.py` | 2j (breaking change) |
| B2-02 | `live_trading/runner.py:~224-231` | Consolider `PositionRiskManager` + `PortfolioRiskManager` + `KillSwitch` dans `RiskFacade` | 1j |

### Priorité MOYENNE — Qualité des agents

| Fichier | Action | Effort |
|---------|--------|--------|
| `agents/code_auditor.md` | Mettre à jour la section "Rapport d'audit attendu" pour inclure les nouvelles colonnes après audit structurel | 0.25j |
| `.claude/context.md` | Vérifier les numéros de ligne de B2-02 (`live_trading/runner.py`) après refactoring RiskFacade | 0.25j |

### Priorité BASSE — Documentation complémentaire

| Fichier | Action | Raison |
|---------|--------|--------|
| `knowledge/ibkr_constraints.md` | Ajouter section "Trading Hours" (9h30-16h ET, pré-market exclus) | Absent actuellement |
| `architecture/decisions.md` | ADR-008 : Signal Combiner weights calibration (0.70/0.30) | Décision non documentée |
| `agents/quant_researcher.md` | Ajouter checklist OOS re-benchmarking (quand les params de `trading_constraints.md` changent) | Cohérence |

---

## Critères de succès final

```powershell
# 1. Tests — baseline maintenue
venv\Scripts\python.exe -m pytest tests/ -q
# Attendu : 2659 passed, 0 failed, 0 skipped

# 2. Aucun DeprecationWarning utcnow
venv\Scripts\python.exe -m pytest tests/ -W error::DeprecationWarning -q

# 3. Types corrects
mypy risk/ risk_engine/ execution/

# 4. Lint propre
ruff check .

# 5. Risk tier coherence
venv\Scripts\python.exe -c "from config.settings import get_settings; get_settings()._assert_risk_tier_coherence(); print('OK')"

# 6. Config prod valide
$env:EDGECORE_ENV="prod"; venv\Scripts\python.exe -c "from config.settings import get_settings; s=get_settings(); print('prod OK:', s.strategy.entry_z_score)"
```

---

## Suivi des fichiers créés/modifiés (ce sprint)

```
ADDED   architecture/system_design.md
ADDED   knowledge/trading_constraints.md
MODIFIED .claude/rules.md          (compteur 2654→2659)
MODIFIED .claude/context.md        (dettes B5-01, B4-05 → CORRIGÉ)
MODIFIED agents/code_auditor.md    (compteur 2654→2659)
```
