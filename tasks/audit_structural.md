# Audit Structurel EDGECORE — Checklist

> Source : Audit technique V3 — 18 issues identifiées (B2-01 → B5-04)
> Utilisation : cocher manuellement ou via `code_auditor` en session AI

---

## Bloc B2 — Dupliques et violations SRP

- [ ] **B2-01** `TradeOrder` dans `execution_engine/router.py` supprimé ou fusionné avec `Order` de `execution/base.py`
  ```powershell
  grep -n "class TradeOrder" execution_engine/router.py
  # Attendu : 0 résultats (après correction)
  ```

- [ ] **B2-02** `LiveTradingRunner._initialize()` utilise `RiskFacade` comme point d'entrée unique (pas 4 instanciations séparées)
  ```powershell
  grep -c "PositionRiskManager\|PortfolioRiskManager\|KillSwitch\|RiskFacade" live_trading/runner.py
  # Attendu après correction : 2 (import + instanciation RiskFacade)
  ```

- [ ] **B2-03** `LiveTradingRunner` fait < 400 lignes (SRP respecté, orchestrateur pur)
  ```powershell
  (Get-Content live_trading/runner.py).Count
  # Attendu : < 400
  ```

- [ ] **B2-04** `OrderStatus` source de vérité unique = `execution/base.py` (pas de redéfinition ailleurs)
  ```powershell
  grep -rn "class OrderStatus" --include="*.py" .
  # Attendu : 1 seul fichier
  ```

---

## Bloc B3 — Dettes de code

- [ ] **B3-01** Zéro occurrence de `datetime.utcnow()` dans les modules de production
  ```powershell
  grep -r "utcnow" --include="*.py" . | Where-Object { $_ -notmatch "test|\.pyc" }
  # Attendu : 0 résultats
  ```

- [ ] **B3-02** Zéro `print()` dans les modules de production (hors scripts/, examples/, research/)
  ```powershell
  grep -rn "^\s*print(" --include="*.py" backtests/ execution/ execution_engine/ live_trading/ risk/ risk_engine/ models/ pair_selection/ portfolio_engine/ signal_engine/ universe/
  # Attendu : 0 résultats
  ```

- [ ] **B3-03** Zéro seuil de risque hardcodé (drawdown, entry_z, stop_loss) dans les modules de production
  ```powershell
  grep -n "slippage\s*=\s*[0-9]" execution_engine/router.py
  # Attendu : 0 (ou lignes marquées DEPRECATED)
  ```

- [ ] **B3-04** Tous les appels IBKR passent par `_ibkr_rate_limiter.acquire()` ou `acquire_sync()`
  ```powershell
  grep -c "rate_limiter" execution/ibkr_engine.py
  # Vérifier visuellement que chaque appel reqXxx est précédé d'un acquire
  ```

---

## Bloc B4 — Fichiers orphelins et sprint

- [ ] **B4-01** `models/performance_optimizer_s41.py` archivé ou supprimé (aucun import en production)
  ```powershell
  grep -r "performance_optimizer_s41" --include="*.py" . | Where-Object { $_ -notmatch "test" }
  # Attendu : 0 résultats
  ```

- [ ] **B4-02** `monitoring/cache_advanced_s42.py` et `monitoring/portfolio_extension_s43.py` renommés sans suffixe sprint
  ```powershell
  Test-Path "monitoring/cache_advanced_s42.py"
  # Attendu : False
  ```

- [ ] **B4-03** Aucun fichier `run_backtest_v*.py` dans `scripts/` (conserver uniquement `run_backtest.py`)
  ```powershell
  Get-ChildItem scripts/ -Filter "run_backtest_v*.py"
  # Attendu : 0 fichiers
  ```

- [ ] **B4-04** `CMakeLists.txt` archivé dans `docs/archived/` (pipeline C++/pybind11 abandonné)
  ```powershell
  Test-Path "CMakeLists.txt"
  # Attendu : False (déplacé)
  Test-Path "docs/archived/CMakeLists.txt"
  # Attendu : True
  ```

- [ ] **B4-05** `backtester/__init__.py` existe
  ```powershell
  Test-Path "backtester/__init__.py"
  # Attendu : True
  ```

- [ ] **B4-06** Fichiers debug à la racine supprimés (`phase0_test_results.txt`, `pytest_output.txt`, `paper_trading_log.txt`, `ibkr_invalid_symbols.txt`)
  ```powershell
  Get-ChildItem . -Filter "*.txt" -Depth 0
  # Attendu : 0 fichiers .txt à la racine
  ```

---

## Bloc B5 — Configuration et infrastructure

- [ ] **B5-01** Docker utilise `EDGECORE_ENV=prod` (pas `production`)
  ```powershell
  Select-String -Path Dockerfile,docker-compose.yml -Pattern "production"
  # Attendu : 0 résultats
  Select-String -Path Dockerfile,docker-compose.yml -Pattern "EDGECORE_ENV"
  # Attendu : valeur = "prod"
  ```

- [ ] **B5-02** `execution_engine/router.py` lit `get_settings().costs.slippage_bps` (pas `slippage = 2.0`)
  ```powershell
  grep -n "slippage\s*=\s*2" execution_engine/router.py
  # Attendu : 0 résultats
  ```

- [ ] **B5-03** `backtests/runner.py` — constantes `COMMISSION_BPS` et `SLIPPAGE_BPS` supprimées ou remplacées par `CostModel.from_settings()`
  ```powershell
  grep -n "COMMISSION_BPS\|SLIPPAGE_BPS" backtests/runner.py
  # Attendu : 0 résultats ou lignes marquées DEPRECATED
  ```

- [ ] **B5-04** Risk tier coherence passe au démarrage
  ```powershell
  venv\Scripts\python.exe -c "from config.settings import get_settings; get_settings()._assert_risk_tier_coherence(); print('OK')"
  # Attendu : "OK" sans exception
  ```

---

## Validation finale

```powershell
# Tests complets
venv\Scripts\python.exe -m pytest tests/ -q
# Attendu : >= 2654 passed, 0 failed

# Warnings datetime
venv\Scripts\python.exe -m pytest tests/ -W error::DeprecationWarning -q
# Attendu : 0 DeprecationWarning
```

---

## Résumé statut

| Issue | Fichier | Statut | Date |
|-------|---------|--------|------|
| B2-01 | execution_engine/router.py | ⏳ | — |
| B2-02 | live_trading/runner.py | ⏳ | — |
| B2-03 | live_trading/runner.py | ⏳ | — |
| B2-04 | execution/base.py | ⏳ | — |
| B3-01 | All .py | ✅ | 2026-03 |
| B3-02 | Production modules | ✅ | 2026-03 |
| B3-03 | execution_engine/router.py | ⏳ | — |
| B3-04 | execution/ibkr_engine.py | ✅ | 2026-03 |
| B4-01 | models/performance_optimizer_s41.py | ✅ | 2026-03-17 |
| B4-02 | monitoring/cache_advanced_s42.py | ✅ | 2026-03-17 |
| B4-03 | scripts/run_backtest_v*.py | ✅ | 2026-03-17 |
| B4-04 | CMakeLists.txt | ✅ | 2026-03-17 |
| B4-05 | backtester/__init__.py | ✅ | 2026-03-17 |
| B4-06 | *.txt root files | ✅ | 2026-03-17 |
| B5-01 | Dockerfile, docker-compose.yml | ✅ | 2026-03-17 |
| B5-02 | execution_engine/router.py | ⏳ | — |
| B5-03 | backtests/runner.py | ⏳ | — |
| B5-04 | config/settings.py | ✅ | 2026-03 |
