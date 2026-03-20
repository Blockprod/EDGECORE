---
projet: EDGECORE
type: plan-action
source: tasks/audits/audit_structural_edgecore.md
date: 2026-03-20
modele: claude-sonnet-4.6
---

# PLAN D'ACTION â€” EDGECORE â€” 2026-03-20
Sources : `tasks/audits/audit_structural_edgecore.md`
Total : ðŸ”´ 2 Â· ðŸŸ  7 Â· ðŸŸ¡ 5 Â· ðŸ”µ 4 Â· Effort estimÃ© : 12â€“18 jours

---

## PHASE 1 â€” CRITIQUES ðŸ”´

---

### [C-01] Supprimer le double ThreadPoolExecutor dans bulk_load

Fichier : `data/loader.py:366-400`

ProblÃ¨me : `bulk_load()` contient deux blocs `with ThreadPoolExecutor(...)` identiques.
Le premier appelle les workers IBKR mais ne persiste pas les rÃ©sultats dans `results`
(`completed = 0` reset, boucle rejouÃ©e entiÃ¨rement). Chaque appel dÃ©clenche **2Ã—
les appels IBKR** pour tous les symboles non cachÃ©s â€” double consommation du rate
limit (45 req/s), temps d'exÃ©cution doublÃ©, risque de dÃ©connexion TWS.

Correction :
  1. Lire `data/loader.py` autour de la ligne 366.
  2. Supprimer le PREMIER bloc `with ThreadPoolExecutor(...)` et son
     `completed = 0` associÃ© (lignes ~366â€“376). Ne conserver que le SECOND
     bloc (lignes ~377+) qui peuple rÃ©ellement `results`.
  3. VÃ©rifier que `symbol_chunks` est dÃ©fini avant le bloc conservÃ©.
  4. Supprimer le commentaire orphelin `# ...existing code...` Ã  l'intÃ©rieur
     du premier bloc.

Validation :
  ```powershell
  venv\Scripts\python.exe -m pytest tests/ -x -q -k "bulk_load or loader"
  # Attendu : tests passe, aucune deuxieme connexion IBKR en mock
  venv\Scripts\python.exe -m pytest tests/ -x -q
  # Attendu : 2654+ passed, 0 failed
  ```

DÃ©pend de : Aucune
Statut : ✅ — commit `2bcc745`

---

### [C-02] Supprimer l'Ã©criture debug en production dans bulk_load

Fichier : `data/loader.py:282-288`

ProblÃ¨me : Bloc `try: with open("debug_bulk_to_fetch_snapshot.txt", "w"...)` Ã©crit
un fichier de debug Ã  chaque appel `bulk_load()`. L'Ã©criture est relative au cwd â€”
peut atterrir n'importe oÃ¹ en production. Fuite d'information, I/O inutile.

Correction :
  1. Supprimer le bloc `try: with open("debug_bulk_to_fetch_snapshot.txt" ...)
     ... except Exception: pass` dans son intÃ©gralitÃ© (lignes ~282-288).
  2. Supprimer le commentaire qui l'introduit
     (`# Debug snapshot: write the to_fetch list...`).
  3. Si le snapshot est utile au debug, le remplacer par :
     `logger.debug("bulk_load_to_fetch_snapshot", count=len(to_fetch), first_five=to_fetch[:5])`

Validation :
  ```powershell
  venv\Scripts\python.exe -m pytest tests/ -x -q
  # Attendu : 2654+ passed, 0 failed
  # Verifier qu'aucun fichier debug_bulk_*.txt n'est cree dans le repertoire courant
  Test-Path "debug_bulk_to_fetch_snapshot.txt"
  # Attendu : False
  ```

DÃ©pend de : Aucune
Statut : ✅

---

## PHASE 2 â€” MAJEURES ðŸŸ 

---

### [C-03] Corriger OrderStatus dans execution/modes.py â€” importer depuis base.py

Fichier : `execution/modes.py:30-40`

