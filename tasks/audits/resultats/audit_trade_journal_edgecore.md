---
audit: 12
titre: Trade Journal — Traçabilité live & backtest
produit: tasks/audits/resultats/audit_trade_journal_edgecore.md
creé: 2026-03-24
auditeur: GitHub Copilot / Senior Quant Engineer
---

# Audit #12 — Journal de trading EDGECORE

---

## 1. État actuel — Traçabilité live

### 1.1 AuditTrail (`persistence/audit_trail.py`)

L'`AuditTrail` est une classe solide sur le plan de l'infrastructure.
Elle produit des fichiers CSV journaliers (`data/audit/audit_trail_YYYYMMDD.csv`)
avec rotation par taille (50 MB), signature HMAC-SHA256 par ligne, et
`os.fsync()` configurable (`fsync_mode="always"/"never"`).

**Colonnes du CSV (L1–L50 environ) :**
```
timestamp | event_type | symbol_pair | side | quantity |
entry_price | exit_price | pnl | equity_at_event | event_id | _hmac
```
11 colonnes — **aucune colonne de contexte signal**.

**Mécanisme de persistance :**
- Append atomique via `os.O_APPEND | os.O_CREAT | os.O_WRONLY` (`persistence/audit_trail.py` L~180)
- `os.fsync()` après chaque ligne en mode `"always"` (`persistence/audit_trail.py` L~195)
- Crash recovery : `AuditTrail.recover_state()` reconstruit les positions
  depuis les événements ENTRY/EXIT avec vérification HMAC (`persistence/audit_trail.py` L~280–360)
- **Non atomique pour la création d'en-tête** : `_ensure_headers()` utilise
  `open()` ordinaire sans `.tmp → os.replace` (race condition sur boot multiple)

**Fichiers observés (`data/audit/`) :**
- 24 fichiers `audit_trail_YYYYMMDD.csv`
- 24 fichiers `equity_snapshots_YYYYMMDD.csv`
- 1 fichier `symbol_scores.csv` (schéma inconnu — non lié aux trades)

### 1.2 Connexion au chemin de trading live (`live_trading/runner.py`)

**CRITIQUE — L'AuditTrail n'est jamais appelée lors d'un trade live.**

| Emplacement | Usage de `_audit_trail` |
|---|---|
| `LiveTradingRunner.__init__` (L129) | Initialisation uniquement |
| `_run_startup_reconciliation()` (L348–360) | `recover_state()` crash recovery |
| `_step_execute_signals()` (L800–825) | ❌ Absent — uniquement `logger.info("live_trading_order_submitted")` |
| `_step_process_stops()` (L608–717) | ❌ Absent — uniquement `logger.info("live_trading_stop_exit")` |
| `_process_fill_confirmations()` (L500–540) | ❌ Absent — état `"pending_close"` mis à jour mais non persisté |

Résultat : les événements de trading live sont émis via `structlog` (fichiers
de logs texte rotatifs) mais **ne sont jamais écrits dans le CSV auditable
`data/audit/audit_trail_YYYYMMDD.csv`**.

### 1.3 BrokerReconciler (`execution/reconciler.py`)

**Ce qui existe :**
- `reconcile_equity(broker_equity)` → `(bool, diff_pct)`
- `reconcile_positions(broker_positions)` → `(bool, inconsistencies_list)`
- `full_reconciliation()` → `ReconciliationReport` (equity_match, positions_match, orders_match, divergences)
- `ReconciliationDivergence` : enregistre `broker_value`, `internal_value`, `severity`

**Câblage dans `live_trading/runner.py` :**
- Démarrage : `_run_startup_reconciliation()` appelle `full_reconciliation()`,
  halte si CRITICAL (`live_trading/runner.py` L348–413)
- Périodique : `_maybe_reconcile()` toutes les 5 minutes (`timedelta(minutes=5)`) (`live_trading/runner.py` L~430)
- **Bug identifié** : dans `_maybe_reconcile()`, `self._reconciler.internal_equity`
  est réinitialisé à `self.config.initial_capital` (capital initial figé)
  plutôt qu'à l'equity courante trackée — drift de réconciliation croissant
  avec le temps (live_trading/runner.py L~445)

