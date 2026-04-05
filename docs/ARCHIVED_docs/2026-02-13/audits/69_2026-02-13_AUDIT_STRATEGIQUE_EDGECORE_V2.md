<<<<<<< HEAD
﻿# AUDIT STRAT├ëGIQUE ÔÇö EDGECORE V2

**Date :** 12 f├®vrier 2026  
**Auditeur :** Senior Quant Researcher & Risk Architect  
**P├®rim├¿tre :** Strat├®gie Statistical Arbitrage (Pair Trading Mean Reversion) ÔÇö code r├®el uniquement  
**Verdict anticip├® :** ­ƒƒá Strat├®gie structurellement fragile ÔÇö exploitable sous conditions strictes

---

## 1. Nature r├®elle de la strat├®gie

### Description exacte (inf├®r├®e du code)

EDGECORE impl├®mente un **statistical arbitrage par pair trading mean reversion** sur actions US (equities) (IBKR, USD pairs). Le pipeline est :

1. **Screening** : filtrage par corr├®lation ÔëÑ 0.7 sur un univers de 50-100+ tokens
2. **Test de coint├®gration** : Engle-Granger (ADF sur r├®sidus OLS) avec correction de Bonferroni
3. **Mod├®lisation du spread** : OLS lin├®aire `y = ╬▒ + ╬▓┬Àx + ╬Á`
4. **Signal** : Z-score adaptatif sur spread rolling, seuils dynamiques [1.0, 3.5]
5. **Entr├®e** : |Z| > seuil adaptatif (base ~2.0, ajust├® par r├®gime et half-life)
6. **Sortie** : |Z| < seuil de sortie (~0.5 ajust├®) ou trailing stop (widening > 1¤â)
7. **Garde-fous** : concentration limits (30%/symbole), r├®gime detector, hedge ratio tracker

### Hypoth├¿se ├®conomique sous-jacente

La relation de coint├®gration entre actions US refl├¿te une co-d├®pendance structurelle (m├¬me secteur, m├¬me narrative, exposition march├® commune) qui cr├®e un spread stationnaire exploitable par mean reversion.

### Type r├®el

**Pseudo-arbitrage statistique.** Ce n'est PAS un arbitrage au sens strict (pas de garantie de convergence). C'est un pari directionnel sur la stationnarit├® future d'un spread estim├® sur donn├®es historiques. La distinction est critique pour le sizing et le risk management.

### Coh├®rence globale

La coh├®rence architecturale est **correcte** : le pipeline suit la logique classique Engle-Granger ÔåÆ spread ÔåÆ z-score ÔåÆ signal. Les ajouts (adaptive thresholds, regime detector, trailing stops, concentration limits, hedge ratio tracking) montrent une maturit├® progressive. Cependant, plusieurs ├®l├®ments fondamentaux fragilisent l'ensemble (cf. sections suivantes).

---

## 2. Validit├® statistique

### Impl├®mentation du test Engle-Granger

| Aspect | Constat | Verdict |
|--------|---------|---------|
| **M├®thode** | OLS deux ├®tapes + ADF sur r├®sidus | Ô£à Standard |
| **Normalisation** | Donn├®es normalis├®es avant OLS `(x - ╬╝) / ¤â` | Ô£à Bonne pratique |
| **Robustesse num├®rique** | V├®rification condition number > 1e10, NaN, Inf | Ô£à Solide |
| **P-value** | ADF p-value via `statsmodels.adfuller` | Ô£à Standard |
| **Correction multiple** | Bonferroni `╬▒_corrected = 0.05 / n_pairs` | Ô£à Impl├®ment├® |

### P-value utilis├®e

- Seuil nominal : `0.05`
- Avec Bonferroni (45 symboles ÔåÆ 990 paires) : `╬▒ Ôëê 0.00005`
- Avec Bonferroni prod (100+ symboles ÔåÆ 4950+ paires) : `╬▒ Ôëê 0.00001`

­ƒƒí **Alerte : Bonferroni est tr├¿s conservateur.** Il r├®duit drastiquement les faux positifs mais aussi les vrais positifs. Avec 100+ symboles, seules les paires avec p < 1e-5 survivent. Ceci limite s├®v├¿rement l'univers tradable et peut forcer le syst├¿me vers le fallback synth├®tique (cf. section 5).

### ­ƒö┤ CRITIQUE : Coint├®gration Cython bypass Bonferroni

Le fichier `models/cointegration.py` lignes 201-250 r├®v├¿le un **probl├¿me grave** :

```python
# engle_granger_test_cpp_optimized
result_dict['is_cointegrated'] = adf_result[1] < 0.05  # ÔåÉ HARDCOD├ë ├á 0.05
```

La version Cython optimis├®e **ignore la correction Bonferroni** et utilise un seuil brut de 0.05. Le `BacktestRunner._find_cointegrated_pairs_in_data()` appelle `engle_granger_test_cpp_optimized` (sans `num_symbols`, sans `apply_bonferroni`), contournant toute la correction multiple.

**Impact :** Le backtest accepte des faux positifs que la strat├®gie live (via `pair_trading.py` qui passe `apply_bonferroni=True`) rejetterait. Le backtest est donc **plus optimiste que la r├®alit├®**.

### Fen├¬tres roulantes ou statiques

- **Statique** pour la d├®couverte de paires : fen├¬tre fixe de `lookback_window = 252` jours
- **Pas de rolling cointegration test** : la coint├®gration est test├®e UNE FOIS au d├®but, pas r├®├®valu├®e continuellement
- Le `ModelRetrainingManager` schedule un re-test toutes les 14 jours, mais cette logique n'est **pas int├®gr├®e dans le backtest** (seulement dans `generate_signals`)

­ƒƒá **Risque : la coint├®gration est ├®valu├®e une fois et consid├®r├®e valide pour toute la p├®riode de trading.** En equity, les relations se d├®gradent en jours, pas en mois.

### Robustesse de la coint├®gration dans le temps

- Le `HedgeRatioTracker` d├®tecte les d├®rives ╬▓ > 10% et deprecate les paires
- Le `OutOfSampleValidator` exige la persistance en OOS
- **Mais** : ces composants existent dans `generate_signals()` (live) et sont **absents du backtest runner**

­ƒö┤ **Le backtest ne simule pas le cycle de vie r├®el de la strat├®gie** (red├®couverte, re-validation, d├®pr├®ciation).

### Stabilit├® du hedge ratio

- Re-estimation mensuelle (30 jours)
- Drift tolerance : 10%
- Auto-d├®pr├®ciation au-del├á

­ƒƒí **30 jours est trop lent pour la equity.** Un hedge ratio peut d├®river de 20%+ en une semaine pendant un ├®v├®nement de march├® (delisting, hack, r├®gulation).

### Risque de r├®gime shift

- Le `RegimeDetector` classifie LOW/NORMAL/HIGH via percentiles de volatilit├® rolling
- Ajustement des seuils d'entr├®e et du position sizing par r├®gime
- `min_regime_duration = 3` bars avant transition

­ƒƒí **Le d├®tecteur par percentiles est r├®actif, pas pr├®dictif.** Il ne d├®tecte le changement de r├®gime qu'APR├êS qu'il s'est produit. Pas de mod├¿le Markov-switching r├®el malgr├® le commentaire dans le code.

### Absences critiques identifi├®es

- ­ƒö┤ Pas de test de Johansen (seul Engle-Granger 2-step) ÔåÆ non-d├®tection de relations multivari├®es
- ­ƒö┤ Pas de rolling cointegration dans le backtest
- ­ƒƒá Pas de test de racine unitaire sur les s├®ries individuelles avant coint├®gration (les s├®ries doivent ├¬tre I(1))
- ­ƒƒá Pas de test KPSS compl├®mentaire ├á l'ADF (probl├¿me de puissance de l'ADF)
- ­ƒƒá Pas de correction de Newey-West sur les erreurs standards de l'OLS
=======
# AUDIT STRATÉGIQUE — EDGECORE V2

**Date :** 12 février 2026  
**Auditeur :** Senior Quant Researcher & Risk Architect  
**Périmètre :** Stratégie Statistical Arbitrage (Pair Trading Mean Reversion) — code réel uniquement  
**Verdict anticipé :** 🟠 Stratégie structurellement fragile — exploitable sous conditions strictes

---

## 1. Nature réelle de la stratégie

### Description exacte (inférée du code)

EDGECORE implémente un **statistical arbitrage par pair trading mean reversion** sur actions US (equities) (IBKR, USD pairs). Le pipeline est :

