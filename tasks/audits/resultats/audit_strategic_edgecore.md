# Audit Stratégique EDGECORE — Stat-Arb Pairs Trading
**Date :** 2026-05-14     
**Création :** 2026-03-22 à 12:42  
**Version codebase :** post-IA/ML (2681 tests, commit `52e92ab`)  
**Auditeur :** GitHub Copilot (Claude Sonnet 4.6)  
**Échelle sévérité :** P0 invalide le backtest · P1 surestimation forte · P2 surestimation modérée · P3 amélioration

---

## BLOC 1 — INTÉGRITÉ STATISTIQUE DES SIGNAUX

### 1.1 Biais de look-ahead

| # | Point | Verdict | Référence | Notes |
|---|-------|---------|-----------|-------|
| 1.1a | Fenêtre expansive barre-par-barre | ✅ CONFORME | `backtests/strategy_simulator.py:343` `hist_prices = prices_df.iloc[:bar_idx + 1]` | Strictement causal — aucun accès aux données futures |
| 1.1b | Filtre de Kalman (hedge ratio) | ✅ CONFORME | `models/kalman_hedge.py:update()` | Passe forward uniquement — `P` mis à jour sequentiellement, aucun lissage RTS |
| 1.1c | Calcul du z-score (rolling causal) | ✅ CONFORME | `signal_engine/zscore.py:75-79` | `rolling(window).mean()/.std()` — strictement causal |
| 1.1d | **Signal sur barre courante (timing exécution ambigu)** | ⚠️ À VÉRIFIER | `strategies/pair_trading.py:982` + `simulator:343` | `z_score.iloc[-1]` sur la barre `bar_idx` dont le close est inclus. Si exécution = ce même close → biais P1. Acceptable uniquement si slippage modélise correctement le fill au close+1 |

**Détail 1.1d :** Le simulateur construit `hist_prices = prices_df.iloc[:bar_idx + 1]` (inclut la barre courante), puis `generate_signals()` lit `z_score.iloc[-1]` sur ce close. Si l'ordre est supposé être exécuté à **ce même close**, cela dépasse la convention market-on-close standard (signal non connu avant fin de barre). Le modèle de coût Almgren-Chriss inclut un composant slippage mais la synchronisation signal→fill n'est **nulle part documentée** comme décalée d'une barre.

---

### 1.2 Biais de data-snooping (surapprentissage paramétrique)

| # | Point | Verdict | Référence |
|---|-------|---------|-----------|
| 1.2a | Walk-forward fenêtre expansive — pas de sélection du meilleur fold | ✅ CONFORME | `backtests/walk_forward.py:167-210` — `profitable_periods/total ≥ 50%` comme critère pass |
| 1.2b | Instance fraîche par fold (`disable_cache()`) | ✅ CONFORME | `backtests/walk_forward.py` — `strategy = PairTradingStrategy(); strategy.disable_cache()` |
| 1.2c | Paramètres non ré-optimisés intra-fold | ✅ CONFORME (à confirmer) | `backtests/parameter_cv.py` existe mais pas invoqué dans WalkForwardBacktester. Les paramètres viennent de `get_settings()` figés |

---

### 1.3 Biais de survie

| # | Point | Verdict | Sévérité |
|---|-------|---------|---------|
| 1.3a | **Univers hardcodé = snapshot actuel du marché** | ❌ NON CONFORME | **P0** |
| 1.3b | `DelistingGuard` réactif (temps réel) — pas de filtrage rétroactif | ❌ NON CONFORME | **P0** |

**Détail critique P0 :**  
`universe/manager.py` contient `DEFAULT_SECTOR_MAP` — un dictionnaire hardcodé de ~100 actions **actuellement cotées** (AAPL, MSFT, GS, JPM…). Les backtests exécutés sur 5-10 ans de données **ne sélectionnent que des survivantes** : aucune entreprise délistée pendant la période de test (faillite, OPA, radiation) n'est incluse dans l'univers.

```
universe/manager.py → DEFAULT_SECTOR_MAP = {
    "AAPL": "Technology", "MSFT": "Technology", ...  # ~100 titres, tous survivants
}
```

`data/delisting_guard.py` effectue des vérifications réactives (crash de volume >80%, prix <$0.001, données périmées >3 jours) **en temps réel uniquement** — il ne reconstitue pas un univers point-in-time historique.

**Impact quantitatif estimé :** surestimation du Sharpe de **15-25%** (littérature académique sur le biais de survie equity long-short : Elton et al. 1996, Carhart 1997).

