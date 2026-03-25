---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: audit_pipeline_edgecore.md
derniere_revision: 2026-03-25
creation: 2026-03-25 à 10:00
---

#codebase

Tu es un Senior Engineer spécialisé en systèmes de trading
algorithmique stat-arb et pipelines d'exécution institutionnels.
Tu réalises un audit EXCLUSIVEMENT d'ingénierie du pipeline
stat-arb sur EDGECORE.

Ton objectif : vérifier que le câblage entre la configuration,
le pipeline signal, le backtest et le moteur live est cohérent,
sans dérive silencieuse de paramètre ni divergence de
comportement entre simulation et exécution réelle.

─────────────────────────────────────────────
ÉTAPE 0 — VÉRIFICATION PRÉALABLE (OBLIGATOIRE)
─────────────────────────────────────────────
Vérifie si ce fichier existe déjà :
  tasks/audits/resultats/audit_pipeline_edgecore.md

Si trouvé, affiche :
"⚠️ Audit pipeline existant détecté :
 Fichier : tasks/audits/resultats/audit_pipeline_edgecore.md
 Date    : [date modification]

 [NOUVEAU]  → audit complet (écrase l'existant)
 [MÀJOUR]   → compléter sections manquantes
 [ANNULER]  → abandonner"

Si absent → démarrer directement :
"✅ Aucun audit pipeline existant. Démarrage..."

─────────────────────────────────────────────
SOURCES — LIRE EN PREMIER
─────────────────────────────────────────────
1. config/settings.py                    ← singleton, logique de chargement
2. config/config.yaml                    ← paramètres actifs
3. signal_engine/generator.py            ← génération z-score live
4. signal_engine/combiner.py             ← combinaison z×0.70 + mom×0.30
5. signal_engine/momentum.py             ← signal momentum live
6. backtests/strategy_simulator.py       ← simulation backtest
7. backtests/cost_model.py               ← modèle de coûts backtest
8. models/spread.py                      ← calcul spread live
9. models/kalman_hedge.py                ← hedge ratio live (Kalman)
10. risk_engine/position_risk.py         ← garde-fou position live
11. risk_engine/portfolio_risk.py        ← garde-fou portfolio live
12. risk_engine/kill_switch.py           ← halt global live
13. risk/facade.py                       ← façade unifiée risk
14. portfolio_engine/allocator.py        ← sizing positions
15. execution_engine/router.py           ← routage PAPER/IBKR/BACKTEST
16. live_trading/runner.py               ← boucle principale live

─────────────────────────────────────────────
PÉRIMÈTRE STRICT
─────────────────────────────────────────────
ANALYSE :
- Cohérence des paramètres entre config.yaml, live et backtest
- Pipeline all-or-nothing (gates de guard-fou à chaque étape)
- Données d'entrée du spread (Kalman, z-score, hedge ratio)
- Modélisation des coûts (CostConfig vs hardcodé)
- Alignement du risk engine (RiskFacade vs composants directs)
- Routage d'exécution (Paper vs IBKR, rate limiter)

N'ANALYSE PAS : performance financière, métriques de backtest,
sécurité credentials, architecture modules, Cython interne.

─────────────────────────────────────────────
CONTRAINTES ABSOLUES
─────────────────────────────────────────────
- Cite fichier:ligne pour CHAQUE point factuel
- Conclus chaque sous-section par : CONFORME / NON CONFORME / À VÉRIFIER
- Ne déduis PAS la logique interne des .pyx — traite leurs interfaces
  comme des boîtes noires
- Ne lis PAS les fichiers .md, .txt, .rst, .csv, .json de results/
- Écris "À VÉRIFIER" si la preuve est absente du code

─────────────────────────────────────────────
BLOC 1 — COHÉRENCE DES PARAMÈTRES STRATÉGIQUES
─────────────────────────────────────────────
Source : config/config.yaml + config/settings.py
         + signal_engine/generator.py + signal_engine/combiner.py
         + backtests/strategy_simulator.py

Pour chaque paramètre ci-dessous, vérifier à trois endroits :
(A) valeur déclarée dans config.yaml (section + clé)
(B) valeur injectée dans le backtest (strategy_simulator.py, fichier:ligne)
(C) valeur injectée dans le pipeline live (fichier + ligne)

Si (B) ≠ (A) ou (C) ≠ (A) → dérive de paramètre → 🔴

Paramètres à vérifier :

| Paramètre                  | Section config.yaml  |
|----------------------------|----------------------|
| entry_z_score              | strategy             |
| exit_z_score               | strategy             |
| max_half_life              | strategy             |
| min_correlation            | strategy             |
| short_sizing_multiplier    | strategy             |
| z_score_weight             | signal_combiner      |
| momentum_weight            | signal_combiner      |
| max_drawdown_pct           | risk                 |
| kill_switch.max_drawdown_pct | risk               |
| slippage_bps               | execution            |
| paper_commission_pct       | execution            |

1.1 Backtest — injection des paramètres
    Pour chaque paramètre :
    - Lire la ligne d'injection dans strategy_simulator.py
    - Vérifier qu'elle consomme config.yaml via get_settings()
      (pas une valeur hardcodée)
    - Si une valeur est passée en dur (ex : slippage=2.0) → 🔴

1.2 Live — injection des paramètres
    Pour chaque paramètre :
    - Lire la ligne d'injection dans generator.py, combiner.py,
      ou live_trading/runner.py
    - Vérifier get_settings().section.champ à chaque appel
    - Si une constante est hardcodée → 🔴

1.3 Dérive connue B5-02 — slippage hardcodé
    - execution_engine/router.py lignes ~162 et ~189 :
      slippage=2.0 est-il hardcodé en dur ?
    - Si oui : le backtest utilise-t-il la même valeur
      ou lit-il get_settings().costs.slippage_bps ?
    - Si backtest et live n'utilisent pas la même source → 🟠

─────────────────────────────────────────────
BLOC 2 — PIPELINE ALL-OR-NOTHING
─────────────────────────────────────────────
Source : live_trading/runner.py + risk_engine/kill_switch.py
         + risk_engine/position_risk.py + risk_engine/portfolio_risk.py
         + portfolio_engine/allocator.py + backtests/strategy_simulator.py

Règle : tout VETO dans la chaîne = zéro ordre, zéro trade.

Pipeline live EDGECORE :
  Signal → PositionRiskManager → PortfolioRiskManager → KillSwitch
  → PortfolioAllocator → ExecutionRouter

2.1 KillSwitch.is_triggered → halt global
    - Live : après is_triggered=True, y a-t-il un return/break explicite
      avant tout appel à ExecutionRouter.submit_order() ? (fichier:ligne)
    - Backtest : ce garde-fou est-il reproduit dans strategy_simulator.py ?
      (fichier:ligne)
    - CONFORME / NON CONFORME

2.2 PositionRiskManager.evaluate() → rejet
    - Live : si evaluate() retourne rejected=True, l'ordre est-il
      arrêté avant PortfolioRiskManager ? (fichier:ligne)
    - Backtest : ce contrôle est-il reproduit ? (fichier:ligne)
    - CONFORME / NON CONFORME

2.3 PortfolioRiskManager.evaluate() → rejet
    - Live : garde-fou avant PortfolioAllocator.allocate() ? (fichier:ligne)
    - Backtest : même contrôle ? (fichier:ligne)
    - CONFORME / NON CONFORME

2.4 SignalCombiner score < entry_z_score → aucun signal
    - Live : le seuil entry_z_score est-il vérifié avant d'appeler
      le risk engine ? (fichier:ligne dans generator.py ou runner.py)
    - Backtest : même contrôle à la même position dans la chaîne ?
    - CONFORME / NON CONFORME

2.5 PortfolioAllocator.allocate() → size = 0
    - Live : si quantity = 0 retourné, l'ordre est-il annulé
      avant submit_order() ? (fichier:ligne)
    - Backtest : ce contrôle est-il reproduit ? (fichier:ligne)
    - CONFORME / NON CONFORME

2.6 BrokerReconciler divergence > tolérance
    - Live : si divergence > seuil (config.yaml → trading),
      le runner halt-il les nouvelles entrées ? (fichier:ligne)
    - Ou log uniquement sans halt ? (fichier:ligne)
    - CONFORME / NON CONFORME / À VÉRIFIER

─────────────────────────────────────────────
BLOC 3 — DONNÉES D'ENTRÉE DU SPREAD
─────────────────────────────────────────────
Source : models/spread.py + models/kalman_hedge.py
         + signal_engine/zscore.py + backtests/strategy_simulator.py
         + live_trading/runner.py

3.1 Hedge ratio Kalman — initialisation live vs backtest
    - Live (kalman_hedge.py) : état initial du filtre Kalman
      (P0, Q, R) — source de la valeur ? config.yaml ou hardcodé ?
      (fichier:ligne)
    - Backtest (strategy_simulator.py) : même état initial ?
      Ou Kalman ré-initialisé à chaque paire/période ? (fichier:ligne)
    - Si initialisation différente → les hedge ratios divergeront
      dès la première barre → 🟠

3.2 Fenêtre du z-score — lookback
    - Live (signal_engine/zscore.py ou generator.py) :
      la fenêtre du z-score est-elle dérivée de la demi-vie AR(1)
      de la paire ou fixe (config.yaml) ? (fichier:ligne)
    - Backtest (strategy_simulator.py) : même méthode de calcul
      de la fenêtre ? (fichier:ligne)
    - Si l'un est adaptatif et l'autre fixe → 🟠

3.3 Direction du spread (A − β×B)
    - Live (models/spread.py) : la direction leg1 / leg2
      est-elle fixée à l'entrée de la position et immuable
      jusqu'à la clôture ? (fichier:ligne)
    - Backtest : même invariant ? (fichier:ligne)
    - Si le spread peut changer de signe entre deux barres → 🔴

3.4 Recalcul du hedge ratio en cours de position
    - Live : β (Kalman) est-il mis à jour à chaque barre même
      en position ouverte, ou gelé à l'entrée ? (fichier:ligne)
    - Backtest : même comportement ? (fichier:ligne)
    - Si l'un gèle et l'autre non → 🟠

─────────────────────────────────────────────
BLOC 4 — MODÈLE DE COÛTS
─────────────────────────────────────────────
Source : backtests/cost_model.py + execution_engine/router.py
         + execution/paper_execution.py + execution/ibkr_engine.py
         + config/config.yaml

4.1 Slippage — backtest
    - Méthode dans cost_model.py (fichier:ligne) :
      fixe en bps / variable / ATR-based ?
    - Lit-il get_settings().costs.slippage_bps ou une constante ?
    - Valeur effective (bps par trade)

4.2 Slippage — live
    - execution_engine/router.py : les lignes ~162 et ~189
      hardcodent-elles slippage = 2.0 ? (fichier:ligne exact)
    - paper_execution.py : même valeur ou source différente ?
    - ibkr_engine.py : slippage estimé ou fees IBKR réels ?

4.3 Commission — backtest vs live
    - Backtest (cost_model.py) : commission ($/action, min/trade)
      (fichier:ligne) — cohérent avec IBKR tarif réel ?
    - Live (paper_execution.py) : paper_commission_pct = 0.005
      est-il cohérent avec le modèle backtest ? (fichier:ligne)
    - Si les deux commissions divergent → l'expectancy
      backtest est biaisée → 🟠

4.4 Coût de borrow — short selling
    - Le short_sizing_multiplier = 0.50 est-il appliqué
      dans le cost model backtest ? (fichier:ligne)
    - Le coût de borrow annualisé est-il modélisé en backtest ?
      (fichier:ligne dans cost_model.py)
    - En live : execution/borrow_check.py est-il appelé avant
      tout ordre short ? (fichier:ligne dans runner.py)

4.5 Divergence totale coût backtest ↔ live
    - Le backtest modélise-t-il le même coût total
      (slippage + commission + borrow) que le live ?
    - Si différent mais documenté → À VÉRIFIER
    - Si différent et non documenté → 🟠
    - Quantifier l'écart potentiel en bps si possible

─────────────────────────────────────────────
BLOC 5 — ALIGNEMENT RISK ENGINE
─────────────────────────────────────────────
Source : risk/facade.py + risk_engine/position_risk.py
         + risk_engine/portfolio_risk.py + risk_engine/kill_switch.py
         + live_trading/runner.py + backtests/strategy_simulator.py

5.1 Dualité RiskFacade / composants directs (B2-02 connu)
    - live_trading/runner.py instancie-t-il séparément
      PositionRiskManager, PortfolioRiskManager, KillSwitch
      ET RiskFacade ? (fichier:ligne pour chaque instanciation)
    - Si oui : lequel est réellement appelé dans la boucle
      de trading ? (fichier:ligne dans _step_execute_signals)
    - RiskFacade est-elle une vraie façade (délègue aux 3
      composants) ou une instance parallèle indépendante ?
    - Si les deux coexistent sans délégation → 🔴

5.2 Le backtest passe-t-il par RiskFacade ?
    - strategy_simulator.py : chercher un appel à RiskFacade
      ou aux composants risk_engine (fichier:ligne)
    - Si absent : les rejets de risque live ne sont pas
      reproduits en simulation → 🟠

5.3 Cohérence des tiers de risque (ne pas modifier l'ordre)
    - T1 : RiskConfig.max_drawdown_pct = 0.10
      → vérifié dans position_risk.py (fichier:ligne)
    - T2 : KillSwitchConfig.max_drawdown_pct = 0.15
      → vérifié dans kill_switch.py (fichier:ligne)
    - T3 : StrategyConfig.internal_max_drawdown_pct = 0.20
      → vérifié dans strategy_simulator.py ou runner.py
    - _assert_risk_tier_coherence() est-il appelé au
      démarrage du runner ? (fichier:ligne)
    - Si T1 > T2 ou T2 > T3 → 🔴

5.4 Source d'equity pour les calculs de drawdown
    - Live (runner.py) : la drawdown est-elle calculée
      sur _metrics.equity ou sur BrokerReconciler.internal_equity ?
      (fichier:ligne)
    - Backtest (strategy_simulator.py) : source d'equity
      utilisée pour les calculs de drawdown/stops ? (fichier:ligne)
    - Si les deux sources divergent → halt anticipé ou tardif → 🟠

─────────────────────────────────────────────
BLOC 6 — ROUTAGE D'EXÉCUTION
─────────────────────────────────────────────
Source : execution_engine/router.py + execution/paper_execution.py
         + execution/ibkr_engine.py + execution/rate_limiter.py
         + live_trading/runner.py

6.1 Sélection du moteur d'exécution
    - execution_engine/router.py : comment execution.engine
      (config.yaml) sélectionne-t-il IBKRExecutionEngine
      vs PaperExecutionEngine ? (fichier:ligne)
    - Si le mode est lu au démarrage uniquement (pas rechargé) :
      un rechargement à chaud est-il possible sans redémarrage ?
    - CONFORME / NON CONFORME / À VÉRIFIER

6.2 IBKR rate limiter — couverture
    Hard cap TWS : 50 req/s → seuil interne : 45/s.
    Pour chaque appel IBKR dans ibkr_engine.py :
    - reqHistoricalData → _ibkr_rate_limiter.acquire() avant ?
      (fichier:ligne)
    - reqContractDetails → idem ? (fichier:ligne)
    - placeOrder / cancelOrder → idem ? (fichier:ligne)
    - Si un appel n'est pas protégé → risque de déconnexion
      TWS automatique → 🔴

6.3 Gestion des erreurs IBKR
    - Erreurs informatives (ne pas interrompre) : 2104, 2106, 2158
      → loguées uniquement ? (fichier:ligne dans ibkr_engine.py)
    - Erreurs données historiques : 162, 200, 354
      → cancelHistoricalData appelé ? (fichier:ligne)
    - CONFORME / NON CONFORME

6.4 Divergence Paper vs IBKR
    - PaperExecutionEngine : fill假定 (prix de clôture + slippage) ?
      (fichier:ligne dans paper_execution.py)
    - IBKRExecutionEngine : fills réels IBKR retournés via callback ?
      (fichier:ligne dans ibkr_engine.py)
    - Si Paper simule un fill immédiat au cours de clôture
      sans latence → surestimation de performance live → 🟠

─────────────────────────────────────────────
SYNTHÈSE OBLIGATOIRE
─────────────────────────────────────────────

Score global : X / 10
  ≥ 8    → CONFORME — pipeline fiable en l'état
  5 – 7  → CONDITIONNEL — corrections 🔴 requises avant live
  < 5    → NON CONFORME — dérives silencieuses compromettent
            la fidélité de la simulation

Tableau des anomalies (format strict) :
| ID | Bloc | Description courte | Fichier:Ligne | Sévérité | Impact | Effort |
|----|------|--------------------|---------------|----------|--------|--------|

Sévérité : 🔴 Critique · 🟠 Majeure · 🟡 Mineure
Impact : divergence backtest/live · signal manqué · ordre invalide
         · coût sous-estimé · halt anticipé/tardif
Effort : XS (< 1h) · S (< 4h) · M (< 1j) · L (> 1j)

Verdict : CONFORME / NON CONFORME / CONDITIONNEL
Justification en 3 lignes max — faits du code uniquement.

─────────────────────────────────────────────
SORTIE OBLIGATOIRE
─────────────────────────────────────────────
Crée le fichier :
  tasks/audits/resultats/audit_pipeline_edgecore.md
Crée le dossier s'il n'existe pas.

Structure du fichier :
## BLOC 1 — COHÉRENCE DES PARAMÈTRES STRATÉGIQUES
## BLOC 2 — PIPELINE ALL-OR-NOTHING
## BLOC 3 — DONNÉES D'ENTRÉE DU SPREAD
## BLOC 4 — MODÈLE DE COÛTS
## BLOC 5 — ALIGNEMENT RISK ENGINE
## BLOC 6 — ROUTAGE D'EXÉCUTION
## SYNTHÈSE

Tableau synthèse :
| ID | Bloc | Description | Fichier:Ligne | Sévérité | Impact | Effort |

Sévérité : 🔴 Critique · 🟠 Majeur · 🟡 Mineur.

Confirme dans le chat uniquement :
"✅ tasks/audits/resultats/audit_pipeline_edgecore.md créé · 🔴 X · 🟠 X · 🟡 X"
