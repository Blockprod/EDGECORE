---
modele: claude-sonnet-4.6
mode: agent
contexte: codebase
derniere_revision: 2026-03-21
---

#codebase

Je suis le chef de projet EDGECORE.

Tu vas corriger **toutes les erreurs** détectées par le linter (ruff)
et le type-checker (Pylance / PROBLEMS panel) dans le workspace,
dossier par dossier, fichier par fichier.

Tu ne dois **pas** présumer des erreurs à l'avance. Tu les découvres
dynamiquement en lisant la sortie de ruff et du PROBLEMS panel,
puis tu appliques la correction appropriée à chaque erreur détectée.

─────────────────────────────────────────────
INVENTAIRE DES DOSSIERS
─────────────────────────────────────────────
Scanne le workspace pour lister tous les dossiers contenant des
fichiers `.py`, en excluant :
`venv/`, `__pycache__/`, `build/`, `backups/`, `.git/`, `ARCHIVED_*/`.

Affiche le tableau de progression :

```
DOSSIER            | FICHIERS .py | STATUT
-------------------|--------------|--------
backtester/        |      4       | ⏳
backtests/         |     11       | ⏳
...
```

Puis traite le premier dossier. Demande `GO` avant chaque suivant.

─────────────────────────────────────────────
PROCÉDURE PAR DOSSIER (6 étapes)
─────────────────────────────────────────────

### Étape 1 — Ouvrir les fichiers + auto-fix ruff
Combine ouverture dans VS Code Open Editors et première passe ruff :
```powershell
Get-ChildItem -Path "<dossier>" -Filter "*.py" `
  | Where-Object { $_.FullName -notmatch "__pycache__" } `
  | ForEach-Object { code $_.FullName }
venv\Scripts\python.exe -m ruff check <dossier>\ --fix 2>&1
```
Note le nombre d'erreurs corrigées et le nombre restant.

### Étape 2 — Unsafe-fixes si erreurs restantes
Si ruff signale des erreurs fixables avec `--unsafe-fixes` :
```powershell
venv\Scripts\python.exe -m ruff check <dossier>\ --fix --unsafe-fixes 2>&1
```

### Étape 3 — Lire les erreurs ruff restantes
```powershell
venv\Scripts\python.exe -m ruff check <dossier>\ 2>&1
```
**Lis chaque erreur**, identifie le code (B904, B905, UP031, E902…),
le fichier et la ligne, puis applique la correction appropriée :
- Lis le contexte du fichier autour de la ligne signalée.
- Déduis la bonne correction en te basant sur le code d'erreur et
  le contexte réel du code.
- Applique la correction via `replace_string_in_file` ou
  `multi_replace_string_in_file`.
- Si l'erreur est E902 (UTF-8 corrompu), re-sauvegarde le fichier :
  ```powershell
  $b = [System.IO.File]::ReadAllBytes("<fichier>")
  [System.IO.File]::WriteAllText("<fichier>",
    [System.Text.Encoding]::UTF8.GetString($b),
    [System.Text.Encoding]::UTF8)
  ```
- Si une erreur est un faux positif récurrent sur tout un dossier
  (ex: B017 dans tests/), propose de l'ajouter dans
  `pyproject.toml → [tool.ruff.lint.per-file-ignores]`.

Relance `ruff check` jusqu'à `All checks passed!`.

### Étape 4 — Lire le PROBLEMS panel (Pylance)
```
get_errors ["c:\\Users\\averr\\EDGECORE_V1\\<dossier>"]
```
**Lis chaque erreur Pylance** retournée et corrige-la :
- Import non utilisé → le supprimer.
- Type incompatible → corriger l'annotation ou le code.
- Attribut inconnu → vérifier l'API et adapter.
- **Variable non utilisée** (`"X" is not accessed`) → **NE PAS
  simplement supprimer ou renommer en `_`**. Une variable créée est
  supposée être utilisée. Lis le contexte du code, comprends
  l'intention originale, et utilise la variable là où elle devrait
  l'être (logging, assertion, condition, retour…). Le renommage en
  `_` n'est acceptable que si la variable est réellement jetable
  (ex: index de boucle `for i, x in enumerate(...)` où `i` n'a
  aucun usage possible).
- Toute autre erreur → lire le fichier, comprendre le problème,
  corriger.

Relance `get_errors` jusqu'à `No errors found.`.

### Étape 5 — Double vérification finale
```powershell
venv\Scripts\python.exe -m ruff check <dossier>\ 2>&1 | Select-Object -Last 3
```
→ Doit afficher `All checks passed!`

### Étape 6 — Annoncer et passer au suivant
Annoncer : **`<dossier>/` ✅ — N erreurs corrigées.**
Mettre à jour le tableau de progression.
Demander `GO` pour le prochain dossier.

─────────────────────────────────────────────
CONTRAINTES DU PROJET
─────────────────────────────────────────────
- ❌ Ne jamais utiliser `# type: ignore` — toujours corriger proprement.
- ❌ Ne jamais supprimer ou renommer en `_` une variable non utilisée
  par facilité — comprendre pourquoi elle existe et l'utiliser
  correctement (logging, assertion, condition, retour…).
- ❌ Ne jamais utiliser `datetime.utcnow()` — utiliser
  `datetime.now(UTC)`.
- ❌ Ne jamais modifier `risk_engine/kill_switch.py` sans adapter
  `risk/facade.py`.
- ✅ Toujours ouvrir les fichiers dans VS Code Open Editors **avant**
  de les corriger.
- ✅ Toujours valider ruff ET Pylance (`get_errors`) sur chaque dossier.
- ✅ Grouper les corrections avec `multi_replace_string_in_file`
  quand possible.

─────────────────────────────────────────────
VÉRIFICATION GLOBALE FINALE
─────────────────────────────────────────────
Après **tous** les dossiers, lancer :

```powershell
venv\Scripts\python.exe -m ruff check . 2>&1 | Select-Object -Last 5
```

Si erreurs restantes → les corriger et relancer jusqu'à
`All checks passed!`.

Puis valider qu'aucune régression n'a été introduite :

```powershell
venv\Scripts\python.exe -m pytest tests/ -q 2>&1 | Select-Object -Last 5
```

─────────────────────────────────────────────
DÉMARRAGE
─────────────────────────────────────────────
Commence maintenant : scanne, affiche le tableau, traite le premier
dossier sans attendre de confirmation.
Demande `GO` avant chaque dossier suivant.
