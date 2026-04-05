<<<<<<< HEAD
﻿# PLAN DE REM├ëDIATION EDGECORE ÔÇö OBJECTIF 10/10

**Date :** 13 f├®vrier 2026  
**Source :** `AUDIT_STRATEGIQUE_EDGECORE_V2.md`  
**Objectif :** Corriger les 19 failles (6 ­ƒö┤ + 8 ­ƒƒá + 5 ­ƒƒí) ÔÇö Scores cibles : 10/10 statistique, 10/10 robustesse  
**Probabilit├® de survie cible :** 80%+ ├á 12 mois  
**Verdict cible :** ­ƒæë Strat├®giquement exploitable avec capital r├®el
=======
# PLAN DE REMÉDIATION EDGECORE — OBJECTIF 10/10

**Date :** 13 février 2026  
**Source :** `AUDIT_STRATEGIQUE_EDGECORE_V2.md`  
**Objectif :** Corriger les 19 failles (6 🔴 + 8 🟠 + 5 🟡) — Scores cibles : 10/10 statistique, 10/10 robustesse  
**Probabilité de survie cible :** 80%+ à 12 mois  
**Verdict cible :** 👉 Stratégiquement exploitable avec capital réel
>>>>>>> origin/main

---

## ARCHITECTURE DU PLAN

```
<<<<<<< HEAD
PHASE 1 ÔÇö FONDATIONS CRITIQUES          [Semaines 1-2]   6 ­ƒö┤ ÔåÆ 0 ­ƒö┤
PHASE 2 ÔÇö SOLIDIFICATION MAJEURE        [Semaines 3-4]   8 ­ƒƒá ÔåÆ 0 ­ƒƒá
PHASE 3 ÔÇö POLISH & EXCELLENCE           [Semaine 5]      5 ­ƒƒí ÔåÆ 0 ­ƒƒí
PHASE 4 ÔÇö VALIDATION INT├ëGRALE          [Semaine 6]      Preuve formelle 10/10
```

Chaque t├óche est sp├®cifi├®e avec :
- Faille source (ID audit)
- Fichiers impact├®s
- Logique exacte ├á impl├®menter
- Crit├¿re de validation (Definition of Done)
=======
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
>>>>>>> origin/main
- Impact sur le score

---

<<<<<<< HEAD
## PHASE 1 ÔÇö FONDATIONS CRITIQUES

> ├ëliminer les 6 failles ­ƒö┤ qui invalident la strat├®gie.  
=======
## PHASE 1 — FONDATIONS CRITIQUES

> Éliminer les 6 failles 🔴 qui invalident la stratégie.  
>>>>>>> origin/main
> **Sans cette phase, rien d'autre n'a de valeur.**

---

<<<<<<< HEAD
### SPRINT 1.1 ÔÇö Unifier backtest et strat├®gie live

**Faille :** ­ƒö┤ C-01 ÔÇö Divergence backtest/live  
**Impact score :** Backtesting 2/10 ÔåÆ 8/10

#### Probl├¿me exact

`BacktestRunner.run()` et `PairTradingStrategy.generate_signals()` sont deux impl├®mentations ind├®pendantes. Le backtest n'utilise ni les seuils adaptatifs, ni les trailing stops, ni les concentration limits, ni le regime detector, ni le hedge ratio tracking.

#### Solution : cr├®er `StrategyBacktestSimulator`
=======
### SPRINT 1.1 — Unifier backtest et stratégie live

**Faille :** 🔴 C-01 — Divergence backtest/live  
**Impact score :** Backtesting 2/10 → 8/10

#### Problème exact

`BacktestRunner.run()` et `PairTradingStrategy.generate_signals()` sont deux implémentations indépendantes. Le backtest n'utilise ni les seuils adaptatifs, ni les trailing stops, ni les concentration limits, ni le regime detector, ni le hedge ratio tracking.

#### Solution : créer `StrategyBacktestSimulator`
>>>>>>> origin/main

**Nouveau fichier :** `backtests/strategy_simulator.py`

```python
class StrategyBacktestSimulator:
    """
<<<<<<< HEAD
    Simule la strat├®gie live bar-par-bar en utilisant EXACTEMENT
    le m├¬me code que PairTradingStrategy.generate_signals().
    
    Principe : ├á chaque date_idx, on passe les donn├®es historiques
    [0:date_idx] ├á la strat├®gie et on collecte les signaux.
=======
    Simule la stratégie live bar-par-bar en utilisant EXACTEMENT
    le même code que PairTradingStrategy.generate_signals().
    
    Principe : à chaque date_idx, on passe les données historiques
    [0:date_idx] à la stratégie et on collecte les signaux.
>>>>>>> origin/main
    """
    
    def __init__(self, strategy: PairTradingStrategy, cost_model: CostModel):
        self.strategy = strategy
        self.cost_model = cost_model
        self.portfolio = SimulatedPortfolio()
    
    def run(self, prices_df: pd.DataFrame, 
            pair_rediscovery_interval: int = 21) -> BacktestMetrics:
        """
        Boucle bar-par-bar :
<<<<<<< HEAD
        1. Toutes les `pair_rediscovery_interval` barres ÔåÆ re-d├®couvrir paires
           sur donn├®es [max(0, idx-252):idx] uniquement (pas de look-ahead)
        2. Appeler strategy.generate_signals(hist_prices) 
        3. Appliquer les signaux avec CostModel r├®aliste
        4. Calculer les m├®triques
        """
```

**Fichiers ├á modifier :**

| Fichier | Action |
|---------|--------|
| `backtests/strategy_simulator.py` | **CR├ëER** ÔÇö Simulateur unifi├® |
| `backtests/runner.py` | Refactor : `run()` d├®l├¿gue ├á `StrategyBacktestSimulator` |
| `backtests/walk_forward.py` | Refactor : utiliser le simulateur au lieu de `run()` |
| `backtests/cost_model.py` | **CR├ëER** ÔÇö Mod├¿le de co├╗ts param├®trable |

**Definition of Done :**
- [ ] `StrategyBacktestSimulator.run()` appelle `PairTradingStrategy.generate_signals()` ├á chaque barre
- [ ] Z├®ro duplication de logique de signal entre backtest et live
- [ ] Test de r├®gression : m├¬me donn├®es ÔåÆ m├¬me signaux entre simulateur et strat├®gie directe
=======
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
>>>>>>> origin/main
- [ ] Trailing stops, concentration limits, regime detector actifs dans le backtest

---

<<<<<<< HEAD
### SPRINT 1.2 ÔÇö ├ëliminer le look-ahead bias

**Faille :** ­ƒö┤ C-02 ÔÇö Look-ahead bias sur la s├®lection des paires  
**Impact score :** Backtesting +2/10

#### Probl├¿me exact

Dans `BacktestRunner.run()`, `_find_cointegrated_pairs_in_data(prices_df)` re├ºoit TOUTES les donn├®es (`prices_df` complet), puis les trades sont simul├®s bar-par-bar. Les paires sont s├®lectionn├®es avec connaissance du futur.

#### Solution : d├®couverte strictement in-sample
=======
### SPRINT 1.2 — Éliminer le look-ahead bias

**Faille :** 🔴 C-02 — Look-ahead bias sur la sélection des paires  
**Impact score :** Backtesting +2/10

#### Problème exact

Dans `BacktestRunner.run()`, `_find_cointegrated_pairs_in_data(prices_df)` reçoit TOUTES les données (`prices_df` complet), puis les trades sont simulés bar-par-bar. Les paires sont sélectionnées avec connaissance du futur.

#### Solution : découverte strictement in-sample
>>>>>>> origin/main

**Dans `StrategyBacktestSimulator` :**

```python
def _discover_pairs_no_lookahead(self, prices_df, current_idx, lookback=252):
    """
<<<<<<< HEAD
    D├®couvre les paires en utilisant UNIQUEMENT les donn├®es
    [current_idx - lookback : current_idx].
    Aucune donn├®e future n'est visible.
=======
    Découvre les paires en utilisant UNIQUEMENT les données
    [current_idx - lookback : current_idx].
    Aucune donnée future n'est visible.
>>>>>>> origin/main
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
<<<<<<< HEAD
Bar 252:  d├®couverte paires sur [0:252)     ÔåÆ trade bar 252
Bar 273:  re-d├®couverte sur [21:273)        ÔåÆ trade bars 273-293
Bar 294:  re-d├®couverte sur [42:294)        ÔåÆ trade bars 294-314
=======
Bar 252:  découverte paires sur [0:252)     → trade bar 252
Bar 273:  re-découverte sur [21:273)        → trade bars 273-293
Bar 294:  re-découverte sur [42:294)        → trade bars 294-314
>>>>>>> origin/main
...
```

**Definition of Done :**
<<<<<<< HEAD
- [ ] ├Ç aucun moment le simulateur ne voit des donn├®es post├®rieures ├á `current_idx`
- [ ] Test formel : injecter un changement de r├®gime ├á T=500, v├®rifier que les paires avant T=500 ne changent pas
- [ ] Les paires sont re-d├®couvertes toutes les `pair_rediscovery_interval` barres (configurable, default 21)

---

### SPRINT 1.3 ÔÇö Walk-forward r├®el avec re-training

**Faille :** ­ƒö┤ C-03 ÔÇö Walk-forward invalide  
**Impact score :** Validation OOS 5/10 ÔåÆ 9/10

#### Probl├¿me exact

Le walk-forward actuel ne retraine pas le mod├¿le entre les p├®riodes. Le commentaire dans le code l'avoue explicitement.
=======
- [ ] À aucun moment le simulateur ne voit des données postérieures à `current_idx`
- [ ] Test formel : injecter un changement de régime à T=500, vérifier que les paires avant T=500 ne changent pas
- [ ] Les paires sont re-découvertes toutes les `pair_rediscovery_interval` barres (configurable, default 21)

---

### SPRINT 1.3 — Walk-forward réel avec re-training

**Faille :** 🔴 C-03 — Walk-forward invalide  
**Impact score :** Validation OOS 5/10 → 9/10

#### Problème exact

Le walk-forward actuel ne retraine pas le modèle entre les périodes. Le commentaire dans le code l'avoue explicitement.
>>>>>>> origin/main

