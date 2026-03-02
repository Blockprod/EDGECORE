# AUDIT STRATÉGIQUE — EDGECORE

> **Date :** 22 février 2026 | **Version :** V4 — audit complet avec corrections V3 et nouvelles failles  
> **Base :** code source intégral analysé ligne par ligne, zéro supposition  
> **Périmètre :** stratégie, signaux, cointegration, spread, backtest, walk-forward, OOS, risk engine  
> **Capital cible : réel. Tolérance illusion statistique : zéro.**

---

## 1. Nature réelle de la stratégie

### Description exacte inférée depuis le code

EDGECORE est une stratégie de **statistical arbitrage bivariée** basée sur la mean reversion de spreads cointégrés sur paires de cryptomonnaies Binance (marché spot/perpetuals). Le pipeline complet tel que codé :

1. **Découverte de paires** — Engle-Granger (OLS normalisé → ADF sur résidus, `autolag='AIC'`) + confirmation Johansen + consensus Newey-West HAC + filtre corrélation min. 0.75 + filtre liquidité ≥ $5M/24h + I(1) pre-check (ADF + KPSS)
2. **Modélisation du spread** — OLS brut reconstruit à chaque barre sur l'historique complet : `spread = y − (α + β·x)` via `np.linalg.lstsq`
3. **Z-score adaptatif** — fenêtre glissante [10, 120] bars, calibrée par half-life estimé via AR(1), clamping à [−6, +6]
4. **Seuils adaptatifs** — base 2.0 ajusté par régime de volatilité (−0.4 LOW / +0.5 HIGH) et half-life (−0.3 court / +0.3 long) → plage effective [1.0, 3.5]
5. **Pipeline de filtres pré-entrée** — régime détecteur (LOW/NORMAL/HIGH), Z-momentum (slope 3 bars), stationarité rolling ADF, CUSUM structural break, corrélation des legs rolling, limites internes de risque (8 positions max, 10% DD, 20 trades/jour)
6. **Gestion des positions** — trailing stop (widening > 1σ depuis entrée Z), time stop (≤ 2 × HL, cap 60 bars), stop-loss P&L (3%), partial profit (1.5% profit déclenche fermeture 50%), circuit breaker portfolio (15% DD)
7. **Sizing** — 2% du capital par paire × quality multiplier (p-value) × vol multiplier (inverse-vol) × strength signal (régime)

### Hypothèse économique sous-jacente

Existence d'une relation d'équilibre coïntégrée stable entre deux cryptos corrélés — fondée implicitement sur des liens fondamentaux (infrastructure commune, adoption BTC/ETH, tokenomics liés). Cette hypothèse économique est **non étayée dans le code** : aucune documentation d'une thèse économique par paire. L'argument repose uniquement sur la corrélation statistique historique.

### Type réel

**Pseudo-arbitrage statistique** — pas d'arbitrage véritable (aucune garantie de convergence). Corrélation-based mean reversion habillée en formalisme de cointégration. La persistance de cointégration sur crypto est **structurellement instable** : cycles altcoins, BTC dominance rotation, bankruptcies d'émetteurs (FTX, Luna), tokenomics changeants.

### Cohérence globale

Architecture multi-sprint avec couverture de protection dense (10+ couches). La stratégie est sur-architecturée en guarde-fous par rapport à son edge statistique démontré. **Aucun résultat de backtest sur données réelles n'est documenté dans le dépôt.** La validité empirique est inconnue.

---

## 2. Validité statistique

### Implémentation du test Engle-Granger

**Méthode :** OLS sur prix z-scorés (normalisés par μ et σ) → résidus normalisés → ADF (`autolag='AIC'`, `regression='c'`).  
**Dénormalisation β :** `beta_raw = (y_std × β_n) / x_std` — mathématiquement correcte.  
**Double screening :** EG + Johansen (trace + max-eigenvalue, rang conservatif = min(trace_rank, max_eig_rank)) + Newey-West HAC consensus.

> 🔴 **CRITIQUE — Double OLS divergent : β validé ≠ β tradé**  
> L'EG test estime β sur des **prix z-scorés** puis "dénormalise" via `beta_raw = y_std × β_n / x_std`. Le `SpreadModel` / `DynamicSpreadModel` refait une **régression OLS brute séparée** sur les prix en niveaux (`np.linalg.lstsq(X, y.values)`). Ces deux régressions ne sont jamais alignées ni vérifiées l'une contre l'autre. Sur des paires à ordres de grandeur très différents (BTC ~50 000, BONK ~0.00002), la dénormalisation peut produire des écarts β significatifs. **La cointegration est validée sur une relation qui n'est pas exactement celle tradée.**

### P-value utilisée

**Découverte :** `α_corrigé = 0.05 / (N × (N-1) / 2)`.  
Avec 100 symboles → `num_pairs = 4 950` → `α ≈ 1.01 × 10⁻⁵`.

