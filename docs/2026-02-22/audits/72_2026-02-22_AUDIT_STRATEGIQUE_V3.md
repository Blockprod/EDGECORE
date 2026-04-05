<<<<<<< HEAD
﻿# AUDIT STRAT├ëGIQUE ÔÇö EDGECORE

> **Date :** 22 f├®vrier 2026 | **Base :** code source int├®gral analys├®, z├®ro supposition  
> **P├®rim├¿tre :** strat├®gie, signaux, cointegration, spread, backtest, walk-forward, OOS, risk engine  

---

## 1. Nature r├®elle de la strat├®gie

### Description exacte inf├®r├®e depuis le code

EDGECORE est une strat├®gie de **statistical arbitrage bivariate** bas├®e sur la mean reversion de spreads coint├®gr├®s, op├®rant sur des paires de cryptomonnaies Binance (march├® spot/perpetual).

Pipeline complet :

1. **D├®couverte de paires** ÔÇö Engle-Granger (OLS normalis├® ÔåÆ ADF sur r├®sidus) + confirmation Johansen + consensus Newey-West HAC + filtre corr├®lation ÔëÑ 0.75 + filtre liquidit├® ÔëÑ $5M/24h
2. **Mod├®lisation du spread** ÔÇö OLS brut s├®par├® (`SpreadModel` / `DynamicSpreadModel`) : `spread = y - (╬▒ + ╬▓┬Àx)`
3. **Z-score adaptatif** ÔÇö fen├¬tre glissante [10, 120], calibr├®e par half-life estim├®e via AR(1)
4. **Seuils adaptatifs** ÔÇö base 2.0 ajust├® par r├®gime volatilit├® (┬▒0.4/+0.5) et half-life (┬▒0.3) ÔåÆ plage [1.0, 3.5]
5. **Filtres pr├®-entr├®e** ÔÇö r├®gime d├®tecteur (LOW/NORMAL/HIGH), momentum Z-score (slope 3 bars), stationnarit├® rolling ADF, CUSUM structural break, corr├®lation des legs, limites internes de risque (S4.4)
6. **Sorties** ÔÇö mean reversion (|Z| Ôëñ 0.5 ├ù exit_multiplier), trailing stop (├®largissement 1¤â), time stop, stop-loss positionnel, circuit breaker portfolio (DD > 15%)
7. **Dimensionnement** ÔÇö 2% du capital par paire, modifi├® par `position_multiplier` r├®gime (0.5├ùÔÇô1.0├ù)

### Hypoth├¿se ├®conomique sous-jacente

Coint├®gration ├®conomique entre des crypto-actifs corr├®l├®s (ex : ETH/BTC, altcoins L1/L2) supposant l'existence d'une relation d'├®quilibre stable ├á long terme retenant contre les chocs transitoires.

### Type r├®el

**Pseudo-arbitrage statistique** ÔÇö pas d'arbitrage v├®ritable (aucune garantie de convergence). La strat├®gie est fondamentalement une **corr├®lation-based mean reversion** habill├®e en coint├®gration. La persistance ├®conomique de la coint├®gration sur march├®s crypto est **structurellement fragile** (cycles altcoins, BTC dominance shifts, bankruptcies d'├®metteurs, tokenomics).

### Coh├®rence globale

Le code est multi-sprint, largement refactoris├®, avec une couverture de protection raisonnable. La complexit├® des garde-fous (10+ couches de protection) **contraste** avec l'absence de r├®sultats backtests document├®s sur donn├®es r├®elles.

---

## 2. Validit├® statistique

### Impl├®mentation du test Engle-Granger

**M├®thode :** OLS normalis├® (z-score des prix) ÔåÆ r├®sidus normalis├®s ÔåÆ ADF avec `autolag='AIC'`.  
**D├®normalisation du ╬▓ :** `beta_raw = (y_std ├ù ╬▓_n) / x_std` ÔÇö math├®matiquement correcte.  
**Correction Bonferroni :** `╬▒_corrig├® = 0.05 / (N ├ù (N-1) / 2)`.

> ­ƒö┤ **CRITIQUE ÔÇö Divergence double OLS :**  
> L'EG test utilise une **r├®gression OLS normalis├®e** (prix z-scor├®s) pour les r├®sidus ADF.  
> `SpreadModel` / `DynamicSpreadModel` utilisent une **r├®gression OLS brute** s├®par├®e (`np.linalg.lstsq`) sur les prix non normalis├®s pour calculer ╬▓, ╬▒, et les r├®sidus du spread utilis├® en trading.  
> Ces deux r├®gressions ne sont **jamais compar├®es ni v├®rifi├®es contre chaque autre**.  
> Le ╬▓ qui passe le test de coint├®gration n'est **pas le m├¬me ╬▓** utilis├® pour construire le spread trad├®. Si les prix ont des ordres de grandeur tr├¿s diff├®rents (ex : BTC ├á 50k, XRP ├á 0.5), la d├®normalisation peut produire un ╬▓ divergent de l'OLS brut. La coint├®gration est valid├®e sur une relation qui **ne correspond pas exactement** ├á celle trad├®e.

### P-value utilis├®e

**En-sample (d├®couverte) :** `╬▒_corrig├® = 0.05 / N_pairs` avec `N_pairs = N ├ù (N-1) / 2`.  
Pour 100 symboles : `╬▒ Ôëê 1.01e-5`.

> ­ƒö┤ **CRITIQUE ÔÇö Bonferroni ultra-restrictif potentiellement l├®tal :**  
> Avec un univers de ~100 symboles, le seuil Bonferroni est ~1e-5. Les p-values ADF pour r├®sidus de cointegration sur donn├®es crypto journali├¿res atteignent rarement ce niveau hors paires v├®ritablement co├»nt├®gr├®es (HL tr├¿s courte, BTC/ETH stables). En march├®s lat├®raux ou ├á forte rotation altcoins, la strat├®gie **d├®couvrira z├®ro paires**. Les backtests en p├®riodes historiques favorables (bull 2020ÔÇô2021, trending 2023) masquent ce risque op├®rationnel. Il n'existe aucun test documentant le taux de d├®couverte de paires par r├®gime de march├®.

**OOS re-validation :** `engle_granger_test` appel├® dans `OutOfSampleValidator` avec `num_symbols = len(discovered_unique_symbols)` ÔÇö **beaucoup plus faible** que l'univers complet. Un lot de 5 paires (10 symboles) donne `╬▒_corrig├® = 0.05 / 45 Ôëê 0.001` ÔÇö ~100├ù plus permissif que la d├®couverte. La validation OOS utilise de fait une barre nettement plus basse que la d├®couverte.

### Fen├¬tres roulantes ou statiques

**Pair discovery :** statique sur `lookback_window=252` barres.  
**Stationarity monitor :** rolling ADF sur les 60 derni├¿res observations ÔÇö correct.  
**Structural break :** CUSUM + ╬▓ stability sur r├®sidus complets ÔÇö correct.

### Risque de faux positifs

Avec Bonferroni strict en d├®couverte mais Bonferroni assoupli en OOS, les faux positifs r├®siduels passant la d├®couverte ont une **bonne chance de passer la re-validation OOS** (seuil plus bas). Le syst├¿me offre une apparence de rigueur mais contient une asym├®trie de rigueur entre les deux ├®tapes.

### Robustesse de la coint├®gration dans le temps

**Pr├®sente :**
- Rolling ADF tous les bars (StationarityMonitor)
- CUSUM + ╬▓ drift (StructuralBreakDetector)
- Rolling leg correlation (Sprint 4.6)
- Reestimation ╬▓ tous les 7 jours (HedgeRatioTracker)