#### Solution : refactorer `WalkForwardBacktester`

**Fichier :** `backtests/walk_forward.py`

```python
def run_walk_forward(self, ...):
    for period_idx, (train_df, test_df) in enumerate(splits):
<<<<<<< HEAD
        # ├ëTAPE 1 : D├®couvrir les paires sur train_df UNIQUEMENT
=======
        # ÉTAPE 1 : Découvrir les paires sur train_df UNIQUEMENT
>>>>>>> origin/main
        pairs = self.strategy.find_cointegrated_pairs(
            train_df, use_cache=False
        )
        
<<<<<<< HEAD
        # ├ëTAPE 2 : Valider OOS sur les 20% finaux de train_df
=======
        # ÉTAPE 2 : Valider OOS sur les 20% finaux de train_df
>>>>>>> origin/main
        is_split = int(len(train_df) * 0.8)
        is_data = train_df.iloc[:is_split]
        oos_data = train_df.iloc[is_split:]
        validated_pairs, _ = self.strategy.validate_pairs_oos(
            pairs, is_data, oos_data
        )
        
<<<<<<< HEAD
        # ├ëTAPE 3 : Simuler sur test_df avec paires valid├®es uniquement
        simulator = StrategyBacktestSimulator(
            strategy=self._create_fresh_strategy(),
            cost_model=self.cost_model,
            fixed_pairs=validated_pairs  # Paires gel├®es pour cette p├®riode
        )
        period_metrics = simulator.run(test_df)
        
        # ├ëTAPE 4 : Collecter les m├®triques OOS
=======
        # ÉTAPE 3 : Simuler sur test_df avec paires validées uniquement
        simulator = StrategyBacktestSimulator(
            strategy=self._create_fresh_strategy(),
            cost_model=self.cost_model,
            fixed_pairs=validated_pairs  # Paires gelées pour cette période
        )
        period_metrics = simulator.run(test_df)
        
        # ÉTAPE 4 : Collecter les métriques OOS
>>>>>>> origin/main
        self.per_period_metrics.append(period_metrics)
```

**Definition of Done :**
<<<<<<< HEAD
- [ ] Chaque p├®riode de walk-forward a son propre ensemble de paires
- [ ] Les paires sont d├®couvertes sur train_df et valid├®es OOS avant trading
- [ ] Aucune donn├®e de test_df n'est visible pendant la d├®couverte
- [ ] La strat├®gie est r├®initialis├®e ├á chaque p├®riode (fresh state)
- [ ] Test : comparer les r├®sultats WF avec et sans re-training ÔÇö le re-training doit donner des r├®sultats diff├®rents

---

### SPRINT 1.4 ÔÇö Corriger le bypass Bonferroni Cython

**Faille :** ­ƒö┤ C-04 ÔÇö Cython bypass Bonferroni  
**Impact score :** Test de coint├®gration 7/10 ÔåÆ 10/10

#### Probl├¿me exact

```python
# models/cointegration.py, ligne ~233
result_dict['is_cointegrated'] = adf_result[1] < 0.05  # ÔåÉ HARDCOD├ë
=======
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
>>>>>>> origin/main
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
<<<<<<< HEAD
    num_symbols: Optional[int] = None,      # ÔåÉ AJOUTER
    apply_bonferroni: bool = True             # ÔåÉ AJOUTER
=======
    num_symbols: Optional[int] = None,      # ← AJOUTER
    apply_bonferroni: bool = True             # ← AJOUTER
>>>>>>> origin/main
) -> dict:
    # ...
    if CYTHON_COINTEGRATION_AVAILABLE:
        try:
            # ... Cython call ...
            
<<<<<<< HEAD
            # Calculer le seuil corrig├®
=======
            # Calculer le seuil corrigé
>>>>>>> origin/main
            if apply_bonferroni and num_symbols is not None:
                num_pairs = num_symbols * (num_symbols - 1) // 2
                alpha_corrected = 0.05 / num_pairs
            else:
                alpha_corrected = 0.05
            
<<<<<<< HEAD
            result_dict['is_cointegrated'] = adf_result[1] < alpha_corrected  # ÔåÉ CORRIG├ë
=======
            result_dict['is_cointegrated'] = adf_result[1] < alpha_corrected  # ← CORRIGÉ
>>>>>>> origin/main
            result_dict['alpha_threshold'] = alpha_corrected
            result_dict['num_pairs'] = num_pairs if apply_bonferroni else None
```

<<<<<<< HEAD
**Fichier :** `backtests/runner.py` ÔÇö mettre ├á jour tous les appels :
=======
**Fichier :** `backtests/runner.py` — mettre à jour tous les appels :
>>>>>>> origin/main

```python
result = engle_granger_test_cpp_optimized(
    series1, series2,
<<<<<<< HEAD
    num_symbols=len(symbols),       # ÔåÉ AJOUTER
    apply_bonferroni=True            # ÔåÉ AJOUTER
=======
    num_symbols=len(symbols),       # ← AJOUTER
    apply_bonferroni=True            # ← AJOUTER
>>>>>>> origin/main
)
```

**Definition of Done :**
- [ ] `engle_granger_test_cpp_optimized` accepte et utilise `num_symbols` et `apply_bonferroni`
<<<<<<< HEAD
- [ ] Plus aucun `< 0.05` hardcod├®
- [ ] Test : avec 50 symboles, le seuil effectif est `0.05 / 1225 Ôëê 4.08e-5`
- [ ] Test de non-r├®gression : r├®sultats de `engle_granger_test` et `engle_granger_test_cpp_optimized` identiques ├á param├¿tres identiques

---

### SPRINT 1.5 ÔÇö Time stop obligatoire

**Faille :** ­ƒö┤ C-05 ÔÇö Absence de time stop  
**Impact score :** Entr├®e/sortie 4/10 ÔåÆ 7/10
=======
- [ ] Plus aucun `< 0.05` hardcodé
- [ ] Test : avec 50 symboles, le seuil effectif est `0.05 / 1225 ≈ 4.08e-5`
- [ ] Test de non-régression : résultats de `engle_granger_test` et `engle_granger_test_cpp_optimized` identiques à paramètres identiques

---

### SPRINT 1.5 — Time stop obligatoire

**Faille :** 🔴 C-05 — Absence de time stop  
**Impact score :** Entrée/sortie 4/10 → 7/10
>>>>>>> origin/main

#### Solution : `TimeStopManager`

**Nouveau fichier :** `execution/time_stop.py`

```python
class TimeStopManager:
    """
    Ferme les positions ouvertes trop longtemps.
    
<<<<<<< HEAD
    R├¿gle : position ferm├®e si dur├®e > min(2 ├ù half_life, max_days).
=======
    Règle : position fermée si durée > min(2 × half_life, max_days).
>>>>>>> origin/main
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

<<<<<<< HEAD
**Int├®gration dans :** `strategies/pair_trading.py` ÔåÆ `generate_signals()`

```python
# Apr├¿s les checks de trailing stop, AVANT les exits de mean reversion :
=======
**Intégration dans :** `strategies/pair_trading.py` → `generate_signals()`

```python
# Après les checks de trailing stop, AVANT les exits de mean reversion :
>>>>>>> origin/main
if pair_key in self.active_trades:
    should_exit_time, time_reason = self.time_stop_manager.should_exit(
        pair_key, datetime.now()
    )
    if should_exit_time:
        signals.append(Signal(pair_key, side="exit", strength=1.0, reason=time_reason))
        # cleanup...
```

**Definition of Done :**
<<<<<<< HEAD
- [ ] Toute position est ferm├®e apr├¿s `min(2├ùHL, 30)` jours
- [ ] Int├®gr├® dans `generate_signals()` ET dans `StrategyBacktestSimulator`
- [ ] Test : position ouverte ├á T, forc├®e ferm├®e ├á T+31 si max_days=30
=======
- [ ] Toute position est fermée après `min(2×HL, 30)` jours
- [ ] Intégré dans `generate_signals()` ET dans `StrategyBacktestSimulator`
- [ ] Test : position ouverte à T, forcée fermée à T+31 si max_days=30
>>>>>>> origin/main
- [ ] Config : `max_time_stop_days` configurable dans `StrategyConfig`

---

<<<<<<< HEAD
### SPRINT 1.6 ÔÇö Matrice de corr├®lation des spreads

**Faille :** ­ƒö┤ C-06 ÔÇö Corr├®lation crois├®e des spreads non g├®r├®e  
**Impact score :** Corr├®lation des positions 1/10 ÔåÆ 9/10
=======
### SPRINT 1.6 — Matrice de corrélation des spreads

**Faille :** 🔴 C-06 — Corrélation croisée des spreads non gérée  
**Impact score :** Corrélation des positions 1/10 → 9/10
>>>>>>> origin/main

#### Solution : `SpreadCorrelationGuard`

**Nouveau fichier :** `risk/spread_correlation.py`

```python
class SpreadCorrelationGuard:
    """
<<<<<<< HEAD
    Emp├¬che l'ouverture de positions dont le spread est corr├®l├®
    avec un spread d├®j├á en portefeuille.
    
    Logique :
    1. Maintenir un historique de spread (60 derni├¿res barres) pour chaque position active
    2. Avant nouvel entry : calculer corr├®lation du nouveau spread 
=======
    Empêche l'ouverture de positions dont le spread est corrélé
    avec un spread déjà en portefeuille.
    
    Logique :
    1. Maintenir un historique de spread (60 dernières barres) pour chaque position active
    2. Avant nouvel entry : calculer corrélation du nouveau spread 
>>>>>>> origin/main
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
<<<<<<< HEAD
        V├®rifie que le spread n'est pas trop corr├®l├® avec les spreads actifs.
        """
        for active_key, active_spread in self.active_spreads.items():
            # Aligner les s├®ries sur l'intersection temporelle
=======
        Vérifie que le spread n'est pas trop corrélé avec les spreads actifs.
        """
        for active_key, active_spread in self.active_spreads.items():
            # Aligner les séries sur l'intersection temporelle
>>>>>>> origin/main
            common_idx = new_spread.index.intersection(active_spread.index)
            if len(common_idx) < 20:
                continue
            
            corr = new_spread.loc[common_idx].corr(active_spread.loc[common_idx])
            
            if abs(corr) > self.max_corr:
                return False, (
<<<<<<< HEAD
                    f"Spread {pair_key} corr├®l├® ├á {corr:.2f} avec {active_key} "
=======
                    f"Spread {pair_key} corrélé à {corr:.2f} avec {active_key} "
>>>>>>> origin/main
                    f"(max: {self.max_corr})"
                )
        
        return True, None
    
    def register_position(self, pair_key: str, spread: pd.Series):
        self.active_spreads[pair_key] = spread.tail(self.lookback)
    
    def remove_position(self, pair_key: str):
        self.active_spreads.pop(pair_key, None)
    
    def get_correlation_matrix(self) -> pd.DataFrame:
<<<<<<< HEAD
        """Retourne la matrice de corr├®lation de tous les spreads actifs."""
=======
        """Retourne la matrice de corrélation de tous les spreads actifs."""
>>>>>>> origin/main
        if len(self.active_spreads) < 2:
            return pd.DataFrame()
        df = pd.DataFrame(self.active_spreads)
        return df.corr()
```

