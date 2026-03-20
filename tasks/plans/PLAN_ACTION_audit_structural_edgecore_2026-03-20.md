---
projet: EDGECORE
type: plan-action
source: tasks/audits/audit_structural_edgecore.md
date: 2026-03-20
modele: claude-sonnet-4.6
---

# PLAN D'ACTION — EDGECORE — 2026-03-20
Sources : `tasks/audits/audit_structural_edgecore.md`
Total : 🔴 2 · 🟠 7 · 🟡 5 · 🔵 4 · Effort estimé : 12–18 jours

---

## PHASE 1 — CRITIQUES 🔴

---

### [C-01] Supprimer le double ThreadPoolExecutor dans bulk_load

Fichier : `data/loader.py:366-400`

Problème : `bulk_load()` contient deux blocs `with ThreadPoolExecutor(...)` identiques.
Le premier appelle les workers IBKR mais ne persiste pas les résultats dans `results`
(`completed = 0` reset, boucle rejouée entièrement). Chaque appel déclenche **2×
les appels IBKR** pour tous les symboles non cachés — double consommation du rate
limit (45 req/s), temps d'exécution doublé, risque de déconnexion TWS.

Correction :
  1. Lire `data/loader.py` autour de la ligne 366.
  2. Supprimer le PREMIER bloc `with ThreadPoolExecutor(...)` et son
     `completed = 0` associé (lignes ~366–376). Ne conserver que le SECOND
     bloc (lignes ~377+) qui peuple réellement `results`.
  3. Vérifier que `symbol_chunks` est défini avant le bloc conservé.
  4. Supprimer le commentaire orphelin `# ...existing code...` à l'intérieur
     du premier bloc.

Validation :
  ```powershell
  venv\Scripts\python.exe -m pytest tests/ -x -q -k "bulk_load or loader"
  # Attendu : tests passe, aucune deuxieme connexion IBKR en mock
  venv\Scripts\python.exe -m pytest tests/ -x -q
  # Attendu : 2654+ passed, 0 failed
  ```

Dépend de : Aucune
Statut : ⏳

---

### [C-02] Supprimer l'écriture debug en production dans bulk_load

Fichier : `data/loader.py:282-288`

Problème : Bloc `try: with open("debug_bulk_to_fetch_snapshot.txt", "w"...)` écrit
un fichier de debug à chaque appel `bulk_load()`. L'écriture est relative au cwd —
peut atterrir n'importe où en production. Fuite d'information, I/O inutile.

Correction :
  1. Supprimer le bloc `try: with open("debug_bulk_to_fetch_snapshot.txt" ...)
     ... except Exception: pass` dans son intégralité (lignes ~282-288).
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

Dépend de : Aucune
Statut : ⏳

---

## PHASE 2 — MAJEURES 🟠

---

### [C-03] Corriger OrderStatus dans execution/modes.py — importer depuis base.py

Fichier : `execution/modes.py:30-40`

Problème : `OrderStatus` est redéfini localement avec 6 états (PENDING, SUBMITTED,
FILLED, PARTIALLY_FILLED, CANCELLED, FAILED) vs 11 dans `execution/base.py`
(+ PARTIAL, TIMEOUT, ERROR, UNKNOWN, REJECTED). Le commentaire docstring dit
"delegates to execution.base.OrderStatus values" mais ce n'est pas le cas — valeurs
redéfinies inline. Les états TIMEOUT/ERROR/UNKNOWN manquants causent des bugs
silencieux quand un ordre atteint un état non géré.

Correction :
  1. Supprimer la classe `OrderStatus` dans `execution/modes.py` (lignes 30-40).
  2. Ajouter en tête du fichier : `from execution.base import OrderStatus`
  3. Vérifier que toutes les références dans `execution/modes.py` à
     `OrderStatus.PENDING`, `.FILLED`, etc. restent valides avec les 11 états.
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

Dépend de : Aucune
Statut : ⏳

---

### [C-04] Unifier slippage backtest vs paper — lire CostConfig uniformément

Fichier : `execution_engine/router.py:211`

Problème : Le path paper lit `get_settings().execution.slippage_bps` (2.0 bps)
alors que le path backtest lit `get_settings().costs.slippage_bps` (3.0 bps).
Un backtest calibré sur 3.0 bps trade en paper à 2.0 bps → résultats de paper
systématiquement optimistes vs backtest. Rend la comparaison backtest/live invalide.

