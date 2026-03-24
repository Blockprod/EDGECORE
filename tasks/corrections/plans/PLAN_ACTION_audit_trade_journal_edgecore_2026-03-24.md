# PLAN D'ACTION — EDGECORE — 2026-03-24
Sources : `tasks/audits/resultats/audit_trade_journal_edgecore.md`
Total : 🔴 4 · 🟠 2 · 🟡 3 · Effort estimé : 1.75 jours

---

## PHASE 1 — CRITIQUES 🔴

---

### [C-01] Étendre les colonnes CSV AuditTrail avec le contexte signal

**Fichier** : `persistence/audit_trail.py:129` + `monitoring/events.py:~L5`
**Problème** :
- `_ensure_headers()` écrit 11 colonnes sans contexte signal.
- `TradingEvent` (monitoring/events.py) manque : `hedge_ratio`, `half_life`,
  `momentum_score`, `bid_ask_spread`, `slippage_actual`, `risk_tier`.
- `z_score` est déclaré dans `TradingEvent` mais absent de la liste des colonnes CSV.

**Correction** :
1. Dans `monitoring/events.py` — ajouter au dataclass `TradingEvent` :
   ```python
   hedge_ratio: float | None = None
   half_life: float | None = None
   momentum_score: float | None = None
   slippage_actual: float | None = None
   bid_ask_spread: float | None = None
   risk_tier: str | None = None
   ```
2. Dans `persistence/audit_trail.py` `_ensure_headers()` (L~138) — ajouter
   dans `writer.writerow(...)` les colonnes :
   ```
   "z_score", "hedge_ratio", "half_life", "momentum_score",
   "slippage_actual", "bid_ask_spread", "exit_reason", "risk_tier"
   ```
3. Dans `log_trade_event()` (L~175) — ajouter ces valeurs dans
   `_atomic_append()` (après `event_id`, avant `_hmac`).
4. Dans `recover_state()` — gérer la rétrocompatibilité : padder les
   colonnes manquantes à `None` si le CSV existant a 11 colonnes.

**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/ -x -q -k "audit_trail or trade_event"
# Attendu : tests audit_trail verts, 0 erreur de colonnes
venv\Scripts\python.exe -c "from persistence.audit_trail import AuditTrail; print('OK')"
```
**Dépend de** : Aucune
**Statut** : ⏳

---

### [C-02] Câbler `log_trade_event()` à l'entrée live (`_step_execute_signals`)

**Fichier** : `live_trading/runner.py:~L811`
**Problème** :
Après `self._router.submit_order(sized_order)` (L~810), seul un `logger.info`
est émis. Aucune écriture dans `self._audit_trail`. L'AuditTrail est muette
pour tous les ordres d'entrée live.

**Correction** :
Après la ligne `logger.info("live_trading_order_submitted", ...)`, ajouter :
```python
if self._audit_trail is not None:
    from monitoring.events import TradingEvent, EventType
    from datetime import timezone
    _ev = TradingEvent(
        event_type=EventType.TRADE_ENTRY,
        timestamp=datetime.now(timezone.utc),
        symbol_pair=sig.pair_key,
        position_size=getattr(sized_order, "quantity", 0.0),
        entry_price=getattr(sized_order, "limit_price", None),
        z_score=getattr(sig, "z_score", None),
        hedge_ratio=getattr(sig, "hedge_ratio", None),
        half_life=getattr(sig, "half_life", None),
        momentum_score=getattr(sig, "momentum_score", None),
        risk_tier=None,
    )
    try:
        self._audit_trail.log_trade_event(_ev, current_equity=_balance)
    except Exception as _ae:
        logger.error("audit_trail_entry_failed", pair=sig.pair_key, error=str(_ae)[:200])
```

**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/ -x -q -k "live_trading or audit"
# Attendu : 0 erreur
```
**Dépend de** : C-01 (colonnes CSV étendues)
**Statut** : ⏳

---

### [C-03] Câbler `log_trade_event()` aux sorties live (`_step_process_stops`)