1. **Screening** : filtrage par corrélation ≥ 0.7 sur un univers de 50-100+ tokens
2. **Test de cointégration** : Engle-Granger (ADF sur résidus OLS) avec correction de Bonferroni
3. **Modélisation du spread** : OLS linéaire `y = α + β·x + ε`
4. **Signal** : Z-score adaptatif sur spread rolling, seuils dynamiques [1.0, 3.5]
5. **Entrée** : |Z| > seuil adaptatif (base ~2.0, ajusté par régime et half-life)
6. **Sortie** : |Z| < seuil de sortie (~0.5 ajusté) ou trailing stop (widening > 1σ)
7. **Garde-fous** : concentration limits (30%/symbole), régime detector, hedge ratio tracker

### Hypothèse économique sous-jacente

La relation de cointégration entre actions US reflète une co-dépendance structurelle (même secteur, même narrative, exposition marché commune) qui crée un spread stationnaire exploitable par mean reversion.

### Type réel

**Pseudo-arbitrage statistique.** Ce n'est PAS un arbitrage au sens strict (pas de garantie de convergence). C'est un pari directionnel sur la stationnarité future d'un spread estimé sur données historiques. La distinction est critique pour le sizing et le risk management.

### Cohérence globale

La cohérence architecturale est **correcte** : le pipeline suit la logique classique Engle-Granger → spread → z-score → signal. Les ajouts (adaptive thresholds, regime detector, trailing stops, concentration limits, hedge ratio tracking) montrent une maturité progressive. Cependant, plusieurs éléments fondamentaux fragilisent l'ensemble (cf. sections suivantes).

---

## 2. Validité statistique

### Implémentation du test Engle-Granger

| Aspect | Constat | Verdict |
|--------|---------|---------|
| **Méthode** | OLS deux étapes + ADF sur résidus | ✅ Standard |
| **Normalisation** | Données normalisées avant OLS `(x - μ) / σ` | ✅ Bonne pratique |
| **Robustesse numérique** | Vérification condition number > 1e10, NaN, Inf | ✅ Solide |
| **P-value** | ADF p-value via `statsmodels.adfuller` | ✅ Standard |
| **Correction multiple** | Bonferroni `α_corrected = 0.05 / n_pairs` | ✅ Implémenté |

### P-value utilisée

- Seuil nominal : `0.05`
- Avec Bonferroni (45 symboles → 990 paires) : `α ≈ 0.00005`
- Avec Bonferroni prod (100+ symboles → 4950+ paires) : `α ≈ 0.00001`

🟡 **Alerte : Bonferroni est très conservateur.** Il réduit drastiquement les faux positifs mais aussi les vrais positifs. Avec 100+ symboles, seules les paires avec p < 1e-5 survivent. Ceci limite sévèrement l'univers tradable et peut forcer le système vers le fallback synthétique (cf. section 5).

### 🔴 CRITIQUE : Cointégration Cython bypass Bonferroni

Le fichier `models/cointegration.py` lignes 201-250 révèle un **problème grave** :

```python
# engle_granger_test_cpp_optimized
result_dict['is_cointegrated'] = adf_result[1] < 0.05  # ← HARDCODÉ à 0.05
```

La version Cython optimisée **ignore la correction Bonferroni** et utilise un seuil brut de 0.05. Le `BacktestRunner._find_cointegrated_pairs_in_data()` appelle `engle_granger_test_cpp_optimized` (sans `num_symbols`, sans `apply_bonferroni`), contournant toute la correction multiple.

**Impact :** Le backtest accepte des faux positifs que la stratégie live (via `pair_trading.py` qui passe `apply_bonferroni=True`) rejetterait. Le backtest est donc **plus optimiste que la réalité**.

### Fenêtres roulantes ou statiques

- **Statique** pour la découverte de paires : fenêtre fixe de `lookback_window = 252` jours
- **Pas de rolling cointegration test** : la cointégration est testée UNE FOIS au début, pas réévaluée continuellement
- Le `ModelRetrainingManager` schedule un re-test toutes les 14 jours, mais cette logique n'est **pas intégrée dans le backtest** (seulement dans `generate_signals`)

🟠 **Risque : la cointégration est évaluée une fois et considérée valide pour toute la période de trading.** En equity, les relations se dégradent en jours, pas en mois.

### Robustesse de la cointégration dans le temps

- Le `HedgeRatioTracker` détecte les dérives β > 10% et deprecate les paires
- Le `OutOfSampleValidator` exige la persistance en OOS
- **Mais** : ces composants existent dans `generate_signals()` (live) et sont **absents du backtest runner**

🔴 **Le backtest ne simule pas le cycle de vie réel de la stratégie** (redécouverte, re-validation, dépréciation).

### Stabilité du hedge ratio

- Re-estimation mensuelle (30 jours)
- Drift tolerance : 10%
- Auto-dépréciation au-delà

🟡 **30 jours est trop lent pour la equity.** Un hedge ratio peut dériver de 20%+ en une semaine pendant un événement de marché (delisting, hack, régulation).

### Risque de régime shift

- Le `RegimeDetector` classifie LOW/NORMAL/HIGH via percentiles de volatilité rolling
- Ajustement des seuils d'entrée et du position sizing par régime
- `min_regime_duration = 3` bars avant transition

🟡 **Le détecteur par percentiles est réactif, pas prédictif.** Il ne détecte le changement de régime qu'APRÈS qu'il s'est produit. Pas de modèle Markov-switching réel malgré le commentaire dans le code.

### Absences critiques identifiées

- 🔴 Pas de test de Johansen (seul Engle-Granger 2-step) → non-détection de relations multivariées
- 🔴 Pas de rolling cointegration dans le backtest
- 🟠 Pas de test de racine unitaire sur les séries individuelles avant cointégration (les séries doivent être I(1))
- 🟠 Pas de test KPSS complémentaire à l'ADF (problème de puissance de l'ADF)
- 🟠 Pas de correction de Newey-West sur les erreurs standards de l'OLS
>>>>>>> origin/main

---

## 3. Construction du spread

<<<<<<< HEAD
### M├®thode de calcul
=======
### Méthode de calcul
>>>>>>> origin/main

```python
spread = y - (intercept + beta * x)
```

<<<<<<< HEAD
OLS standard avec intercept. Le ╬▓ est estim├® sur l'ensemble de la fen├¬tre `lookback_window`.

### Normalisation

- Les donn├®es sont normalis├®es `(x-╬╝)/¤â` DANS le test de coint├®gration
- **Mais** le SpreadModel utilise les prix BRUTS pour calculer le spread
- Le Z-score normalise ensuite via rolling mean/std

­ƒƒí **Incoh├®rence** entre la normalisation du test (normalis├®) et la construction du spread (prix bruts). Le ╬▓ estim├® sur donn├®es normalis├®es Ôëá ╬▓ sur donn├®es brutes. Cependant, le SpreadModel re-estime son propre ╬▓ sur donn├®es brutes, donc l'impact est limit├® aux cas limites.

### Stationnarit├® v├®rifi├®e ou suppos├®e ?

- **V├®rifi├®e** au moment de la d├®couverte via ADF sur r├®sidus
- **Suppos├®e stationnaire ensuite** jusqu'├á re-test (14-30 jours)
- Pas de monitoring continu de la stationnarit├® du spread en cours de trade

­ƒƒá **On trade un spread non-v├®rifi├® pendant potentiellement 30 jours.** Un spread qui perd sa stationnarit├® ne mean-revert plus ÔÇö les positions deviennent des paris directionnels.

### Robustesse du Z-score

Le Z-score est calcul├® avec une fen├¬tre adaptative bas├®e sur la half-life :

- HL < 30 jours : `lookback = 3 ├ù HL`
- 30 Ôëñ HL Ôëñ 60 : `lookback = HL`
- HL > 60 : `lookback = 60`
- Bornes : `[10, 120]`

Ô£à L'adaptation au half-life est une bonne pratique.

­ƒƒí Le diviseur `rolling_std + 1e-8` emp├¬che la division par z├®ro mais peut produire des Z-scores artificiellement ├®lev├®s quand la variance est quasi-nulle (spread temporairement constant).

### Sensibilit├® aux outliers

- **Aucune gestion des outliers** dans le calcul du spread ou du Z-score
- Le module `preprocessing.py` offre un `remove_outliers()` mais il n'est **jamais appel├®** dans le pipeline de la strat├®gie
- Un flash crash ou un spike de prix produit un Z-score extr├¬me qui d├®clenche imm├®diatement un signal

