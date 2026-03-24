---
modele: claude-sonnet-4.6
mode: agent
contexte: codebase
produit: corrections appliquées · ruff OK · Pylance OK · 2787 tests pass
derniere_revision: 2026-03-23
creation: 2026-03-21 à 14:12
---

#codebase

Je suis le chef de projet EDGECORE.

─────────────────────────────────────────────
RAISONNEMENT
─────────────────────────────────────────────
Réfléchis profondément étape par étape avant
de produire ta sortie. Explore d'abord, planifie
ensuite, puis exécute.

─────────────────────────────────────────────
OBJECTIF PRINCIPAL
─────────────────────────────────────────────
Corriger **tous les fichiers Python** du projet
(chaque dossier et sous-dossier) pour que :

1. Zéro erreur ruff (y compris paramètres orphelins ARG)
2. Zéro erreur Pylance / Pyright
3. Tous les fichiers Python qui appellent le module Cython
   (`models/cointegration_fast.pyx`) sont parfaitement
   alignés avec ses signatures et clés de retour
4. 2787 tests passent (baseline actuel)

L'alignement Cython est une contrainte transversale —
elle s'applique à TOUS les fichiers Python du projet
qui importent ou wrappent `cointegration_fast`.

─────────────────────────────────────────────
RÈGLE D'ALIGNEMENT CYTHON (transversale)
─────────────────────────────────────────────
Le module Cython du projet est unique :
  `models/cointegration_fast.pyx`

Compilé en :
  `models/cointegration_fast.cp311-win_amd64.pyd`  (Python 3.11)
  `models/cointegration_fast.cp313-win_amd64.pyd`  (Python 3.13)

Fonctions publiques exposées (à vérifier pour chaque wrapper) :
  - `engle_granger_fast(x, y, threshold)` → dict avec clés :
    `is_cointegrated`, `pvalue`, `statistic`, `beta`,
    `intercept`, `half_life`, `critical_values`, `error`
  - `half_life_fast(spread)` → int

Pour tout fichier Python qui importe, wrap, appelle ou
interagit avec `cointegration_fast` :

- Les signatures d'appel doivent correspondre exactement
  à la définition Cython (ordre et noms des arguments)
- Les types des arguments doivent être cohérents
  (numpy arrays `float64`, seuil `float`)
- Les clés des dicts retournés doivent être identiques
- Toute divergence dans un fichier Python = erreur critique

Corrige toujours le fichier Python (ou son wrapper),
**jamais** le `.pyx`.
Pour vérifier une signature Cython :
→ Lis `models/cointegration_fast.pyx` directement.

Fichiers concernés à vérifier en priorité :
  `models/cointegration.py`
  `pair_selection/` (tout fichier qui appelle EG fast)
  `models/spread.py`

─────────────────────────────────────────────
ÉTAPE 0 — AUDIT PRIORITAIRE DU MODULE CYTHON
─────────────────────────────────────────────
Le wrapper Python `models/cointegration.py` est le
point d'entrée canonical de `cointegration_fast.pyd`.
Toute divergence ici se propage dans tout le projet.

### 0a — Ouverture du wrapper dans l'éditeur

⛔ **BLOQUANT** — ouvre chaque fichier Python qui
interagit avec `cointegration_fast` dans VSCode via
la commande PowerShell ci-dessous AVANT toute lecture
ou modification.

```powershell
$files = @(
  "c:\Users\averr\EDGECORE_V1\models\cointegration_fast.pyx",
  "c:\Users\averr\EDGECORE_V1\models\cointegration.py",
  "c:\Users\averr\EDGECORE_V1\models\spread.py"
)
$files | ForEach-Object { code --reuse-window $_ }
```

⚠️ Attends que les 3 onglets soient visibles dans
l'éditeur avant de procéder à l'étape 0b.

### 0b — Vérification paramètres orphelins (ARG)
```powershell
venv\Scripts\python.exe -m ruff check models/ --select ARG 2>&1
```