**Absente :**
- Pas de test Granger causality syst├®matique pour distinguer cointegration ├®conomique de spurious regression
- Pas de test KPSS sur le spread (le KPSS n'est employ├® que pour la v├®rification I(1), pas sur le spread lui-m├¬me)

### Stabilit├® du hedge ratio

Reestimation hebdomadaire via OLS glissant. `is_deprecated=True` si drift > 10%. M├®canisme pr├®sent et fonctionnel.

### Risque de r├®gime shift

> ­ƒƒá **MAJEUR ÔÇö R├®gime d├®tecteur calculant la volatilit├® sur les niveaux du spread :**  
> `RegimeDetector.update(spread=spread.iloc[-1])` re├ºoit la **valeur** du spread (pas un rendement). Quand le spread oscille autour de z├®ro (comportement attendu), les "rendements" calcul├®s par `(curr - prev) / abs(prev)` ou `log(|curr/prev|)` produisent des valeurs explosives lorsque `prev` est proche de z├®ro. Cela g├®n├¿re des pressions de classification HIGH volatility artificielles et des seuils d'entr├®e injustement relev├®s, bloquant des entr├®es l├®gitimes. **Ce bug peut invalider la r├®gulation de taille de position.**
=======
# AUDIT STRATÉGIQUE — EDGECORE

> **Date :** 22 février 2026 | **Base :** code source intégral analysé, zéro supposition  
> **Périmètre :** stratégie, signaux, cointegration, spread, backtest, walk-forward, OOS, risk engine  

---

## 1. Nature réelle de la stratégie

### Description exacte inférée depuis le code

EDGECORE est une stratégie de **statistical arbitrage bivariate** basée sur la mean reversion de spreads cointégrés, opérant sur des paires de cryptomonnaies Binance (marché spot/perpetual).

Pipeline complet :

1. **Découverte de paires** — Engle-Granger (OLS normalisé → ADF sur résidus) + confirmation Johansen + consensus Newey-West HAC + filtre corrélation ≥ 0.75 + filtre liquidité ≥ $5M/24h
2. **Modélisation du spread** — OLS brut séparé (`SpreadModel` / `DynamicSpreadModel`) : `spread = y - (α + β·x)`
3. **Z-score adaptatif** — fenêtre glissante [10, 120], calibrée par half-life estimée via AR(1)
4. **Seuils adaptatifs** — base 2.0 ajusté par régime volatilité (±0.4/+0.5) et half-life (±0.3) → plage [1.0, 3.5]
5. **Filtres pré-entrée** — régime détecteur (LOW/NORMAL/HIGH), momentum Z-score (slope 3 bars), stationnarité rolling ADF, CUSUM structural break, corrélation des legs, limites internes de risque (S4.4)
6. **Sorties** — mean reversion (|Z| ≤ 0.5 × exit_multiplier), trailing stop (élargissement 1σ), time stop, stop-loss positionnel, circuit breaker portfolio (DD > 15%)
7. **Dimensionnement** — 2% du capital par paire, modifié par `position_multiplier` régime (0.5×–1.0×)

### Hypothèse économique sous-jacente

Cointégration économique entre des crypto-actifs corrélés (ex : ETH/BTC, altcoins L1/L2) supposant l'existence d'une relation d'équilibre stable à long terme retenant contre les chocs transitoires.

### Type réel

**Pseudo-arbitrage statistique** — pas d'arbitrage véritable (aucune garantie de convergence). La stratégie est fondamentalement une **corrélation-based mean reversion** habillée en cointégration. La persistance économique de la cointégration sur marchés crypto est **structurellement fragile** (cycles altcoins, BTC dominance shifts, bankruptcies d'émetteurs, tokenomics).

### Cohérence globale

Le code est multi-sprint, largement refactorisé, avec une couverture de protection raisonnable. La complexité des garde-fous (10+ couches de protection) **contraste** avec l'absence de résultats backtests documentés sur données réelles.

---

## 2. Validité statistique

### Implémentation du test Engle-Granger

**Méthode :** OLS normalisé (z-score des prix) → résidus normalisés → ADF avec `autolag='AIC'`.  
**Dénormalisation du β :** `beta_raw = (y_std × β_n) / x_std` — mathématiquement correcte.  
**Correction Bonferroni :** `α_corrigé = 0.05 / (N × (N-1) / 2)`.

> 🔴 **CRITIQUE — Divergence double OLS :**  
> L'EG test utilise une **régression OLS normalisée** (prix z-scorés) pour les résidus ADF.  
> `SpreadModel` / `DynamicSpreadModel` utilisent une **régression OLS brute** séparée (`np.linalg.lstsq`) sur les prix non normalisés pour calculer β, α, et les résidus du spread utilisé en trading.  
> Ces deux régressions ne sont **jamais comparées ni vérifiées contre chaque autre**.  
> Le β qui passe le test de cointégration n'est **pas le même β** utilisé pour construire le spread tradé. Si les prix ont des ordres de grandeur très différents (ex : BTC à 50k, XRP à 0.5), la dénormalisation peut produire un β divergent de l'OLS brut. La cointégration est validée sur une relation qui **ne correspond pas exactement** à celle tradée.

### P-value utilisée

**En-sample (découverte) :** `α_corrigé = 0.05 / N_pairs` avec `N_pairs = N × (N-1) / 2`.  
Pour 100 symboles : `α ≈ 1.01e-5`.

> 🔴 **CRITIQUE — Bonferroni ultra-restrictif potentiellement létal :**  
> Avec un univers de ~100 symboles, le seuil Bonferroni est ~1e-5. Les p-values ADF pour résidus de cointegration sur données crypto journalières atteignent rarement ce niveau hors paires véritablement coïntégrées (HL très courte, BTC/ETH stables). En marchés latéraux ou à forte rotation altcoins, la stratégie **découvrira zéro paires**. Les backtests en périodes historiques favorables (bull 2020–2021, trending 2023) masquent ce risque opérationnel. Il n'existe aucun test documentant le taux de découverte de paires par régime de marché.

**OOS re-validation :** `engle_granger_test` appelé dans `OutOfSampleValidator` avec `num_symbols = len(discovered_unique_symbols)` — **beaucoup plus faible** que l'univers complet. Un lot de 5 paires (10 symboles) donne `α_corrigé = 0.05 / 45 ≈ 0.001` — ~100× plus permissif que la découverte. La validation OOS utilise de fait une barre nettement plus basse que la découverte.

### Fenêtres roulantes ou statiques

**Pair discovery :** statique sur `lookback_window=252` barres.  
**Stationarity monitor :** rolling ADF sur les 60 dernières observations — correct.  
**Structural break :** CUSUM + β stability sur résidus complets — correct.

### Risque de faux positifs

Avec Bonferroni strict en découverte mais Bonferroni assoupli en OOS, les faux positifs résiduels passant la découverte ont une **bonne chance de passer la re-validation OOS** (seuil plus bas). Le système offre une apparence de rigueur mais contient une asymétrie de rigueur entre les deux étapes.

### Robustesse de la cointégration dans le temps

**Présente :**
- Rolling ADF tous les bars (StationarityMonitor)
- CUSUM + β drift (StructuralBreakDetector)
- Rolling leg correlation (Sprint 4.6)
- Reestimation β tous les 7 jours (HedgeRatioTracker)

