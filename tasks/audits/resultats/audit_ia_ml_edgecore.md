# Audit IA/ML — EDGECORE V1
date: 2026-03-22
creation: 2026-03-22 à 00:21
auteur: GitHub Copilot (audit_ia_ml_prompt.md)
base: 2674 tests passants

---

## PHASE 1 — Inventaire et statut des modules IA/ML

### 1.1 Carte de statut

| Statut | Module | Classe principale | Observations |
|--------|--------|-------------------|--------------|
| ✅ ACTIF | `signal_engine/adaptive.py` | `AdaptiveThresholdEngine` | Wired `generator.py:25` + `runner.py:228` |
| ✅ ACTIF | `models/adaptive_thresholds.py` | `AdaptiveThresholdCalculator` | Via `AdaptiveThresholdEngine` |
| ✅ ACTIF | `models/regime_detector.py` | `RegimeDetector` | `generator.py:21` — percentile LOW/NORMAL/HIGH |
| ✅ ACTIF | `signal_engine/zscore.py` | `ZScoreCalculator` | `generator.py:26` — half-life adaptive |
| ✅ ACTIF | `models/stationarity_monitor.py` | `StationarityMonitor` | `generator.py:24` |
| ✅ ACTIF | `signal_engine/momentum.py` | `MomentumOverlay` | Optionnel, injecté via constructor |
| 🟡 PARTIEL | `signal_engine/ml_combiner.py` | `MLSignalCombiner` | Backtest only — `strategy_simulator.py:43,194,1454` |
| 🟡 PARTIEL | `signal_engine/market_regime.py` | `MarketRegimeFilter` | Backtest only — `strategy_simulator.py:42,213,530` |
| 🟡 PARTIEL | `signal_engine/sentiment.py` | `SentimentSignal` | `pair_trading.py:27` + `strategy_simulator.py:45` — pas de live |
| 🟡 PARTIEL | `signal_engine/options_flow.py` | `OptionsFlowSignal` | `pair_trading.py:25` + `strategy_simulator.py:44` — pas de live |
| 🟡 PARTIEL | `models/model_retraining.py` | `ModelRetrainingManager` | `pair_trading.py:106` (lazy import) — pas de scheduler |
| 🟡 PARTIEL | `signal_engine/combiner.py` | `SignalCombiner` | `pair_trading.py:159` — PAS dans `runner.py` ni `generator.py` |
| 🔴 ORPHELIN | `models/markov_regime.py` | `MarkovRegimeDetector` | Défini uniquement dans son propre fichier — aucun consommateur |
| 🔴 ORPHELIN | `models/ml_threshold_optimizer.py` | `MLThresholdOptimizer` | Tests seulement — jamais wired en production |
| 🔴 ORPHELIN | `models/ml_threshold_validator.py` | `MLThresholdValidator` | Appelé uniquement depuis `ml_threshold_optimizer.py` |
| 🔴 ORPHELIN | `models/structural_break.py` | `StructuralBreakDetector` | Défini uniquement dans son propre fichier — aucun consommateur |

### 1.2 Pipeline signal live (confirmé via `generator.py` + `runner.py`)

```
SpreadModel (OLS β ± Kalman optionnel)
  → ZScoreCalculator (lookback adapté au half-life)
  → RegimeDetector (percentile : LOW / NORMAL / HIGH)
  → AdaptiveThresholdEngine (entry [1.0–3.5], exit [0.5] selon régime)
  → MomentumOverlay (optionnel, non wired par défaut dans runner.py)
  → Signal { direction, z_score, threshold, confidence }
```

**Observations critiques :**
- `SignalCombiner` (poids 0.70 z-score + 0.30 momentum) n'est **PAS** utilisé par `generator.py` — le
  générateur applique son propre overlay momentum séparément.
- `MLSignalCombiner` (GBT/LightGBM walk-forward) est entraîné et utilisé en **backtest uniquement** —
  aucun chemin vers le live runner.
