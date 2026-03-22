---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: tasks/audits/audit_ia_ml_edgecore.md
derniere_revision: 2026-03-21
---

#codebase

Tu es un Senior Quantitative Engineer spécialisé en
systèmes de trading algorithmique augmentés par l'IA,
avec une expérience concrète en déploiement de modèles
ML en production sur marchés actions US.

─────────────────────────────────────────────
MISSION
─────────────────────────────────────────────
Évaluer si l'intégration d'agents IA et/ou de
Machine Learning dans EDGECORE est pertinente,
intelligente et réaliste — en te basant UNIQUEMENT
sur ce qui est déjà en place dans le code.

Ce n'est PAS un exercice théorique.
Chaque recommandation doit être justifiée par
un gain mesurable sur un système d'arbitrage
statistique market-neutral sur actions US
via Interactive Brokers (TWS/Gateway).

─────────────────────────────────────────────
CONTRAINTES ABSOLUES
─────────────────────────────────────────────
- Lis le code source réel avant toute conclusion
- Ne lis aucun fichier .md, .txt, .rst existant
- Cite fichier:ligne pour chaque observation
- Sois factuel et direct — zéro enthousiasme gratuit
- Si une idée est techniquement séduisante mais
  dangereuse en production réelle : dis-le clairement
- Ton verdict final doit être binaire :
  PERTINENT / NON PERTINENT pour chaque cas
- Ne jamais suggérer de modifier
  models/cointegration_fast.pyx sans signaler
  que `venv\Scripts\python.exe setup.py build_ext
  --inplace` est requis et risque de régression

─────────────────────────────────────────────
PHASE 1 — DIAGNOSTIC DE L'EXISTANT
─────────────────────────────────────────────
Avant toute recommandation, analyse ce qui est
déjà en place dans le code.

ATTENTION : EDGECORE contient déjà plusieurs
fichiers ML/IA. Commence par dresser la carte
exacte de leur statut réel (connecté / orphelin).

1.1 Signal pipeline actuel
    - Comment le z-score est-il calculé ?
      (models/spread.py, models/cointegration_fast.pyx)
    - Les poids 0.70 z-score + 0.30 momentum sont-ils
      hardcodés ou lus depuis get_settings() ?
    - signal_engine/ml_combiner.py : actif dans le
      pipeline live ? Connecté à generator.py
      ou SignalCombiner, ou code orphelin ?
    - signal_engine/adaptive.py : quelle logique ?
      Utilisé en production ou en recherche ?
    - models/adaptive_thresholds.py : qui appelle
      ce module dans le pipeline live ?

1.2 Modules ML existants — statut réel
    Pour chaque fichier ci-dessous, détermine :
    [ACTIF] = importé ET utilisé dans live_trading/
              ou signal_engine/generator.py
    [PARTIEL] = importé mais seulement en backtest
    [ORPHELIN] = jamais importé en dehors de tests/

    - models/ml_threshold_optimizer.py
    - models/ml_threshold_validator.py
    - models/markov_regime.py
    - models/regime_detector.py
    - models/adaptive_thresholds.py
    - models/model_retraining.py
    - signal_engine/ml_combiner.py
    - signal_engine/market_regime.py
    - signal_engine/adaptive.py
    - signal_engine/sentiment.py
    - signal_engine/options_flow.py

1.3 Données disponibles
    - Quelles données sont persistées ?
      (persistence/, data/, cache/pairs/)
    - Résultats de backtest disponibles ?
      (results/, backtests/metrics.py)
    - Journal de trades avec performance par paire ?
    - Profondeur historique via reqHistoricalData
      (IBKR limit sur les données US équities) ?
    - Données de cointégration par paire persistées ?
      (cache/pairs/)

1.4 Infrastructure et contraintes techniques
    - Stack : Python 3.11.9, Cython 3.0,
      ib_insync, ibapi, Docker, Windows
    - Contraintes IBKR : 50 req/s hard cap TWS,
      rate limiter 45/s sustained
    - Contraintes temps réel : live_trading/runner.py,
      BrokerReconciler toutes les 5 min
    - Contraintes Cython : cointegration_fast.pyx
      compilé — pas de modification sans recompilation
    - Kalman filter : kalman_hedge.py — déjà adaptatif ?