ProblÃ¨me : `OrderStatus` est redÃ©fini localement avec 6 Ã©tats (PENDING, SUBMITTED,
FILLED, PARTIALLY_FILLED, CANCELLED, FAILED) vs 11 dans `execution/base.py`
(+ PARTIAL, TIMEOUT, ERROR, UNKNOWN, REJECTED). Le commentaire docstring dit
"delegates to execution.base.OrderStatus values" mais ce n'est pas le cas â€” valeurs
redÃ©finies inline. Les Ã©tats TIMEOUT/ERROR/UNKNOWN manquants causent des bugs
silencieux quand un ordre atteint un Ã©tat non gÃ©rÃ©.

Correction :
  1. Supprimer la classe `OrderStatus` dans `execution/modes.py` (lignes 30-40).
  2. Ajouter en tÃªte du fichier : `from execution.base import OrderStatus`
  3. VÃ©rifier que toutes les rÃ©fÃ©rences dans `execution/modes.py` Ã 
     `OrderStatus.PENDING`, `.FILLED`, etc. restent valides avec les 11 Ã©tats.
  4. Adapter `is_complete` dans la classe `Order` locale si besoin
     (ajouter `OrderStatus.REJECTED`, `OrderStatus.TIMEOUT` dans la liste).

Validation :
  ```powershell
  grep -n "class OrderStatus" execution/modes.py
  # Attendu : 0 resultats
  grep -n "from execution.base import" execution/modes.py
  # Attendu : 1 ligne contenant OrderStatus
  venv\Scripts\python.exe -m pytest tests/ -x -q
  # Attendu : 2654+ passed, 0 failed
  ```

DÃ©pend de : Aucune
Statut : ✅

---

### [C-04] Unifier slippage backtest vs paper â€” lire CostConfig uniformÃ©ment

Fichier : `execution_engine/router.py:211`

ProblÃ¨me : Le path paper lit `get_settings().execution.slippage_bps` (2.0 bps)
alors que le path backtest lit `get_settings().costs.slippage_bps` (3.0 bps).
Un backtest calibrÃ© sur 3.0 bps trade en paper Ã  2.0 bps â†’ rÃ©sultats de paper
systÃ©matiquement optimistes vs backtest. Rend la comparaison backtest/live invalide.

Correction :
  1. Lire `execution_engine/router.py` lignes ~200-230 (mÃ©thode `_paper_fill`).
  2. Remplacer `slippage = get_settings().execution.slippage_bps` (ligne ~211)
     par `slippage = get_settings().costs.slippage_bps`.
  3. VÃ©rifier que `CostConfig.slippage_bps` est bien prÃ©sent dans `dev.yaml`,
     `test.yaml`, `prod.yaml` (ou qu'un dÃ©faut raisonnable est dÃ©fini dans
     la dataclass `CostConfig`).
  4. Dans `config/settings.py`, supprimer ou dÃ©prÃ©cier `ExecutionConfig.slippage_bps`
     si sa seule utilisation Ã©tait ce path paper (vÃ©rifier par grep).

Validation :
  ```powershell
  grep -n "execution.slippage_bps" execution_engine/router.py
  # Attendu : 0 resultats
  grep -n "costs.slippage_bps" execution_engine/router.py
  # Attendu : 2 resultats (backtest + paper)
  venv\Scripts\python.exe -m pytest tests/ -x -q
  # Attendu : 2654+ passed, 0 failed
  ```

DÃ©pend de : Aucune
Statut : ✅

---

### [C-05] Corriger exit_z_score dans test.yaml (0.0 â†’ 0.5)

Fichier : `config/test.yaml:13`

ProblÃ¨me : `exit_z_score: 0.0` â€” un spread ne touche jamais exactement 0.0 en
arithmÃ©tique flottante. Les tests de stratÃ©gie qui utilisent cette config ne
couvrent jamais les sorties de position â†’ biais systÃ©matique des tests.

Correction :
  1. Modifier `config/test.yaml` ligne 13 : `exit_z_score: 0.0` â†’ `exit_z_score: 0.5`
  2. VÃ©rifier la cohÃ©rence avec `entry_z_score` dans le mÃªme fichier
     (doit respecter `exit_z_score < entry_z_score`).