### 1.4 `monitoring/events.py` — TradingEvent

```python
@dataclass
class TradingEvent:
    event_type: EventType
    timestamp: datetime
    symbol_pair: str
    position_size: float
    entry_price: float | None = None
    exit_price: float | None = None
    z_score: float | None = None   # ← présent dans le struct
    pnl: float | None = None
    reason: str | None = None
    # MANQUANTS : hedge_ratio, half_life, momentum_score,
    #             bid_ask_spread, slippage_actual, risk_tier
```

Le champ `z_score` est déclaré dans le struct mais **n'est pas mappé
aux colonnes du CSV** dans `AuditTrail._ensure_headers()`.

---

## 2. État actuel — Traçabilité backtest

### 2.1 BacktestMetrics (`backtests/metrics.py` L1–200)

```python
@dataclass
class BacktestMetrics:
    start_date: str
    end_date: str
    total_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    total_trades: int
    avg_trade_duration: float | None    # ← TOUJOURS None (jamais calculé)
    calmar_ratio: float
    sortino_ratio: float
    var_95: float
    cvar_95: float
    initial_capital: float
    final_capital: float
    realized_pnl: float
    note: str | None
    daily_returns: list[float]
    num_symbols: int
```

19 champs — **aucun champ de contexte par trade** (slippage, spread, timestamps,
exit_reason, hedge_ratio).

**`avg_trade_duration` est systématiquement `None`** : le champ existe
dans le dataclass mais n'est jamais calculé dans `BacktestMetrics.from_returns()`
(`backtests/metrics.py` L~120–180). C'est une fonctionnalité déclarée non implémentée.

### 2.2 StrategyBacktestSimulator (`backtests/strategy_simulator.py`)

- Slippage modélisé via Almgren-Chriss (`slippage_model.compute()` appelé ~L882)
  mais le résultat **n'est écrit nulle part** (ni metrics, ni log structuré, ni CSV)
- `time_stop.should_exit()` retourne `ts_reason` (~L1104) mais la raison de
  sortie **n'est pas capturée** dans les trades ni dans les métriques
- Liste interne `trades_pnl` : liste de P&L scalaires par trade complète, mais
  sans contexte (pas de timestamp, pas de z_score, pas de hedge_ratio)
- Aucun appel à `AuditTrail.log_trade_event()` dans le simulateur

### 2.3 Réconciliation live/backtest — impossibilité structurelle

| Dimension | Backtest | Live |
|---|---|---|
| Granularité | P&L agrégé (daily_returns) | Événements par trade (si câblé) |
| Slippage | Modélisé (Almgren-Chriss) non persisté | Absent (IBKR fill price non comparé) |
| Exit reason | Non persisté | Non persisté |
| Signal context | Non persisté | Non persisté |
| Format | `BacktestMetrics` dataclass | CSV 11 colonnes |

**Aucun pont ne peut être établi entre `BacktestMetrics` et `AuditTrail` CSV
au niveau trade individuel.** La réconciliation live/backtest est actuellement
impossible de façon programmatique.

---

## 3. Données manquantes — Gaps critiques

### 🔴 P0 — Bloquants opérationnels

**P0-01 : `AuditTrail.log_trade_event()` jamais appelée en trading live**

`live_trading/runner.py` `_step_execute_signals()` (L~811) émet uniquement
`logger.info("live_trading_order_submitted")`. Aucun appel à `self._audit_trail.log_trade_event()`.
Même situation pour les exits via `_step_process_stops()` (L~679).

Impact : en cas d'incident live ou de litige IBKR, **aucune trace structurée
horodatée et signée ne prouve l'historique des décisions de trading**.

**P0-02 : Contexte signal absent des colonnes AuditTrail**

Les champs suivants ne sont **ni dans TradingEvent ni dans le CSV** :