- `MarketRegimeFilter` (SPY MA50/MA200 : BULL/BEAR/MR/NEUTRAL) est **backtest uniquement**.

### 1.3 État du walk-forward

| Fichier | Rôle | Relation |
|---------|------|----------|
| `backtests/walk_forward.py` | Implémentation (`WalkForwardBacktester`, `split_walk_forward`) | Source de vérité |
| `backtester/walk_forward.py` | Façade (`WalkForwardEngine`) qui wrappe `backtests/walk_forward` | Légitime — PAS un doublon |

Architecture en couches : `backtester/` est la façade haut niveau qui expose une API propre au-dessus
de `backtests/`.

### 1.4 Modules de monitoring (drift IA/ML)

`monitoring/correlation_monitor.py` surveille la **corrélation des paires** (`PairCorrelationTracker`,
`CorrelationMonitor`) — utile mais ce n'est pas du monitoring de drift de features ML.

**Aucun module de détection de drift de distribution de features n'existe** dans `monitoring/`.

### 1.5 Persistance des modèles ML

`persistence/audit_trail.py` = audit des trades. **Aucun mécanisme de sérialisation de modèle ML**
(joblib, pickle) n'est présent dans le codebase. `MLSignalCombiner._model` est purement en mémoire,
perdu à chaque redémarrage → le walk-forward repart de zéro à chaque session.

---

## PHASE 2 — Audit des 12 opportunités (A–L)

---

### A · Filtre ML sur le z-score (seuil adaptatif piloté par RandomForest)

**Description :** `models/ml_threshold_optimizer.py` optimise les seuils entry/exit avec un
RandomForest entraîné sur données synthétiques. `models/ml_threshold_validator.py` fait une
validation walk-forward OOS en 5-fold.

**Statut actuel :** 🔴 ORPHELIN. `MLThresholdOptimizer` est couvert par des tests mais n'est jamais
appelé depuis `signal_engine/adaptive.py`, `generator.py` ou `runner.py`. Or `AdaptiveThresholdEngine`
calcule déjà des seuils adaptatifs basés sur le régime de volatilité et le half-life (implémentation
dans `models/adaptive_thresholds.py`).

**Analyse :**
- `AdaptiveThresholdEngine` (ACTIF) couvre déjà le besoin adaptatif avec une logique percentile simple.
- Ajouter `MLThresholdOptimizer` crée une double couche d'adaptation sans gain clair.
- Les données synthétiques utilisées pour l'entraînement constituent un risque de surfit.
- La valeur marginale est faible tant que `AdaptiveThresholdEngine` n'est pas validé insuffisant.

**Recommandation :** ❌ **NON PERTINENT** à court terme.
Prérequis avant d'envisager : mesurer empiriquement les seuils produits par `AdaptiveThresholdEngine`
vs rendements live. Si le gap est significatif, envisager un Optuna HPO sur données réelles plutôt
qu'un modèle RF.

---

### B · Activation de `MLSignalCombiner` en pipeline live

**Description :** `signal_engine/ml_combiner.py` est un combineur GBT/LightGBM walk-forward prêt,
avec interface `combine()` compatible `SignalCombiner`. Il est fonctionnel en backtest
(`strategy_simulator.py`) avec gestion du purge gap, de l'imbalance de classes et du fallback
equal-weight.

**Statut actuel :** 🟡 PARTIEL. Qualité du code : ✅ robuste. Gap unique : n'est pas instancié dans
`live_trading/runner.py` ni dans `signal_engine/generator.py`.

**Analyse :**
- Le code est mature, l'interface est propre et la validation walk-forward existe en backtest.
- L'activation en live nécessite :
  1. Un mécanisme de **persistance du modèle entraîné** (limiter le warm-up time à chaque restart).
  2. La décision architecturale de câbler le combiner dans `generator.py` via injection de
     dépendance (le `MomentumOverlay` actuel serait remplacé ou complété).
  3. Une période de shadow mode (prédire sans trader) pour valider les prédictions live vs backtest.
