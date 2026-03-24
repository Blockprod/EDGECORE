# PLAN D'ACTION — EDGECORE — 2026-03-22
**Création :** 2026-03-22 à 12:45  
Sources : `tasks/audits/audit_strategic_edgecore.md`  
Total : 🔴 1 · 🟠 2 · 🟡 6 · Effort estimé : **12 jours**

---

## PHASE 1 — CRITIQUES 🔴

### [C-01] Éliminer le biais de survie — univers point-in-time ✅
Fichier : `universe/manager.py` (DEFAULT_SECTOR_MAP)  
Problème : `DEFAULT_SECTOR_MAP` est un snapshot statique des ~100 titres **actuellement cotés**. Tout backtest sur 5-10 ans exclut les entreprises délistées (faillites, OPA, radiations), surestimant le Sharpe de **+15-25%**.  
Correction :
1. Créer `data/universe_history.csv` (colonnes : `symbol, sector, date_in, date_out`) — ou wrapper autour d'un fichier CSV CRSP/Compustat minimal.
2. Modifier `UniverseManager.get_universe(as_of_date: datetime)` pour retourner uniquement les symboles actifs à `as_of_date` (filtre `date_in ≤ as_of_date < date_out`).
3. Dans `backtests/strategy_simulator.py`, passer `as_of_date=prices_df.index[bar_idx]` à `get_universe()` lors de chaque redécouverte de paires.
4. `DEFAULT_SECTOR_MAP` devient un fallback live (mode temps réel uniquement).

Validation :
```powershell
venv\Scripts\python.exe -m pytest tests/ -x -q
# Attendu : 2681+ pass, 0 failed
# Vérifier que les tests d'UniverseManager passent avec as_of_date
venv\Scripts\python.exe -m pytest tests/ -k "universe" -v
```
Dépend de : Aucune  
Effort : 4 jours  
Statut : ⏳

---

## PHASE 2 — MAJEURES 🟠

### [C-02] Corriger l'ambiguïté execution timing (signal T → fill T+1)
Fichier : `backtests/strategy_simulator.py:343` + `strategies/pair_trading.py:982`  
Problème : `hist_prices = prices_df.iloc[:bar_idx + 1]` inclut la barre courante dont `z_score.iloc[-1]` est le close. Si l'exécution est simulée au même close, c'est un biais de look-ahead caché (signal non connu avant end-of-bar). Surestimation rendement **+5-10%**.  
Correction :
1. Séparer la logique signal (barre T) de la logique fill (barre T+1) :

```python
# Dans _run_bar() du simulateur, lorsqu'un signal est émis à bar_idx :
# — Signal évalué sur hist_prices = prices_df.iloc[:bar_idx + 1]  ← inchangé
# — Prix d'exécution = prices_df.iloc[bar_idx + 1]  ← OPEN ou VWAP barre suivante
```

2. Modifier `_open_position()` et `_close_position()` pour accepter `execution_bar_idx = bar_idx + 1` et utiliser `prices_df.iloc[execution_bar_idx]` pour le prix fill.
3. Gérer le cas `bar_idx == len(prices_df) - 1` (dernière barre — signal ignoré, pas de T+1).
4. Documenter la convention dans le docstring de `StrategyBacktestSimulator`.

Validation :
```powershell
venv\Scripts\python.exe -m pytest tests/ -x -q
# Attendu : 2681+ pass
# Vérifier que le PnL walk-forward final est ~5-10% plus faible (signal de correction réaliste)
venv\Scripts\python.exe -m pytest tests/ -k "simulator or backtest" -v
```
Dépend de : C-01 (pour que les résultats corrigés soient significatifs)  
Effort : 2 jours  
Statut : ⏳

---