**Absente :**
- Pas de test Granger causality systématique pour distinguer cointegration économique de spurious regression
- Pas de test KPSS sur le spread (le KPSS n'est employé que pour la vérification I(1), pas sur le spread lui-même)

### Stabilité du hedge ratio

Reestimation hebdomadaire via OLS glissant. `is_deprecated=True` si drift > 10%. Mécanisme présent et fonctionnel.

### Risque de régime shift

> 🟠 **MAJEUR — Régime détecteur calculant la volatilité sur les niveaux du spread :**  
> `RegimeDetector.update(spread=spread.iloc[-1])` reçoit la **valeur** du spread (pas un rendement). Quand le spread oscille autour de zéro (comportement attendu), les "rendements" calculés par `(curr - prev) / abs(prev)` ou `log(|curr/prev|)` produisent des valeurs explosives lorsque `prev` est proche de zéro. Cela génère des pressions de classification HIGH volatility artificielles et des seuils d'entrée injustement relevés, bloquant des entrées légitimes. **Ce bug peut invalider la régulation de taille de position.**
>>>>>>> origin/main

---

## 3. Construction du spread

<<<<<<< HEAD
### M├®thode de calcul

`spread = y - (╬▒ + ╬▓┬Àx)` via OLS brut sur fen├¬tre glissante. ╬▓ re-estim├® tous les 7 jours ou en cas d'urgence (ÔëÑ 3¤â volatilit├® spread).

### Normalisation

Z-score rolling sur fen├¬tre [10, 120], centr├®e/r├®duite. Clamping ├á [-6, +6]. M├®canisme correct.

### Stationnarit├® v├®rifi├®e ou suppos├®e ?

**V├®rifi├®e (rolling ADF)** tous les bars sur les 60 derni├¿res observations. Seuil conservateur (p < 0.10). Ce m├®canisme est la protection principale contre la non-stationnarit├® inter-red├®couvertes.

### Robustesse du Z-score

L'adaptive lookback bas├®e sur le half-life est **coh├®rente** : HL=5 ÔåÆ lookback=15, HL=60 ÔåÆ lookback=60. La d├®pendance ├á la pr├®cision du half-life estim├® (AR(1) sur 252 observations max) introduit une sensibilit├® : une mauvaise estimation de HL biaise la fen├¬tre de Z-score.

### Sensibilit├® aux outliers

`remove_outliers(threshold=4.0)` + `ffill()` avant calcul du spread. Seul `ffill` sans `bfill` ÔÇö conforme (pas de look-ahead via bfill).

> ­ƒƒí **MINEUR :** Le forward-fill sur outliers cr├®e des bougies "phant├┤mes" o├╣ le spread est calcul├® sur un prix fictif. Pour des cryptos tr├¿s volatiles (ex : PEPE durante un KOL pump), plusieurs barres cons├®cutives d'outlier peuvent produire un "faux spread stable" suivi d'un retour brutal au prix r├®el ÔÇö r├®sultant en un faux signal d'entr├®e.

---

## 4. Logique d'entr├®e / sortie

### Seuil |Z| > 2 justifi├® ou arbitraire ?

Base 2.0 param├®trique. Ajustements volatilit├® (┬▒0.4/0.5) et HL (┬▒0.3) produits empiriquement ÔÇö **aucune justification statistique document├®e** pour les valeurs d'ajustement sp├®cifiques. Aucun r├®sultat de cross-validation param├®trique n'accompagne ces choix.

> ­ƒƒá **MAJEUR ÔÇö Param├¿tres empiriques non valid├®s :**  
> 12+ param├¿tres libres (seuils, ajustements, fen├¬tres, coefficients de r├®gimes) d├®finis manuellement. `ParameterCrossValidator` existe dans le code mais **aucune trace d'ex├®cution ni de rapport** dans la base de code ou la documentation. Le risque de sur-ajustement implicite est ├®lev├®.

### Optimisation implicite

Les coefficients d'ajustement (ÔêÆ0.4 LOW, +0.5 HIGH, ÔêÆ0.3 courte HL, +0.3 longue HL) ressemblent ├á des valeurs t├ótonn├®es plut├┤t que optimis├®es. Sans CV document├®, ces chiffres sont des **priors non valid├®s**.

### Risque de sur-ajustement

L'univers contient des Tier4 altcoins (PEPE, SHIB, FLOKI, BONK, WIF, TURBO, BLUR). L'historique de ces tokens est court (< 2 ans) et domin├® par des r├®gimes de corr├®lation ├®pisodiques. L'int├®gration de ces actifs dans l'univers de coint├®gration **gonfle artificiellement le nombres de paires test├®es** (et donc la correction Bonferroni) sans apporter de paires r├®ellement exploitables.

### Absence ou pr├®sence de stop

**Pr├®sents :**
- Trailing stop (├®largissement 1¤â depuis entr├®e)
=======
### Méthode de calcul

`spread = y - (α + β·x)` via OLS brut sur fenêtre glissante. β re-estimé tous les 7 jours ou en cas d'urgence (≥ 3σ volatilité spread).

### Normalisation

Z-score rolling sur fenêtre [10, 120], centrée/réduite. Clamping à [-6, +6]. Mécanisme correct.

### Stationnarité vérifiée ou supposée ?

**Vérifiée (rolling ADF)** tous les bars sur les 60 dernières observations. Seuil conservateur (p < 0.10). Ce mécanisme est la protection principale contre la non-stationnarité inter-redécouvertes.

### Robustesse du Z-score

L'adaptive lookback basée sur le half-life est **cohérente** : HL=5 → lookback=15, HL=60 → lookback=60. La dépendance à la précision du half-life estimé (AR(1) sur 252 observations max) introduit une sensibilité : une mauvaise estimation de HL biaise la fenêtre de Z-score.

### Sensibilité aux outliers

`remove_outliers(threshold=4.0)` + `ffill()` avant calcul du spread. Seul `ffill` sans `bfill` — conforme (pas de look-ahead via bfill).

> 🟡 **MINEUR :** Le forward-fill sur outliers crée des bougies "phantômes" où le spread est calculé sur un prix fictif. Pour des cryptos très volatiles (ex : PEPE durante un KOL pump), plusieurs barres consécutives d'outlier peuvent produire un "faux spread stable" suivi d'un retour brutal au prix réel — résultant en un faux signal d'entrée.

---

## 4. Logique d'entrée / sortie

### Seuil |Z| > 2 justifié ou arbitraire ?

Base 2.0 paramétrique. Ajustements volatilité (±0.4/0.5) et HL (±0.3) produits empiriquement — **aucune justification statistique documentée** pour les valeurs d'ajustement spécifiques. Aucun résultat de cross-validation paramétrique n'accompagne ces choix.

> 🟠 **MAJEUR — Paramètres empiriques non validés :**  
> 12+ paramètres libres (seuils, ajustements, fenêtres, coefficients de régimes) définis manuellement. `ParameterCrossValidator` existe dans le code mais **aucune trace d'exécution ni de rapport** dans la base de code ou la documentation. Le risque de sur-ajustement implicite est élevé.

### Optimisation implicite

Les coefficients d'ajustement (−0.4 LOW, +0.5 HIGH, −0.3 courte HL, +0.3 longue HL) ressemblent à des valeurs tâtonnées plutôt que optimisées. Sans CV documenté, ces chiffres sont des **priors non validés**.

### Risque de sur-ajustement

L'univers contient des Tier4 altcoins (PEPE, SHIB, FLOKI, BONK, WIF, TURBO, BLUR). L'historique de ces tokens est court (< 2 ans) et dominé par des régimes de corrélation épisodiques. L'intégration de ces actifs dans l'univers de cointégration **gonfle artificiellement le nombres de paires testées** (et donc la correction Bonferroni) sans apporter de paires réellement exploitables.

### Absence ou présence de stop

**Présents :**
- Trailing stop (élargissement 1σ depuis entrée)
>>>>>>> origin/main
- Time stop (via `TimeStopManager`)
- Stop-loss positionnel (3% `max_position_loss_pct`)
- Internal drawdown guard (10% depuis pic equity)
- Portfolio circuit breaker (15%)

<<<<<<< HEAD
> ­ƒƒá **MAJEUR ÔÇö Stop-loss de 3% insuffisant pour crypto altcoins :**  
> Pour une paire incluant GALA, FLOW, ou un jeton mid-cap, un mouvement de 3% est du bruit intra-journalier. Le stop-loss r├®el pour prot├®ger contre une d├®corr├®lation brutale (FTX-style, Luna-style) devrait ├¬tre calibr├® en termes de Z-score, non en % de notionnel de position.

### Gestion du temps en position

`TimeStopManager` active. Max dur├®e = `min(2 ├ù half_life, cap)`.

> ­ƒö┤ **CRITIQUE ÔÇö `entry_time = datetime.now()` en backtest :**  
> Dans `generate_signals()`, lors de l'enregistrement d'un trade :  
> `entry_trade_info['entry_time'] = datetime.now()`  
> En backtest, **`datetime.now()` retourne la date r├®elle d'ex├®cution du code**, pas la date de la barre historique. Toutes les fonctionnalit├®s bas├®es sur la dur├®e de position (TimeStopManager, Markov regime duration) sont **calcul├®es en temps r├®el, pas en temps simul├®**. Les positions ouvertes ├á la barre T et closes ├á T+5 bars se voient attribuer une dur├®e de quelques **millisecondes** (temps CPU), pas 5 jours. Le time stop est **structurellement non fonctionnel en backtest**.

### Risque de drift structurel

Couvert par CUSUM + ╬▓ stability. M├®canisme pr├®sent.
=======
> 🟠 **MAJEUR — Stop-loss de 3% insuffisant pour crypto altcoins :**  
> Pour une paire incluant GALA, FLOW, ou un jeton mid-cap, un mouvement de 3% est du bruit intra-journalier. Le stop-loss réel pour protéger contre une décorrélation brutale (FTX-style, Luna-style) devrait être calibré en termes de Z-score, non en % de notionnel de position.

### Gestion du temps en position

`TimeStopManager` active. Max durée = `min(2 × half_life, cap)`.

> 🔴 **CRITIQUE — `entry_time = datetime.now()` en backtest :**  
> Dans `generate_signals()`, lors de l'enregistrement d'un trade :  
> `entry_trade_info['entry_time'] = datetime.now()`  
> En backtest, **`datetime.now()` retourne la date réelle d'exécution du code**, pas la date de la barre historique. Toutes les fonctionnalités basées sur la durée de position (TimeStopManager, Markov regime duration) sont **calculées en temps réel, pas en temps simulé**. Les positions ouvertes à la barre T et closes à T+5 bars se voient attribuer une durée de quelques **millisecondes** (temps CPU), pas 5 jours. Le time stop est **structurellement non fonctionnel en backtest**.

### Risque de drift structurel

Couvert par CUSUM + β stability. Mécanisme présent.
>>>>>>> origin/main

---

## 5. Backtesting & Validation

<<<<<<< HEAD
### S├®paration in-sample / out-of-sample r├®elle ?

Oui ÔÇö Walk-forward avec `strategy.disable_cache()` et fresh strategy par p├®riode. La structure WF est correcte dans son architecture.

### Walk-forward correctement impl├®ment├® ?

**Fen├¬tre expansive** (expanding window) : chaque p├®riode d'entra├«nement commence en t=0. C'est une d├®cision de design d├®fendable mais qui **surexpose les p├®riodes r├®centes** : les paires dominent les derni├¿res p├®riodes d'entra├«nement qui couvrent le plus de donn├®es.

**OOS per-period :** `oos_per_period = max(1, oos_total_rows // num_periods)`. Avec `num_periods=4` et `oos_ratio=0.2`, les p├®riodes de test couvrent chacune environ 5% du total. **Avec 2 ans de donn├®es (504 barres) et 4 p├®riodes, chaque fen├¬tre test = ~25 barres Ôëê 1 mois**. Ce n'est pas suffisant pour ├®valuer la robustesse OOS d'une strat├®gie dont les half-lives peuvent atteindre 60 jours.

### Data leakage possible ?

> ­ƒƒá **MAJEUR ÔÇö Half-life utilis├® en OOS d├®coule de la p├®riode d'entra├«nement mais pas recalibr├® pendant le test :**  
> Les paires `(sym1, sym2, pvalue, hl)` issues du training sont pass├®es au simulateur via `fixed_pairs`. Le `hl` est le half-life de la p├®riode d'entra├«nement. Pendant la p├®riode de test, `DynamicSpreadModel` re-calcule le Z-score avec une fen├¬tre adapt├®e ├á `hl` du training AND estime un nouveau HL depuis les donn├®es disponibles. Mais le **seuil d'entr├®e adaptatif** continue d'utiliser `hl` de la d├®couverte comme base. Ce n'est pas un data leakage strict mais une **incoh├®rence de calibration** : les seuils entr├®e/sortie sont partiellement ancr├®s ├á des statistiques in-sample.

> ­ƒƒá **MAJEUR ÔÇö Position time tracking en backtest (r├®f. ┬º4) :**  
> Le time stop est bas├® sur `datetime.now()` ÔÇö toutes les positions en backtest ont une dur├®e de vie de quelques ms. Le simulateur ne se rend **jamais compte** qu'une position a expir├® son time stop. **Toute position ouverte dans un backtest ne sera jamais ferm├®e par le time stop**, ce qui peut cr├®er des positions zombie jusqu'├á la prochaine divergence de Z-score ou circuit breaker.

### Survivorship bias ?

L'univers inclut des tokens qui pourraient avoir d├®list├® (BSV/USDT rare sur Binance, WAXP, AGLD, MAGIC ├á liquidit├® intermittente). Le `DelistingGuard` d├®tecte les tokens mourants mais **ne garantit pas l'existence historique de ces assets** dans la fen├¬tre de backtest. Si le DataLoader charge seulement les assets encore actifs en 2026, les backtests 2022ÔÇô2024 souffrent d'un **survivorship bias partiel**.

### Look-ahead bias ?

**Aucun look-ahead d├®tect├®** dans la construction du signal :
- Expanding window correctement impl├®ment├®e (slice `iloc[:bar_idx+1]`)
- `ffill()` uniquement, pas de `bfill()`
- Cache d├®sactiv├® en walk-forward

### Slippage et frais r├®alistes ?

`CostModel` : 10 bps maker = 10 bps taker, 5 bps slippage de base, mod├¿le volume-adaptatif, borrowing cost 5%/an pour short leg.

> ­ƒƒá **MAJEUR ÔÇö Volume par d├®faut de 1e9 USD/24h :**  
> Dans `execution_cost_one_leg`, le param├¿tre `volume_24h` est d├®fini par d├®faut ├á `1e9`. Sauf appel explicite avec le volume r├®el, **tous les calculs de slippage utilisent 1 milliard USD de volume**, ce qui ram├¿ne l'impact march├® ├á quasi-z├®ro (tr├¿s optimiste). Pour MAGIC/USDT, WAXP/USDT, AGLD/USDT dont le volume est < $10M, le slippage r├®el est 10ÔÇô100├ù sup├®rieur ├á celui mod├®lis├®. **Les r├®sultats de backtest sur ces actifs sont financi├¿rement irr├®alistes.**

> ­ƒƒí **MINEUR ÔÇö `include_funding=False` par d├®faut :**  
> Les perpetual futures sur Binance ont un taux de financement moyen de 0.01%/8h (soit ~0.03%/jour). Pour une position d├®tenue 20 jours, ce co├╗t suppl├®mentaire repr├®sente 0.6% de notionnel ÔÇö non captur├® par d├®faut.

### Annualisation (Sharpe / m├®triques)

> ­ƒö┤ **CRITIQUE ÔÇö `TRADING_DAYS_PER_YEAR = 252` pour des actifs crypto qui tradent 365j/an :**  
> Le Sharpe est calcul├® comme `(returns.mean() / returns.std()) ├ù ÔêÜ252`.  
> Les cryptos tradent 7j/7, 365j/an. L'utilisation de 252 jours **sous-annualise le d├®nominateur**, ce qui **surestime le Sharpe d'un facteur ÔêÜ(365/252) Ôëê 1.20**.  
> Pour un Sharpe "apparent" de 1.5 sur backtest crypto, le Sharpe correct est **~1.25**.  
> Cette inflation est syst├®matique dans toutes les sorties de m├®triques. Le commentaire dans le code dit explicitement "Default is 252 for equities (target market)" ÔÇö **mais EDGECORE trade du crypto, pas des equities.**

> ­ƒƒí **MINEUR ÔÇö Sharpe sans risk-free rate :**  
> Aucune d├®duction du taux sans risque (> 4.5% en 2023ÔÇô2024). Un Sharpe apparent de 1.5 se r├®duit ├á ~0.9ÔÇô1.0 en exc├¿s de rendement.

---

## 6. Robustesse en environnement r├®el

### Sensibilit├® aux gaps

Les cryptos ont des gaps sur d├®listing, hard forks (BCH, BSV), exploits (LUNA, FTT). La strat├®gie n'a aucun m├®canisme de filtrage des gaps de prix brutaux autre que le z-score outlier ├á 4¤â. Un gap de ÔêÆ50% (LUNA-style) produit un Z-score de ~ÔêÆ15 (clamp├® ├á ÔêÆ6) ÔÇö la protection n'est pas un stop-loss de prix.

### Sensibilit├® ├á la liquidit├®

Le filtre liquidit├® ($5M/24h minimum) est trop bas pour une strat├®gie institutionnelle. Pour un capital de $100k et une allocation de 2% par paire ($2k), la participation est <0.04% du volume ÔÇö acceptable. Mais si le capital monte ├á $1M, $5M de volume devient contraignant. **La strat├®gie n'est pas scalable au-del├á de $200ÔÇô300k de capital sans r├®├®valuer les seuils de liquidit├®.**

### Impact du slippage (r├®el vs mod├®lis├®)

Voir ┬º5. Le slippage est s├®v├¿rement sous-estim├® pour les Tier 3/4 altcoins en raison du `volume_24h` par d├®faut.

### Impact des frais Binance

4 transactions par round-trip ├ù 10 bps = 40 bps minimum en frais, + 10 bps slippage minimum = **50 bps de frais de base par trade**. Pour un spread avec ¤â = 5% et entr├®e ├á Z=2.0 (spread = 10% au-del├á de la moyenne), l'edge esp├®r├® au retour ├á la moyenne est ~10%. Apr├¿s 50 bps de frais = 9.5%. Net positif mais marginal.

Pour des paires avec HL = 5 jours tradant tr├¿s fr├®quemment, la rotation de capital peut ├®liminer cet edge sur des s├®quences de 5ÔÇô7 trades.

### Risque de breakdown de corr├®lation

Couvert par rolling leg correlation monitor (Sprint 4.6). La d├®tection d├®clenche une exclusion imm├®diate du pair.

### Sc├®narios critiques

| Sc├®nario | Impact th├®orique | Protection actuelle |
|---|---|---|
| **Crash march├® (ÔêÆ40% BTC en 24h)** | Tous les spreads crypto divergent simultan├®ment ; corr├®lations ÔåÆ 1 ; cointegration bris├®e ; positions directionnelles nettes. | Circuit breaker 15% + time stop + trailing stop ÔÇö protection tardive, le crash survient intraday. |
| **Volatilit├® extr├¬me prolong├®e (5ÔÇô10 jours)** | Faux signaux d'entr├®e en r├®gime HIGH (seuil ├®lev├® ÔåÆ peu d'entr├®es) ; mais les positions existantes peuvent souffrir davantage. | R├®gime d├®tecteur r├®duit la taille ; stationarity monitor ferme les positions non stationnaires. |
| **D├®corr├®lation brutale (terra/luna-style)** | Un leg s'effondre de ÔêÆ99% ; l'autre non ; spread explose. | Leg correlation breakdown d├®tect├® en quelques barres ÔÇö mais dommage d├®j├á fait si journalier. |