Validation :
  ```powershell
  venv\Scripts\python.exe -c "
  import yaml
  with open('config/test.yaml') as f:
    c = yaml.safe_load(f)
  assert c['strategy']['exit_z_score'] == 0.5, 'KO'
  assert c['strategy']['exit_z_score'] < c['strategy']['entry_z_score'], 'coherence KO'
  print('OK')
  "
  venv\Scripts\python.exe -m pytest tests/ -x -q
  # Attendu : 2654+ passed, 0 failed
  ```

DÃ©pend de : Aucune
Statut : ✅

---

### [C-06] Nettoyer edgecore/ â€” supprimer artefacts C++ Python 3.13

Fichier : `edgecore/` (dossier entier)

ProblÃ¨me : Le dossier `edgecore/` contient :
  - `backtest_engine_cpp.cp313-win_amd64.pyd` : extension C++ compilÃ©e pour Python 3.13
    (projet cible 3.11). Non chargeable, prÃ©sence confuse.
  - `cointegration_cpp.cp313-win_amd64.pyd` : idem.
  - `backtest_engine_wrapper.py` (134 lignes) : passthrough Python pur vers
    `backtests/strategy_simulator.py` â€” doublon fonctionnel.
  - `cointegration_engine_wrapper.py` : passthrough vers `models/cointegration.py`.

Correction :
  1. VÃ©rifier qu'aucun fichier de production n'importe depuis `edgecore/` :
     `grep -r "from edgecore" --include="*.py" . | grep -v test | grep -v __pycache__`
  2. Si aucun import en prod â†’ dÃ©placer `edgecore/backtest_engine_wrapper.py`
     et `edgecore/cointegration_engine_wrapper.py` dans `docs/archived/edgecore/`.
  3. Supprimer `edgecore/backtest_engine_cpp.cp313-win_amd64.pyd` et
     `edgecore/cointegration_cpp.cp313-win_amd64.pyd` (non utilisables en 3.11).
  4. Si `edgecore/__init__.py` n'expose rien de nÃ©cessaire, le vider.
  5. Ajouter `edgecore/` dans `.gitignore` s'il ne reste que des .pyd rÃ©siduels.

Validation :
  ```powershell
  Get-ChildItem edgecore/ -Filter "*.pyd"
  # Attendu : uniquement les .cp311-win_amd64.pyd (s'il en reste)
  venv\Scripts\python.exe -m pytest tests/ -x -q
  # Attendu : 2654+ passed, 0 failed
  ```

DÃ©pend de : Aucune
Statut : ✅

---

### [C-07] Fixer divergence drawdown â€” LiveTradingRunner utilise RiskFacade comme seule source de vÃ©ritÃ©

Fichier : `live_trading/runner.py:227-237`

ProblÃ¨me : `_initialize()` crÃ©e `PositionRiskManager`, `PortfolioRiskManager`,
`KillSwitch` ET `RiskFacade`. Le `KillSwitch` est partagÃ© (B2-02 partiellement
corrigÃ©), mais `RiskFacade` contient un `RiskEngine` interne qui monitore
**aussi** le drawdown â€” indÃ©pendamment de `PortfolioRiskManager`. Deux compteurs
de drawdown peuvent diverger, causant un Ã©tat incohÃ©rent (l'un dit OK, l'autre dit halt).

Correction :
  Approche minimale (sans refactoring massif) :
  1. Lire `live_trading/runner.py` mÃ©thodes `_initialize()` et `_tick()`.
  2. Identifier oÃ¹ `self._portfolio_risk.check(...)` et `self._risk_facade.can_enter_trade(...)`
     sont appelÃ©s dans `_tick()`.
  3. Dans `_tick()`, **ne plus appeler `self._portfolio_risk.check()`** si
     `self._risk_facade.can_enter_trade()` effectue dÃ©jÃ  le mÃªme check drawdown.
  4. Conserver `self._portfolio_risk` uniquement pour les fonctions que `RiskFacade`
     ne couvre pas (ex: heat mapping, position monitoring par paire).
  5. Documenter clairement quelles vÃ©rifications sont dÃ©lÃ©guÃ©es Ã  la faÃ§ade vs
     celles qui restent dans `PortfolioRiskManager`.
  Alternative : Si l'analyse montre que `PortfolioRiskManager` est redondant avec
  `RiskEngine` (dans RiskFacade) pour les checks de drawdown â†’ supprimer l'instanciation
  de `self._portfolio_risk` et dÃ©lÃ©guer Ã  `self._risk_facade` uniquement.