**Fichier** : `live_trading/runner.py:~L679–717`
**Problème** :
Les sorties déclenchées par les stops (trailing, time, correlation) soumettent
un ordre via `self._router.submit_order(close_order)` mais n'écrivent rien dans
l'`AuditTrail`. Le `reason` existant (`ts_reason`, `time_reason`) est disponible
dans la variable locale mais jamais persisté.

**Correction** :
Après `self._router.submit_order(close_order)` dans le bloc `exit_signals_from_stops`
(L~690–710), ajouter :
```python
if self._audit_trail is not None:
    from monitoring.events import TradingEvent, EventType
    from datetime import timezone
    _pos = self._positions.get(pair_key, {})
    _ev_exit = TradingEvent(
        event_type=EventType.TRADE_EXIT,
        timestamp=datetime.now(timezone.utc),
        symbol_pair=pair_key,
        position_size=abs(_pos.get("quantity", 0.0)),
        exit_price=None,  # fill price inconnu avant confirmation
        pnl=None,          # P&L réalisé inconnu avant confirmation
        reason=reason,
        risk_tier=None,
    )
    try:
        self._audit_trail.log_trade_event(_ev_exit, current_equity=_balance_at_exit)
    except Exception as _ae:
        logger.error("audit_trail_exit_failed", pair=pair_key, error=str(_ae)[:200])
```
Note : `_balance_at_exit` = `self._metrics.equity` (equity courante disponible).

**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/ -x -q -k "live_trading or audit"
# Attendu : 0 erreur
```
**Dépend de** : C-01, C-02
**Statut** : ⏳

---

### [C-04] Mesurer et persister le slippage réel dans `_process_fill_confirmations`

**Fichier** : `live_trading/runner.py:~L500–540`
**Problème** :
Quand IBKR confirme un fill, `_process_fill_confirmations()` met à jour le
statut de la position mais ne calcule jamais le slippage réel
(`fill_price - requested_price`). En backtest, `slippage_model.compute()`
(`backtests/strategy_simulator.py` L~882) calcule un coût Almgren-Chriss
mais ne le stocke nulle part.

**Correction — Live** :
Dans `_process_fill_confirmations()`, après mise à jour du statut `"filled"`,
ajouter :
```python
requested_price = pos.get("requested_price")
fill_price = getattr(order_status, "fill_price", None)
if requested_price and fill_price:
    slippage_bps = (fill_price - requested_price) / requested_price * 10_000
    logger.info(
        "trade_slippage_measured",
        pair=pair_key,
        requested=requested_price,
        fill=fill_price,
        slippage_bps=round(slippage_bps, 2),
    )
    # Mettre à jour l'événement d'audit avec slippage_actual
    # (mise à jour de la ligne ENTRY via un événement UPDATE ou
    #  insertion d'un événement FILL séparé)
```

**Correction — Backtest** :
Dans `backtests/strategy_simulator.py` L~882, capturer la valeur retournée :
```python
_slippage_cost = self.slippage_model.compute(...)
_slippage_costs.append(_slippage_cost)   # liste parallèle à trades_pnl
```
Agréger dans `BacktestMetrics` : `total_slippage_cost = sum(_slippage_costs)`.

**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/ -x -q -k "slippage or backtest_metrics"
# Attendu : 0 erreur
```
**Dépend de** : C-01 (champ `slippage_actual` dans TradingEvent)
**Statut** : ⏳

---

## PHASE 2 — MAJEURES 🟠

---

### [C-05] Corriger le bug de réconciliation equity dans `_maybe_reconcile`

**Fichier** : `live_trading/runner.py:421`
**Problème** :
```python
# ACTUEL — bug
self._reconciler.internal_equity = self.config.initial_capital  # update if tracking
```
Le commentaire "update if tracking" est trompeur : la valeur est toujours le
capital initial, jamais l'equity mark-to-market courante. Le reconciler compare
donc systématiquement IBKR vs le capital de départ au lieu d'une valeur courante.

**Correction** :
```python
# CORRECT
self._reconciler.internal_equity = (
    self._metrics.equity
    if self._metrics.equity > 0
    else self.config.initial_capital
)
```

