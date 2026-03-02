# PLAN DE REMÉDIATION EDGECORE — OBJECTIF 10/10

**Date :** 13 février 2026  
**Source :** `AUDIT_STRATEGIQUE_EDGECORE_V2.md`  
**Objectif :** Corriger les 19 failles (6 🔴 + 8 🟠 + 5 🟡) — Scores cibles : 10/10 statistique, 10/10 robustesse  
**Probabilité de survie cible :** 80%+ à 12 mois  
**Verdict cible :** 👉 Stratégiquement exploitable avec capital réel

---

## ARCHITECTURE DU PLAN

```
PHASE 1 — FONDATIONS CRITIQUES          [Semaines 1-2]   6 🔴 → 0 🔴
PHASE 2 — SOLIDIFICATION MAJEURE        [Semaines 3-4]   8 🟠 → 0 🟠
PHASE 3 — POLISH & EXCELLENCE           [Semaine 5]      5 🟡 → 0 🟡
PHASE 4 — VALIDATION INTÉGRALE          [Semaine 6]      Preuve formelle 10/10
```

Chaque tâche est spécifiée avec :
- Faille source (ID audit)
- Fichiers impactés
- Logique exacte à implémenter
- Critère de validation (Definition of Done)
- Impact sur le score

---

## PHASE 1 — FONDATIONS CRITIQUES

> Éliminer les 6 failles 🔴 qui invalident la stratégie.  
> **Sans cette phase, rien d'autre n'a de valeur.**

---

### SPRINT 1.1 — Unifier backtest et stratégie live

**Faille :** 🔴 C-01 — Divergence backtest/live  
**Impact score :** Backtesting 2/10 → 8/10

#### Problème exact

`BacktestRunner.run()` et `PairTradingStrategy.generate_signals()` sont deux implémentations indépendantes. Le backtest n'utilise ni les seuils adaptatifs, ni les trailing stops, ni les concentration limits, ni le regime detector, ni le hedge ratio tracking.

#### Solution : créer `StrategyBacktestSimulator`

**Nouveau fichier :** `backtests/strategy_simulator.py`

```python
class StrategyBacktestSimulator:
    """
    Simule la stratégie live bar-par-bar en utilisant EXACTEMENT
    le même code que PairTradingStrategy.generate_signals().
    
    Principe : à chaque date_idx, on passe les données historiques
    [0:date_idx] à la stratégie et on collecte les signaux.
    """
    
    def __init__(self, strategy: PairTradingStrategy, cost_model: CostModel):
        self.strategy = strategy
        self.cost_model = cost_model
        self.portfolio = SimulatedPortfolio()
    
    def run(self, prices_df: pd.DataFrame, 
            pair_rediscovery_interval: int = 21) -> BacktestMetrics:
        """
        Boucle bar-par-bar :
        1. Toutes les `pair_rediscovery_interval` barres → re-découvrir paires
           sur données [max(0, idx-252):idx] uniquement (pas de look-ahead)
        2. Appeler strategy.generate_signals(hist_prices) 
        3. Appliquer les signaux avec CostModel réaliste
        4. Calculer les métriques
        """
```

**Fichiers à modifier :**

| Fichier | Action |
|---------|--------|
| `backtests/strategy_simulator.py` | **CRÉER** — Simulateur unifié |
| `backtests/runner.py` | Refactor : `run()` délègue à `StrategyBacktestSimulator` |
| `backtests/walk_forward.py` | Refactor : utiliser le simulateur au lieu de `run()` |
| `backtests/cost_model.py` | **CRÉER** — Modèle de coûts paramétrable |

**Definition of Done :**
- [ ] `StrategyBacktestSimulator.run()` appelle `PairTradingStrategy.generate_signals()` à chaque barre
- [ ] Zéro duplication de logique de signal entre backtest et live
- [ ] Test de régression : même données → même signaux entre simulateur et stratégie directe
- [ ] Trailing stops, concentration limits, regime detector actifs dans le backtest

---

### SPRINT 1.2 — Éliminer le look-ahead bias

**Faille :** 🔴 C-02 — Look-ahead bias sur la sélection des paires  
**Impact score :** Backtesting +2/10

#### Problème exact

Dans `BacktestRunner.run()`, `_find_cointegrated_pairs_in_data(prices_df)` reçoit TOUTES les données (`prices_df` complet), puis les trades sont simulés bar-par-bar. Les paires sont sélectionnées avec connaissance du futur.

#### Solution : découverte strictement in-sample

**Dans `StrategyBacktestSimulator` :**

```python
def _discover_pairs_no_lookahead(self, prices_df, current_idx, lookback=252):
    """
    Découvre les paires en utilisant UNIQUEMENT les données
    [current_idx - lookback : current_idx].
    Aucune donnée future n'est visible.
    """
    start = max(0, current_idx - lookback)
    training_window = prices_df.iloc[start:current_idx]  # STRICT: exclut current_idx
    return self.strategy.find_cointegrated_pairs(
        training_window, 
        use_cache=False,   # Pas de cache en backtest
        use_parallel=True
    )
```

**Logique temporelle :**

```
Bar 252:  découverte paires sur [0:252)     → trade bar 252
Bar 273:  re-découverte sur [21:273)        → trade bars 273-293
Bar 294:  re-découverte sur [42:294)        → trade bars 294-314
...
```

**Definition of Done :**
- [ ] À aucun moment le simulateur ne voit des données postérieures à `current_idx`
- [ ] Test formel : injecter un changement de régime à T=500, vérifier que les paires avant T=500 ne changent pas
- [ ] Les paires sont re-découvertes toutes les `pair_rediscovery_interval` barres (configurable, default 21)

---

### SPRINT 1.3 — Walk-forward réel avec re-training

**Faille :** 🔴 C-03 — Walk-forward invalide  
**Impact score :** Validation OOS 5/10 → 9/10

#### Problème exact

Le walk-forward actuel ne retraine pas le modèle entre les périodes. Le commentaire dans le code l'avoue explicitement.

#### Solution : refactorer `WalkForwardBacktester`

**Fichier :** `backtests/walk_forward.py`

```python
def run_walk_forward(self, ...):
    for period_idx, (train_df, test_df) in enumerate(splits):
        # ÉTAPE 1 : Découvrir les paires sur train_df UNIQUEMENT
        pairs = self.strategy.find_cointegrated_pairs(
            train_df, use_cache=False
        )
        
        # ÉTAPE 2 : Valider OOS sur les 20% finaux de train_df
        is_split = int(len(train_df) * 0.8)
        is_data = train_df.iloc[:is_split]
        oos_data = train_df.iloc[is_split:]
        validated_pairs, _ = self.strategy.validate_pairs_oos(
            pairs, is_data, oos_data
        )
        
        # ÉTAPE 3 : Simuler sur test_df avec paires validées uniquement
        simulator = StrategyBacktestSimulator(
            strategy=self._create_fresh_strategy(),
            cost_model=self.cost_model,
            fixed_pairs=validated_pairs  # Paires gelées pour cette période
        )
        period_metrics = simulator.run(test_df)
        
        # ÉTAPE 4 : Collecter les métriques OOS
        self.per_period_metrics.append(period_metrics)
```