**Correction requise :** Intégrer une base de données point-in-time (ex. CRSP, Compustat, ou fichier CSV avec dates d'ajout/retrait par symbole) et filtrer `get_universe()` par `universe_date`.

---

### 1.4 Cohérence backtest ↔ live

| # | Point | Verdict | Référence |
|---|-------|---------|-----------|
| 1.4a | Code path unique (`generate_signals()`) pour backtest et live | ✅ CONFORME | `backtests/strategy_simulator.py:4` "Uses `PairTradingStrategy.generate_signals()` as the **sole** source of trading logic" |
| 1.4b | `SignalGenerator.generate()` partagé | ✅ CONFORME | `signal_engine/generator.py` — même instance en backtest et en live |

---

## BLOC 2 — SOLIDITÉ DU MODÈLE STATISTIQUE

### 2.1 Sélection des paires

| # | Point | Verdict | Référence |
|---|-------|---------|-----------|
| 2.1a | Correction de Bonferroni avant filtre half-life | ✅ CONFORME | `pair_selection/discovery.py:218-224` — `alpha_adj = significance_level / n_tests` |
| 2.1b | Triple gate : EG + Johansen + Newey-West | ✅ CONFORME | `pair_selection/discovery.py:245-280` — `johansen_confirmation=True` par défaut |
| 2.1c | Fenêtre IS-only pour la sélection | ✅ CONFORME | `data = price_data.tail(lb)` — lookback window uniquement |
| 2.1d | Vérification de stationnarité ADF + break structurel CUSUM | ✅ CONFORME | `signal_engine/generator.py` steps 3 & 3b |

**Point positif majeur :** La séquence Bonferroni → EG → NW → Johansen est rigoureuse et va au-delà de la pratique standard. Le gate triple réduit significativement les faux positifs de cointégration.

---

### 2.2 Modèle de spread et hedge ratio

| # | Point | Verdict | Sévérité |
|---|-------|---------|---------|
| 2.2a | **Hedge ratio OLS statique (pas Kalman barre-par-barre)** | ❌ NON CONFORME | **P2** |
| 2.2b | Z-score avec fenêtre adaptative (half-life) | ✅ CONFORME | `signal_engine/zscore.py:_resolve_lookback()` |
| 2.2c | **Spread en prix niveau (non log-prix)** | ❌ NON CONFORME | P3 |
| 2.2d | Thresholds adaptatifs via régime | ✅ CONFORME | `signal_engine/generator.py:252-258` → `AdaptiveThresholdEngine` |

**Détail 2.2a — P2 :**  
`models/spread.py` calcule le beta OLS à l'instanciation :
```python
beta = np.linalg.lstsq(X, y, rcond=None)[0]  # OLS statique
```
`reestimate_beta_if_needed()` fait une ré-estimation OLS périodique (fréquence : 7 jours), **pas barre-par-barre**. Or `models/kalman_hedge.py` (classe `KalmanHedgeRatio`) implante un filtre de Kalman en passe forward, mais `SpreadModel` ne l'utilise pas. Le drift du hedge ratio entre deux ré-estimations hebdomadaires peut générer un spread non-stationnaire artificiellement → faux signaux et drawdowns amplifiés.

**Détail 2.2c — P3 :**  
Le spread est calculé en prix niveau : `y - (intercept + beta*x)`. Pour des actions, les log-prix sont préférables (processus multiplicatif, stationnarité à long terme, interprétation en rendements). L'impact est surtout marqué sur les paires de prix très asymétriques.

---

### 2.3 Modèle de coûts

| # | Point | Verdict | Sévérité |
|---|-------|---------|---------|
| 2.3a | Almgren-Chriss 3 composantes (spread + impact + timing) | ✅ CONFORME | `backtests/cost_model.py:_slippage()` |
| 2.3b | **Borrowing cost 0.5% (GC rate — HTB sous-estimé)** | ❌ NON CONFORME | **P2** |
| 2.3c | **Volume ADV = $10M par défaut (impact sous-estimé small-cap)** | ❌ NON CONFORME | **P2** |

**Détail 2.3b — P2 :**  
`backtests/cost_model.py:CostModelConfig` fixe `borrowing_cost_annual_pct = 0.005` (50 pb). Pour les actions GC (General Collateral) liquides, c'est correct. Mais la stratégie peut inclure des mid-caps à fort beta court impliquant des frais HTB (Hard-to-Borrow) de 1% à 20%+ par an. Aucun surcoût HTB n'est modélisé.

**Détail 2.3c — P2 :**  
Dans `_execution_cost_one_leg()`, le paramètre `volume_24h` coûts de marché impact est passé avec default `1e7` ($10M). Si le backtest n'injecte pas le vrai ADV par symbole, le composant `η × σ × sqrt(Q/ADV)` est systématiquement sous-estimé pour tous les titres avec ADV < $10M.

---

### 2.4 Validation hors-échantillon

| # | Point | Verdict | Référence |
|---|-------|---------|-----------|
| 2.4a | Split ancré (pas rolling) avec 21 jours OOS | ✅ CONFORME | `backtester/oos.py:validate()` — `is_data = price_data.loc[:split_ts]` / `oos_data = price_data.loc[split_ts:]` |
| 2.4b | Gates : 70% persistance de cointégration + drift HL ±50% | ✅ CONFORME | `validation/oos_validator.py:acceptance_threshold=0.70` |
| 2.4c | Gates calibrés indépendamment des résultats backtest ? | ⚠️ À VÉRIFIER | Risque de méta-surapprentissage si les seuils 70%/±50% ont été ajustés après observation des performances IS |

---

## BLOC 3 — RISK MANAGEMENT FINANCIER

### 3.1 Kill-switch

| # | Point | Verdict | Référence |
|---|-------|---------|-----------|
| 3.1a | 6 conditions kill (DRAWDOWN·DAILY_LOSS·CONSECUTIVE_LOSSES·VOLATILITY_EXTREME·DATA_STALE·MANUAL) | ✅ CONFORME | `risk_engine/kill_switch.py:KillReason` |
| 3.1b | Persistance état JSON (survie aux redémarrages) | ✅ CONFORME | `risk_engine/kill_switch.py:_load_state()` |
| 3.1c | Lock threading atomique | ✅ CONFORME | `risk_engine/kill_switch.py:_activation_lock = threading.Lock()` |
| 3.1d | **Callback d'annulation des ordres IBKR à vérifier** | ⚠️ À VÉRIFIER | `risk_engine/kill_switch.py:on_activate` — le callback existe mais le câblage dans `live_trading/runner.py` pour annuler les ordres ouverts chez IBKR n'est pas vérifié |

**Risque opérationnel 3.1d :** Si le kill-switch déclenche mais que le callback `cancel_all_orders()` n'est pas correctement branché au `IBKRExecutionEngine`, des positions peuvent rester ouvertes alors que le système ne les monitore plus — risque de pertes illimitées.

---

### 3.2 Sizing et concentration

| # | Point | Verdict | Sévérité |
|---|-------|---------|---------|
| 3.2a | Limite par paire : max 30% du portefeuille | ✅ CONFORME | `portfolio_engine/allocator.py:max_allocation_pct=0.30` |
| 3.2b | **Sizing EQUAL_WEIGHT par défaut (ignore la volatilité des spreads)** | ❌ NON CONFORME | **P2** |
| 3.2c | Délimitation sectorielle (40%) | ✅ CONFORME | `portfolio_engine/concentration.py` → `ConcentrationLimitManager` |
| 3.2d | Hedging bêta-neutre dynamique | ✅ CONFORME | `portfolio_engine/hedger.py:BetaNeutralHedger.compute_beta_hedge()` |

**Détail 3.2b — P2 :**  
`SizingMethod.EQUAL_WEIGHT` (défaut) alloue `frac = min(1/max_pairs, max_allocation_pct)` identiquement à chaque paire. Or les spreads ont des volatilités très différentes — une paire très volatile reçoit le même capital qu'une paire dormante. `SizingMethod.VOLATILITY_INVERSE` est disponible mais non activé par défaut.

Conséquence : le portefeuille est dominé par les paires à forte vol → drawdown amplifiable lors d'un retournement de régime.

---

### 3.3 Stops et durée maximale

| # | Point | Verdict | Référence |
|---|-------|---------|-----------|
| 3.3a | Stop trailing sur z-score du spread (1σ widening) | ✅ CONFORME | `risk_engine/position_risk.py:TrailingStop` |
| 3.3b | Stop temporel 60 barres | ✅ CONFORME | `risk_engine/position_risk.py` cohérent avec `max_half_life ≤ 60` |
| 3.3c | Stop perte max par position 10% | ✅ CONFORME | `risk_engine/position_risk.py:max_loss_pct=0.10` |
| 3.3d | Stop absolu |z| > 3σ | ⚠️ À VÉRIFIER | Non visible en tant que stop nommé — vérifié implicitement via trailing stop mais pas explicitement |

---

### 3.4 Corrélations de portefeuille et régimes

| # | Point | Verdict | Sévérité |
|---|-------|---------|---------|
| 3.4a | `PCASpreadMonitor` : vérification intrabar, bloque si PC1 > 50% | ✅ CONFORME | `risk/pca_spread_monitor.py` + `simulator:457` |
| 3.4b | `SpreadCorrelationGuard` : bloque nouvelles entrées si corrélation anormale | ✅ CONFORME | `portfolio_engine/hedger.py:SpreadCorrelationGuard` |
| 3.4c | **`RegimeDetector` jamais ré-entraîné** | ❌ NON CONFORME | P3 |
| 3.4d | Sizing non réduit automatiquement en régime de risque | ⚠️ À VÉRIFIER | La réduction via `DD_ACTION.sizing_multiplier` existe mais est basée sur DD réalisé, pas sur le régime de vol |

**Détail 3.4c — P3 :**  
`models/regime_detector.py` utilise des percentiles roulants sur 20 barres (33ème/67ème) pour classifier l'état de volatilité LOW/NORMAL/HIGH. Ces seuils de percentile ne sont jamais calibrés sur des données OOS ni recalculés périodiquement — ils sont calculés in-window à chaque barre, ce qui reste causal, mais la fenêtre de 20 barres est courte et peut mal capturer les transitions de régime prolongées (ex. crise de mars 2020).

---

## BLOC 4 — VIABILITÉ EN CONDITIONS RÉELLES

### 4.1 Capacité et liquidité

| # | Point | Verdict | Sévérité |
|---|-------|---------|---------|
| 4.1a | Filtre liquidité min $5M/j | ✅ CONFORME | `data/liquidity_filter.py:min_volume_24h_usd=5_000_000` |
| 4.1b | `strict_mode=False` (accepte symboles sans volume) | ⚠️ À VÉRIFIER | En mode non-strict, des titres sans données de volume passent le filtre |
| 4.1c | **ADV non transmis au modèle de coût en backtest** | ❌ NON CONFORME | **P2** — voir 2.3c |

---

### 4.2 Couverture des régimes de marché

| # | Point | Verdict | Notes |
|---|-------|---------|-------|
| 4.2a | Filtre de régime SPY-based (MA + vol réalisée) | ✅ CONFORME | `simulator:534` — `MarketRegimeFilter.classify()` bloque entrées en TRENDING |
| 4.2b | Couverture stress periods (COVID mars 2020, Dotcom, GFC 2008) | ⚠️ À VÉRIFIER | Aucune preuve code de backtest sur périodes de stress explicites. Si `DEFAULT_SECTOR_MAP` ne contenait pas ces titres en 2008, les résultats GFC sont de toute façon invalides (P0 survie) |

---

### 4.3 Stabilité des paramètres

| # | Point | Verdict | Notes |
|---|-------|---------|-------|
| 4.3a | `parameter_cv.py` présent mais non invoqué par `WalkForwardEngine` | ⚠️ À VÉRIFIER | Le module cross-validation des paramètres existe dans `backtests/` mais est-il réellement utilisé dans les tests de production ? |
| 4.3b | Paramètres figés entre folds (pas de ré-optimisation) | ✅ CONFORME | `get_settings()` est immuable pendant un run |

---

## SYNTHÈSE GÉNÉRALE

### Tableau des anomalies par ordre de priorité

| ID | Sévérité | Bloc | Description | Fichier:Ligne | Impact Perf estimé | Effort correctif |
|----|---------|------|-------------|---------------|--------------------|-----------------|
| **S-01** | 🔴 **P0** | 1.3 | Biais de survie — univers hardcodé = snapshot actuel (pas point-in-time) | `universe/manager.py:DEFAULT_SECTOR_MAP` | Sharpe surestimé **+15-25%** | **Élevé** — nécessite DB point-in-time |
| **S-02** | 🟠 **P1** | 1.1 | Ambiguïté timing exécution — signal sur close barre courante, ordres non décalés à T+1 | `simulator:343` + `pair_trading.py:982` | Rendement surestimé **+5-10%** | Moyen — décaler `bar_idx` pour calcul exécution |
| **S-03** | 🟠 **P1** | 3.1 | Kill-switch : callback annulation ordres IBKR non vérifié | `risk_engine/kill_switch.py:on_activate` → `live_trading/runner.py` | Risque opérationnel ouvert | Faible — vérification câblage |
| **S-04** | 🟡 **P2** | 2.2 | Hedge ratio OLS statique — pas de mise à jour Kalman barre-par-barre | `models/spread.py:35-45` | Sharpe surestimé **+5-10%** | Moyen — activer `KalmanHedgeRatio` dans `SpreadModel` |
| **S-05** | 🟡 **P2** | 2.3 | Coût d'emprunt 0.5% (GC rate) — premium HTB non modélisé | `backtests/cost_model.py:CostModelConfig` | PnL surestimé **+1-3%/an** | Faible — lookup HTB par symbole |
| **S-06** | 🟡 **P2** | 2.3 | ADV par défaut $10M — impact marché sous-estimé sur small-caps | `backtests/cost_model.py:execution_cost_one_leg` | Slippage sous-estimé | Moyen — passer ADV réel depuis `DataLoader` |
| **S-07** | 🟡 **P2** | 3.2 | Sizing `EQUAL_WEIGHT` — ignore les volatilités différentes entre spreads | `portfolio_engine/allocator.py:SizingMethod.EQUAL_WEIGHT` | Sharpe sous-optimal, tail risk accru | Moyen — activer `VOLATILITY_INVERSE` par défaut |
| **S-08** | 🟢 P3 | 2.2 | Spread en prix niveau (non log-prix) — asymétries long terme | `models/spread.py:compute_spread()` | Mineur (paires à prix proches) | Faible |
| **S-09** | 🟢 P3 | 3.4 | `RegimeDetector` fenêtre 20 barres non adaptative | `models/regime_detector.py` | Mineur | Faible |

---

### Points forts du modèle (à conserver)

| Point | Description | Fichier |
|-------|-------------|---------|
| ✅ Triple gate sélection | EG + Johansen + Newey-West avec Bonferroni | `pair_selection/discovery.py` |
| ✅ Walk-forward propre | Fenêtre expansive, instance fraîche, critère pas de cherry-picking | `backtests/walk_forward.py` |
| ✅ Filtre de Kalman disponible | Forward-only, P matrix bien initialisée | `models/kalman_hedge.py` |
| ✅ Almgren-Chriss 3 composantes | Modèle de coût sophistiqué et réaliste pour actions | `backtests/cost_model.py` |
| ✅ Kill-switch 6 conditions | Persistance JSON, thread-safe, pré-ordre | `risk_engine/kill_switch.py` |
| ✅ PCA intrabar | Bloque les entrées si PC1 > 50% variance | `risk/pca_spread_monitor.py` |
| ✅ Code path unique backtest=live | `generate_signals()` partagé | `backtests/strategy_simulator.py` |
| ✅ Thresholds adaptatifs au régime | `AdaptiveThresholdEngine` conditionné sur `RegimeDetector` | `signal_engine/generator.py` |

---

### Verdict global

> **Le backtest EDGECORE est structurellement valide dans son architecture mais contient 1 biais invalidant (S-01) et 1 ambiguïté méthodologique sérieuse (S-02) qui doivent être corrigés avant toute présentation à des investisseurs ou passage en capital réel significatif.**

**Priorité immédiate :**
1. **S-01 (P0)** — Construire un univers point-in-time ou au minimum exclure explicitement les entreprises délistées pendant la période de test via un fichier de delisting historique.
2. **S-02 (P1)** — Clarifier et documenter la convention signal→exécution. Si les ordres sont envoyés à l'ouverture T+1, modifier `_close_position()` et `_open_position()` dans le simulateur pour utiliser `prices_df.iloc[bar_idx + 1]` comme prix d'exécution.
3. **S-03 (P1)** — Vérifier le câblage du kill-switch avec l'annulation des ordres IBKR dans `live_trading/runner.py`.

**Priorité secondaire (avant live avec capital > $100k) :**
4. **S-04** — Activer `KalmanHedgeRatio` dans `SpreadModel` pour le suivi barre-par-barre du hedge ratio.
5. **S-06** — Passer le vrai ADV (depuis `DataLoader` ou `LiquidityFilter`) au `CostModel`.
6. **S-07** — Passer `SizingMethod.VOLATILITY_INVERSE` comme défaut dans `PortfolioAllocator`.

---

*Audit basé sur lecture directe du code source — 25+ fichiers analysés — aucun test modifié.*
