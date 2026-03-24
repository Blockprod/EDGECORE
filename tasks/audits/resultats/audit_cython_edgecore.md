---
type: audit
dimension: Cython
projet: EDGECORE_V1
date: 2026-03-21
creation: 2026-03-21 à 23:56
modele: Claude Sonnet 4.6
statut: complet
---

# Audit Cython — EDGECORE
**Date** : 2026-03-21  
**Périmètre** : `models/cointegration_fast.pyx` · `models/cointegration.py` (façade) · `setup.py` · `tests/models/056_test_cython_module.py` · consommateurs

---

## BLOC 1 — INVENTAIRE DU MODULE CYTHON

### Artefacts présents

| Artefact | Présent |
|----------|---------|
| `models/cointegration_fast.pyx` | ✅ |
| `models/cointegration_fast.cp311-win_amd64.pyd` | ✅ |
| `models/cointegration_fast.cp313-win_amd64.pyd` | ✅ |
| `models/cointegration_fast.c` (transpilation) | ✅ commité (⚠️ voir CY-01) |
| `.so` (Linux) | ❌ — normal en environnement Windows |

### Fonctions publiques exportées

| Fonction | Dans .pyx | Signature annotée | Docstring |
|----------|-----------|-------------------|-----------|
| `engle_granger_fast` | ✅ | ✅ `(y, x: np.ndarray[float64, ndim=1]) -> dict` | ✅ |
| `half_life_fast` | ✅ | ✅ `(spread: np.ndarray[float64, ndim=1]) -> int` | ✅ |
| `brownian_bridge_batch_fast` | ✅ | ✅ `(closes: ndim=2, noise: ndim=3, bars_per_day: int) -> np.ndarray` | ✅ (paramètres détaillés) |
| `compute_zscore_last_fast` | ✅ | ✅ `(spread: np.ndarray[float64, ndim=1], lookback: int) -> double` | ✅ |

---

## BLOC 2 — COHÉRENCE DES INTERFACES

### `engle_granger_fast`
- **Signature .pyx** : `(y, x: np.ndarray[float64, ndim=1]) -> dict`
- **Consommateur `models/cointegration.py:210`** : `_engle_granger_fast(y.values.astype(np.float64), x.values.astype(np.float64))` → **CONFORME**
- **Clés attendues** : `beta, intercept, residuals, adf_statistic, adf_pvalue, is_cointegrated, critical_values, error`
- **Observation** : les branches early-return (`n < 20`, NaN, zero variance) retournent des dicts **sans la clé `adf_statistic`**. Le consommateur vérifie `cy_result.get("error")` avant toute lecture → **pas de KeyError en pratique** mais l'interface est incohérente.
- **Documentation** : `agents/dev_engineer.md:49` documente `engle_granger_test_fast` — **cette fonction n'existe pas** dans le .pyx. Nom réel : `engle_granger_fast`. → voir CY-05.

### `half_life_fast`
- **Signature .pyx** : `(spread: np.ndarray[float64, ndim=1]) -> int`, retourne -1 si invalide
- **Consommateur `models/spread.py:10`** : `from models.cointegration_fast import half_life_fast as _half_life_fast_cython` → **CONFORME**
- Retour -1 géré en aval ✅

### `brownian_bridge_batch_fast`
- **Signature .pyx** : `(closes: ndim=2, noise: ndim=3, bars_per_day: int) -> np.ndarray`
- **Dimensions attendues** : closes `(n_days, n_sym)`, noise `(n_days-1, bars_per_day, n_sym)`, out `(n_days-1)*bars_per_day × n_sym`
- **Consommateur `data/intraday_loader.py:250`** : passage correct (`mat_vals`, `noise`, `bars_per_day`) → **CONFORME**
- **Ajout** : import **direct** depuis le .pyx, hors façade — voir CY-09.

### `compute_zscore_last_fast`
- **Signature .pyx** : `(spread: ndim=1, lookback: int) -> double`, retourne 0.0 si insuffisant, clampé [-6, 6]
- **Consommateurs `backtests/strategy_simulator.py:460,968`** : `_compute_zscore_last_fast(_sp_v, min(60, len(_sp_v)))` avec guard `if _compute_zscore_last_fast is None:` → **CONFORME**

---

## BLOC 3 — FALLBACK PYTHON ET FLAG CYTHON