> 🔴 **CRITIQUE — Bonferroni orthodoxe trop conservateur pour marchés crypto normaux**  
> Avec ~100 symboles, le seuil Bonferroni est `~1e-5`. Les résidus de régression OLS sur des séries crypto de 252 jours quotidiens atteignent ce niveau de significance ADF seulement pour des paires exceptionnellement bien cointégrées. En marchés latéraux ou à rotation altcoin, la stratégie **découvrira zéro paires valides** sans aucune alarme opérationnelle. Le taux de découverte de paires par régime de marché n'est jamais monitoré ni documenté.

**Validation OOS :** `OutOfSampleValidator` re-teste avec `num_symbols = len(unique_symbols_in_discovered_pairs)`. Si 5 paires survivent la découverte sur 10 symboles uniques → `num_pairs = 45` → `α ≈ 1.1 × 10⁻³` — **100× plus permissif** que le seuil de découverte. La validation OOS accepte donc des paires au seuil de rigueur bien inférieur à la découverte, créant une asymétrie qui donne une fausse impression de robustesse.

### Fenêtres roulantes ou statiques

- **Pair discovery :** statique sur `lookback_window = 252` barres (1 an calendaire)
- **StationarityMonitor :** rolling ADF sur 60 dernières observations — correct
- **StructuralBreakDetector :** CUSUM + β stability sur résidus complets — correct
- **Régime détecteur :** rolling 20 barres pour volatilité

### Risque de faux positifs

Avec Bonferroni strict en découverte mais ~100× plus laxiste en OOS validation, les faux positifs subsistants passent facilement la validation. Le système offre une apparence de double validation alors que la seconde étape n'est pas suffisamment discriminante.

### Robustesse de la cointégration dans le temps

**Protections présentes :**
- Rolling ADF tous les bars (StationarityMonitor, window=60, p < 0.10)
- CUSUM + β drift (StructuralBreakDetector, drift_threshold=15%)
- Rolling leg correlation monitoring (window 30 bars, decline > 50% → exclusion)
- Reestimation β toutes les 7 jours (HedgeRatioTracker)

**Absentes :**
- Pas de test KPSS sur le spread résiduel (uniquement sur les niveaux I(1))
- Pas de test de causalité de Granger (présent dans les imports mais non intégré au pipeline)

### Stabilité du hedge ratio

> 🔴 **CRITIQUE — Détection de dérive β architecturalement contournée**  
> Dans `generate_signals()`, un nouveau `DynamicSpreadModel(y, x, ...)` est instancié **à chaque appel** (chaque barre). Le constructeur `SpreadModel.__init__` appelle immédiatement `self.tracker.record_initial_beta(pair_key, self.beta)`. La méthode `reestimate_beta_if_needed()` est ensuite appelée avec `new_beta` issu des mêmes données → drift ≈ 0%. De plus, le `HedgeRatioTracker` utilise `datetime.now()` pour son throttling (7 jours calendaires) : en backtest, les barres se succèdent en millisecondes, donc la condition temporelle n'est jamais satisfaite et la reestimation n'est jamais déclenchée. **La détection de dérive β est fonctionnellement neutralisée dans le backtest et incorrecte en live (le tracker voit chaque barre comme une nouvelle "initialisation").**

### Risque de régime shift

> 🟠 **MAJEUR — RegimeDetector alimenté par des niveaux de spread (pas des rendements)**  
> `generate_signals()` appelle `self.regime_detector.update(spread=spread.iloc[-1])` en passant la **valeur** du spread. `RegimeDetector.update()` calcule les rendements internes par `(curr - prev) / abs(prev)`. Quand le spread oscille autour de zéro (comportement attendu), `prev` est proche de zéro → division explosive → volatilité artificielle → classification HIGH injustifiée → seuils d'entrée gonflés → positions légitimes bloquées. Ce bug biaise systématiquement le sizing positionnel vers 0.5× en phases de mean-reversion normale.

---

## 3. Construction du spread

### Méthode de calcul

`spread = y − (α + β·x)` via OLS brut sur historique complet jusqu'à la barre courante (expanding window). β re-estimé à chaque barre par reconstruction complète du modèle. Formellement correct mais crée un look-ahead statistique doux (cf. §5).

### Normalisation

Z-score rolling sur fenêtre adaptée [10, 120] bars en fonction du half-life estimé. Clamping à [−6, +6]. Normalisation correcte.

### Stationnarité vérifiée ou supposée ?

**Vérifiée rolling** tous les bars via StationarityMonitor (ADF sur 60 dernières obs., p < 0.10). Si test échoue → fermeture de la position existante + blocage des nouvelles entrées. Mécanisme le plus fiable du système.

### Robustesse du Z-score

La fenêtre Z-score est adaptée au half-life (`hl <= 10 → lookback = 3×hl`, `hl >= 60 → lookback = 60`). Dépendance à la précision du half-life estimé via AR(1) sur 252 obs. max. Une mauvaise estimation de HL biaise la fenêtre de normalisation.

