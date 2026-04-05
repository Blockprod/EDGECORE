---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: plan_corrections_prioritaires.md
derniere_revision: 2026-04-05
creation: 2026-04-05 à 14:00
---

# Plan d'action — Corrections prioritaires EDGECORE

**Date :** 2026-04-05  
**Scope :** 4 points identifiés lors de l'évaluation qualitative (score 8.3/10)

---

## Tableau synthèse

| ID   | Titre                                    | Sévérité | Impact                                     | Effort   | Statut      |
|------|------------------------------------------|----------|--------------------------------------------|----------|-------------|
| P-01 | Corporate actions (dividendes, splits)   | 🔴 Haute  | Backtests faussés après ex-date, positions live corrompues | Moyen-Haut | À faire |
| P-02 | Retry absent dans `_live_fill` du router | 🟠 Moyen  | Erreurs IBKR transitoires non-retentées au niveau routeur  | Faible   | À faire     |
| P-03 | Slippage hardcodé B5-02                  | 🟡 Faible | Aucun (déjà résolu)                        | —        | ✅ Résolu   |
| P-04 | `print()` résiduels backtests            | 🟡 Faible | Output mixte structlog/print en backtest   | Très faible | À faire  |

---

## P-01 — Gestion des corporate actions 🔴

### Contexte
Aucun mécanisme n'ajuste les prix OHLCV ni les quantités de position lors d'un split ou d'un versement de dividende. Conséquences :
- **Backtest** : P&L inexact après chaque ex-date (jump artificiel sur les prix bruts).
- **Live** : hedge ratio β et z-score calculés sur des séries non-ajustées après split.
- **Walk-forward** : les fenêtres qui enjambent un corporate event produisent des cointégrations instables.

### Fichiers concernés
| Fichier | Rôle actuel | Modification attendue |
|---------|-------------|----------------------|
| `data/loader.py` | Chargement OHLCV IBKR | Ajouter `adjust_prices()` post-chargement |
| `data/preprocessing.py` | Nettoyage des séries | Ajouter détection et marquage des ex-dates |
| `data/` (nouveau) | — | Créer `corporate_actions.py` |
| `backtests/event_driven.py` | Simulation tick par tick | Déclencher ajustement au crossing d'une ex-date |
| `config/schemas.py` | CostConfig | Ajouter `adjust_for_corporate_actions: bool = True` |

### Étapes d'implémentation

#### Étape 1 — `data/corporate_actions.py` (nouveau fichier)
Créer une class `CorporateActionsProvider` :
```python
class CorporateActionsProvider:
    """
    Source : IBKR reqFundamentalData ou Yahoo Finance (fallback).
    Fournit splits et dividendes pour une liste de symboles + plage de dates.
    """
    def get_splits(self, symbol: str, start: date, end: date) -> pd.Series: ...
    def get_dividends(self, symbol: str, start: date, end: date) -> pd.Series: ...
    def adjust_ohlcv(self, df: pd.DataFrame, symbol: str) -> pd.DataFrame: ...
```
- Source primaire : `ibapi.client.EClient.reqFundamentalData` (déjà utilisé pour HTB rates)
- Fallback : `yfinance.Ticker(symbol).splits` / `.dividends`
- Respecter `_ibkr_rate_limiter.acquire()` avant chaque appel IBKR

#### Étape 2 — Intégration dans `data/loader.py`
Après le chargement OHLCV, si `get_settings().data.adjust_for_corporate_actions` est `True` :
```python
provider = CorporateActionsProvider()
for symbol in symbols:
    price_data[symbol] = provider.adjust_ohlcv(price_data[symbol], symbol)
```

#### Étape 3 — Marquage des ex-dates dans `data/preprocessing.py`
Ajouter une colonne `is_exdate: bool` dans le DataFrame pour permettre à `EventDrivenBacktester` de rejeter les signaux générés en fenêtre d'ajustement (±1 bar).

#### Étape 4 — `backtests/event_driven.py`
Au début de chaque itération bar, vérifier si `bar.is_exdate` → forcer la réévaluation de β via `KalmanHedgeRatio.reset()`. Optionnel : sauter l'entrée ce bar-là.

#### Étape 5 — Tests
- `tests/data/test_corporate_actions.py` : tests avec données synthétiques (split 2:1, dividende 1.50$)
- `tests/backtests/test_event_driven_exdate.py` : vérifier que P&L est stable after split

### Validation
```powershell
venv\Scripts\python.exe -m pytest tests/data/test_corporate_actions.py tests/backtests/ -q
```

---

## P-02 — Retry absent dans `_live_fill` du router 🟠

### Contexte
`execution/ibkr_engine.py` implémente `@retry_with_backoff` + circuit breaker 3 états.  
Mais `execution_engine/router.py::_live_fill()` appelle directement `self._ibkr_engine.submit_order(ibkr_order)` sans wrapper retry. Si `IBKRExecutionEngine.submit_order` lève une exception non-retentée en interne, l'ordre est perdu silencieusement.