<<<<<<< HEAD
**Int├®gration dans :** `strategies/pair_trading.py` ÔåÆ avant chaque `signals.append()` d'entr├®e

```python
# Avant l'entr├®e long ou short :
=======
**Intégration dans :** `strategies/pair_trading.py` → avant chaque `signals.append()` d'entrée

```python
# Avant l'entrée long ou short :
>>>>>>> origin/main
can_add, corr_reason = self.spread_correlation_guard.can_add_position(
    pair_key, spread.tail(60)
)
if not can_add:
    logger.info("signal_skipped_spread_correlation", pair=pair_key, reason=corr_reason)
    continue

<<<<<<< HEAD
# Si accept├®, apr├¿s l'ajout :
=======
# Si accepté, après l'ajout :
>>>>>>> origin/main
self.spread_correlation_guard.register_position(pair_key, spread)
```

**Definition of Done :**
<<<<<<< HEAD
- [ ] Toute nouvelle position est v├®rifi├®e contre la matrice de corr├®lation des spreads existants
- [ ] Seuil configurable (`max_spread_correlation` dans `RiskConfig`)
- [ ] Test : 3 paires corr├®l├®es ├á 0.9 ÔåÆ seule la premi├¿re est accept├®e
- [ ] La matrice de corr├®lation est logu├®e ├á chaque tick pour monitoring
- [ ] Int├®gr├® dans le backtest simulator ET dans la strat├®gie live

---

## PHASE 2 ÔÇö SOLIDIFICATION MAJEURE

> Corriger les 8 failles ­ƒƒá qui fragilisent la strat├®gie.

---

### SPRINT 2.1 ÔÇö Monitoring continu de stationnarit├®

**Faille :** ­ƒƒá M-01 ÔÇö Stationnarit├® suppos├®e entre re-tests  
**Impact score :** R├®sistance aux r├®gimes 5/10 ÔåÆ 8/10
=======
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
>>>>>>> origin/main

#### Solution : `StationarityMonitor`

**Nouveau fichier :** `models/stationarity_monitor.py`

```python
class StationarityMonitor:
    """
<<<<<<< HEAD
    V├®rifie en continu (bar-par-bar) si le spread reste stationnaire
    via un test ADF rolling rapide.
    
    Si le spread perd sa stationnarit├® :
    ÔåÆ Signal d'alerte au TradeManager
    ÔåÆ Fermeture de la position recommand├®e
=======
    Vérifie en continu (bar-par-bar) si le spread reste stationnaire
    via un test ADF rolling rapide.
    
    Si le spread perd sa stationnarité :
    → Signal d'alerte au TradeManager
    → Fermeture de la position recommandée
>>>>>>> origin/main
    """
    
    def __init__(self, window: int = 60, alert_pvalue: float = 0.10):
        self.window = window
        self.alert_pvalue = alert_pvalue
    
    def check_stationarity(self, spread: pd.Series) -> Tuple[bool, float]:
        """
<<<<<<< HEAD
        Test ADF rapide sur les `window` derni├¿res observations.
=======
        Test ADF rapide sur les `window` dernières observations.
>>>>>>> origin/main
        
        Returns:
            (is_stationary, current_pvalue)
        """
        if len(spread) < self.window:
<<<<<<< HEAD
            return True, 0.0  # Pas assez de donn├®es, pr├®sumer OK
=======
            return True, 0.0  # Pas assez de données, présumer OK
>>>>>>> origin/main
        
        recent = spread.tail(self.window).values
        adf_result = adfuller(recent, regression='c', autolag='AIC')
        pvalue = adf_result[1]
        
        return pvalue < self.alert_pvalue, pvalue
```

<<<<<<< HEAD
**Int├®gration :** dans `generate_signals()`, apr├¿s le calcul du spread et AVANT l'├®valuation du z-score :
=======
**Intégration :** dans `generate_signals()`, après le calcul du spread et AVANT l'évaluation du z-score :
>>>>>>> origin/main

```python
is_stationary, stationarity_pval = self.stationarity_monitor.check_stationarity(spread)
if not is_stationary:
<<<<<<< HEAD
    # Si position ouverte ÔåÆ fermer
    if pair_key in self.active_trades:
        signals.append(Signal(pair_key, "exit", 1.0,
            f"Stationarity lost: p={stationarity_pval:.4f}"))
    # Si pas en position ÔåÆ ne pas entrer
=======
    # Si position ouverte → fermer
    if pair_key in self.active_trades:
        signals.append(Signal(pair_key, "exit", 1.0,
            f"Stationarity lost: p={stationarity_pval:.4f}"))
    # Si pas en position → ne pas entrer
>>>>>>> origin/main
    continue
```

**Definition of Done :**
<<<<<<< HEAD
- [ ] ADF rolling ex├®cut├® ├á chaque barre pour chaque paire active
- [ ] Perte de stationnarit├® ÔåÆ fermeture imm├®diate + pas de nouvelles entr├®es
- [ ] Seuil `alert_pvalue=0.10` configurable
- [ ] Impact perf mesur├® : ADF sur 60 observations < 5ms (acceptable bar-par-bar)
- [ ] Test : injecter un random walk apr├¿s bar 200 ÔåÆ position ferm├®e ├á bar 201

---

### SPRINT 2.2 ÔÇö Granularit├® de d├®tection acc├®l├®r├®e

**Faille :** ­ƒƒá M-02 ÔÇö Granularit├® de d├®tection insuffisante  
**Impact score :** R├®sistance aux r├®gimes ÔåÆ 9/10
=======
- [ ] ADF rolling exécuté à chaque barre pour chaque paire active
- [ ] Perte de stationnarité → fermeture immédiate + pas de nouvelles entrées
- [ ] Seuil `alert_pvalue=0.10` configurable
- [ ] Impact perf mesuré : ADF sur 60 observations < 5ms (acceptable bar-par-bar)
- [ ] Test : injecter un random walk après bar 200 → position fermée à bar 201

---

### SPRINT 2.2 — Granularité de détection accélérée

**Faille :** 🟠 M-02 — Granularité de détection insuffisante  
**Impact score :** Résistance aux régimes → 9/10
>>>>>>> origin/main

#### Actions

**Fichier :** `models/hedge_ratio_tracker.py`
<<<<<<< HEAD
- R├®duire `reestimation_frequency_days` : 30 ÔåÆ **7 jours**
- Ajouter un mode `emergency_reestimate` d├®clench├® si la volatilit├® du spread > 3¤â

**Fichier :** `models/regime_detector.py`
- R├®duire `min_regime_duration` : 3 ÔåÆ **1 bar** (r├®activit├® maximale)
- Ajouter un mode `instant_transition` pour les spikes de volatilit├® > 99e percentile
=======
- Réduire `reestimation_frequency_days` : 30 → **7 jours**
- Ajouter un mode `emergency_reestimate` déclenché si la volatilité du spread > 3σ

**Fichier :** `models/regime_detector.py`
- Réduire `min_regime_duration` : 3 → **1 bar** (réactivité maximale)
- Ajouter un mode `instant_transition` pour les spikes de volatilité > 99e percentile
>>>>>>> origin/main

**Fichier :** `config/settings.py`
- Ajouter dans `StrategyConfig` :
  ```python
  hedge_ratio_reestimation_days: int = 7
  regime_min_duration: int = 1
  emergency_vol_threshold_percentile: float = 99.0
  ```

**Definition of Done :**
- [ ] Hedge ratio check toutes les 7 barres (pas 30)
<<<<<<< HEAD
- [ ] R├®gime detector r├®agit en 1 barre au lieu de 3
- [ ] Mode d'urgence : si vol 99e percentile, transition imm├®diate + re-estimation forc├®e du hedge ratio
- [ ] Tests mis ├á jour avec les nouvelles valeurs

---

### SPRINT 2.3 ÔÇö Mod├¿le de frais r├®aliste

**Faille :** ­ƒƒá M-03 ÔÇö Frais sous-estim├®s  
**Impact score :** Co├╗ts r├®alistes 4/10 ÔåÆ 10/10
=======
- [ ] Régime detector réagit en 1 barre au lieu de 3
- [ ] Mode d'urgence : si vol 99e percentile, transition immédiate + re-estimation forcée du hedge ratio
- [ ] Tests mis à jour avec les nouvelles valeurs

---

### SPRINT 2.3 — Modèle de frais réaliste

**Faille :** 🟠 M-03 — Frais sous-estimés  
**Impact score :** Coûts réalistes 4/10 → 10/10
>>>>>>> origin/main

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
<<<<<<< HEAD
    borrowing_cost_annual_pct: float = 5.0  # Co├╗t d'emprunt pour short
=======
    borrowing_cost_annual_pct: float = 5.0  # Coût d'emprunt pour short
>>>>>>> origin/main
    include_funding: bool = False
    include_borrowing: bool = True


class RealisticCostModel:
    """
<<<<<<< HEAD
    Mod├¿le de co├╗ts 4-legs : 
    Entry (long leg + short leg) + Exit (close long + close short)
    = 4 ├ù (fee + slippage)
    + holding cost (borrowing + funding) ├ù dur├®e
=======
    Modèle de coûts 4-legs : 
    Entry (long leg + short leg) + Exit (close long + close short)
    = 4 × (fee + slippage)
    + holding cost (borrowing + funding) × durée
>>>>>>> origin/main
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
        
<<<<<<< HEAD
        # Slippage adaptatif ├á la liquidit├®
=======
        # Slippage adaptatif à la liquidité
>>>>>>> origin/main
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
<<<<<<< HEAD
        Slippage = base + impact ├ù (order_size / volume_24h)
=======
        Slippage = base + impact × (order_size / volume_24h)
>>>>>>> origin/main
        Plus le ratio order/volume est grand, plus le slippage augmente.
        """
        if volume_24h <= 0:
            return 50 / 10000  # Worst case: 50 bps
        
        participation_rate = order_size / volume_24h
        impact_bps = self.config.base_slippage_bps + 100 * participation_rate
<<<<<<< HEAD
        return min(impact_bps, 100) / 10000  # Cap ├á 100 bps
```

