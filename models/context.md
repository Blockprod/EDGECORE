# models/ — Context Module

## Responsabilité

Primitives mathématiques du stat-arb : tests de cointégration, calcul de spread, hedge ratio (OLS et Kalman), z-score, half-life, régimes de marché, ML thresholds.

**Ce module est purement fonctionnel.** Il calcule des métriques à partir de séries temporelles. Il ne prend aucune décision de trading, ne soumet aucun ordre, ne lit pas de config.

---

## Ce que ce module FAIT

| Fichier | Fonction/Classe principale | Rôle |
|---------|---------------------------|------|
| `cointegration.py` | `engle_granger_test()`, `half_life_mean_reversion()`, `verify_integration_order()` | Tests EG + Johansen + Newey-West HAC |
| `cointegration_fast.pyx` | `half_life_fast()`, `engle_granger_fast()` | Accélération Cython (compilé en .pyd) |
| `spread.py` | `SpreadModel` | Calcul spread = Y - β×X, résidus, vol normalisée |
| `kalman_hedge.py` | `KalmanHedgeRatioEstimator` | Hedge ratio dynamique barre-par-barre |
| `johansen.py` | `johansen_test()` | Test de rang de cointégration (Johansen) |
| `half_life_estimator.py` | `SpreadHalfLifeEstimator` | AR(1) OU process, estimation demi-vie |
| `hedge_ratio_tracker.py` | `HedgeRatioTracker` | Maintient état Kalman par paire + réévaluation périodique |
| `regime_detector.py` | `RegimeDetector` | SPY-based: bull/bear/neutral (MA 50/200 + vol) |
| `markov_regime.py` | `MarkovRegimeSwitching` | Régimes Markov cachés pour vol switching |
| `structural_break.py` | `StructuralBreakDetector` | Chow test + CUSUM pour breaks dans cointégration |
| `stationarity_monitor.py` | `StationarityMonitor` | ADF rolling sur spread pour détecter non-stationnarité |
| `adaptive_thresholds.py` | `AdaptiveThresholdCalculator` | Calcul seuils adaptatifs par régime de vol |
| `ml_threshold_optimizer.py` | `MLThresholdOptimizer` | Optimisation ML des seuils z-score par paire |
| `ml_threshold_validator.py` | `MLThresholdValidator` | Validation OOS des thresholds ML |
| `model_retraining.py` | `ModelRetrainingScheduler` | Re-fit automatique des modèles ML |
| `performance_optimizer.py` | `LRUSpreadModelCache`, `VectorizedSignalGenerator` | LRU cache + vectorisation signaux |
| `performance_optimizer_s41.py` | (idem + ML integration) | **Sprint file — doublon** de `performance_optimizer.py` |

---

## Ce que ce module NE FAIT PAS

- ❌ Génère des signaux de trading (BUY/SELL) → `signal_engine/`
- ❌ Vérifie les limites de risque → `risk_engine/`
- ❌ Se connecte à IBKR → `execution/`
- ❌ Lit `get_settings()` pour les seuils opérationnels (seul exception : `cointegration.py` qui lit `bonferroni_correction` si passé en argument)

---

## Accélération Cython

### Fichiers compilés
```
models/cointegration_fast.pyx          → source Cython
models/cointegration_fast.cp311-win_amd64.pyd  → Python 3.11 (venv)
models/cointegration_fast.cp313-win_amd64.pyd  → Python 3.13 (system)
```

### Compilation
```powershell
venv\Scripts\python.exe setup.py build_ext --inplace
# Résultat : les deux .pyd créés ou mis à jour
```

### Utilisation dans cointegration.py
```python
try:
    from models.cointegration_fast import half_life_fast, engle_granger_fast
    CYTHON_COINTEGRATION_AVAILABLE = True
except ImportError:
    CYTHON_COINTEGRATION_AVAILABLE = False

# NB : half_life_mean_reversion() délègue TOUJOURS à SpreadHalfLifeEstimator (Python).
# Le bypass Cython a été supprimé car les résultats divergeaient légèrement.
# Cython accessible uniquement via import direct de cointegration_fast.
```

---

## Contrats

### `engle_granger_test(y, x, ...) → dict`
```python
{
    'is_cointegrated': bool,
    'adf_pvalue': float,        # p-value ADF sur les résidus
    'beta': float,              # hedge ratio OLS
    'residuals': np.ndarray,
    'critical_values': dict,    # {'1%': float, '5%': float, '10%': float}
}
```

### `half_life_mean_reversion(spread_series) → Optional[float]`
Retourne la demi-vie en barres. `None` si le spread n'est pas mean-reverting.  
Valeurs typiques : 5–70 barres (jours).

### `SpreadModel.calculate(prices_df, sym1, sym2, use_kalman=True) → SpreadResult`
```python
# SpreadResult attributes :
spread: pd.Series
beta: float
half_life: float
z_score: pd.Series       # (spread - mean) / std
normalized_vol: float
```

### `KalmanHedgeRatioEstimator.update(price_x, price_y) → (float, float)`
Retourne `(beta_t, spread_t)`. Beta mis à jour barre-par-barre.

---

## Dépendances internes

```
models/cointegration.py     ←── models/cointegration_fast (optionnel)
                            ←── models/johansen.py
                            ←── models/half_life_estimator.py
models/spread.py            ←── models/kalman_hedge.py
models/regime_detector.py   ←── (standalone — data externe : SPY prices)
models/hedge_ratio_tracker.py ←── models/kalman_hedge.py
models/stationarity_monitor.py ←── models/half_life_estimator.py
models/ml_threshold_optimizer.py ←── models/adaptive_thresholds.py
```

---

## Points d'attention

1. **`performance_optimizer_s41.py`** est un doublon de `performance_optimizer.py` (sprint S4.1). Aucun module de production ne l'importe. Ne pas en ajouter.

2. **Johansen test** (`models/johansen.py`) : utilise `statsmodels.tsa.vector_ar.vecm`. Les résultats dépendent du nombre de lags — défaut `maxlags=None` (AIC auto-selection).

3. **Stationnarité** : `StationarityMonitor` tourne un ADF sur la fenêtre roulante `leg_correlation_window=30 bars`. Si p-value > 0.05 sur 3 barres consécutives → alerte non-stationnarité.

4. **Cache par régime** : `LRUSpreadModelCache` dans `performance_optimizer.py` est partagé entre paires via singleton. Capacité : 100 modèles. Eviction LRU.