­ƒƒá **Un spike de prix unique (wick, erreur d'broker) peut ouvrir une position sur un faux signal.**

---

## 4. Logique d'entr├®e / sortie

### Seuils d'entr├®e
=======
OLS standard avec intercept. Le β est estimé sur l'ensemble de la fenêtre `lookback_window`.

### Normalisation

- Les données sont normalisées `(x-μ)/σ` DANS le test de cointégration
- **Mais** le SpreadModel utilise les prix BRUTS pour calculer le spread
- Le Z-score normalise ensuite via rolling mean/std

🟡 **Incohérence** entre la normalisation du test (normalisé) et la construction du spread (prix bruts). Le β estimé sur données normalisées ≠ β sur données brutes. Cependant, le SpreadModel re-estime son propre β sur données brutes, donc l'impact est limité aux cas limites.

### Stationnarité vérifiée ou supposée ?

- **Vérifiée** au moment de la découverte via ADF sur résidus
- **Supposée stationnaire ensuite** jusqu'à re-test (14-30 jours)
- Pas de monitoring continu de la stationnarité du spread en cours de trade

🟠 **On trade un spread non-vérifié pendant potentiellement 30 jours.** Un spread qui perd sa stationnarité ne mean-revert plus — les positions deviennent des paris directionnels.

### Robustesse du Z-score

Le Z-score est calculé avec une fenêtre adaptative basée sur la half-life :

- HL < 30 jours : `lookback = 3 × HL`
- 30 ≤ HL ≤ 60 : `lookback = HL`
- HL > 60 : `lookback = 60`
- Bornes : `[10, 120]`

✅ L'adaptation au half-life est une bonne pratique.

🟡 Le diviseur `rolling_std + 1e-8` empêche la division par zéro mais peut produire des Z-scores artificiellement élevés quand la variance est quasi-nulle (spread temporairement constant).

### Sensibilité aux outliers

- **Aucune gestion des outliers** dans le calcul du spread ou du Z-score
- Le module `preprocessing.py` offre un `remove_outliers()` mais il n'est **jamais appelé** dans le pipeline de la stratégie
- Un flash crash ou un spike de prix produit un Z-score extrême qui déclenche immédiatement un signal

🟠 **Un spike de prix unique (wick, erreur d'broker) peut ouvrir une position sur un faux signal.**

---

## 4. Logique d'entrée / sortie

### Seuils d'entrée
>>>>>>> origin/main

| Config | Dev | Prod |
|--------|-----|------|
| `entry_z_score` | 2.0 | 2.3 |
| Seuil adaptatif | [1.0, 3.5] | [1.0, 3.5] |
| Ajustement vol basse | -0.4 | -0.4 |
| Ajustement vol haute | +0.5 | +0.5 |
| Ajustement HL court | -0.3 | -0.3 |
| Ajustement HL long | +0.3 | +0.3 |

<<<<<<< HEAD
### |Z| > 2 justifi├® ou arbitraire ?

­ƒƒá **Partiellement arbitraire.** Le seuil de base 2.0 est un standard acad├®mique mais n'est justifi├® par aucune optimisation formelle dans le code. Les ajustements adaptatifs (-0.4 ├á +0.5) sont des constantes hardcod├®es sans justification empirique document├®e.

La plage [1.0, 3.5] est raisonnable mais les incr├®ments ┬▒0.3/┬▒0.4/┬▒0.5 semblent choisis manuellement.

### Optimisation implicite ?

­ƒƒá **Oui.** Les seuils adaptatifs et les coefficients de r├®gime (`position_multiplier`, `entry_threshold_multiplier`) sont des param├¿tres qui pourraient ├¬tre le r├®sultat d'un tuning implicite sur donn├®es historiques sans que ce soit document├® comme tel.
=======
### |Z| > 2 justifié ou arbitraire ?

🟠 **Partiellement arbitraire.** Le seuil de base 2.0 est un standard académique mais n'est justifié par aucune optimisation formelle dans le code. Les ajustements adaptatifs (-0.4 à +0.5) sont des constantes hardcodées sans justification empirique documentée.

La plage [1.0, 3.5] est raisonnable mais les incréments ±0.3/±0.4/±0.5 semblent choisis manuellement.

### Optimisation implicite ?

🟠 **Oui.** Les seuils adaptatifs et les coefficients de régime (`position_multiplier`, `entry_threshold_multiplier`) sont des paramètres qui pourraient être le résultat d'un tuning implicite sur données historiques sans que ce soit documenté comme tel.
>>>>>>> origin/main

### Risque de sur-ajustement

Le `MLThresholdOptimizer` (Random Forest, 100 arbres, max_depth=8, 11 features) constitue un risque significatif :

<<<<<<< HEAD
­ƒö┤ **Le ML threshold optimizer n'a aucun test de performance OOS.** Les tests v├®rifient la forme des pr├®dictions, pas leur capacit├® pr├®dictive. Un RF avec 100 arbres et 11 features sur un spread uni-vari├® est un sur-param├®trage ├®vident si le training set est petit (< 1000 samples).

### Gestion des sorties

| M├®canisme | Seuil | Impl├®mentation |
|-----------|-------|----------------|
| Mean reversion | \|Z\| < 0.5 ├ù exit_threshold_multiplier | Ô£à Impl├®ment├® |
| Trailing stop | Widening > 1.0¤â from entry | Ô£à Impl├®ment├® |
| Stop-loss fixe | 5% par d├®faut (RiskEngine) | Ô£à Impl├®ment├® mais ind├®pendant |
| Time stop | **ABSENT** | ­ƒö┤ Aucun |

### ­ƒö┤ Absence de time stop

Aucun m├®canisme ne ferme une position apr├¿s N jours en position. Un trade entr├® ├á Z=2.5 peut rester ouvert ind├®finiment si le spread oscille entre Z=1.0 et Z=2.0 sans jamais atteindre le seuil de sortie ni le trailing stop.

**Impact :** Capital immobilis├®, co├╗t d'opportunit├®, exposition au risque de breakdown cumul├®.

### Risque de drift structurel

Le hedge ratio tracker d├®tecte les drifts ╬▓ > 10% apr├¿s 30 jours. Mais entre deux checks :
- Le spread peut d├®river sans que la position soit ferm├®e
- Le Z-score est calcul├® sur des param├¿tres obsol├¿tes
- La position trade sur un spread non-stationnaire

­ƒƒá La granularit├® de 30 jours est insuffisante pour la equity.
=======
🔴 **Le ML threshold optimizer n'a aucun test de performance OOS.** Les tests vérifient la forme des prédictions, pas leur capacité prédictive. Un RF avec 100 arbres et 11 features sur un spread uni-varié est un sur-paramétrage évident si le training set est petit (< 1000 samples).

### Gestion des sorties

| Mécanisme | Seuil | Implémentation |
|-----------|-------|----------------|
| Mean reversion | \|Z\| < 0.5 × exit_threshold_multiplier | ✅ Implémenté |
| Trailing stop | Widening > 1.0σ from entry | ✅ Implémenté |
| Stop-loss fixe | 5% par défaut (RiskEngine) | ✅ Implémenté mais indépendant |
| Time stop | **ABSENT** | 🔴 Aucun |

### 🔴 Absence de time stop

Aucun mécanisme ne ferme une position après N jours en position. Un trade entré à Z=2.5 peut rester ouvert indéfiniment si le spread oscille entre Z=1.0 et Z=2.0 sans jamais atteindre le seuil de sortie ni le trailing stop.

**Impact :** Capital immobilisé, coût d'opportunité, exposition au risque de breakdown cumulé.

### Risque de drift structurel

Le hedge ratio tracker détecte les drifts β > 10% après 30 jours. Mais entre deux checks :
- Le spread peut dériver sans que la position soit fermée
- Le Z-score est calculé sur des paramètres obsolètes
- La position trade sur un spread non-stationnaire

🟠 La granularité de 30 jours est insuffisante pour la equity.
>>>>>>> origin/main

---

## 5. Backtesting & validation

<<<<<<< HEAD
### ­ƒö┤ CRITIQUE : Le backtest ne refl├¿te PAS la strat├®gie r├®elle

Le `BacktestRunner.run()` et `PairTradingStrategy.generate_signals()` sont **deux impl├®mentations diff├®rentes** :

| Aspect | BacktestRunner.run() | PairTradingStrategy |
|--------|---------------------|---------------------|
| Coint├®gration | `engle_granger_test_cpp_optimized` (pas de Bonferroni) | `engle_granger_test` avec Bonferroni |
| Seuils | Statiques (`config.entry_z_score`) | Adaptatifs (r├®gime + HL) |
| Trailing stops | **Absents** | Ô£à Impl├®ment├® |
| Concentration limits | **Absents** | Ô£à Impl├®ment├® |
| Regime detector | **Absent** | Ô£à Impl├®ment├® |
| Hedge ratio tracking | **Absent** | Ô£à Impl├®ment├® |
| OOS validation | **Absente** | Ô£à Disponible via `validate_pairs_oos()` |
| Re-d├®couverte p├®riodique | **Absente** | Ô£à Via ModelRetrainingManager |
| Position sizing | Fixe (1% par paire) | Ajust├® par r├®gime multiplier |

**Conclusion :** Le backtest simule une version simplifi├®e de la strat├®gie. Les m├®triques de backtest (Sharpe, DD, etc.) ne sont **pas repr├®sentatives** de la performance attendue en live.

### S├®paration in-sample / out-of-sample

- `split_walk_forward()` cr├®e des splits train/test avec `oos_ratio = 0.2`
- L'`OutOfSampleValidator` teste la persistance de coint├®gration en OOS

­ƒƒá **Mais** : dans `WalkForwardBacktester.run_walk_forward()`, le commentaire explicite l'absence de re-training :
=======
### 🔴 CRITIQUE : Le backtest ne reflète PAS la stratégie réelle

Le `BacktestRunner.run()` et `PairTradingStrategy.generate_signals()` sont **deux implémentations différentes** :

| Aspect | BacktestRunner.run() | PairTradingStrategy |
|--------|---------------------|---------------------|
| Cointégration | `engle_granger_test_cpp_optimized` (pas de Bonferroni) | `engle_granger_test` avec Bonferroni |
| Seuils | Statiques (`config.entry_z_score`) | Adaptatifs (régime + HL) |
| Trailing stops | **Absents** | ✅ Implémenté |
| Concentration limits | **Absents** | ✅ Implémenté |
| Regime detector | **Absent** | ✅ Implémenté |
| Hedge ratio tracking | **Absent** | ✅ Implémenté |
| OOS validation | **Absente** | ✅ Disponible via `validate_pairs_oos()` |
| Re-découverte périodique | **Absente** | ✅ Via ModelRetrainingManager |
| Position sizing | Fixe (1% par paire) | Ajusté par régime multiplier |

**Conclusion :** Le backtest simule une version simplifiée de la stratégie. Les métriques de backtest (Sharpe, DD, etc.) ne sont **pas représentatives** de la performance attendue en live.

### Séparation in-sample / out-of-sample

- `split_walk_forward()` crée des splits train/test avec `oos_ratio = 0.2`
- L'`OutOfSampleValidator` teste la persistance de cointégration en OOS

🟠 **Mais** : dans `WalkForwardBacktester.run_walk_forward()`, le commentaire explicite l'absence de re-training :
>>>>>>> origin/main

```python
# For now, we run backtest on test data directly
# In production, you'd retrain the strategy on train_df
```

<<<<<<< HEAD
Le walk-forward **ne retraine pas le mod├¿le** entre les p├®riodes. Il ex├®cute le m├¬me backtest avec les m├¬mes param├¿tres sur des fen├¬tres diff├®rentes. Ce n'est PAS un walk-forward valide.

### ­ƒö┤ Walk-forward : impl├®mentation invalide

L'impl├®mentation actuelle :
1. Cr├®e des splits temporels Ô£à
2. Ex├®cute `BacktestRunner.run()` sur chaque split OOS
3. **Mais `run()` recharge les donn├®es et re-d├®couvre les paires ├á chaque fois** via `_find_cointegrated_pairs_in_data()`
4. La d├®couverte utilise TOUTES les donn├®es charg├®es (pas seulement le training set)
5. R├®sultat : **look-ahead bias** potentiel

Le `run()` filtre par dates mais charge avec `limit=3000` et n'isole pas strictement la fen├¬tre de training.

### Data leakage possible ?

­ƒö┤ **Oui, par construction.** Le `BacktestRunner.run()` appel├® par le walk-forward ne re├ºoit que les dates de test, mais la logique interne :
- Charge les donn├®es depuis l'broker avec un buffer de 60 jours avant le start
- Calcule la coint├®gration sur TOUTES les donn├®es charg├®es (pas seulement le training window)
- Le Z-score rolling utilise une fen├¬tre qui peut inclure des donn├®es hors de la p├®riode assign├®e

### Survivorship bias

­ƒƒá L'univers de trading (`dev.yaml`) inclut `FTT/USD` (token de FTX, effondr├® en novembre 2022) et `LUNC/USD` (ex-LUNA, effondr├® en mai 2022). Si le backtest d├®marre apr├¿s ces effondrements, le survivorship bias est invers├® (on inclut des tokens morts). Si avant, le syst├¿me les tradera et subira les crashes.

Aucun filtre de delisting ou de liquidit├® minimum dynamique n'est impl├®ment├®.

### Look-ahead bias

­ƒƒá Le `SpreadModel` est estim├® sur l'ensemble des donn├®es historiques disponibles puis appliqu├® bar-par-bar dans le backtest. Le ╬▓ OLS est calcul├® UNE FOIS au d├®but puis utilis├® pour tous les jours suivants. C'est un look-ahead partiel car le ╬▓ "conna├«t" l'avenir.

Le backtest re-cr├®e un `SpreadModel` ├á chaque `date_idx` avec `hist_prices = prices_df.iloc[:date_idx+1]`, ce qui est correct pour le ╬▓. Cependant, la liste des paires coint├®gr├®es est d├®couverte UNE FOIS au d├®but sur TOUTES les donn├®es.

­ƒö┤ **Look-ahead bias confirm├® sur la s├®lection des paires** : les paires sont s├®lectionn├®es en utilisant des donn├®es futures.

### Slippage et frais r├®alistes ?
=======
Le walk-forward **ne retraine pas le modèle** entre les périodes. Il exécute le même backtest avec les mêmes paramètres sur des fenêtres différentes. Ce n'est PAS un walk-forward valide.

### 🔴 Walk-forward : implémentation invalide

L'implémentation actuelle :
1. Crée des splits temporels ✅
2. Exécute `BacktestRunner.run()` sur chaque split OOS
3. **Mais `run()` recharge les données et re-découvre les paires à chaque fois** via `_find_cointegrated_pairs_in_data()`
4. La découverte utilise TOUTES les données chargées (pas seulement le training set)
5. Résultat : **look-ahead bias** potentiel

Le `run()` filtre par dates mais charge avec `limit=3000` et n'isole pas strictement la fenêtre de training.

### Data leakage possible ?

🔴 **Oui, par construction.** Le `BacktestRunner.run()` appelé par le walk-forward ne reçoit que les dates de test, mais la logique interne :
- Charge les données depuis l'broker avec un buffer de 60 jours avant le start
- Calcule la cointégration sur TOUTES les données chargées (pas seulement le training window)
- Le Z-score rolling utilise une fenêtre qui peut inclure des données hors de la période assignée

### Survivorship bias

🟠 L'univers de trading (`dev.yaml`) inclut `FTT/USD` (token de FTX, effondré en novembre 2022) et `LUNC/USD` (ex-LUNA, effondré en mai 2022). Si le backtest démarre après ces effondrements, le survivorship bias est inversé (on inclut des tokens morts). Si avant, le système les tradera et subira les crashes.

Aucun filtre de delisting ou de liquidité minimum dynamique n'est implémenté.

### Look-ahead bias

🟠 Le `SpreadModel` est estimé sur l'ensemble des données historiques disponibles puis appliqué bar-par-bar dans le backtest. Le β OLS est calculé UNE FOIS au début puis utilisé pour tous les jours suivants. C'est un look-ahead partiel car le β "connaît" l'avenir.

Le backtest re-crée un `SpreadModel` à chaque `date_idx` avec `hist_prices = prices_df.iloc[:date_idx+1]`, ce qui est correct pour le β. Cependant, la liste des paires cointégrées est découverte UNE FOIS au début sur TOUTES les données.

🔴 **Look-ahead bias confirmé sur la sélection des paires** : les paires sont sélectionnées en utilisant des données futures.

### Slippage et frais réalistes ?
>>>>>>> origin/main

```python
COMMISSION_BPS = 10   # 0.10% par side
SLIPPAGE_BPS = 5      # 0.05% par side
TOTAL_COST_FACTOR = 0.0015  # 15 bps per side, 30 bps round-trip
```

<<<<<<< HEAD
­ƒƒí **R├®aliste pour IBKR spot** (maker 0.10%, taker 0.10% sans GOOGL). Cependant :
- **Slippage de 5 bps est optimiste** pour les mid/small cap equity. MANA, GALA, SAND ont des orderbooks thin qui peuvent causer 20-50 bps de slippage
- Le slippage est fixe et ne d├®pend pas de la taille de l'ordre ni de la liquidit├®
- **Aucun funding rate** pour les positions longues dur├®e (si futures)
- **Aucun borrowing cost** pour le short leg

### Robustesse des m├®triques

Le Sharpe est calcul├® correctement : `(mean / std) ├ù ÔêÜ252`. Le max drawdown est correct. Le profit factor est standard.

­ƒƒí Le Sharpe est annualis├® avec ÔêÜ252 (trading days), mais la equity trade 365 jours. Si les donn├®es sont journali├¿res 365j, l'annualisation devrait utiliser ÔêÜ365.

---

## 6. Robustesse en environnement r├®el

### Sensibilit├® aux gaps

- La equity trade market hours, donc pas de gaps overnight classiques
- **Mais** : gaps de maintenance broker, flash crashes, circuit breakers IBKR
- Aucune gestion des gaps dans le code (pas de check de continuit├® temporelle dans le signal generator)

­ƒƒí Impact mod├®r├® car market hours, mais les ├®v├®nements extr├¬mes ne sont pas g├®r├®s.

### Sensibilit├® ├á la liquidit├®

­ƒö┤ **Critique.** L'univers inclut des tokens avec des liquidit├®s tr├¿s variables :
- AAPL : depth > $10M ÔåÆ OK
- GALA/USD, SAND/USD : depth ~$100K-$500K
- POPCAT/USD, MOG/USD (prod) : depth potentiellement < $50K

Le position sizing ne prend PAS en compte la liquidit├®. Un trade de $1000 sur POPCAT peut repr├®senter 2%+ du carnet d'ordres.

### Impact du slippage

Avec 30 bps round-trip et un Sharpe typique de pair trading equity (~0.5-1.5), le breakeven exige un rendement annualis├® de ~5-10% juste pour couvrir les co├╗ts. Si le nombre de trades est ├®lev├® (high turnover), les frais ├®rodent rapidement l'alpha.
=======
🟡 **Réaliste pour IBKR spot** (maker 0.10%, taker 0.10% sans GOOGL). Cependant :
- **Slippage de 5 bps est optimiste** pour les mid/small cap equity. MANA, GALA, SAND ont des orderbooks thin qui peuvent causer 20-50 bps de slippage
- Le slippage est fixe et ne dépend pas de la taille de l'ordre ni de la liquidité
- **Aucun funding rate** pour les positions longues durée (si futures)
- **Aucun borrowing cost** pour le short leg

### Robustesse des métriques

Le Sharpe est calculé correctement : `(mean / std) × √252`. Le max drawdown est correct. Le profit factor est standard.

🟡 Le Sharpe est annualisé avec √252 (trading days), mais la equity trade 365 jours. Si les données sont journalières 365j, l'annualisation devrait utiliser √365.

---

## 6. Robustesse en environnement réel

### Sensibilité aux gaps

- La equity trade market hours, donc pas de gaps overnight classiques
- **Mais** : gaps de maintenance broker, flash crashes, circuit breakers IBKR
- Aucune gestion des gaps dans le code (pas de check de continuité temporelle dans le signal generator)

🟡 Impact modéré car market hours, mais les événements extrêmes ne sont pas gérés.

### Sensibilité à la liquidité

🔴 **Critique.** L'univers inclut des tokens avec des liquidités très variables :
- AAPL : depth > $10M → OK
- GALA/USD, SAND/USD : depth ~$100K-$500K
- POPCAT/USD, MOG/USD (prod) : depth potentiellement < $50K

Le position sizing ne prend PAS en compte la liquidité. Un trade de $1000 sur POPCAT peut représenter 2%+ du carnet d'ordres.

### Impact du slippage

Avec 30 bps round-trip et un Sharpe typique de pair trading equity (~0.5-1.5), le breakeven exige un rendement annualisé de ~5-10% juste pour couvrir les coûts. Si le nombre de trades est élevé (high turnover), les frais érodent rapidement l'alpha.
>>>>>>> origin/main

### Impact des frais IBKR

| Tier | Maker | Taker |
|------|-------|-------|
| Standard | 0.10% | 0.10% |
| VIP 1 ($1M/30d) | 0.09% | 0.10% |

<<<<<<< HEAD
Avec 2 legs par trade (long + short) ├ù 2 (entr├®e + sortie) = 4 transactions ├ù 0.10% = **40 bps minimum par round-trip complet** (sans GOOGL discount). Le backtest utilise 30 bps ÔåÆ **sous-estimation de 10 bps.**

­ƒƒá Sous-estimation syst├®matique des co├╗ts dans le backtest.

### Risque de breakdown de corr├®lation

Le equity est sujet ├á des d├®corr├®lations brutales :
- ├ëv├®nements idiosyncratiques (hack, r├®gulation sp├®cifique)
- Rotation sectorielle rapide (DeFi ÔåÆ Meme ÔåÆ AI ÔåÆ RWA)
- Delisting/listing events

Le `RegimeDetector` d├®tecte la volatilit├® mais pas la d├®corr├®lation directe.

­ƒƒá Pas de monitoring de corr├®lation rolling entre les legs de chaque paire.

### Sc├®narios critiques

| Sc├®nario | Impact estim├® | Mitigation dans le code |
|----------|--------------|------------------------|
| **Crash march├® (-30% en 24h)** | Les deux legs chutent ensemble mais le spread peut exploser si ╬▓ change | Trailing stop (1¤â) + position size r├®gime | 
| **Volatilit├® extr├¬me (VIX equity)** | Z-scores erratiques, faux signaux multiples | R├®gime HIGH ÔåÆ seuils plus hauts + sizing r├®duit |
| **D├®corr├®lation brutale** | Spread non-stationnaire, positions perdantes | Hedge ratio drift detection (30j delay!) |
| **Flash crash single asset** | Position sur le leg affect├®, stop 5% | Stop loss percentage |
| **broker outage** | Trades non ex├®cutables | max_retries=3, timeout=30s |

­ƒƒá **Les mitigations existent mais sont trop lentes** (30 jours pour la d├®tection de drift, 3 bars minimum pour le changement de r├®gime). En equity, les r├®gimes changent en heures, pas en jours.
=======
Avec 2 legs par trade (long + short) × 2 (entrée + sortie) = 4 transactions × 0.10% = **40 bps minimum par round-trip complet** (sans GOOGL discount). Le backtest utilise 30 bps → **sous-estimation de 10 bps.**

🟠 Sous-estimation systématique des coûts dans le backtest.

### Risque de breakdown de corrélation

Le equity est sujet à des décorrélations brutales :
- Événements idiosyncratiques (hack, régulation spécifique)
- Rotation sectorielle rapide (DeFi → Meme → AI → RWA)
- Delisting/listing events

Le `RegimeDetector` détecte la volatilité mais pas la décorrélation directe.

🟠 Pas de monitoring de corrélation rolling entre les legs de chaque paire.

### Scénarios critiques

| Scénario | Impact estimé | Mitigation dans le code |
|----------|--------------|------------------------|
| **Crash marché (-30% en 24h)** | Les deux legs chutent ensemble mais le spread peut exploser si β change | Trailing stop (1σ) + position size régime | 
| **Volatilité extrême (VIX equity)** | Z-scores erratiques, faux signaux multiples | Régime HIGH → seuils plus hauts + sizing réduit |
| **Décorrélation brutale** | Spread non-stationnaire, positions perdantes | Hedge ratio drift detection (30j delay!) |
| **Flash crash single asset** | Position sur le leg affecté, stop 5% | Stop loss percentage |
| **broker outage** | Trades non exécutables | max_retries=3, timeout=30s |

🟠 **Les mitigations existent mais sont trop lentes** (30 jours pour la détection de drift, 3 bars minimum pour le changement de régime). En equity, les régimes changent en heures, pas en jours.
>>>>>>> origin/main

---

## 7. Interaction avec le Risk Engine

<<<<<<< HEAD
### La strat├®gie d├®pend-elle trop du risk engine ?
=======
### La stratégie dépend-elle trop du risk engine ?
>>>>>>> origin/main

**Oui, structurellement.**

Le `RiskEngine` fournit :
- Limite de positions concurrentes (max 10)
- Stop-loss par position (5%)
<<<<<<< HEAD
- Kill-switch de perte journali├¿re (2%)
- Limite de pertes cons├®cutives (3)
- Limite de levier (3├ù)
- Trailing stops via le manager d├®di├®

­ƒö┤ **Sans le risk engine, la strat├®gie n'a aucun m├®canisme de sortie forc├®e.** Les seules sorties strat├®giques sont :
- Mean reversion ├á Z Ôëê 0 (qui peut ne jamais arriver)
- Trailing stop widening > 1¤â (qui peut ne pas se d├®clencher si le spread d├®rive lentement)
=======
- Kill-switch de perte journalière (2%)
- Limite de pertes consécutives (3)
- Limite de levier (3×)
- Trailing stops via le manager dédié

🔴 **Sans le risk engine, la stratégie n'a aucun mécanisme de sortie forcée.** Les seules sorties stratégiques sont :
- Mean reversion à Z ≈ 0 (qui peut ne jamais arriver)
- Trailing stop widening > 1σ (qui peut ne pas se déclencher si le spread dérive lentement)
>>>>>>> origin/main

### Le risk engine compense-t-il une faiblesse structurelle ?

**Oui.**

- Le stop-loss de 5% compense l'absence de time stop
<<<<<<< HEAD
- Le kill-switch journalier de 2% compense l'absence de limite de drawdown intra-strat├®gie
- La limite de positions concurrentes compense l'absence de corr├®lation-check entre les paires

­ƒƒá Le risk engine est un filet de s├®curit├®, pas une optimisation. La strat├®gie devrait int├®grer ses propres m├®canismes de contr├┤le.

### La strat├®gie reste-t-elle viable sans protection externe ?

**Non.** Sans le risk engine :
- Positions potentiellement illimit├®es (pas de max positions dans la strat├®gie elle-m├¬me)
- Pas de stop sur perte absolue
- Accumulation de pertes possible sur des spreads divergents
- Perte maximale th├®orique : 100% du capital allou├®

---

## 8. Scalabilit├® strat├®gique

### Multi-paires

Ô£à L'architecture supporte nativement le multi-paires :
- Screening exhaustif de toutes les combinaisons
- Parall├®lisation via multiprocessing
- Configuration de 50+ (dev) ├á 100+ (prod) symboles

### Risque de corr├®lation crois├®e entre spreads

­ƒö┤ **Non g├®r├®.** Si on trade AAPL/MSFT, AAPL/JPM et MSFT/JPM simultan├®ment :
- Les 3 spreads sont corr├®l├®s (AAPL est dans 2/3 des paires)
- Un mouvement AAPL affecte les 3 positions dans la m├¬me direction
- La diversification apparente est illusoire

Le `ConcentrationLimitManager` limite l'exposition par symbole (30%) mais ne mesure PAS la corr├®lation entre spreads.

­ƒö┤ **Absence critique de matrice de corr├®lation des spreads** pour un portfolio de paires.

### Effet de crowding

­ƒƒí Le pair trading equity est une strat├®gie connue. Avec la m├¬me logique (EG + Z-score + m├¬me univers IBKR), de nombreux quants convergent vers les m├¬mes paires. Ceci :
- R├®duit les inefficiencies exploitables
- Acc├®l├¿re la convergence (r├®duit le profit potentiel)
- Cr├®e du crowding sur les sorties en cas de stress

---

## 9. Failles critiques identifi├®es

### ­ƒö┤ Critiques (strat├®gie invalide / illusion statistique / danger capital)

1. **­ƒö┤ C-01 : Divergence backtest/live** ÔÇö Le backtest et la strat├®gie live sont deux impl├®mentations diff├®rentes (Bonferroni, seuils adaptatifs, trailing stops, r├®gime detection absents du backtest). Les m├®triques de backtest sont **non-repr├®sentatives** de la performance live.

2. **­ƒö┤ C-02 : Look-ahead bias sur la s├®lection des paires** ÔÇö Dans `BacktestRunner.run()`, les paires coint├®gr├®es sont s├®lectionn├®es sur l'int├®gralit├® des donn├®es puis trad├®es bar-par-bar. Le backtest "conna├«t" quelles paires seront coint├®gr├®es ├á l'avance.

3. **­ƒö┤ C-03 : Walk-forward invalide** ÔÇö Le walk-forward ne retraine pas le mod├¿le, ne re-d├®couvre pas les paires par p├®riode, et r├®utilise le m├¬me `BacktestRunner.run()` avec look-ahead. Ce n'est pas un walk-forward.

4. **­ƒö┤ C-04 : Cython bypass Bonferroni** ÔÇö `engle_granger_test_cpp_optimized` hardcode `p < 0.05` sans correction multiple, utilis├® dans le backtest. Accepte ~100├ù plus de faux positifs que la version live.

5. **­ƒö┤ C-05 : Absence de time stop** ÔÇö Aucun m├®canisme de sortie temporelle. Capital potentiellement bloqu├® ind├®finiment sur des spreads non-convergents.

6. **­ƒö┤ C-06 : Corr├®lation crois├®e des spreads non g├®r├®e** ÔÇö Concentration apparente diversifi├®e mais corr├®lation effective entre les spreads non mesur├®e ni contr├┤l├®e. Risque de perte concurrente sur tous les trades.

### ­ƒƒá Majeurs (fragilit├® importante)

7. **­ƒƒá M-01 : Stationnarit├® suppos├®e entre re-tests (14-30 jours)** ÔÇö Le spread peut perdre sa stationnarit├® entre deux v├®rifications sans que la strat├®gie ne r├®agisse.

8. **­ƒƒá M-02 : Granularit├® de d├®tection insuffisante** ÔÇö Hedge ratio tracker (30j), regime detector (3 bars min) sont trop lents pour le rythme equity.

9. **­ƒƒá M-03 : Frais sous-estim├®s** ÔÇö 30 bps backtest vs 40+ bps r├®alit├® (4 legs ├ù 0.10%). Ni funding rate ni borrowing cost.

10. **­ƒƒá M-04 : Survivorship/selection bias dans l'univers** ÔÇö FTT et LUNC dans l'univers dev, tokens ├á tr├¿s faible liquidit├® en prod (POPCAT, MOG, GOAT).

11. **­ƒƒá M-05 : ML threshold optimizer non valid├® OOS** ÔÇö Random Forest (100 arbres, depth 8) sans cross-validation ni test OOS. Risque d'overfitting majeur.

12. **­ƒƒá M-06 : Fallback synth├®tique dans le backtest** ÔÇö Quand aucune paire n'est trouv├®e, le backtest g├®n├¿re des donn├®es synth├®tiques parfaitement coint├®gr├®es (`Y = 2X + noise`), produisant des m├®triques artificiellement positives.

13. **­ƒƒá M-07 : Pas de test I(1) sur les s├®ries individuelles** ÔÇö Engle-Granger suppose que les s├®ries sont individuellement non-stationnaires (I(1)). Si les s├®ries sont d├®j├á stationnaires (I(0)), le test est invalide. Aucune v├®rification pr├®alable.

14. **­ƒƒá M-08 : Absence de gestion des outliers** ÔÇö Le module `remove_outliers` existe mais n'est jamais int├®gr├® au pipeline de signal. Un flash crash peut d├®clencher des faux signaux.

### ­ƒƒí Mineurs (optimisation ou am├®lioration)

15. **­ƒƒí m-01 : Annualisation ÔêÜ252 vs ÔêÜ365** ÔÇö equity trade 365j/an, l'annualisation du Sharpe devrait utiliser ÔêÜ365 si les barres sont calendaires.

16. **­ƒƒí m-02 : Half-life estimation en double** ÔÇö `SpreadModel` et `SpreadHalfLifeEstimator` utilisent deux estimateurs AR(1) l├®g├¿rement diff├®rents. Redondance et incoh├®rence potentielle.

17. **­ƒƒí m-03 : BAC dupliqu├®** ÔÇö Le fichier `dev.yaml` contient deux fois `BAC`.

18. **­ƒƒí m-04 : Tests trop permissifs** ÔÇö De nombreux tests v├®rifient le type des sorties (`isinstance`, `is not None`) sans v├®rifier la correction des valeurs. Les tests de r├®gime acceptent n'importe quel r├®gime comme "correct".

19. **­ƒƒí m-05 : Cache de 24h pour les paires** ÔÇö En live, le cache de paires expire apr├¿s 24h. Un march├® volatile peut invalider les paires en heures.
=======
- Le kill-switch journalier de 2% compense l'absence de limite de drawdown intra-stratégie
- La limite de positions concurrentes compense l'absence de corrélation-check entre les paires

🟠 Le risk engine est un filet de sécurité, pas une optimisation. La stratégie devrait intégrer ses propres mécanismes de contrôle.

### La stratégie reste-t-elle viable sans protection externe ?

**Non.** Sans le risk engine :
- Positions potentiellement illimitées (pas de max positions dans la stratégie elle-même)
- Pas de stop sur perte absolue
- Accumulation de pertes possible sur des spreads divergents
- Perte maximale théorique : 100% du capital alloué

---

## 8. Scalabilité stratégique

### Multi-paires

✅ L'architecture supporte nativement le multi-paires :
- Screening exhaustif de toutes les combinaisons
- Parallélisation via multiprocessing
- Configuration de 50+ (dev) à 100+ (prod) symboles

### Risque de corrélation croisée entre spreads

🔴 **Non géré.** Si on trade AAPL/MSFT, AAPL/JPM et MSFT/JPM simultanément :
- Les 3 spreads sont corrélés (AAPL est dans 2/3 des paires)
- Un mouvement AAPL affecte les 3 positions dans la même direction
- La diversification apparente est illusoire

Le `ConcentrationLimitManager` limite l'exposition par symbole (30%) mais ne mesure PAS la corrélation entre spreads.

🔴 **Absence critique de matrice de corrélation des spreads** pour un portfolio de paires.

### Effet de crowding

🟡 Le pair trading equity est une stratégie connue. Avec la même logique (EG + Z-score + même univers IBKR), de nombreux quants convergent vers les mêmes paires. Ceci :
- Réduit les inefficiencies exploitables
- Accélère la convergence (réduit le profit potentiel)
- Crée du crowding sur les sorties en cas de stress

---

## 9. Failles critiques identifiées

### 🔴 Critiques (stratégie invalide / illusion statistique / danger capital)

1. **🔴 C-01 : Divergence backtest/live** — Le backtest et la stratégie live sont deux implémentations différentes (Bonferroni, seuils adaptatifs, trailing stops, régime detection absents du backtest). Les métriques de backtest sont **non-représentatives** de la performance live.

2. **🔴 C-02 : Look-ahead bias sur la sélection des paires** — Dans `BacktestRunner.run()`, les paires cointégrées sont sélectionnées sur l'intégralité des données puis tradées bar-par-bar. Le backtest "connaît" quelles paires seront cointégrées à l'avance.

3. **🔴 C-03 : Walk-forward invalide** — Le walk-forward ne retraine pas le modèle, ne re-découvre pas les paires par période, et réutilise le même `BacktestRunner.run()` avec look-ahead. Ce n'est pas un walk-forward.

4. **🔴 C-04 : Cython bypass Bonferroni** — `engle_granger_test_cpp_optimized` hardcode `p < 0.05` sans correction multiple, utilisé dans le backtest. Accepte ~100× plus de faux positifs que la version live.

5. **🔴 C-05 : Absence de time stop** — Aucun mécanisme de sortie temporelle. Capital potentiellement bloqué indéfiniment sur des spreads non-convergents.

6. **🔴 C-06 : Corrélation croisée des spreads non gérée** — Concentration apparente diversifiée mais corrélation effective entre les spreads non mesurée ni contrôlée. Risque de perte concurrente sur tous les trades.

### 🟠 Majeurs (fragilité importante)

7. **🟠 M-01 : Stationnarité supposée entre re-tests (14-30 jours)** — Le spread peut perdre sa stationnarité entre deux vérifications sans que la stratégie ne réagisse.

8. **🟠 M-02 : Granularité de détection insuffisante** — Hedge ratio tracker (30j), regime detector (3 bars min) sont trop lents pour le rythme equity.

9. **🟠 M-03 : Frais sous-estimés** — 30 bps backtest vs 40+ bps réalité (4 legs × 0.10%). Ni funding rate ni borrowing cost.

10. **🟠 M-04 : Survivorship/selection bias dans l'univers** — FTT et LUNC dans l'univers dev, tokens à très faible liquidité en prod (POPCAT, MOG, GOAT).

11. **🟠 M-05 : ML threshold optimizer non validé OOS** — Random Forest (100 arbres, depth 8) sans cross-validation ni test OOS. Risque d'overfitting majeur.

12. **🟠 M-06 : Fallback synthétique dans le backtest** — Quand aucune paire n'est trouvée, le backtest génère des données synthétiques parfaitement cointégrées (`Y = 2X + noise`), produisant des métriques artificiellement positives.

13. **🟠 M-07 : Pas de test I(1) sur les séries individuelles** — Engle-Granger suppose que les séries sont individuellement non-stationnaires (I(1)). Si les séries sont déjà stationnaires (I(0)), le test est invalide. Aucune vérification préalable.

14. **🟠 M-08 : Absence de gestion des outliers** — Le module `remove_outliers` existe mais n'est jamais intégré au pipeline de signal. Un flash crash peut déclencher des faux signaux.

### 🟡 Mineurs (optimisation ou amélioration)

15. **🟡 m-01 : Annualisation √252 vs √365** — equity trade 365j/an, l'annualisation du Sharpe devrait utiliser √365 si les barres sont calendaires.

16. **🟡 m-02 : Half-life estimation en double** — `SpreadModel` et `SpreadHalfLifeEstimator` utilisent deux estimateurs AR(1) légèrement différents. Redondance et incohérence potentielle.

17. **🟡 m-03 : BAC dupliqué** — Le fichier `dev.yaml` contient deux fois `BAC`.

18. **🟡 m-04 : Tests trop permissifs** — De nombreux tests vérifient le type des sorties (`isinstance`, `is not None`) sans vérifier la correction des valeurs. Les tests de régime acceptent n'importe quel régime comme "correct".

19. **🟡 m-05 : Cache de 24h pour les paires** — En live, le cache de paires expire après 24h. Un marché volatile peut invalider les paires en heures.
>>>>>>> origin/main

---

## 10. Recommandations prioritaires

### Top 5 corrections OBLIGATOIRES avant paper trading

| # | Action | Faille | Effort |
|---|--------|--------|--------|
<<<<<<< HEAD
| 1 | **Unifier backtest et strat├®gie live** ÔÇö Le backtest doit utiliser exactement le m├¬me code de signal que la strat├®gie (adaptive thresholds, trailing stops, concentration limits, Bonferroni). Cr├®er un `StrategySimulator` qui wrappe `PairTradingStrategy.generate_signals()`. | C-01 | ├ëlev├® |
| 2 | **Corriger le look-ahead bias** ÔÇö D├®couvrir les paires uniquement sur donn├®es in-sample pour chaque barre/p├®riode. Impl├®menter un walk-forward r├®el avec re-training par p├®riode. | C-02, C-03 | ├ëlev├® |
| 3 | **Fixer la coint├®gration Cython** ÔÇö Passer `num_symbols` et `apply_bonferroni=True` dans `engle_granger_test_cpp_optimized`. Supprimer le hardcode `p < 0.05`. | C-04 | Faible |
| 4 | **Ajouter un time stop** ÔÇö Fermer toute position ouverte > 2├ù half-life jours (ou max 30 jours). | C-05 | Faible |
| 5 | **Impl├®menter une matrice de corr├®lation des spreads** ÔÇö Avant d'ouvrir un nouveau trade, v├®rifier que le spread n'est pas corr├®l├® > 0.6 avec un spread d├®j├á en position. | C-06 | Moyen |

### Am├®liorations moyen terme

| # | Action | Faille |
|---|--------|--------|
| 6 | Ajouter un test ADF/KPSS sur chaque s├®rie avant coint├®gration (v├®rifier I(1)) | M-07 |
| 7 | R├®duire la granularit├® de re-estimation du hedge ratio ├á 7 jours | M-02 |
| 8 | Int├®grer les frais r├®alistes (4 legs ├ù maker/taker + funding rate si futures) | M-03 |
| 9 | Filtrer l'univers par liquidit├® minimum dynamique (volume 24h > $5M) | M-04 |
| 10 | Valider le ML threshold optimizer en OOS avec walk-forward CV ou le d├®sactiver | M-05 |
| 11 | Supprimer ou conditionner le fallback synth├®tique (jamais de m├®triques synth├®tiques pass├®es pour r├®elles) | M-06 |
| 12 | Int├®grer `remove_outliers` dans le pipeline de signal avant le calcul du Z-score | M-08 |
| 13 | Ajouter un monitoring de corr├®lation rolling entre les legs de chaque paire active | M-01 |

### Optimisations avanc├®es

| # | Action |
|---|--------|
| 14 | Impl├®menter Johansen pour la d├®tection multi-vari├®e |
| 15 | Ajouter un mod├¿le de market impact bas├® sur le volume |
| 16 | Impl├®menter un Kalman filter pour le hedge ratio dynamique (remplacer OLS statique) |
| 17 | Ajouter des tests de puissance statistique (power analysis) pour calibrer la taille d'├®chantillon |
=======
| 1 | **Unifier backtest et stratégie live** — Le backtest doit utiliser exactement le même code de signal que la stratégie (adaptive thresholds, trailing stops, concentration limits, Bonferroni). Créer un `StrategySimulator` qui wrappe `PairTradingStrategy.generate_signals()`. | C-01 | Élevé |
| 2 | **Corriger le look-ahead bias** — Découvrir les paires uniquement sur données in-sample pour chaque barre/période. Implémenter un walk-forward réel avec re-training par période. | C-02, C-03 | Élevé |
| 3 | **Fixer la cointégration Cython** — Passer `num_symbols` et `apply_bonferroni=True` dans `engle_granger_test_cpp_optimized`. Supprimer le hardcode `p < 0.05`. | C-04 | Faible |
| 4 | **Ajouter un time stop** — Fermer toute position ouverte > 2× half-life jours (ou max 30 jours). | C-05 | Faible |
| 5 | **Implémenter une matrice de corrélation des spreads** — Avant d'ouvrir un nouveau trade, vérifier que le spread n'est pas corrélé > 0.6 avec un spread déjà en position. | C-06 | Moyen |

### Améliorations moyen terme

| # | Action | Faille |
|---|--------|--------|
| 6 | Ajouter un test ADF/KPSS sur chaque série avant cointégration (vérifier I(1)) | M-07 |
| 7 | Réduire la granularité de re-estimation du hedge ratio à 7 jours | M-02 |
| 8 | Intégrer les frais réalistes (4 legs × maker/taker + funding rate si futures) | M-03 |
| 9 | Filtrer l'univers par liquidité minimum dynamique (volume 24h > $5M) | M-04 |
| 10 | Valider le ML threshold optimizer en OOS avec walk-forward CV ou le désactiver | M-05 |
| 11 | Supprimer ou conditionner le fallback synthétique (jamais de métriques synthétiques passées pour réelles) | M-06 |
| 12 | Intégrer `remove_outliers` dans le pipeline de signal avant le calcul du Z-score | M-08 |
| 13 | Ajouter un monitoring de corrélation rolling entre les legs de chaque paire active | M-01 |

### Optimisations avancées

| # | Action |
|---|--------|
| 14 | Implémenter Johansen pour la détection multi-variée |
| 15 | Ajouter un modèle de market impact basé sur le volume |
| 16 | Implémenter un Kalman filter pour le hedge ratio dynamique (remplacer OLS statique) |
| 17 | Ajouter des tests de puissance statistique (power analysis) pour calibrer la taille d'échantillon |
>>>>>>> origin/main
| 18 | Backtester event-driven avec order book simulation |

---

<<<<<<< HEAD
## 11. Score strat├®gique final

### Qualit├® statistique : 4.5 / 10

| Composante | Score | Justification |
|-----------|-------|---------------|
| Test de coint├®gration | 7/10 | Engle-Granger + Bonferroni correct, mais Cython bypass et pas de KPSS |
| Construction du spread | 6/10 | OLS standard correct, mais pas de Kalman, pas de gestion outliers |
| Z-score | 7/10 | Adaptation HL bien pens├®e, bornes raisonnables |
| Entr├®e/sortie | 4/10 | Seuils semi-arbitraires, pas de time stop, ML non valid├® |
| Backtesting | 2/10 | Look-ahead bias, walk-forward invalide, divergence avec live |
| Validation OOS | 5/10 | Composant pr├®sent mais non int├®gr├® dans le backtest |

**Score global qualit├® statistique : 4.5/10**

### Robustesse r├®elle : 3.5 / 10

| Composante | Score | Justification |
|-----------|-------|---------------|
| R├®sistance aux r├®gimes | 5/10 | D├®tecteur de r├®gime pr├®sent mais r├®actif, pas pr├®dictif |
| Gestion de la liquidit├® | 2/10 | Non prise en compte du tout |
| Co├╗ts r├®alistes | 4/10 | Pr├®sents mais sous-estim├®s |
| Corr├®lation des positions | 1/10 | Non g├®r├®e (critique) |
| D├®pendance au risk engine | 3/10 | Trop d├®pendant, pas de self-contained risk |
| Sc├®narios extr├¬mes | 4/10 | Stops pr├®sents mais trop lents |

**Score global robustesse r├®elle : 3.5/10**

### Probabilit├® de survie 12 mois live
=======
## 11. Score stratégique final

### Qualité statistique : 4.5 / 10

| Composante | Score | Justification |
|-----------|-------|---------------|
| Test de cointégration | 7/10 | Engle-Granger + Bonferroni correct, mais Cython bypass et pas de KPSS |
| Construction du spread | 6/10 | OLS standard correct, mais pas de Kalman, pas de gestion outliers |
| Z-score | 7/10 | Adaptation HL bien pensée, bornes raisonnables |
| Entrée/sortie | 4/10 | Seuils semi-arbitraires, pas de time stop, ML non validé |
| Backtesting | 2/10 | Look-ahead bias, walk-forward invalide, divergence avec live |
| Validation OOS | 5/10 | Composant présent mais non intégré dans le backtest |

**Score global qualité statistique : 4.5/10**

### Robustesse réelle : 3.5 / 10

| Composante | Score | Justification |
|-----------|-------|---------------|
| Résistance aux régimes | 5/10 | Détecteur de régime présent mais réactif, pas prédictif |
| Gestion de la liquidité | 2/10 | Non prise en compte du tout |
| Coûts réalistes | 4/10 | Présents mais sous-estimés |
| Corrélation des positions | 1/10 | Non gérée (critique) |
| Dépendance au risk engine | 3/10 | Trop dépendant, pas de self-contained risk |
| Scénarios extrêmes | 4/10 | Stops présents mais trop lents |

**Score global robustesse réelle : 3.5/10**

### Probabilité de survie 12 mois live
>>>>>>> origin/main

**15-25%**

Justification :
<<<<<<< HEAD
- Les equity pairs perdent leur coint├®gration en moyenne en 2-6 mois
- Les frais sous-estim├®s ├®rodent l'alpha restant
- L'absence de corr├®lation crois├®e expose ├á des drawdowns simultan├®s
- Le regime detector trop lent ne prot├¿ge pas des ├®v├®nements rapides
- La strat├®gie est structurellement d├®pendante du risk engine pour la survie

### Verdict final

> **­ƒæë STRAT├ëGIE FRAGILE**
>
> EDGECORE pr├®sente une **architecture bien con├ºue** avec de nombreux composants pertinents (Bonferroni, adaptive thresholds, regime detector, trailing stops, hedge ratio tracking, OOS validator). L'intention et la direction sont correctes.
>
> Cependant, l'**impl├®mentation souffre de d├®fauts fondamentaux** :
> - Le backtest ne refl├¿te pas la strat├®gie r├®elle (divergence totale)
> - Le walk-forward est invalide (pas de re-training, look-ahead bias)
> - La validation statistique est contourn├®e dans le path du backtest (Cython bypass)
> - L'absence de time stop et de corr├®lation des spreads cr├®e des risques structurels
>
> **En l'├®tat, d├®ployer du capital r├®el serait pr├®matur├® et risqu├®.**
>
> Apr├¿s correction des failles C-01 ├á C-06 (estim├® 2-3 semaines de d├®veloppement), la strat├®gie pourrait ├¬tre ├®valu├®e en paper trading avec un horizon de 3 mois minimum avant toute d├®cision de go-live.
>
> La probabilit├® de survie post-correction passerait ├á **40-55%** ÔÇö un niveau toujours insuffisant pour du capital institutionnel mais acceptable pour une phase d'exploration avec capital risque limit├®.

---

*Audit r├®alis├® sur le code source uniquement. Aucune hypoth├¿se gratuite. Tol├®rance ├á l'illusion statistique : z├®ro.*
=======
- Les equity pairs perdent leur cointégration en moyenne en 2-6 mois
- Les frais sous-estimés érodent l'alpha restant
- L'absence de corrélation croisée expose à des drawdowns simultanés
- Le regime detector trop lent ne protège pas des événements rapides
- La stratégie est structurellement dépendante du risk engine pour la survie

### Verdict final

> **👉 STRATÉGIE FRAGILE**
>
> EDGECORE présente une **architecture bien conçue** avec de nombreux composants pertinents (Bonferroni, adaptive thresholds, regime detector, trailing stops, hedge ratio tracking, OOS validator). L'intention et la direction sont correctes.
>
> Cependant, l'**implémentation souffre de défauts fondamentaux** :
> - Le backtest ne reflète pas la stratégie réelle (divergence totale)
> - Le walk-forward est invalide (pas de re-training, look-ahead bias)
> - La validation statistique est contournée dans le path du backtest (Cython bypass)
> - L'absence de time stop et de corrélation des spreads crée des risques structurels
>
> **En l'état, déployer du capital réel serait prématuré et risqué.**
>
> Après correction des failles C-01 à C-06 (estimé 2-3 semaines de développement), la stratégie pourrait être évaluée en paper trading avec un horizon de 3 mois minimum avant toute décision de go-live.
>
> La probabilité de survie post-correction passerait à **40-55%** — un niveau toujours insuffisant pour du capital institutionnel mais acceptable pour une phase d'exploration avec capital risque limité.

---

*Audit réalisé sur le code source uniquement. Aucune hypothèse gratuite. Tolérance à l'illusion statistique : zéro.*
>>>>>>> origin/main
