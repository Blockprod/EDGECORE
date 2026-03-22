# PLAN D'ACTION — EDGECORE — 2026-03-22
Sources : `tasks/audits/audit_ia_ml_edgecore.md`
Total : 🔴 2 · 🟠 6 · 🟡 3 · Effort estimé : ~4 jours

> Note préliminaire : H-BUG-01 (KeyError `'p_value'` vs `'adf_pvalue'`) n'est
> **pas un bug actif** — `model_retraining.py` utilise déjà `"adf_pvalue"` aux
> lignes 248 et 316 (confirmé par grep). Il était mentionné dans l'ancien audit
> docs mais avait déjà été corrigé. Seul H-BUG-02 (datetime.now() sans UTC) est
> un bug réel.

---

## PHASE 1 — CRITIQUES 🔴

### [C-01] Wirer StructuralBreakDetector dans le pipeline signal live

Fichier : `signal_engine/generator.py` · `models/structural_break.py`
Problème : `StructuralBreakDetector` (CUSUM + stabilité récursive β) est
implémenté et testé mais n'a aucun consommateur en production. Le pipeline
live ne détecte pas les ruptures de la relation de cointégration (β drift
lent, invisible pour `StationarityMonitor`). C'est un angle mort opérationnel :
une paire peut continuer à trader après dégradation structurelle de β.

Correction :
1. Dans `signal_engine/generator.py`, importer `StructuralBreakDetector` et
   `StructuralBreakConfig` depuis `models/structural_break`.
2. Instancier un `StructuralBreakDetector` par paire dans `_initialize_pair()`
   (ou le stocker dans le state de paire).
3. Dans `_process_pair()`, après calcul du spread (résidus OLS), appeler
   `detector.check(residuals, y=series_y, x=series_x)`.
4. Si `has_break=True` : retourner un signal neutre (direction="none",
   confidence=0.0) et logger `structural_break_detected` avec les détails.
5. Ajouter une métrique Prometheus `edgecore_structural_break_total` (counter
   par paire) dans `monitoring/metrics.py`.

Validation :
```powershell
venv\Scripts\python.exe -m pytest tests/ -x -q -k "structural_break or generator"
# Attendu : tous les tests existants passent + le break est détecté
venv\Scripts\python.exe -m pytest tests/ -q
# Attendu : ≥ 2674 passed
```
Dépend de : Aucune
Statut : ✅ 2026-03-22

---

### [C-02] Corriger datetime.now() sans timezone dans model_retraining.py

Fichier : `models/model_retraining.py:223,297,337,342`
Problème : 4 occurrences de `datetime.now()` (naive, sans UTC) en violation
de la règle absolue du projet. Provoque un `DeprecationWarning` et des
comparaisons incorrectes si `PairDiscoveryMetadata.discovery_date` est aware.

Lignes concernées :
- L.223 : `cutoff_date = datetime.now() - timedelta(...)`
- L.297 : `cutoff_date = datetime.now() - timedelta(...)`
- L.337 : `metadata.last_reestimate_date = datetime.now()`
- L.342 : `metadata.metadata["invalidated_date"] = datetime.now().isoformat()`

Correction : Remplacer toutes les occurrences par `datetime.now(timezone.utc)`.
Vérifier que `from datetime import datetime, timezone, timedelta` est bien importé.

Validation :
```powershell
venv\Scripts\python.exe -m pytest tests/ -W error::DeprecationWarning -q -k "retraining"
# Attendu : 0 DeprecationWarning, tous les tests passent
venv\Scripts\python.exe -m pytest tests/ -q
# Attendu : ≥ 2674 passed
```
Dépend de : Aucune
Statut : ✅ 2026-03-22

---

## PHASE 2 — MAJEURES 🟠

### [C-03] Persistance joblib du modèle MLSignalCombiner entre sessions

Fichier : `signal_engine/ml_combiner.py` · `live_trading/runner.py`
Problème : `MLSignalCombiner._model` est purement en mémoire — perdu à chaque
redémarrage. Le walk-forward repart de zéro, exigeant un warm-up de plusieurs
semaines avant que le modèle soit entraîné. En live, cela signifie que le
combiner reste en mode fallback equal-weight indéfiniment.

Correction :
1. Ajouter deux méthodes à `MLSignalCombiner` :
   - `save(path: str | Path) -> None` : `joblib.dump(self._model, path)` +
     sauvegarder `_feature_importance`, `_last_train_bar`, `_n_trainings`.
   - `load(path: str | Path) -> bool` : `joblib.load(path)`, retourne `False`
     si le fichier n'existe pas.
2. Dans `live_trading/runner.py`, appeler `ml_combiner.load(...)` à
   l'initialisation et `ml_combiner.save(...)` après chaque retraining.
3. Path par défaut : `data/models/ml_combiner_{pair_key}.joblib`.
4. Créer le répertoire `data/models/` si inexistant.

