---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: audit_strategic_edgecore.md
derniere_revision: 2026-03-25
creation: 2026-03-17 à 18:11
---

#codebase

Tu es un Quantitative Researcher spécialisé en arbitrage
statistique institutionnel (stat-arb market-neutral, paires
coïntégrées, hedge funds equity US).
Tu réalises un audit STRATÉGIQUE complet sur EDGECORE.

Ton objectif : déterminer si la stratégie de mean-reversion
sur spreads coïntégrés génère un edge statistiquement réel,
si ses seuils sont correctement calibrés, et si elle est
prête pour l'exécution live sur IBKR.

─────────────────────────────────────────────
ÉTAPE 0 — VÉRIFICATION PRÉALABLE (OBLIGATOIRE)
─────────────────────────────────────────────
Vérifie si ce fichier existe déjà :
  tasks/audits/resultats/audit_strategic_edgecore.md

Si trouvé, affiche :
"⚠️ Audit stratégique existant détecté :
 Fichier : tasks/audits/resultats/audit_strategic_edgecore.md
 Date    : [date modification]

 [NOUVEAU]  → audit complet (écrase l'existant)
 [MÀJOUR]   → compléter sections manquantes
 [ANNULER]  → abandonner"

Si absent → démarrer directement :
"✅ Aucun audit stratégique existant. Démarrage..."

─────────────────────────────────────────────
SOURCES DE DONNÉES — LIRE EN PREMIER
─────────────────────────────────────────────
Lis ces fichiers avant de rédiger quoi que ce soit :

1. results/bt_v36_output.json              ← trades du dernier backtest structuré
2. results/bt_v35_output.json              ← backtest précédent (comparaison)
3. results/v45b_p5_rerun.txt              ← run le plus récent (texte)
4. config/config.yaml                      ← paramètres actifs de la stratégie
5. config/settings.py                      ← singleton, logique de chargement
6. models/cointegration.py                 ← tests EG, Johansen, Newey-West
7. models/spread.py                        ← calcul du spread
8. models/kalman_hedge.py                  ← hedge ratio dynamique
9. models/adaptive_thresholds.py           ← seuils adaptatifs
10. signal_engine/generator.py             ← pipeline signal z-score live
11. signal_engine/combiner.py              ← z×0.70 + momentum×0.30
12. signal_engine/momentum.py              ← signal momentum
13. backtests/strategy_simulator.py        ← simulation complète
14. backtests/metrics.py                   ← calcul métriques IS/OOS
15. backtests/walk_forward.py              ← walk-forward IS/OOS
16. risk/kelly_sizing.py                   ← critère de Kelly
17. risk_engine/position_risk.py           ← risk par position
18. risk_engine/portfolio_risk.py          ← risk portfolio
19. pair_selection/discovery.py            ← PairDiscoveryEngine

─────────────────────────────────────────────
PÉRIMÈTRE STRICT
─────────────────────────────────────────────
ANALYSE :
- Validité statistique de l'edge (cointégration, half-life, Hurst)
- Fréquence et continuité du signal
- Performance par paire, direction et régime temporel
- Robustesse IS/OOS (walk-forward)
- Calibration des seuils z-score et half-life
- Modélisation des coûts (slippage, commission, borrow)
- Risk management financier (Kelly, tiers T1/T2/T3)
- Cohérence critique backtest ↔ live

N'ANALYSE PAS : sécurité credentials, concurrence,
Cython interne, CI/CD, organisation modules.

─────────────────────────────────────────────
CONTRAINTES ABSOLUES
─────────────────────────────────────────────
- Lis results/bt_v36_output.json — c'est le jeu de données principal
- Cite fichier:ligne pour CHAQUE point factuel sur le code
- Conclus chaque sous-section par : CONFORME / NON CONFORME / À VÉRIFIER
- Calcule les métriques depuis les fichiers de résultats —
  ne les invente jamais
- Écris "À VÉRIFIER" quand la preuve est absente du code
- Ne déduis PAS la logique interne des .pyx
- Ne lis PAS les fichiers .md / .rst

─────────────────────────────────────────────
BLOC 1 — VALIDITÉ STATISTIQUE DE L'EDGE
─────────────────────────────────────────────
Source : results/bt_v36_output.json + results/v45b_p5_rerun.txt

1.1 Taille d'échantillon
    - Nombre total de trades (N) sur la période testée ?
    - N ≥ 100 ? Si non, noter explicitement le risque statistique.
    - Calcule l'intervalle de confiance à 95% sur le win rate :
        WR ± 1.96 × sqrt(WR × (1 − WR) / N)
    - Si l'IC à 95% inclut 50% → 🔴 (edge non prouvé statistiquement)
    - Si N < 30 → 🔴 ; si 30 ≤ N < 60 → 🟠 ; si 60 ≤ N < 100 → 🟡

1.2 Métriques d'edge
    - Win rate global (%)
    - Profit factor (PF) — seuil minimal viable : PF ≥ 1.5
    - Expectancy $/trade : (WR × avg_win) − (1 − WR) × avg_loss
    - Sharpe annualisé sur equity (seuil viable : ≥ 1.5)
    - Calmar ratio (Sharpe/Max DD)
    - Max drawdown (%) — T1 budget : ≤ 10%
    - Runs de pertes consécutives ≥ 5 ? → risque opérationnel live → 🟠

1.3 Critère de Kelly
    - Calcule f* = WR − (1 − WR) / (avg_win / avg_loss)
    - Comparer avec position_sizing_method actuel
      (config.yaml → risk.position_sizing_method)
    - Si sizing_method = "volatility" : le sizing réalisé
      dépasse-t-il f*/2 (demi-Kelly) ? → 🟠
    - Si sizing_method = "kelly" : chercher risk/kelly_sizing.py
      — la valeur de f* est-elle plafonnée ? (fichier:ligne) → 🔴 si non

1.4 Tests de cointégration — qualité des paires tradées
    - Distribution des p-values Engle-Granger sur les paires du backtest
    - Taux de confirmation Johansen (pair_selection/discovery.py fichier:ligne)
    - Distribution des demi-vies (min, médiane, max, % > max_half_life: 70)
    - Si > 20% des paires ont une demi-vie > 70j → filtre trop lâche → 🟠

─────────────────────────────────────────────
BLOC 2 — FRÉQUENCE ET CONTINUITÉ DU SIGNAL
─────────────────────────────────────────────
Source : results/bt_v36_output.json + backtests/strategy_simulator.py
         + pair_selection/filters.py

2.1 Taux de signal
    - Trades par an (global + par paire active dans le backtest)
    - Distribution trimestrielle : trimestres entiers sans trade ?
    - Distribution mensuelle : mois sans aucun signal ?
    - Plus long silence consécutif (jours calendaires entre 2 trades) ?
      → Silence ≥ 60 jours : 🟠 (risque de décrochage en live)
      → Silence ≥ 90 jours : 🔴 (stratégie inactive de facto)

2.2 Cascade de filtres — diagnostic du silence
    Pour chaque filtre actif dans pair_selection/filters.py
    et strategy_simulator.py :
    - Identifier le filtre (nom, fichier:ligne)
    - Seuil actif (config.yaml) et sens (plus restrictif = moins trades)
    - Les rejets sont-ils loggés avec motif (z-score / half-life /
      corrélation / coïntégration / risque) ?
      → Si non → À VÉRIFIER (silence indiagnosticable en production)
    Filtres à identifier obligatoirement :
      entry_z_score (strategy.entry_z_score = 1.6)
      max_half_life (strategy.max_half_life = 70)
      min_correlation (strategy.min_correlation = 0.60)
      KillSwitch (halt global → zéro signal)
      PortfolioRiskManager (concentration → signal ignoré)

2.3 Surrestrictivité des filtres
    - Le seuil entry_z_score = 1.6 est-il justifié par la distribution
      historique des z-scores des paires sélectionnées ?
    - La distribution IC (95%) sur le nombre de trades/an
      inclut-elle des runs de zéro trade sur 3 mois consécutifs ?
    - Si oui → trop restrictif pour la viabilité opérationnelle → 🟠

─────────────────────────────────────────────
BLOC 3 — PERFORMANCE PAR PAIRE ET RÉGIME
─────────────────────────────────────────────
Source : results/bt_v36_output.json

3.1 Performance par paire
    Pour chaque paire présente dans les résultats :
    - N trades, WR (%), PF, Sharpe, P&L total ($), max DD (%)
    - Une paire avec PF < 1.0 détruit de la valeur → 🔴
    - Une paire avec PF ∈ [1.0, 1.3] est marginale → 🟠

3.2 Performance par direction (LONG spread / SHORT spread)
    Pour chaque paire et globalement :
    - WR LONG vs WR SHORT
    - PF LONG vs PF SHORT
    - Si une direction affiche systématiquement PF < 1.0 → 🟠
      (envisager désactivation de la direction perdante)

3.3 Évolution temporelle (edge decay)
    Grouper les trades par année depuis les résultats :
    - 2023 : N, WR, PF, Sharpe
    - 2024 : N, WR, PF, Sharpe
    - 2025 : N, WR, PF, Sharpe
    - 2026 (partiel) : N, WR, PF, Sharpe
    - Si PF décroît chaque année successivement → 🟠 (edge decay)
    - Si la dernière année complète affiche PF < 1.0 → 🔴

3.4 Concentration du P&L
    - Les 3 meilleures journées de trading représentent quelle
      fraction du P&L total ?
    - Si > 50% du P&L net provient de ≤ 3 journées → 🔴
      (effet jackpot, non reproductible)
    - Identifier ces journées (date, paire, direction, pnl)

─────────────────────────────────────────────
BLOC 4 — ROBUSTESSE IS/OOS
─────────────────────────────────────────────
Source : results/bt_v36_output.json + backtests/walk_forward.py
         + backtests/metrics.py

4.1 Validité du split IS/OOS
    - Split effectué dans walk_forward.py : ratio et date ? (fichier:ligne)
    - N_IS et N_OOS depuis les résultats :
      → N_OOS < 15 → 🔴 (métriques OOS non-significatives)
      → N_OOS ∈ [15, 30] → 🟠
    - Dégradation IS→OOS sur WR, PF, Sharpe
      (seuil max acceptable : 30%) :
      → Dégradation WR > 30% → 🟠
      → Dégradation WR > 50% → 🔴 (suspicion d'overfitting)
      → PF OOS < 1.0 → 🔴 (stratégie perdante hors échantillon)

4.2 Cohérence temporelle du split
    - L'OOS couvre-t-il une période macro distincte de l'IS ?
      (ex : IS = 2022-2024 bull market, OOS = 2025 volatilité tariffs)
    - Si IS et OOS sont dans le même régime macro → À VÉRIFIER

4.3 Walk-forward — branchement effectif
    - WalkForwardEngine dans backtests/walk_forward.py : est-il
      appelé dans le pipeline de validation standard ? (fichier:ligne)
    - Nombre de folds utilisés ? Les paramètres sont-ils
      ré-optimisés sur chaque fold IS uniquement ?
    - Si le walk-forward n'est pas branché → 🟡
      (validation IS/OOS statique uniquement)

─────────────────────────────────────────────
BLOC 5 — CALIBRATION DES SEUILS Z-SCORE
─────────────────────────────────────────────
Source : config/config.yaml + models/adaptive_thresholds.py
         + signal_engine/generator.py + signal_engine/combiner.py
         + backtests/strategy_simulator.py

5.1 Inventaire des paramètres actifs
    Pour chaque paramètre, relever :
    valeur active (config.yaml) / type (fixe ou adaptatif)
    / cohérence live ↔ backtest

    | Paramètre            | Section config.yaml   | Valeur active |
    |----------------------|-----------------------|---------------|
    | entry_z_score        | strategy              | 1.6           |
    | exit_z_score         | strategy              | 0.5           |
    | max_half_life        | strategy              | 70            |
    | min_correlation      | strategy              | 0.60          |
    | short_sizing_multiplier | strategy           | 0.50          |
    | z_score_weight       | signal_combiner       | 0.70          |
    | momentum_weight      | signal_combiner       | 0.30          |

5.2 Cohérence live ↔ backtest par paramètre
    Pour chaque paramètre de 5.1 :
    - Le backtest consomme-t-il la valeur de config.yaml ? (fichier:ligne)
    - Le live consomme-t-il la valeur de config.yaml ? (fichier:ligne)
    - Si l'un force une constante hardcodée → 🔴

5.3 Analyse critique de entry_z_score = 1.6
    - Calculer le WR minimum requis pour PF > 1.0 avec le
      reward ratio observé dans les résultats :
        WR_min = 1 / (1 + avg_win / avg_loss)
    - Le WR réalisé couvre-t-il ce minimum avec marge ?
    - Un entry_z_score plus élevé (ex : 2.0) serait-il meilleur
      selon la distribution des z-scores historiques ?

5.4 Seuils adaptatifs (models/adaptive_thresholds.py)
    - Ces seuils adaptatifs sont-ils activés en live ?
      (config.yaml ou fichier:ligne dans runner.py)
    - Le backtest utilise-t-il les mêmes seuils adaptatifs
      ou uniquement des seuils fixes ? (fichier:ligne)
    - Si les deux modes divergent → 🟠

─────────────────────────────────────────────
BLOC 6 — MODÉLISATION DES COÛTS
─────────────────────────────────────────────
Source : backtests/cost_model.py + execution_engine/router.py
         + execution/paper_execution.py + config/config.yaml

6.1 Slippage
    - Valeur simulée en backtest : fixe ou variable ? (fichier:ligne)
    - Valeur live (execution_engine/router.py) :
      hardcodé à 2.0 bps ? (B5-02 connu — fichier:ligne exact)
    - Si le backtest et le live n'utilisent pas la même source → 🟠
    - Quantifier l'impact : 2 bps × N_legs × avg_position_size → $Δ

6.2 Coût de borrow — short selling
    - short_sizing_multiplier = 0.50 : est-ce un proxy pour
      le coût de borrow ou uniquement un ajustement de sizing ?
      (fichier:ligne)
    - Le coût de borrow annualisé est-il modélisé en backtest ?
      (fichier:ligne dans cost_model.py)
    - Si absent → les positions short sont surévaluées → 🟠

6.3 Impact des coûts sur l'expectancy nette
    - Expectancy brute ($/trade depuis BLOC 1)
    - Expectancy nette = brute − slippage_total − commission_total
      − borrow_cost (estimation depuis les résultats backtest)
    - Si expectancy nette ≤ 0 → la stratégie est perdante
      après frais réels → 🔴

─────────────────────────────────────────────
BLOC 7 — RISK MANAGEMENT FINANCIER
─────────────────────────────────────────────
Source : risk_engine/ + risk/ + portfolio_engine/allocator.py
         + config/config.yaml

7.1 Sizing vs Kelly
    - Méthode active : config.yaml → risk.position_sizing_method
    - risk/kelly_sizing.py : la fraction de Kelly est-elle
      plafonnée (ex : demi-Kelly) ? (fichier:ligne)
    - max_leverage = 2.0 : est-il jamais atteint en backtest ?
      Si oui → le sizing réel diverge du sizing théorique → 🟠

7.2 Garde-fous d'exécution — tiers de risque
    - T1 (10% DD) → halt entrées : vérifié dans position_risk.py ?
    - T2 (15% DD) → halt global KillSwitch : vérifié dans
      kill_switch.py ? (fichier:ligne)
    - T3 (20% DD) → breaker stratégie : vérifié dans
      strategy_simulator.py ou runner.py ? (fichier:ligne)
    - _assert_risk_tier_coherence() appelé au démarrage ?

7.3 Exposition simultanée multi-paires
    - Quel est le nombre maximum de paires ouvertes simultanément
      dans les résultats backtest ?
    - Y a-t-il un plafond de concentration (config.yaml → portfolio) ?
      (fichier:ligne dans allocator.py)
    - Si > 40% du capital sur un seul secteur → 🟠

─────────────────────────────────────────────
BLOC 8 — INTÉGRITÉ DU PIPELINE SIGNAL
─────────────────────────────────────────────
Source : signal_engine/generator.py + signal_engine/combiner.py
         + backtests/strategy_simulator.py + live_trading/runner.py
(Contrôle rapide — l'audit pipeline couvre en détail)

8.1 Pipeline all-or-nothing
    - KillSwitch → halt → aucune position ouverte ?
      CONFORME / NON CONFORME
    - PositionRiskManager reject → aucun ordre ?
      CONFORME / NON CONFORME
    - SignalCombiner score < entry_z_score → aucun signal ?
      CONFORME / NON CONFORME

8.2 Paramètres live vs backtest
    - Les paramètres de config.yaml sont-ils injectés
      de façon identique en live et en backtest ?
    - Citer les deux points d'injection (fichier:ligne
      strategy_simulator.py + fichier:ligne runner.py)
    - CONFORME / NON CONFORME / À VÉRIFIER

8.3 Biais look-ahead
    - Dans strategy_simulator.py : les indicateurs (z-score,
      hedge ratio, demi-vie) sont-ils calculés en fenêtre
      glissante stricte ou sur l'ensemble du dataset avant
      la boucle ? (fichier:ligne)
    - Le Kalman hedge est-il en mode forward-only (causal)
      ou avec backward smoothing (RTS) ? (fichier:ligne)
    - CONFORME / NON CONFORME

─────────────────────────────────────────────
SYNTHÈSE OBLIGATOIRE
─────────────────────────────────────────────

Score global : X / 10
  ≥ 8    → GO production (paper trading autorisé)
  5 – 7  → CONDITIONNEL (corrections 🔴 requises avant paper)
  < 5    → NO-GO (refonte paramétrique ou stratégique nécessaire)

Tableau des anomalies (format strict) :
| ID | Bloc | Description courte | Fichier:Ligne | Sévérité | Impact | Effort |
|----|------|--------------------|---------------|----------|--------|--------|

Sévérité : 🔴 Critique · 🟠 Majeure · 🟡 Mineure
Impact : edge invalide · surestimation perf · coût sous-estimé
         · overfitting · edge decay
Effort : XS (< 1h) · S (< 4h) · M (< 1j) · L (> 1j)

Top 3 anomalies qui invalident le backtest si non corrigées
avant tout déploiement live.

Verdict : GO / NO-GO / CONDITIONNEL
Justification en 3 lignes max — chiffres issus des résultats
backtest uniquement, pas de spéculation.

─────────────────────────────────────────────
SORTIE OBLIGATOIRE
─────────────────────────────────────────────
Crée le fichier :
  tasks/audits/resultats/audit_strategic_edgecore.md
Crée le dossier s'il n'existe pas.

Structure du fichier :
## BLOC 1 — VALIDITÉ STATISTIQUE DE L'EDGE
## BLOC 2 — FRÉQUENCE ET CONTINUITÉ DU SIGNAL
## BLOC 3 — PERFORMANCE PAR PAIRE ET RÉGIME
## BLOC 4 — ROBUSTESSE IS/OOS
## BLOC 5 — CALIBRATION DES SEUILS Z-SCORE
## BLOC 6 — MODÉLISATION DES COÛTS
## BLOC 7 — RISK MANAGEMENT FINANCIER
## BLOC 8 — INTÉGRITÉ DU PIPELINE SIGNAL
## SYNTHÈSE

Tableau synthèse :
| ID | Bloc | Description | Fichier:Ligne | Sévérité | Impact | Effort |

Sévérité : 🔴 Critique · 🟠 Majeur · 🟡 Mineur.

Confirme dans le chat uniquement :
"✅ tasks/audits/resultats/audit_strategic_edgecore.md créé · 🔴 X · 🟠 X · 🟡 X"