| Champ | Disponibilité dans le code | Manquant dans CSV |
|---|---|---|
| `z_score` | `signal.z_score` dans `_step_execute_signals` | ✅ dans TradingEvent mais non mappé |
| `hedge_ratio` | `pos_info.get("entry_z")` dans runner | ❌ absent partout |
| `half_life` | `pos_info.get("half_life")` dans runner | ❌ absent CSV |
| `momentum_score` | calculé dans `signal_engine/` | ❌ absent CSV |
| `exit_reason` | `ts_reason` / `time_reason` dans runner | ❌ absent CSV |
| `risk_tier_triggered` | non exposé | ❌ absent CSV |

**P0-03 : Slippage réel jamais mesuré ni persisté**

En backtest : `slippage_model.compute()` (~L882 `strategy_simulator.py`) retourne
un coût Almgren-Chriss mais ce coût n'est **ni stocké** dans `BacktestMetrics`
ni dans les trades individuels.

En live : IBKR remonte un `fill_price` via `_process_fill_confirmations()` mais
la différence `fill_price - request_price` n'est **jamais calculée ni loggée**.

Impact métier : impossible de quantifier le coût réel d'implémentation.
Le P&L live vs backtest ne peut pas être réconcilié.

---

### 🟠 P1 — Important

**P1-01 : `avg_trade_duration` toujours `None` dans BacktestMetrics**

`backtests/metrics.py` L~130 : `avg_trade_duration: float | None = None`
Non calculé dans `from_returns()`. Impossible de mesurer le timing de
rotation du portefeuille ou de comparer avec la demi-vie théorique Kalman.

**P1-02 : Bug réconciliation equity — reset à `initial_capital`**

`live_trading/runner.py` `_maybe_reconcile()` L~445 :
```python
self._reconciler.internal_equity = self.config.initial_capital
```
Doit être l'equity courante trackée (equity mark-to-market), pas le capital
initial. Ce bug crée un écart de réconciliation croissant dès le premier trade
profitable.

**P1-03 : Timestamps d'entrée/sortie absents des métriques**

`BacktestMetrics` ne stocke que `start_date` / `end_date` de la simulation.
Les timestamps UTC par trade (entry_ts, exit_ts) ne sont capturés ni en
backtest ni en live.

**P1-04 : Signal de `_audit_trail` initialisé mais jamais exploité en live**

`AuditTrail.recover_state()` est appelé au boot (`live_trading/runner.py` L351)
pour reconstruire les positions après crash. Mais comme `log_trade_event()`
n'est jamais appelée par le chemin live (P0-01), le fichier de recovery est
**identique à sa création** — la recovery est une illusion si le process
meurt après avoir tradé.

---

### 🟡 P2 — Secondaire

**P2-01 : `equity_snapshots_YYYYMMDD.csv` — positions_list non structuré**

La colonne `positions_list` est un `str(dict)` Python brut, non parseable
de façon fiable (dépend du `repr` Python, pas JSON).

**P2-02 : `_ensure_headers()` non atomique**

`persistence/audit_trail.py` L~95 : `open(self._file_path, "w")` ordinaire.
Sur un boot simultané de deux processes (PAPER + monitoring), race condition
possible sur la création des en-têtes.

**P2-03 : `symbol_scores.csv` — schéma inconnu**

`data/audit/symbol_scores.csv` n'est référencé dans aucun module identifié.
Son producteur et son consommateur sont inconnus.

**P2-04 : HMAC optionnel sans blocage en prod**

`persistence/audit_trail.py` : si `AUDIT_HMAC_KEY` est absent,
l'audit trail écrit des lignes non signées. En `prod`, cela devrait
déclencher une erreur bloquante, pas un warning.

---

## 4. Risques

### 4.1 Non-auditabilité en cas d'incident live

**Scénario** : une position est ouverte par le live runner, le kill-switch se
déclenche (Tier 2 — perte 15%), la position est fermée en urgence.

**Résultat actuel** : `structlog` écrit dans un fichier de log texte rotatif.
L'`AuditTrail` ne contient aucune trace de ce trade. Les `equity_snapshots`
montrent une baisse mais sans lien avec une raison.

**Risque** : litige IBKR sur le motif de fermeture d'ordre, audit interne
impossible, absence de preuve de la chronologie décisionnelle.

### 4.2 Corruption de données en crash