> ­ƒö┤ **CRITIQUE ÔÇö Aucun guard contre la perte totale d'un leg :**  
> Si un token du portefeuille est suspendu ou d├®liste instantan├®ment (FTT/USDT, LUNC), la strat├®gie ne peut pas sortir automatiquement avant la prochaine barre. Un d├®listing peut effacer 100% de la valeur du leg concern├®. Le `DelistingGuard` filtre les tokens "mourants" mais ne pr├®vient pas un d├®listing de surprise.
=======
### Séparation in-sample / out-of-sample réelle ?

Oui — Walk-forward avec `strategy.disable_cache()` et fresh strategy par période. La structure WF est correcte dans son architecture.

### Walk-forward correctement implémenté ?

**Fenêtre expansive** (expanding window) : chaque période d'entraînement commence en t=0. C'est une décision de design défendable mais qui **surexpose les périodes récentes** : les paires dominent les dernières périodes d'entraînement qui couvrent le plus de données.

**OOS per-period :** `oos_per_period = max(1, oos_total_rows // num_periods)`. Avec `num_periods=4` et `oos_ratio=0.2`, les périodes de test couvrent chacune environ 5% du total. **Avec 2 ans de données (504 barres) et 4 périodes, chaque fenêtre test = ~25 barres ≈ 1 mois**. Ce n'est pas suffisant pour évaluer la robustesse OOS d'une stratégie dont les half-lives peuvent atteindre 60 jours.