**Int├®gration :** remplacer les constantes `COMMISSION_BPS` / `SLIPPAGE_BPS` dans `runner.py` par `RealisticCostModel`.

**Definition of Done :**
- [ ] 4 legs comptabilis├®s (long entry + short entry + long exit + short exit)
- [ ] Slippage adaptatif au volume 24h du symbole
- [ ] Borrowing cost pour le short leg
- [ ] Frais totaux r├®alistes ÔëÑ 40 bps round-trip (vs 30 bps avant)
- [ ] Test : un trade sur POPCAT avec $1000 et volume_24h=$50K ÔåÆ slippage > 20 bps

---

### SPRINT 2.4 ÔÇö Filtre de liquidit├® dynamique

**Faille :** ­ƒƒá M-04 ÔÇö Survivorship/selection bias dans l'univers  
**Impact score :** Gestion de la liquidit├® 2/10 ÔåÆ 9/10

#### Actions

**1. Filtre de liquidit├® dans le pair discovery**

**Fichier :** `strategies/pair_trading.py` ÔåÆ `find_cointegrated_pairs`
=======
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
>>>>>>> origin/main

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
<<<<<<< HEAD
                filtered.append(sym)  # Pas de volume dispo ÔåÆ accepter
=======
                filtered.append(sym)  # Pas de volume dispo → accepter
>>>>>>> origin/main
    return filtered
```

**2. Nettoyage de l'univers**

**Fichier :** `config/dev.yaml`
<<<<<<< HEAD
- Supprimer `FTT/USD` (token FTX effondr├®)
- Supprimer le doublon `BAC`
- Ajouter un commentaire : symboles valid├®s au 2026-02-13

**Fichier :** `config/prod.yaml`
- Supprimer `POPCAT/USD`, `MOG/USD`, `GOAT/USD` (liquidit├® < $1M/jour)
=======
- Supprimer `FTT/USD` (token FTX effondré)
- Supprimer le doublon `BAC`
- Ajouter un commentaire : symboles validés au 2026-02-13

**Fichier :** `config/prod.yaml`
- Supprimer `POPCAT/USD`, `MOG/USD`, `GOAT/USD` (liquidité < $1M/jour)
>>>>>>> origin/main
- Supprimer `FTT/USD`
- Ajouter filtre dynamique de volume

**3. DelistingGuard**

**Nouveau fichier :** `data/delisting_guard.py`

```python
class DelistingGuard:
    """
<<<<<<< HEAD
    D├®tecte les tokens en voie de delisting :
    - Volume chutant > 80% sur 7 jours
    - Prix < $0.001
    - Pas de donn├®es depuis > 3 jours
=======
    Détecte les tokens en voie de delisting :
    - Volume chutant > 80% sur 7 jours
    - Prix < $0.001
    - Pas de données depuis > 3 jours
>>>>>>> origin/main
    """
    def is_safe(self, symbol: str, recent_data: pd.Series) -> bool:
        ...
```

**Definition of Done :**
<<<<<<< HEAD
- [ ] Filtre de liquidit├® min $5M/jour (configurable)
- [ ] FTT, LUNC retir├®s de dev.yaml ; tokens < $1M/jour retir├®s de prod.yaml
- [ ] Doublon BAC corrig├®
- [ ] DelistingGuard d├®tecte les tokens mourants
- [ ] Test : injecter un token avec volume $100K ÔåÆ exclu du discovery

---

### SPRINT 2.5 ÔÇö Validation OOS du ML threshold optimizer

**Faille :** ­ƒƒá M-05 ÔÇö ML threshold optimizer non valid├® OOS  
**Impact score :** Entr├®e/sortie ÔåÆ 9/10
=======
- [ ] Filtre de liquidité min $5M/jour (configurable)
- [ ] FTT, LUNC retirés de dev.yaml ; tokens < $1M/jour retirés de prod.yaml
- [ ] Doublon BAC corrigé
- [ ] DelistingGuard détecte les tokens mourants
- [ ] Test : injecter un token avec volume $100K → exclu du discovery

---

### SPRINT 2.5 — Validation OOS du ML threshold optimizer

**Faille :** 🟠 M-05 — ML threshold optimizer non validé OOS  
**Impact score :** Entrée/sortie → 9/10
>>>>>>> origin/main

#### Solution : walk-forward cross-validation sur le ML

**Fichier :** `models/ml_threshold_optimizer.py`

Ajouter :

```python
class MLThresholdValidator:
    """
    Walk-forward CV du ML threshold optimizer.
    
<<<<<<< HEAD
    1. Diviser les donn├®es en 5 folds temporels
    2. Pour chaque fold : train sur [0:fold], test sur [fold:fold+1]
    3. M├®trique : precision@0.6 en OOS (le seuil optimal OOS doit ├¬tre 
       meilleur que le seuil fixe)
    4. Si OOS degradation > 20% vs IS ÔåÆ d├®sactiver le ML et utiliser les seuils fixes
=======
    1. Diviser les données en 5 folds temporels
    2. Pour chaque fold : train sur [0:fold], test sur [fold:fold+1]
    3. Métrique : precision@0.6 en OOS (le seuil optimal OOS doit être 
       meilleur que le seuil fixe)
    4. Si OOS degradation > 20% vs IS → désactiver le ML et utiliser les seuils fixes
>>>>>>> origin/main
    """
    
    def validate_oos_performance(self, data: pd.DataFrame, 
                                  n_folds: int = 5) -> ValidationResult:
        ...
    
    def should_use_ml_thresholds(self) -> bool:
        """
<<<<<<< HEAD
        Si la performance ML OOS < 80% de IS ÔåÆ utiliser seuils fixes.
=======
        Si la performance ML OOS < 80% de IS → utiliser seuils fixes.
>>>>>>> origin/main
        Anti-overfitting automatique.
        """
        return self.oos_score >= 0.8 * self.is_score
```

<<<<<<< HEAD
**Fallback :** si le ML ne valide pas en OOS, les seuils adaptatifs heuristiques (volatilit├® + half-life) restent actifs. Seul le composant RF est d├®sactiv├®.

**Definition of Done :**
- [ ] Walk-forward CV ├á 5 folds temporels impl├®ment├®
- [ ] D├®sactivation automatique si d├®gradation OOS > 20%
- [ ] Log explicite : "ML thresholds disabled: OOS degradation 35%"
- [ ] Test : donn├®es random ÔåÆ ML d├®sactiv├® automatiquement

---

### SPRINT 2.6 ÔÇö Supprimer le fallback synth├®tique

**Faille :** ­ƒƒá M-06 ÔÇö Fallback synth├®tique dans le backtest  
**Impact score :** Backtesting ÔåÆ 10/10

#### Action

**Fichier :** `backtests/runner.py` ÔÇö SUPPRIMER le bloc :

```python
# ÔØî SUPPRIMER ENTI├êREMENT :
=======
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
>>>>>>> origin/main
if len(cointegrated_pairs) == 0:
    logger.warning("backtest_no_cointegrated_pairs")
    # Fallback: Generate a synthetic cointegrated pair
    np.random.seed(42)
<<<<<<< HEAD
    # ... tout le bloc synth├®tique ...
=======
    # ... tout le bloc synthétique ...
>>>>>>> origin/main
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
<<<<<<< HEAD
- [ ] Aucune donn├®e synth├®tique g├®n├®r├®e dans le backtest
- [ ] Si 0 paires trouv├®es ÔåÆ retour d'un r├®sultat vide avec flag explicite
- [ ] Test : backtest avec symboles non-coint├®gr├®s ÔåÆ retour `total_return=0`, `note=NO_PAIRS_FOUND`

---

### SPRINT 2.7 ÔÇö Test I(1) pr├®-coint├®gration

**Faille :** ­ƒƒá M-07 ÔÇö Pas de test de racine unitaire sur les s├®ries individuelles  
**Impact score :** Test de coint├®gration ÔåÆ 10/10

#### Solution : ADF + KPSS en pr├®-screening

**Fichier :** `models/cointegration.py` ÔÇö Ajouter :
=======
- [ ] Aucune donnée synthétique générée dans le backtest
- [ ] Si 0 paires trouvées → retour d'un résultat vide avec flag explicite
- [ ] Test : backtest avec symboles non-cointégrés → retour `total_return=0`, `note=NO_PAIRS_FOUND`

---

### SPRINT 2.7 — Test I(1) pré-cointégration

**Faille :** 🟠 M-07 — Pas de test de racine unitaire sur les séries individuelles  
**Impact score :** Test de cointégration → 10/10

#### Solution : ADF + KPSS en pré-screening

**Fichier :** `models/cointegration.py` — Ajouter :
>>>>>>> origin/main