**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/ -x -q -k "reconcil"
# Attendu : tests reconciler verts
```
**Dépend de** : Aucune
**Statut** : ⏳

---

### [C-06] Calculer `avg_trade_duration` dans BacktestMetrics

**Fichier** : `backtests/strategy_simulator.py:~L882` + `backtests/metrics.py:~L130`
**Problème** :
`BacktestMetrics.avg_trade_duration` est déclaré `float | None = None` et n'est
jamais calculé. Le simulateur n'enregistre pas les bar indices d'entrée/sortie
par trade.

**Correction — `strategy_simulator.py`** :
1. Ajouter `_trade_durations: list[int] = []` parallèle à `trades_pnl`
2. À l'ouverture d'une position, enregistrer `_pos["entry_bar"] = bar_idx`
3. À la clôture, ajouter `_trade_durations.append(bar_idx - pos["entry_bar"])`
4. Passer `avg_trade_duration` dans `BacktestMetrics` : `float(np.mean(_trade_durations)) if _trade_durations else None`

**Correction — `backtests/metrics.py`** :
Accepter le paramètre dans `from_returns()` ou le constructeur et l'assigner.

**Validation** :
```powershell
venv\Scripts\python.exe -m pytest tests/ -x -q -k "backtest"
# Attendu : avg_trade_duration != None dans BacktestMetrics si au moins 1 trade fermé
```
**Dépend de** : Aucune
**Statut** : ⏳

---

## PHASE 3 — MINEURES 🟡

---

### [C-07] Rendre la création d'en-têtes CSV atomique dans `_ensure_headers`

**Fichier** : `persistence/audit_trail.py:129`
**Problème** :
`_ensure_headers()` utilise `open(self.trail_file, "w", ...)` simple.
Sur un boot simultané de deux instances (PAPER + monitoring), race condition
possible → CSV avec double en-tête ou en-tête corrompu.

**Correction** :
```python
def _ensure_headers(self) -> None:
    for filepath, header_row in [
        (self.trail_file, ["timestamp", "event_type", ...]),
        (self.equity_snapshot_file, ["timestamp", "equity", ...]),
    ]:
        if not filepath.exists():
            tmp = filepath.with_suffix(".tmp")
            with open(tmp, "w", newline="") as f:
                csv.writer(f).writerow(header_row)
            os.replace(tmp, filepath)   # atomique sous Linux et Windows NTFS
```

**Validation** :
```powershell
venv\Scripts\python.exe -c "from persistence.audit_trail import AuditTrail; print('OK')"
# Attendu : OK
```
**Dépend de** : C-01 (liste des nouvelles colonnes)
**Statut** : ⏳

---

### [C-08] Structurer `positions_list` en JSON dans `equity_snapshots`

**Fichier** : producteur de `equity_snapshots_YYYYMMDD.csv` (chercher `log_equity_snapshot`)
**Problème** :
La colonne `positions_list` est sérialisée via `str(dict)` Python (repr arbitraire),
non parseable de façon fiable.

**Correction** :
Remplacer `str(positions_dict)` par `json.dumps(positions_dict, default=str)`
dans tous les appels à `log_equity_snapshot()`. Ajouter `import json` si absent.

**Validation** :
```powershell
venv\Scripts\python.exe -c "import json; json.loads('{\"a\": 1}'); print('OK')"
# Attendu : OK
venv\Scripts\python.exe -m pytest tests/ -x -q -k "equity_snapshot"
```
**Dépend de** : Aucune
**Statut** : ⏳

---

### [C-09] Bloquer l'absence de `AUDIT_HMAC_KEY` en environnement prod

**Fichier** : `persistence/audit_trail.py:~L60–80` (bloc `__init__`)
**Problème** :
Si `AUDIT_HMAC_KEY` est absent, l'AuditTrail écrit des lignes non signées
et émet un simple warning. En production, c'est un risque d'intégrité silencieux.

**Correction** :
```python
import os
from config.settings import get_settings

_hmac_key = os.environ.get("AUDIT_HMAC_KEY")
if not _hmac_key and get_settings().env == "prod":
    raise RuntimeError(
        "AUDIT_HMAC_KEY est obligatoire en production. "
        "Définir la variable d'environnement avant de démarrer."
    )