### Data leakage possible ?

> 🟠 **MAJEUR — Half-life utilisé en OOS découle de la période d'entraînement mais pas recalibré pendant le test :**  
> Les paires `(sym1, sym2, pvalue, hl)` issues du training sont passées au simulateur via `fixed_pairs`. Le `hl` est le half-life de la période d'entraînement. Pendant la période de test, `DynamicSpreadModel` re-calcule le Z-score avec une fenêtre adaptée à `hl` du training AND estime un nouveau HL depuis les données disponibles. Mais le **seuil d'entrée adaptatif** continue d'utiliser `hl` de la découverte comme base. Ce n'est pas un data leakage strict mais une **incohérence de calibration** : les seuils entrée/sortie sont partiellement ancrés à des statistiques in-sample.

> 🟠 **MAJEUR — Position time tracking en backtest (réf. §4) :**  
> Le time stop est basé sur `datetime.now()` — toutes les positions en backtest ont une durée de vie de quelques ms. Le simulateur ne se rend **jamais compte** qu'une position a expiré son time stop. **Toute position ouverte dans un backtest ne sera jamais fermée par le time stop**, ce qui peut créer des positions zombie jusqu'à la prochaine divergence de Z-score ou circuit breaker.

### Survivorship bias ?

L'univers inclut des tokens qui pourraient avoir délisté (BSV/USDT rare sur Binance, WAXP, AGLD, MAGIC à liquidité intermittente). Le `DelistingGuard` détecte les tokens mourants mais **ne garantit pas l'existence historique de ces assets** dans la fenêtre de backtest. Si le DataLoader charge seulement les assets encore actifs en 2026, les backtests 2022–2024 souffrent d'un **survivorship bias partiel**.

### Look-ahead bias ?

**Aucun look-ahead détecté** dans la construction du signal :
- Expanding window correctement implémentée (slice `iloc[:bar_idx+1]`)
- `ffill()` uniquement, pas de `bfill()`
- Cache désactivé en walk-forward

### Slippage et frais réalistes ?

`CostModel` : 10 bps maker = 10 bps taker, 5 bps slippage de base, modèle volume-adaptatif, borrowing cost 5%/an pour short leg.

> 🟠 **MAJEUR — Volume par défaut de 1e9 USD/24h :**  
> Dans `execution_cost_one_leg`, le paramètre `volume_24h` est défini par défaut à `1e9`. Sauf appel explicite avec le volume réel, **tous les calculs de slippage utilisent 1 milliard USD de volume**, ce qui ramène l'impact marché à quasi-zéro (très optimiste). Pour MAGIC/USDT, WAXP/USDT, AGLD/USDT dont le volume est < $10M, le slippage réel est 10–100× supérieur à celui modélisé. **Les résultats de backtest sur ces actifs sont financièrement irréalistes.**

> 🟡 **MINEUR — `include_funding=False` par défaut :**  
> Les perpetual futures sur Binance ont un taux de financement moyen de 0.01%/8h (soit ~0.03%/jour). Pour une position détenue 20 jours, ce coût supplémentaire représente 0.6% de notionnel — non capturé par défaut.

### Annualisation (Sharpe / métriques)

> 🔴 **CRITIQUE — `TRADING_DAYS_PER_YEAR = 252` pour des actifs crypto qui tradent 365j/an :**  
> Le Sharpe est calculé comme `(returns.mean() / returns.std()) × √252`.  
> Les cryptos tradent 7j/7, 365j/an. L'utilisation de 252 jours **sous-annualise le dénominateur**, ce qui **surestime le Sharpe d'un facteur √(365/252) ≈ 1.20**.  
> Pour un Sharpe "apparent" de 1.5 sur backtest crypto, le Sharpe correct est **~1.25**.  
> Cette inflation est systématique dans toutes les sorties de métriques. Le commentaire dans le code dit explicitement "Default is 252 for equities (target market)" — **mais EDGECORE trade du crypto, pas des equities.**

> 🟡 **MINEUR — Sharpe sans risk-free rate :**  
> Aucune déduction du taux sans risque (> 4.5% en 2023–2024). Un Sharpe apparent de 1.5 se réduit à ~0.9–1.0 en excès de rendement.

---

## 6. Robustesse en environnement réel

### Sensibilité aux gaps

Les cryptos ont des gaps sur délisting, hard forks (BCH, BSV), exploits (LUNA, FTT). La stratégie n'a aucun mécanisme de filtrage des gaps de prix brutaux autre que le z-score outlier à 4σ. Un gap de −50% (LUNA-style) produit un Z-score de ~−15 (clampé à −6) — la protection n'est pas un stop-loss de prix.

### Sensibilité à la liquidité

Le filtre liquidité ($5M/24h minimum) est trop bas pour une stratégie institutionnelle. Pour un capital de $100k et une allocation de 2% par paire ($2k), la participation est <0.04% du volume — acceptable. Mais si le capital monte à $1M, $5M de volume devient contraignant. **La stratégie n'est pas scalable au-delà de $200–300k de capital sans réévaluer les seuils de liquidité.**

### Impact du slippage (réel vs modélisé)

Voir §5. Le slippage est sévèrement sous-estimé pour les Tier 3/4 altcoins en raison du `volume_24h` par défaut.

### Impact des frais Binance

4 transactions par round-trip × 10 bps = 40 bps minimum en frais, + 10 bps slippage minimum = **50 bps de frais de base par trade**. Pour un spread avec σ = 5% et entrée à Z=2.0 (spread = 10% au-delà de la moyenne), l'edge espéré au retour à la moyenne est ~10%. Après 50 bps de frais = 9.5%. Net positif mais marginal.

Pour des paires avec HL = 5 jours tradant très fréquemment, la rotation de capital peut éliminer cet edge sur des séquences de 5–7 trades.

### Risque de breakdown de corrélation

Couvert par rolling leg correlation monitor (Sprint 4.6). La détection déclenche une exclusion immédiate du pair.

### Scénarios critiques

| Scénario | Impact théorique | Protection actuelle |
|---|---|---|
| **Crash marché (−40% BTC en 24h)** | Tous les spreads crypto divergent simultanément ; corrélations → 1 ; cointegration brisée ; positions directionnelles nettes. | Circuit breaker 15% + time stop + trailing stop — protection tardive, le crash survient intraday. |
| **Volatilité extrême prolongée (5–10 jours)** | Faux signaux d'entrée en régime HIGH (seuil élevé → peu d'entrées) ; mais les positions existantes peuvent souffrir davantage. | Régime détecteur réduit la taille ; stationarity monitor ferme les positions non stationnaires. |
| **Décorrélation brutale (terra/luna-style)** | Un leg s'effondre de −99% ; l'autre non ; spread explose. | Leg correlation breakdown détecté en quelques barres — mais dommage déjà fait si journalier. |

> 🔴 **CRITIQUE — Aucun guard contre la perte totale d'un leg :**  
> Si un token du portefeuille est suspendu ou déliste instantanément (FTT/USDT, LUNC), la stratégie ne peut pas sortir automatiquement avant la prochaine barre. Un délisting peut effacer 100% de la valeur du leg concerné. Le `DelistingGuard` filtre les tokens "mourants" mais ne prévient pas un délisting de surprise.
>>>>>>> origin/main

---

## 7. Interaction avec le Risk Engine

<<<<<<< HEAD
### La strat├®gie d├®pend-elle trop du risk engine ?

Non ÔÇö la strat├®gie `pair_trading.py` a ses **propres limites internes** (Sprint 4.4) : 8 positions max, 10% DD, 20 trades/jour. Le `RiskEngine` ext├®rieur est **optionnel** dans `StrategyBacktestSimulator` (param├¿tre `risk_engine=None`).

### Le risk engine compense-t-il une faiblesse structurelle ?

Partiellement. Le circuit breaker portfolio (15% DD) est le dernier rempart contre une s├®quence de pertes corr├®l├®es. Sans signal edge r├®el, ce circuit breaker sera d├®clench├® r├®guli├¿rement ÔÇö ce qui est un signal d'alarme, pas une protection suffisante.

### La strat├®gie reste-t-elle viable sans protection externe ?

