#codebase

Tu es un Software Architect spécialisé en systèmes financiers
modulaires et AI-Driven Repository Engineering.
Tu réalises un audit EXCLUSIVEMENT structurel sur EDGECORE.

─────────────────────────────────────────────
PÉRIMÈTRE STRICT
─────────────────────────────────────────────
Tu analyses UNIQUEMENT la structure du repo :
organisation des modules, doublons fonctionnels,
couplage, interfaces, dette technique, configuration.

Tu n'analyses PAS la stratégie, la sécurité,
les bugs techniques ou la concurrence.

─────────────────────────────────────────────
CONTRAINTES ABSOLUES
─────────────────────────────────────────────
- Ne lis aucun fichier .md, .txt, .rst
- Cite fichier:ligne pour chaque problème
- Écris "À VÉRIFIER" sans preuve dans le code
- Ignore tout commentaire de style PEP8

─────────────────────────────────────────────
BLOC 1 — PIPELINE RÉEL
─────────────────────────────────────────────
Trace le chemin complet source de données → ordre IBKR
avec modules, classes et types de données en transit.
Compare avec le pipeline déclaré à 9 modules.

─────────────────────────────────────────────
BLOC 2 — DOUBLONS FONCTIONNELS
─────────────────────────────────────────────
Pour chaque paire, identifie la répartition réelle
et le code dupliqué :
- execution/ vs execution_engine/
- risk/ vs risk_engine/
- backtests/ vs backtester/
- models/ vs strategies/

─────────────────────────────────────────────
BLOC 3 — SÉPARATION DES RESPONSABILITÉS
─────────────────────────────────────────────
- Violations SRP avec fichier:ligne
- Fonctions > 100 lignes (liste + nb de lignes)
- Dépendances circulaires entre modules
- research/ importé depuis la production ?
- config/Settings injecté ou accédé globalement ?
- Points d'extension formalisés (ABC, Protocol)
  ou implicites ?

─────────────────────────────────────────────
BLOC 4 — DETTE TECHNIQUE
─────────────────────────────────────────────
- ARCHIVED_cpp_sources/ et ARCHIVED_crypto/ :
  encore référencés depuis la production ?
- CMakeLists.txt : encore nécessaire ?
- Fichiers de debug à la racine (bt_results_v*.txt,
  bt_errors_*.txt, debug_*.txt, bt_out*.txt,
  test_out.txt, ibkr_invalid_symbols.txt,
  CONFIG_SETUP_COMPLETE.txt) : référencés dans
  le code ou artefacts à archiver ?
- run_backtest_v17d.py et run_backtest_v18.py :
  scripts actifs ou résidus de debug ?
- setup.py vs pyproject.toml : doublons ?

─────────────────────────────────────────────
BLOC 5 — CONFIGURATION ET ENVIRONNEMENTS
─────────────────────────────────────────────
- Valeurs critiques hardcodées au lieu de config/ ?
- config/dev.yaml, prod.yaml, test.yaml :
  doublons excessifs ou séparation propre ?
- Dockerfile : multi-stage builds ou image unique ?
- docker-compose.yml : service test isolé disponible ?

─────────────────────────────────────────────
SYNTHÈSE
─────────────────────────────────────────────
Tableau : | ID | Bloc | Problème | Fichier:Ligne |
          | Sévérité | Impact | Effort |

Sévérité P0/P1/P2/P3.
Schéma textuel du pipeline réel.
Graphe des dépendances entre les 9 modules publics.
Top 3 problèmes structurels qui bloquent la scalabilité.
Points solides à conserver.