Validation :
```powershell
venv\Scripts\python.exe -m pytest tests/ -x -q -k "ml_combiner"
# Attendu : tous les tests ml_combiner passent + nouveaux tests save/load
venv\Scripts\python.exe -m pytest tests/ -q
# Attendu : ≥ 2674 passed
```
Dépend de : Aucune
Statut : ✅ 2026-03-22

---

### [C-04] Shadow mode MLSignalCombiner (prédire sans trader, logging 30 jours)

Fichier : `live_trading/runner.py` · `signal_engine/ml_combiner.py` ·
          `config/settings.py`
Problème : `MLSignalCombiner` n'est pas câblé dans `live_trading/runner.py`.
Activer directement le combiner ML en trading live sans période de validation
est un risque opérationnel. Un mode shadow (predict-only, log the signals)
est nécessaire pour comparer les prédictions ML vs les signaux actuels pendant
30 jours avant bascule.

Correction :
1. Ajouter `ml_combiner_shadow_mode: bool = True` dans `SignalCombinerConfig`
   (config/settings.py).
2. Dans `live_trading/runner.py` : instancier `MLSignalCombiner` et appeler
   `ml_combiner.combine(features)` à chaque signal, mais **uniquement logger**
   le résultat si `shadow_mode=True` (pas d'impact sur l'ordre).
3. Logger `ml_signal_shadow` avec `composite_score`, `direction`, `confidence`,
   `model_trained` à chaque barre traitée.
4. En `shadow_mode=False` : utiliser `ml_combiner.direction` pour filtrer les
   signaux (gate : ne trader que si `ml_combiner.direction == signal.direction`).

Validation :
```powershell
venv\Scripts\python.exe -m pytest tests/ -x -q -k "shadow or ml_combiner"
# Attendu : tests shadow mode passent
venv\Scripts\python.exe -m pytest tests/ -q
# Attendu : ≥ 2674 passed
```
Dépend de : C-03
Statut : ✅ 2026-03-22

---

### [C-05] Valider hmmlearn dans requirements.txt

Fichier : `requirements.txt`
Problème : `models/markov_regime.py` importe `hmmlearn` de façon conditionnelle
(`try/except`). Si `hmmlearn` n'est pas dans `requirements.txt`, l'installation
en production (Dockerfile) ne l'inclura pas, et `MarkovRegimeDetector` tombera
silencieusement sur le fallback percentile sans avertissement opérateur.

Correction :
1. Vérifier si `hmmlearn` est présent dans `requirements.txt`.
2. Si absent : ajouter `hmmlearn>=0.3.0,<0.4.0`.
3. Vérifier que l'import fonctionne dans le venv actuel :
   `venv\Scripts\python.exe -c "import hmmlearn; print(hmmlearn.__version__)"`.
4. Si absent du venv, installer : `venv\Scripts\pip.exe install hmmlearn`.

Validation :
```powershell
venv\Scripts\python.exe -c "from hmmlearn import hmm; print('OK')"
# Attendu : OK
venv\Scripts\python.exe -m pytest tests/ -q -k "markov"
# Attendu : tests markov passent
```
Dépend de : Aucune
Statut : ⏳

---

### [C-06] Câbler MarkovRegimeDetector dans generator.py (canary, flag config)

Fichier : `signal_engine/generator.py` · `models/markov_regime.py` ·
          `config/settings.py`
Problème : `MarkovRegimeDetector` (HMM 3 états, fallback percentile intégré)
est orphelin. `RegimeDetector` (percentile) en place est simple mais ne
modélise pas les transitions probabilistes entre régimes — transitions abruptes
visibles sur données de volatilité en régime extrême.

Correction :
1. Ajouter `use_markov_regime: bool = False` dans `StrategyConfig` ou
   `SignalCombinerConfig` (config/settings.py).
2. Dans `signal_engine/generator.py`, si `use_markov_regime=True`, instancier
   `MarkovRegimeDetector` à la place de `RegimeDetector`.
3. `MarkovRegimeDetector` implémente le fallback percentile si `hmmlearn` est
   absent → aucun risque opérationnel.
4. Écrire un test de régression : sur 252 barres synthétiques, comparer les
   régimes produits par `MarkovRegimeDetector` vs `RegimeDetector` — ils doivent
   être corrélés (concordance ≥ 60%).

Validation :
```powershell
venv\Scripts\python.exe -m pytest tests/ -x -q -k "markov or regime"
# Attendu : tests régression concordance passent
venv\Scripts\python.exe -m pytest tests/ -q
# Attendu : ≥ 2674 passed
```
Dépend de : C-05
Statut : ⏳

---

### [C-07] Câbler ModelRetrainingManager dans scheduler/