Correction :
  1. Lire `execution_engine/router.py` lignes ~200-230 (méthode `_paper_fill`).
  2. Remplacer `slippage = get_settings().execution.slippage_bps` (ligne ~211)
     par `slippage = get_settings().costs.slippage_bps`.
  3. Vérifier que `CostConfig.slippage_bps` est bien présent dans `dev.yaml`,
     `test.yaml`, `prod.yaml` (ou qu'un défaut raisonnable est défini dans
     la dataclass `CostConfig`).
  4. Dans `config/settings.py`, supprimer ou déprécier `ExecutionConfig.slippage_bps`
     si sa seule utilisation était ce path paper (vérifier par grep).

Validation :
  ```powershell
  grep -n "execution.slippage_bps" execution_engine/router.py
  # Attendu : 0 resultats
  grep -n "costs.slippage_bps" execution_engine/router.py
  # Attendu : 2 resultats (backtest + paper)
  venv\Scripts\python.exe -m pytest tests/ -x -q
  # Attendu : 2654+ passed, 0 failed
  ```

Dépend de : Aucune
Statut : ⏳

---

### [C-05] Corriger exit_z_score dans test.yaml (0.0 → 0.5)

Fichier : `config/test.yaml:13`

Problème : `exit_z_score: 0.0` — un spread ne touche jamais exactement 0.0 en
arithmétique flottante. Les tests de stratégie qui utilisent cette config ne
couvrent jamais les sorties de position → biais systématique des tests.

Correction :
  1. Modifier `config/test.yaml` ligne 13 : `exit_z_score: 0.0` → `exit_z_score: 0.5`
  2. Vérifier la cohérence avec `entry_z_score` dans le même fichier
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

Dépend de : Aucune
Statut : ⏳

---

### [C-06] Nettoyer edgecore/ — supprimer artefacts C++ Python 3.13

Fichier : `edgecore/` (dossier entier)

Problème : Le dossier `edgecore/` contient :
  - `backtest_engine_cpp.cp313-win_amd64.pyd` : extension C++ compilée pour Python 3.13
    (projet cible 3.11). Non chargeable, présence confuse.
  - `cointegration_cpp.cp313-win_amd64.pyd` : idem.
  - `backtest_engine_wrapper.py` (134 lignes) : passthrough Python pur vers
    `backtests/strategy_simulator.py` — doublon fonctionnel.
  - `cointegration_engine_wrapper.py` : passthrough vers `models/cointegration.py`.

Correction :
  1. Vérifier qu'aucun fichier de production n'importe depuis `edgecore/` :
     `grep -r "from edgecore" --include="*.py" . | grep -v test | grep -v __pycache__`
  2. Si aucun import en prod → déplacer `edgecore/backtest_engine_wrapper.py`
     et `edgecore/cointegration_engine_wrapper.py` dans `docs/archived/edgecore/`.
  3. Supprimer `edgecore/backtest_engine_cpp.cp313-win_amd64.pyd` et
     `edgecore/cointegration_cpp.cp313-win_amd64.pyd` (non utilisables en 3.11).
  4. Si `edgecore/__init__.py` n'expose rien de nécessaire, le vider.
  5. Ajouter `edgecore/` dans `.gitignore` s'il ne reste que des .pyd résiduels.

Validation :
  ```powershell
  Get-ChildItem edgecore/ -Filter "*.pyd"
  # Attendu : uniquement les .cp311-win_amd64.pyd (s'il en reste)
  venv\Scripts\python.exe -m pytest tests/ -x -q
  # Attendu : 2654+ passed, 0 failed
  ```

Dépend de : Aucune
Statut : ⏳

---

### [C-07] Fixer divergence drawdown — LiveTradingRunner utilise RiskFacade comme seule source de vérité

Fichier : `live_trading/runner.py:227-237`

Problème : `_initialize()` crée `PositionRiskManager`, `PortfolioRiskManager`,
`KillSwitch` ET `RiskFacade`. Le `KillSwitch` est partagé (B2-02 partiellement
corrigé), mais `RiskFacade` contient un `RiskEngine` interne qui monitore
**aussi** le drawdown — indépendamment de `PortfolioRiskManager`. Deux compteurs
de drawdown peuvent diverger, causant un état incohérent (l'un dit OK, l'autre dit halt).