**Definition of Done :**
- [ ] Chaque période de walk-forward a son propre ensemble de paires
- [ ] Les paires sont découvertes sur train_df et validées OOS avant trading
- [ ] Aucune donnée de test_df n'est visible pendant la découverte
- [ ] La stratégie est réinitialisée à chaque période (fresh state)
- [ ] Test : comparer les résultats WF avec et sans re-training — le re-training doit donner des résultats différents

---

### SPRINT 1.4 — Corriger le bypass Bonferroni Cython

**Faille :** 🔴 C-04 — Cython bypass Bonferroni  
**Impact score :** Test de cointégration 7/10 → 10/10

#### Problème exact

```python
# models/cointegration.py, ligne ~233
result_dict['is_cointegrated'] = adf_result[1] < 0.05  # ← HARDCODÉ
```

La fonction `engle_granger_test_cpp_optimized` ne propage pas `num_symbols` ni `apply_bonferroni`.

#### Solution

**Fichier :** `models/cointegration.py`

```python
def engle_granger_test_cpp_optimized(
    y: pd.Series,
    x: pd.Series,
    max_lags: int = 12,
    regression: str = "c",
    num_symbols: Optional[int] = None,      # ← AJOUTER
    apply_bonferroni: bool = True             # ← AJOUTER
) -> dict:
    # ...
    if CYTHON_COINTEGRATION_AVAILABLE:
        try:
            # ... Cython call ...
            
            # Calculer le seuil corrigé
            if apply_bonferroni and num_symbols is not None:
                num_pairs = num_symbols * (num_symbols - 1) // 2
                alpha_corrected = 0.05 / num_pairs
            else:
                alpha_corrected = 0.05
            
            result_dict['is_cointegrated'] = adf_result[1] < alpha_corrected  # ← CORRIGÉ
            result_dict['alpha_threshold'] = alpha_corrected
            result_dict['num_pairs'] = num_pairs if apply_bonferroni else None
```

**Fichier :** `backtests/runner.py` — mettre à jour tous les appels :

```python
result = engle_granger_test_cpp_optimized(
    series1, series2,
    num_symbols=len(symbols),       # ← AJOUTER
    apply_bonferroni=True            # ← AJOUTER
)
```

**Definition of Done :**
- [ ] `engle_granger_test_cpp_optimized` accepte et utilise `num_symbols` et `apply_bonferroni`
- [ ] Plus aucun `< 0.05` hardcodé
- [ ] Test : avec 50 symboles, le seuil effectif est `0.05 / 1225 ≈ 4.08e-5`
- [ ] Test de non-régression : résultats de `engle_granger_test` et `engle_granger_test_cpp_optimized` identiques à paramètres identiques

---

### SPRINT 1.5 — Time stop obligatoire

**Faille :** 🔴 C-05 — Absence de time stop  
**Impact score :** Entrée/sortie 4/10 → 7/10

#### Solution : `TimeStopManager`

**Nouveau fichier :** `execution/time_stop.py`

```python
class TimeStopManager:
    """
    Ferme les positions ouvertes trop longtemps.
    
    Règle : position fermée si durée > min(2 × half_life, max_days).
    Default max_days = 30 jours.
    """
    
    def __init__(self, max_days: int = 30, half_life_multiplier: float = 2.0):
        self.max_days = max_days
        self.hl_multiplier = half_life_multiplier
        self.positions: Dict[str, TimeStopPosition] = {}
    
    def register_entry(self, pair_key: str, entry_time: datetime, 
                       half_life: Optional[float] = None):
        time_limit = min(
            self.max_days,
            int(self.hl_multiplier * half_life) if half_life else self.max_days
        )
        self.positions[pair_key] = TimeStopPosition(
            pair_key=pair_key,
            entry_time=entry_time,
            time_limit_days=time_limit
        )
    
    def should_exit(self, pair_key: str, current_time: datetime) -> Tuple[bool, str]:
        pos = self.positions.get(pair_key)
        if pos is None:
            return False, ""
        days_held = (current_time - pos.entry_time).days
        if days_held >= pos.time_limit_days:
            return True, f"Time stop: {days_held}d >= limit {pos.time_limit_days}d"
        return False, ""
```

**Intégration dans :** `strategies/pair_trading.py` → `generate_signals()`

```python
# Après les checks de trailing stop, AVANT les exits de mean reversion :
if pair_key in self.active_trades:
    should_exit_time, time_reason = self.time_stop_manager.should_exit(
        pair_key, datetime.now()
    )
    if should_exit_time:
        signals.append(Signal(pair_key, side="exit", strength=1.0, reason=time_reason))
        # cleanup...
```

**Definition of Done :**
- [ ] Toute position est fermée après `min(2×HL, 30)` jours
- [ ] Intégré dans `generate_signals()` ET dans `StrategyBacktestSimulator`
- [ ] Test : position ouverte à T, forcée fermée à T+31 si max_days=30
- [ ] Config : `max_time_stop_days` configurable dans `StrategyConfig`

---

### SPRINT 1.6 — Matrice de corrélation des spreads

**Faille :** 🔴 C-06 — Corrélation croisée des spreads non gérée  
**Impact score :** Corrélation des positions 1/10 → 9/10

#### Solution : `SpreadCorrelationGuard`

**Nouveau fichier :** `risk/spread_correlation.py`

```python
class SpreadCorrelationGuard:
    """
    Empêche l'ouverture de positions dont le spread est corrélé
    avec un spread déjà en portefeuille.
    
    Logique :
    1. Maintenir un historique de spread (60 dernières barres) pour chaque position active
    2. Avant nouvel entry : calculer corrélation du nouveau spread 
       avec CHAQUE spread actif
    3. Rejeter si correlation > max_spread_correlation (default: 0.60)
    """
    
    def __init__(self, max_spread_correlation: float = 0.60, 
                 lookback_bars: int = 60):
        self.max_corr = max_spread_correlation
        self.lookback = lookback_bars
        self.active_spreads: Dict[str, pd.Series] = {}
    
    def can_add_position(self, pair_key: str, 
                         new_spread: pd.Series) -> Tuple[bool, Optional[str]]:
        """
        Vérifie que le spread n'est pas trop corrélé avec les spreads actifs.
        """
        for active_key, active_spread in self.active_spreads.items():
            # Aligner les séries sur l'intersection temporelle
            common_idx = new_spread.index.intersection(active_spread.index)
            if len(common_idx) < 20:
                continue
            
            corr = new_spread.loc[common_idx].corr(active_spread.loc[common_idx])
            
            if abs(corr) > self.max_corr:
                return False, (
                    f"Spread {pair_key} corrélé à {corr:.2f} avec {active_key} "
                    f"(max: {self.max_corr})"
                )
        
        return True, None
    
    def register_position(self, pair_key: str, spread: pd.Series):
        self.active_spreads[pair_key] = spread.tail(self.lookback)
    
    def remove_position(self, pair_key: str):
        self.active_spreads.pop(pair_key, None)
    
    def get_correlation_matrix(self) -> pd.DataFrame:
        """Retourne la matrice de corrélation de tous les spreads actifs."""
        if len(self.active_spreads) < 2:
            return pd.DataFrame()
        df = pd.DataFrame(self.active_spreads)
        return df.corr()
```

**Intégration dans :** `strategies/pair_trading.py` → avant chaque `signals.append()` d'entrée