**Scénario** : le process meurt pendant l'écriture d'une ligne CSV
(entre le `write()` et le `fsync()`).

**Risque** : ligne CSV tronquée → HMAC invalide → `recover_state()` échoue
sur cette ligne → positions précédentes non reconstruites. Mitigation partielle
par `os.O_APPEND` (le système d'exploitation garantit l'atomicité de chaque
`write()` sous Linux pour les tailles < PIPE_BUF ~4KB), mais non garanti
sur Windows (cible de dev).

### 4.3 Drift silencieux de réconciliation

**Scénario** : le bug P1-02 (`internal_equity` réinitialisé à
`initial_capital` à chaque réconciliation) masque progressivement les
écarts entre l'état interne et IBKR. Une divergence de 2% (~$2k sur
$100k) ne déclencherait pas d'alerte car le comparateur utilise toujours
`initial_capital` comme référence interne.

### 4.4 Faux sentiment de recovery

Le crash recovery (`recover_state()` au boot) est fonctionnel **uniquement
si** `log_trade_event()` a été appelée pendant le run précédent. Comme
décrit en P0-01, cette condition n'est jamais remplie en trading live.
**Le crash recovery est une fonctionnalité inopérante.**

### 4.5 Slippage réel inconnu → drift P&L live/backtest non détectable

Sans mesure du slippage réel (fill_price vs mid), il est impossible de
distinguer entre : (a) une stratégie qui dégrade ses performances avec le
temps, (b) un coût d'implémentation supérieur aux hypothèses du backtest.
Ce risque est amplifié par la liquidité typique des ETFs stat-arb.

---

## 5. Recommandations

### R1 — Câbler `log_trade_event()` dans le chemin live [PRIORITÉ P0 — Effort S]

**Fichier** : `live_trading/runner.py`

**Point d'ancrage** : `_step_execute_signals()` après `self._router.submit_order()`
(L~811), et `_step_process_stops()` après la soumission de l'ordre de clôture (L~717).

```python
# Exemple d'ancrage dans _step_execute_signals() (après submit_order)
from monitoring.events import TradingEvent, EventType

event = TradingEvent(
    event_type=EventType.TRADE_ENTRY,
    timestamp=datetime.now(timezone.utc),
    symbol_pair=sig.pair_key,
    position_size=sized_order.quantity,
    entry_price=current_price,
    z_score=sig.z_score,
    reason=None,
)
self._audit_trail.log_trade_event(event)
```

**Contraintes** : utiliser `datetime.now(timezone.utc)` — jamais `datetime.utcnow()`.

---

### R2 — Étendre les colonnes AuditTrail avec le contexte signal [PRIORITÉ P0 — Effort M]

**Fichier** : `persistence/audit_trail.py` + `monitoring/events.py`

**Nouvelles colonnes à ajouter** :
```
z_score | hedge_ratio | half_life | momentum_score |
slippage_actual | bid_ask_spread | exit_reason | risk_tier
```

**Point d'ancrage** : `_ensure_headers()` dans `persistence/audit_trail.py`
et `_row_from_event()` qui construit la ligne CSV.

**Contrainte** : les fichiers existants (`data/audit/audit_trail_*.csv`) ont
11 colonnes — la migration doit gérer la rétrocompatibilité lors de
`recover_state()` (padding des nouvelles colonnes avec `None`).

---

### R3 — Corriger le bug de réconciliation equity [PRIORITÉ P1 — Effort XS]

**Fichier** : `live_trading/runner.py` `_maybe_reconcile()` (~L445)

```python
# AVANT (bug)
self._reconciler.internal_equity = self.config.initial_capital

# APRÈS (correct)
self._reconciler.internal_equity = self._metrics.equity  # equity courante
```

---

### R4 — Mesurer et persister le slippage réel [PRIORITÉ P1 — Effort M]

**Fichier** : `live_trading/runner.py` `_process_fill_confirmations()`

Après confirmation du fill IBKR :
```python
slippage_bps = (fill_price - requested_price) / requested_price * 10_000
logger.info("trade_slippage", pair=pair_key, slippage_bps=round(slippage_bps, 2))
# Puis écrire dans l'audit trail en UPDATE de la ligne ENTRY
```