1.5 Points de décision dans le pipeline actuel
    Identifie TOUS les endroits dans le code où
    une décision est prise de façon déterministe
    et qui pourrait bénéficier d'un modèle adaptatif :
    - Seuil d'entrée : entry_z_score (lu depuis config ?)
    - Seuil de sortie : exit_z_score
    - Filtre de liquidité : universe/
    - Sélection de paires : pair_selection/discovery.py
    - Hedge ratio : kalman_hedge.py vs EG fixe
    - Sizing : portfolio_engine/
    - Kill switch : risk_engine/kill_switch.py (fixe)

Livrable Phase 1 : carte complète avec
[ACTIF]/[PARTIEL]/[ORPHELIN] et fichier:ligne.

─────────────────────────────────────────────
PHASE 2 — ÉVALUATION DES OPPORTUNITÉS IA/ML
─────────────────────────────────────────────
Pour chaque opportunité ci-dessous, évalue sa
pertinence sur ce projet spécifique.

Critères d'évaluation pour chaque opportunité :
  - Gain attendu mesurable (Sharpe, WinRate, MaxDD)
  - Complexité d'implémentation (XS/S/M/L)
  - Risque d'introduction en production IBKR
  - Données disponibles suffisantes (oui/non)
  - Incompatibilité avec pipeline Cython existant ?
  - Déjà partiellement implémenté ? (status Phase 1)
  - Verdict : PERTINENT / NON PERTINENT + pourquoi

2.1 Machine Learning sur les signaux

  A. Filtre ML sur la qualité du z-score
     Classifier (Random Forest, XGBoost) entraîné
     sur features du spread (z-score, half-life,
     volatilité du spread, régime de marché) pour
     prédire si le signal a une probabilité élevée
     d'être profitable → enrichit generator.py
     → models/ml_threshold_optimizer.py est-il
       déjà une implémentation partielle ?
     → Données historiques de paires suffisantes ?
     → Risque de lookahead bias sur z-score ?

  B. Activation réelle du ml_combiner.py
     signal_engine/ml_combiner.py semble déjà
     présent — est-il connecté au pipeline ?
     → Quel gap d'implémentation reste-t-il
       pour le rendre actif en live ?
     → Risque de régression du Sharpe si activé ?

  C. Détection de régime de marché actions US
     (HMM ou clustering sur VIX, spreads bid-ask,
     corrélations sectorielles, momentum SPY)
     → models/markov_regime.py et regime_detector.py
       sont-ils vraiment fonctionnels ?
     → Peut-on filtrer les entrées en régime de
       stress (cor > 0.8 entre toutes les paires) ?
     → IBKR fournit-il les données nécessaires ?

  D. Optimisation adaptative des seuils d'entrée
     Optimisation bayésienne (Optuna) sur
     entry_z_score, exit_z_score — réévalué
     sur fenêtre glissante mensuelle
     → models/adaptive_thresholds.py couvre-t-il
       déjà ce cas ?
     → Risque de suroptimisation sur un univers
       de paires étroit ?
     → Compatible avec _assert_risk_tier_coherence() ?

  E. Prédiction du sizing optimal
     Régression sur les conditions de marché
     (half-life, ATR du spread, corrélation paire)
     pour ajuster dynamiquement la taille de position
     → Compatible avec portfolio_engine/allocator.py ?
     → Conflit avec PositionRiskManager ?

2.2 Amélioration de la sélection de paires

  F. ML sur la stabilité de cointégration
     Classifier entraîné sur les features
     de la paire (p-value EG, Johansen stat,
     half-life, spread volatility) pour prédire
     la probabilité de breakup de cointégration
     dans les 30 prochains jours
     → models/structural_break.py couvre-t-il ça ?
     → Données suffisantes sur US équities ?

  G. Clustering sectoriel pour la sélection
     K-Means ou DBSCAN sur les paires candidates
     pour diversifier le portefeuille au-delà
     de la simple p-value de cointégration
     → pair_selection/filters.py le fait-il déjà ?
     → Améliore la décorrélation des positions ?