| Vérification | Résultat |
|---|---|
| `CYTHON_COINTEGRATION_AVAILABLE` utilisé avant appel Cython dans `models/cointegration.py` | ✅ (`cointegration.py:210`) |
| Bloc `try/except ImportError` couvre les 4 fonctions | ✅ — tout dans un seul bloc |
| Import lazy `backtests/strategy_simulator.py` avec fallback | ✅ — `_compute_zscore_last_fast = None` + guard explicite |
| Import lazy `data/intraday_loader.py` avec fallback | ✅ — `_cython_bb = False` + branche Python pure |
| Log warning cite la commande de recompilation | ✅ — dans les 3 modules (`models/spread.py`, `backtests/strategy_simulator.py`, `models/cointegration.py`) |
| `CPP_COINTEGRATION_AVAILABLE` — alias legacy mort | ⚠️ Déclaré `models/cointegration.py:36`, aucun consommateur Python de prod → **dead code** — voir CY-07 |
| Aliases `_brownian_bridge_batch_fast`, `_compute_zscore_last_fast`, `_half_life_fast` dans la façade | ⚠️ Importés avec `# noqa: F401` mais **jamais utilisés** dans `models/cointegration.py` — voir CY-08 |

---

## BLOC 4 — BUILD ET REPRODUCTIBILITÉ

### `setup.py`

| Vérification | Résultat |
|---|---|
| Extension `models.cointegration_fast` correctement déclarée | ✅ (sources, include_dirs, language='c') |
| `language_level='3'` dans `cythonize()` | ✅ — ET directive `# cython: language_level=3` en tête du .pyx |
| `boundscheck=False` | ✅ — dans `cythonize()` ET décorateurs `@cython.boundscheck(False)` |
| `wraparound=False` | ✅ |
| `cdivision=True` | ✅ |
| `nonecheck=False` | ✅ |
| `extra_compile_args`: `/O2` Windows, `-O2` Linux | ✅ |
| `annotate` non défini | ✅ — aucun `.html` généré ni présent dans `models/` |

### Gestion des versions Cython

| Vérification | Résultat |
|---|---|
| Cython dans `requirements.txt` | ❌ **ABSENT** |
| Cython dans `pyproject.toml` | ❌ **ABSENT** |
| Déclaration dans `setup.py` | ⚠️ `Cython>=0.29` — Cython 3.2.4 installé — déclaration trop permissive → voir CY-06 |

### Artefacts dans `.gitignore`

| Artefact | En `.gitignore` |
|----------|----------------|
| `*.pyd` | ✅ (ligne 61) |
| `build/` | ✅ (lignes 60, 95) |
| `*.so` | ✅ (ligne 65) |
| `*.c` (transpilation Cython) | ❌ — `models/cointegration_fast.c` commité dans le repo → voir CY-01 |
| `.html` (`annotate`) | ✅ (indirect — non générés) |

### CI/CD

| Vérification | Résultat |
|---|---|
| Build Cython AVANT les tests | ✅ — `.github/workflows/ci.yml:49-52` (`pip install cython numpy` + `python setup.py build_ext --inplace`) |
| Cython pinné dans le step CI | ⚠️ `pip install cython numpy` sans version — risque de Cython incompatible en CI |

---

## BLOC 5 — COUVERTURE DES TESTS CYTHON

**Fichier principal** : `tests/models/056_test_cython_module.py`

### Couverture par fonction

| Fonction | Testée | Cas nominaux | Cas limites |
|----------|--------|--------------|-------------|
| `engle_granger_fast` | ✅ | ✅ (cointegrated + non-cointegrated) | ❌ (n<20, NaN, zero variance non testés) |
| `half_life_fast` | ✅ | ✅ (AR(1) avec rho=0.95, hl dans [5,25]) | ❌ (n<3 → -1 non testé) |
| `brownian_bridge_batch_fast` | ❌ | ❌ aucun test direct | ❌ |
| `compute_zscore_last_fast` | ❌ | ❌ aucun test direct | ❌ (lookback>n, clamping [-6,6] non testés) |

### Autres vérifications

| Point | Résultat |
|---|---|
| Test que le .pyd est compilé (glob pyd/so) | ✅ (`056_test_cython_module.py:37-38`) |
| Skip gracieux si ImportError | ✅ (`pytest.skip`) |
| Comparaison Cython vs Python | ✅ (`test_cython_result_consistency`) — mais uniquement pour `engle_granger_fast` |
| Benchmark de performance (speedup) | ✅ (`test_cython_faster_than_pure_python`) — seuil bas : `speedup > 0.5` |

**Fonctions sans aucun test direct** : `brownian_bridge_batch_fast` et `compute_zscore_last_fast` — voir CY-02 et CY-03.

---

## BLOC 6 — USAGES SUSPECTS

### Imports directs court-circuitant la façade

