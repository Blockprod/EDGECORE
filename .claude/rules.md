# EDGECORE — Règles de modification Claude

## Ordre de priorité absolu

1. **Sécurité & correctness** — jamais de régression silencieuse
2. **Cohérence risk tiers** — T1 ≤ T2 ≤ T3 (10% ≤ 15% ≤ 20%)
3. **Zéro DeprecationWarning** — `datetime.now(timezone.utc)` partout
4. **Tests verts** — 2659 passed, 0 skipped, 0 failed (baseline)
5. **Config centralisée** — toujours `get_settings()`, jamais hardcoder
6. **Logging structuré** — `structlog`, jamais `print()`

---

## Avant toute modification

- [ ] Lire le fichier complet avant d'éditer (minimum 50 lignes de contexte)
- [ ] Identifier les imports existants (ne pas dupliquer `timezone`, `structlog`, etc.)
- [ ] Vérifier si la classe/fonction cible est testée dans `tests/`
- [ ] Consulter `architecture/decisions.md` si la modification touche un choix architectural

---

## Règles de codage

### Datetime
```python
# TOUJOURS
from datetime import datetime, timezone
datetime.now(timezone.utc)

# JAMAIS
datetime.utcnow()
datetime.now()  # naive — interdit dans tout contexte de trading
```

### Logging
```python
# TOUJOURS
import structlog
logger = structlog.get_logger(__name__)
logger.info("event_key", key=value)

# JAMAIS
print(...)
import logging; logging.basicConfig(...)
```

### Config
```python
# TOUJOURS
from config.settings import get_settings
threshold = get_settings().strategy.entry_z_score

# JAMAIS
entry_z = 2.0  # hardcoded
slippage = 2.0  # hardcoded (bug B5-02 connu dans router.py, ne pas reproduire)
```

### Types d'ordres
```python
# INTERNE (execution layer) — seule source de vérité
from execution.base import Order, OrderSide, OrderStatus

# ROUTEUR (interface externe) — toléré mais ne pas étendre
from execution_engine.router import TradeOrder, TradeExecution

# JAMAIS créer un 3ème type Order-like
```

### IBKR
```python
# TOUJOURS rate-limiter avant tout appel API
from execution.ibkr_engine import _ibkr_rate_limiter
_ibkr_rate_limiter.acquire()
self._ib.placeOrder(contract, order)

# Erreurs informatives — NE PAS interrompre
INFORMATIVE_ERRORS = {2104, 2106, 2158}

# Erreurs données historiques — interrompre + cancelHistoricalData
HISTORICAL_DATA_ERRORS = {162, 200, 354}
```

---

## Obligations post-modification

1. **Tout nouveau fichier** modifiant `execution/` → vérifier `tests/execution/`
2. **Tout nouveau paramètre** de config → l'ajouter dans `config/dev.yaml`, `prod.yaml`, `test.yaml`
3. **Toute nouvelle dépendance** → `requirements.txt` ET `pyproject.toml`
4. **Toute modification `risk_engine/kill_switch.py`** → adapter `risk/facade.py` (B2-02)
5. **Après modification** de `models/cointegration_fast.pyx` → recompiler Cython :
   ```powershell
   venv\Scripts\python.exe setup.py build_ext --inplace
   ```
6. **Validation finale** :
   ```powershell
   venv\Scripts\python.exe -m pytest tests/ -q
   # Résultat attendu : 2659 passed, 0 failed, 0 skipped
   ```

---

## Interdictions absolues

| Interdit | Alternative |
|----------|-------------|
| `EDGECORE_ENV=production` | `EDGECORE_ENV=prod` |
| `datetime.utcnow()` | `datetime.now(timezone.utc)` |
| `print(...)` | `logger.info(...)` |
| Hardcoder `entry_z_score`, `max_drawdown_pct`, `slippage_bps` | `get_settings().strategy.*` |
| `from research.* import` dans un module de production | Copier la logique dans `pair_selection/` |
| `@pytest.mark.skip` sans raison tracée | Corriger le test ou créer un issue |
| Créer `run_backtest_v49_*.py` dans `scripts/` | Utiliser `scripts/run_backtest.py` |
| Modifier les risk tiers T1/T2/T3 sans tester `_assert_risk_tier_coherence()` | Tester via `get_settings()._assert_risk_tier_coherence()` |
| `from backtester import ...` (pas de `__init__.py`) | `from backtester.runner import BacktestEngine` |

---

## Fichiers à ne pas toucher sans compréhension complète

- `risk_engine/kill_switch.py` — dernier rempart, logique de halt global
- `config/settings.py` — singleton, ordre de chargement YAML critique
- `execution/reconciler.py` — logique de divergence aware/naive datetime
- `models/cointegration_fast.pyx` — code Cython compilé, break si mal modifié
- `persistence/audit_trail.py` — crash recovery, perte de données possible