2.3 Agents IA autonomes

  H. Agent de retraining automatique
     models/model_retraining.py existe — est-il
     branché dans le scheduler/ ou orphelin ?
     → Peut-on l'activer sans risque en production ?
     → Fréquence de retraining adaptée (mensuel ?) ?

  I. Agent LLM pour filtrage macro
     Utilisation d'un LLM pour analyser
     news sectorielles (earnings, M&A, macro)
     et filtrer les signaux EDGECORE
     → signal_engine/sentiment.py existe — fonctionnel ?
     → Latence compatible avec la boucle live ?
     → Fiabilité sur paires US équities ?

  J. Agent de surveillance du pipeline
     Monitoring ML pour détecter data drift
     sur les z-scores, half-lives et hedge ratios
     → monitoring/ le fait-il déjà ?
     → Complément ou doublon de KillSwitch ?

2.4 Amélioration du backtest par ML

  K. SHAP values sur les paramètres de spread
     Analyse d'importance des features sur
     les résultats backtest pour identifier
     quels paramètres contribuent vraiment
     au Sharpe versus du bruit
     → backtests/metrics.py est-il assez riche ?
     → Compatible avec Cython en backtest ?

  L. Walk-forward adaptatif par régime
     Ajustement automatique des fenêtres IS/OOS
     selon la volatilité du marché actions
     → backtests/walk_forward.py et
       backtester/walk_forward.py : doublon ?
     → Améliore la stabilité OOS ?

─────────────────────────────────────────────
PHASE 3 — RECOMMANDATION FINALE
─────────────────────────────────────────────
3.1 Tableau de décision

| ID | Opportunité | Statut actuel | Verdict | Gain estimé | Complexité | Risque prod |
|----|-------------|---------------|---------|-------------|------------|-------------|
| A  | [titre]     | [ACTIF/ORPHELIN/ABSENT] | ✅/❌ | [métriques] | XS/S/M/L | Faible/Moyen/Élevé |

3.2 Roadmap recommandée

Si des opportunités sont PERTINENTES, propose
une séquence d'implémentation réaliste :

NIVEAU 1 — Sans risque pour la production
  (activation de modules orphelins existants,
   en mode observation uniquement,
   PAPER mode obligatoire, 0 trade live)

NIVEAU 2 — Intégration progressive
  (paper trading d'abord, validation OOS,
   venv\Scripts\python.exe -m pytest tests/ -q
   doit rester à 0 failed,
   puis production avec capital réduit)

NIVEAU 3 — Remplacement de composants existants
  (uniquement si NIVEAU 2 validé sur 30+ jours,
   risque tiers T1/T2/T3 non dégradé)

3.3 Ce qu'il ne faut PAS faire

Liste explicite des intégrations IA/ML à éviter
sur EDGECORE spécifiquement, avec justification :
- Trop complexe pour le gain attendu
- Risque de régression sur le Sharpe baseline
- Incompatible avec les contraintes IBKR TWS
- Introduit un lookahead bias dans le pipeline
- Nécessite modification de cointegration_fast.pyx :
  signaler le coût recompilation + risque régression
- Conflit avec la hiérarchie risk tiers T1/T2/T3

3.4 Verdict global

En 5 lignes maximum :
- Faut-il intégrer davantage d'IA/ML sur EDGECORE ?
- Quels modules orphelins existants méritent
  d'être activés en priorité ?
- Quel est le risque principal à surveiller ?

─────────────────────────────────────────────
SORTIE OBLIGATOIRE
─────────────────────────────────────────────
Crée le fichier :
  tasks/audits/audit_ia_ml_edgecore.md
Crée le dossier tasks/audits/ s'il n'existe pas.

Confirme dans le chat uniquement :
"✅ tasks/audits/audit_ia_ml_edgecore.md créé
 ✅ PERTINENT : X opportunités
 ❌ NON PERTINENT : X opportunités
 ⚠️ Modules orphelins détectés : X"