**Fichiers :**
- `execution_engine/router.py` → méthode `_live_fill()` (ligne ~260)
- `common/retry.py` → `retry_with_backoff` (décorateur ou appelable direct)

### Étapes d'implémentation

#### Étape 1 — Identifier les exceptions IBKR retentables
Les erreurs transitoires IBKR connues : `ConnectionError`, `TimeoutError`, codes TWS 1100 (connexion perdue), 1102 (reconnexion). Ne pas retenter : 201 (ordre rejeté), 103 (duplicate order id).

#### Étape 2 — Wrapper le submit dans `_live_fill`
```python
# execution_engine/router.py
from common.retry import RetryConfig, retry_call

_IBKR_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    initial_delay_seconds=1.0,
    exponential_base=2.0,
    jitter_factor=0.2,
    retryable_exceptions=(ConnectionError, TimeoutError, OSError),
)

# Dans _live_fill, remplacer :
submitted_order_id = self._ibkr_engine.submit_order(ibkr_order)
# Par :
submitted_order_id = retry_call(
    self._ibkr_engine.submit_order,
    args=(ibkr_order,),
    config=_IBKR_RETRY_CONFIG,
    logger=logger,
    context={"symbol": ibkr_order.symbol, "order_id": original_order_id},
)
```

> **Note :** vérifier la signature exacte de `retry_call` dans `common/retry.py` avant implémentation. Si l'API diffère, adapter en conséquence (certains RetryConfig utilisent un decorator, d'autres un callable wrapper).

#### Étape 3 — Logging enrichi
Logger l'attempt number, le délai, et le motif de retry dans structlog (pas de `print()`).

#### Étape 4 — Tests
- `tests/execution_engine/test_router_live_retry.py` : mock `ibkr_engine.submit_order` pour lever `ConnectionError` 2 fois puis réussir → vérifier 1 `TradeExecution` retournée.
- Cas limite : 3 échecs → vérifier que l'exception remonte proprement (pas d'ordre fantôme).

### Validation
```powershell
venv\Scripts\python.exe -m pytest tests/execution_engine/ -q
```

---

## P-03 — Slippage hardcodé B5-02 ✅ RÉSOLU

### Statut
**Déjà corrigé.** Les deux méthodes concernées lisent désormais `get_settings().costs.slippage_bps` :
- `_simulate_fill()` → ligne 166
- `_paper_fill()` → ligne 211

La mention dans `copilot-instructions.md` ("dette B5-02, lignes 162 et 189") est obsolète.  
**Action :** mettre à jour `copilot-instructions.md` pour supprimer la référence B5-02.

---

## P-04 — `print()` résiduels dans backtests 🟡

### Contexte
Deux fichiers du module `backtests/` contiennent des `print()` de debug qui produisent une sortie mixte avec les logs structlog lors des backtests.

| Fichier | Lignes | Type |
|---------|--------|------|
| `backtests/runner.py` | 234, 277, 304, 317, 371, 391 | IBKR Validation progress logs |
| `backtests/strategy_simulator.py` | 322–325, 502, 504, 505, 509, 605 | Debug loop internals |

### Étapes d'implémentation

#### `backtests/runner.py`
Remplacer chaque `print("[IBKR Validation] ...")` par `logger.info(...)` avec un event slug structuré :
```python
# Avant :
print("[IBKR Validation] Démarrage de la validation des symboles...")
# Après :
logger.info("ibkr_validation_start")

# Avant :
print(f"[IBKR Validation] Cache hit ({_age_days:.1f}d old) — skipping IBKR data load.")
# Après :
logger.debug("ibkr_validation_cache_hit", age_days=round(_age_days, 1))
```

#### `backtests/strategy_simulator.py`
Les `print("[DEBUG]...")` sont des traces de boucle interne → remplacer par `logger.debug(...)` :
```python
# Avant :
print("[DEBUG][PRE-BOUCLE] prices_df.index.min=", prices_df.index.min())
# Après :
logger.debug("pre_loop_prices_range",
    index_min=str(prices_df.index.min()),
    index_max=str(prices_df.index.max()),
    n_bars=len(prices_df),
    oos_start_date=str(oos_start_date),
)
```

> Vérifier que `logger = structlog.get_logger(__name__)` est déjà importé dans chaque fichier avant de supprimer les `print()`.

### Validation
```powershell
# Vérifier zéro print() dans backtests/ (hors commentaires)
Select-String -Path "backtests\*.py" -Pattern "^\s*print\(" | Select-Object -First 5

# Tests complets
venv\Scripts\python.exe -m pytest tests/ -q
```

---

## Ordre d'exécution recommandé

```
P-04  →  P-02  →  P-01
(~30 min)  (~1h)  (~4-6h)
```

P-03 est déjà résolu. Commencer par P-04 (changements mécaniques, risque zéro) pour nettoyer le code avant les modifications plus structurelles.