```python
# Avant l'entrée long ou short :
can_add, corr_reason = self.spread_correlation_guard.can_add_position(
    pair_key, spread.tail(60)
)
if not can_add:
    logger.info("signal_skipped_spread_correlation", pair=pair_key, reason=corr_reason)
    continue

# Si accepté, après l'ajout :
self.spread_correlation_guard.register_position(pair_key, spread)
```

**Definition of Done :**
- [ ] Toute nouvelle position est vérifiée contre la matrice de corrélation des spreads existants
- [ ] Seuil configurable (`max_spread_correlation` dans `RiskConfig`)
- [ ] Test : 3 paires corrélées à 0.9 → seule la première est acceptée
- [ ] La matrice de corrélation est loguée à chaque tick pour monitoring
- [ ] Intégré dans le backtest simulator ET dans la stratégie live

---

## PHASE 2 — SOLIDIFICATION MAJEURE

> Corriger les 8 failles 🟠 qui fragilisent la stratégie.

---

### SPRINT 2.1 — Monitoring continu de stationnarité

**Faille :** 🟠 M-01 — Stationnarité supposée entre re-tests  
**Impact score :** Résistance aux régimes 5/10 → 8/10

#### Solution : `StationarityMonitor`

**Nouveau fichier :** `models/stationarity_monitor.py`

```python
class StationarityMonitor:
    """
    Vérifie en continu (bar-par-bar) si le spread reste stationnaire
    via un test ADF rolling rapide.
    
    Si le spread perd sa stationnarité :
    → Signal d'alerte au TradeManager
    → Fermeture de la position recommandée
    """
    
    def __init__(self, window: int = 60, alert_pvalue: float = 0.10):
        self.window = window
        self.alert_pvalue = alert_pvalue
    
    def check_stationarity(self, spread: pd.Series) -> Tuple[bool, float]:
        """
        Test ADF rapide sur les `window` dernières observations.
        
        Returns:
            (is_stationary, current_pvalue)
        """
        if len(spread) < self.window:
            return True, 0.0  # Pas assez de données, présumer OK
        
        recent = spread.tail(self.window).values
        adf_result = adfuller(recent, regression='c', autolag='AIC')
        pvalue = adf_result[1]
        
        return pvalue < self.alert_pvalue, pvalue
```

**Intégration :** dans `generate_signals()`, après le calcul du spread et AVANT l'évaluation du z-score :

```python
is_stationary, stationarity_pval = self.stationarity_monitor.check_stationarity(spread)
if not is_stationary:
    # Si position ouverte → fermer
    if pair_key in self.active_trades:
        signals.append(Signal(pair_key, "exit", 1.0,
            f"Stationarity lost: p={stationarity_pval:.4f}"))
    # Si pas en position → ne pas entrer
    continue
```

**Definition of Done :**
- [ ] ADF rolling exécuté à chaque barre pour chaque paire active
- [ ] Perte de stationnarité → fermeture immédiate + pas de nouvelles entrées
- [ ] Seuil `alert_pvalue=0.10` configurable
- [ ] Impact perf mesuré : ADF sur 60 observations < 5ms (acceptable bar-par-bar)
- [ ] Test : injecter un random walk après bar 200 → position fermée à bar 201

---

### SPRINT 2.2 — Granularité de détection accélérée

**Faille :** 🟠 M-02 — Granularité de détection insuffisante  
**Impact score :** Résistance aux régimes → 9/10

#### Actions

**Fichier :** `models/hedge_ratio_tracker.py`
- Réduire `reestimation_frequency_days` : 30 → **7 jours**
- Ajouter un mode `emergency_reestimate` déclenché si la volatilité du spread > 3σ

**Fichier :** `models/regime_detector.py`
- Réduire `min_regime_duration` : 3 → **1 bar** (réactivité maximale)
- Ajouter un mode `instant_transition` pour les spikes de volatilité > 99e percentile

**Fichier :** `config/settings.py`
- Ajouter dans `StrategyConfig` :
  ```python
  hedge_ratio_reestimation_days: int = 7
  regime_min_duration: int = 1
  emergency_vol_threshold_percentile: float = 99.0
  ```

**Definition of Done :**
- [ ] Hedge ratio check toutes les 7 barres (pas 30)
- [ ] Régime detector réagit en 1 barre au lieu de 3
- [ ] Mode d'urgence : si vol 99e percentile, transition immédiate + re-estimation forcée du hedge ratio
- [ ] Tests mis à jour avec les nouvelles valeurs

---

### SPRINT 2.3 — Modèle de frais réaliste

**Faille :** 🟠 M-03 — Frais sous-estimés  
**Impact score :** Coûts réalistes 4/10 → 10/10

#### Solution : `RealisticCostModel`

**Nouveau fichier :** `backtests/cost_model.py`

```python
@dataclass
class CostModelConfig:
    maker_fee_bps: float = 10.0      # 0.10%
    taker_fee_bps: float = 10.0      # 0.10%
    slippage_model: str = "volume_adaptive"  # fixed, volume_adaptive
    base_slippage_bps: float = 5.0
    funding_rate_daily_bps: float = 1.0  # Si futures
    borrowing_cost_annual_pct: float = 5.0  # Coût d'emprunt pour short
    include_funding: bool = False
    include_borrowing: bool = True


class RealisticCostModel:
    """
    Modèle de coûts 4-legs : 
    Entry (long leg + short leg) + Exit (close long + close short)
    = 4 × (fee + slippage)
    + holding cost (borrowing + funding) × durée
    """
    
    def calculate_round_trip_cost(
        self, 
        notional_per_leg: float,
        volume_24h_sym1: float,
        volume_24h_sym2: float,
        holding_days: int = 0
    ) -> float:
        # Legs entry + exit = 4 transactions
        fee_per_tx = self.config.taker_fee_bps / 10000
        
        # Slippage adaptatif à la liquidité
        slip_sym1 = self._adaptive_slippage(notional_per_leg, volume_24h_sym1)
        slip_sym2 = self._adaptive_slippage(notional_per_leg, volume_24h_sym2)
        
        # Total execution cost
        execution_cost = notional_per_leg * 2 * (  # 2 legs
            2 * fee_per_tx +                          # entry + exit
            (slip_sym1 + slip_sym2)                    # slippage
        )
        
        # Holding cost
        if self.config.include_borrowing:
            daily_borrow = notional_per_leg * (self.config.borrowing_cost_annual_pct / 100 / 365)
            execution_cost += daily_borrow * holding_days
        
        return execution_cost
    
    def _adaptive_slippage(self, order_size: float, volume_24h: float) -> float:
        """
        Slippage = base + impact × (order_size / volume_24h)
        Plus le ratio order/volume est grand, plus le slippage augmente.
        """
        if volume_24h <= 0:
            return 50 / 10000  # Worst case: 50 bps
        
        participation_rate = order_size / volume_24h
        impact_bps = self.config.base_slippage_bps + 100 * participation_rate
        return min(impact_bps, 100) / 10000  # Cap à 100 bps
```

**Intégration :** remplacer les constantes `COMMISSION_BPS` / `SLIPPAGE_BPS` dans `runner.py` par `RealisticCostModel`.