- Risque principal : le fallback equal-weight garantit la continuité opérationnelle.

**Recommandation :** ✅ **PERTINENT — Priorité 1.**
Travail estimé : câblage `runner.py` + ajout persistance joblib + shadow mode 30 jours.
Blocker actuel : absence de serialisation modèle (voir finding §1.5).

---

### C · Activation du détecteur de régime HMM (MarkovRegimeDetector)

**Description :** `models/markov_regime.py` implémente un HMM gaussien à 3 états via `hmmlearn`
(import conditionnel, fallback percentile si absent). Conçu pour remplacer ou compléter
`RegimeDetector` (percentile).

**Statut actuel :** 🔴 ORPHELIN. Aucun consommateur en production ou en backtest.

**Analyse :**
- `RegimeDetector` (percentile) en place est simple, stable et testable.
- HMM 3 états apporte une modélisation probabiliste de la transition de régime (la valeur ajoutée est
  réelle sur données de volatilité).
- Le fallback percentile est déjà codé dans `markov_regime.py` — la robustesse est assurée.
- `hmmlearn` est une dépendance à valider dans `requirements.txt`.
- Wiring minimal : remplacer `RegimeDetector` par `MarkovRegimeDetector` dans `generator.py:97`.

**Recommandation :** ✅ **PERTINENT — Priorité 2.**
Prérequis : vérifier `hmmlearn` dans requirements, écrire test de régression vs percentile,
activer en canary sur 1 paire avant généralisation.

---

### D · Optimisation des seuils via Optuna (HPO)

**Description :** Remplacer les seuils statiques (entry_z_score, exit_z_score) par une optimisation
bayésienne Optuna sur données historiques.

**Statut actuel :** `entry_z_score=2.0` et `exit_z_score=0.5` lus depuis `config/settings.py` via
`get_settings()` ✅ — les seuils ne sont pas hardcodés.

**Analyse :**
- `AdaptiveThresholdEngine` (ACTIF) ajuste déjà les seuils dynamiquement selon le régime.
- Optuna apporterait une optimisation globale offline des hyperparamètres de base, mais :
  - Le risque d'overfitting sur la période d'entraînement est élevé (stat-arb est non-stationnaire).
  - La complexité d'ajout (pipeline HPO, reproductibilité, CI/CD) est significative pour un gain hypothétique.

**Recommandation :** ❌ **NON PERTINENT** à ce stade.
Revisiter si `AdaptiveThresholdEngine` montre des lacunes mesurables en comparaison aux seuils fixes.

---

### E · Sizing ML (position sizing piloté par IA)

**Description :** Remplacer la logique de `PortfolioAllocator` par un modèle de sizing appris
(régression ou RL).

**Statut actuel :** `PortfolioAllocator` + `PositionRiskManager` gèrent le sizing via règles de
risque paramétrisées depuis `get_settings()`.

**Analyse :**
- L'architecture risk-first du projet (`RiskConfig.max_drawdown_pct`, `KillSwitchConfig`) rend un
  sizing ML potentiellement dangereux : le modèle pourrait contourner les tiers de risque.
- Conflit direct avec l'assertion `_assert_risk_tier_coherence()`.
- Le RL pour sizing nécessite un environnement de simulation à l'échelle live — infrastructure absent.

**Recommandation :** ❌ **NON PERTINENT** — risque opérationnel trop élevé sans isolement garanti
des tiers de risque.

---

### F · Activation du détecteur de rupture structurelle

**Description :** `models/structural_break.py` implémente CUSUM + stabilité récursive de β
(flaveur Bai-Perron simplifiée). Complète `StationarityMonitor` qui teste la stationnarité du spread
mais ne détecte pas les changements de la relation de cointégration elle-même.