En backtest, stocker `slippage_cost` dans une liste parallèle à
`trades_pnl` et l'agréger dans `BacktestMetrics`.

---

### R5 — Calculer `avg_trade_duration` dans BacktestMetrics [PRIORITÉ P1 — Effort XS]

**Fichier** : `backtests/strategy_simulator.py` + `backtests/metrics.py`

Stocker `entry_bar` à l'ouverture et calculer `exit_bar - entry_bar`
à la clôture. Agréger dans `BacktestMetrics.avg_trade_duration`.

---

### R6 — Rendre la création d'en-tête atomique [PRIORITÉ P2 — Effort XS]

**Fichier** : `persistence/audit_trail.py` `_ensure_headers()` (~L95)

```python
# Pattern atomique (.tmp → os.replace)
tmp_path = self._file_path.with_suffix(".tmp")
with open(tmp_path, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(self.COLUMNS)
os.replace(tmp_path, self._file_path)
```

---

### R7 — Bloquer l'absence de `AUDIT_HMAC_KEY` en prod [PRIORITÉ P2 — Effort XS]

**Fichier** : `persistence/audit_trail.py`

```python
from config.settings import get_settings
if get_settings().env == "prod" and not os.environ.get("AUDIT_HMAC_KEY"):
    raise RuntimeError("AUDIT_HMAC_KEY obligatoire en production")
```

---

### R8 — Structurer `positions_list` en JSON [PRIORITÉ P2 — Effort XS]

**Fichier** : producteur des `equity_snapshots_YYYYMMDD.csv` (à identifier)

Remplacer `str(positions_dict)` par `json.dumps(positions_dict)` pour
permettre le parsing programmatique.

---

## 6. Synthèse

### Score de maturité du journal de trading

| Dimension | Score | Commentaire |
|---|---|---|
| Infrastructure AuditTrail | 7/10 | HMAC, fsync, rotation — solide |
| Câblage live (trades réels) | 0/10 | AuditTrail jamais appelée pendant le trading |
| Contexte signal capturé | 1/10 | z_score dans TradingEvent, non mappé CSV |
| Slippage mesuré | 0/10 | Calculé en backtest, non persisté nulle part |
| Crash recovery opérationnel | 1/10 | Fonctionnel seulement si câblage live (R1) fait |
| Réconciliation live/backtest | 0/10 | Aucun pont possible — schémas incompatibles |
| Timestamps par trade | 2/10 | Présents dans structlog, absents du CSV audit |

### **Score global : 4/10**

### Verdict : 🔴 NO-GO pour passage en trading live

**Justification** :

Le système EDGECORE dispose d'une infrastructure de persistance bien
conçue (`AuditTrail` avec HMAC, fsync, rotation) mais cette
infrastructure est **entièrement déconnectée du chemin d'exécution
live**. Aucun trade live n'est enregistré dans le CSV auditable.

En l'état, il est **impossible** de :
- Reconstituer l'historique des décisions post-incident (P0-01)
- Mesurer le coût d'implémentation réel (P0-03)  
- Réconcilier les résultats live avec les prévisions backtest (P1 structurel)
- Effectuer un crash recovery fiable suite à un arrêt non planifié (P0-01 conséquence)

**Conditions minimales avant passage en live :**
1. R1 — Câbler `log_trade_event()` dans `_step_execute_signals()` et `_step_process_stops()`
2. R2 — Ajouter au minimum 4 colonnes : `z_score`, `exit_reason`, `slippage_actual`, `risk_tier`
3. R3 — Corriger le bug de réconciliation equity

**Effort estimé minimal (R1 + R2 + R3) : ~1 jour de développement.**

---

*Audit réalisé sur branche `lfs-migration-preview` commit `ee34f5c`.*
*Fichiers principaux analysés : `persistence/audit_trail.py`, `live_trading/runner.py` (L129, L348–360, L500–900), `backtests/strategy_simulator.py` (L820–1110), `backtests/metrics.py`, `execution/reconciler.py`, `monitoring/events.py`.*
