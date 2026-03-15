# AUDIT STRAT├ëGIQUE EDGECORE ÔÇö V5
## Audit Complet, Critique et Actionnable de la Strat├®gie de Trading

**Date** : 2026-02-25  
**Auteur** : Senior Quant Researcher & Risk Architect  
**P├®rim├¿tre** : Strat├®gie de trading exclusivement ÔÇö validit├® statistique, g├®n├®ration de signaux, rigueur du backtesting, viabilit├® en conditions r├®elles  
**Tol├®rance ├á l'illusion statistique** : **Z├ëRO**

---

## Table des mati├¿res

1. [R├®sum├® ex├®cutif](#1-r├®sum├®-ex├®cutif)
2. [Fondation statistique](#2-fondation-statistique)
3. [G├®n├®ration de signaux](#3-g├®n├®ration-de-signaux)
4. [Backtesting ÔÇö Rigueur m├®thodologique](#4-backtesting--rigueur-m├®thodologique)
5. [Gestion des risques int├®gr├®e](#5-gestion-des-risques-int├®gr├®e)
6. [Mod├¿le de co├╗ts & frais r├®els](#6-mod├¿le-de-co├╗ts--frais-r├®els)
7. [Validit├® OOS & Walk-Forward](#7-validit├®-oos--walk-forward)
8. [Robustesse aux r├®gimes de march├®](#8-robustesse-aux-r├®gimes-de-march├®)
9. [Failles critiques & risques l├®taux](#9-failles-critiques--risques-l├®taux)
10. [Plan d'action prioris├®](#10-plan-daction-prioris├®)
11. [Verdict final](#11-verdict-final)

---

## 1. R├®sum├® ex├®cutif

EDGECORE est un syst├¿me d'arbitrage statistique par paires (*statistical arbitrage pair trading*) ciblant les actions am├®ricaines via Interactive Brokers. La strat├®gie repose sur la coint├®gration Engle-Granger, le calcul de hedge ratios par OLS/Kalman, la g├®n├®ration de signaux via Z-score adaptatif, et un cadre de backtesting walk-forward.

### Points forts confirm├®s
- Correction de Bonferroni c├óbl├®e pour les tests multiples de coint├®gration
- Consensus Newey-West HAC (OLS standard + HAC robuste) pour filtrer les faux positifs
- Filtre de Kalman pour le hedge ratio dynamique (╬▓ adaptatif barre-par-barre)
- Moniteur de stationnarit├® rolling (ADF bar-by-bar sur le spread actif)
- Walk-forward avec fen├¬tre expansive et validation OOS des paires
- Mod├¿le de co├╗ts r├®aliste 4-jambes (commission IBKR + slippage + emprunt short)
- Stress testing synth├®tique (flash crash, drawdown prolong├®, d├®corr├®lation, spike vol)
- Time stop, trailing stop, P&L stop, partial profit, spread correlation guard, PCA monitor

### R├®sum├® des s├®v├®rit├®s

| S├®v├®rit├® | Nombre | Description |
|----------|--------|-------------|
| ­ƒö┤ Critique | 5 | Menace directe sur le capital |
| ­ƒƒá Majeur | 8 | D├®gradation significative des performances |
| ­ƒƒí Mineur | 6 | Am├®liorations souhaitables |

---

## 2. Fondation statistique

### 2.1. Coint├®gration : Engle-Granger

**Impl├®mentation** : `models/cointegration.py`

Le test Engle-Granger suit la proc├®dure classique :
1. R├®gression OLS : $y = \alpha + \beta x + \varepsilon$
2. Test ADF sur les r├®sidus $\hat{\varepsilon}_t$
3. Rejet de $H_0$ (pas de coint├®gration) si $p < \alpha$

**Normalisation probl├®matique** ­ƒö┤ **CRITIQUE**

Le code normalise les s├®ries **avant** la r├®gression de coint├®gration :
```python
x_normalized = (x - x.mean()) / x.std()
y_normalized = (y - y.mean()) / y.std()
```
La normalisation (z-scoring) des niveaux de prix **avant** OLS est une erreur m├®thodologique. La coint├®gration teste une relation lin├®aire *en niveaux* : $y_t = \alpha + \beta x_t + \varepsilon_t$. En normalisant :
- Le $\beta$ estim├® n'a plus la signification de hedge ratio en unit├®s/dollars
- Le $\beta$ retourn├® par `engle_granger_test()` est un $\beta^*$ en unit├®s standardis├®es, **pas** le vrai hedge ratio exploitable
- L'ADF sur les r├®sidus normalis├®s reste valide (les r├®sidus sont invariants ├á la transformation affine), mais le `beta` retourn├® est inutilisable directement

**Impact** : Le `SpreadModel` recalcule ind├®pendamment un OLS sur les prix bruts (non normalis├®s), ce qui produit le ┬½ vrai ┬╗ $\beta$. Le syst├¿me poss├¿de un check de divergence (`beta_divergence_eg_vs_spread`) qui d├®tecte >5% de diff├®rence. Cependant :
1. Le $\beta$ retourn├® par `engle_granger_test()` est incoh├®rent avec celui du `SpreadModel`
2. La dualit├® $\beta_{\text{EG}}^*$ vs $\beta_{\text{spread}}$ cr├®e de la confusion et un risque d'usage incorrect en aval

**Correction Bonferroni** Ô£à

```python
if apply_bonferroni and num_symbols and num_symbols > 1:
    n_pairs = num_symbols * (num_symbols - 1) // 2
    alpha = 0.05 / max(n_pairs, 1)
```
Correctement impl├®ment├®e. Pour 50 symboles : $n = 1225$ paires ÔåÆ $\alpha_{\text{bonf}} = 4.08 \times 10^{-5}$. C'est tr├¿s conservateur ÔÇö attendu pour un univers de cette taille.

**Consensus Newey-West** Ô£à

La fonction `newey_west_consensus()` exige que *les deux* tests (standard et HAC-robuste) confirment la coint├®gration. C'est une bonne pratique pour filtrer les paires dont la significativit├® d├®pend de la structure d'autocorr├®lation des r├®sidus.

**V├®rification I(1)** ÔÜá´©Å ­ƒƒá **MAJEUR**

La fonction `verify_integration_order()` existe mais `check_integration_order=False` **par d├®faut** dans `engle_granger_test()`. Le test de coint├®gration Engle-Granger **exige** que les deux s├®ries soient I(1). Sans v├®rification :
- Deux s├®ries I(0) (stationnaires) peuvent produire un faux positif
- Une s├®rie I(2) peut produire des r├®sidus non-stationnaires m├¬me s'il existe une relation

Le fait que ce soit d├®sactiv├® par d├®faut est un trou m├®thodologique.

### 2.2. Half-life de mean-reversion

**Impl├®mentation** : `models/half_life_estimator.py`

Estimation AR(1) sur le spread centr├® :
$$\Delta S_t = \rho \cdot S_{t-1} + \varepsilon_t$$
$$\text{Half-life} = -\frac{\ln 2}{\ln \rho}$$

**Validation** : $5 \leq \text{HL} \leq 200$ jours. Bornes raisonnables pour les actions US.

**Probl├¿me** ­ƒƒí **MINEUR** : Le lookback par d├®faut est 252. Si les donn├®es sont insuffisantes (< 252 points), la fonction retourne `None` et le half-life est mis ├á 100 par d├®faut dans le legacy backtest runner. Ce d├®faut ├á 100 jours est potentiellement trop long pour un pair trading actif.

### 2.3. Test de Johansen

**Configuration** : `johansen_confirmation: true` dans `config.yaml`

Le flag est pr├®sent et transmis aux fonctions de discovery, mais **aucune impl├®mentation r├®elle du test de Johansen n'existe dans le code**. Le flag `johansen_flag` est re├ºu par `_test_pair_cointegration()` mais jamais utilis├® dans le corps de la fonction.

­ƒö┤ **CRITIQUE** ÔÇö Le test de Johansen, d├®clar├® comme ┬½ confirmation ┬╗ du test Engle-Granger, n'est pas impl├®ment├®. C'est un **faux sentiment de s├®curit├®** : la configuration sugg├¿re une validation crois├®e qui n'existe pas.

---

## 3. G├®n├®ration de signaux

### 3.1. Dual Signal Path ÔÇö Divergence Architecturale

Il existe **deux** g├®n├®rateurs de signaux ind├®pendants :

| Composant | Fichier | Utilis├® par |
|-----------|---------|-------------|
| `PairTradingStrategy.generate_signals()` | `strategies/pair_trading.py` | `StrategyBacktestSimulator`, `EventDrivenBacktester`, legacy `BacktestRunner` |
| `SignalGenerator.generate()` | `signal_engine/generator.py` | `live_trading/runner.py` (live pipeline) |

­ƒö┤ **CRITIQUE** ÔÇö Ces deux chemins produisent des signaux de mani├¿re **diff├®rente** :

| Caract├®ristique | `PairTradingStrategy` | `SignalGenerator` |
|-----------------|----------------------|-------------------|
| Spread model | Cr├®e un **nouveau** `SpreadModel` ├á chaque appel de `generate_signals()` | **R├®utilise** le `SpreadModel` existant via `update()` (pr├®serve l'├®tat Kalman) |
| Stationnarit├® | ÔØî Aucune v├®rification | Ô£à Rolling ADF via `StationarityMonitor` |
| R├®gime | ÔØî Non utilis├® pour le signal | Ô£à `RegimeDetector` + seuils adaptatifs |
| Seuils | Fixe : `config.entry_z_score` (1.0) | Adaptatifs : volatilit├® + half-life + r├®gime |
| Z-score lookback | Fixe : 20 | Adaptatif via half-life |
| Signal type | `Signal(symbol_pair=..., side=..., strength=..., reason=...)` | `Signal(pair_key=..., side=..., strength=..., z_score=..., regime=...)` |
| Objet Signal | `strategies.base.Signal` (4 champs) | `signal_engine.generator.Signal` (10 champs) |

**Cons├®quence directe** : Le backtesting (`StrategyBacktestSimulator`) utilise `PairTradingStrategy.generate_signals()` qui :
1. Ne v├®rifie **pas** la stationnarit├® du spread
2. N'applique **pas** de seuils adaptatifs
3. Recr├®e un `SpreadModel` frais ├á chaque barre ÔåÆ perd l'├®tat Kalman
4. Utilise un lookback Z-score fixe de 20 au lieu d'adaptatif

Le live trading utilise `SignalGenerator.generate()` qui fait tout cela correctement.

**R├®sultat** : Le backtest ne reproduit PAS les signaux du live. Les m├®triques de backtest sont **non repr├®sentatives** du comportement en production.

### 3.2. Z-Score : Calcul et bornage

**Formule** :
$$Z_t = \frac{S_t - \bar{S}_w}{\sigma_{S,w} + 10^{-8}}$$

o├╣ $w$ est le lookback adaptatif.

**Bornage** : $Z \in [-6, +6]$ (clamp). Acceptable pour ├®viter les aberrations.

**Lookback adaptatif** (dans `SpreadModel.compute_z_score()` et `ZScoreCalculator`) :

$$\text{multiplier} = \begin{cases} 3.0 & \text{si HL} \leq 10 \\ 3.0 - 2.0 \cdot \frac{\text{HL} - 10}{50} & \text{si } 10 < \text{HL} \leq 60 \\ 1.0 & \text{si HL} > 60 \end{cases}$$

$$\text{lookback} = \min(\lceil \text{multiplier} \times \text{HL} \rceil, 60)$$

La logique est coh├®rente entre `SpreadModel`, `DynamicSpreadModel` et `ZScoreCalculator`. Ô£à

### 3.3. Seuils d'entr├®e et sortie

**Config** : `entry_z_score: 1.0`, `exit_z_score: 0.5`

­ƒƒá **MAJEUR** ÔÇö Un seuil d'entr├®e de 1.0¤â est **tr├¿s agressif** pour le pair trading actions US. La litt├®rature acad├®mique standard utilise typiquement 2.0¤â. Avec 1.0¤â :
- ~31.7% de chance qu'un spread normalement distribu├® d├®passe naturellement ┬▒1¤â
- Le ratio signal/bruit est faible ÔåÆ beaucoup de faux signaux
- Les co├╗ts de transaction (m├¬me ~4 bps aller-retour) mangent le PnL sur des excursions faibles

Le seuil adaptatif du `SignalGenerator` (base 2.0 ┬▒ ajustements) est plus raisonnable, mais il n'est **pas utilis├® en backtest**.

L'`exit_z_score: 0.5` implique qu'on ne sort que quand le Z repasse sous 0.5, ce qui est raisonnable mais laisse du P&L sur la table vs un exit ├á 0.

### 3.4. Force du signal (strength)

$$\text{strength} = \min\left(\frac{|Z|}{3.0}, 1.0\right)$$

Utilis├® pour le sizing mais la logique est identique entre les deux paths. Maximum ├á $Z = 3.0$. Correct.

---

## 4. Backtesting ÔÇö Rigueur m├®thodologique

### 4.1. Architecture du backtester

Trois backtesteurs existent :

| Backtester | Fichier | Statut |
|------------|---------|--------|
| `BacktestRunner.run()` (legacy) | `backtests/runner.py` | ÔÜá´©Å **D├®pr├®ci├®** ÔÇö contient un look-ahead bias (C-02) |
| `StrategyBacktestSimulator` | `backtests/strategy_simulator.py` | Ô£à Recommand├® ÔÇö causal bar-by-bar |
| `EventDrivenBacktester` | `backtests/event_driven.py` | Ô£à Avanc├® ÔÇö simulation carnet d'ordres |

Le `StrategyBacktestSimulator` (Sprint 1.1) est correctement causal :
- Fen├¬tre expansive : `hist_prices = prices_df.iloc[:bar_idx + 1]`
- Lookback minimum : 60 barres
- Pas de look-ahead dans la g├®n├®ration de signaux Ô£à
- Paires red├®couvertes p├®riodiquement avec donn├®es strictement in-sample Ô£à

### 4.2. Calcul du P&L

Le P&L est calcul├® par jambe :

$$\text{PnL}_{\text{long}} = \frac{P_1^{exit} - P_1^{entry}}{P_1^{entry}} \cdot \text{notional}_{\text{leg}} + \frac{P_2^{entry} - P_2^{exit}}{P_2^{entry}} \cdot \text{notional}_{\text{leg}}$$

Les co├╗ts sont correctement d├®compos├®s :
- `entry_cost` : frais des 2 jambes ├á l'ouverture
- `exit_cost` : frais des 2 jambes ├á la fermeture
- `holding_cost` : emprunt de la jambe short (quotidien)
- `funding_cost` : financement marge (d├®sactiv├® pour equities) Ô£à

### 4.3. Look-ahead bias r├®siduel

­ƒƒá **MAJEUR** ÔÇö Le legacy `BacktestRunner.run()` contient un look-ahead bias explicite :
```python
cointegrated_pairs = self._find_cointegrated_pairs_in_data(prices_df)  # uses FULL data
```
Ce runner est marqu├® `DeprecationWarning` mais **n'est pas supprim├®** et reste appelable. Il devrait ├¬tre compl├¿tement ├®limin├® du codebase pour ├®viter toute utilisation accidentelle.

### 4.4. Allocation et sizing

**Base** : 30% du portefeuille par paire (`allocation_per_pair_pct: 30.0`)

­ƒƒá **MAJEUR** ÔÇö 30% par paire est **extr├¬mement concentr├®** pour un portefeuille de pair trading. Avec un max de 10 positions simultan├®es, l'exposition totale th├®orique est de 300% ÔÇö largement au-del├á du levier max configur├® (2.0x).

Le code applique ensuite :
- Quality multiplier : [0.5, 1.5] bas├® sur p-value + half-life
- Volatility sizing : [0.4, 1.5] inverse-vol
- Floor combin├® : minimum 50% de l'allocation de base
- Portfolio heat limit : 95%

L'interaction de ces multiplicateurs avec le 30% de base et le heat limit devrait ├¬tre valid├®e empiriquement. Un pair ├á forte conviction peut recevoir 30% ├ù 1.5 ├ù 1.5 = 67.5% du portefeuille, limit├® seulement par le heat limit de 95%.

### 4.5. Mark-to-Market

Ô£à Le `StrategyBacktestSimulator` calcule correctement le MtM :
- Delta unrealised P&L calcul├® chaque barre
- Ajout├® au portfolio avec le realized P&L
- Portfolio drawdown circuit breaker ├á 15%

---

## 5. Gestion des risques int├®gr├®e

### 5.1. Architecture des limites

EDGECORE dispose de **trois couches** de risk management :

| Couche | Composant | Scope |
|--------|-----------|-------|
| Strat├®gie | `PairTradingStrategy._check_internal_risk_limits()` | Max positions (50), max trades/jour (200), max DD (20%) |
| Risk Engine | `risk/engine.py` ÔåÆ `RiskEngine` | Max positions (10), risk/trade (0.5%), perte cons├®cutive (5), DD quotidien (2%), levier (2x) |
| Portfolio Risk | `risk_engine/portfolio_risk.py` ÔåÆ `PortfolioRiskManager` | DD portfolio (15%), perte quotidienne (3%), heat (95%) |

­ƒƒí **MINEUR** ÔÇö La couche strat├®gie a des limites internes (50 positions, 200 trades/jour, 20% DD) qui sont **beaucoup plus l├óches** que les limites du `RiskEngine` (10 positions, 2% daily loss, 10% DD). Bien que ce soit du ┬½ defense in depth ┬╗, les limites strat├®gie ne seront jamais atteintes si le RiskEngine fonctionne correctement ÔåÆ code mort effectif.

### 5.2. Kill Switch

`risk_engine/kill_switch.py` ÔÇö persistance fichier JSON (`data/kill_switch_state.json`).

D├®clenche sur :
- DD portfolio > 15%
- Perte quotidienne > 3%
- Pertes cons├®cutives ÔëÑ 5
- Vol extr├¬me > 4¤â
- Donn├®es stales > 300s

Ô£à Bonne impl├®mentation. Le kill switch n├®cessite un `manual_reset()` ÔÇö pas d'auto-resume.

### 5.3. Time Stop

```python
max_holding_bars = min(2 * half_life, cap)  # cap = 60 jours
```

Si HL = 25 jours ÔåÆ arr├¬t forc├® apr├¿s 50 jours. Raisonnable.

### 5.4. Trailing Stop (Phase 5)

Activation ├á 1.5% de profit, trail ├á 1.0% depuis le pic. Pour un pair trading equity, les moves attendus sont typiquement faibles (2-5%). Un trailing qui s'active ├á 1.5% et traile ├á 1.0% va :
- S'activer rapidement
- Couper des positions rentables pr├®matur├®ment

­ƒƒí **MINEUR** ÔÇö Les param├¿tres du trailing stop semblent trop serr├®s pour la volatilit├® typique du pair trading actions US.

### 5.5. Spread Correlation Guard

`risk/spread_correlation.py` ÔÇö rejette les entr├®es dont le spread est corr├®l├® > seuil (¤ü_max = 0.60) avec les positions existantes.

Ô£à Excellente protection contre le risque de concentration factorielle. Compl├®t├® par le PCA Monitor.

### 5.6. Drawdown circuit breaker

`StrategyBacktestSimulator` : si le drawdown portfolio d├®passe 15%, toutes les positions sont ferm├®es et le trading est suspendu pendant 10 barres.

Ô£à C├óbl├® correctement dans le backtester et la couche risk. Apr├¿s le cooldown, le trading reprend ÔÇö ce qui pourrait ├¬tre probl├®matique si les conditions n'ont pas chang├®.

---

## 6. Mod├¿le de co├╗ts & frais r├®els

### 6.1. Param├¿tres configur├®s

| Composant | Valeur | R├®aliste? |
|-----------|--------|-----------|
| Commission taker | 2.0 bps | Ô£à IBKR Pro tiered ~1.5-2.5 bps |
| Commission maker | 1.5 bps | Ô£à IBKR rebates |
| Slippage base | 2.0 bps | Ô£à Large-cap US equity |
| Emprunt short | 0.5% annuel | Ô£à General collateral ETB rate |
| Impact march├® | Volume-adaptatif | Ô£à `base + 100 ├ù participation` bps |
| Financement marge | 0.0 bps/jour | Ô£à Non applicable equities cash |

**Note importante** : Ce mod├¿le est calibr├® pour des **actions US via IBKR**, PAS pour des cryptomonnaies. Les frais Binance ne sont pas pertinents ici.

### 6.2. Co├╗t aller-retour estim├®

Pour un pair trade de $5,000/jambe ($10K total) avec holding moyen de 25 jours :
- Entry : 2 ├ù 5000 ├ù (2.0 + 2.0) / 10000 = **$4.00**
- Exit : **$4.00**
- Emprunt : 5000 ├ù 0.005 / 365 ├ù 25 = **$1.71**
- **Total** : ~$9.71 Ôëê **9.7 bps** du notional total

### 6.3. Seuil de rentabilit├® ZCE (Zero-Cost Entry)

Pour que le trade soit profitable apr├¿s co├╗ts :
$$|Z_{\text{entr├®e}}| - |Z_{\text{sortie}}| > \frac{\text{co├╗t RT en } \sigma}{\sigma_{spread}}$$

Avec un co├╗t RT de ~10 bps et une vol spread typique de ~200 bps/jour :
$$\Delta Z_{\text{min}} \approx 0.05\sigma$$

Ceci est facilement atteignable avec $Z_{entry} = 1.0$ et $Z_{exit} = 0.5$. Le mod├¿le de co├╗ts n'est **pas** le facteur limitant. Ô£à

### 6.4. Emprunt hard-to-borrow

­ƒƒí **MINEUR** ÔÇö Le mod├¿le utilise un taux d'emprunt fixe de 0.50% annuel. Certaines actions (small-cap, forte demande short) peuvent avoir des taux de 5-50%+ annualis├®. Le filtre de liquidit├® (`LiquidityFilter`) existe mais ne v├®rifie pas la disponibilit├®/co├╗t de l'emprunt.

---

## 7. Validit├® OOS & Walk-Forward

### 7.1. Impl├®mentation Walk-Forward

`backtests/walk_forward.py` ÔåÆ `WalkForwardBacktester`

**Caract├®ristiques** :
- Fen├¬tre expansive (pas rolling) : chaque p├®riode d'entra├«nement commence ├á t=0 Ô£à
- Nombre de p├®riodes configurable (d├®faut : 6)
- Ratio OOS : 20%
- Paires d├®couvertes sur IS uniquement Ô£à
- Validation OOS optionnelle des paires avant trading Ô£à
- Instance de strat├®gie fra├«che par p├®riode (pas de fuite d'├®tat) Ô£à
- Cache d├®sactiv├® en walk-forward Ô£à

### 7.2. Agr├®gation des m├®triques

Le Sharpe ratio agr├®g├® est calcul├® sur les rendements **concat├®n├®s** (pas la moyenne des Sharpe par p├®riode) :

$$SR_{\text{agg}} = \frac{\bar{r}_{\text{concat}}}{\sigma_{r_{\text{concat}}}} \times \sqrt{252}$$

C'est statistiquement correct. Ô£à

Le Sortino est aussi calcul├® sur les rendements concat├®n├®s avec le downside deviation. Ô£à

### 7.3. Validation OOS des paires

Quand `validate_pairs_oos=True` :
1. Le train set est subdivis├® en IS (80%) et OOS validation (20%)
2. Les paires sont d├®couvertes sur IS
3. Les paires sont **valid├®es** sur l'OOS validation slice
4. Seules les paires valid├®es sont trad├®es sur le vrai OOS test set

­ƒƒá **MAJEUR** ÔÇö La m├®thode `validate_pairs_oos()` est **appel├®e** dans le walk-forward mais son impl├®mentation **n'est pas visible** dans les fichiers lus. Si elle n'existe pas dans `PairTradingStrategy`, l'appel provoquera une `AttributeError` en runtime. Cela doit ├¬tre v├®rifi├®.

### 7.4. Absence de netting/combining des P&L walks

Le walk-forward agr├¿ge les rendements des p├®riodes mais ne calcule pas :
- La d├®gradation du Sharpe ratio entre IS et OOS (┬½ Sharpe decay ┬╗)
- Le ratio de performance OOS/IS pour d├®tecter l'overfitting
- La stabilit├® des paires valid├®es d'une p├®riode ├á l'autre

­ƒƒá **MAJEUR** ÔÇö Sans ces m├®triques, il est impossible de diagnostiquer si la strat├®gie est overfitt├®e aux donn├®es d'entra├«nement.

---

## 8. Robustesse aux r├®gimes de march├®

### 8.1. D├®tection de r├®gime

`models/regime_detector.py` ÔåÆ `RegimeDetector`

Classification par percentile de volatilit├® rolling :
- LOW : vol < percentile 33
- NORMAL : entre 33 et 67
- HIGH : vol > percentile 67

**Transition** : respecte `min_regime_duration` (1 barre par d├®faut) sauf pour les spikes > 99e percentile (transition instantan├®e).

­ƒƒí **MINEUR** ÔÇö La d├®tection de r├®gime est bas├®e sur la volatilit├® du **spread**, pas sur le march├® global (VIX, corr├®lation cross-sectorielle). Un spread peut avoir une vol faible alors que le march├® est en crise (corr├®lation breakdown ÔåÆ spreads s'effondrent puis explosent). L'ajout d'un indicateur macro (VIX feed, market-wide dispersion) renforcerait la robustesse.

### 8.2. Utilisation du r├®gime

Le r├®gime est d├®tect├® mais **diff├®remment exploit├®** selon le chemin :

| Chemin | Position sizing | Entry threshold | Exit threshold |
|--------|----------------|-----------------|----------------|
| `PairTradingStrategy` (backtest) | Aucun ajustement | Aucun ajustement | Aucun ajustement |
| `SignalGenerator` (live) | Via `RegimeDetector.get_position_multiplier()` | Via `AdaptiveThresholdEngine` | Via `AdaptiveThresholdEngine` |

­ƒö┤ **CRITIQUE** ÔÇö En backtest, le r├®gime n'affecte **rien**. Le `StrategyBacktestSimulator` applique un `_volatility_sizing_multiplier` bas├® sur la vol du spread (pas le r├®gime d├®tect├®), mais les seuils d'entr├®e restent fix├®s ├á `config.entry_z_score = 1.0`. Tout le travail fait sur les seuils adaptatifs et la d├®tection de r├®gime est **non test├®** par le backtester principal.

### 8.3. Stress testing

`backtests/stress_testing.py` ÔåÆ `StressTestRunner`

8 sc├®narios synth├®tiques :
1. Flash crash -20% (mod├®r├®) / -40% (s├®v├¿re)
2. Bear prolong├® -15% (60 barres) / -30% (90 barres)
3. D├®corr├®lation 30/60 barres
4. Spike vol 3x/5x

Ô£à Infrastructure correcte. Cependant :

­ƒƒí **MINEUR** ÔÇö Les sc├®narios de stress appliquent des chocs **identiques ├á toutes les colonnes** (sauf la d├®corr├®lation). Dans un vrai stress, les paires r├®agissent de mani├¿re **asym├®trique** (flight to quality, rotation sectorielle). Un sc├®nario de divergence intra-paire serait plus pertinent pour le pair trading.

---

## 9. Failles critiques & risques l├®taux

### ­ƒö┤ F-01 : Divergence Backtest Ôåö Live (LETHAL)

**Fichiers** : `strategies/pair_trading.py` vs `signal_engine/generator.py`

Le chemin de signal du backtest (`PairTradingStrategy.generate_signals()`) ne reproduit pas le comportement du live (`SignalGenerator.generate()`). Les seuils adaptatifs, la stationnarit├® rolling, et le r├®gime sont absents du backtest.

**Impact** : Les m├®triques de backtest (Sharpe, DD, win rate) sont **non repr├®sentatives** du comportement r├®el. Un Sharpe de 1.5 en backtest peut ├¬tre 0.5 ou -0.3 en live.

**Action** : Refactorer `StrategyBacktestSimulator` pour utiliser `SignalGenerator.generate()` comme unique source de signaux, identique au live.

### ­ƒö┤ F-02 : Normalisation pr├®-OLS dans Engle-Granger

**Fichier** : `models/cointegration.py:168-169`

La normalisation z-score des prix avant OLS produit un ╬▓ non-exploitable en unit├®s de prix. Le `SpreadModel` recalcule son propre ╬▓ sur les prix bruts, cr├®ant une divergence permanente.

**Action** : Supprimer la normalisation dans `engle_granger_test()`. L'OLS doit op├®rer sur les prix bruts. Alternatively, normaliser uniquement pour stabilit├® num├®rique APR├êS le calcul du ╬▓, ou utiliser `np.linalg.lstsq(rcond=None)` qui g├¿re d├®j├á le conditionnement.

### ­ƒö┤ F-03 : Johansen non impl├®ment├® mais configur├®

**Fichier** : `config/config.yaml` ÔåÆ `johansen_confirmation: true`

Le test de Johansen est d├®clar├® comme actif mais le code ne contient aucune impl├®mentation. Le flag est transmis mais ignor├® silencieusement.

**Action** : Soit (a) impl├®menter le test de Johansen via `statsmodels.tsa.vector_ar.vecm.coint_johansen`, soit (b) retirer le flag de la config et documenter que seul Engle-Granger est utilis├®.

### ­ƒö┤ F-04 : SpreadModel recr├®├® ├á chaque barre (backtest)

**Fichier** : `strategies/pair_trading.py:600-601`

```python
model = SpreadModel(y, x)
self.spread_models[pair_key] = model
```

├Ç chaque appel de `generate_signals()`, un *nouveau* `SpreadModel` est cr├®├®, ├®crasant le pr├®c├®dent. Cons├®quences :
- L'├®tat Kalman (si `DynamicSpreadModel` avec Kalman) est perdu
- Le `HedgeRatioTracker` voit chaque initialisation comme une ┬½ premi├¿re fois ┬╗
- Les ╬▓eta driftent silencieusement sans que le tracker ne les d├®tecte

Le `SignalGenerator` (live) fait correctement `model.update(y, x)` pour pr├®server l'├®tat.

**Action** : Dans `generate_signals()`, r├®utiliser le mod├¿le existant si `pair_key` est d├®j├á dans `self.spread_models`, et appeler `model.update(y, x)` au lieu de recr├®er.

### ­ƒö┤ F-05 : Entry Z-score 1.0¤â trop agressif

**Fichier** : `config/config.yaml` ÔåÆ `entry_z_score: 1.0`

Avec un seuil ├á 1.0¤â et un exit ├á 0.5¤â, le profit brut par trade est ~0.5¤â. Pour un spread avec une vol quotidienne de ~100 bps, cela fait ~50 bps de profit brut. Apr├¿s ~10 bps de co├╗ts RT, le profit net est ~40 bps. Cependant :

- La probabilit├® que le spread revienne ├á la moyenne AVANT de continuer ├á diverger est non-triviale ├á 1.0¤â
- Le ratio win/loss sera d├®grad├® par les faux signaux
- En r├®gime de haute vol, 1.0¤â est du bruit

Ce seul param├¿tre peut transformer une strat├®gie profitable en strat├®gie perdante dans les mauvais r├®gimes.

**Action** : Augmenter `entry_z_score` ├á 2.0 (standard) et utiliser les seuils adaptatifs du `SignalGenerator` dans le backtester pour validation.

---

### ­ƒƒá F-06 : Allocation 30% par paire

**Fichier** : `backtests/strategy_simulator.py` ÔåÆ `allocation_per_pair_pct: 30.0`

Concentration excessive. Maximum th├®orique : 300% d'exposition (10 paires ├ù 30%). M├¬me avec le heat limit ├á 95%, trois paires peuvent consommer l'int├®gralit├® du budget.

### ­ƒƒá F-07 : verify_integration_order d├®sactiv├® par d├®faut

**Fichier** : `models/cointegration.py` ÔåÆ `check_integration_order: bool = False`

Le test I(1) n'est pas ex├®cut├® sauf si explicitement demand├®. Aucun appelant ne le demande.

### ­ƒƒá F-08 : Legacy BacktestRunner avec look-ahead bias toujours pr├®sent

**Fichier** : `backtests/runner.py` ÔåÆ `BacktestRunner.run()`

Marqu├® d├®pr├®ci├® mais toujours importable et utilisable. Risque d'utilisation accidentelle.

### ­ƒƒá F-09 : Sharpe decay non mesur├® dans le walk-forward

**Fichier** : `backtests/walk_forward.py` ÔåÆ `_aggregate_metrics()`

Pas de calcul du ratio IS performance / OOS performance.

### ­ƒƒá F-10 : validate_pairs_oos potentiellement absent

**Fichier** : `backtests/walk_forward.py:207` ÔåÆ `strategy.validate_pairs_oos(...)`

Appel ├á une m├®thode qui n'est pas visible dans `strategies/pair_trading.py`. Risque d'erreur runtime.

### ­ƒƒá F-11 : Seuils adaptatifs non test├®s en backtest

**Fichier** : `signal_engine/adaptive.py` ÔÇö Le code est mature mais jamais ex├®cut├® par le chemin de backtesting standard.

### ­ƒƒá F-12 : RegimeDetector bas├® uniquement sur vol spread

**Fichier** : `models/regime_detector.py` ÔÇö Aucun input macro (VIX, market correlation, dispersion).

### ­ƒƒá F-13 : model_retraining utilise cl├® 'p_value' au lieu de 'adf_pvalue'

**Fichier** : `models/model_retraining.py:282`

```python
p_value = eg_result['p_value']
```

Le r├®sultat de `engle_granger_test()` retourne `'adf_pvalue'`, pas `'p_value'`. Ceci provoquera un `KeyError` en runtime, rendant la red├®couverte de paires dans `ModelRetrainingManager` inop├®rante.

---

## 10. Plan d'action prioris├®

### Sprint imm├®diat (avant tout d├®ploiement de capital)

| # | S├®v├®rit├® | Action | Fichiers | Effort |
|---|----------|--------|----------|--------|
| 1 | ­ƒö┤ | Unifier le signal path : remplacer `PairTradingStrategy.generate_signals()` par `SignalGenerator.generate()` dans `StrategyBacktestSimulator` | `backtests/strategy_simulator.py`, `strategies/pair_trading.py` | 2-3 jours |
| 2 | ­ƒö┤ | Supprimer la normalisation z-score dans `engle_granger_test()` ÔÇö OLS sur prix bruts | `models/cointegration.py` | 0.5 jour |
| 3 | ­ƒö┤ | Impl├®menter le test de Johansen OU retirer le flag de config | `models/cointegration.py`, `config/config.yaml` | 1-2 jours |
| 4 | ­ƒö┤ | Corriger `generate_signals()` pour r├®utiliser le SpreadModel existant (comme le ligne `SignalGenerator`) | `strategies/pair_trading.py` | 0.5 jour |
| 5 | ­ƒö┤ | Augmenter `entry_z_score` de 1.0 ├á 2.0 (ou c├óbler les seuils adaptatifs dans le backtest) | `config/config.yaml` | 0.5 jour |

### Sprint suivant (semaine 2)

| # | S├®v├®rit├® | Action | Fichiers | Effort |
|---|----------|--------|----------|--------|
| 6 | ­ƒƒá | Activer `check_integration_order=True` par d├®faut | `models/cointegration.py` | 0.5 jour |
| 7 | ­ƒƒá | R├®duire `allocation_per_pair_pct` ├á 10-15% | `backtests/strategy_simulator.py`, `config/config.yaml` | 0.5 jour |
| 8 | ­ƒƒá | Supprimer `BacktestRunner.run()` legacy | `backtests/runner.py` | 0.5 jour |
| 9 | ­ƒƒá | Ajouter Sharpe IS/OOS ratio dans walk-forward | `backtests/walk_forward.py` | 1 jour |
| 10 | ­ƒƒá | V├®rifier/impl├®menter `validate_pairs_oos()` | `strategies/pair_trading.py` | 1 jour |
| 11 | ­ƒƒá | Fixer `model_retraining.py` : `'p_value'` ÔåÆ `'adf_pvalue'` | `models/model_retraining.py` | 0.5 jour |

### Am├®liorations (semaine 3-4)

| # | S├®v├®rit├® | Action | Fichiers | Effort |
|---|----------|--------|----------|--------|
| 12 | ­ƒƒí | Ajouter feed VIX/dispersion au RegimeDetector | `models/regime_detector.py` | 2 jours |
| 13 | ­ƒƒí | V├®rifier disponibilit├® emprunt (ETB/HTB screening) | `data/liquidity_filter.py` | 1 jour |
| 14 | ­ƒƒí | Stress tests asym├®triques intra-paire | `backtests/stress_testing.py` | 1 jour |
| 15 | ­ƒƒí | Ajuster trailing stop (activation 2.5%, trail 1.5%) | `config/config.yaml` | 0.5 jour |
| 16 | ­ƒƒí | Half-life default 100 ÔåÆ 40 quand estimation ├®choue | `backtests/runner.py` | 0.5 jour |

---

## 11. Verdict final

### La strat├®gie est-elle d├®ployable en production avec du capital r├®el ?

# ÔØî NON ÔÇö EN L'├ëTAT ACTUEL

### Raisons :

1. **Divergence backtest/live non r├®solue** : Le signal path du backtester (`PairTradingStrategy.generate_signals()`) ne refl├¿te pas le comportement du live (`SignalGenerator.generate()`). Les seuils adaptatifs, la v├®rification de stationnarit├®, et le r├®gime sont absents du backtest. **Toute m├®trique de backtest est non fiable.**

2. **Seuil d'entr├®e trop agressif (1.0¤â)** : La majorit├® des trades ├á ce seuil sont du bruit, surtout dans les r├®gimes de haute volatilit├®. Le ratio signal/bruit est insuffisant pour compenser les co├╗ts de transaction et le risque d'ex├®cution.

3. **Normalisation OLS corrompant le ╬▓** : Le hedge ratio estim├® par `engle_granger_test()` est en unit├®s standardis├®es, pas en dollars. Le `SpreadModel` corrige cela ind├®pendamment, mais la dualit├® cr├®e un risque syst├®mique de confusion.

4. **Johansen fant├┤me** : Le flag `johansen_confirmation: true` active une s├®curit├® qui n'existe pas. Le code ignore silencieusement le flag.

5. **Concentration excessive (30%/paire)** : Un seul pair trade malheureux peut impacter 30% du portefeuille.

### Conditions pour d├®ploiement :

Le syst├¿me peut devenir d├®ployable apr├¿s r├®solution des 5 items critiques (Sprint imm├®diat, ~5-7 jours de d├®veloppement) et validation walk-forward avec le signal path unifi├® montrant :
- Sharpe ratio OOS ÔëÑ 1.0
- Max drawdown OOS Ôëñ 15%
- Ratio Sharpe OOS/IS ÔëÑ 0.60 (Ôëñ40% de d├®gradation)
- Win rate ÔëÑ 50%
- Profit factor ÔëÑ 1.3
- Survie ├á tous les sc├®narios de stress

### Score global

| Dimension | Score | Commentaire |
|-----------|-------|-------------|
| Fondation statistique | 6/10 | Bonferroni + NW-HAC Ô£à mais normalisation OLS + Johansen absent |
| G├®n├®ration de signaux | 4/10 | Dual path non unifi├® ÔÇö faille architecturale |
| Backtesting | 7/10 | Walk-forward correct mais utilise le mauvais signal path |
| Risk management | 8/10 | Multicouche, kill switch persistant, circuit breakers |
| Mod├¿le de co├╗ts | 9/10 | R├®aliste, IBKR-calibr├®, 4 jambes |
| Robustesse r├®gime | 5/10 | D├®tecteur ok mais non c├óbl├® dans le backtest |
| Stress testing | 7/10 | Infrastructure solide, sc├®narios ├á enrichir |
| **Score global** | **6.3/10** | **Non d├®ployable sans corrections critiques** |

---

*Fin de l'audit strat├®gique EDGECORE V5*

*Ce document doit ├¬tre trait├® comme confidentiel. Les findings d├®crits constituent des risques r├®els pour le capital en gestion. Aucun capital ne doit ├¬tre d├®ploy├® tant que les items ­ƒö┤ ne sont pas r├®solus et valid├®s.*