**Definition of Done :**
- [ ] 4 legs comptabilisés (long entry + short entry + long exit + short exit)
- [ ] Slippage adaptatif au volume 24h du symbole
- [ ] Borrowing cost pour le short leg
- [ ] Frais totaux réalistes ≥ 40 bps round-trip (vs 30 bps avant)
- [ ] Test : un trade sur POPCAT avec $1000 et volume_24h=$50K → slippage > 20 bps

---

### SPRINT 2.4 — Filtre de liquidité dynamique

**Faille :** 🟠 M-04 — Survivorship/selection bias dans l'univers  
**Impact score :** Gestion de la liquidité 2/10 → 9/10

#### Actions

**1. Filtre de liquidité dans le pair discovery**

**Fichier :** `strategies/pair_trading.py` → `find_cointegrated_pairs`

```python
def _filter_by_liquidity(self, symbols: List[str], 
                          price_data: pd.DataFrame,
                          min_volume_24h_usd: float = 5_000_000) -> List[str]:
    """Exclure les symboles dont le volume 24h < seuil."""
    filtered = []
    for sym in symbols:
        if sym in price_data.columns:
            # Estimer le volume moyen sur 30 jours
            if hasattr(price_data[sym], 'volume'):
                avg_vol = price_data[sym].tail(30).mean()
                if avg_vol >= min_volume_24h_usd:
                    filtered.append(sym)
            else:
                filtered.append(sym)  # Pas de volume dispo → accepter
    return filtered
```

**2. Nettoyage de l'univers**

**Fichier :** `config/dev.yaml`
- Supprimer `FTT/USD` (token FTX effondré)
- Supprimer le doublon `BAC`
- Ajouter un commentaire : symboles validés au 2026-02-13

**Fichier :** `config/prod.yaml`
- Supprimer `POPCAT/USD`, `MOG/USD`, `GOAT/USD` (liquidité < $1M/jour)
- Supprimer `FTT/USD`
- Ajouter filtre dynamique de volume

**3. DelistingGuard**

**Nouveau fichier :** `data/delisting_guard.py`

```python
class DelistingGuard:
    """
    Détecte les tokens en voie de delisting :
    - Volume chutant > 80% sur 7 jours
    - Prix < $0.001
    - Pas de données depuis > 3 jours
    """
    def is_safe(self, symbol: str, recent_data: pd.Series) -> bool:
        ...
```

**Definition of Done :**
- [ ] Filtre de liquidité min $5M/jour (configurable)
- [ ] FTT, LUNC retirés de dev.yaml ; tokens < $1M/jour retirés de prod.yaml
- [ ] Doublon BAC corrigé
- [ ] DelistingGuard détecte les tokens mourants
- [ ] Test : injecter un token avec volume $100K → exclu du discovery

---

### SPRINT 2.5 — Validation OOS du ML threshold optimizer

**Faille :** 🟠 M-05 — ML threshold optimizer non validé OOS  
**Impact score :** Entrée/sortie → 9/10

#### Solution : walk-forward cross-validation sur le ML

**Fichier :** `models/ml_threshold_optimizer.py`

Ajouter :

```python
class MLThresholdValidator:
    """
    Walk-forward CV du ML threshold optimizer.
    
    1. Diviser les données en 5 folds temporels
    2. Pour chaque fold : train sur [0:fold], test sur [fold:fold+1]
    3. Métrique : precision@0.6 en OOS (le seuil optimal OOS doit être 
       meilleur que le seuil fixe)
    4. Si OOS degradation > 20% vs IS → désactiver le ML et utiliser les seuils fixes
    """
    
    def validate_oos_performance(self, data: pd.DataFrame, 
                                  n_folds: int = 5) -> ValidationResult:
        ...
    
    def should_use_ml_thresholds(self) -> bool:
        """
        Si la performance ML OOS < 80% de IS → utiliser seuils fixes.
        Anti-overfitting automatique.
        """
        return self.oos_score >= 0.8 * self.is_score
```

**Fallback :** si le ML ne valide pas en OOS, les seuils adaptatifs heuristiques (volatilité + half-life) restent actifs. Seul le composant RF est désactivé.

**Definition of Done :**
- [ ] Walk-forward CV à 5 folds temporels implémenté
- [ ] Désactivation automatique si dégradation OOS > 20%
- [ ] Log explicite : "ML thresholds disabled: OOS degradation 35%"
- [ ] Test : données random → ML désactivé automatiquement

---

### SPRINT 2.6 — Supprimer le fallback synthétique

**Faille :** 🟠 M-06 — Fallback synthétique dans le backtest  
**Impact score :** Backtesting → 10/10

#### Action

**Fichier :** `backtests/runner.py` — SUPPRIMER le bloc :

```python
# ❌ SUPPRIMER ENTIÈREMENT :
if len(cointegrated_pairs) == 0:
    logger.warning("backtest_no_cointegrated_pairs")
    # Fallback: Generate a synthetic cointegrated pair
    np.random.seed(42)
    # ... tout le bloc synthétique ...
```

**Remplacer par :**

```python
if len(cointegrated_pairs) == 0:
    logger.error("backtest_no_cointegrated_pairs_ABORT", symbols=list(price_data.keys()))
    return BacktestMetrics.from_returns(
        returns=pd.Series([0.0]),
        trades=[],
        start_date=start_date,
        end_date=end_date,
        note="NO_PAIRS_FOUND - backtest non exploitable"
    )
```

**Definition of Done :**
- [ ] Aucune donnée synthétique générée dans le backtest
- [ ] Si 0 paires trouvées → retour d'un résultat vide avec flag explicite
- [ ] Test : backtest avec symboles non-cointégrés → retour `total_return=0`, `note=NO_PAIRS_FOUND`

---

### SPRINT 2.7 — Test I(1) pré-cointégration

**Faille :** 🟠 M-07 — Pas de test de racine unitaire sur les séries individuelles  
**Impact score :** Test de cointégration → 10/10

#### Solution : ADF + KPSS en pré-screening

**Fichier :** `models/cointegration.py` — Ajouter :

```python
def verify_integration_order(series: pd.Series, name: str = "") -> dict:
    """
    Vérifie que la série est I(1) : non-stationnaire en niveau, stationnaire en différences.
    
    Tests :
    1. ADF sur niveau : p > 0.05 (non-stationnaire → OK pour I(1))
    2. KPSS sur niveau : p < 0.05 (rejet de stationnarité → OK pour I(1))
    3. ADF sur diff : p < 0.05 (stationnaire après différenciation → I(1) confirmé)
    """
    from statsmodels.tsa.stattools import adfuller, kpss
    
    # Niveau
    adf_level = adfuller(series.dropna(), regression='c', autolag='AIC')
    kpss_level = kpss(series.dropna(), regression='c', nlags='auto')
    
    # Différences
    diff = series.diff().dropna()
    adf_diff = adfuller(diff, regression='c', autolag='AIC')
    
    is_I1 = (
        adf_level[1] > 0.05 and     # Non-stationnaire en niveau
        kpss_level[1] < 0.05 and     # KPSS confirme non-stationnarité
        adf_diff[1] < 0.05            # Stationnaire en différences
    )
    
    return {
        'series_name': name,
        'is_I1': is_I1,
        'adf_level_pvalue': adf_level[1],
        'kpss_level_pvalue': kpss_level[1],
        'adf_diff_pvalue': adf_diff[1]
    }
```