### Sensibilité aux outliers

`remove_outliers(threshold=4σ)` + `ffill()` uniquement (pas de `bfill` — pas de look-ahead). Correct dans son principe.

> 🟡 **MINEUR — Forward-fill sur outliers : barres fantômes**  
> Pour des tokens ultra-volatils (PEPE pendant un KOL pump), plusieurs barres consécutives peuvent être taguées outlier et remplacées par le dernier prix valide. La séquence produit un spread artificiellement stable → faux signal d'entrée → retour au prix réel sur la barre suivante = perte immédiate garantie. L'impact est d'autant plus fréquent que l'univers contient des Tier-4 meme coins.

---

## 4. Logique d'entrée / sortie

### Seuil |Z| > 2 justifié ou arbitraire ?

Base 2.0 paramétrique sans justification documentée. Les ajustements adaptatifs (−0.4/+0.5 volatilité, −0.3/+0.3 HL) sont **empiriques et non validés par cross-validation**. `ParameterCrossValidator` est implémenté dans `backtests/parameter_cv.py` mais **aucun résultat d'exécution ni rapport de recommandation n'existe dans le dépôt**. Ces 12+ paramètres libres restent donc des priors non validés.

### Optimisation implicite

Les valeurs d'ajustement spécifiques (`−0.4`, `+0.5`, `−0.3`, `+0.3`) ressemblent à des valeurs tâtonnées sur données historiques sans procédure d'optimisation documentée. Risque de sur-ajustement implicite élevé.

### Risque de sur-ajustement

L'univers prod contient ~100 symboles incluant des Tier-4 (PEPE, SHIB, FLOKI, BONK, WIF, TURBO, BLUR). Ces assets ont un historique court (< 2 ans) et des patterns de corrélation épisodiques. Leur inclusion gonfle `num_pairs` dans Bonferroni sans apporter de paires exploitables durables.

### Stops présents

**Présents et fonctionnels dans le simulateur :**
- Time stop : `bar_idx − pos["entry_bar"] >= min(2×HL, 60)` — **bar-counting correct**
- Trailing stop : widening Z > 1.0σ depuis entrée — correct
- Stop-loss P&L : loss_pct ≥ 3% de notionnel — trop faible (cf. §6)
- Partial profit : ≥ 1.5% profit → fermeture 50% — implémenté et appelé dans le simulateur
- Internal drawdown guard (10% equity drawdown) + circuit breaker portfolio (15%)

> 🟠 **MAJEUR — `datetime.now()` dans `generate_signals` : incohérence live/backtest**  
> Dans `generate_signals()`, chaque entrée enregistrée dans `self.active_trades` utilise `entry_time = datetime.now()`. En backtest, cela produit des timestamps en temps réel (ex: `2026-02-22 14:32:01`) au lieu de la date de la barre simulée (ex: `2023-06-15`). Le `TrailingStopManager` reçoit aussi `entry_time=datetime.now()`. Bien que `TrailingStopManager.should_exit_on_trailing_stop()` n'utilise pas `entry_time` dans ses calculs, **l'état interne de la stratégie (active_trades) est temporellement incohérent avec le simulateur** (qui utilise correctement `entry_bar`). En live trading, cela crée des logs erronés et peut affecter tout composant futur utilisant `entry_time` pour calculer des durées de position.

### Gestion du temps en position

Le time stop dans le simulateur est **correctement implémenté** : `holding_bars = bar_idx − pos["entry_bar"]`, comparé à `min(2×HL, 60)` via `TimeStopManager.should_exit()`. Ce mécanisme fonctionne correctement en backtest et en live.

### Risque de drift structurel

Couvert par CUSUM + β stability (StructuralBreakDetector). Mais cf. §2 sur la neutralisation de la détection β.

---

## 5. Backtesting & validation

### Séparation in-sample / out-of-sample réelle ?

Structurellement oui : Walk-forward avec `strategy.disable_cache()` et fresh instance par période. Logique de découverte strictement sur train_df. Pas de contamination détectée dans le flow principal.

### Walk-forward correctement implémenté ?

**Fenêtre expansive (expanding window) :** chaque période d'entraînement part de t=0. Défendable mais crée une prédominance des données récentes : les dernières fenêtres de train incluent toutes les données depuis l'origine, ce qui inclut des régimes de cointégration qui n'existent plus. Une fenêtre glissante (rolling) serait plus représentative du "vrai" régime actuel.

**Durée des fenêtres test :** avec `num_periods=4` et `oos_ratio=0.2` sur 2 ans de données (504 barres journalières), chaque période de test ≈ `504 × 0.2 × 4 / (4+1) / 4 ≈ ` environ 25–32 barres. **Avec un max_half_life de 60 jours, certaines positions ne complètent même pas un cycle de mean-reversion dans la fenêtre de test.** La robustesse OOS ne peut pas être évaluée statistiquement sur 25 barres.

