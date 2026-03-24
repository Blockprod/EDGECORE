---
type: plan-action
projet: EDGECORE
source_audit: tasks/audits/audit_ai_driven_edgecore.md
date: 2026-03-21
creation: 2026-03-21 à 22:12
modele: claude-sonnet-4.6
---

# PLAN D'ACTION — EDGECORE — 2026-03-21
Sources : `tasks/audits/audit_ai_driven_edgecore.md`
Total : 🔴 0 · 🟠 1 · 🟡 0 · Effort estimé : 2h

> **Note de vérification pré-plan** : Les dettes B5-02 et B2-01 listées dans l'audit
> ont été vérifiées dans le code source — elles sont **déjà corrigées** (voir §Vérifications).
> Seule B2-02 requiert une action résiduelle.

---

## VÉRIFICATIONS PRÉ-PLAN (lecture code réel)

### B5-02 — `slippage = 2.0` hardcodé — ✅ DÉJÀ CORRIGÉ

```python
# execution_engine/router.py:148
slippage = get_settings().costs.slippage_bps   # ← lu depuis CostConfig ✅

# execution_engine/router.py:173
slippage = get_settings().costs.slippage_bps   # ← lu depuis CostConfig ✅
```

**→ Aucune action requise. Dette soldée.**

---

### B2-01 — `TradeOrder` duplique `Order` — ✅ DÉJÀ CORRIGÉ

```bash
grep "class TradeOrder" execution_engine/router.py
# → 0 occurrence
```

Le fichier `execution_engine/router.py` utilise directement `Order` de `execution/base.py`
via `submit_order(order: Order)`. La classe `TradeOrder` n'existe plus.

**→ Aucune action requise. Dette soldée.**

---

### B2-02 — Risk managers instanciés séparément — ⚠️ PARTIELLEMENT RÉSOLU

**Mitigation appliquée (session précédente) :**
```python
# live_trading/runner.py:235-241
self._kill_switch = KillSwitch()
# Inject the shared KillSwitch into RiskFacade so both references
# point to the same object — prevents divergent halt states (B2-02).
self._risk_facade = RiskFacade(
    initial_equity=self.config.initial_capital,
    kill_switch=self._kill_switch,   # ← même instance ✅
)
```

La divergence du KillSwitch est résolue. Mais **deux appels directs subsistent** :

```python
# live_trading/runner.py:474 — check direct kill_switch (redondant mais inoffensif)
if self._kill_switch and self._kill_switch.is_active:
    ...

# live_trading/runner.py:636-643 — PositionRiskManager appelé directement
if self._position_risk:
    risk_ok = self._position_risk.check(...)
    ...
# puis RiskFacade aussi appelé (ligne 647)
if self._risk_facade:
    facade_ok, facade_reason = self._risk_facade.can_enter_trade(...)
```

**Problème résiduel** : `PositionRiskManager.check()` est invoqué séparément de la
`RiskFacade`. Les deux checks s'exécutent en séquence — la `RiskFacade` est censée
être le point d'entrée unifié. Si `RiskFacade.can_enter_trade()` encapsule déjà
`PositionRiskManager`, le double appel est redondant et peut masquer des divergences
de config futures.

**→ Action requise : C-01.**

---

## PHASE 1 — CRITIQUES 🔴

*Aucune correction critique.*

---

## PHASE 2 — MAJEURES 🟠

### [C-01] Supprimer le double appel direct `_position_risk` et `_kill_switch` dans `_tick()`

**Fichier** : `live_trading/runner.py:474` et `live_trading/runner.py:636-643`

**Problème** :
`LiveTradingRunner._tick()` appelle séquentiellement :
1. `self._kill_switch.is_active` directement (ligne 474)
2. `self._position_risk.check()` directement (ligne 636-643)
3. `self._risk_facade.can_enter_trade()` (ligne 647-656)

La `RiskFacade` est censée être le point d'entrée unifié pour tous les checks risk.
Les appels directs à `_kill_switch` et `_position_risk` parallèles à `_risk_facade`
constituent une duplication qui peut dégénérer si `RiskFacade` évolue.

**Vérification préalable requise** :
Confirmer que `RiskFacade.can_enter_trade()` appelle bien en interne :
- `KillSwitch.is_active`
- une forme de position risk check

```powershell
Select-String -Path "risk\facade.py" -Pattern "kill_switch|position_risk|can_enter"
```