**Intégration dans `engle_granger_test()` :**

```python
# Au début de engle_granger_test(), AVANT l'OLS :
y_order = verify_integration_order(y, "y")
x_order = verify_integration_order(x, "x")

if not y_order['is_I1'] or not x_order['is_I1']:
    return {
        'is_cointegrated': False,
        'error': f"Series not I(1): y={y_order['is_I1']}, x={x_order['is_I1']}"
        # ...
    }
```

**Definition of Done :**
- [ ] ADF + KPSS exécutés sur chaque série AVANT le test de cointégration
- [ ] Paires rejetées si une série n'est pas I(1)
- [ ] Test : série stationnaire (I(0)) → rejet explicite
- [ ] Test : random walk (I(1)) → accepté
- [ ] Performance : ADF+KPSS < 10ms par série (acceptable)

---

### SPRINT 2.8 — Pipeline d'outliers pré-signal

**Faille :** 🟠 M-08 — Absence de gestion des outliers  
**Impact score :** Construction du spread 6/10 → 9/10

#### Solution : intégrer `remove_outliers` dans le pipeline

**Fichier :** `strategies/pair_trading.py` → dans `generate_signals`, après le chargement des prix :

```python
from data.preprocessing import remove_outliers

# Nettoyer les outliers AVANT le calcul du spread
y_clean = remove_outliers(y, method="zscore", threshold=4.0)
x_clean = remove_outliers(x, method="zscore", threshold=4.0)

# Remplacer les NaN résultants par forward fill
y_clean = y_clean.ffill().bfill()
x_clean = x_clean.ffill().bfill()

# Utiliser les séries nettoyées pour le spread
model = DynamicSpreadModel(y_clean, x_clean, ...)
spread = model.compute_spread(y_clean, x_clean)
```

**Fichier :** `models/spread.py` → `compute_z_score` → protection supplémentaire :

```python
def compute_z_score(self, spread, lookback=None, half_life=None):
    # ... calcul existant ...
    
    # Clamp Z-score à [-6, 6] pour éviter les signaux sur outliers résiduels
    z_score = z_score.clip(-6.0, 6.0)
    
    return z_score
```

**Definition of Done :**
- [ ] `remove_outliers(threshold=4σ)` appliqué à chaque série de prix AVANT le spread
- [ ] Z-score clampé à [-6, +6]
- [ ] Test : injecter un spike de +50% sur une barre → pas de signal aberrant
- [ ] Test de non-régression : sur données propres, résultats identiques (threshold 4σ ne touche pas les données normales)

---

## PHASE 3 — POLISH & EXCELLENCE

> Corriger les 5 failles 🟡 et ajouter les optimisations différenciantes.

---

### SPRINT 3.1 — Annualisation equity correcte

**Faille :** 🟡 m-01 — Annualisation √252 vs √365  
**Impact score :** Métriques → perfectionnement

**Fichier :** `backtests/metrics.py`

```python
# Remplacer :
sharpe_ratio = (returns.mean() / returns.std()) * np.sqrt(252)
# Par :
CRYPTO_TRADING_DAYS = 365  # equity trade market hours/365
sharpe_ratio = (returns.mean() / returns.std()) * np.sqrt(CRYPTO_TRADING_DAYS)

# Idem pour Sortino :
sortino_ratio = (returns.mean() / downside_returns.std()) * np.sqrt(CRYPTO_TRADING_DAYS)
```

**Definition of Done :**
- [ ] Constante `CRYPTO_TRADING_DAYS = 365` définie et utilisée partout
- [ ] Sharpe, Sortino, Calmar recalculés avec √365
- [ ] Test mis à jour

---

### SPRINT 3.2 — Unifier l'estimation de half-life

**Faille :** 🟡 m-02 — Half-life estimation en double  
**Impact score :** Cohérence interne

**Action :** Faire de `SpreadHalfLifeEstimator` la seule source de vérité.

**Fichier :** `models/cointegration.py` → `half_life_mean_reversion()`

```python
def half_life_mean_reversion(spread: pd.Series, max_lag: int = 60) -> Optional[int]:
    """Delegate to SpreadHalfLifeEstimator for single source of truth."""
    estimator = SpreadHalfLifeEstimator(lookback=min(252, len(spread)))
    hl = estimator.estimate_half_life_from_spread(spread, validate=True)
    return int(np.round(hl)) if hl is not None else None
```

**Definition of Done :**
- [ ] Une seule implémentation AR(1) dans `SpreadHalfLifeEstimator`
- [ ] `half_life_mean_reversion()` est un wrapper qui délègue
- [ ] Test de non-régression : mêmes résultats qu'avant sur les cas de test existants

---

### SPRINT 3.3 — Nettoyage de l'univers YAML

**Faille :** 🟡 m-03 — BAC dupliqué  
**Impact score :** Propreté de configuration

**Fichier :** `config/dev.yaml`
- Supprimer la deuxième occurrence de `BAC`
- Supprimer `FTT/USD`
- Ajouter commentaire de date de dernière validation

**Definition of Done :**
- [ ] Aucun doublon dans dev.yaml ni prod.yaml
- [ ] Validation automatique (script ou test) détectant les doublons

---

### SPRINT 3.4 — Tests rigoureux avec assertions de valeur

**Faille :** 🟡 m-04 — Tests trop permissifs  
**Impact score :** Confiance dans la suite de tests

#### Actions

**Fichiers :** tous les fichiers `tests/**`

Renforcer les assertions :

```python
# AVANT (trop permissif) :
assert regime_state is not None
assert regime_state.regime in [VolatilityRegime.LOW, VolatilityRegime.NORMAL, VolatilityRegime.HIGH]

# APRÈS (assertion de valeur) :
assert regime_state.regime == VolatilityRegime.HIGH, \
    f"Expected HIGH regime for vol spike, got {regime_state.regime}"
```

**Tests à ajouter/renforcer :**

| Test | Assertion manquante |
|------|---------------------|
| `test_strategy.py` | Z=2.5 → signal long ; Z=-2.5 → signal short ; Z=0.3 → no signal |
| `test_regime_detector.py` | Volatilité 99e percentile → HIGH (pas "any of the three") |
| `test_backtest_runner.py` | Vérifier que les trades sont réellement exécutés (count > 0) |
| `test_oos_validator.py` | Supprimer les `if result.oos_half_life:` guards → assert direct |
| `test_walk_forward.py` | Vérifier le data leakage : train.index.max() < test.index.min() |

**Nouveau test :** `tests/integration/test_end_to_end.py`

```python
def test_full_pipeline_no_leakage():
    """
    Test intégral : data → strategy → risk → metrics
    Vérifie qu'aucune donnée future n'est utilisée.
    """
    ...

def test_backtest_matches_live_signals():
    """
    Vérifie que le StrategyBacktestSimulator produit
    les mêmes signaux que PairTradingStrategy.generate_signals()
    sur les mêmes données.
    """
    ...
```

**Definition of Done :**
- [ ] Tous les tests de régime vérifient la valeur exacte attendue
- [ ] Tests de signal vérifient la direction (long/short) pour des z-scores donnés
- [ ] Test end-to-end data → metrics sans mocking
- [ ] Test anti-leakage formel
- [ ] Couverture : chaque faille corrigée a au moins 2 tests dédiés