Correction :
  Approche minimale (sans refactoring massif) :
  1. Lire `live_trading/runner.py` méthodes `_initialize()` et `_tick()`.
  2. Identifier où `self._portfolio_risk.check(...)` et `self._risk_facade.can_enter_trade(...)`
     sont appelés dans `_tick()`.
  3. Dans `_tick()`, **ne plus appeler `self._portfolio_risk.check()`** si
     `self._risk_facade.can_enter_trade()` effectue déjà le même check drawdown.
  4. Conserver `self._portfolio_risk` uniquement pour les fonctions que `RiskFacade`
     ne couvre pas (ex: heat mapping, position monitoring par paire).
  5. Documenter clairement quelles vérifications sont déléguées à la façade vs
     celles qui restent dans `PortfolioRiskManager`.
  Alternative : Si l'analyse montre que `PortfolioRiskManager` est redondant avec
  `RiskEngine` (dans RiskFacade) pour les checks de drawdown → supprimer l'instanciation
  de `self._portfolio_risk` et déléguer à `self._risk_facade` uniquement.

Validation :
  ```powershell
  venv\Scripts\python.exe -m pytest tests/ -x -q -k "risk or runner or facade"
  # Attendu : tous les tests risk passent
  venv\Scripts\python.exe -m pytest tests/ -x -q
  # Attendu : 2654+ passed, 0 failed
  ```

Dépend de : Aucune (mais analyser avant d'éditer — ce ticket nécessite une lecture
             approfondie de _tick() avant toute modification)
Statut : ⏳

---

### [C-08] Corriger commission hardcodée dans router.py — lire depuis CostConfig

Fichier : `execution_engine/router.py:192,226`

Problème : `commission=order.quantity * price * 0.00005` (~0.5 bps) hardcodé aux
lignes 192 et 226. La commission n'est pas configurable et diverge de `CostConfig`.

Correction :
  1. Lire `execution_engine/router.py` lignes 180-230.
  2. Dans `_simulate_fill` et `_paper_fill`, remplacer la commission hardcodée par :
     `commission=order.quantity * price * (get_settings().costs.commission_bps / 10_000)`
  3. Vérifier que `CostConfig` a un champ `commission_bps` dans `config/settings.py`.
     Si absent → ajouter `commission_bps: float = 5.0` dans `CostConfig` (dataclass).
  4. Mettre à jour `dev.yaml`, `test.yaml`, `prod.yaml` si nécessaire.

Validation :
  ```powershell
  grep -n "0.00005" execution_engine/router.py
  # Attendu : 0 resultats
  grep -n "commission_bps" execution_engine/router.py
  # Attendu : 2 resultats
  venv\Scripts\python.exe -m pytest tests/ -x -q
  # Attendu : 2654+ passed, 0 failed
  ```

Dépend de : [C-04] (même fichier — appliquer après C-04)
Statut : ⏳

---

### [C-09] Supprimer execution/modes.py — architecture parallèle non utilisée

Fichier : `execution/modes.py:1-868`

Problème : `execution/modes.py` (868 lignes) est une architecture parallèle complète
(Order, OrderStatus, 3 ExecutionMode, ExecutionEngine) qui n'est pas utilisée par
le pipeline principal. Elle redéfinit `Order` et `OrderStatus` (déjà adressé par C-03),
et contient une classe `ExecutionEngine` (ligne 817) de ~50 méthodes orphelines.

Correction :
  1. Grep pour confirmer les imports : `grep -r "from execution.modes import" --include="*.py" .`
  2. Si le fichier n'est importé que par des tests ou des modules non-production :
     - Déplacer `execution/modes.py` vers `docs/archived/execution_modes_legacy.py`
     - Mettre à jour les tests concernés pour utiliser `execution/base.py`
  3. Si des callers valides existent : extraire uniquement la classe finale nécessaire
     et supprimer le reste.
  4. Vérifier que `ExecutionMode` (enum PAPER/LIVE/BACKTEST) n'est pas défini
     uniquement ici — le déplacer dans `execution/base.py` si c'est le cas.

Validation :
  ```powershell
  grep -r "from execution.modes" --include="*.py" . | Where-Object { $_ -notmatch "__pycache__" }
  # Attendu : 0 resultats (ou seulement des tests mis a jour)
  venv\Scripts\python.exe -m pytest tests/ -x -q
  # Attendu : 2654+ passed, 0 failed
  ```

