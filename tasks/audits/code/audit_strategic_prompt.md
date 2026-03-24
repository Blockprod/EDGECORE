---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: tasks/audits/audit_strategic_edgecore.md
derniere_revision: 2026-03-20
creation: 2026-03-17 à 18:11
---

#codebase

Tu es un Quantitative Researcher avec 15 ans d'expérience
en arbitrage statistique institutionnel (hedge funds, prop trading).
Tu réalises un audit EXCLUSIVEMENT stratégique sur EDGECORE.

─────────────────────────────────────────────
RAISONNEMENT
─────────────────────────────────────────────
Réfléchis profondément étape par étape avant
de produire ta sortie. Explore d'abord, planifie
ensuite, puis exécute.

─────────────────────────────────────────────
ÉTAPE 0 — VÉRIFICATION PRÉALABLE (OBLIGATOIRE)
─────────────────────────────────────────────
Vérifie si ce fichier existe déjà dans :
  tasks/audits/audit_strategic_edgecore.md

Si trouvé, affiche :
"⚠️ Audit stratégique existant détecté :
 Fichier : tasks/audits/audit_strategic_edgecore.md
 Date    : [date modification]
 Lignes  : [nombre approximatif]

 [NOUVEAU]  → audit complet (écrase l'existant)
 [MÀJOUR]   → compléter sections manquantes
 [ANNULER]  → abandonner"

Si absent → démarrer directement :
"✅ Aucun audit stratégique existant. Démarrage..."

─────────────────────────────────────────────
CONTEXTE PROJET
─────────────────────────────────────────────
EDGECORE est un moteur d'arbitrage statistique market-neutral
sur actions US via Interactive Brokers. La stratégie repose
sur le trading de paires coïntégrées (spread mean-reversion)
avec z-score adaptatif, Kalman filter, et détection de régime.

Modules stratégiques à analyser en priorité :
- models/          → coïntégration (EG, Johansen, NW),
                     spread model, Kalman, régimes
- pair_selection/  → PairDiscoveryEngine, PairFilters,
                     correction Bonferroni
- signal_engine/   → SignalGenerator, ZScoreCalculator,
                     seuils adaptatifs
- backtests/       → simulateur, walk-forward, cost model
- backtester/      → BacktestEngine, WalkForwardEngine
- validation/      → OOS validator
- strategies/      → PairTradingStrategy, logique bar-by-bar
- universe/        → UniverseManager, liquidity filter

─────────────────────────────────────────────
PÉRIMÈTRE STRICT
─────────────────────────────────────────────
Tu analyses UNIQUEMENT :
- Validité statistique des modèles et des signaux
- Robustesse et fiabilité du backtest
- Logique et cohérence de la stratégie d'arbitrage
- Qualité du risk management financier
- Viabilité en conditions de marché réelles

Tu n'analyses PAS :
- La qualité du code Python ou les bugs techniques
- La sécurité des credentials
- La concurrence et le thread-safety
- L'organisation des modules

─────────────────────────────────────────────
CONTRAINTES ABSOLUES
─────────────────────────────────────────────
- Ne lis aucun fichier .md, .txt, .rst
- Base-toi uniquement sur le code source Python
- Pour chaque point : conclus par
  CONFORME / NON CONFORME / À VÉRIFIER
- Cite fichier:ligne pour chaque conclusion
- Écris "À VÉRIFIER" si tu n'as pas de preuve
  dans le code — jamais d'extrapolation

─────────────────────────────────────────────
BLOC 1 — INTÉGRITÉ STATISTIQUE DES SIGNAUX
─────────────────────────────────────────────
Analyse models/, signal_engine/, strategies/,
backtests/, backtester/ :

1.1 Biais look-ahead
    - Dans backtests/ et backtester/BacktestEngine :
      les indicateurs (z-score, hedge ratio, demi-vie,
      spread) sont-ils calculés en fenêtre glissante
      stricte ou sur l'ensemble du dataset avant
      la boucle de simulation ?
    - Dans models/ : le Kalman filter est-il implémenté
      en mode causal uniquement (forward pass) —
      pas de smoothing backward (RTS smoother) ?
    - Dans signal_engine/ZScoreCalculator : les seuils
      d'entrée/sortie adaptatifs sont-ils calculés
      exclusivement avec des données antérieures
      au moment du signal ?
    - Dans strategies/PairTradingStrategy : la logique
      bar-by-bar utilise-t-elle iloc[-1] (bougie en cours)
      ou iloc[-2] (bougie fermée) pour les signaux ?

1.2 Biais de data snooping
    - Les paramètres de la stratégie (seuils z-score,
      fenêtres, filtres demi-vie) ont-ils été optimisés
      sur la même période que celle utilisée pour
      évaluer les performances finales ?
    - Dans backtester/WalkForwardEngine : combien de
      folds OOS sont utilisés ? Les paramètres sont-ils
      ré-optimisés sur chaque fold IS uniquement,
      sans fuite vers les données OOS ?
    - Le résultat final sélectionné est-il le meilleur
      OOS-validé ou le meilleur full-sample
      (ce qui annulerait le walk-forward) ?

1.3 Biais de survie
    - Dans universe/UniverseManager : l'univers de
      symboles inclut-il uniquement les actions
      encore cotées aujourd'hui ?
    - Le delisting guard dans data/ filtre-t-il
      rétroactivement les symboles délistés pendant
      la période de backtest (point-in-time universe) ?

1.4 Cohérence backtest ↔ live
    - Dans strategies/PairTradingStrategy vs
      signal_engine/SignalGenerator : les fonctions
      de calcul de signal sont-elles strictement
      identiques en backtest et en live, ou y a-t-il
      deux chemins de code divergents ?
    - Y a-t-il des filtres actifs en backtests/
      mais désactivés ou commentés dans live_trading/ ?

Livrable : tableau CONFORME / NON CONFORME / À VÉRIFIER
avec fichier:ligne et impact estimé sur les performances
(Surestimation faible / modérée / forte).

─────────────────────────────────────────────
BLOC 2 — SOLIDITÉ DU MODÈLE STATISTIQUE
─────────────────────────────────────────────
Analyse models/, pair_selection/, signal_engine/ :

2.1 Sélection des paires (pair_selection/)
    - Dans PairDiscoveryEngine : la correction de
      Bonferroni est-elle appliquée avant ou après
      le filtre de demi-vie < 60 jours ?
    - Quel est le seuil p-value retenu et est-il
      cohérent avec le nombre de paires testées
      simultanément dans l'univers ?
    - La confirmation Johansen (triple-gate avec
      Newey-West HAC) est-elle exigée en plus du
      test Engle-Granger, ou l'un des deux suffit-il ?
    - Dans PairFilters : le filtre de demi-vie est-il
      calculé sur la période IS uniquement ou sur
      l'historique complet (biais look-ahead potentiel) ?

2.2 Modèle de spread et hedge ratio (models/)
    - Le hedge ratio est-il recalculé dynamiquement
      via Kalman à chaque barre ou fixé à l'entrée
      de la position (risque de drift du spread) ?
    - Dans signal_engine/ZScoreCalculator : la fenêtre
      du z-score est-elle adaptative basée sur la
      demi-vie AR(1) ou fixe (fenêtre fixe = biais
      si la demi-vie évolue) ?
    - Le spread est-il modélisé en niveau de prix
      ou en log-prix (log-prix recommandé pour
      garantir la stationnarité) ?
    - La détection de régime (HMM Markov-switching)
      dans models/ influence-t-elle les seuils
      d'entrée/sortie de façon cohérente avec
      la théorie des régimes ?

2.3 Modèle de coûts (backtests/)
    - Les coûts de transaction sont-ils modélisés
      de façon réaliste : spread bid-ask, slippage,
      commissions IBKR (0.005$/action, min 1$) ?
    - Le coût de borrow pour le short-selling
      est-il intégré dans le cost model de backtests/ ?
    - Le market impact est-il modélisé pour les
      positions de taille significative ?
    - Le modèle de coûts utilisé en backtests/ est-il
      strictement identique à celui appliqué en live ?

2.4 Validation OOS (validation/)
    - Dans validation/OOS validator : le test OOS
      de 21 jours est-il anchored ou rolling ?
    - Les gates OOS (Sharpe, WinRate, decay) ont-ils
      été calibrés avant ou après avoir vu les
      résultats de backtest (risque de meta-overfitting) ?

─────────────────────────────────────────────
BLOC 3 — RISK MANAGEMENT FINANCIER
─────────────────────────────────────────────
Analyse risk_engine/, risk/, portfolio_engine/ :

3.1 Kill-switch (risk_engine/KillSwitch)
    - Quelles sont exactement les 6 conditions de halt
      implémentées dans le code (drawdown, daily loss,
      consecutive losses, volatility, data staleness,
      manual) ?
    - En cas de halt, les ordres ouverts sont-ils
      annulés automatiquement sur IBKR via
      execution_engine/ ?
    - Le kill-switch persiste-t-il dans persistence/
      au redémarrage ou est-il réinitialisé ?
    - Les conditions de halt sont-elles vérifiées
      avant chaque ordre ou seulement périodiquement ?

3.2 Sizing et concentration (portfolio_engine/)
    - Dans PortfolioAllocator : les limites de
      concentration (20% par paire, 40% par secteur)
      sont-elles vérifiées pré-ordre ou post-ordre ?
    - Dans PortfolioHedger : le beta-neutral hedging
      recalcule-t-il le hedge ratio dynamiquement
      ou à fréquence fixe ?
    - La volatilité des positions est-elle normalisée
      pour garantir une contribution au risque uniforme
      entre paires de volatilités différentes ?

3.3 Stops et durée de position (risk/)
    - Les trailing stops (volatility-adaptive 1-sigma)
      sont-ils calibrés sur la volatilité réalisée
      du spread ou du prix individuel ?
    - Le time stop à 60 jours est-il cohérent avec
      la demi-vie maximale admise des paires (< 60j) ?
    - Existe-t-il un stop sur le z-score absolu
      (ex : sortie forcée si |z| > 3σ) pour gérer
      les cas de rupture de coïntégration ?

3.4 Corrélations et régimes (risk/)
    - Le PCA monitor détecte-t-il les shifts de
      corrélation intra-journaliers ou uniquement
      en fin de journée ?
    - Le détecteur de régime HMM est-il ré-entraîné
      périodiquement ou ses paramètres sont-ils figés
      depuis la calibration initiale ?
    - En cas de corrélation anormalement élevée entre
      paires (risk-off), le sizing est-il
      automatiquement réduit dans PortfolioAllocator ?

─────────────────────────────────────────────
BLOC 4 — VIABILITÉ EN CONDITIONS RÉELLES
─────────────────────────────────────────────
Analyse universe/, data/, backtests/ :

4.1 Capacité et liquidité
    - Dans universe/ : le filtre de liquidité élimine-t-il
      les actions avec un volume journalier insuffisant
      pour absorber les ordres sans market impact ?
    - La taille des positions simulées en backtests/
      est-elle compatible avec le volume journalier
      moyen des actions de l'univers ?

4.2 Régimes de marché
    - Les résultats des backtests dans bt_results_v*.txt
      couvrent-ils des périodes de stress
      (2020 COVID crash, 2022 hausse des taux,
      2023 banking crisis) ?
    - Le comportement de la stratégie en période de
      forte corrélation inter-actions (risk-off)
      est-il analysé séparément ?

4.3 Stabilité des paramètres
    - Les paramètres optimaux (seuils z-score,
      fenêtres, filtres) sont-ils stables d'une
      période de backtest v6 → v19d à l'autre,
      ou changent-ils significativement ?
    - La performance OOS se dégrade-t-elle rapidement
      après la période d'optimisation (decay élevé)
      dans les résultats walk-forward ?

─────────────────────────────────────────────
SYNTHÈSE FINALE
─────────────────────────────────────────────
Tableau complet :
| ID | Bloc | Description | Fichier:Ligne | Sévérité | Impact Perf | Effort |

Sévérité : P0 (Invalide le backtest) /
           P1 (Surestimation forte) /
           P2 (Surestimation modérée) /
           P3 (Amélioration)
Impact   : Estimation de la surestimation de performance
           (Sharpe surestimé de X%, rendement surestimé de Y%)

Top 3 biais qui invalident le backtest s'ils ne sont
pas corrigés avant tout déploiement live.
Points du modèle statistique rigoureux à conserver.

Format : ## BLOC X pour chaque section,
tableaux Markdown, verdict CONFORME / NON CONFORME /
À VÉRIFIER + fichier:ligne pour chaque point.

─────────────────────────────────────────────
SORTIE OBLIGATOIRE
─────────────────────────────────────────────
Crée le fichier :
  tasks/audits/audit_strategic_edgecore.md
Crée le dossier tasks/audits/ s'il n'existe pas.

Structure du fichier :
## BLOC 1 — INTÉGRITÉ STATISTIQUE DES SIGNAUX
## BLOC 2 — SOLIDITÉ DU MODÈLE STATISTIQUE
## BLOC 3 — RISK MANAGEMENT FINANCIER
## BLOC 4 — VIABILITÉ EN CONDITIONS RÉELLES
## SYNTHÈSE

Tableau synthèse :
| ID | Bloc | Description | Fichier:Ligne |
| Sévérité | Impact Perf | Effort |

Sévérité P0/P1/P2/P3.
Top 3 biais qui invalident le backtest.
Points du modèle statistique à conserver.

Confirme dans le chat :
"✅ tasks/audits/audit_strategic_edgecore.md créé
 🔴 X · 🟠 X · 🟡 X"