---

### SPRINT 3.5 — Cache adaptatif

**Faille :** 🟡 m-05 — Cache de 24h trop long  
**Impact score :** Réactivité live

**Fichier :** `strategies/pair_trading.py`

```python
def load_cached_pairs(self, max_age_hours: int = None) -> Optional[List[Tuple]]:
    """
    Adapte le TTL du cache au régime de marché :
    - Régime NORMAL : 12h (default)
    - Régime HIGH : 2h (re-découverte fréquente en haute vol)
    - Régime LOW : 24h (marché calme, paires stables)
    """
    if max_age_hours is None:
        current_regime = self.regime_detector.current_regime
        if current_regime == VolatilityRegime.HIGH:
            max_age_hours = 2
        elif current_regime == VolatilityRegime.LOW:
            max_age_hours = 24
        else:
            max_age_hours = 12
```

**Definition of Done :**
- [ ] TTL du cache adapté au régime de marché
- [ ] HIGH → 2h, NORMAL → 12h, LOW → 24h
- [ ] Test : simuler régime HIGH → cache expiré après 3h

---

## PHASE 4 — VALIDATION INTÉGRALE & OPTIMISATIONS AVANCÉES

> Prouver formellement que les scores sont 10/10.  
> Ajouter les optimisations qui différencient EDGECORE.

---

### SPRINT 4.1 — Test Johansen multi-varié

**Impact score :** Test de cointégration → 10/10 (certification complète)

**Nouveau fichier :** `models/johansen.py`

```python
from statsmodels.tsa.vector_ar.vecm import coint_johansen

class JohansenCointegrationTest:
    """
    Test de Johansen pour détecter les relations de cointégration multi-variées.
    
    Complémente Engle-Granger (bivarié) :
    - Détecte le rang de cointégration (combien de relations linéaires)
    - Permet les systèmes de plus de 2 variables
    - Plus puissant que EG pour les petits échantillons
    """
    
    def test(self, data: pd.DataFrame, det_order: int = 0, 
             k_ar_diff: int = 1) -> dict:
        result = coint_johansen(data.values, det_order=det_order, k_ar_diff=k_ar_diff)
        
        # Trace test
        trace_stat = result.lr1
        trace_crit = result.cvt  # 90%, 95%, 99%
        
        # Max eigenvalue test  
        max_eig_stat = result.lr2
        max_eig_crit = result.cvm
        
        # Déterminer le rang de cointégration
        rank = 0
        for i in range(len(trace_stat)):
            if trace_stat[i] > trace_crit[i, 1]:  # 95% critical value
                rank += 1
            else:
                break
        
        return {
            'rank': rank,
            'trace_statistics': trace_stat.tolist(),
            'trace_critical_95': trace_crit[:, 1].tolist(),
            'max_eig_statistics': max_eig_stat.tolist(),
            'eigenvectors': result.evec.tolist(),
            'is_cointegrated': rank >= 1
        }
```

**Intégration :** si Engle-Granger détecte une paire, confirmer avec Johansen (double validation).

**Definition of Done :**
- [ ] Johansen implémenté et appelable
- [ ] Utilisé en confirmation après EG (double screening : EG + Johansen)
- [ ] Test : paire connue cointégrée → rang ≥ 1
- [ ] Test : paire random → rang = 0

---

### SPRINT 4.2 — Kalman Filter pour hedge ratio dynamique

**Impact score :** Construction du spread 6/10 → 10/10

**Nouveau fichier :** `models/kalman_hedge.py`

```python
class KalmanHedgeRatio:
    """
    Estimation dynamique du hedge ratio via Kalman Filter.
    
    Remplace l'OLS statique par un β adaptatif bar-par-bar :
    - État : β_t (hedge ratio au temps t)
    - Observation : y_t = β_t × x_t + ε_t
    - Transition : β_t = β_{t-1} + η_t
    
    Avantages :
    - Pas besoin de fenêtre rolling (adapte lisiblement)
    - Détecte les breakdowns en temps réel (innovation > threshold)
    - Produit un β avec intervalle de confiance
    """
    
    def __init__(self, delta: float = 1e-4, ve: float = 1e-3):
        self.delta = delta  # Vitesse d'adaptation
        self.ve = ve        # Variance d'observation
        self.beta = None
        self.P = None       # Covariance de l'état
        self.R = None       # Covariance d'observation
    
    def update(self, y: float, x: float) -> Tuple[float, float, float]:
        """
        Met à jour le hedge ratio avec une nouvelle observation.
        
        Returns:
            (beta, spread, innovation)
        """
        if self.beta is None:
            self.beta = y / x if x != 0 else 1.0
            self.P = 1.0
            self.R = self.ve
            return self.beta, 0.0, 0.0
        
        # Prediction
        beta_pred = self.beta
        P_pred = self.P + self.delta
        
        # Innovation
        spread = y - beta_pred * x
        S = x * P_pred * x + self.R
        
        # Kalman gain
        K = P_pred * x / S
        
        # Update
        self.beta = beta_pred + K * spread
        self.P = (1 - K * x) * P_pred
        
        # Innovation normalisée (pour détection de breakdown)
        innovation = spread / np.sqrt(S) if S > 0 else 0.0
        
        return self.beta, spread, innovation
```

**Intégration :** `DynamicSpreadModel` utilise `KalmanHedgeRatio` au lieu de OLS fixe.

**Definition of Done :**
- [ ] Kalman Filter produit un β adaptatif bar-par-bar
- [ ] Innovation normalisée > 3σ → alerte breakdown
- [ ] Test : changement structurel de β → Kalman s'adapte en < 20 barres
- [ ] Comparaison formelle : Kalman vs OLS rolling sur 3 ans de données → Kalman meilleur Sharpe

---

### SPRINT 4.3 — Newey-West HAC et robustesse OLS

**Impact score :** Construction du spread → 10/10

**Fichier :** `models/cointegration.py`

```python
def engle_granger_test_robust(y, x, ...):
    """Version avec erreurs standards Newey-West HAC."""
    import statsmodels.api as sm
    
    X = sm.add_constant(x.values)
    model = sm.OLS(y.values, X)
    
    # Newey-West HAC pour autocorrélation et hétéroscédasticité
    results = model.fit(cov_type='HAC', cov_kwds={'maxlags': 12})
    
    residuals = results.resid
    beta = results.params[1]
    intercept = results.params[0]
    
    # ADF sur résidus
    adf_result = adfuller(residuals, regression='c', autolag='AIC')
    # ...
```

**Definition of Done :**
- [ ] OLS avec erreurs HAC Newey-West implémenté
- [ ] Utilisé en parallèle de l'OLS standard pour comparaison
- [ ] Si les conclusions divergent → paire rejetée (consensus requis)

---

### SPRINT 4.4 — Self-contained risk dans la stratégie

**Impact score :** Dépendance au risk engine 3/10 → 10/10

**Fichier :** `strategies/pair_trading.py`

Ajouter des gardes INTERNES à la stratégie (indépendants du risk engine) :