### [C-03] Vérifier et câbler le callback kill-switch → annulation ordres IBKR ✅
Fichier : `live_trading/runner.py` + `risk_engine/kill_switch.py` + `execution/ibkr_engine.py`  
Problème : `KillSwitch` déclenche via `on_activate` callback mais le câblage vers `IBKRExecutionEngine.cancel_all_orders()` n'est pas confirmé. Si non câblé, des positions restent ouvertes sans monitoring lors d'un kill → risque de pertes illimitées en live.  
Correction :
1. Dans `LiveTradingRunner._initialize()`, vérifier/ajouter :
```python
self.kill_switch.on_activate = self._on_kill_switch_activated

def _on_kill_switch_activated(self, reason: KillReason) -> None:
    self.logger.critical("kill_switch_activated", reason=reason.value)
    self.execution_engine.cancel_all_open_orders()
    self.execution_engine.close_all_positions_market()  # ou flatten_all()
```
2. Confirmer que `IBKRExecutionEngine` expose `cancel_all_open_orders()` (ou créer la méthode via `reqGlobalCancel()`).
3. Ajouter un test unitaire `tests/test_kill_switch_wiring.py` qui mock le kill-switch et vérifie que `cancel_all_open_orders()` est appelé.

Validation :
```powershell
venv\Scripts\python.exe -m pytest tests/test_kill_switch_wiring.py -v
# Attendu : câblage confirmé, 0 failed
venv\Scripts\python.exe -m pytest tests/ -x -q
# Attendu : 2682+ pass
```
Dépend de : Aucune  
Effort : 1 jour  
Statut : ⏳

---

## PHASE 3 — MINEURES 🟡

### [C-04] Activer le hedge ratio Kalman barre-par-barre dans SpreadModel
Fichier : `models/spread.py:35-45`  
Problème : `SpreadModel` utilise OLS statique + ré-estimation periodique (7 jours). `KalmanHedgeRatio` existe dans `models/kalman_hedge.py` mais n'est pas connecté. Le drift du beta entre deux re-estimations génère un spread artificiellement non-stationnaire → faux signaux, drawdowns amplifiés. Surestimation Sharpe **+5-10%**.  
Correction :
1. Ajouter `use_kalman: bool = False` dans `SpreadModelConfig` (config-driven, lisible depuis `get_settings()`).
2. Dans `SpreadModel.__init__()`, si `use_kalman=True`, instancier `KalmanHedgeRatio` et appeler `update()` à chaque `compute_spread()`.
3. `reestimate_beta_if_needed()` devient un fallback si `use_kalman=False`.
4. Activer via `config/dev.yaml` : `spread.use_kalman: true`.

Validation :
```powershell
venv\Scripts\python.exe -m pytest tests/ -x -q
# Attendu : 2681+ pass
venv\Scripts\python.exe -m pytest tests/ -k "spread or kalman" -v
```
Dépend de : C-08 (les log-prix doivent être en place avant de changer le modèle de spread)  
Effort : 2 jours  
Statut : ⏳

---

### ✅ [C-05] Modéliser le premium HTB dans le coût d'emprunt
Fichier : `backtests/cost_model.py:CostModelConfig`  
Problème : `borrowing_cost_annual_pct = 0.005` (50 pb GC rate) ignore les frais Hard-to-Borrow (1%-20%/an) pour les mid-caps à forte pression de court. PnL surestimé **+1-3%/an** pour les paires impliquant des HTB names.  
Correction :
1. Ajouter `htb_symbols: dict[str, float] = field(default_factory=dict)` dans `CostModelConfig` (ex. `{"GME": 0.15, "AMC": 0.20}`).
2. Dans `_borrowing_cost()`, utiliser `htb_symbols.get(symbol, borrowing_cost_annual_pct)` comme taux.
3. Optionnel (recommandé) : créer `data/htb_rates.csv` (source IBKR Shortable Shares API) et le charger dans `CostModelConfig` au démarrage.
4. Lire depuis `get_settings().costs.htb_symbols` pour respecter la convention config.

Validation :
```powershell
venv\Scripts\python.exe -m pytest tests/ -x -q
# Attendu : 2681+ pass
venv\Scripts\python.exe -m pytest tests/ -k "cost_model" -v
```
Dépend de : Aucune  
Effort : 1 jour  
Statut : ✅ 2026-03-22

---