```python
def verify_integration_order(series: pd.Series, name: str = "") -> dict:
    """
<<<<<<< HEAD
    V├®rifie que la s├®rie est I(1) : non-stationnaire en niveau, stationnaire en diff├®rences.
    
    Tests :
    1. ADF sur niveau : p > 0.05 (non-stationnaire ÔåÆ OK pour I(1))
    2. KPSS sur niveau : p < 0.05 (rejet de stationnarit├® ÔåÆ OK pour I(1))
    3. ADF sur diff : p < 0.05 (stationnaire apr├¿s diff├®renciation ÔåÆ I(1) confirm├®)
=======
    Vérifie que la série est I(1) : non-stationnaire en niveau, stationnaire en différences.
    
    Tests :
    1. ADF sur niveau : p > 0.05 (non-stationnaire → OK pour I(1))
    2. KPSS sur niveau : p < 0.05 (rejet de stationnarité → OK pour I(1))
    3. ADF sur diff : p < 0.05 (stationnaire après différenciation → I(1) confirmé)
>>>>>>> origin/main
    """
    from statsmodels.tsa.stattools import adfuller, kpss
    
    # Niveau
    adf_level = adfuller(series.dropna(), regression='c', autolag='AIC')
    kpss_level = kpss(series.dropna(), regression='c', nlags='auto')
    
<<<<<<< HEAD
    # Diff├®rences
=======
    # Différences
>>>>>>> origin/main
    diff = series.diff().dropna()
    adf_diff = adfuller(diff, regression='c', autolag='AIC')
    
    is_I1 = (
        adf_level[1] > 0.05 and     # Non-stationnaire en niveau
<<<<<<< HEAD
        kpss_level[1] < 0.05 and     # KPSS confirme non-stationnarit├®
        adf_diff[1] < 0.05            # Stationnaire en diff├®rences
=======
        kpss_level[1] < 0.05 and     # KPSS confirme non-stationnarité
        adf_diff[1] < 0.05            # Stationnaire en différences
>>>>>>> origin/main
    )
    
    return {
        'series_name': name,
        'is_I1': is_I1,
        'adf_level_pvalue': adf_level[1],
        'kpss_level_pvalue': kpss_level[1],
        'adf_diff_pvalue': adf_diff[1]
    }
```

<<<<<<< HEAD
**Int├®gration dans `engle_granger_test()` :**

```python
# Au d├®but de engle_granger_test(), AVANT l'OLS :
=======
**Intégration dans `engle_granger_test()` :**

```python
# Au début de engle_granger_test(), AVANT l'OLS :
>>>>>>> origin/main
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
<<<<<<< HEAD
- [ ] ADF + KPSS ex├®cut├®s sur chaque s├®rie AVANT le test de coint├®gration
- [ ] Paires rejet├®es si une s├®rie n'est pas I(1)
- [ ] Test : s├®rie stationnaire (I(0)) ÔåÆ rejet explicite
- [ ] Test : random walk (I(1)) ÔåÆ accept├®
- [ ] Performance : ADF+KPSS < 10ms par s├®rie (acceptable)

---

### SPRINT 2.8 ÔÇö Pipeline d'outliers pr├®-signal

**Faille :** ­ƒƒá M-08 ÔÇö Absence de gestion des outliers  
**Impact score :** Construction du spread 6/10 ÔåÆ 9/10

#### Solution : int├®grer `remove_outliers` dans le pipeline

**Fichier :** `strategies/pair_trading.py` ÔåÆ dans `generate_signals`, apr├¿s le chargement des prix :
=======
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
>>>>>>> origin/main

```python
from data.preprocessing import remove_outliers

# Nettoyer les outliers AVANT le calcul du spread
y_clean = remove_outliers(y, method="zscore", threshold=4.0)
x_clean = remove_outliers(x, method="zscore", threshold=4.0)

<<<<<<< HEAD
# Remplacer les NaN r├®sultants par forward fill
y_clean = y_clean.ffill().bfill()
x_clean = x_clean.ffill().bfill()

# Utiliser les s├®ries nettoy├®es pour le spread
=======
# Remplacer les NaN résultants par forward fill
y_clean = y_clean.ffill().bfill()
x_clean = x_clean.ffill().bfill()

# Utiliser les séries nettoyées pour le spread
>>>>>>> origin/main
model = DynamicSpreadModel(y_clean, x_clean, ...)
spread = model.compute_spread(y_clean, x_clean)
```

<<<<<<< HEAD
**Fichier :** `models/spread.py` ÔåÆ `compute_z_score` ÔåÆ protection suppl├®mentaire :
=======
**Fichier :** `models/spread.py` → `compute_z_score` → protection supplémentaire :
>>>>>>> origin/main

```python
def compute_z_score(self, spread, lookback=None, half_life=None):
    # ... calcul existant ...
    
<<<<<<< HEAD
    # Clamp Z-score ├á [-6, 6] pour ├®viter les signaux sur outliers r├®siduels
=======
    # Clamp Z-score à [-6, 6] pour éviter les signaux sur outliers résiduels
>>>>>>> origin/main
    z_score = z_score.clip(-6.0, 6.0)
    
    return z_score
```

**Definition of Done :**
<<<<<<< HEAD
- [ ] `remove_outliers(threshold=4¤â)` appliqu├® ├á chaque s├®rie de prix AVANT le spread
- [ ] Z-score clamp├® ├á [-6, +6]
- [ ] Test : injecter un spike de +50% sur une barre ÔåÆ pas de signal aberrant
- [ ] Test de non-r├®gression : sur donn├®es propres, r├®sultats identiques (threshold 4¤â ne touche pas les donn├®es normales)

---

## PHASE 3 ÔÇö POLISH & EXCELLENCE

> Corriger les 5 failles ­ƒƒí et ajouter les optimisations diff├®renciantes.

---

### SPRINT 3.1 ÔÇö Annualisation equity correcte

**Faille :** ­ƒƒí m-01 ÔÇö Annualisation ÔêÜ252 vs ÔêÜ365  
**Impact score :** M├®triques ÔåÆ perfectionnement
=======
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
>>>>>>> origin/main

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
<<<<<<< HEAD
- [ ] Constante `CRYPTO_TRADING_DAYS = 365` d├®finie et utilis├®e partout
- [ ] Sharpe, Sortino, Calmar recalcul├®s avec ÔêÜ365
- [ ] Test mis ├á jour

---

### SPRINT 3.2 ÔÇö Unifier l'estimation de half-life

**Faille :** ­ƒƒí m-02 ÔÇö Half-life estimation en double  
**Impact score :** Coh├®rence interne

**Action :** Faire de `SpreadHalfLifeEstimator` la seule source de v├®rit├®.

**Fichier :** `models/cointegration.py` ÔåÆ `half_life_mean_reversion()`
=======
- [ ] Constante `CRYPTO_TRADING_DAYS = 365` définie et utilisée partout
- [ ] Sharpe, Sortino, Calmar recalculés avec √365
- [ ] Test mis à jour

---

### SPRINT 3.2 — Unifier l'estimation de half-life

**Faille :** 🟡 m-02 — Half-life estimation en double  
**Impact score :** Cohérence interne

**Action :** Faire de `SpreadHalfLifeEstimator` la seule source de vérité.

**Fichier :** `models/cointegration.py` → `half_life_mean_reversion()`
>>>>>>> origin/main

```python
def half_life_mean_reversion(spread: pd.Series, max_lag: int = 60) -> Optional[int]:
    """Delegate to SpreadHalfLifeEstimator for single source of truth."""
    estimator = SpreadHalfLifeEstimator(lookback=min(252, len(spread)))
    hl = estimator.estimate_half_life_from_spread(spread, validate=True)
    return int(np.round(hl)) if hl is not None else None
```

**Definition of Done :**
<<<<<<< HEAD
- [ ] Une seule impl├®mentation AR(1) dans `SpreadHalfLifeEstimator`
- [ ] `half_life_mean_reversion()` est un wrapper qui d├®l├¿gue
- [ ] Test de non-r├®gression : m├¬mes r├®sultats qu'avant sur les cas de test existants

---

### SPRINT 3.3 ÔÇö Nettoyage de l'univers YAML

**Faille :** ­ƒƒí m-03 ÔÇö BAC dupliqu├®  
**Impact score :** Propret├® de configuration

**Fichier :** `config/dev.yaml`
- Supprimer la deuxi├¿me occurrence de `BAC`
- Supprimer `FTT/USD`
- Ajouter commentaire de date de derni├¿re validation

**Definition of Done :**
- [ ] Aucun doublon dans dev.yaml ni prod.yaml
- [ ] Validation automatique (script ou test) d├®tectant les doublons

---

### SPRINT 3.4 ÔÇö Tests rigoureux avec assertions de valeur

**Faille :** ­ƒƒí m-04 ÔÇö Tests trop permissifs  
=======
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
>>>>>>> origin/main
**Impact score :** Confiance dans la suite de tests

#### Actions

**Fichiers :** tous les fichiers `tests/**`

Renforcer les assertions :

```python
# AVANT (trop permissif) :
assert regime_state is not None
assert regime_state.regime in [VolatilityRegime.LOW, VolatilityRegime.NORMAL, VolatilityRegime.HIGH]

<<<<<<< HEAD
# APR├êS (assertion de valeur) :
=======
# APRÈS (assertion de valeur) :
>>>>>>> origin/main
assert regime_state.regime == VolatilityRegime.HIGH, \
    f"Expected HIGH regime for vol spike, got {regime_state.regime}"
```

<<<<<<< HEAD
**Tests ├á ajouter/renforcer :**

| Test | Assertion manquante |
|------|---------------------|
| `test_strategy.py` | Z=2.5 ÔåÆ signal long ; Z=-2.5 ÔåÆ signal short ; Z=0.3 ÔåÆ no signal |
| `test_regime_detector.py` | Volatilit├® 99e percentile ÔåÆ HIGH (pas "any of the three") |
| `test_backtest_runner.py` | V├®rifier que les trades sont r├®ellement ex├®cut├®s (count > 0) |
| `test_oos_validator.py` | Supprimer les `if result.oos_half_life:` guards ÔåÆ assert direct |
| `test_walk_forward.py` | V├®rifier le data leakage : train.index.max() < test.index.min() |
=======
**Tests à ajouter/renforcer :**

| Test | Assertion manquante |
|------|---------------------|
| `test_strategy.py` | Z=2.5 → signal long ; Z=-2.5 → signal short ; Z=0.3 → no signal |
| `test_regime_detector.py` | Volatilité 99e percentile → HIGH (pas "any of the three") |
| `test_backtest_runner.py` | Vérifier que les trades sont réellement exécutés (count > 0) |
| `test_oos_validator.py` | Supprimer les `if result.oos_half_life:` guards → assert direct |
| `test_walk_forward.py` | Vérifier le data leakage : train.index.max() < test.index.min() |
>>>>>>> origin/main