Validation :
  ```powershell
  venv\Scripts\python.exe -m pytest tests/ -x -q -k "risk or runner or facade"
  # Attendu : tous les tests risk passent
  venv\Scripts\python.exe -m pytest tests/ -x -q
  # Attendu : 2654+ passed, 0 failed
  ```

DÃ©pend de : Aucune (mais analyser avant d'Ã©diter â€” ce ticket nÃ©cessite une lecture
             approfondie de _tick() avant toute modification)
Statut : ✅

---

### [C-08] Corriger commission hardcodÃ©e dans router.py â€” lire depuis CostConfig

Fichier : `execution_engine/router.py:192,226`

ProblÃ¨me : `commission=order.quantity * price * 0.00005` (~0.5 bps) hardcodÃ© aux
lignes 192 et 226. La commission n'est pas configurable et diverge de `CostConfig`.

Correction :
  1. Lire `execution_engine/router.py` lignes 180-230.
  2. Dans `_simulate_fill` et `_paper_fill`, remplacer la commission hardcodÃ©e par :
     `commission=order.quantity * price * (get_settings().costs.commission_bps / 10_000)`
  3. VÃ©rifier que `CostConfig` a un champ `commission_bps` dans `config/settings.py`.
     Si absent â†’ ajouter `commission_bps: float = 5.0` dans `CostConfig` (dataclass).
  4. Mettre Ã  jour `dev.yaml`, `test.yaml`, `prod.yaml` si nÃ©cessaire.

Validation :
  ```powershell
  grep -n "0.00005" execution_engine/router.py
  # Attendu : 0 resultats
  grep -n "commission_bps" execution_engine/router.py
  # Attendu : 2 resultats
  venv\Scripts\python.exe -m pytest tests/ -x -q
  # Attendu : 2654+ passed, 0 failed
  ```

DÃ©pend de : [C-04] (mÃªme fichier â€” appliquer aprÃ¨s C-04)
Statut : ✅

---

### [C-09] Supprimer execution/modes.py â€” architecture parallÃ¨le non utilisÃ©e

Fichier : `execution/modes.py:1-868`

ProblÃ¨me : `execution/modes.py` (868 lignes) est une architecture parallÃ¨le complÃ¨te
(Order, OrderStatus, 3 ExecutionMode, ExecutionEngine) qui n'est pas utilisÃ©e par
le pipeline principal. Elle redÃ©finit `Order` et `OrderStatus` (dÃ©jÃ  adressÃ© par C-03),
et contient une classe `ExecutionEngine` (ligne 817) de ~50 mÃ©thodes orphelines.

Correction :
  1. Grep pour confirmer les imports : `grep -r "from execution.modes import" --include="*.py" .`
  2. Si le fichier n'est importÃ© que par des tests ou des modules non-production :
     - DÃ©placer `execution/modes.py` vers `docs/archived/execution_modes_legacy.py`
     - Mettre Ã  jour les tests concernÃ©s pour utiliser `execution/base.py`
  3. Si des callers valides existent : extraire uniquement la classe finale nÃ©cessaire
     et supprimer le reste.
  4. VÃ©rifier que `ExecutionMode` (enum PAPER/LIVE/BACKTEST) n'est pas dÃ©fini
     uniquement ici â€” le dÃ©placer dans `execution/base.py` si c'est le cas.

Validation :
  ```powershell
  grep -r "from execution.modes" --include="*.py" . | Where-Object { $_ -notmatch "__pycache__" }
  # Attendu : 0 resultats (ou seulement des tests mis a jour)
  venv\Scripts\python.exe -m pytest tests/ -x -q
  # Attendu : 2654+ passed, 0 failed
  ```

DÃ©pend de : [C-03] (OrderStatus unifiÃ© en premier)
Statut : ✅

---

## PHASE 3 â€” MINEURES ðŸŸ¡