Fichier : `models/model_retraining.py` · `scheduler/` (nouveau ou existant)
Problème : `ModelRetrainingManager` existe dans `strategies/pair_trading.py`
(import lazy, ligne 106) mais n'est jamais invoqué automatiquement. La
re-découverte de paires et la re-estimation des hedge ratios β ne se produisent
jamais sans trigger manuel. Le scheduler/ est vide de cette logique.

Correction :
1. Lire le contenu de `scheduler/` pour identifier la structure existante.
2. Créer ou étendre la tâche périodique de retraining dans `scheduler/` :
   - Fréquence par défaut : toutes les 2 semaines (configurable via settings).
   - Appeler `ModelRetrainingManager.discover_cointegrated_pairs()` et
     `reestimate_hedge_ratios()`.
   - Logger `retraining_report` avec le résumé `RetrainingReport`.
3. Câbler la tâche dans le scheduler existant avec gestion d'erreurs.
4. Ajouter un garde : ne pas retrainer si le KillSwitch est actif.

Validation :
```powershell
venv\Scripts\python.exe -m pytest tests/ -x -q -k "retraining or scheduler"
# Attendu : tests retraining planifié passent
venv\Scripts\python.exe -m pytest tests/ -q
# Attendu : ≥ 2674 passed
```
Dépend de : C-02
Statut : ⏳

---

## PHASE 3 — MINEURES 🟡

### [C-08] Clustering hiérarchique sur matrice de corrélation existante

Fichier : `pair_selection/discovery.py`
Problème : La pré-sélection de paires repose uniquement sur filtres statistiques
(corrélation ≥ 0.70, EG + Johansen + Newey-West, half-life ≤ 60j). Des paires
économiquement non liées peuvent passer les tests si la corrélation est
temporairement élevée. Un clustering sur la matrice de corrélation permettrait
de regrouper les actifs économiquement liés avant de tester la cointégration.

Correction :
1. Après calcul de la matrice de corrélation dans `PairDiscoveryEngine`, appeler
   `scipy.cluster.hierarchy.linkage(1 - corr_matrix, method="ward")` sur les
   symboles.
2. Avec `fcluster(linkage, t=0.5, criterion="distance")`, ne former des paires
   que dans le même cluster (évite les paires inter-cluster).
3. Ajouter `use_clustering: bool = False` dans `DiscoveryConfig` — désactivé
   par défaut pour ne pas modifier le comportement existant.
4. Logger le nombre de paires filtrées par clustering.

Validation :
```powershell
venv\Scripts\python.exe -m pytest tests/ -x -q -k "discovery or pair_selection"
# Attendu : tests existants passent, clustering optionnel testé
venv\Scripts\python.exe -m pytest tests/ -q
# Attendu : ≥ 2674 passed
```
Dépend de : Aucune
Statut : ⏳

---

### [C-09] PSI drift monitoring pour les features MLSignalCombiner

Fichier : `monitoring/` (nouveau module `ml_drift.py`) · `signal_engine/ml_combiner.py`
Problème : Aucun module ne surveille le drift de distribution des features
d'entrée du `MLSignalCombiner` (zscore, momentum, ou, vol_regime, etc.) entre
la distribution d'entraînement et la distribution courante live. Un drift
significatif rend les prédictions ML non fiables sans avertissement.

Correction :
1. Dans `MLSignalCombiner`, sauvegarder les statistiques de la distribution
   d'entraînement (mean, std par feature) lors de chaque `_retrain()`.
2. Créer `monitoring/ml_drift.py` avec `MLFeatureDriftMonitor` :
   - `compute_psi(expected, actual, n_bins=10)` : Population Stability Index.
   - Seuils : PSI < 0.1 = stable, 0.1–0.25 = avertissement, > 0.25 = drift critique.
3. Appeler `MLFeatureDriftMonitor.check()` toutes les 252 barres et logger
   `ml_feature_drift` avec le PSI par feature.
4. Déclencher une alerte `alerter.py` si PSI > 0.25 pour ≥ 3 features.

Validation :
```powershell
venv\Scripts\python.exe -m pytest tests/ -x -q -k "drift or psi"
# Attendu : tests PSI passent
venv\Scripts\python.exe -m pytest tests/ -q
# Attendu : ≥ 2674 passed
```
Dépend de : C-04
Statut : ⏳

---

### [C-10] Fréquence de retraining proportionnelle au régime de marché

Fichier : `models/model_retraining.py` · `scheduler/`
Problème : `ModelRetrainingManager` utilise une fréquence de re-estimation fixe
(`reestimation_frequency_days=14`). En régime haute volatilité (détecté par
`RegimeDetector` = HIGH), les relations de cointégration se dégradent plus vite
— un retraining plus fréquent est justifié.

Correction :
1. Injecter `RegimeDetector` dans `ModelRetrainingManager` (optionnel, via
   constructeur).