### Data leakage possible ?

> 🔴 **CRITIQUE — Look-ahead statistique doux via OLS expanding window**  
> Dans `generate_signals()`, le modèle `DynamicSpreadModel(y, x)` est construit à la barre T avec `y = market_data[sym1]` et `x = market_data[sym2]` — c'est-à-dire toutes les données **de t=0 jusqu'à T**. Le β estimé inclut donc l'observation à la barre T elle-même. Le spread calculé à toutes les barres précédentes [0:T-1] utilise un β contamié par l'information de T. Quand le Z-score rolling est calculé sur ce spread, sa moyenne et son écart-type sont biaisés par des données "futures" (relatives à chaque point antérieur). **Ce look-ahead doux est systématique, présent à toutes les barres, et gonfle artificiellement les métriques de backtest.** L'impact est faible par barre mais s'accumule sur toute la période.

> 🟠 **MAJEUR — Half-life ancré sur découverte, pas recalibré sur fenêtre OOS**  
> Les paires `(sym1, sym2, pvalue, hl)` du training sont transmises au simulateur via `fixed_pairs`. Le `hl` de découverte est utilisé pour calibrer la fenêtre Z-score ET comme base du quality multiplier d'allocation. Pendant la période de test OOS, le HL réel de la paire peut avoir drifté significativement, mais les seuils d'allocation restent ancrés sur la valeur IS.

### Survivorship bias ?

L'univers 2026 contient des tokens qui ont eu des historiques discontinus (BSV/USDT rare sur Binance, WAXP-AGLD-MAGIC à liquidité intermittente). Si `DataLoader` charge uniquement les assets actifs en 2026, les backtests 2022-2024 souffrent d'un **survivorship bias partiel** : les tokens qui ont été délistés entre 2022 et 2026 ne figurent pas dans l'univers historique. L'univers est bénin (tokens encore actifs) mais biaisé par exclusion.

### Look-ahead bias ?

**Strict look-ahead élimé :**
- Expanding window `prices_df.iloc[:bar_idx+1]` — correct
- `ffill()` uniquement, pas de `bfill()` — correct
- Cache désactivé en walk-forward — correct

**Look-ahead statistique résiduel :** OLS expanding window (cf. ci-dessus).

### Slippage et frais réalistes ?

> 🔴 **CRITIQUE — `volume_24h = 1e9` par défaut dans le cost model**  
> `CostModel.execution_cost_one_leg()` est défini avec `volume_24h: float = 1e9`. Cette valeur est utilisée dans tous les appels du simulateur sans injection de volume réel. Pour MAGIC/USDT (~$5M/jour), WAXP/USDT (~$3M/jour), AGLD/USDT (~$2M/jour), le slippage volume-adaptatif est `5 + 100 × (order_size / 1e9) bps ≈ 5 bps` au lieu de `5 + 100 × (order_size / 5e6) bps` — soit **jusqu'à 200× sous-estimé**. **Tous les backtests impliquant des Tier-3/4 altcoins produisent des métriques de coût fictives.**

### Robustesse des métriques — Sharpe, Drawdown

> 🔴 **CRITIQUE — Annualisation incorrecte : 252 jours pour actifs crypto 365j/an**  
> `backtests/metrics.py:11` : `TRADING_DAYS_PER_YEAR: int = 252`. Le commentaire dans le code précise *"Default is 252 for equities"* mais EDGECORE trade exclusivement du crypto. Les cryptos tradent 365 jours/an sans interruption. Le Sharpe est calculé `(μ/σ) × √252` au lieu de `(μ/σ) × √365`. **Cela surestime le Sharpe d'un facteur √(365/252) ≈ 1.20**. Un Sharpe affiché de 1.5 représente un Sharpe réel de ≈ 1.25. Cette inflation est systématique sur TOUTES les sorties de métriques, TOUTES les périodes walk-forward, et TOUS les rapports de stress testing.

> 🟠 **MAJEUR — Sharpe calculé sans déduction du taux sans risque**  
> `sharpe_ratio = (returns.mean() / returns.std()) × √252` — aucun risk-free rate déduit. Avec des taux US à 4.5-5% en 2023-2024, le ratio d'information réel est inférieur d'environ 0.5 point de Sharpe en termes absolus par rapport au chiffre affiché.

---

## 6. Robustesse en environnement réel

### Sensibilité aux gaps

Les cryptos créent des gaps sur délisting, hard forks, exploits, ou réorganisations d'échanges. Le seul mécanisme de protection contre les gaps extrêmes est le clamping Z-score à [−6, +6]. Un gap de −80% (LUNA-style) crée un Z-score négatif clamped à −6 — la position longue du leg concerné subit la perte complète avant que le trailing stop ou le stop-loss P&L (3%) puisse agir (journalier, déclenché seulement à la prochaine barre).

