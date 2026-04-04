---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: plan_action_edgecore_2026.md
derniere_revision: 2026-03-28
creation: 2026-03-28 à 15:00
---

# Plan d'action priorisé — EDGECORE (mars 2026)

## Synthèse de l'état actuel
- Toutes les briques critiques (slippage, Kelly, signaux, risk, intraday, algo execution) sont codées.
- L'intégration pipeline est souvent partielle : beaucoup de classes prêtes mais non branchées partout (backtest, live, simulateur).
- Les points bloquants sont l'intégration systématique (event filter, borrow, signaux avancés, risk tiers) et l'automatisation (expansion univers, monitoring live).

## Objectif immédiat
> Débloquer la génération de trades réels et fiabiliser le pipeline institutionnel sur la période P5 (v48), puis généraliser à l'ensemble du backtest.

## Priorités (ordre d'exécution)

### 1. Intégration systématique des filtres institutionnels
- [ ] Vérifier et forcer l'appel du **event filter** (earnings/dividend blackout) dans tout le pipeline de génération de signaux (backtest ET live).
- [ ] Vérifier et forcer l'appel du **BorrowChecker** avant chaque short dans le simulateur ET l'exécution live.
- [ ] Ajouter des logs explicites sur chaque rejet (event/borrow) pour analyse fine.

### 2. SignalCombiner et wiring multi-signal
- [ ] Brancher le **SignalCombiner** dans tous les pipelines (backtest, live, simulateur).
- [ ] S'assurer que tous les signaux avancés (OU, cross-sectional, vol, etc.) sont bien pris en compte dans la décision d'entrée.
- [ ] Ajouter un log synthétique du flux de signaux (nombre générés, nombre rejetés, motif de rejet).

### 3. Calibration et validation du sizing institutionnel
- [ ] Vérifier que le **KellySizer** et les plafonds (position, secteur, levier) sont bien appliqués à chaque allocation.
- [ ] Ajouter un test de cohérence sur le respect des plafonds et du stop-loss NAV.
- [ ] Re-backtester v31h et v48 avec sizing institutionnel, comparer DD et Sharpe.

### 4. Monitoring et alerting risk tiers
- [ ] S'assurer que le monitoring **drawdown multi-tier** et **VaR/CVaR** est actif et relié à des alertes (logs, dashboard, email/alerte si possible).
- [ ] Vérifier la présence d'un dashboard sector/correlation et compléter si besoin.

### 5. Automatisation de l'expansion univers
- [ ] Finaliser ou créer un script d'expansion incrémentale de l'univers (ajout 1-par-1, backtest, validation Sharpe/PF, log tableau résultat).

### 6. Intraday & algo execution (si pipeline daily validé)
- [ ] Valider l'intégration des signaux intraday et de l'algo execution (TWAP/VWAP) dans le simulateur et l'exécution live.

## Quick wins immédiats
- [ ] Ajouter un log synthétique du flux de signaux (générés, rejetés, motif) sur P5 pour diagnostiquer le "zéro trade".
- [ ] Forcer l'appel du event filter et du borrow check dans le simulateur.
- [ ] Re-backtester P5 après correction pour valider la reprise de l'activité.

## Suivi
- Ce plan doit être révisé après chaque étape majeure (ex : retour de trades sur P5, validation sizing, etc.).
- Documenter chaque correction dans `tasks/corrections/logs/`.

---
Ce plan est priorisé pour débloquer la stratégie et fiabiliser le pipeline institutionnel avant toute optimisation avancée.
