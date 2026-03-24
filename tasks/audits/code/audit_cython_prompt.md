---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: tasks/audits/audit_cython_edgecore.md
derniere_revision: 2026-03-21
creation: 2026-03-21 à 23:34
---

#codebase

Tu es un ingénieur Cython senior spécialisé en systèmes
de trading algorithmique haute performance.
Tu réalises un audit EXCLUSIVEMENT centré sur
la couche Cython d'EDGECORE.

─────────────────────────────────────────────
RAISONNEMENT
─────────────────────────────────────────────
Réfléchis profondément étape par étape avant
de produire ta sortie. Explore d'abord, planifie
ensuite, puis exécute.

─────────────────────────────────────────────
ÉTAPE 0 — VÉRIFICATION PRÉALABLE (OBLIGATOIRE)
─────────────────────────────────────────────
Vérifie si ce fichier existe déjà dans :
  tasks/audits/audit_cython_edgecore.md

Si trouvé, affiche :
"⚠️ Audit Cython existant détecté :
 Fichier : tasks/audits/audit_cython_edgecore.md
 Date    : [date modification]
 Lignes  : [nombre approximatif]

 [NOUVEAU]  → audit complet (écrase l'existant)
 [MÀJOUR]   → compléter sections manquantes
 [ANNULER]  → abandonner"

Si absent → démarrer directement :
"✅ Aucun audit Cython existant. Démarrage..."

─────────────────────────────────────────────
PÉRIMÈTRE STRICT
─────────────────────────────────────────────
Tu analyses UNIQUEMENT :
- Le module Cython models/cointegration_fast.pyx
- Sa cohérence avec models/cointegration.py (fallback)
- La reproductibilité du build (setup.py)
- La couverture des tests dans tests/models/
- Les imports Cython dans le reste du codebase

Tu n'analyses PAS la logique statistique des modèles,
la sécurité des credentials IBKR, ni l'architecture
des modules non-Cython.

─────────────────────────────────────────────
CONTRAINTES ABSOLUES
─────────────────────────────────────────────
- Analyse models/cointegration_fast.pyx comme
  code source de référence — mais NE PAS inférer
  la logique mathématique interne
- Cite fichier:ligne pour chaque écart
- Écris "À VÉRIFIER" sans preuve dans le code
- Le fichier .c est un artefact de transpilation
  — ne pas l'analyser directement
- Ne jamais suggérer de modifier .pyx sans signaler
  que la recompilation est obligatoire :
  `venv\Scripts\python.exe setup.py build_ext --inplace`

─────────────────────────────────────────────
BLOC 1 — INVENTAIRE DU MODULE CYTHON
─────────────────────────────────────────────
EDGECORE a un seul module Cython :
  models/cointegration_fast

Pour ce module, vérifie :
- .pyx présent ? ✅ / ❌
- .cp311-win_amd64.pyd présent ? ✅ / ❌
- .cp313-win_amd64.pyd présent ? ✅ / ❌
- .c présent (artefact de transpilation) ? ✅ / ❌
- .so présent (Linux, si applicable) ? ✅ / ❌

Vérifie les 4 fonctions publiques exportées :
- engle_granger_fast   → dict
- half_life_fast       → int
- brownian_bridge_batch_fast → np.ndarray
- compute_zscore_last_fast   → double

Pour chaque fonction, confirme :
- Présente dans le .pyx ? ✅ / ❌
- Signature annotée (type hints) ? ✅ / ❌
- Docstring présente ? ✅ / ❌

─────────────────────────────────────────────
BLOC 2 — COHÉRENCE DES INTERFACES
─────────────────────────────────────────────
Compare les signatures dans models/cointegration_fast.pyx
avec leurs consommateurs dans le codebase.

Interfaces à vérifier :

engle_granger_fast :
  Signature .pyx :
    engle_granger_fast(
      y: np.ndarray[float64, ndim=1],
      x: np.ndarray[float64, ndim=1]
    ) -> dict
  Clés attendues dans le dict retourné :
    beta, intercept, residuals, adf_statistic,
    adf_pvalue, is_cointegrated, critical_values, error
  Consommateurs à vérifier :
    - models/cointegration.py (import + usage)
    - agents/dev_engineer.md mentionne
      `engle_granger_test_fast` — alias cohérent ?

half_life_fast :
  Signature .pyx :
    half_life_fast(
      spread: np.ndarray[float64, ndim=1]
    ) -> int
  Retourne -1 si invalide (n < 3)
  Consommateurs :
    - models/spread.py (import comme _half_life_fast_cython)

brownian_bridge_batch_fast :
  Signature .pyx :
    brownian_bridge_batch_fast(
      closes: np.ndarray[float64, ndim=2],
      noise: np.ndarray[float64, ndim=3],
      bars_per_day: int
    ) -> np.ndarray
  Dimensions attendues :
    closes : (n_days, n_symbols)
    noise  : (n_days-1, bars_per_day, n_symbols)
    out    : ((n_days-1)*bars_per_day, n_symbols)
  Consommateurs :
    - data/intraday_loader.py (import lazy)

compute_zscore_last_fast :
  Signature .pyx :
    compute_zscore_last_fast(
      spread: np.ndarray[float64, ndim=1],
      lookback: int
    ) -> double
  Retourne 0.0 si données insuffisantes
  Clampé à [-6, 6]
  Consommateurs :
    - backtests/strategy_simulator.py (import lazy)

Pour chaque fonction :
- Signature appelante == signature .pyx ? CONFORME / ÉCART
- Arguments optionnels documentés ?
- Valeur de retour validée côté consommateur ?

─────────────────────────────────────────────
BLOC 3 — FALLBACK PYTHON ET FLAG CYTHON
─────────────────────────────────────────────
Analyse models/cointegration.py :

- Le flag CYTHON_COINTEGRATION_AVAILABLE est-il
  utilisé partout où une fonction Cython est appelée ?
- Le bloc try/except ImportError est-il complet ?
  (les 4 fonctions sont-elles toutes couvertes ?)
- Les imports lazy dans backtests/strategy_simulator.py
  et data/intraday_loader.py ont-ils un fallback ?
- Le log warning cite-t-il la commande de recompilation
  exacte ?
- CPP_COINTEGRATION_AVAILABLE (alias legacy) :
  utilisé dans le codebase ? Peut-il être supprimé ?
- Cohérence des aliases :
  _brownian_bridge_batch_fast, _compute_zscore_last_fast,
  _half_life_fast, _engle_granger_fast — tous importés ?
  Certains sont-ils importés mais jamais utilisés ?

─────────────────────────────────────────────
BLOC 4 — BUILD ET REPRODUCTIBILITÉ
─────────────────────────────────────────────
Analyse setup.py :

- L'extension `models.cointegration_fast` est-elle
  correctement déclarée avec sources et include_dirs ?
- Compiler directives définis dans cythonize() :
  language_level='3' ? ✅ / ❌
  boundscheck=False ?  ✅ / ❌
  wraparound=False ?   ✅ / ❌
  cdivision=True ?     ✅ / ❌
  nonecheck=False ?    ✅ / ❌
- extra_compile_args : /O2 sur Windows,
  -O2 sur Linux ? ✅ / ❌
- Cython version dans requirements.txt ou
  pyproject.toml : fixée ? Cohérente ?
  (Cython >= 0.29 déclaré — est-ce 3.0
   qui est réellement utilisé ?)
- annotate non défini → pas de .html générés ?
  Si .html présents : sont-ils dans .gitignore ?
- build/ dans .gitignore ?
- .pyd dans .gitignore ou commités dans le repo ?
- .c dans .gitignore ou commité ?
- Workflow CI (si .github/workflows/ présent) :
  build Cython avant les tests ? ✅ / ❌

─────────────────────────────────────────────
BLOC 5 — COUVERTURE DES TESTS CYTHON
─────────────────────────────────────────────
Analyse tests/models/056_test_cython_module.py
et tout autre test mentionnant cointegration_fast :

- Le test vérifie-t-il que le .pyd est compilé
  (glob sur cointegration_fast*.pyd/.so) ?
- Les 4 fonctions sont-elles toutes testées ?
  - engle_granger_fast : ✅ / ❌
  - half_life_fast : ✅ / ❌
  - brownian_bridge_batch_fast : ✅ / ❌
  - compute_zscore_last_fast : ✅ / ❌
- Les cas limites sont-ils couverts :
  - n < 20 pour engle_granger_fast → error key ?
  - NaN dans les séries → retour cohérent ?
  - n < 3 pour half_life_fast → retour -1 ?
  - lookback > n pour compute_zscore_last_fast
    → retour 0.0 ?
  - z > 6 ou z < -6 → clamping correctement testé ?
- Test de comparaison Cython vs Python :
  les résultats sont-ils proches (tolérance 1e-6) ?
- Le test skip-se proprement si le .pyd est absent
  (ImportError) ou plante-t-il ?
- Tests de performance (benchmark) présents ?
  Speedup mesuré vs Python pur ?

─────────────────────────────────────────────
BLOC 6 — USAGES SUSPECTS DANS LE CODEBASE
─────────────────────────────────────────────
Recherche tous les imports et usages de
models.cointegration_fast dans le codebase
(hors tests/ et docs/) :

- Imports directs vs imports via
  models/cointegration.py (façade) ?
  Un consommateur court-circuite-t-il la façade ?
- Imports lazy (dans un bloc try/except) vs
  imports en top-level ?
- agents/dev_engineer.md mentionne
  `engle_granger_test_fast` : cette fonction
  existe-t-elle dans le .pyx ou est-ce une erreur
  de documentation ?
- Usages dans research/ ou scripts/ ?
  (ne peuvent pas compter sur le .pyd en CI)

─────────────────────────────────────────────
SORTIE OBLIGATOIRE
─────────────────────────────────────────────
Crée le fichier :
  tasks/audits/audit_cython_edgecore.md
Crée le dossier tasks/audits/ s'il n'existe pas.

Structure du fichier :
## BLOC 1 — INVENTAIRE DU MODULE CYTHON
## BLOC 2 — COHÉRENCE DES INTERFACES
## BLOC 3 — FALLBACK PYTHON ET FLAG CYTHON
## BLOC 4 — BUILD ET REPRODUCTIBILITÉ
## BLOC 5 — COUVERTURE DES TESTS CYTHON
## BLOC 6 — USAGES SUSPECTS
## SYNTHÈSE

Tableau synthèse :
| ID | Bloc | Description | Fichier:Ligne | Sévérité | Impact | Effort |

Sévérité : 🔴 Critique · 🟠 Majeur · 🟡 Mineur.

Confirme dans le chat uniquement :
"✅ tasks/audits/audit_cython_edgecore.md créé
 🔴 X · 🟠 X · 🟡 X"