> ­ƒƒá **MAJEUR ÔÇö Viabilit├® sans risk engine non test├®e :**  
> Aucun backtest ne documente les r├®sultats avec `risk_engine=None` vs `risk_engine` actif. L'impact des diff├®rentes couches de protection sur le P&L (trailing stop, concentration limits, internal drawdown) n'est jamais isol├®. On ne sait pas si la strat├®gie est profitable avant protection ou si les garde-fous d├®guisent une strat├®gie marginalement negative-edge.

---

## 8. Scalabilit├® strat├®gique

### Peut-elle ├¬tre multi-paires ?

Architecturalement oui ÔÇö jusqu'├á 8 positions simultan├®es. La concentration par symbole est limit├®e ├á 30%.

### Risque de corr├®lation crois├®e entre spreads ?

`SpreadCorrelationGuard` (¤ü_max = 0.60) + `PCASpreadMonitor` actifs. Ces protections sont pr├®sentes mais n'ont pas de r├®sultats document├®s sur la r├®duction de drawdown.

### Effet de crowding potentiel ?

> ­ƒƒá **MAJEUR ÔÇö Univers de paires crypto sur Binance identique ├á tous les acteurs stat arb crypto :**  
> BTC/ETH, ETH/BNB, SOL/AVAX sont les paires "├®videntes" test├®es par tous les fonds de stat arb crypto. En p├®riode de stress (liquidations DeFi, CeFi), toutes ces strat├®gies se d├®bouclent simultan├®ment, amplifiant les pertes. EDGECORE n'int├¿gre aucune mesure de crowding ni aucun signal d'alerte sur le spread momentum d'un c├┤t├® du livre d'ordres.

---

## 9. Failles critiques identifi├®es

### ­ƒö┤ Critique

| ID | Faille | Localisation | Impact |
|---|---|---|---|
| C-01 | `TRADING_DAYS_PER_YEAR = 252` sur actifs crypto (365j/an) ÔåÆ Sharpe surestim├® de ~20% syst├®matiquement | `backtests/metrics.py:11` | Illusion de performance ÔÇö tous les Sharpe publi├®s sont faux |
| C-02 | `entry_time = datetime.now()` en backtest ÔåÆ time stop et duration-based features non fonctionnels dans toutes les simulations | `strategies/pair_trading.py` (generate_signals, active_trades dict) | Le time stop ne se d├®clenche jamais en backtest ÔÇö positions zombie possibles |
| C-03 | Double OLS divergent : EG test utilise OLS normalis├®, SpreadModel utilise OLS brut, jamais compar├®s ÔÇö le ╬▓ valid├® Ôëá ╬▓ trad├® | `models/cointegration.py` + `models/spread.py` | La cointegration est valid├®e sur une relation statistiquement diff├®rente de celle r├®ellement trad├®e |
| C-04 | Bonferroni ╬▒ Ôëê 1e-5 avec ~100 symboles ÔåÆ zero pairs en march├®s non-trending ÔåÆ strat├®gie silencieuse et non diagnostiqu├®e comme telle | `strategies/pair_trading.py:_test_pair_cointegration` | Incapacit├® ├á g├®n├®rer des signaux sans d├®tection explicite |
| C-05 | Aucun stop contre d├®listing surprise d'un leg (FTT, LUNA) ÔåÆ perte totale du leg sans gate | `strategies/pair_trading.py`, absence | Risque de perte catastrophique sans recours |

### ­ƒƒá Majeur

| ID | Faille | Localisation | Impact |
|---|---|---|---|
| M-01 | R├®gime d├®tecteur calcule volatilit├® depuis niveaux spread (approchant z├®ro) ÔåÆ r├®gime HIGH artificiel, blocage d'entr├®es l├®gitimes | `models/regime_detector.py:update()` | Classification de r├®gime biais├®e ÔåÆ sizing agressif sous-activ├® |
| M-02 | OOS re-validation utilise Bonferroni avec `num_symbols = len(unique_symbols_in_pairs)` ÔÇö beaucoup moins strict que la d├®couverte | `validation/oos_validator.py:__init__` | La validation OOS est moins rigoureuse que la d├®couverte ÔÇö faux sentiment de robustesse |
| M-03 | Volume 24h default ├á 1e9 USD ÔåÆ slippage quasi-nul pour Tier3/Tier4 altcoins | `backtests/cost_model.py:execution_cost_one_leg` | Co├╗ts d'ex├®cution sous-estim├®s de 10ÔÇô100├ù sur altcoins peu liquides |
| M-04 | Aucun r├®sultat de `ParameterCrossValidator` document├® ÔÇö 12+ param├¿tres libres non valid├®s par CV | `backtests/parameter_cv.py` | Sur-ajustement implicite ├á param├¿tres manuels |
| M-05 | Z-slope momentum filter sur 3 bars quotidiens = bruit statistique pur ÔÇö rejette arbitrairement des entr├®es valides | `strategies/pair_trading.py:z_momentum_ok` | D├®gradation du hit rate sans filtrage de qualit├® r├®el |
| M-06 | Fen├¬tres test walk-forward trop courtes (~25 barres/p├®riode avec 2 ans de donn├®es) ÔÇö pas suffisant pour extrapoler statistiquement | `backtests/walk_forward.py:split_walk_forward` | M├®triques OOS statistiquement non fiables |
| M-07 | Stress tests (`StressTestRunner`) impl├®ment├®s mais aucun r├®sultat enregistr├® ni int├®gr├® ├á la CI | `backtests/stress_testing.py` | R├®silience aux sc├®narios extr├¬mes non d├®montr├®e |
| M-08 | Stop-loss positionnel 3% insuffisant pour altcoins crypto ÔÇö ne prot├¿ge pas contre une d├®corr├®lation l├®g├¿re ou un pump/dump | `backtests/strategy_simulator.py:max_position_loss_pct=0.03` | Faux sentiment de protection sur actifs ├á volatilit├® quotidienne 5ÔÇô15% |

### ­ƒƒí Mineur

| ID | Faille | Localisation | Impact |
|---|---|---|---|
| mn-01 | Sharpe sans risk-free rate (4.5%+ en 2023ÔÇô2024) ÔåÆ surestimation ~0.5 point de Sharpe en absolu | `backtests/metrics.py:from_returns` | Performance apparente sup├®rieure ├á la performance ajust├®e r├®elle |
| mn-02 | `include_funding=False` par d├®faut ÔÇö co├╗t de financement perpetuals non captur├® | `backtests/cost_model.py` | Sous-estimation des co├╗ts sur futures de 0.6% pour 20 jours de d├®tention |
| mn-03 | Tier4 altcoins (PEPE, SHIB, FLOKI) ├®largissent l'univers mais g├®n├¿rent quasi-aucune paire valid├®e : gaspillage de tests Bonferroni et bruit statistique | `config/prod.yaml` | Bonferroni plus strict inutilement sur vraies paires |
| mn-04 | `ffill()` sur outliers peut cr├®er prix fant├┤mes pendant plusieurs barres et faux signals | `data/preprocessing.py` + `strategies/pair_trading.py` | Signal spurieux sur tokens ultra-volatils |
| mn-05 | `PartialProfitManager` initialis├® dans `StrategyBacktestSimulator` mais jamais appel├® explicitement dans la boucle de trade | `backtests/strategy_simulator.py` | Feature document├®e mais ornementale ÔÇö aucun partial profit r├®el |
=======
### La stratégie dépend-elle trop du risk engine ?

Non — la stratégie `pair_trading.py` a ses **propres limites internes** (Sprint 4.4) : 8 positions max, 10% DD, 20 trades/jour. Le `RiskEngine` extérieur est **optionnel** dans `StrategyBacktestSimulator` (paramètre `risk_engine=None`).

### Le risk engine compense-t-il une faiblesse structurelle ?

Partiellement. Le circuit breaker portfolio (15% DD) est le dernier rempart contre une séquence de pertes corrélées. Sans signal edge réel, ce circuit breaker sera déclenché régulièrement — ce qui est un signal d'alarme, pas une protection suffisante.

### La stratégie reste-t-elle viable sans protection externe ?

> 🟠 **MAJEUR — Viabilité sans risk engine non testée :**  
> Aucun backtest ne documente les résultats avec `risk_engine=None` vs `risk_engine` actif. L'impact des différentes couches de protection sur le P&L (trailing stop, concentration limits, internal drawdown) n'est jamais isolé. On ne sait pas si la stratégie est profitable avant protection ou si les garde-fous déguisent une stratégie marginalement negative-edge.

---

## 8. Scalabilité stratégique

### Peut-elle être multi-paires ?

Architecturalement oui — jusqu'à 8 positions simultanées. La concentration par symbole est limitée à 30%.

### Risque de corrélation croisée entre spreads ?

`SpreadCorrelationGuard` (ρ_max = 0.60) + `PCASpreadMonitor` actifs. Ces protections sont présentes mais n'ont pas de résultats documentés sur la réduction de drawdown.

### Effet de crowding potentiel ?