Pour chaque violation `ARG001` / `ARG002` :
1. Lis le fichier dans l'onglet ouvert
2. Lis la signature Cython dans `models/cointegration_fast.pyx`
3. Détermine si le paramètre est :
   - **nécessaire à la logique** → connecte-le à son usage
     naturel. Ne jamais supprimer.
   - **présent uniquement pour mirrorer la signature Cython**
     et intrinsèquement inutilisable en Python pur →
     renomme-le `_param` + commentaire inline :
     `# mirrors Cython signature — unused in Python fallback`
   - **totalement superflu** → signale au chef de projet
     avant toute suppression.

### 0c — Vérification alignement complet wrapper↔Cython
Pour chaque appel à `engle_granger_fast` ou `half_life_fast`
dans les fichiers ouverts :
- Ordre et noms des arguments
- Types des arguments (numpy arrays `float64`)
- Clés du dict retourné (`is_cointegrated`, `pvalue`, etc.)
- Gestion du fallback Python pur (si pyd absent)

Toute divergence = erreur critique → corrige le wrapper.

### 0d — Validation finale du module Cython
```powershell
venv\Scripts\python.exe -m ruff check models/ --select ARG 2>&1
venv\Scripts\python.exe -m ruff check models/ 2>&1
```
→ Les deux doivent donner zéro violation.

```
get_errors ["c:\\Users\\averr\\EDGECORE_V1\\models"]
```
→ `No errors found.`

Ferme tous les onglets ouverts :
```
① Charge l'outil (obligatoire pour les outils différés) :
   tool_search_tool_regex "run_vscode_command"

② Appelle l'outil récupéré :
   commandId : workbench.action.closeAllEditors
```

⚠️ Attends la confirmation de fermeture avant de continuer.

Annonce : **`models/` Cython ✅ — N erreurs corrigées.**
Demande `GO` pour passer à l'ÉTAPE 1.

─────────────────────────────────────────────
ÉTAPE 1 — TABLEAU DES DOSSIERS
─────────────────────────────────────────────
Scanne **l'ensemble du projet** et dresse un tableau
de **tous les dossiers et sous-dossiers contenant des
fichiers `.py`**, en excluant :
`venv/`, `__pycache__/`, `build/`, `.git/`,
`backups/`, `cache/`, `results/`, `logs/`.