---

### [C-10] Synchroniser versions setup.py et pyproject.toml

Fichier : `setup.py:30`, `pyproject.toml:7`

ProblÃ¨me : `setup.py` dÃ©clare `version='0.1.0'`, `pyproject.toml` dÃ©clare
`version = "1.0.0"`. Deux sources de vÃ©ritÃ© incohÃ©rentes.

Correction :
  1. DÃ©cider de la version canonique (probablement `1.0.0` de `pyproject.toml`).
  2. Modifier `setup.py:30` : `version='0.1.0'` â†’ `version='1.0.0'`.
  3. Pour l'avenir, envisager de lire la version depuis une seule source :
     ```python
     # setup.py
     import tomllib
     with open("pyproject.toml", "rb") as f:
         version = tomllib.load(f)["project"]["version"]
     ```

Validation :
  ```powershell
  Select-String -Path setup.py,pyproject.toml -Pattern "version"
  # Attendu : valeur identique dans les deux fichiers
  venv\Scripts\python.exe setup.py --version
  # Attendu : 1.0.0
  ```

DÃ©pend de : Aucune
Statut : ✅

---

### [C-11] Corriger test.yaml â€” ajouter section costs avec slippage_bps

Fichier : `config/test.yaml`

ProblÃ¨me : `test.yaml` ne contient pas de section `costs`. Les tests utilisent
les dÃ©fauts Python de `CostConfig` (~3.0 bps de slippage) â€” valeurs non maÃ®trisÃ©es
et potentiellement diffÃ©rentes des autres environnements. AprÃ¨s [C-04], la section
`costs` est lue dans tous les paths â†’ son absence en test provoquerait des dÃ©fauts
silencieux.

Correction :
  1. Lire `config/test.yaml` et `config/dev.yaml` pour comparer les sections.
  2. Ajouter dans `config/test.yaml` une section `costs` :
     ```yaml
     costs:
       slippage_bps: 3.0
       commission_bps: 5.0
     ```
  3. VÃ©rifier que les dÃ©fauts dataclass `CostConfig` correspondent Ã  ces valeurs
     (pour Ã©viter de casser les tests qui mockent la config).

Validation :
  ```powershell
  venv\Scripts\python.exe -c "
  import os; os.environ['EDGECORE_ENV']='test'
  from config.settings import get_settings
  s = get_settings()
  print(s.costs.slippage_bps)
  # Attendu : 3.0
  "
  venv\Scripts\python.exe -m pytest tests/ -x -q
  # Attendu : 2654+ passed, 0 failed
  ```

DÃ©pend de : [C-04], [C-05]
Statut : ✅

---

### [C-12] Supprimer les 4 schemas Pydantic inutilisÃ©s dans config/schemas.py

Fichier : `config/schemas.py:170-508`