**Nouveau test :** `tests/integration/test_end_to_end.py`

```python
def test_full_pipeline_no_leakage():
    """
<<<<<<< HEAD
    Test int├®gral : data ÔåÆ strategy ÔåÆ risk ÔåÆ metrics
    V├®rifie qu'aucune donn├®e future n'est utilis├®e.
=======
    Test intégral : data → strategy → risk → metrics
    Vérifie qu'aucune donnée future n'est utilisée.
>>>>>>> origin/main
    """
    ...

def test_backtest_matches_live_signals():
    """
<<<<<<< HEAD
    V├®rifie que le StrategyBacktestSimulator produit
    les m├¬mes signaux que PairTradingStrategy.generate_signals()
    sur les m├¬mes donn├®es.
=======
    Vérifie que le StrategyBacktestSimulator produit
    les mêmes signaux que PairTradingStrategy.generate_signals()
    sur les mêmes données.
>>>>>>> origin/main
    """
    ...
```

**Definition of Done :**
<<<<<<< HEAD
- [ ] Tous les tests de r├®gime v├®rifient la valeur exacte attendue
- [ ] Tests de signal v├®rifient la direction (long/short) pour des z-scores donn├®s
- [ ] Test end-to-end data ÔåÆ metrics sans mocking
- [ ] Test anti-leakage formel
- [ ] Couverture : chaque faille corrig├®e a au moins 2 tests d├®di├®s

---

### SPRINT 3.5 ÔÇö Cache adaptatif

**Faille :** ­ƒƒí m-05 ÔÇö Cache de 24h trop long  
**Impact score :** R├®activit├® live
=======
- [ ] Tous les tests de régime vérifient la valeur exacte attendue
- [ ] Tests de signal vérifient la direction (long/short) pour des z-scores donnés
- [ ] Test end-to-end data → metrics sans mocking
- [ ] Test anti-leakage formel
- [ ] Couverture : chaque faille corrigée a au moins 2 tests dédiés

---

### SPRINT 3.5 — Cache adaptatif

**Faille :** 🟡 m-05 — Cache de 24h trop long  
**Impact score :** Réactivité live
>>>>>>> origin/main

**Fichier :** `strategies/pair_trading.py`

```python
def load_cached_pairs(self, max_age_hours: int = None) -> Optional[List[Tuple]]:
    """
<<<<<<< HEAD
    Adapte le TTL du cache au r├®gime de march├® :
    - R├®gime NORMAL : 12h (default)
    - R├®gime HIGH : 2h (re-d├®couverte fr├®quente en haute vol)
    - R├®gime LOW : 24h (march├® calme, paires stables)
=======
    Adapte le TTL du cache au régime de marché :
    - Régime NORMAL : 12h (default)
    - Régime HIGH : 2h (re-découverte fréquente en haute vol)
    - Régime LOW : 24h (marché calme, paires stables)
>>>>>>> origin/main
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
<<<<<<< HEAD
- [ ] TTL du cache adapt├® au r├®gime de march├®
- [ ] HIGH ÔåÆ 2h, NORMAL ÔåÆ 12h, LOW ÔåÆ 24h
- [ ] Test : simuler r├®gime HIGH ÔåÆ cache expir├® apr├¿s 3h

---

## PHASE 4 ÔÇö VALIDATION INT├ëGRALE & OPTIMISATIONS AVANC├ëES

> Prouver formellement que les scores sont 10/10.  
> Ajouter les optimisations qui diff├®rencient EDGECORE.

---

### SPRINT 4.1 ÔÇö Test Johansen multi-vari├®

**Impact score :** Test de coint├®gration ÔåÆ 10/10 (certification compl├¿te)
=======
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
>>>>>>> origin/main

**Nouveau fichier :** `models/johansen.py`

```python
from statsmodels.tsa.vector_ar.vecm import coint_johansen

class JohansenCointegrationTest:
    """
<<<<<<< HEAD
    Test de Johansen pour d├®tecter les relations de coint├®gration multi-vari├®es.
    
    Compl├®mente Engle-Granger (bivari├®) :
    - D├®tecte le rang de coint├®gration (combien de relations lin├®aires)
    - Permet les syst├¿mes de plus de 2 variables
    - Plus puissant que EG pour les petits ├®chantillons
=======
    Test de Johansen pour détecter les relations de cointégration multi-variées.
    
    Complémente Engle-Granger (bivarié) :
    - Détecte le rang de cointégration (combien de relations linéaires)
    - Permet les systèmes de plus de 2 variables
    - Plus puissant que EG pour les petits échantillons
>>>>>>> origin/main
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
        
<<<<<<< HEAD
        # D├®terminer le rang de coint├®gration
=======
        # Déterminer le rang de cointégration
>>>>>>> origin/main
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

<<<<<<< HEAD
**Int├®gration :** si Engle-Granger d├®tecte une paire, confirmer avec Johansen (double validation).

**Definition of Done :**
- [ ] Johansen impl├®ment├® et appelable
- [ ] Utilis├® en confirmation apr├¿s EG (double screening : EG + Johansen)
- [ ] Test : paire connue coint├®gr├®e ÔåÆ rang ÔëÑ 1
- [ ] Test : paire random ÔåÆ rang = 0

---

### SPRINT 4.2 ÔÇö Kalman Filter pour hedge ratio dynamique

**Impact score :** Construction du spread 6/10 ÔåÆ 10/10
=======
**Intégration :** si Engle-Granger détecte une paire, confirmer avec Johansen (double validation).

**Definition of Done :**
- [ ] Johansen implémenté et appelable
- [ ] Utilisé en confirmation après EG (double screening : EG + Johansen)
- [ ] Test : paire connue cointégrée → rang ≥ 1
- [ ] Test : paire random → rang = 0

---

### SPRINT 4.2 — Kalman Filter pour hedge ratio dynamique

**Impact score :** Construction du spread 6/10 → 10/10
>>>>>>> origin/main

**Nouveau fichier :** `models/kalman_hedge.py`

```python
class KalmanHedgeRatio:
    """
    Estimation dynamique du hedge ratio via Kalman Filter.
    
<<<<<<< HEAD
    Remplace l'OLS statique par un ╬▓ adaptatif bar-par-bar :
    - ├ëtat : ╬▓_t (hedge ratio au temps t)
    - Observation : y_t = ╬▓_t ├ù x_t + ╬Á_t
    - Transition : ╬▓_t = ╬▓_{t-1} + ╬À_t
    
    Avantages :
    - Pas besoin de fen├¬tre rolling (adapte lisiblement)
    - D├®tecte les breakdowns en temps r├®el (innovation > threshold)
    - Produit un ╬▓ avec intervalle de confiance
=======
    Remplace l'OLS statique par un β adaptatif bar-par-bar :
    - État : β_t (hedge ratio au temps t)
    - Observation : y_t = β_t × x_t + ε_t
    - Transition : β_t = β_{t-1} + η_t
    
    Avantages :
    - Pas besoin de fenêtre rolling (adapte lisiblement)
    - Détecte les breakdowns en temps réel (innovation > threshold)
    - Produit un β avec intervalle de confiance
>>>>>>> origin/main
    """
    
    def __init__(self, delta: float = 1e-4, ve: float = 1e-3):
        self.delta = delta  # Vitesse d'adaptation
        self.ve = ve        # Variance d'observation
        self.beta = None
<<<<<<< HEAD
        self.P = None       # Covariance de l'├®tat
=======
        self.P = None       # Covariance de l'état
>>>>>>> origin/main
        self.R = None       # Covariance d'observation
    
    def update(self, y: float, x: float) -> Tuple[float, float, float]:
        """
<<<<<<< HEAD
        Met ├á jour le hedge ratio avec une nouvelle observation.
=======
        Met à jour le hedge ratio avec une nouvelle observation.
>>>>>>> origin/main
        
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
        
<<<<<<< HEAD
        # Innovation normalis├®e (pour d├®tection de breakdown)
=======
        # Innovation normalisée (pour détection de breakdown)
>>>>>>> origin/main
        innovation = spread / np.sqrt(S) if S > 0 else 0.0
        
        return self.beta, spread, innovation
```

<<<<<<< HEAD
**Int├®gration :** `DynamicSpreadModel` utilise `KalmanHedgeRatio` au lieu de OLS fixe.

**Definition of Done :**
- [ ] Kalman Filter produit un ╬▓ adaptatif bar-par-bar
- [ ] Innovation normalis├®e > 3¤â ÔåÆ alerte breakdown
- [ ] Test : changement structurel de ╬▓ ÔåÆ Kalman s'adapte en < 20 barres
- [ ] Comparaison formelle : Kalman vs OLS rolling sur 3 ans de donn├®es ÔåÆ Kalman meilleur Sharpe

---

### SPRINT 4.3 ÔÇö Newey-West HAC et robustesse OLS

**Impact score :** Construction du spread ÔåÆ 10/10
=======
**Intégration :** `DynamicSpreadModel` utilise `KalmanHedgeRatio` au lieu de OLS fixe.

**Definition of Done :**
- [ ] Kalman Filter produit un β adaptatif bar-par-bar
- [ ] Innovation normalisée > 3σ → alerte breakdown
- [ ] Test : changement structurel de β → Kalman s'adapte en < 20 barres
- [ ] Comparaison formelle : Kalman vs OLS rolling sur 3 ans de données → Kalman meilleur Sharpe

---

### SPRINT 4.3 — Newey-West HAC et robustesse OLS

**Impact score :** Construction du spread → 10/10
>>>>>>> origin/main

**Fichier :** `models/cointegration.py`

```python
def engle_granger_test_robust(y, x, ...):
    """Version avec erreurs standards Newey-West HAC."""
    import statsmodels.api as sm
    
    X = sm.add_constant(x.values)
    model = sm.OLS(y.values, X)
    
<<<<<<< HEAD
    # Newey-West HAC pour autocorr├®lation et h├®t├®rosc├®dasticit├®
=======
    # Newey-West HAC pour autocorrélation et hétéroscédasticité