**Correction** (si RiskFacade couvre bien ces checks) :
- Supprimer le bloc `if self._kill_switch and self._kill_switch.is_active:` (ligne 474)
  et le remplacer par un appui sur `self._risk_facade`
- Supprimer le bloc `if self._position_risk:` / `risk_ok = self._position_risk.check(...)`
  (lignes 636-643) et laisser uniquement `self._risk_facade.can_enter_trade()`
- Garder `self._position_risk`, `self._portfolio_risk`, `self._kill_switch` instanciés
  séparément (pour monitoring / accès direct par les stops), mais ne pas les appeler
  dans le flow principal d'entrée — déléguer à `RiskFacade`

**Validation** :
```powershell
# 1. Lire risk/facade.py pour confirmer la couverture
# 2. Tests unitaires
venv\Scripts\python.exe -m pytest tests/ -x -q -k "risk or kill_switch or live_trading"
# Attendu : tous passants, aucune régression

# 3. Baseline complète
venv\Scripts\python.exe -m pytest tests/ -q
# Attendu : 2659 passed, 0 failed, 0 skipped

# 4. Risk tier coherence
venv\Scripts\python.exe -c "from config.settings import get_settings; get_settings()._assert_risk_tier_coherence(); print('OK')"
```

**Dépend de** : Aucune

**Statut** : ✅ CORRIGÉ (2026-03-21)

---

## PHASE 3 — MINEURES 🟡

### [C-02] Mettre à jour `tasks/audits/audit_ai_driven_edgecore.md` — dettes soldées

**Fichier** : `tasks/audits/audit_ai_driven_edgecore.md`

**Problème** :
La section 7 "Dettes techniques ouvertes" liste B5-02 et B2-01 comme ouvertes alors
qu'elles ont été vérifiées comme résolues lors de la génération de ce plan.

**Correction** :
Mettre à jour la table des dettes dans l'audit avec les statuts corrects :
- B5-02 → `✅ CORRIGÉ (vérifié 2026-03-21 — router.py:148,173 lit get_settings())`
- B2-01 → `✅ CORRIGÉ (vérifié 2026-03-21 — class TradeOrder absente)`
- B2-02 → `⚠️ PARTIEL — KillSwitch partagé ✅ mais _position_risk encore direct`

**Validation** : Cohérence documentaire — pas de test requis.

**Dépend de** : Aucune

**Statut** : ✅ CORRIGÉ (2026-03-21)

---

## SÉQUENCE D'EXÉCUTION

```
C-02  (mise à jour audit — 5 min, indépendante)
  ↓
C-01  (refactoring _tick() — lire facade.py, supprimer doubles appels)
```

Démarrer par C-02 (documentation) pour que l'audit soit à jour avant d'éditer le code.

---

## CRITÈRES PASSAGE EN PRODUCTION

- [ ] Zéro 🔴 ouvert (déjà satisfait)
- [ ] pytest tests/ : 100% pass (2659+)
- [ ] mypy risk/ risk_engine/ execution/ : exit 0
- [ ] ruff check . : 0 erreurs
- [ ] Zéro credential IBKR dans les logs
- [ ] Kill-switch persisté au redémarrage
- [ ] Risk tiers cohérents (`_assert_risk_tier_coherence` OK)
- [ ] `EDGECORE_ENV=prod` dans Dockerfile (pas "production") ← ✅ déjà conforme
- [ ] Paper trading validé avant live

---

## TABLEAU DE SUIVI

| ID | Titre | Sévérité | Fichier | Effort | Statut | Date |
|----|-------|----------|---------|--------|--------|------|
| C-01 | Supprimer double appel `_position_risk` + `_kill_switch` direct dans `_tick()` | 🟠 MAJEURE | `live_trading/runner.py:474,636` | 30 min | ✅ | 2026-03-21 |
| C-02 | Mettre à jour audit — B5-02 et B2-01 soldées | 🟡 MINEURE | `tasks/audits/audit_ai_driven_edgecore.md` | 5 min | ✅ | 2026-03-21 |
| — | B5-02 slippage hardcodé | ✅ RÉSOLU | `execution_engine/router.py:148,173` | — | ✅ | 2026-03-21 |
| — | B2-01 TradeOrder duplique Order | ✅ RÉSOLU | `execution_engine/router.py` | — | ✅ | 2026-03-21 |