ProblÃ¨me : `config/schemas.py` dÃ©finit 6 schemas Pydantic mais `Settings._validate_config()`
n'en utilise que 2 (`RiskConfigSchema`, `StrategyConfigSchema`). Les 4 autres
(`ExecutionConfigSchema`, `DataSourceConfigSchema`, `AlerterConfigSchema`,
`BacktestConfigSchema`) sont du code mort. Ils crÃ©ent une fausse sÃ©curitÃ©
(on pense que la config est validÃ©e, mais elle ne l'est pas).

Correction :
  1. Lire `config/settings.py:265-290` (`_validate_config()`).
  2. Option A (minimal) : Appliquer les 4 schemas manquants dans `_validate_config()`.
  3. Option B (nettoyage) : Supprimer les 4 schemas non utilisÃ©s de `schemas.py`
     et documenter que seuls `RiskConfigSchema` et `StrategyConfigSchema` sont
     la stratÃ©gie de validation retenue.
  4. RecommandÃ© : Option A â€” Ã©tendre la couverture de validation (retour sur
     l'investissement immÃ©diat en qualitÃ©).

Validation :
  ```powershell
  venv\Scripts\python.exe -c "
  import os; os.environ['EDGECORE_ENV']='dev'
  from config.settings import get_settings
  s = get_settings()
  print('Config validated OK')
  "
  venv\Scripts\python.exe -m pytest tests/ -x -q
  # Attendu : 2654+ passed, 0 failed
  ```

DÃ©pend de : Aucune
Statut : ✅

---

### [C-13] Nettoyer les artefacts de debug Ã  la racine et dans data/

Fichiers : `ibkr_invalid_symbols.txt`, `data/kill_switch_state.bak`, `scripts/ARCHIVED_*.py`

ProblÃ¨me :
  - `ibkr_invalid_symbols.txt` (racine) : artefact manuel non rÃ©fÃ©rencÃ© dans le code.
  - `data/kill_switch_state.bak` : Ã©tat persistÃ© du KillSwitch dans `data/` au lieu
    de `persistence/` â€” incohÃ©rence architecturale.
  - `scripts/ARCHIVED_benchmark_cpp_acceleration.py`,
    `scripts/ARCHIVED_setup_cpp_acceleration.py` : prÃ©sents dans scripts/ actif,
    source de confusion si exÃ©cutÃ©s.

Correction :
  1. DÃ©placer `ibkr_invalid_symbols.txt` â†’ `data/audit/ibkr_invalid_symbols.txt`
     ET l'ajouter Ã  `.gitignore` (artefact gÃ©nÃ©rÃ©).
  2. DÃ©placer `data/kill_switch_state.bak` â†’ `persistence/kill_switch_state.bak`
     ET mettre Ã  jour le chemin dans `risk_engine/kill_switch.py` (grep le chemin hardcodÃ©).
  3. DÃ©placer `scripts/ARCHIVED_*.py` â†’ `docs/archived/scripts/` OU les supprimer
     si plus utiles.
  4. Ajouter `*.bak` dans `.gitignore`.

Validation :
  ```powershell
  Test-Path "ibkr_invalid_symbols.txt"
  # Attendu : False
  Test-Path "data/kill_switch_state.bak"
  # Attendu : False (si deplace)
  venv\Scripts\python.exe -m pytest tests/ -x -q
  # KillSwitch doit fonctionner apres deplacement du chemin .bak
  # Attendu : 2654+ passed, 0 failed
  ```

DÃ©pend de : Aucune
Statut : ✅

---

### [C-14] Documenter architecture backtests/ vs backtester/ dans les docstrings

Fichier : `backtester/runner.py:1`, `backtester/walk_forward.py:1`, `backtests/runner.py:1`

ProblÃ¨me : L'architecture deux-couches (backtests/ = implÃ©mentations, backtester/ = faÃ§ades)
est intentionnelle mais non documentÃ©e. De nouveaux dÃ©veloppeurs importent directement
`backtests/runner.py` contournant la faÃ§ade typÃ©e. Pas de guideline sur quand utiliser
chaque couche.

Correction :
  1. Ajouter/mettre Ã  jour le module docstring de `backtester/runner.py` :
     ```python
     """
     Haute-level facade over backtests.runner.BacktestRunner.
     Callers SHOULD import from backtester/, not backtests/ directly.
     backtests/ contains raw implementations; backtester/ exposes typed API.
     """
     ```
  2. Idem pour `backtester/walk_forward.py` et `backtester/oos.py`.
  3. Ajouter un commentaire dans `backtests/runner.py` : "Internal â€” use backtester.runner.BacktestEngine for external callers."
  4. Grep pour imports directs de `backtests.runner` dans des modules non-backtests/
     et les router vers `backtester.runner`.

Validation :
  ```powershell
  venv\Scripts\python.exe -m pytest tests/ -x -q
  # Attendu : 2654+ passed, 0 failed
  ```

DÃ©pend de : Aucune
Statut : ✅

---

## PHASE 4 â€” REFACTORING MAJEUR ðŸ”µ (post-corrections critiques)

Ces items sont des restructurations profondes. Ã€ planifier sÃ©parÃ©ment aprÃ¨s
validation complÃ¨te des phases 1â€“3.

---

### [R-01] DÃ©composer backtests/strategy_simulator.py (1 609 lignes)

Fichier : `backtests/strategy_simulator.py:1-1609`
Effort : 3â€“5 jours

Le God class mÃ©lange loop de simulation, risk inline, cost model, pair discovery
et mÃ©triques. DÃ©composer en :
- `backtests/simulation_loop.py` (moteur bar-par-bar)
- `backtests/order_book.py` (gestion des ordres simulÃ©s)
- DÃ©lÃ©guer risk checks Ã  `risk/facade.py::RiskFacade`
- DÃ©lÃ©guer cost model Ã  `backtests/cost_model.py::CostModel` (dÃ©jÃ  prÃ©sent)
- DÃ©lÃ©guer pair discovery Ã  `pair_selection/discovery.py`

DÃ©pend de : [C-07] (RiskFacade unifiÃ©), toutes les phases 1â€“3
Statut : ✅

---

### [R-02] DÃ©composer strategies/pair_trading.py (1 102 lignes)

Fichier : `strategies/pair_trading.py:1-1102`
Effort : 2â€“4 jours

Extraire vers les modules existants :
- `is_cointegration_stable()` â†’ `models/cointegration.py`
- Gestion `active_trades` â†’ classe dÃ©diÃ©e `strategies/trade_book.py`
- Regime detection â†’ dÃ©lÃ©guer Ã  `models/regime_detector.py::RegimeDetector`
- Tout signal â†’ dÃ©lÃ©guer Ã  `signal_engine/generator.py::SignalGenerator`

DÃ©pend de : [R-01], [C-03]
Statut : ✅

---

### [R-03] Ã‰liminer TradeOrder dans execution_engine/router.py â€” migrer vers Order

Fichier : `execution_engine/router.py:42-67`
Effort : 1â€“2 jours

`TradeOrder` est marquÃ© `@deprecated (B2-01)` mais les callers internes utilisent
encore ce type. Migrer toutes les crÃ©ations de `TradeOrder` vers `execution.base.Order`.
Supprimer ensuite la classe `TradeOrder`.

DÃ©pend de : [C-03], [C-09]
Statut : ✅

---

### [R-04] Ajouter key Protocols (typing.Protocol) pour SignalGenerator, Allocator, Loader

Fichier : `execution/base.py`, `signal_engine/`, `portfolio_engine/`, `data/`
Effort : 1 jour

Introduire des `Protocol` pour les trois interfaces non formalisÃ©es afin de
dÃ©coupler les dÃ©pendances et faciliter le testing par injection.

DÃ©pend de : [R-01], [R-02]
Statut : ✅

---

## SÃ‰QUENCE D'EXÃ‰CUTION

```
[C-01] â†’ [C-02]                     (P0 indÃ©pendants, prioritÃ© absolue)
          â†“
[C-03] â†’ [C-09]                     (OrderStatus unifiÃ© avant suppression modes.py)
[C-04] â†’ [C-08] â†’ [C-11]           (slippage unifiÃ© avant commission, puis test.yaml)
[C-05]                               (indÃ©pendant â€” modifier test.yaml exit_z_score)
[C-06]                               (indÃ©pendant â€” nettoyer edgecore/)
[C-07]                               (analyser _tick() avant toute modification)
[C-10]                               (indÃ©pendant â€” versions)
[C-12]                               (indÃ©pendant â€” schemas Pydantic)
[C-13]                               (indÃ©pendant â€” artefacts)
[C-14]                               (indÃ©pendant â€” documentation)
          â†“
[R-01] â†’ [R-02] â†’ [R-03] â†’ [R-04]  (refactoring sÃ©quentiel â€” aprÃ¨s toutes corrections)
```

---

## CRITÃˆRES PASSAGE EN PRODUCTION

- [x] Zéro 🔴 ouvert (C-01 et C-02 rÃ©solus et testÃ©s)
- [x] `pytest tests/ -q` : 2659 passed, 0 failed
- [x] `pytest tests/ -W error::DeprecationWarning -q` : 0 DeprecationWarning
- [x] `mypy risk/ risk_engine/ execution/ --ignore-missing-imports --no-error-summary` : exit 0
- [x] `ruff check .` : 0 erreurs
- [x] `Test-Path "debug_bulk_to_fetch_snapshot.txt"` : False (pas de fichier debug en prod)
- [x] `grep -n "class OrderStatus" execution/modes.py` (archivé → `modes_legacy.py`) : 0 rÃ©sultats
- [x] `grep -n "execution.slippage_bps" execution_engine/router.py` : 0 rÃ©sultats
- [x] Risk tiers cohÃ©rents : `venv\Scripts\python.exe -c "from config.settings import get_settings; get_settings()._assert_risk_tier_coherence(); print('OK')"`
- [x] `EDGECORE_ENV=prod` dans Dockerfile (dÃ©jÃ  corrigÃ© â€” maintenir)
- [x] Kill-switch persistÃ© au redÃ©marrage (vÃ©rifier chemin .bak aprÃ¨s C-13)
- [ ] Paper trading validÃ© sur 48h avant passage live

---

## TABLEAU DE SUIVI

| ID | Titre | SÃ©vÃ©ritÃ© | Fichier | Effort | Statut | Date |
|----|-------|----------|---------|--------|--------|------|
| C-01 | Supprimer double ThreadPoolExecutor | ðŸ”´ P0 | `data/loader.py:366-400` | 1h | ✅ | 2026-03-20 |
| C-02 | Supprimer Ã©criture debug en prod | ðŸ”´ P0 | `data/loader.py:282-288` | 30min | ✅ | 2026-03-20 |
| C-03 | OrderStatus importer depuis base.py | ðŸŸ  P1 | `execution/modes.py:30-40` | 1h | ✅ | 2026-03-20 |
| C-04 | Unifier slippage backtest=paper | ðŸŸ  P1 | `execution_engine/router.py:211` | 1h | ✅ | 2026-03-20 |
| C-05 | exit_z_score: 0.0 â†’ 0.5 dans test.yaml | ðŸŸ  P1 | `config/test.yaml:13` | 15min | ✅ | 2026-03-20 |
| C-06 | Nettoyer edgecore/ artefacts C++ | ðŸŸ  P1 | `edgecore/` | 2h | ✅ | 2026-03-20 |
| C-07 | Unifier drawdown via RiskFacade seule | ðŸŸ  P1 | `live_trading/runner.py:227-237` | 4h | ✅ | 2026-03-20 |
| C-08 | Commission hardcodÃ©e â†’ CostConfig | ðŸŸ  P1 | `execution_engine/router.py:192,226` | 1h | ✅ | 2026-03-20 |
| C-09 | Supprimer execution/modes.py | ðŸŸ  P1 | `execution/modes.py:1-868` | 4h | ✅ | 2026-03-20 |
| C-10 | Synchroniser versions setup.py/pyproject.toml | ðŸŸ¡ P2 | `setup.py:30` | 15min | ✅ | 2026-03-20 |
| C-11 | Ajouter section costs dans test.yaml | ðŸŸ¡ P2 | `config/test.yaml` | 30min | ✅ | 2026-03-20 |
| C-12 | Activer/supprimer schemas Pydantic inutilisÃ©s | ðŸŸ¡ P2 | `config/schemas.py:170-508` | 3h | ✅ | 2026-03-20 |
| C-13 | Nettoyer artefacts racine et data/ | ðŸŸ¡ P2 | plusieurs | 1h | ✅ | 2026-03-20 |
| C-14 | Documenter architecture backtests/ vs backtester/ | ðŸŸ¡ P2 | `backtester/*.py` | 1h | ✅ | 2026-03-20 |
| R-01 | DÃ©composer strategy_simulator.py | ðŸ”µ P1 | `backtests/strategy_simulator.py` | 3-5j | ✅ | 2026-03-20 |
| R-02 | DÃ©composer pair_trading.py | ðŸ”µ P1 | `strategies/pair_trading.py` | 2-4j | ✅ | 2026-03-20 |
| R-03 | Ã‰liminer TradeOrder | ðŸ”µ P1 | `execution_engine/router.py:42-67` | 1-2j | ✅ | 2026-03-20 |
| R-04 | Ajouter Protocols typing | ðŸ”µ P2 | `execution/base.py` + 3 modules | 1j | ✅ | 2026-03-20 |