2. Dans la logique du scheduler (C-07), consulter `RegimeDetector.current_regime`
   avant de décider si un retraining est dû :
   - Régime LOW : fréquence × 2 (moins souvent)
   - Régime NORMAL : fréquence nominale (14 jours)
   - Régime HIGH : fréquence / 2 (plus souvent, min 7 jours)
3. Logger la fréquence effective utilisée dans chaque cycle de retraining.

Validation :
```powershell
venv\Scripts\python.exe -m pytest tests/ -x -q -k "retraining or regime"
# Attendu : tests fréquence adaptative passent
venv\Scripts\python.exe -m pytest tests/ -q
# Attendu : ≥ 2674 passed
```
Dépend de : C-07
Statut : ⏳

---

## SÉQUENCE D'EXÉCUTION

```
Étape 1 (parallélisables — sans dépendances mutuelles)
├── C-01  Wirer StructuralBreakDetector                        ~2h
├── C-02  Corriger datetime.now() (tzinfo UTC)                 ~1h
└── C-05  Valider/ajouter hmmlearn dans requirements.txt       ~0.5h

Étape 2 (après Étape 1)
├── C-03  Persistance joblib MLSignalCombiner                  ~3h
└── C-07  Câbler ModelRetrainingManager dans scheduler/        ~4h   (après C-02)

Étape 3 (après Étape 2)
├── C-04  Shadow mode MLSignalCombiner                         ~4h   (après C-03)
├── C-06  Câbler MarkovRegimeDetector dans generator.py        ~2h   (après C-05)
└── C-08  Clustering hiérarchique pair_selection               ~6h

Étape 4 (après Étape 3)
├── C-09  PSI drift monitoring features ML                     ~4h   (après C-04)
└── C-10  Fréquence retraining adaptative au régime            ~3h   (après C-07)
```

---

## CRITÈRES PASSAGE EN PRODUCTION

- [ ] Zéro 🔴 ouvert
- [ ] `pytest tests/ -q` : 100% pass (≥ 2674)
- [ ] `pytest tests/ -W error::DeprecationWarning -q` : 0 DeprecationWarning
- [ ] `mypy risk/ risk_engine/ execution/ --ignore-missing-imports --no-error-summary` : exit 0
- [ ] `ruff check .` : 0 erreurs
- [ ] Zéro `datetime.now()` sans timezone dans les modules modifiés
- [ ] Kill-switch persisté au redémarrage
- [ ] Risk tiers cohérents (`_assert_risk_tier_coherence()` OK)
- [ ] `EDGECORE_ENV=prod` dans Dockerfile (pas `"production"`)
- [ ] `StructuralBreakDetector` loggue `structural_break_detected` sur paires dégradées
- [ ] `MLSignalCombiner` en shadow mode 30 jours avant activation live
- [ ] `hmmlearn` disponible dans le venv et dans `requirements.txt`
- [ ] Paper trading validé avant live

---

## TABLEAU DE SUIVI

| ID    | Titre                                          | Sévérité | Fichier(s) principal(aux)               | Effort | Statut | Date |
|-------|------------------------------------------------|----------|-----------------------------------------|--------|--------|------|
| C-01  | Wirer StructuralBreakDetector (pipeline live)  | 🔴        | signal_engine/generator.py              | ~2h    | ✅     | 2026-03-22 |
| C-02  | Corriger datetime.now() sans UTC               | 🔴        | models/model_retraining.py:223,297,337,342 | ~1h | ✅     | 2026-03-22 |
| C-03  | Persistance joblib MLSignalCombiner            | 🟠        | signal_engine/ml_combiner.py            | ~3h    | ✅     | 2026-03-22 |
| C-04  | Shadow mode MLSignalCombiner (live)            | 🟠        | live_trading/runner.py                  | ~4h    | ✅     | 2026-03-22 |
| C-05  | Valider hmmlearn dans requirements.txt         | 🟠        | requirements.txt                        | ~0.5h  | ✅     | 2026-03-22 |
| C-06  | Câbler MarkovRegimeDetector (canary + config)  | 🟠        | signal_engine/generator.py              | ~2h    | ✅     | 2026-03-22 |
| C-07  | Câbler ModelRetrainingManager dans scheduler/  | 🟠        | scheduler/ + models/model_retraining.py | ~4h    | ✅     | 2026-03-22 |
| C-08  | Clustering hiérarchique pair_selection         | 🟡        | pair_selection/discovery.py             | ~6h    | ✅     | 2026-03-22 |
| C-09  | PSI drift monitoring features MLSignalCombiner | 🟡        | monitoring/ml_drift.py (nouveau)        | ~4h    | ✅     | 2026-03-22 |
| C-10  | Fréquence retraining adaptative au régime      | 🟡        | models/model_retraining.py + scheduler/ | ~3h    | ✅     | 2026-03-22 |