```powershell
Get-ChildItem -Path "c:\Users\averr\EDGECORE_V1" `
  -Filter "*.py" -Recurse |
  Where-Object { $_.FullName -notmatch `
    "(__pycache__|\\venv\\|\\build\\|\.git|\\backups\\|\\cache\\|\\results\\|\\logs\\)" } |
  Select-Object DirectoryName |
  Sort-Object DirectoryName -Unique
```

Format du tableau (basé sur l'inventaire du 2026-03-23) :
```
DOSSIER                  | FICHIERS .py | STATUT
-------------------------|--------------|--------
(racine)/                |      2       | ⏳  ← main.py, setup.py
backtester/              |      4       | ⏳
backtests/               |     11       | ⏳
common/                  |      9       | ⏳
config/                  |      3       | ⏳
data/                    |      9       | ⏳
edgecore/                |      3       | ⏳
examples/                |      5       | ⏳
execution/               |     24       | ⏳
execution_engine/        |      2       | ⏳
live_trading/            |      3       | ⏳
models/                  |     16       | ✅  ← déjà traité (étape 0)
monitoring/              |     21       | ⏳
pair_selection/          |      4       | ⏳
persistence/             |      2       | ⏳
portfolio_engine/        |      4       | ⏳
research/                |      2       | ⏳
risk/                    |     12       | ⏳
risk_engine/             |      4       | ⏳
scheduler/               |      1       | ⏳
scripts/                 |     48       | ⏳
signal_engine/           |     15       | ⏳
strategies/              |      4       | ⏳
tests/                   |     11       | ⏳
tests/backtests/         |     12       | ⏳
tests/common/            |      8       | ⏳
tests/config/            |      3       | ⏳
tests/data/              |      7       | ⏳
tests/edgecore/          |      2       | ⏳
tests/execution/         |     19       | ⏳
tests/execution_engine/  |      2       | ⏳
tests/integration/       |      8       | ⏳
tests/live_trading/      |      6       | ⏳
tests/models/            |     22       | ⏳
tests/monitoring/        |     13       | ⏳
tests/persistence/       |      2       | ⏳
tests/phase3/            |      2       | ⏳
tests/phase4/            |      2       | ⏳
tests/portfolio_engine/  |      2       | ⏳
tests/risk/              |      5       | ⏳
tests/risk_engine/       |      2       | ⏳
tests/signal_engine/     |      3       | ⏳
tests/strategies/        |      5       | ⏳
tests/universe/          |      2       | ⏳
tests/validation/        |     11       | ⏳
universe/                |      5       | ⏳
validation/              |      2       | ⏳
```

⚠️ La racine (`main.py`, `setup.py`), `scripts/`,
`examples/` et `research/` font partie du périmètre —
ne pas les oublier.

Affiche le tableau complet mis à jour.
Demande `GO` pour démarrer le premier dossier.

─────────────────────────────────────────────
ÉTAPE 2 — TRAITEMENT DOSSIER PAR DOSSIER
─────────────────────────────────────────────
Pour chaque ligne du tableau (sauf `models/` déjà traité
à l'étape 0), répète la séquence suivante **une ligne à la
fois dans l'ordre du tableau**.

⚠️ **RÈGLE CRITIQUE — SOUS-DOSSIERS** :
Chaque ligne du tableau (y compris `tests/backtests/`,
`tests/common/`, `tests/execution/`, etc.) est traitée
**exactement comme un dossier de premier niveau**.
La séquence 2a→2h est répétée intégralement pour chaque
sous-dossier. **Ne regroupe jamais plusieurs sous-dossiers
en une seule itération.**

Exemple réel :
- `tests/` → séquence 2a→2h complète → GO → `tests/backtests/`
- `tests/backtests/` → séquence 2a→2h complète → GO → `tests/common/`
- `tests/common/` → séquence 2a→2h complète → GO → `tests/config/`
- … et ainsi de suite jusqu'à `tests/validation/`

**Ne passe jamais au dossier/sous-dossier suivant tant que
le dossier courant n'est pas entièrement propre :
0 erreur ruff · 0 paramètre ARG · 0 erreur Pylance.**

### 2a — Ouvrir tous les fichiers dans l'éditeur VSCode

⛔ **BLOQUANT — PRÉ-CONDITION OBLIGATOIRE** — avant d'ouvrir
les fichiers du nouveau dossier, ferme **tous** les onglets
encore ouverts du dossier précédent :

```
① Charge l'outil (obligatoire pour les outils différés) :
   tool_search_tool_regex "run_vscode_command"

② Appelle l'outil récupéré :
   commandId : workbench.action.closeAllEditors
```

⚠️ Attends la confirmation de fermeture avant de continuer.
Ne jamais ouvrir un nouveau dossier avec des onglets du
dossier précédent encore ouverts — les diagnostics Pylance
seront pollués.

Ouvre ensuite **chaque** fichier `.py` du dossier courant
dans VSCode via la commande PowerShell ci-dessous :

```powershell
$dossier = "c:\Users\averr\EDGECORE_V1\<chemin_dossier>"
Get-ChildItem -Path $dossier -Filter "*.py" |
  Where-Object { $_.FullName -notmatch "__pycache__" } |
  Sort-Object Name |
  ForEach-Object { code --reuse-window $_.FullName }
```

⚠️ Remplace `<chemin_dossier>` par le chemin réel du
dossier courant à chaque itération.
⚠️ Attends que tous les onglets soient visibles dans
l'éditeur avant de passer à l'étape 2c.

✅ Dès que les onglets sont visibles, Pylance analyse
automatiquement les fichiers ouverts et alimente le panneau
**PROBLEMS**. Passe directement à l'étape 2c pour lire ce
panneau et corriger chaque erreur avant toute autre
vérification.

### 2b — Vérifier l'alignement Cython (si applicable)
Si le dossier contient un fichier qui importe ou appelle
`cointegration_fast` :

1. Lis le fichier Python dans l'onglet ouvert
2. Lis `models/cointegration_fast.pyx`
3. Compare signatures d'appel, types d'arguments, clés de
   retour
4. Corrige toute divergence dans le fichier Python

Cette vérification est obligatoire même si aucune
erreur ruff ou Pylance n'est remontée.

### 2c — Lire et vider le panneau PROBLEMS de VSCode

⛔ **BLOQUANT** — accède immédiatement au panneau PROBLEMS
de VSCode. Lis-le via :
```
get_errors ["c:\\Users\\averr\\EDGECORE_V1\\<chemin_dossier>"]
```
C'est la source de vérité — identique au contenu visible
dans l'onglet PROBLEMS de l'éditeur VSCode.

Dresse la liste complète de toutes les erreurs remontées.

**Boucle de correction — une erreur à la fois :**
1. Prends la première erreur de la liste
2. Lis le fichier concerné dans l'onglet ouvert
3. Comprends le contexte — ne corrige jamais à l'aveugle
4. Applique la correction selon les règles de l'étape 2f
5. Relance `get_errors ["c:\\Users\\averr\\EDGECORE_V1\\<chemin_dossier>"]`
6. Vérifie que l'erreur est résolue et qu'aucune nouvelle
   erreur n'est apparue
7. Répète jusqu'à ce que le panneau PROBLEMS retourne **0 erreurs**

⚠️ Ne passe jamais à 2d tant que `get_errors` retourne
des erreurs. Les fichiers doivent rester ouverts pendant
toute cette phase.

### 2d — Corriger les erreurs ruff (auto-fix)
```powershell
venv\Scripts\python.exe -m ruff check <chemin_dossier>/ --fix 2>&1
venv\Scripts\python.exe -m ruff check <chemin_dossier>/ --fix --unsafe-fixes 2>&1
```
Si des erreurs restent après l'auto-fix → lis le fichier
dans l'onglet ouvert, comprends le contexte, corrige
manuellement via `replace_string_in_file` ou
`multi_replace_string_in_file`.
Relance jusqu'à `All checks passed!`

### 2e — Vérifier les paramètres orphelins (ARG)
⚠️ Obligatoire — ruff standard ne détecte pas ARG.
```powershell
venv\Scripts\python.exe -m ruff check <chemin_dossier>/ --select ARG 2>&1
```

Pour chaque violation :
1. Lis le fichier dans l'onglet ouvert
2. Connecte le paramètre à son usage naturel si possible
3. Si structurellement inutilisable → renomme `_param`
   avec commentaire justificatif inline
4. Vérifie l'impact sur les call sites :
```powershell
# grep_search "<nom_parametre>" dans le dossier concerné
```
5. Ne jamais supprimer sans validation chef de projet

### 2e.bis — Audit des paramètres `_`-préfixés (angle mort de ruff)

⚠️ **CRITIQUE** — `ruff --select ARG` ignore silencieusement
les paramètres préfixés `_param` car la convention Python
signifie "intentionnellement inutilisé". Or la règle d'or du
projet est **zéro paramètre déclaré sans usage**.
Ce step comble cet angle mort.

```powershell
# Pour un dossier plat (tous les dossiers sauf scripts/) :
Select-String -Path "<chemin_dossier>\*.py" `
  -Pattern "def .*\b_[a-z][a-z0-9_]*\s*[=:,)]"

# Pour scripts/ (sous-dossiers possibles) :
Get-ChildItem -Path "<chemin_dossier>" -Filter "*.py" -Recurse |
  Select-String -Pattern "def .*\b_[a-z][a-z0-9_]*\s*[=:,)]"
```

⚠️ N'utilise **jamais** le flag `-Recurse` sur `Select-String`
directement avec un wildcard `*.py` — cela provoque une erreur
PowerShell. Utilise le pipeline `Get-ChildItem | Select-String`
si une récursion est nécessaire.

Pour chaque occurrence trouvée :
1. Lis la fonction entière dans l'onglet ouvert
   (de la `def` jusqu'à la fin du corps — **ligne par ligne**)
2. Vérifie si `_param` apparaît dans le corps de la fonction
3. **S'il n'apparaît pas → c'est un orphelin caché** :
   - Renomme `_param` → `param`
   - Identifie l'usage naturel (validation, condition, log)
   - Connecte-le à cet usage
4. Ne jamais laisser un paramètre `_`-préfixé non utilisé

### 2f — Règles de correction par type d'erreur

Référence pour la boucle de la section 2c.
Pour chaque erreur rencontrée dans le panneau PROBLEMS :

**Import non utilisé** → supprimer l'import.

**Type incompatible** → corriger l'annotation ou le code.

**Variable, paramètre ou fonction non utilisé(e)**
(`"X" is not accessed` / `"_x" is not accessed`) →
**Règle d'or — zéro orphelin** :
toute variable, tout paramètre et toute fonction présents
dans le code doivent être utilisés avec cohérence.
Cela inclut les paramètres `_`-préfixés — le préfixe `_` ne
dispense PAS d'une connexion à un usage naturel.
Marche à suivre :
1. Lis le fichier **ligne par ligne** dans l'onglet ouvert
   (aucune ligne ne doit être sautée)
2. Identifie où l'identifiant devrait logiquement être utilisé
   (validation, logging, assertion, condition, valeur de retour)
3. Connecte-le à son usage naturel
4. Ne le supprime pas
5. **Exception unique** : index de boucle sans usage
   possible → renomme `_i` + commentaire inline
6. Si inutile après analyse → signale au chef de projet
   avant toute suppression

**`datetime.utcnow()` détecté** →
remplace par `datetime.now(timezone.utc)`.
Vérifie que `from datetime import timezone` est présent.

**`print()` détecté** →
remplace par `logger.debug(...)` ou `logger.info(...)`.
Vérifie que `logger = structlog.get_logger(__name__)` est
présent en haut du module.

**Seuil de risque hardcodé** (valeur numérique pour un
paramètre de stratégie comme entry_z, drawdown, stop…) →
remplace par la lecture config :
`get_settings().<section>.<champ>`

**Divergence avec Cython** → applique la règle
d'alignement Cython définie en haut du prompt.

**Toute autre erreur** → lire, comprendre, corriger.

→ Reprends à l'étape 2c (boucle) après chaque correction.

### 2g — Validation finale du dossier
```powershell
venv\Scripts\python.exe -m ruff check <chemin_dossier>/ 2>&1 |
  Select-Object -Last 3
venv\Scripts\python.exe -m ruff check <chemin_dossier>/ --select ARG 2>&1 |
  Select-Object -Last 3
```
→ Les deux : `All checks passed!`
```
get_errors ["c:\\Users\\averr\\EDGECORE_V1\\<chemin_dossier>"]
```
→ `No errors found.`

### 2h — Fermer les fichiers et annoncer

⛔ **CONDITION PRÉALABLE** — ne ferme les fichiers que
lorsque les trois conditions suivantes sont simultanément
réunies :
- `get_errors` retourne **0 erreurs** (panneau PROBLEMS vide)
- `ruff check <dossier>/ --select ARG` → 0 violation
- `ruff check <dossier>/` → `All checks passed!`

Ferme tous les onglets ouverts :
```
① Charge l'outil (obligatoire pour les outils différés) :
   tool_search_tool_regex "run_vscode_command"

② Appelle l'outil récupéré :
   commandId : workbench.action.closeAllEditors
```

⚠️ **BLOQUANT** — attends la confirmation de fermeture
avant d'ouvrir les fichiers du dossier suivant (2a).

### 2i — Lancer les tests du dossier courant

Après la fermeture des onglets, lance les tests
correspondant au dossier venant d'être traité.

**Règle de correspondance dossier → tests :**

| Dossier traité | Commande pytest |
|---|---|
| `(racine)/` | `pytest tests/ -q --tb=no` (global) |
| `backtester/` | `pytest tests/backtests/ tests/ -q --tb=no -k "backtest"` |
| `backtests/` | `pytest tests/backtests/ -q --tb=no` |
| `common/` | `pytest tests/common/ -q --tb=no` |
| `config/` | `pytest tests/config/ -q --tb=no` |
| `data/` | `pytest tests/data/ -q --tb=no` |
| `edgecore/` | `pytest tests/edgecore/ -q --tb=no` |
| `execution/` | `pytest tests/execution/ -q --tb=no` |
| `execution_engine/` | `pytest tests/execution_engine/ -q --tb=no` |
| `live_trading/` | `pytest tests/live_trading/ -q --tb=no` |
| `models/` | `pytest tests/models/ -q --tb=no` |
| `monitoring/` | `pytest tests/monitoring/ -q --tb=no` |
| `pair_selection/` | `pytest tests/ -q --tb=no -k "pair"` |
| `persistence/` | `pytest tests/persistence/ -q --tb=no` |
| `portfolio_engine/` | `pytest tests/portfolio_engine/ -q --tb=no` |
| `risk/` | `pytest tests/risk/ -q --tb=no` |
| `risk_engine/` | `pytest tests/risk_engine/ -q --tb=no` |
| `signal_engine/` | `pytest tests/signal_engine/ -q --tb=no` |
| `strategies/` | `pytest tests/strategies/ -q --tb=no` |
| `universe/` | `pytest tests/universe/ -q --tb=no` |
| `validation/` | `pytest tests/validation/ -q --tb=no` |
| `tests/` | `pytest tests/ -q --tb=no --ignore=tests/backtests --ignore=tests/common` *(etc. — uniquement les fichiers racine de tests/)* |
| `tests/<sous-dossier>/` | `pytest tests/<sous-dossier>/ -q --tb=no` |
| `scripts/`, `research/`, `examples/` | `pytest tests/ -q --tb=no` (global) |

⚠️ Si le dossier traité est un **sous-dossier de `tests/`**
(ex. `tests/backtests/`), la commande pytest cible
exactement ce sous-dossier :
```powershell
venv\Scripts\python.exe -m pytest tests/<sous-dossier>/ -q --tb=no 2>&1 | Select-Object -Last 5
```

⛔ **BLOQUANT** — si des tests échouent après une
correction, corrige le problème avant de passer au dossier
suivant. Reviens à l'étape 2c si nécessaire.

Annonce :
**`<dossier>/` ✅ — ruff: N · ARG: N · Pylance: N ·
Alignement Cython: N divergences corrigées · Tests: X passed.**

Met à jour le tableau :
```
DOSSIER                  | FICHIERS .py | STATUT
-------------------------|--------------|--------
(racine)/                |      2       | ✅
backtester/              |      4       | ✅
backtests/               |     11       | ✅ ← vient de finir
common/                  |      9       | ⏳ ← suivant
...
tests/backtests/         |     12       | ✅ ← vient de finir
tests/common/            |      8       | ⏳ ← suivant
...
```

Demande `GO` pour passer au dossier/sous-dossier suivant.

─────────────────────────────────────────────
CONTRAINTES DU PROJET EDGECORE
─────────────────────────────────────────────
- ❌ Ne jamais utiliser `# type: ignore` —
  préférer des corrections typées robustes et explicites
  (cast, isinstance guard, annotation précise)
- ❌ Ne jamais utiliser `Any` comme raccourci de type
- ❌ Ne jamais utiliser `datetime.utcnow()` →
  utiliser `datetime.now(timezone.utc)`
- ❌ Ne jamais utiliser `print()` →
  utiliser `structlog.get_logger(__name__)`
- ❌ Ne jamais hardcoder de seuils de risque ou de
  paramètres de stratégie (entry_z, drawdown %, stop…) →
  tout passe par `get_settings().<section>.<champ>`
- ❌ Ne jamais toucher `models/cointegration_fast.pyx`
- ❌ Ne jamais utiliser `ccxt` ou importer depuis
  `research/` dans un module de production
- ❌ Ne jamais appeler l'API IBKR sans
  `_ibkr_rate_limiter.acquire()` au préalable
- ❌ **RÈGLE D'OR — zéro orphelin** : toute variable,
  fonction ET paramètre présent dans le code doit être
  utilisé. Couvre :
  - Variables locales (Pylance `"X" is not accessed`)
  - Fonctions non appelées (Pylance)
  - Paramètres non référencés dans le corps
    (`ruff --select ARG` uniquement)
  Ne jamais supprimer ou masquer sans comprendre
  l'intention et avoir connecté à l'usage naturel.
- ❌ **RÈGLE ALIGNEMENT CYTHON** : tout fichier Python
  interagissant avec `models/cointegration_fast.pyx` doit
  être parfaitement aligné (signatures, types, clés de
  retour). Corrige toujours le Python, jamais le `.pyx`.
- ❌ `EDGECORE_ENV=production` → valeur invalide,
  utiliser `prod`
- ✅ Python 3.11.9 (venv `venv\Scripts\python.exe`)
- ✅ Grouper les corrections avec
  `multi_replace_string_in_file` quand possible
- ✅ Toujours ouvrir les fichiers via PowerShell
  `code --reuse-window <chemin>` avant toute modification.
  Attendre que les onglets soient visibles dans VSCode.
- ✅ `structlog.get_logger(__name__)` — jamais
  `logging.basicConfig` ni `logging.getLogger`

─────────────────────────────────────────────
ÉTAPE 3 — VALIDATION GLOBALE FINALE
─────────────────────────────────────────────
Après tous les dossiers :

```powershell
# ruff global (hors venv, __pycache__, build)
venv\Scripts\python.exe -m ruff check . `
  --exclude venv,__pycache__,build,.git,backups,cache,results,logs `
  --select ARG 2>&1 | Select-Object -Last 3

venv\Scripts\python.exe -m ruff check . `
  --exclude venv,__pycache__,build,.git,backups,cache,results,logs `
  2>&1 | Select-Object -Last 3

# Pylance global
get_errors

# Suite de tests complète
venv\Scripts\python.exe -m pytest tests/ -q 2>&1 | Select-Object -Last 3
```

→ ruff ARG : `All checks passed!` (zéro orphelin)
→ ruff standard : `All checks passed!`
→ Pylance : `No errors found.`
→ Tests : `2787 passed` (ou plus si de nouveaux tests
  ont été ajoutés pendant l'audit)

─────────────────────────────────────────────
SORTIE FINALE
─────────────────────────────────────────────
```
✅ Correction complète terminée — EDGECORE_V1
   Dossiers traités                  : X / 47
   Fichiers Python audités           : X
   Erreurs ruff corrigées            : X
   Paramètres orphelins (ARG)        : X
   Erreurs Pylance corrigées         : X
   Divergences Python↔Cython         : X
   utcnow() → now(timezone.utc)      : X occurrences
   print() → structlog               : X occurrences
   Seuils hardcodés déplacés config  : X occurrences
   Tests finaux :
     2787+ tests  ✅
     0 ruff       ✅
     0 ARG        ✅
     0 Pylance    ✅
```

─────────────────────────────────────────────
DÉMARRAGE
─────────────────────────────────────────────
Commence maintenant par l'**ÉTAPE 0**.

Exécute d'abord la commande PowerShell d'ouverture
des fichiers Cython + wrappers dans VSCode, audite
l'alignement, corrige, valide, puis demande `GO`
pour l'ÉTAPE 1.