### ✅ [C-06] Passer l'ADV réel au modèle de coût Almgren-Chriss
Fichier : `backtests/cost_model.py` (paramètre `volume_24h=1e7` par défaut)  
Problème : Le composant impact `η × σ × sqrt(Q/ADV)` utilise $10M d'ADV par défaut pour tous les titres. Pour les mid-caps, le vrai ADV peut être 2-5× inférieur → impact de marché sous-estimé de 40-120%.  
Correction :
1. Dans `DataLoader` ou `LiquidityFilter`, calculer l'ADV 30j par symbole (fenêtre roulante sur `hist_prices`).
2. Passer `adv_by_symbol: dict[str, float]` à `StrategyBacktestSimulator.__init__()`.
3. Dans `_execute_trade()`, récupérer `volume_24h = adv_by_symbol.get(symbol, 10_000_000)` et le passer à `CostModel.execution_cost_one_leg()`.
4. `CostModelConfig.default_adv_usd: float = 10_000_000` reste le fallback documenté.

Validation :
```powershell
venv\Scripts\python.exe -m pytest tests/ -x -q
# Attendu : 2681+ pass
venv\Scripts\python.exe -m pytest tests/ -k "cost" -v
```
Dépend de : Aucune  
Effort : 1 jour  
Statut : ✅ 2026-03-22

---

### ✅ [C-07] Activer le sizing VOLATILITY_INVERSE par défaut
Fichier : `portfolio_engine/allocator.py` (SizingMethod.EQUAL_WEIGHT)  
Problème : `EQUAL_WEIGHT` alloue la même fraction à toutes les paires indépendamment de leur vol de spread. Le portefeuille est dominé par les paires les plus volatiles → tail risk amplifié lors des retournements de régime.  
Correction :
1. Changer le défaut dans `PortfolioAllocatorConfig` :
```python
sizing_method: SizingMethod = SizingMethod.VOLATILITY_INVERSE  # était EQUAL_WEIGHT
volatility_lookback: int = 20  # barres pour calcul de la vol de spread
min_vol_floor: float = 0.001   # évite division par zéro
```
2. Lire `sizing_method` depuis `get_settings().portfolio.sizing_method` (ajouter le champ dans `config/config.yaml`).
3. Conserver `EQUAL_WEIGHT` comme option configurable (backtests de comparaison).

Validation :
```powershell
venv\Scripts\python.exe -m pytest tests/ -x -q
# Attendu : 2681+ pass
venv\Scripts\python.exe -m pytest tests/ -k "allocator" -v
# Vérifier que les allocations sont proportionnelles à 1/vol_spread
```
Dépend de : Aucune  
Effort : 0,5 jour  
Statut : ✅ 2026-03-22

---

### [C-08] Passer en log-prix pour le calcul du spread ✅
Fichier : `models/spread.py:compute_spread()`  
Problème : Le spread est calculé en prix niveau `y - (intercept + beta*x)`. Pour des actions (processus multiplicatif), les log-prix sont préférables : meilleure stationnarité à long terme, interprétation en rendements, moins sensible aux paires à prix très asymétriques.  
Correction :
1. Ajouter `use_log_prices: bool = False` dans `SpreadModelConfig` (activé en `dev`).
2. Dans `compute_spread()` :
```python
if self.config.use_log_prices:
    y_vals = np.log(y_series.values)
    x_vals = np.log(x_series.values)
else:
    y_vals, x_vals = y_series.values, x_series.values
```
3. S'assurer que les séries ne contiennent pas de valeurs ≤ 0 (gating `DelistingGuard` déjà en place).
4. Mettre à jour les tests existants avec `use_log_prices=False` pour compatibilité ascendante.

Validation :
```powershell
venv\Scripts\python.exe -m pytest tests/ -x -q
# Attendu : 2681+ pass
venv\Scripts\python.exe -m pytest tests/ -k "spread" -v
```
Dépend de : Aucune (mais doit précéder C-04)  
Effort : 0,5 jour  
Statut : ⏳

---

### [C-09] Rendre le RegimeDetector adaptatif (fenêtre dynamique)
Fichier : `models/regime_detector.py`  
Problème : La classification de régime (LOW/NORMAL/HIGH vol) utilise une fenêtre fixe de 20 barres pour les percentiles 33/67. Cette fenêtre est trop courte pour capturer les transitions de régimes prolongées (ex. bear market 2022 : 250 barres).  
Correction :
1. Ajouter `regime_window: int = 60` dans `RegimeDetectorConfig` (lisible depuis `get_settings()`).
2. Option : `adaptive_window: bool = False` — si activé, faire varier la fenêtre entre 20 et 120 barres en fonction de la vol réalisée récente (fenêtre courte en vol haute, longue en vol basse).
3. S'assurer que le changement ne casse pas le `régime → AdaptiveThresholdEngine` pipeline.