>>>>>>> origin/main
    results = model.fit(cov_type='HAC', cov_kwds={'maxlags': 12})
    
    residuals = results.resid
    beta = results.params[1]
    intercept = results.params[0]
    
<<<<<<< HEAD
    # ADF sur r├®sidus
=======
    # ADF sur résidus
>>>>>>> origin/main
    adf_result = adfuller(residuals, regression='c', autolag='AIC')
    # ...
```

**Definition of Done :**
<<<<<<< HEAD
- [ ] OLS avec erreurs HAC Newey-West impl├®ment├®
- [ ] Utilis├® en parall├¿le de l'OLS standard pour comparaison
- [ ] Si les conclusions divergent ÔåÆ paire rejet├®e (consensus requis)

---

### SPRINT 4.4 ÔÇö Self-contained risk dans la strat├®gie

**Impact score :** D├®pendance au risk engine 3/10 ÔåÆ 10/10

**Fichier :** `strategies/pair_trading.py`

Ajouter des gardes INTERNES ├á la strat├®gie (ind├®pendants du risk engine) :
=======
- [ ] OLS avec erreurs HAC Newey-West implémenté
- [ ] Utilisé en parallèle de l'OLS standard pour comparaison
- [ ] Si les conclusions divergent → paire rejetée (consensus requis)

---

### SPRINT 4.4 — Self-contained risk dans la stratégie

**Impact score :** Dépendance au risk engine 3/10 → 10/10

**Fichier :** `strategies/pair_trading.py`

Ajouter des gardes INTERNES à la stratégie (indépendants du risk engine) :
>>>>>>> origin/main

```python
class PairTradingStrategy(BaseStrategy):
    def __init__(self):
        # ... existant ...
        
<<<<<<< HEAD
        # Self-contained risk limits (strat├®gie autonome)
        self.max_positions = 8  # La strat├®gie elle-m├¬me limite ├á 8
        self.max_drawdown_pct = 0.10  # Arr├¬t si DD > 10% depuis le peak
=======
        # Self-contained risk limits (stratégie autonome)
        self.max_positions = 8  # La stratégie elle-même limite à 8
        self.max_drawdown_pct = 0.10  # Arrêt si DD > 10% depuis le peak
>>>>>>> origin/main
        self.max_daily_trades = 20    # Pas plus de 20 trades/jour
        self.daily_trade_count = 0
        self.peak_equity = None
        self.current_equity = None
    
    def _check_internal_risk_limits(self) -> Tuple[bool, str]:
        """
<<<<<<< HEAD
        V├®rifie les limites de risque INTERNES ├á la strat├®gie.
        Ind├®pendant du RiskEngine externe.
=======
        Vérifie les limites de risque INTERNES à la stratégie.
        Indépendant du RiskEngine externe.
>>>>>>> origin/main
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
<<<<<<< HEAD
- [ ] La strat├®gie a ses propres limites (max positions, max drawdown, max daily trades)
- [ ] Ces limites sont PLUS strictes que le risk engine (defense in depth)
- [ ] Test : sans risk engine, la strat├®gie se prot├¿ge elle-m├¬me
- [ ] Le risk engine reste actif comme deuxi├¿me couche de protection

---

### SPRINT 4.5 ÔÇö Event-driven backtester avec order book

**Impact score :** Sc├®narios extr├¬mes 4/10 ÔåÆ 10/10
=======
- [ ] La stratégie a ses propres limites (max positions, max drawdown, max daily trades)
- [ ] Ces limites sont PLUS strictes que le risk engine (defense in depth)
- [ ] Test : sans risk engine, la stratégie se protège elle-même
- [ ] Le risk engine reste actif comme deuxième couche de protection

---

### SPRINT 4.5 — Event-driven backtester avec order book

**Impact score :** Scénarios extrêmes 4/10 → 10/10
>>>>>>> origin/main

**Nouveau fichier :** `backtests/event_driven.py`

```python
class EventDrivenBacktester:
    """
    Backtester event-driven avec simulation de carnet d'ordres.
    
    Au lieu de boucler bar-par-bar avec Fill-at-Close :
    - Simule un carnet d'ordres avec spread bid/ask
<<<<<<< HEAD
    - Les ordres sont des limit orders au mid ┬▒ slippage
    - Partial fills si la taille d├®passe X% du volume
    - Gaps de prix entre barres cr├®ent du slippage suppl├®mentaire
=======
    - Les ordres sont des limit orders au mid ± slippage
    - Partial fills si la taille dépasse X% du volume
    - Gaps de prix entre barres créent du slippage supplémentaire
>>>>>>> origin/main
    """
    
    def __init__(self, strategy, cost_model, book_depth_pct: float = 0.02):
        self.strategy = strategy
        self.cost_model = cost_model
        self.book_depth_pct = book_depth_pct
    
    def simulate_fill(self, order, market_state) -> Fill:
        """
        Simule le fill d'un ordre avec :
<<<<<<< HEAD
        - Bid/ask spread estim├® (2├ù slippage)
        - Participation rate ÔåÆ partial fill si > 5% du volume
        - Impact de prix proportionnel ├á la taille
=======
        - Bid/ask spread estimé (2× slippage)
        - Participation rate → partial fill si > 5% du volume
        - Impact de prix proportionnel à la taille
>>>>>>> origin/main
        """
        ...
```

**Definition of Done :**
<<<<<<< HEAD
- [ ] Simulation de fill r├®aliste avec bid/ask spread
- [ ] Partial fills si ordre > 5% du volume
- [ ] Impact de march├® proportionnel ├á la taille
- [ ] Test : comparaison avec l'ancien backtest ÔåÆ r├®sultats plus pessimistes (confirmation r├®alisme)

---

### SPRINT 4.6 ÔÇö Monitoring de corr├®lation rolling entre legs

**Impact score :** R├®sistance aux r├®gimes ÔåÆ 10/10
=======
- [ ] Simulation de fill réaliste avec bid/ask spread
- [ ] Partial fills si ordre > 5% du volume
- [ ] Impact de marché proportionnel à la taille
- [ ] Test : comparaison avec l'ancien backtest → résultats plus pessimistes (confirmation réalisme)

---

### SPRINT 4.6 — Monitoring de corrélation rolling entre legs

**Impact score :** Résistance aux régimes → 10/10
>>>>>>> origin/main

**Fichier :** `strategies/pair_trading.py`

```python
def _check_leg_correlation_stability(self, y: pd.Series, x: pd.Series, 
                                       pair_key: str, window: int = 30) -> bool:
    """
<<<<<<< HEAD
    V├®rifie que la corr├®lation entre les deux legs reste stable.
    Si la corr├®lation chute > 30% vs la moyenne historique ÔåÆ signal d'alerte.
=======
    Vérifie que la corrélation entre les deux legs reste stable.
    Si la corrélation chute > 30% vs la moyenne historique → signal d'alerte.
>>>>>>> origin/main
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

<<<<<<< HEAD
**Int├®gration :** avant `generate_signals()`, v├®rifier la corr├®lation des legs ÔåÆ si breakdown, fermer la position.

**Definition of Done :**
- [ ] Corr├®lation rolling calcul├®e ├á chaque barre pour chaque paire active
- [ ] Chute > 50% ÔåÆ position ferm├®e + paire exclue
- [ ] Monitoring logu├® pour analytics

---

## MATRICE DE TRA├çABILIT├ë FAILLE ÔåÆ CORRECTION

| ID | Faille | Sprint | Fichiers principaux | Score impact├® |
|----|--------|--------|---------------------|---------------|
| ­ƒö┤ C-01 | Divergence backtest/live | 1.1 | `backtests/strategy_simulator.py` (nouveau), `runner.py` | Backtesting 2ÔåÆ8 |
| ­ƒö┤ C-02 | Look-ahead bias | 1.2 | `backtests/strategy_simulator.py` | Backtesting +2 |
| ­ƒö┤ C-03 | Walk-forward invalide | 1.3 | `backtests/walk_forward.py` | Validation OOS 5ÔåÆ9 |
| ­ƒö┤ C-04 | Cython bypass Bonferroni | 1.4 | `models/cointegration.py`, `backtests/runner.py` | Coint├®gration 7ÔåÆ10 |
| ­ƒö┤ C-05 | Absence time stop | 1.5 | `execution/time_stop.py` (nouveau), `strategies/pair_trading.py` | Entr├®e/sortie 4ÔåÆ7 |
| ­ƒö┤ C-06 | Corr├®lation spreads | 1.6 | `risk/spread_correlation.py` (nouveau), `strategies/pair_trading.py` | Corr├®lation 1ÔåÆ9 |
| ­ƒƒá M-01 | Stationnarit├® suppos├®e | 2.1 | `models/stationarity_monitor.py` (nouveau) | R├®gimes 5ÔåÆ8 |
| ­ƒƒá M-02 | Granularit├® d├®tection | 2.2 | `hedge_ratio_tracker.py`, `regime_detector.py`, `settings.py` | R├®gimes ÔåÆ9 |
| ­ƒƒá M-03 | Frais sous-estim├®s | 2.3 | `backtests/cost_model.py` (nouveau), `runner.py` | Co├╗ts 4ÔåÆ10 |
| ­ƒƒá M-04 | Survivorship bias | 2.4 | `dev.yaml`, `prod.yaml`, `data/delisting_guard.py` (nouveau) | Liquidit├® 2ÔåÆ9 |
| ­ƒƒá M-05 | ML non valid├® OOS | 2.5 | `models/ml_threshold_optimizer.py` | Entr├®e/sortie ÔåÆ9 |
| ­ƒƒá M-06 | Fallback synth├®tique | 2.6 | `backtests/runner.py` | Backtesting ÔåÆ10 |
| ­ƒƒá M-07 | Pas de test I(1) | 2.7 | `models/cointegration.py` | Coint├®gration ÔåÆ10 |
| ­ƒƒá M-08 | Pas d'outliers | 2.8 | `strategies/pair_trading.py`, `models/spread.py` | Spread 6ÔåÆ9 |
| ­ƒƒí m-01 | ÔêÜ252 vs ÔêÜ365 | 3.1 | `backtests/metrics.py` | M├®triques |
| ­ƒƒí m-02 | Half-life double | 3.2 | `models/cointegration.py` | Spread ÔåÆ10 |
| ­ƒƒí m-03 | BAC doublon | 3.3 | `config/dev.yaml` | Config |
| ­ƒƒí m-04 | Tests permissifs | 3.4 | `tests/**` | Confiance |
| ­ƒƒí m-05 | Cache 24h | 3.5 | `strategies/pair_trading.py` | R├®activit├® |
| ÔÇö | Johansen | 4.1 | `models/johansen.py` (nouveau) | Coint├®gration 10/10 |
| ÔÇö | Kalman hedge | 4.2 | `models/kalman_hedge.py` (nouveau) | Spread 10/10 |
| ÔÇö | Newey-West HAC | 4.3 | `models/cointegration.py` | Spread 10/10 |
| ÔÇö | Self-contained risk | 4.4 | `strategies/pair_trading.py` | D├®pendance ÔåÆ10 |
| ÔÇö | Event-driven backtest | 4.5 | `backtests/event_driven.py` (nouveau) | Sc├®narios 10/10 |
| ÔÇö | Corr├®lation legs rolling | 4.6 | `strategies/pair_trading.py` | R├®gimes 10/10 |