| Fichier | Fonction | Via façade | Fallback |
|---------|----------|-----------|---------|
| `models/cointegration.py` | `_engle_granger_fast` | ✅ (IS la façade) | ✅ |
| `models/spread.py:10` | `half_life_fast` | ❌ direct | ✅ try/except |
| `data/intraday_loader.py:250` | `brownian_bridge_batch_fast` | ❌ direct | ✅ try/except local |
| `backtests/strategy_simulator.py:53` | `compute_zscore_last_fast` | ❌ direct | ✅ `= None` + guard |

**Observation** : `models/spread.py` et `backtests/strategy_simulator.py` court-circuitent la façade mais ont chacun un fallback correct. Le risque principal est la duplication des messages de log.

### Documentation erronée

- `agents/dev_engineer.md:49` : `from models.cointegration_fast import engle_granger_test_fast` → **cette fonction n'existe pas**. Nom correct : `engle_granger_fast`. → CY-05

### Scripts dépendant du .pyd sans CI guard

- `scripts/benchmark_cython_acceleration.py` importe `engle_granger_test` et `CYTHON_COINTEGRATION_AVAILABLE` depuis la façade → **OK** (passe par la façade, fallback gracieux)
- `research/` : aucun usage direct de `cointegration_fast` ✅

---

## SYNTHÈSE

| ID | Bloc | Description | Fichier:Ligne | Sévérité | Impact | Effort |
|----|------|-------------|---------------|----------|--------|--------|
| CY-01 | B4 | `cointegration_fast.c` commité dans le repo sans être dans `.gitignore` | `models/cointegration_fast.c`, `.gitignore` | 🟡 Mineur | Pollue l'historique git; ~170 Ko ; peut masquer divergences de transpilation | 5 min |
| CY-02 | B5 | `brownian_bridge_batch_fast` — aucun test unitaire direct | `tests/models/` | 🟠 Majeur | Régression silencieuse possible sur génération intraday synthétique | 1-2 h |
| CY-03 | B5 | `compute_zscore_last_fast` — aucun test unitaire direct | `tests/models/` | 🟠 Majeur | Régression silencieuse dans la boucle de backtest (hot path) | 1-2 h |
| CY-04 | B5 | Cas limites non couverts : `n<20`, NaN, `n<3 → -1`, `lookback>n → 0.0`, clamping `[-6,6]` | `tests/models/056_test_cython_module.py` | 🟡 Mineur | Confiance incomplète sur les cas dégénérés | 1 h |
| CY-05 | B6 | `agents/dev_engineer.md:49` référence `engle_granger_test_fast` — fonction inexistante dans le .pyx | `agents/dev_engineer.md:49` | 🟡 Mineur | Documentation trompeuse — provoquerait `ImportError` au développeur | 5 min |
| CY-06 | B4 | Cython absent de `requirements.txt` et `pyproject.toml`; `setup.py` déclare `Cython>=0.29` trop permissif (`3.2.4` installé) | `setup.py:47`, `requirements.txt`, `pyproject.toml` | 🟠 Majeur | Install fresh peut résoudre Cython 0.x incompatible avec directives `language_level=3` | 10 min |
| CY-07 | B3 | `CPP_COINTEGRATION_AVAILABLE` alias legacy — dead code, aucun consommateur Python de prod | `models/cointegration.py:36` | 🟡 Mineur | Confusion héritage C++, trompeur | 5 min |
| CY-08 | B3 | `_brownian_bridge_batch_fast`, `_compute_zscore_last_fast`, `_half_life_fast` importés dans la façade avec `# noqa: F401` mais jamais utilisés dans ce fichier | `models/cointegration.py:13–22` | 🟡 Mineur | Imports trompeurs; les consommateurs importent directement | 10 min |
| CY-09 | B6 | `data/intraday_loader.py` importe `brownian_bridge_batch_fast` sans passer par la façade `models/cointegration.py` | `data/intraday_loader.py:250` | 🟡 Mineur | Court-circuite la façade; fallback local présent; risque faible | 15 min |

**Bilan** : 🔴 0 · 🟠 3 (CY-02, CY-03, CY-06) · 🟡 6 (CY-01, CY-04, CY-05, CY-07, CY-08, CY-09)

---

## Points positifs notables

- Architecture `.pyx` + façade `cointegration.py` + fallback Python pur dans chaque consommateur : pattern solide.
- Directives de compilation optimales (`boundscheck=False`, `wraparound=False`, `cdivision=True`, `nonecheck=False`, `language_level=3`) — en doublon header + `cythonize()`, ce qui est la bonne pratique.
- Build Cython intégré en CI avant les tests ✅.
- Les deux `.pyd` (cp311 + cp313) sont présents pour Python 3.11 et 3.13.
- La recompilation obligatoire est systématiquement rappelée dans les logs warning.

---

*Recompilation obligatoire après toute modification du .pyx :*
```powershell
venv\Scripts\python.exe setup.py build_ext --inplace
```