> 🟠 **MAJEUR — Univers de paires crypto sur Binance identique à tous les acteurs stat arb crypto :**  
> BTC/ETH, ETH/BNB, SOL/AVAX sont les paires "évidentes" testées par tous les fonds de stat arb crypto. En période de stress (liquidations DeFi, CeFi), toutes ces stratégies se débouclent simultanément, amplifiant les pertes. EDGECORE n'intègre aucune mesure de crowding ni aucun signal d'alerte sur le spread momentum d'un côté du livre d'ordres.

---

## 9. Failles critiques identifiées

### 🔴 Critique

| ID | Faille | Localisation | Impact |
|---|---|---|---|
| C-01 | `TRADING_DAYS_PER_YEAR = 252` sur actifs crypto (365j/an) → Sharpe surestimé de ~20% systématiquement | `backtests/metrics.py:11` | Illusion de performance — tous les Sharpe publiés sont faux |
| C-02 | `entry_time = datetime.now()` en backtest → time stop et duration-based features non fonctionnels dans toutes les simulations | `strategies/pair_trading.py` (generate_signals, active_trades dict) | Le time stop ne se déclenche jamais en backtest — positions zombie possibles |
| C-03 | Double OLS divergent : EG test utilise OLS normalisé, SpreadModel utilise OLS brut, jamais comparés — le β validé ≠ β tradé | `models/cointegration.py` + `models/spread.py` | La cointegration est validée sur une relation statistiquement différente de celle réellement tradée |
| C-04 | Bonferroni α ≈ 1e-5 avec ~100 symboles → zero pairs en marchés non-trending → stratégie silencieuse et non diagnostiquée comme telle | `strategies/pair_trading.py:_test_pair_cointegration` | Incapacité à générer des signaux sans détection explicite |
| C-05 | Aucun stop contre délisting surprise d'un leg (FTT, LUNA) → perte totale du leg sans gate | `strategies/pair_trading.py`, absence | Risque de perte catastrophique sans recours |

### 🟠 Majeur

| ID | Faille | Localisation | Impact |
|---|---|---|---|
| M-01 | Régime détecteur calcule volatilité depuis niveaux spread (approchant zéro) → régime HIGH artificiel, blocage d'entrées légitimes | `models/regime_detector.py:update()` | Classification de régime biaisée → sizing agressif sous-activé |
| M-02 | OOS re-validation utilise Bonferroni avec `num_symbols = len(unique_symbols_in_pairs)` — beaucoup moins strict que la découverte | `validation/oos_validator.py:__init__` | La validation OOS est moins rigoureuse que la découverte — faux sentiment de robustesse |
| M-03 | Volume 24h default à 1e9 USD → slippage quasi-nul pour Tier3/Tier4 altcoins | `backtests/cost_model.py:execution_cost_one_leg` | Coûts d'exécution sous-estimés de 10–100× sur altcoins peu liquides |
| M-04 | Aucun résultat de `ParameterCrossValidator` documenté — 12+ paramètres libres non validés par CV | `backtests/parameter_cv.py` | Sur-ajustement implicite à paramètres manuels |
| M-05 | Z-slope momentum filter sur 3 bars quotidiens = bruit statistique pur — rejette arbitrairement des entrées valides | `strategies/pair_trading.py:z_momentum_ok` | Dégradation du hit rate sans filtrage de qualité réel |
| M-06 | Fenêtres test walk-forward trop courtes (~25 barres/période avec 2 ans de données) — pas suffisant pour extrapoler statistiquement | `backtests/walk_forward.py:split_walk_forward` | Métriques OOS statistiquement non fiables |
| M-07 | Stress tests (`StressTestRunner`) implémentés mais aucun résultat enregistré ni intégré à la CI | `backtests/stress_testing.py` | Résilience aux scénarios extrêmes non démontrée |
| M-08 | Stop-loss positionnel 3% insuffisant pour altcoins crypto — ne protège pas contre une décorrélation légère ou un pump/dump | `backtests/strategy_simulator.py:max_position_loss_pct=0.03` | Faux sentiment de protection sur actifs à volatilité quotidienne 5–15% |

### 🟡 Mineur

| ID | Faille | Localisation | Impact |
|---|---|---|---|
| mn-01 | Sharpe sans risk-free rate (4.5%+ en 2023–2024) → surestimation ~0.5 point de Sharpe en absolu | `backtests/metrics.py:from_returns` | Performance apparente supérieure à la performance ajustée réelle |
| mn-02 | `include_funding=False` par défaut — coût de financement perpetuals non capturé | `backtests/cost_model.py` | Sous-estimation des coûts sur futures de 0.6% pour 20 jours de détention |
| mn-03 | Tier4 altcoins (PEPE, SHIB, FLOKI) élargissent l'univers mais génèrent quasi-aucune paire validée : gaspillage de tests Bonferroni et bruit statistique | `config/prod.yaml` | Bonferroni plus strict inutilement sur vraies paires |
| mn-04 | `ffill()` sur outliers peut créer prix fantômes pendant plusieurs barres et faux signals | `data/preprocessing.py` + `strategies/pair_trading.py` | Signal spurieux sur tokens ultra-volatils |
| mn-05 | `PartialProfitManager` initialisé dans `StrategyBacktestSimulator` mais jamais appelé explicitement dans la boucle de trade | `backtests/strategy_simulator.py` | Feature documentée mais ornementale — aucun partial profit réel |
>>>>>>> origin/main

---

## 10. Recommandations prioritaires

<<<<<<< HEAD
### Top 5 ÔÇö Corrections obligatoires avant paper trading

1. **[C-01] Corriger l'annualisation crypto**  
   `backtests/metrics.py` : `TRADING_DAYS_PER_YEAR = 365`. Appeler `set_trading_days(365)` au d├®marrage de tout backtest crypto. Tous les Sharpe publi├®s doivent ├¬tre recalcul├®s.

2. **[C-02] Fixer le time tracking en backtest**  
   Dans `generate_signals`, remplacer `datetime.now()` par le **timestamp de la derni├¿re barre** de `market_data` (ex : `market_data.index[-1]`). Propager ce timestamp ├á `TrailingStopManager` et `TimeStopManager`. Valider le time stop en test unitaire avec un timestep artificiel.

3. **[C-03] Unifier les deux OLS**  
   Soit utiliser le `beta_raw` produit par `engle_granger_test` directement pour initialiser `SpreadModel` (passer le r├®sultat EG au constructeur), soit ajouter un assert/test que `abs(beta_EG_raw - beta_SpreadModel) / beta_SpreadModel < 0.01`. L'├®cart doit ├¬tre document├® et contr├┤l├®.

4. **[M-03] Passer les volumes r├®els au CostModel**  
   Connecter le `LiquidityFilter` (qui maintient `avg_24h_volume` par symbol) au `CostModel.execution_cost_one_leg`. Supprimer la valeur par d├®faut `volume_24h=1e9`. Sans volume r├®el, les m├®triques de co├╗t sont fictives.

5. **[M-01] Corriger RegimeDetector sur spread levels**  
   Passer les **rendements du spread** (non les niveaux) ├á `RegimeDetector.update()`. Modifier `generate_signals` :  
   `spread_return = spread.diff().iloc[-1]` ÔåÆ `regime_state = self.regime_detector.update(spread=spread_return)`. Ou mieux : utiliser le Z-score lui-m├¬me comme proxy de volatilit├® (volatilit├® du Z-score = norme).

### Am├®liorations moyen terme

- Ex├®cuter `ParameterCrossValidator` sur donn├®es r├®elles et documenter les r├®sultats ÔÇö remplacer tous les param├¿tres manuels par les valeurs OOS-optimales
- Augmenter les p├®riodes de test walk-forward (utiliser 5+ ans de donn├®es ou r├®duire le nombre de fen├¬tres)
- Impl├®menter un monitoring du taux de d├®couverte de paires par r├®gime (indicateur op├®rationnel cl├®)
- Ajouter un "dry-run" test : v├®rifier que la strat├®gie d├®couvre > 0 paires sur les 6 derniers mois de donn├®es r├®elles
- Relier `PartialProfitManager` ou le supprimer du code (dead code)
- Exclure d├®finitivement les Tier4 meme coins de l'univers de cointegration (trop courts, trop ├®pisodiques)

### Optimisations avanc├®es

- Calibrer le seuil de stop-loss positionnel par actif (bas├® sur la volatilit├® historique du leg, pas fixe ├á 3%)
- Impl├®menter une alerte crowding bas├®e sur le d├®s├®quilibre du carnet d'ordres (OBI) ou la corr├®lation inter-spreads acc├®l├®r├®e
- Tester une sortie partielle (50% ├á Z=1.0, 50% ├á Z=0) -> limiter le "holding late" par s├®curit├®
- ├ëvaluer un r├®gime detector bas├® sur VIX crypto (BVIX) ou primes de futures pour d├®tecter les crises plus t├┤t

---

## 11. Score strat├®gique final