Validation :
```powershell
venv\Scripts\python.exe -m pytest tests/ -x -q
# Attendu : 2681+ pass
venv\Scripts\python.exe -m pytest tests/ -k "regime" -v
```
Dépend de : Aucune  
Effort : 0,5 jour  
Statut : ⏳

---

## SÉQUENCE D'EXÉCUTION

```
C-03  ← Sécurité live (câblage kill-switch) — risque ops critique, effort minimal
  ↓
C-08  ← Log-prix dans SpreadModel (prérequis pour C-04)
  ↓
C-01  ← Univers point-in-time (P0 — invalide tout backtest sans ça)
  ↓
C-05  ← HTB costs (simple, indépendant)
C-07  ← Vol-inverse sizing (simple, indépendant)
C-06  ← ADV réel au cost model (moyen, indépendant)
  ↓
C-04  ← Kalman hedge ratio (dépend de C-08)
  ↓
C-02  ← Execution timing T+1 (mesure réaliste possible seulement après C-01)
  ↓
C-09  ← Fenêtre régime adaptative (P3, peut passer en dernier)
```

> **Note processus** : exécuter `venv\Scripts\python.exe -m pytest tests/ -q` après chaque correction. Aucun commit si le test count régresse.

---

## CRITÈRES PASSAGE EN PRODUCTION

- [ ] Zéro 🔴 ouvert (C-01 validé avec univers point-in-time)
- [ ] `pytest tests/` : 100% pass (2681+)
- [ ] `mypy risk/ risk_engine/ execution/ models/` : exit 0
- [ ] `ruff check .` : 0 erreurs
- [ ] Zéro credential IBKR dans les logs
- [ ] Kill-switch persisté au redémarrage (`data/kill_switch_state.json` rechargé)
- [ ] **Kill-switch câblé à `cancel_all_open_orders()`** (C-03 ✅)
- [ ] Risk tiers cohérents (`_assert_risk_tier_coherence()` → OK)
- [ ] `EDGECORE_ENV=prod` dans Dockerfile (pas `production`)
- [ ] Backtest walk-forward avec univers point-in-time : Sharpe > 1.0, max DD < 10%
- [ ] Paper trading 10 jours validé avant live
- [ ] Convention execution timing documentée dans `backtests/strategy_simulator.py` (C-02)

---

## TABLEAU DE SUIVI

| ID | Titre | Sévérité | Fichier clé | Effort | Statut | Date |
|----|-------|---------|-------------|--------|--------|------|
| C-01 | Univers point-in-time (biais survie) | 🔴 P0 | `universe/manager.py` | 4 j | ✅ 2026-03-22 | — |
| C-02 | Execution timing T+1 | 🟠 P1 | `backtests/strategy_simulator.py:343` | 2 j | ✅ 2026-03-22 | — |
| C-03 | Câblage kill-switch → annulation IBKR | 🟠 P1 | `live_trading/runner.py` | 1 j | ✅ 2026-03-22 | — |
| C-04 | Hedge ratio Kalman barre-par-barre | 🟡 P2 | `models/spread.py:35-45` | 2 j | ✅ 2026-03-22 | — |
| C-05 | Coût emprunt HTB premium | 🟡 P2 | `backtests/cost_model.py` | 1 j | ✅ 2026-03-22 | — |
| C-06 | ADV réel → Almgren-Chriss | 🟡 P2 | `backtests/cost_model.py` | 1 j | ✅ 2026-03-22 | — |
| C-07 | Sizing VOLATILITY_INVERSE par défaut | 🟡 P2 | `portfolio_engine/allocator.py` | 0,5 j | ✅ 2026-03-22 | — |
| C-08 | Spread en log-prix | 🟡 P3 | `models/spread.py` | 0,5 j | ✅ 2026-03-22 | — |
| C-09 | RegimeDetector fenêtre adaptative | 🟡 P3 | `models/regime_detector.py` | 0,5 j | ✅ 2026-03-22 | 2764 |