```

**Validation** :
```powershell
$env:EDGECORE_ENV = "prod"
venv\Scripts\python.exe -c "
from persistence.audit_trail import AuditTrail
try:
    AuditTrail()
    print('FAIL — devrait lever RuntimeError')
except RuntimeError as e:
    print('OK', e)
"
Remove-Item Env:EDGECORE_ENV
```
**Dépend de** : Aucune
**Statut** : ⏳

---

## SÉQUENCE D'EXÉCUTION

```
C-01  (colonnes CSV + TradingEvent)         ← base, aucune dépendance
  └─ C-02  (câblage entrée live)            ← dépend C-01
       └─ C-03  (câblage sortie live)       ← dépend C-01 + C-02
C-04  (slippage réel)                       ← dépend C-01, parallélisable avec C-02/C-03
C-05  (bug equity réconciliation)           ← indépendant, quick win
C-06  (avg_trade_duration)                  ← indépendant
C-07  (_ensure_headers atomique)            ← dépend C-01 (colonnes finales)
C-08  (positions_list JSON)                 ← indépendant
C-09  (HMAC prod guard)                     ← indépendant
```

**Ordre recommandé d'exécution :**
`C-05 → C-01 → C-07 → C-02 → C-03 → C-04 → C-06 → C-08 → C-09`

Rationale : C-05 est un one-liner sans dépendance (impact immédiat sur la
réconciliation), puis C-01 ouvre la voie à tout le câblage qui suit.

---

## CRITÈRES PASSAGE EN PRODUCTION

- [ ] Zéro 🔴 ouvert (C-01, C-02, C-03, C-04 complétés)
- [ ] `pytest tests/` : 100% pass (2787+)
- [ ] `mypy risk/ risk_engine/ execution/ persistence/ --ignore-missing-imports` : exit 0
- [ ] `ruff check .` : 0 erreurs
- [ ] `data/audit/audit_trail_*.csv` contient des lignes lors d'un run PAPER
- [ ] Les lignes CSV incluent les colonnes `z_score`, `exit_reason`, `slippage_actual`
- [ ] `_maybe_reconcile()` ne reset plus à `initial_capital` (vérifié en log)
- [ ] `BacktestMetrics.avg_trade_duration` n'est plus `None` sur une run non vide
- [ ] `AUDIT_HMAC_KEY` absent → `RuntimeError` au boot en mode `prod`
- [ ] Risk tiers cohérents (`_assert_risk_tier_coherence OK`)
- [ ] `EDGECORE_ENV=prod` dans Dockerfile (pas "production")
- [ ] Paper trading validé avant live

---

## TABLEAU DE SUIVI

| ID | Titre | Sévérité | Fichier principal | Effort | Statut | Date |
|---|---|:---:|---|:---:|---|---|
| C-01 | Colonnes CSV + TradingEvent signal context | 🔴 | `persistence/audit_trail.py:129` | M | ⏳ | |
| C-02 | Câbler `log_trade_event()` entrée live | 🔴 | `live_trading/runner.py:~811` | S | ⏳ | |
| C-03 | Câbler `log_trade_event()` sortie live | 🔴 | `live_trading/runner.py:~679` | S | ⏳ | |
| C-04 | Mesurer slippage réel (live + backtest) | 🔴 | `live_trading/runner.py:~500` | S | ⏳ | |
| C-05 | Bug equity réconciliation — reset initial_capital | 🟠 | `live_trading/runner.py:421` | XS | ⏳ | |
| C-06 | Calculer `avg_trade_duration` BacktestMetrics | 🟠 | `backtests/strategy_simulator.py:~882` | S | ⏳ | |
| C-07 | Écriture atomique `_ensure_headers` | 🟡 | `persistence/audit_trail.py:129` | XS | ⏳ | |
| C-08 | `positions_list` → JSON | 🟡 | producteur `log_equity_snapshot` | XS | ⏳ | |
| C-09 | HMAC guard obligatoire en prod | 🟡 | `persistence/audit_trail.py:~60` | XS | ⏳ | |