```python
class PairTradingStrategy(BaseStrategy):
    def __init__(self):
        # ... existant ...
        
        # Self-contained risk limits (stratégie autonome)
        self.max_positions = 8  # La stratégie elle-même limite à 8
        self.max_drawdown_pct = 0.10  # Arrêt si DD > 10% depuis le peak
        self.max_daily_trades = 20    # Pas plus de 20 trades/jour
        self.daily_trade_count = 0
        self.peak_equity = None
        self.current_equity = None
    
    def _check_internal_risk_limits(self) -> Tuple[bool, str]:
        """
        Vérifie les limites de risque INTERNES à la stratégie.
        Indépendant du RiskEngine externe.
        """
        if len(self.active_trades) >= self.max_positions:
            return False, f"Internal max positions ({self.max_positions}) reached"
        
        if self.daily_trade_count >= self.max_daily_trades:
            return False, f"Internal max daily trades ({self.max_daily_trades}) reached"
        
        if self.peak_equity and self.current_equity:
            dd = (self.peak_equity - self.current_equity) / self.peak_equity
            if dd > self.max_drawdown_pct:
                return False, f"Internal drawdown limit ({dd:.1%} > {self.max_drawdown_pct:.1%})"
        
        return True, ""
```

**Definition of Done :**
- [ ] La stratégie a ses propres limites (max positions, max drawdown, max daily trades)
- [ ] Ces limites sont PLUS strictes que le risk engine (defense in depth)
- [ ] Test : sans risk engine, la stratégie se protège elle-même
- [ ] Le risk engine reste actif comme deuxième couche de protection

---

### SPRINT 4.5 — Event-driven backtester avec order book

**Impact score :** Scénarios extrêmes 4/10 → 10/10

**Nouveau fichier :** `backtests/event_driven.py`

```python
class EventDrivenBacktester:
    """
    Backtester event-driven avec simulation de carnet d'ordres.
    
    Au lieu de boucler bar-par-bar avec Fill-at-Close :
    - Simule un carnet d'ordres avec spread bid/ask
    - Les ordres sont des limit orders au mid ± slippage
    - Partial fills si la taille dépasse X% du volume
    - Gaps de prix entre barres créent du slippage supplémentaire
    """
    
    def __init__(self, strategy, cost_model, book_depth_pct: float = 0.02):
        self.strategy = strategy
        self.cost_model = cost_model
        self.book_depth_pct = book_depth_pct
    
    def simulate_fill(self, order, market_state) -> Fill:
        """
        Simule le fill d'un ordre avec :
        - Bid/ask spread estimé (2× slippage)
        - Participation rate → partial fill si > 5% du volume
        - Impact de prix proportionnel à la taille
        """
        ...
```

**Definition of Done :**
- [ ] Simulation de fill réaliste avec bid/ask spread
- [ ] Partial fills si ordre > 5% du volume
- [ ] Impact de marché proportionnel à la taille
- [ ] Test : comparaison avec l'ancien backtest → résultats plus pessimistes (confirmation réalisme)

---

### SPRINT 4.6 — Monitoring de corrélation rolling entre legs

**Impact score :** Résistance aux régimes → 10/10

**Fichier :** `strategies/pair_trading.py`

```python
def _check_leg_correlation_stability(self, y: pd.Series, x: pd.Series, 
                                       pair_key: str, window: int = 30) -> bool:
    """
    Vérifie que la corrélation entre les deux legs reste stable.
    Si la corrélation chute > 30% vs la moyenne historique → signal d'alerte.
    """
    if len(y) < window * 2:
        return True
    
    recent_corr = y.tail(window).corr(x.tail(window))
    historical_corr = y.tail(window * 4).corr(x.tail(window * 4))
    
    if abs(recent_corr) < 0.5 * abs(historical_corr):
        logger.warning("leg_correlation_breakdown", pair=pair_key,
                       recent=recent_corr, historical=historical_corr)
        return False
    
    return True
```

**Intégration :** avant `generate_signals()`, vérifier la corrélation des legs → si breakdown, fermer la position.

**Definition of Done :**
- [ ] Corrélation rolling calculée à chaque barre pour chaque paire active
- [ ] Chute > 50% → position fermée + paire exclue
- [ ] Monitoring logué pour analytics

---

## MATRICE DE TRAÇABILITÉ FAILLE → CORRECTION

| ID | Faille | Sprint | Fichiers principaux | Score impacté |
|----|--------|--------|---------------------|---------------|
| 🔴 C-01 | Divergence backtest/live | 1.1 | `backtests/strategy_simulator.py` (nouveau), `runner.py` | Backtesting 2→8 |
| 🔴 C-02 | Look-ahead bias | 1.2 | `backtests/strategy_simulator.py` | Backtesting +2 |
| 🔴 C-03 | Walk-forward invalide | 1.3 | `backtests/walk_forward.py` | Validation OOS 5→9 |
| 🔴 C-04 | Cython bypass Bonferroni | 1.4 | `models/cointegration.py`, `backtests/runner.py` | Cointégration 7→10 |
| 🔴 C-05 | Absence time stop | 1.5 | `execution/time_stop.py` (nouveau), `strategies/pair_trading.py` | Entrée/sortie 4→7 |
| 🔴 C-06 | Corrélation spreads | 1.6 | `risk/spread_correlation.py` (nouveau), `strategies/pair_trading.py` | Corrélation 1→9 |
| 🟠 M-01 | Stationnarité supposée | 2.1 | `models/stationarity_monitor.py` (nouveau) | Régimes 5→8 |
| 🟠 M-02 | Granularité détection | 2.2 | `hedge_ratio_tracker.py`, `regime_detector.py`, `settings.py` | Régimes →9 |
| 🟠 M-03 | Frais sous-estimés | 2.3 | `backtests/cost_model.py` (nouveau), `runner.py` | Coûts 4→10 |
| 🟠 M-04 | Survivorship bias | 2.4 | `dev.yaml`, `prod.yaml`, `data/delisting_guard.py` (nouveau) | Liquidité 2→9 |
| 🟠 M-05 | ML non validé OOS | 2.5 | `models/ml_threshold_optimizer.py` | Entrée/sortie →9 |
| 🟠 M-06 | Fallback synthétique | 2.6 | `backtests/runner.py` | Backtesting →10 |
| 🟠 M-07 | Pas de test I(1) | 2.7 | `models/cointegration.py` | Cointégration →10 |
| 🟠 M-08 | Pas d'outliers | 2.8 | `strategies/pair_trading.py`, `models/spread.py` | Spread 6→9 |
| 🟡 m-01 | √252 vs √365 | 3.1 | `backtests/metrics.py` | Métriques |
| 🟡 m-02 | Half-life double | 3.2 | `models/cointegration.py` | Spread →10 |
| 🟡 m-03 | BAC doublon | 3.3 | `config/dev.yaml` | Config |
| 🟡 m-04 | Tests permissifs | 3.4 | `tests/**` | Confiance |
| 🟡 m-05 | Cache 24h | 3.5 | `strategies/pair_trading.py` | Réactivité |
| — | Johansen | 4.1 | `models/johansen.py` (nouveau) | Cointégration 10/10 |
| — | Kalman hedge | 4.2 | `models/kalman_hedge.py` (nouveau) | Spread 10/10 |
| — | Newey-West HAC | 4.3 | `models/cointegration.py` | Spread 10/10 |
| — | Self-contained risk | 4.4 | `strategies/pair_trading.py` | Dépendance →10 |
| — | Event-driven backtest | 4.5 | `backtests/event_driven.py` (nouveau) | Scénarios 10/10 |
| — | Corrélation legs rolling | 4.6 | `strategies/pair_trading.py` | Régimes 10/10 |

