---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: tasks/corrections/plans/plan_data_staleness_structural_break_2026-04-16.md
derniere_revision: 2026-04-16  # commit d859af1 — P1+P2+P3 implémentés, 2809 tests OK
creation: 2026-04-16 à 17:49
---

# Plan de correction — Données périmées & cassures structurelles
**Date incident** : 2026-04-16  
**Origine** : Analyse log session 12:34 UTC+2 — tick #1

---

## Contexte

Au démarrage du bot le 16 avril, deux anomalies critiques ont été détectées :

1. **Lag données = 34.6 heures** (DUK, SO) — la session entière du 15 avril est absente
2. **Cassure structurelle double** sur la paire 1 (cusum+beta) et cassure CUSUM extrême sur la paire 2 (stat=9.96), qui a perdu sa cointégration (p=0.355)
3. **Encodage log** : `│` (U+2502) rendu `Ã"Ã‡Ã¶` — problème cosmétique, aucun impact opérationnel

---

## Actions à mener

### P0 — Diagnostiquer l'absence de données du 15 avril

**Fichiers cibles** : `data/loader.py`, `data/intraday_loader.py`, `live_trading/runner.py`

- [x] **P0-01** : Vérifier les logs du 15 avril dans `logs/` — `ibkr_sync_gateway` connecté 18s (12:42:09→12:42:27) puis déconnecté ; cache stale Yahoo/disk utilisé sans alerte
- [x] **P0-02** : Erreurs 162/200/354 déjà correctement gérées dans `ibkr_sync_gateway.py` — interrompent et appellent `cancelHistoricalData`
- [x] **P0-03** : `data_max_age_hours` existait déjà dans `TradingConfig` (paper=4h, prod=2h) — couvert par P1
- [x] **P0-04** : Couvert par la garde P1 qui bloque tout signal si lag > seuil

---

### P1 — Ajouter une garde de staleness bloquante au démarrage

**Fichiers cibles** : `live_trading/runner.py`, `config/settings.py`

- [x] **P1-01** : Garde ajoutée dans `_tick()` (`live_trading/runner.py`) — bloque signaux si TOUS les symboles actifs > `data_max_age_hours`
- [x] **P1-02** : Log `CRITICAL 'live_trading_all_data_stale_signals_blocked'` + stops toujours exécutés pour protéger positions ouvertes
- [x] **P1-03** : Lu via `getattr(self.config, 'data_max_age_hours', 99999.0)` → `get_settings()` — aucune valeur hardcodée

---

### P2 — Gestion des paires post-cassure structurelle

**Fichiers cibles** : `models/structural_break.py`, `signal_engine/signal_generator.py`, `strategies/pair_cache_manager.py`

- [x] **P2-01** : `StrategyConfig.structural_break_cooldown_bars = 10` ajouté ; `_break_cooldown: dict[str, int]` dans `SignalGenerator` — paire supprimée N bars post-break
- [x] **P2-02** : Confirmé — `SignalGenerator` ne génère aucun signal si `is_cointegrated=False` (chemin existant)
- [x] **P2-03** : `pair_suspended` WARNING loggé avec `cusum_break`, `beta_break`, `cooldown_bars`, `both_criteria`

---

### P3 — Correction encodage logs (cosmétique)

**Fichiers cibles** : `live_trading/runner.py` ou le handler de logging racine

- [x] **P3-01** : Handlers identifiés : `monitoring/logging_config.py::setup_logging()` + `scripts/run_paper_tick.py` démarrage
- [x] **P3-02** : `TextIOWrapper.reconfigure(encoding="utf-8")` ajouté sur `StreamHandler` dans les deux fichiers (guard `isinstance(..., io.TextIOWrapper)`)
- [ ] **P3-03** : À valider sur le prochain démarrage réel que `│` s'affiche correctement

---

## Priorités et séquence

```
P0-01 → P0-02 → P0-03   (diagnostic d'abord, avant toute correction)
        ↓
P1-01 → P1-02 → P1-03   (garde bloquante : empêche de rejouer le scénario)
        ↓
P2-01 → P2-02 → P2-03   (protection signaux post-cassure)
        ↓
P3-01 → P3-02 → P3-03   (cosmétique, dernier)
```

---

## Critères de validation

| ID | Test attendu |
|----|-------------|
| P0 | Log du 15 avril identifié ou absence expliquée |
| P1 | Bot refuse d'émettre des signaux si lag > seuil ; loggé en CRITICAL |
| P2 | Paire avec `is_cointegrated=False` n'apparaît pas dans les signaux actifs |
| P3 | Logs affichent `│` sans caractères parasites |

---

## Fichiers à ne pas modifier sans précaution

- `risk_engine/kill_switch.py` → adapter `risk/facade.py` en parallèle
- `config/settings.py` → toujours via `get_settings()`, jamais de valeur hardcodée