---

## PROJECTION DES SCORES POST-REM├ëDIATION

### Qualit├® statistique : 10 / 10

| Composante | Avant | Apr├¿s Phase 1 | Apr├¿s Phase 2 | Apr├¿s Phase 4 |
|-----------|-------|---------------|---------------|---------------|
| Test de coint├®gration | 7 | 10 (C-04 fix) | 10 (+ I(1) check) | 10 (+ Johansen) |
| Construction du spread | 6 | 6 | 9 (outliers) | 10 (Kalman + HAC) |
| Z-score | 7 | 7 | 8 (outlier clamp) | 10 (Kalman spreads) |
| Entr├®e/sortie | 4 | 7 (time stop) | 9 (ML v├ílid OOS) | 10 (self-risk) |
| Backtesting | 2 | 8 (unification) | 10 (no synth) | 10 (event-driven) |
| Validation OOS | 5 | 9 (WF r├®el) | 10 (stationarity) | 10 |

### Robustesse r├®elle : 10 / 10

| Composante | Avant | Apr├¿s Phase 1 | Apr├¿s Phase 2 | Apr├¿s Phase 4 |
|-----------|-------|---------------|---------------|---------------|
| R├®sistance r├®gimes | 5 | 5 | 9 (granularit├® + stationary) | 10 (leg corr) |
| Gestion liquidit├® | 2 | 2 | 9 (filtre + delisting) | 10 (order book) |
| Co├╗ts r├®alistes | 4 | 4 | 10 (cost model) | 10 |
| Corr├®lation positions | 1 | 9 (spread guard) | 9 | 10 (+ leg corr) |
| D├®pendance risk engine | 3 | 3 | 3 | 10 (self risk) |
| Sc├®narios extr├¬mes | 4 | 5 (time stop) | 8 (faster detect) | 10 (event-driven) |

### Probabilit├® de survie 12 mois

| Phase | Probabilit├® |
|-------|-------------|
| Avant (├®tat actuel) | 15-25% |
=======
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
>>>>>>> origin/main
| Post Phase 1 | 45-55% |
| Post Phase 2 | 65-75% |
| Post Phase 3 | 70-78% |
| Post Phase 4 | **80-88%** |

---

## PLANNING CALENDAIRE

```
<<<<<<< HEAD
Semaine 1 (17-21 f├®v) : Sprints 1.1 + 1.2 + 1.4
                         ÔåÆ Backtest unifi├®, look-ahead ├®limin├®, Bonferroni fix├®

Semaine 2 (24-28 f├®v) : Sprints 1.3 + 1.5 + 1.6
                         ÔåÆ Walk-forward r├®el, time stop, spread correlation

Semaine 3 (03-07 mar) : Sprints 2.1 + 2.2 + 2.3 + 2.4
                         ÔåÆ Stationnarit├®, granularit├®, co├╗ts, liquidit├®

Semaine 4 (10-14 mar) : Sprints 2.5 + 2.6 + 2.7 + 2.8
                         ÔåÆ ML OOS, no synthetic, I(1) check, outliers

Semaine 5 (17-21 mar) : Sprints 3.1 ÔåÆ 3.5
                         ÔåÆ Polish : annualisation, half-life, YAML, tests, cache

Semaine 6 (24-28 mar) : Sprints 4.1 ÔåÆ 4.6
                         ÔåÆ Johansen, Kalman, HAC, self-risk, event-driven, leg corr

Semaine 7 (31 mar - 04 avr) : Validation int├®grale
                         ÔåÆ Run complet WF 2023-2025, paper trading launch
=======
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
>>>>>>> origin/main
```

---

<<<<<<< HEAD
## CRIT├êRES DE GATE (GO/NO-GO)

### Gate 1 ÔÇö Fin Phase 1 (28 f├®vrier)

| Crit├¿re | Seuil |
|---------|-------|
| Backtest unifi├® op├®rationnel | Ô£à / ÔØî |
| Walk-forward avec re-training | Ô£à / ÔØî |
| Zero look-ahead bias (test formel) | Ô£à / ÔØî |
| Tous tests existants passent | Ô£à / ÔØî |
| Sharpe OOS walk-forward > 0.5 | Valeur mesur├®e |

### Gate 2 ÔÇö Fin Phase 2 (14 mars)

| Crit├¿re | Seuil |
|---------|-------|
| Co├╗ts r├®alistes ÔëÑ 40 bps round-trip | Ô£à / ÔØî |
| Filtre liquidit├® actif | Ô£à / ÔØî |
| Walk-forward Sharpe OOS > 0.5 avec co├╗ts r├®alistes | Valeur mesur├®e |
| ML thresholds valid├®s OOS OU d├®sactiv├®s | Ô£à / ÔØî |
| Zero fallback synth├®tique | Ô£à / ÔØî |

### Gate 3 ÔÇö Go Paper Trading (28 mars)

| Crit├¿re | Seuil |
|---------|-------|
| Scores qualit├® ÔëÑ 9/10 ET robustesse ÔëÑ 9/10 | Ô£à / ÔØî |
| Walk-forward 2023-2025 : Sharpe > 0.7, DD < 15% | Valeurs mesur├®es |
| 100% tests passent (0 skip, 0 fail) | Ô£à / ÔØî |
| Johansen + Kalman op├®rationnels | Ô£à / ÔØî |
| Paper trading sandbox configur├® | Ô£à / ÔØî |

### Gate 4 ÔÇö Go Live (apr├¿s 3 mois de paper)

| Crit├¿re | Seuil |
|---------|-------|
| Paper trading Sharpe > 0.5 sur 90 jours | Valeur mesur├®e |
| Max DD paper < 10% | Valeur mesur├®e |
| 0 incidents critiques en paper | Ô£à / ÔØî |
| Audit externe ind├®pendant positif | Ô£à / ÔØî |

---

## FICHIERS ├Ç CR├ëER (R├ëCAPITULATIF)

| Fichier | Sprint | Description |
|---------|--------|-------------|
| `backtests/strategy_simulator.py` | 1.1 | Simulateur unifi├® backtest=live |
| `backtests/cost_model.py` | 2.3 | Mod├¿le de co├╗ts r├®aliste 4-legs |
| `backtests/event_driven.py` | 4.5 | Backtester event-driven |
| `execution/time_stop.py` | 1.5 | Time stop manager |
| `risk/spread_correlation.py` | 1.6 | Garde de corr├®lation des spreads |
| `models/stationarity_monitor.py` | 2.1 | Monitoring continu ADF rolling |
| `models/johansen.py` | 4.1 | Test de Johansen multi-vari├® |
| `models/kalman_hedge.py` | 4.2 | Kalman filter pour ╬▓ dynamique |
| `data/delisting_guard.py` | 2.4 | D├®tection de tokens mourants |
| `tests/integration/test_end_to_end.py` | 3.4 | Test int├®gral pipeline |
=======
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
>>>>>>> origin/main
| `tests/integration/test_no_leakage.py` | 3.4 | Test anti-look-ahead |

---

## MOT DE FIN

<<<<<<< HEAD
Ce plan transforme EDGECORE d'une **strat├®gie fragile (4.5/10 + 3.5/10)** en un **syst├¿me institutionnel-grade (10/10 + 10/10)** en 7 semaines.

La cl├® est la **Phase 1** : tant que le backtest ne refl├¿te pas la strat├®gie r├®elle, aucune d├®cision ne peut ├¬tre prise sur des bases solides. Les Phases 2-4 construisent la robustesse et la diff├®renciation.

Le facteur critique de succ├¿s : **ne jamais sacrifier la rigueur statistique pour la v├®locit├® de d├®veloppement.** Chaque sprint a un Definition of Done explicite. Si un gate ├®choue ÔåÆ on ne passe pas ├á la phase suivante.

> **Objectif final : une strat├®gie dont chaque composant est prouv├®, test├®, et valid├® OOS avant qu'un centime de capital r├®el ne soit engag├®.**

---

*Plan g├®n├®r├® le 13 f├®vrier 2026 ├á partir de AUDIT_STRATEGIQUE_EDGECORE_V2.md*
=======
Ce plan transforme EDGECORE d'une **stratégie fragile (4.5/10 + 3.5/10)** en un **système institutionnel-grade (10/10 + 10/10)** en 7 semaines.

La clé est la **Phase 1** : tant que le backtest ne reflète pas la stratégie réelle, aucune décision ne peut être prise sur des bases solides. Les Phases 2-4 construisent la robustesse et la différenciation.

Le facteur critique de succès : **ne jamais sacrifier la rigueur statistique pour la vélocité de développement.** Chaque sprint a un Definition of Done explicite. Si un gate échoue → on ne passe pas à la phase suivante.

> **Objectif final : une stratégie dont chaque composant est prouvé, testé, et validé OOS avant qu'un centime de capital réel ne soit engagé.**

---

*Plan généré le 13 février 2026 à partir de AUDIT_STRATEGIQUE_EDGECORE_V2.md*
>>>>>>> origin/main