---

## PROJECTION DES SCORES POST-REMÉDIATION

### Qualité statistique : 10 / 10

| Composante | Avant | Après Phase 1 | Après Phase 2 | Après Phase 4 |
|-----------|-------|---------------|---------------|---------------|
| Test de cointégration | 7 | 10 (C-04 fix) | 10 (+ I(1) check) | 10 (+ Johansen) |
| Construction du spread | 6 | 6 | 9 (outliers) | 10 (Kalman + HAC) |
| Z-score | 7 | 7 | 8 (outlier clamp) | 10 (Kalman spreads) |
| Entrée/sortie | 4 | 7 (time stop) | 9 (ML válid OOS) | 10 (self-risk) |
| Backtesting | 2 | 8 (unification) | 10 (no synth) | 10 (event-driven) |
| Validation OOS | 5 | 9 (WF réel) | 10 (stationarity) | 10 |

### Robustesse réelle : 10 / 10

| Composante | Avant | Après Phase 1 | Après Phase 2 | Après Phase 4 |
|-----------|-------|---------------|---------------|---------------|
| Résistance régimes | 5 | 5 | 9 (granularité + stationary) | 10 (leg corr) |
| Gestion liquidité | 2 | 2 | 9 (filtre + delisting) | 10 (order book) |
| Coûts réalistes | 4 | 4 | 10 (cost model) | 10 |
| Corrélation positions | 1 | 9 (spread guard) | 9 | 10 (+ leg corr) |
| Dépendance risk engine | 3 | 3 | 3 | 10 (self risk) |
| Scénarios extrêmes | 4 | 5 (time stop) | 8 (faster detect) | 10 (event-driven) |

### Probabilité de survie 12 mois

| Phase | Probabilité |
|-------|-------------|
| Avant (état actuel) | 15-25% |
| Post Phase 1 | 45-55% |
| Post Phase 2 | 65-75% |
| Post Phase 3 | 70-78% |
| Post Phase 4 | **80-88%** |

---

## PLANNING CALENDAIRE

```
Semaine 1 (17-21 fév) : Sprints 1.1 + 1.2 + 1.4
                         → Backtest unifié, look-ahead éliminé, Bonferroni fixé

Semaine 2 (24-28 fév) : Sprints 1.3 + 1.5 + 1.6
                         → Walk-forward réel, time stop, spread correlation

Semaine 3 (03-07 mar) : Sprints 2.1 + 2.2 + 2.3 + 2.4
                         → Stationnarité, granularité, coûts, liquidité

Semaine 4 (10-14 mar) : Sprints 2.5 + 2.6 + 2.7 + 2.8
                         → ML OOS, no synthetic, I(1) check, outliers

Semaine 5 (17-21 mar) : Sprints 3.1 → 3.5
                         → Polish : annualisation, half-life, YAML, tests, cache

Semaine 6 (24-28 mar) : Sprints 4.1 → 4.6
                         → Johansen, Kalman, HAC, self-risk, event-driven, leg corr

Semaine 7 (31 mar - 04 avr) : Validation intégrale
                         → Run complet WF 2023-2025, paper trading launch
```

---

## CRITÈRES DE GATE (GO/NO-GO)

### Gate 1 — Fin Phase 1 (28 février)

| Critère | Seuil |
|---------|-------|
| Backtest unifié opérationnel | ✅ / ❌ |
| Walk-forward avec re-training | ✅ / ❌ |
| Zero look-ahead bias (test formel) | ✅ / ❌ |
| Tous tests existants passent | ✅ / ❌ |
| Sharpe OOS walk-forward > 0.5 | Valeur mesurée |

### Gate 2 — Fin Phase 2 (14 mars)

| Critère | Seuil |
|---------|-------|
| Coûts réalistes ≥ 40 bps round-trip | ✅ / ❌ |
| Filtre liquidité actif | ✅ / ❌ |
| Walk-forward Sharpe OOS > 0.5 avec coûts réalistes | Valeur mesurée |
| ML thresholds validés OOS OU désactivés | ✅ / ❌ |
| Zero fallback synthétique | ✅ / ❌ |

### Gate 3 — Go Paper Trading (28 mars)

| Critère | Seuil |
|---------|-------|
| Scores qualité ≥ 9/10 ET robustesse ≥ 9/10 | ✅ / ❌ |
| Walk-forward 2023-2025 : Sharpe > 0.7, DD < 15% | Valeurs mesurées |
| 100% tests passent (0 skip, 0 fail) | ✅ / ❌ |
| Johansen + Kalman opérationnels | ✅ / ❌ |
| Paper trading sandbox configuré | ✅ / ❌ |

### Gate 4 — Go Live (après 3 mois de paper)

| Critère | Seuil |
|---------|-------|
| Paper trading Sharpe > 0.5 sur 90 jours | Valeur mesurée |
| Max DD paper < 10% | Valeur mesurée |
| 0 incidents critiques en paper | ✅ / ❌ |
| Audit externe indépendant positif | ✅ / ❌ |

---

## FICHIERS À CRÉER (RÉCAPITULATIF)

| Fichier | Sprint | Description |
|---------|--------|-------------|
| `backtests/strategy_simulator.py` | 1.1 | Simulateur unifié backtest=live |
| `backtests/cost_model.py` | 2.3 | Modèle de coûts réaliste 4-legs |
| `backtests/event_driven.py` | 4.5 | Backtester event-driven |
| `execution/time_stop.py` | 1.5 | Time stop manager |
| `risk/spread_correlation.py` | 1.6 | Garde de corrélation des spreads |
| `models/stationarity_monitor.py` | 2.1 | Monitoring continu ADF rolling |
| `models/johansen.py` | 4.1 | Test de Johansen multi-varié |
| `models/kalman_hedge.py` | 4.2 | Kalman filter pour β dynamique |
| `data/delisting_guard.py` | 2.4 | Détection de tokens mourants |
| `tests/integration/test_end_to_end.py` | 3.4 | Test intégral pipeline |
| `tests/integration/test_no_leakage.py` | 3.4 | Test anti-look-ahead |

---

## MOT DE FIN

Ce plan transforme EDGECORE d'une **stratégie fragile (4.5/10 + 3.5/10)** en un **système institutionnel-grade (10/10 + 10/10)** en 7 semaines.

La clé est la **Phase 1** : tant que le backtest ne reflète pas la stratégie réelle, aucune décision ne peut être prise sur des bases solides. Les Phases 2-4 construisent la robustesse et la différenciation.

Le facteur critique de succès : **ne jamais sacrifier la rigueur statistique pour la vélocité de développement.** Chaque sprint a un Definition of Done explicite. Si un gate échoue → on ne passe pas à la phase suivante.

> **Objectif final : une stratégie dont chaque composant est prouvé, testé, et validé OOS avant qu'un centime de capital réel ne soit engagé.**

---

*Plan généré le 13 février 2026 à partir de AUDIT_STRATEGIQUE_EDGECORE_V2.md*