**Statut actuel :** 🔴 ORPHELIN. Implementation mature, zero consommateur.

**Analyse :**
- Gap confirmé : `StationarityMonitor` détecte la non-stationnarité du spread a posteriori,
  `StructuralBreakDetector` détecte les ruptures de β (cointégration) en temps quasi-réel.
- Les deux tests sont complémentaires — absence de `StructuralBreakDetector` est un angle mort opérationnel.
- Performance : CUSUM sur 252 obs ≈ 2–5 ms (acceptable bar-by-bar).
- Wiring : `generator.py._process_pair()` après calcul du spread, avant génération du signal —
  si `has_break=True`, retourner signal neutre et déclencher alerte.

**Recommandation :** ✅ **PERTINENT — Priorité 1.**
C'est la correction d'un angle mort de risque, pas une optimisation ML. Wiring simple dans
`generator.py`, impact de robustesse immédiat.

---

### G · Clustering sectoriel pour la sélection de paires

**Description :** Remplacer ou compléter la pré-sélection de paires par du clustering ML
(K-Means, DBSCAN ou hierarchical sur facteurs sectoriels).

**Statut actuel :** `pair_selection/discovery.py` utilise filtres statistiques uniquement :
corrélation ≥ 0.70, cointegration EG + Johansen, Newey-West HAC, half-life ≤ 60j.
Aucun composant ML de clustering.

**Analyse :**
- Le clustering peut réduire les faux positifs de cointégration entre paires économiquement non liées.
- Impact modéré : les filtres EG + Johansen + NW existants sont déjà multi-couches.
- Risque d'overfitting : les clusters sectoriels peuvent changer de régime (COVID, secteurs ESG, etc.).
- Complexité d'implémentation : le clustering nécessite des données fondamentales (secteur SIC, β
  factoriel) non encore présentes dans la stack.

**Recommandation :** 🟡 **PERTINENT — Priorité 3** (après F et B).
Point de départ recommandé : clustering hiérarchique sur la matrice de corrélation existante
(déjà calculée), sans dépendances externes additionnelles.

---

### H · Retraining automatique planifié (ModelRetrainingManager)

**Description :** `models/model_retraining.py` fournit `ModelRetrainingManager` pour la
re-découverte périodique de paires et la re-estimation des hedge ratios β. Un import lazy existe
dans `strategies/pair_trading.py:106` mais aucun scheduler ne l'invoque.