Dépend de : [C-03] (OrderStatus unifié en premier)
Statut : ⏳

---

## PHASE 3 — MINEURES 🟡

---

### [C-10] Synchroniser versions setup.py et pyproject.toml

Fichier : `setup.py:30`, `pyproject.toml:7`

Problème : `setup.py` déclare `version='0.1.0'`, `pyproject.toml` déclare
`version = "1.0.0"`. Deux sources de vérité incohérentes.

Correction :
  1. Décider de la version canonique (probablement `1.0.0` de `pyproject.toml`).
  2. Modifier `setup.py:30` : `version='0.1.0'` → `version='1.0.0'`.
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

Dépend de : Aucune
Statut : ⏳

---

### [C-11] Corriger test.yaml — ajouter section costs avec slippage_bps

Fichier : `config/test.yaml`

Problème : `test.yaml` ne contient pas de section `costs`. Les tests utilisent
les défauts Python de `CostConfig` (~3.0 bps de slippage) — valeurs non maîtrisées
et potentiellement différentes des autres environnements. Après [C-04], la section
`costs` est lue dans tous les paths → son absence en test provoquerait des défauts
silencieux.

Correction :
  1. Lire `config/test.yaml` et `config/dev.yaml` pour comparer les sections.
  2. Ajouter dans `config/test.yaml` une section `costs` :
     ```yaml
     costs:
       slippage_bps: 3.0
       commission_bps: 5.0
     ```
  3. Vérifier que les défauts dataclass `CostConfig` correspondent à ces valeurs
     (pour éviter de casser les tests qui mockent la config).

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

Dépend de : [C-04], [C-05]
Statut : ⏳

---

### [C-12] Supprimer les 4 schemas Pydantic inutilisés dans config/schemas.py

Fichier : `config/schemas.py:170-508`