### Sensibilité à la liquidité

Filtre ≥ $5M/24h. Pour un capital de $100k et une allocation 2% ($2k), la participation est ~0.04% du volume — acceptable. Au-delà de $300k de capital total, certaines paires Tier-3 deviennent illiquides relativement au sizing. **La stratégie ne scalera pas au-delà de ~$300k sans refonte du filtre de liquidité et des seuils d'allocation.**

### Impact du slippage réel

Cf. §5. Au-delà du bug `volume_24h=1e9`, le slippage crypto en real trading est asymétrique (pire à l'entrée en tendance). Le modèle volume-adaptatif est une approximation linéaire qui sous-estime le slippage d'impact en marchés en mouvement.

### Impact des frais Binance

4 legs × 10 bps = 40 bps frais minimum par round-trip. Pour une paire avec σ_spread ≈ 5% et entrée à Z=2.0 (spread ≈ 10% hors moyenne), edge espéré ≈ 10%. Après frais minimaux 50 bps = 9.5%. L'edge est positif en théorie mais marginal. La fréquence de trading est déterminante.

### Risque de breakdown de corrélation

Couvert par rolling leg correlation (window=30, seuil dépose < 50% de la corrélation historique). Fonctionnel.

### Scénarios critiques

| Scénario | Impact attendu | Protection actuelle | Efficacité |
|---|---|---|---|
| **Crash BTC −40% intraday** | Tous les spreads divergent simultanément ; cointegration brisée instantanément | Circuit breaker 15% DD (journalier) ; trailing stop (journalier) | Tardive — le crash hit avant la prochaine barre |
| **Volatilité prolongée 10 jours** | Faux HIGH-regime → seuils trop élevés → peu d'entrées ; positions existantes souffrent | Régime détecteur (BUGUÉ sur spread levels) ; stationarity monitor | Partielle — régime mal classifié |
| **Décorrélation brutale (Terra/Luna)** | Un leg −99%, l'autre stable ; spread explose | Leg correlation breakdown détecté après window=30 barres | Dommage déjà subi sur 30 barres avant détection |
| **Délisting surprise d'un leg** | Perte totale du leg sans aucune sortie possible | DelistingGuard filtre les tokens "mourants" mais pas les delistings de surprise | Aucune — mort instantanée du leg non protégée |

---

## 7. Interaction avec le Risk Engine

### La stratégie dépend-elle trop du risk engine ?

Non structurellement — la stratégie a ses propres limites internes (Sprint 4.4) indépendantes du RiskEngine externe. Le `RiskEngine` est **optionnel** dans le simulateur (`risk_engine=None` par défaut).

### Le risk engine compense-t-il une faiblesse structurelle ?

Partiellement. Le circuit breaker portfolio (15% DD) est le dernier rempart. Si l'edge statistique de la stratégie est nul ou négatif sur certains régimes, le circuit breaker sera déclenché régulièrement — ce qui est un signal d'alarme, pas une correction de l'edge.

### La stratégie reste-t-elle viable sans protection externe ?

**Non évalué.** Aucun backtest documenté ne compare les performances avec vs sans risk engine, avec vs sans trailing stop, avec vs sans circuit breaker. L'impact isolé de chaque couche de protection sur le P&L est inconnu. On ne peut pas déterminer si la stratégie est profitable avant protection ou si les garde-fous masquent une stratégie à edge marginal/négatif.

---

## 8. Scalabilité stratégique

### Peut-elle être multi-paires ?

Architecturalement oui — jusqu'à 8 positions simultanées. Concentration par symbole limitée à 30%. SpreadCorrelationGuard (ρ_max = 0.60) + PCASpreadMonitor actifs.

### Risque de corrélation croisée entre spreads ?

Couvert par les mécanismes ci-dessus. Mais ces mécanismes sont calibrés sur des corrélations historiques en régime normal. En crise, toutes les corrélations crypto convergent vers 1 et ces guards deviennent inefficaces (toutes les entrées seraient rejetées, ce qui est en fait la bonne décision — mais aussi le signal que la stratégie ferme tout sans capacité de réentrée).

### Effet de crowding potentiel ?

> 🟠 **MAJEUR — Univers de paires identique à tous les acteurs stat arb crypto**  
> BTC/ETH, ETH/BNB, SOL/AVAX, ETH/AVAX — paires "évidentes" testées par tous les fonds de stat arb sur Binance. En cas de liquidation forcée DeFi/CeFi (août 2023, mars 2024), toutes ces stratégies se débouclent simultanément, amplifiant les pertes de chacune. EDGECORE n'a pas de mécanisme de détection du crowding ni de spread momentum contra-indicateur.

---

## 9. Failles critiques identifiées

### 🔴 Critique — Invalide les métriques ou constitue un danger capital direct

| ID | Faille | Localisation précise | Impact |
|---|---|---|---|
| **C-01** | `TRADING_DAYS_PER_YEAR = 252` sur actifs crypto (365j/an) → Sharpe systématiquement surestimé ×1.20 | `backtests/metrics.py:11` | Toutes les métriques publiées sont fausses. Un Sharpe affiché de 1.5 vaut réellement ~1.25. |
| **C-02** | OLS divergent double : EG test sur prix normalisés, SpreadModel sur prix bruts → β validé ≠ β tradé | `models/cointegration.py` + `models/spread.py:31` | La cointegration est confirmée sur une relation statistiquement différente de celle réellement tradée. |
| **C-03** | `DynamicSpreadModel` reconstruit à chaque barre + `record_initial_beta` appelé à chaque reconstuction + throttle temporel `datetime.now()` en backtest → détection de dérive β fonctionnellement neutralisée | `strategies/pair_trading.py:~850` + `models/hedge_ratio_tracker.py` | La dépréciation des paires dont β a drifté ne se déclenche jamais en backtest. Positions zombies sur paires dégradées. |
| **C-04** | `volume_24h = 1e9` par défaut → slippage quasi-nul pour Tier-3/4 altcoins réellement à $2-10M/jour | `backtests/cost_model.py:execution_cost_one_leg` | Coûts d'exécution sous-estimés de 10–200× sur altcoins peu liquides. Métriques de P&L irréalistes sur ces paires. |
| **C-05** | Look-ahead statistique doux : β OLS expanding window estimé sur données [0:T] inclut la barre T → spread et Z-score contaminés par l'observation courante | `strategies/pair_trading.py:generate_signals` + `models/spread.py` | Gonflement artificiel des métriques de backtest. Effet cumulatif sur toute la période. |
| **C-06** | Bonferroni ~100× plus permissif en OOS validation qu'en découverte : `num_symbols` de l'univers complet vs `num_symbols` des paires découvertes seulement | `validation/oos_validator.py:__init__` vs `strategies/pair_trading.py:find_cointegrated_pairs_parallel` | La validation OOS ne filtre pas réellement les faux positifs — elle donne une impression de rigueur sans le niveau de correction requis. |

### 🟠 Majeur — Fragilité importante sans invalider immédiatement

| ID | Faille | Localisation précise | Impact |
|---|---|---|---|
| **M-01** | `RegimeDetector.update(spread=spread.iloc[-1])` reçoit des niveaux (proches de zéro) → volatilité artificielle → regime HIGH injustifié → seuils augmentés → entrées légitimes bloquées | `strategies/pair_trading.py:~1005` | Sizing systématiquement sous-dimensionné en régime normal. Biais opérationnel invisible. |
| **M-02** | `datetime.now()` dans `active_trades` et `TrailingStopManager.add_position` → état interne de la stratégie temporellement incohérent entre backtest et live | `strategies/pair_trading.py:generate_signals` (~L1050, L1065, L1110, L1130) | En live : analytics faux. En backtest : incohérence de débogage. Prépare des bugs dans tout composant futur qui lirait `entry_time`. |
| **M-03** | Fenêtres test WF ~25-32 barres avec `max_half_life=60` : les positions ne complètent pas un cycle de mean-reversion → métriques OOS statistiquement non fiables | `backtests/walk_forward.py:split_walk_forward` | WF ne valide pas réellement la stratégie — les périodes sont trop courtes pour démontrer la robustesse. |
| **M-04** | 12+ paramètres libres (seuils adaptatifs, ajustements régime, fenêtres corrélation) non validés par `ParameterCrossValidator` — outil implémenté mais jamais exécuté | `backtests/parameter_cv.py` (non exécuté) | Risque élevé de sur-ajustement implicite. Paramètres choisis empiriquement sans validation OOS. |
| **M-05** | `KalmanHedgeRatio` (Sprint 4.2, `models/kalman_hedge.py`) implémenté mais **non connecté** au pipeline `generate_signals` — la stratégie utilise toujours le simple OLS batch | `models/kalman_hedge.py` non importé dans `strategies/pair_trading.py` | Feature annoncée (Sprint 4.2) absente en production. OLS statique moins adaptatif que Kalman. Sprint documenté inutilisé. |
| **M-06** | `MLThresholdOptimizer` (`models/ml_threshold_optimizer.py`) implémenté mais non intégré dans le pipeline de trading live ou backtest | `models/ml_threshold_optimizer.py` non appelé | 835 lignes de code de recherche inutilisées en production. |
| **M-07** | Stop-loss P&L à 3% de notionnel inapproprié pour altcoins crypto : mouvement intraday de 5-15% est du bruit normal → stop déclenché par volatilité, pas par décorrélation réelle | `backtests/strategy_simulator.py:max_position_loss_pct=0.03` | Faux sense de protection. Fréquence de déclenchement indépendante de la qualité de la paire. |
| **M-08** | Univers Tier-4 (PEPE, SHIB, FLOKI, BONK, WIF, TURBO, BLUR) : historiques < 2 ans, corrélations épisodiques — gonflent `num_pairs` Bonferroni sans apporter de paires durables | `config/prod.yaml` | Rend le seuil Bonferroni encore plus strict sans valeur ajoutée. Ralentit la découverte. Crée un biais de sur-testing. |

### 🟡 Mineur — Optimisation ou amélioration

| ID | Faille | Impact |
|---|---|---|
| **mn-01** | Sharpe sans déduction du risk-free rate (4.5-5% en 2023-2024) → surestimation de ~0.4-0.5 point absolu | Performance apparente > performance ajustée |
| **mn-02** | `include_funding=False` par défaut → taux de financement perpetuals (~0.01%/8h) non capturé → ~0.6% de coût supplémentaire pour 20 jours de détention | Sous-estimation des coûts sur perpetuals |
| **mn-03** | Z-momentum filter sur 3 barres (`z_slope = z_score.iloc[-1] - z_score.iloc[-3]`) : signal sur 3 points journaliers = bruit pur statistique → rejets d'entrées arbitraires | Dégradation du hit rate sans filtrage de qualité réel |
| **mn-04** | `ffill()` sur outliers crée des barres fantômes sur tokens Tier-4 → faux spread stable → signal d'entrée spurieux | Risk occasionnel sur tokens ultra-volatils |
| **mn-05** | Sharpe annualisé sans risk-free + pas de test de significativité statistique du Sharpe (p-value pour H0: Sharpe ≤ 0) | Impossible de rejeter l'hypothèse nulle de performance nulle. |
| **mn-06** | `import vectorbt as vbt` dans `backtests/runner.py` mais non utilisé dans le chemin principal | Dépendance lourde inutile, erreur si package absent |

---

## 10. Recommandations prioritaires

### Top 5 — Corrections obligatoires avant paper trading

**P1 — [C-01] Corriger l'annualisation crypto immédiatement**

```python
# backtests/metrics.py — ligne 11
TRADING_DAYS_PER_YEAR: int = 365  # Crypto: 24/7/365
```
Recalculer tous les Sharpe précédents. Documenter l'écart avec les valeurs antérieures.

**P2 — [C-04] Injecter les volumes réels dans le cost model**

Connecter `LiquidityFilter._volume_data` (déjà maintenu) au `CostModel.execution_cost_one_leg`. Supprimer le défaut `volume_24h=1e9`. Ajouter une assertion : `assert volume_24h > 0, "volume_24h requis"`. Sans cette correction, tous les backtests sur Tier-3/4 sont économiquement irréalistes.

**P3 — [C-03] Stabiliser la reconstruction du modèle par barre**

Deux options mutuellement exclusives :  
*Option A (minimal) :* Persister le `SpreadModel` dans `self.spread_models[pair_key]` entre les barres. Ne le reconstruire que toutes les 7 jours (config `hedge_ratio_reestimation_days`). Appeler `reestimate_beta_if_needed` sur le modèle existant.  
*Option B (optimal) :* Remplacer l'OLS batch par `KalmanHedgeRatio` (déjà implémenté, jamais connecté) — β adaptatif sans reconstruction.

**P4 — [C-02] Unifier les deux régressions OLS**

Passer le `beta_raw` et `intercept_raw` produits par `engle_granger_test` directement au constructeur de `SpreadModel` au lieu de refaire une régression séparée. Ajouter un test d'assertion :

```python
assert abs(beta_from_EG - beta_from_spreadmodel) / abs(beta_from_EG) < 0.01, \
    f"β divergence: EG={beta_from_EG:.4f} vs SpreadModel={beta_from_spreadmodel:.4f}"
```

**P5 — [M-01] Corriger l'alimentation du RegimeDetector**

```python
# Dans generate_signals(), remplacer :
regime_state = self.regime_detector.update(spread=spread.iloc[-1])

# Par : (rendement du spread ou Z-score normalisé)
spread_change = spread.diff().iloc[-1]  
regime_state = self.regime_detector.update(spread=spread_change)
```
Valider que la distribution des régimes (LOW/NORMAL/HIGH) est bien ~33%/~34%/~33% sur un historique long.

---

### Améliorations moyen terme

- Exécuter `ParameterCrossValidator` sur données réelles 2021-2025 → remplacer les 12+ paramètres empiriques par les valeurs OOS-optimales issues du CV
- Augmenter le nombre de barres de test WF : utiliser 5+ ans de données ou réduire `num_periods` à 3 pour allonger les fenêtres OOS à ≥ 120 barres par période
- Connecter `KalmanHedgeRatio` à la production : remplacer l'OLS batch dans `SpreadModel` par une mise à jour Kalman incrémentale (élimine C-03 et C-05 simultanément)
- Implémenter un tableau de bord opérationnel du taux de découverte de paires par régime : alerter si 0 paire découverte sur 2 cycles consécutifs
- Exclure définitivement les Tier-4 meme coins de l'univers de cointegration
- Lancer les stress tests (`StressTestRunner`) sur données réelles et documenter les résultats

### Optimisations avancées

- Corriger l'asymétrie Bonferroni OOS (C-06) : utiliser `num_symbols = N_univers` dans `OutOfSampleValidator`, pas le sous-ensemble découvert
- Intégrer un test de significance du Sharpe (Lopez de Prado, deflated Sharpe Ratio) pour quantifier si la performance backtestée est statistiquement distinguable du bruit
- Calibrer le stop-loss positionnel par actif : `loss_pct_threshold = k × σ_spread` (multiple de volatilité) plutôt qu'un flat 3%
- Évaluer une sortie par étapes : 50% à Z=1.0, 50% à Z=0 pour réduire le temps en position moyen
- Implémenter un indicateur de crowding (ex : saut du spread OBI sur Binance depth) avant entrée

---

## 11. Score stratégique final

### Score qualité statistique : **4.5 / 10**

| Critère | Évaluation | Score |
|---|---|---|
| Tests de cointegration (triple screening EG+Johansen+HAC) | Rigoureux sur le papier | 7/10 |
| Vérification I(1) pre-EG | Correcte | 8/10 |
| Cohérence β EG vs β tradé | **Divergence non contrôlée** | 2/10 |
| Annualisation Sharpe correcte | **252 au lieu de 365 — faux** | 0/10 |
| Look-ahead bias | **OLS expanding contamine les spreads** | 2/10 |
| Asymétrie Bonferroni IS vs OOS | Rigoureuse en IS, permissive en OOS | 3/10 |
| Robustesse rolling (stationarity + CUSUM) | Bien architecturé | 7/10 |
| Paramètres validés par CV OOS | **ParameterCV jamais exécuté** | 1/10 |
| Résultats documentés sur données réelles | **Inexistants** | 0/10 |
| Détection dérive β | **Neutralisée architecturalement** | 1/10 |

### Score robustesse réelle : **4.0 / 10**

| Critère | Évaluation | Score |
|---|---|---|
| Walk-forward architecture | Correct dans son flow | 7/10 |
| Durée fenêtres OOS | Trop courtes (25 barres) | 2/10 |
| Slippage et frais réalistes | **volume_24h=1e9 — fiction** | 1/10 |
| Time stop (simulateur) | Correct (bar counting) | 8/10 |
| Trailing stop | Correct (Z-score widening) | 7/10 |
| Survivorship bias | Partiel (Tier-3/4 altcoins) | 4/10 |
| Régime détecteur | **Bug spread levels** | 2/10 |
| Protection délisting surprise | Absente | 0/10 |
| Stress tests exécutés + documentés | **Absents** | 0/10 |
| Scalabilité démontrée | Non évaluée | 3/10 |

### Probabilité de survie 12 mois live

**< 30%** dans l'état actuel.

Fondements de cette estimation :
- **4 bugs critiques** (C-01, C-02, C-03, C-04) invalident les métriques de backtest présentées — les performances historiques sont inconnues réellement
- **C-03** (β drift neutralisé) → la stratégie peut trader des paires dégradées indéfiniment sans détection
- **C-04** (coûts fictifs) → les paires Tier-3/4 sont potentiellement loss-making après coûts réels
- **C-05** (look-ahead doux) → les métriques de backtest sont optimistes par construction
- Aucun résultat empirique sur données réelles pour calibrer une estimation plus précise

### Verdict clair

**👉 Stratégiquement fragile — non déployable en capital réel dans l'état actuel**

L'architecture de protection est solide dans ses intentions. Le pipeline de découverte de paires est rigoureux sur le papier (triple screening, I(1) pre-check, rolling stationarity). Mais quatre erreurs d'implémentation combinées (annualisation, coûts, β drift, look-ahead OLS) invalident les métriques de backtest existantes et rendent impossible toute évaluation fiable de l'edge réel.

**Chemin vers le déploiement :**
1. Appliquer les 5 corrections prioritaires (P1–P5) — estimé 1–2 semaines de développement
2. Lancer un walk-forward complet sur 5 ans de données réelles Binance (2020–2025)
3. Exiger un Sharpe OOS ≥ 1.0 (annualisé 365j, sans risk-free, calculé sur données réelles) sur ≥ 3 périodes walk-forward consécutives de ≥ 90 barres chacune
4. Paper trading minimum 90 jours calendaires sur TOUTE l'infrastructure live avec logging complet
5. Monitorer le taux de découverte de paires hebdomadaire en live : si < 1 paire découverte par semaine sur 4 semaines consécutives → stratégie silencieuse → ne pas déployer

**Avant application des 5 corrections prioritaires : allocation en capital réel = 0.**