**Statut actuel :** 🟡 PARTIEL + bugs connus :
1. **KeyError bug** : `'p_value'` vs `'adf_pvalue'` (la clé renvoyée par
   `engle_granger_test_cpp_optimized` peut différer selon l'implémentation Cython vs Python).
2. **Biais backtest** : `datetime.now()` utilisé dans le contexte de simulation au lieu du temps
   de simulation — violation de la règle `datetime.now(timezone.utc)`.

**Analyse :**
- La valeur du retraining automatique est significative (adaptation aux régimes de marché).
- Les bugs doivent être corrigés avant toute activation en production.
- Le scheduler (`scheduler/`) est vide — intégration manquante complète.
- Risque de réobserver une paire invalidée dans la même session si le cache n'est pas purgé.

**Recommandation :** 🟡 **PERTINENT — Priorité 2**, mais **blocké par 2 bugs à corriger d'abord**.

**Corrections requises (H-BUG-01, H-BUG-02) :**
```python
# H-BUG-01 : dans model_retraining.py — adapter la clé selon l'implémentation
# Chercher la clé correcte via :
result = engle_granger_test(...)
# La clé est 'adf_pvalue' (vérifier dans models/cointegration.py)

# H-BUG-02 : remplacer datetime.now() par le paramètre simulation_time
# Toute référence à datetime.now() dans model_retraining.py doit recevoir
# le temps de simulation comme paramètre injecté
```

---

### I · Filtrage macro par LLM

**Description :** Utiliser un LLM (GPT, FinBERT) pour filtrer les signaux lors d'événements macro
(FOMC, CPI, NFP).

**Statut actuel :** `signal_engine/sentiment.py` utilise déjà FinBERT en mode live et un proxy
prix en backtest. Mais latence LLM ≈ 500–2000 ms incompatible avec un pipeline bar-by-bar.

**Analyse :**
- Latence incompatible avec les contraintes temps-réel (< 50 ms par paire souhaitables).
- Les données macro en temps réel nécessitent des abonnements (Bloomberg, Refinitiv) non présents.
- `SentimentSignal` existant couvre partiellement le cas d'usage.

**Recommandation :** ❌ **NON PERTINENT** en live.
Acceptable en pré-calcul offline (cache journalier) mais investissement démesuré vs impact.

---

### J · Monitoring de drift de features ML

**Description :** Détecter quand les distributions des features du `MLSignalCombiner` dérivent
significativement par rapport à la distribution d'entraînement.

**Statut actuel :** `monitoring/correlation_monitor.py` surveille la corrélation des paires,
pas le drift de distribution des features IA/ML. **Aucun module de drift ML n'existe.**

**Analyse :**
- Sans persistance du modèle (finding §1.5), le drift de features ne peut pas être mesuré entre
  sessions.
- La valeur devient pertinente uniquement après activation de `MLSignalCombiner` en live (opportunité B).
- L'implémentation minimale viable : PSI (Population Stability Index) sur chaque feature vs
  distribution de référence d'entraînement.

**Recommandation :** 🟡 **PERTINENT mais dépendant de B.**
À planifier comme Priorité 2 simultanément avec l'activation live de `MLSignalCombiner`.

---

### K · Valeurs SHAP pour l'interprétabilité

**Description :** Calculer des valeurs SHAP sur `MLSignalCombiner` pour auditer les features
les plus influentes.

**Statut actuel :** `MLSignalCombiner` expose déjà `feature_importance` (impureté Gini) dans
`MLPrediction.feature_importance`. SHAP n'est pas implémenté.

**Analyse :**
- `feature_importances_` Gini est déjà disponible et logué à chaque entraînement.
- SHAP apporte une interprétabilité locale (par prédiction) — valeur surtout pour l'audit.
- Impact opérationnel nul — usage offline uniquement.
- Complexité : `shap` est une dépendance additionnelle, SHAP sur TreeModel ≈ 1–10 ms.

**Recommandation :** ❌ **NON PERTINENT — usage offline ponctuel.**
L'importance Gini existante suffit pour le monitoring. SHAP peut être utilisé ad hoc en notebook
sans l'intégrer dans le pipeline.

---

### L · Walk-forward adaptatif (rebalancement dynamique de la fréquence)

**Description :** Ajuster dynamiquement la durée de la fenêtre d'entraînement et l'intervalle de
rebalancement du walk-forward selon des métriques de performance OOS.

**Statut actuel :**
- `backtests/walk_forward.py` : fenêtres fixes (train=504 bars, OOS=126 bars par défaut).
- `backtester/walk_forward.py` : façade propre, wrappant l'implémentation — architecture en couches
  **légitime** (pas un doublon).
- Les paramètres sont configurables mais statiques.

**Analyse :**
- Le walk-forward adaptatif (Combinatorial Purged CV, anchored vs rolling) ajoute de la complexité
  pour un gain discutable en stat-arb — les recherches académiques montrent des résultats mixtes.
- Le vrai gain serait dans la **fréquence de retraining adaptative** (plus souvent en régime haute
  volatilité, moins en régime stable) — réalisable avec `model_retraining.py` + `RegimeDetector`.
- Architecture existante (2 couches) est propre et suffisante.

**Recommandation :** 🟡 **PARTIELLEMENT PERTINENT.**
Le walk-forward adaptatif complet est coûteux. La version simplifiée (fréquence de retraining
proportionnelle au régime VIX) est une extension de `ModelRetrainingManager` — pertinente mais
dépendante de la correction des bugs H-BUG-01/H-BUG-02.

---

## PHASE 3 — Plan d'action priorisé

### Priorités et séquençage

```
P1 (corrections risque / angle mort — faire immédiatement)
├── F·1  Wirer StructuralBreakDetector dans generator._process_pair()
│        Impact: ferme un angle mort opérationnel sur la dégradation β
│        Effort: ~2h (1 import + 1 guard + 1 test)
│
└── H·BUG  Corriger KeyError 'p_value' et datetime.now() dans model_retraining.py
         Impact: débloque l'activation planifiée du retraining automatique
         Effort: ~1h

P2 (activation modules existants — valeur élevée, effort modéré)
├── B·1  Persistance MLSignalCombiner (joblib dump/load à chaque fin de session)
│        Effort: ~3h
├── B·2  Shadow mode MLSignalCombiner en live (30 jours logging sans trading)
│        Effort: ~4h
├── C·1  Valider hmmlearn dans requirements.txt
│        Effort: 30 min
├── C·2  Test de régression MarkovRegimeDetector vs RegimeDetector
│        Effort: ~2h
├── C·3  Wirer MarkovRegimeDetector dans generator.py (canary 1 paire)
│        Effort: ~2h
└── H·1  Câbler ModelRetrainingManager dans scheduler/ (après bugs corrigés)
         Effort: ~4h

P3 (améliorations itératives — planifier après P1+P2)
├── G·1  Clustering hiérarchique sur matrice corrélation existante
│        Effort: ~6h
├── J·1  PSI drift monitoring pour features MLSignalCombiner (post-activation B)
│        Effort: ~4h
└── L·1  Fréquence de retraining proportionnelle au régime (extension H)
         Effort: ~3h (après H·1)

Non retenu
├── A  MLThresholdOptimizer — doublon de AdaptiveThresholdEngine
├── D  HPO Optuna — risque overfitting, AdaptiveThresholdEngine suffisant
├── E  Sizing ML — conflit avec tiers de risque
├── I  LLM macro — latence incompatible
└── K  SHAP — offline ad hoc en notebook
```

---

## Annexe — Résumé des modules orphelins

Ces 4 modules ont du code de qualité mais sont **actuellement inutilisés en production**.
Ils ne doivent pas être supprimés — ils sont soit des candidats à l'activation (C, F) soit
des outils offline (A, K dépendant).

| Module | Classe | Potentiel | Action recommandée |
|--------|--------|-----------|-------------------|
| `models/markov_regime.py` | `MarkovRegimeDetector` | HMM 3 états, fallback intégré | Activer en canary (P2·C) |
| `models/structural_break.py` | `StructuralBreakDetector` | CUSUM + β drift, mature | Wirer immédiatement (P1·F) |
| `models/ml_threshold_optimizer.py` | `MLThresholdOptimizer` | RF sur données synthétiques | Différer — valeur marginale |
| `models/ml_threshold_validator.py` | `MLThresholdValidator` | Walk-forward 5-fold | Garder pour tests régression |

---

## Annexe — Bugs connus à corriger avant activation (H)

### H-BUG-01 : KeyError dans `model_retraining.py`

```python
# Problème probable (à vérifier)
result["p_value"]      # KeyError si la clé est 'adf_pvalue'

# Correction à appliquer après vérification de models/cointegration.py
result.get("adf_pvalue") or result.get("p_value")
```

### H-BUG-02 : `datetime.now()` dans `model_retraining.py`

```python
# Interdit (violation règle utcnow/naive)
discovery_date=datetime.now()

# Correct — passer le temps de simulation comme paramètre
discovery_date=simulation_time  # datetime with timezone.utc
```

---

*Audit terminé. 2674 tests passants non affectés par cet audit (lecture seule).*