Problème : `config/schemas.py` définit 6 schemas Pydantic mais `Settings._validate_config()`
n'en utilise que 2 (`RiskConfigSchema`, `StrategyConfigSchema`). Les 4 autres
(`ExecutionConfigSchema`, `DataSourceConfigSchema`, `AlerterConfigSchema`,
`BacktestConfigSchema`) sont du code mort. Ils créent une fausse sécurité
(on pense que la config est validée, mais elle ne l'est pas).

Correction :
  1. Lire `config/settings.py:265-290` (`_validate_config()`).
  2. Option A (minimal) : Appliquer les 4 schemas manquants dans `_validate_config()`.
  3. Option B (nettoyage) : Supprimer les 4 schemas non utilisés de `schemas.py`
     et documenter que seuls `RiskConfigSchema` et `StrategyConfigSchema` sont
     la stratégie de validation retenue.
  4. Recommandé : Option A — étendre la couverture de validation (retour sur
     l'investissement immédiat en qualité).

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

Dépend de : Aucune
Statut : ⏳

---

### [C-13] Nettoyer les artefacts de debug à la racine et dans data/

Fichiers : `ibkr_invalid_symbols.txt`, `data/kill_switch_state.bak`, `scripts/ARCHIVED_*.py`

Problème :
  - `ibkr_invalid_symbols.txt` (racine) : artefact manuel non référencé dans le code.
  - `data/kill_switch_state.bak` : état persisté du KillSwitch dans `data/` au lieu
    de `persistence/` — incohérence architecturale.
  - `scripts/ARCHIVED_benchmark_cpp_acceleration.py`,
    `scripts/ARCHIVED_setup_cpp_acceleration.py` : présents dans scripts/ actif,
    source de confusion si exécutés.

Correction :
  1. Déplacer `ibkr_invalid_symbols.txt` → `data/audit/ibkr_invalid_symbols.txt`
     ET l'ajouter à `.gitignore` (artefact généré).
  2. Déplacer `data/kill_switch_state.bak` → `persistence/kill_switch_state.bak`
     ET mettre à jour le chemin dans `risk_engine/kill_switch.py` (grep le chemin hardcodé).
  3. Déplacer `scripts/ARCHIVED_*.py` → `docs/archived/scripts/` OU les supprimer
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

Dépend de : Aucune
Statut : ⏳

---

### [C-14] Documenter architecture backtests/ vs backtester/ dans les docstrings

Fichier : `backtester/runner.py:1`, `backtester/walk_forward.py:1`, `backtests/runner.py:1`

Problème : L'architecture deux-couches (backtests/ = implémentations, backtester/ = façades)
est intentionnelle mais non documentée. De nouveaux développeurs importent directement
`backtests/runner.py` contournant la façade typée. Pas de guideline sur quand utiliser
chaque couche.

Correction :
  1. Ajouter/mettre à jour le module docstring de `backtester/runner.py` :
     ```python
     """
     Haute-level facade over backtests.runner.BacktestRunner.
     Callers SHOULD import from backtester/, not backtests/ directly.
     backtests/ contains raw implementations; backtester/ exposes typed API.
     """
     ```
  2. Idem pour `backtester/walk_forward.py` et `backtester/oos.py`.
  3. Ajouter un commentaire dans `backtests/runner.py` : "Internal — use backtester.runner.BacktestEngine for external callers."
  4. Grep pour imports directs de `backtests.runner` dans des modules non-backtests/
     et les router vers `backtester.runner`.

Validation :
  ```powershell
  venv\Scripts\python.exe -m pytest tests/ -x -q
  # Attendu : 2654+ passed, 0 failed
  ```

Dépend de : Aucune
Statut : ⏳

---

## PHASE 4 — REFACTORING MAJEUR 🔵 (post-corrections critiques)

Ces items sont des restructurations profondes. À planifier séparément après
validation complète des phases 1–3.

---

### [R-01] Décomposer backtests/strategy_simulator.py (1 609 lignes)

Fichier : `backtests/strategy_simulator.py:1-1609`
Effort : 3–5 jours

Le God class mélange loop de simulation, risk inline, cost model, pair discovery
et métriques. Décomposer en :
- `backtests/simulation_loop.py` (moteur bar-par-bar)
- `backtests/order_book.py` (gestion des ordres simulés)
- Déléguer risk checks à `risk/facade.py::RiskFacade`
- Déléguer cost model à `backtests/cost_model.py::CostModel` (déjà présent)
- Déléguer pair discovery à `pair_selection/discovery.py`

Dépend de : [C-07] (RiskFacade unifié), toutes les phases 1–3
Statut : ⏳

---

### [R-02] Décomposer strategies/pair_trading.py (1 102 lignes)

Fichier : `strategies/pair_trading.py:1-1102`
Effort : 2–4 jours

Extraire vers les modules existants :
- `is_cointegration_stable()` → `models/cointegration.py`
- Gestion `active_trades` → classe dédiée `strategies/trade_book.py`
- Regime detection → déléguer à `models/regime_detector.py::RegimeDetector`
- Tout signal → déléguer à `signal_engine/generator.py::SignalGenerator`

Dépend de : [R-01], [C-03]
Statut : ⏳

---

### [R-03] Éliminer TradeOrder dans execution_engine/router.py — migrer vers Order

Fichier : `execution_engine/router.py:42-67`
Effort : 1–2 jours

`TradeOrder` est marqué `@deprecated (B2-01)` mais les callers internes utilisent
encore ce type. Migrer toutes les créations de `TradeOrder` vers `execution.base.Order`.
Supprimer ensuite la classe `TradeOrder`.

Dépend de : [C-03], [C-09]
Statut : ⏳

---

### [R-04] Ajouter key Protocols (typing.Protocol) pour SignalGenerator, Allocator, Loader

Fichier : `execution/base.py`, `signal_engine/`, `portfolio_engine/`, `data/`
Effort : 1 jour

Introduire des `Protocol` pour les trois interfaces non formalisées afin de
découpler les dépendances et faciliter le testing par injection.

Dépend de : [R-01], [R-02]
Statut : ⏳

---

## SÉQUENCE D'EXÉCUTION

```
[C-01] → [C-02]                     (P0 indépendants, priorité absolue)
          ↓
[C-03] → [C-09]                     (OrderStatus unifié avant suppression modes.py)
[C-04] → [C-08] → [C-11]           (slippage unifié avant commission, puis test.yaml)
[C-05]                               (indépendant — modifier test.yaml exit_z_score)
[C-06]                               (indépendant — nettoyer edgecore/)
[C-07]                               (analyser _tick() avant toute modification)
[C-10]                               (indépendant — versions)
[C-12]                               (indépendant — schemas Pydantic)
[C-13]                               (indépendant — artefacts)
[C-14]                               (indépendant — documentation)
          ↓
[R-01] → [R-02] → [R-03] → [R-04]  (refactoring séquentiel — après toutes corrections)
```

---

## CRITÈRES PASSAGE EN PRODUCTION

- [ ] Zéro 🔴 ouvert (C-01 et C-02 résolus et testés)
- [ ] `pytest tests/ -q` : 2654+ passed, 0 failed
- [ ] `pytest tests/ -W error::DeprecationWarning -q` : 0 DeprecationWarning
- [ ] `mypy risk/ risk_engine/ execution/ --ignore-missing-imports --no-error-summary` : exit 0
- [ ] `ruff check .` : 0 erreurs
- [ ] `Test-Path "debug_bulk_to_fetch_snapshot.txt"` : False (pas de fichier debug en prod)
- [ ] `grep -n "class OrderStatus" execution/modes.py` : 0 résultats
- [ ] `grep -n "execution.slippage_bps" execution_engine/router.py` : 0 résultats
- [ ] Risk tiers cohérents : `venv\Scripts\python.exe -c "from config.settings import get_settings; get_settings()._assert_risk_tier_coherence(); print('OK')"`
- [ ] `EDGECORE_ENV=prod` dans Dockerfile (déjà corrigé — maintenir)
- [ ] Kill-switch persisté au redémarrage (vérifier chemin .bak après C-13)
- [ ] Paper trading validé sur 48h avant passage live

---

## TABLEAU DE SUIVI

| ID | Titre | Sévérité | Fichier | Effort | Statut | Date |
|----|-------|----------|---------|--------|--------|------|
| C-01 | Supprimer double ThreadPoolExecutor | 🔴 P0 | `data/loader.py:366-400` | 1h | ⏳ | — |
| C-02 | Supprimer écriture debug en prod | 🔴 P0 | `data/loader.py:282-288` | 30min | ⏳ | — |
| C-03 | OrderStatus importer depuis base.py | 🟠 P1 | `execution/modes.py:30-40` | 1h | ⏳ | — |
| C-04 | Unifier slippage backtest=paper | 🟠 P1 | `execution_engine/router.py:211` | 1h | ⏳ | — |
| C-05 | exit_z_score: 0.0 → 0.5 dans test.yaml | 🟠 P1 | `config/test.yaml:13` | 15min | ⏳ | — |
| C-06 | Nettoyer edgecore/ artefacts C++ | 🟠 P1 | `edgecore/` | 2h | ⏳ | — |
| C-07 | Unifier drawdown via RiskFacade seule | 🟠 P1 | `live_trading/runner.py:227-237` | 4h | ⏳ | — |
| C-08 | Commission hardcodée → CostConfig | 🟠 P1 | `execution_engine/router.py:192,226` | 1h | ⏳ | — |
| C-09 | Supprimer execution/modes.py | 🟠 P1 | `execution/modes.py:1-868` | 4h | ⏳ | — |
| C-10 | Synchroniser versions setup.py/pyproject.toml | 🟡 P2 | `setup.py:30` | 15min | ⏳ | — |
| C-11 | Ajouter section costs dans test.yaml | 🟡 P2 | `config/test.yaml` | 30min | ⏳ | — |
| C-12 | Activer/supprimer schemas Pydantic inutilisés | 🟡 P2 | `config/schemas.py:170-508` | 3h | ⏳ | — |
| C-13 | Nettoyer artefacts racine et data/ | 🟡 P2 | plusieurs | 1h | ⏳ | — |
| C-14 | Documenter architecture backtests/ vs backtester/ | 🟡 P2 | `backtester/*.py` | 1h | ⏳ | — |
| R-01 | Décomposer strategy_simulator.py | 🔵 P1 | `backtests/strategy_simulator.py` | À ESTIMER (3-5j) | ⏳ | — |
| R-02 | Décomposer pair_trading.py | 🔵 P1 | `strategies/pair_trading.py` | À ESTIMER (2-4j) | ⏳ | — |
| R-03 | Éliminer TradeOrder | 🔵 P1 | `execution_engine/router.py:42-67` | 1-2j | ⏳ | — |
| R-04 | Ajouter Protocols typing | 🔵 P2 | `execution/base.py` + 3 modules | 1j | ⏳ | — |