### Score qualit├® statistique : **5.5 / 10**

| Crit├¿re | Score |
|---|---|
| Test de cointegration (EG + Johansen + HAC) | 7/10 |
| Correction biais multiples (Bonferroni) | 6/10 |
| V├®rification I(1) avant EG | 8/10 |
| Rolling stationarity monitoring | 7/10 |
| Structural break detection | 7/10 |
| Coh├®rence EG ╬▓ vs SpreadModel ╬▓ | 2/10 |
| Annualisation correcte (Sharpe crypto) | 0/10 |
| Time tracking dans le backtest | 1/10 |
| Param├¿tres valid├®s par CV | 2/10 |
| Stress tests document├®s | 2/10 |

### Score robustesse r├®elle : **4.5 / 10**

| Crit├¿re | Score |
|---|---|
| Architecture walk-forward | 7/10 |
| S├®paration IS/OOS | 7/10 |
| Slippage et frais r├®alistes | 3/10 |
| Robustesse univers (Tier4 inclus) | 3/10 |
| Time stop fonctionnel | 1/10 |
| Survivorship bias contr├┤l├® | 4/10 |
| R├®gime d├®tecteur correct | 3/10 |
| R├®sultats empiriques document├®s | 0/10 |
| Stress test ex├®cut├®s | 1/10 |
| Scalabilit├® capital d├®mont├®e | 4/10 |

### Probabilit├® de survie 12 mois live

**< 35%** dans l'├®tat actuel ÔÇö estimation fond├®e sur :
- 3 bugs critiques (annualisation, time tracking, double OLS) qui invalidant les m├®triques de backtest pr├®sent├®es
- Aucun r├®sultat empirique sur donn├®es r├®elles document├® dans le d├®p├┤t
- Univers trop large, Bonferroni potentiellement st├®rile sur march├®s normaux
- Co├╗ts d'ex├®cution sous-estim├®s pour la majorit├® de l'univers

### Verdict clair

**­ƒæë Strat├®gie structurellement fragile ÔÇö non exploitable en l'├®tat pour du capital r├®el**

L'architecture de la strat├®gie est *intellectuellement solide* : les intentions sont correctes, les m├®canismes de protection sont nombreux, et le pipeline de d├®couverte de paires est rigoureux sur le papier. Mais trois erreurs structurelles dans l'impl├®mentation (annualisation, time tracking, double OLS) invalident les r├®sultats de backtest existants. Aucun run live ou paper trading document├® n'existe pour contrebalancer ces incertitudes.

**├ëtat recommand├® :** Appliquer les 5 corrections prioritaires ÔåÆ relancer un walk-forward complet sur donn├®es 2021ÔÇô2025 ÔåÆ exiger un Sharpe OOS ÔëÑ 1.0 (annualis├® 365j, sans risk-free) sur au moins 3 p├®riodes cons├®cutives ÔåÆ d├®ployer en paper trading avec un capital fictif de $50k pendant au minimum 60 jours calendaires ÔåÆ ├®valuer le taux de d├®couverte de paires hebdomadaire sur donn├®es live avant tout d├®ploiement r├®el.

**Avant correction des 5 items prioritaires : tol├®rance risque capital r├®el = z├®ro.**
=======
### Top 5 — Corrections obligatoires avant paper trading

1. **[C-01] Corriger l'annualisation crypto**  
   `backtests/metrics.py` : `TRADING_DAYS_PER_YEAR = 365`. Appeler `set_trading_days(365)` au démarrage de tout backtest crypto. Tous les Sharpe publiés doivent être recalculés.

2. **[C-02] Fixer le time tracking en backtest**  
   Dans `generate_signals`, remplacer `datetime.now()` par le **timestamp de la dernière barre** de `market_data` (ex : `market_data.index[-1]`). Propager ce timestamp à `TrailingStopManager` et `TimeStopManager`. Valider le time stop en test unitaire avec un timestep artificiel.

3. **[C-03] Unifier les deux OLS**  
   Soit utiliser le `beta_raw` produit par `engle_granger_test` directement pour initialiser `SpreadModel` (passer le résultat EG au constructeur), soit ajouter un assert/test que `abs(beta_EG_raw - beta_SpreadModel) / beta_SpreadModel < 0.01`. L'écart doit être documenté et contrôlé.

4. **[M-03] Passer les volumes réels au CostModel**  
   Connecter le `LiquidityFilter` (qui maintient `avg_24h_volume` par symbol) au `CostModel.execution_cost_one_leg`. Supprimer la valeur par défaut `volume_24h=1e9`. Sans volume réel, les métriques de coût sont fictives.

5. **[M-01] Corriger RegimeDetector sur spread levels**  
   Passer les **rendements du spread** (non les niveaux) à `RegimeDetector.update()`. Modifier `generate_signals` :  
   `spread_return = spread.diff().iloc[-1]` → `regime_state = self.regime_detector.update(spread=spread_return)`. Ou mieux : utiliser le Z-score lui-même comme proxy de volatilité (volatilité du Z-score = norme).

### Améliorations moyen terme

- Exécuter `ParameterCrossValidator` sur données réelles et documenter les résultats — remplacer tous les paramètres manuels par les valeurs OOS-optimales
- Augmenter les périodes de test walk-forward (utiliser 5+ ans de données ou réduire le nombre de fenêtres)
- Implémenter un monitoring du taux de découverte de paires par régime (indicateur opérationnel clé)
- Ajouter un "dry-run" test : vérifier que la stratégie découvre > 0 paires sur les 6 derniers mois de données réelles
- Relier `PartialProfitManager` ou le supprimer du code (dead code)
- Exclure définitivement les Tier4 meme coins de l'univers de cointegration (trop courts, trop épisodiques)

### Optimisations avancées

- Calibrer le seuil de stop-loss positionnel par actif (basé sur la volatilité historique du leg, pas fixe à 3%)
- Implémenter une alerte crowding basée sur le déséquilibre du carnet d'ordres (OBI) ou la corrélation inter-spreads accélérée
- Tester une sortie partielle (50% à Z=1.0, 50% à Z=0) -> limiter le "holding late" par sécurité
- Évaluer un régime detector basé sur VIX crypto (BVIX) ou primes de futures pour détecter les crises plus tôt

---

## 11. Score stratégique final

### Score qualité statistique : **5.5 / 10**

| Critère | Score |
|---|---|
| Test de cointegration (EG + Johansen + HAC) | 7/10 |
| Correction biais multiples (Bonferroni) | 6/10 |
| Vérification I(1) avant EG | 8/10 |
| Rolling stationarity monitoring | 7/10 |
| Structural break detection | 7/10 |
| Cohérence EG β vs SpreadModel β | 2/10 |
| Annualisation correcte (Sharpe crypto) | 0/10 |
| Time tracking dans le backtest | 1/10 |
| Paramètres validés par CV | 2/10 |
| Stress tests documentés | 2/10 |

### Score robustesse réelle : **4.5 / 10**

| Critère | Score |
|---|---|
| Architecture walk-forward | 7/10 |
| Séparation IS/OOS | 7/10 |
| Slippage et frais réalistes | 3/10 |
| Robustesse univers (Tier4 inclus) | 3/10 |
| Time stop fonctionnel | 1/10 |
| Survivorship bias contrôlé | 4/10 |
| Régime détecteur correct | 3/10 |
| Résultats empiriques documentés | 0/10 |
| Stress test exécutés | 1/10 |
| Scalabilité capital démontée | 4/10 |

### Probabilité de survie 12 mois live

**< 35%** dans l'état actuel — estimation fondée sur :
- 3 bugs critiques (annualisation, time tracking, double OLS) qui invalidant les métriques de backtest présentées
- Aucun résultat empirique sur données réelles documenté dans le dépôt
- Univers trop large, Bonferroni potentiellement stérile sur marchés normaux
- Coûts d'exécution sous-estimés pour la majorité de l'univers

### Verdict clair

**👉 Stratégie structurellement fragile — non exploitable en l'état pour du capital réel**

L'architecture de la stratégie est *intellectuellement solide* : les intentions sont correctes, les mécanismes de protection sont nombreux, et le pipeline de découverte de paires est rigoureux sur le papier. Mais trois erreurs structurelles dans l'implémentation (annualisation, time tracking, double OLS) invalident les résultats de backtest existants. Aucun run live ou paper trading documenté n'existe pour contrebalancer ces incertitudes.

**État recommandé :** Appliquer les 5 corrections prioritaires → relancer un walk-forward complet sur données 2021–2025 → exiger un Sharpe OOS ≥ 1.0 (annualisé 365j, sans risk-free) sur au moins 3 périodes consécutives → déployer en paper trading avec un capital fictif de $50k pendant au minimum 60 jours calendaires → évaluer le taux de découverte de paires hebdomadaire sur données live avant tout déploiement réel.

**Avant correction des 5 items prioritaires : tolérance risque capital réel = zéro.**
>>>>>>> origin/main
