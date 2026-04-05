---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: tasks/audits/resultats/audit_certification_edgecore.md
derniere_revision: 2026-04-05
creation: 2026-04-05 à 14:46
---
#codebase

Lance maintenant la grille de certification complète (Critères 1 à 10).
Respecte toutes les contraintes absolues listées en fin de message.
Calcule le score final mécaniquement depuis le tableau de scoring.

═══════════════════════════════════════════════════════════════
GRILLE DE CERTIFICATION — 10 CRITÈRES ÉLIMINATOIRES
═══════════════════════════════════════════════════════════════
Verdict par sous-point :
  ✅ CERTIFIÉ      — preuve dans le code, citation obligatoire
  ❌ BLOQUANT      — exigence non remplie, empêche production-ready
  ⚠️ CONDITIONNEL  — partiel, acceptable sous réserve d'action corrective

RÈGLE DE PLAFONNEMENT :
  0 ❌  → score possible ≥ 8/10
  1 ❌  → score plafonné à 7/10
  2 ❌  → score plafonné à 6/10
  3+ ❌ → REJET automatique ≤ 5/10
  Chaque ⚠️ retire 0.2 point

══════════════════════════════════════════
CRITÈRE 1 — RÉSILIENCE BROKER  [poids 20%]
══════════════════════════════════════════

1.1 Reconnexion automatique IBKR
    → Cherche dans execution/ ET live_trading/ :
      logique reconnect + backoff (fichier:ligne)
    → Si absent dans les deux : ❌ BLOQUANT

1.2 Rate limiting IBKR
    → common/ibkr_rate_limiter.py : méthode acquire() ?
    → acquire() appelé avant chaque appel API dans execution/ ?
      Cite au minimum 2 occurrences (fichier:ligne)
    → Si non utilisé dans le chemin live : ❌ BLOQUANT

1.3 Retry avec backoff exponentiel
    → common/retry.py : backoff exponentiel implémenté ?
      (fichier:ligne)
    → Utilisé dans execution/ ET data/loader.py ?
      (fichier:ligne pour chaque)

1.4 Circuit-breaker opérationnel
    → common/circuit_breaker.py : pattern CLOSED/OPEN/HALF-OPEN ?
      (fichier:ligne)
    → Branché dans le chemin d'exécution live ?
      (fichier:ligne dans execution/ ou live_trading/)

1.5 Gestion des positions orphelines
    → Connexion IBKR tombe avec position ouverte → que se passe-t-il ?
    → Cherche : reconciliation, position_sync, orphan
      dans live_trading/ et execution/
    → Cite fichier:ligne ou ❌ BLOQUANT

1.6 Double architecture execution/ vs execution_engine/
    → Qui appelle qui ? (graph d'imports réel, fichier:ligne)
    → Y a-t-il des imports croisés incohérents ?
    → execution_engine/router.py lignes ~162 et ~189 :
      slippage hardcodé ou lu depuis config/ ?

Verdict C1 : ✅ / ❌ / ⚠️  —  Score partiel : __/20

══════════════════════════════════════════════
CRITÈRE 2 — RISK MANAGEMENT CÂBLÉ  [poids 20%]
══════════════════════════════════════════════

2.1 Kill-switch 6 conditions
    → risk_engine/kill_switch.py : liste les 6 conditions
      avec (fichier:ligne) pour chacune
    → Appelé dans la boucle live_trading/runner.py ?
      (fichier:ligne)
    → Si non câblé dans live : ❌ BLOQUANT

2.2 Niveaux T1 / T2 / T3
    → Niveaux distincts ou monolithique ? (fichier:ligne)
    → T3 (halt total + alerte) : comment déclenché ?

2.3 Double architecture risk/ vs risk_engine/
    → Qui est l'implémentation réelle ? Qui est la façade ?
    → Imports croisés ? (fichier:ligne)

2.4 Synchronisation des legs de paires
    → execution_engine/router.py ou execution/ :
      leg A exécuté, leg B rejeté → que se passe-t-il ?
    → Cherche : rollback, leg_sync, atomic, compensate
    → Cite fichier:ligne ou ❌ BLOQUANT — CRITIQUE

2.5 Concentration limits câblées
    → portfolio_engine/ : max 20%/paire, 40%/secteur
      codé en dur ou config/ ? (fichier:ligne)
    → Ces limites bloquent-elles réellement un ordre ?
      (fichier:ligne dans le chemin d'envoi d'ordre)

2.6 Valeurs hardcodées dans risk et execution
    → Scan dans execution_engine/router.py, execution/,
      risk_engine/, risk/ : valeurs numériques de
      slippage/risk/threshold non lues depuis config/
    → Lister TOUTES les occurrences (fichier:ligne:valeur)

Verdict C2 : ✅ / ❌ / ⚠️  —  Score partiel : __/20

══════════════════════════════════════════════
CRITÈRE 3 — INTÉGRITÉ DU BACKTEST  [poids 15%]
══════════════════════════════════════════════

3.1 Architecture event-driven réelle
    → backtests/event_driven.py : vraie queue d'événements
      (deque / asyncio.Queue / heapq) ? (fichier:ligne)
    → Ou loop-based déguisé ?

3.2 Absence de look-ahead bias
    → signal_engine/ et strategies/ :
      tout accès .shift(-N) ou .iloc[futur]
    → Cite chaque occurrence (fichier:ligne) ou ✅ ABSENT

3.3 Cost model réaliste
    → backtests/cost_model.py (ou équivalent) :
      spread + commission + slippage modélisés ?
      (fichier:ligne pour chaque composante)
    → Lus depuis config/ ou hardcodés ?

3.4 Walk-forward configurable
    → backtests/walk_forward.py : folds IS/OOS
      configurables ? (fichier:ligne)
    → Résultats OOS stockés et comparables ?

3.5 Scripts versionnés à la racine
    → run_backtest.py, run_backtest_v17d.py,
      run_backtest_v18.py : dupliquent-ils la logique
      de backtester/ ? (fichier:ligne)
    → Trackés par git ? Couverts par .gitignore ?

3.6 Résultats de performance réels
    → Lis bt_results_v19d.txt (ou le plus récent)
    → Extrais exactement : Sharpe, MaxDD, Profit Factor,
      nb trades, période couverte, univers de symboles
    → Seuils cibles :
        Sharpe > 1.5  → ✅ / ❌
        MaxDD < 15%   → ✅ / ❌
        PF > 1.8      → ✅ / ❌
    → Lis bt_errors_v18.txt : types d'erreurs récurrentes ?

Verdict C3 : ✅ / ❌ / ⚠️  —  Score partiel : __/15

══════════════════════════════════════════════════
CRITÈRE 4 — INFRASTRUCTURE PRODUCTION  [poids 15%]
══════════════════════════════════════════════════

4.1 Docker production-grade
    → docker-compose.yml :
      - healthchecks présents ? (fichier:ligne)
      - restart: unless-stopped sur services critiques ?
      - volumes persistants pour cache/ et logs/ ?
    → Dockerfile : build multi-stage ? (fichier:ligne)
    → EDGECORE_ENV : valeur "prod" ou "production" ?
      (docker-compose.yml:ligne ET config/settings.py:ligne)
      → Incohérence entre les deux = ❌ BLOQUANT

4.2 Séparation des environnements
    → config/prod.yaml vs config/dev.yaml :
      risk limits et ports IBKR différenciés ? (fichier:ligne)
    → main.py lit EDGECORE_ENV pour switcher ? (fichier:ligne)
    → CONFIG_SETUP_COMPLETE.txt : que contient-il ?

4.3 CI/CD opérationnel
    → .github/workflows/ : liste des fichiers .yml
    → Tests exécutés en CI ? Pipeline bloque sur failure ?
      (workflow:ligne)
    → test_out.txt tracké par git → couvert par .gitignore ?

4.4 Secrets management
    → .env.example : liste toutes les variables requises
    → Scan complet password=, api_key=, token=, secret=
      dans TOUS les .py hors tests/
    → ✅ AUCUN / ❌ liste des occurrences

4.5 Fichiers de debug trackés à la racine
    → diag.py, debug_load_errors.txt, debug_symbols_snapshot.txt,
      ibkr_invalid_symbols.txt, bt_results_*.txt, bt_errors_*.txt,
      bt_out*.txt, test_out.txt, run_backtest_v*.py :
      couverts par .gitignore ? (ligne)
    → Si non → ⚠️ CONDITIONNEL obligatoire

4.6 Dossiers archivés sur main branch
    → ARCHIVED_cpp_sources/ et ARCHIVED_crypto/ présents
      sur main : CMakeLists.txt encore nécessaire ?
    → Résidu ou intentionnel ?

Verdict C4 : ✅ / ❌ / ⚠️  —  Score partiel : __/15

══════════════════════════════════════════
CRITÈRE 5 — QUALITÉ DU CODE  [poids 10%]
══════════════════════════════════════════

5.1 Cohérence des imports production
    → Cherche dans execution/, execution_engine/,
      risk_engine/, live_trading/ :
      tout import depuis research/
    → Cite fichier:ligne ou ✅ ABSENT

5.2 Package edgecore/
    → edgecore/ : quel est son rôle exact ?
    → Est-il importé par les modules de production ?
    → Relation avec les autres modules ? (fichier:ligne)

5.3 Cohérence des types
    → pyproject.toml : mypy configuré ? (ligne)
    → Erreurs mypy connues dans le codebase ?

5.4 Duplication de logique
    → strategies/ vs signal_engine/ : chevauchement ?
    → backtester/ vs backtests/ : qui fait quoi ?
      (fichier:ligne pour les classes principales)

5.5 ARCHIVED sur main branch
    → ARCHIVED_cpp_sources/ et ARCHIVED_crypto/ :
      du code mort sur main est-il importé quelque part ?
    → Cite fichier:ligne ou ✅ ISOLÉ

Verdict C5 : ✅ / ❌ / ⚠️  —  Score partiel : __/10

══════════════════════════════════════════
CRITÈRE 6 — TESTS ET COUVERTURE  [poids 10%]
══════════════════════════════════════════

6.1 Volume réel
    → Nombre de fichiers dans tests/
    → Nombre de fonctions def test_ (approximation)
    → Couverture : signal, risk, execution, backtest,
      pair_selection ? (un fichier par domaine au minimum)

6.2 Qualité des assertions
    → Ouvre 3 fichiers de test au hasard
    → Les assertions testent-elles du comportement réel
      ou juste que la fonction ne lève pas d'exception ?
    → Mocks IBKR réalistes ou MagicMock() vide ?

6.3 Tests d'intégration
    → Test end-to-end backtest ou paper trading ?
    → Kill-switch testé en conditions de drawdown simulé ?
      (fichier:ligne)

6.4 Cohérence avec test_out.txt
    → test_out.txt : combien de tests passent/échouent ?
    → Cohérent avec "295+ tests, 100% pass rate" du README ?

Verdict C6 : ✅ / ❌ / ⚠️  —  Score partiel : __/10

══════════════════════════════════════════
CRITÈRE 7 — OBSERVABILITÉ  [poids 5%]
══════════════════════════════════════════

7.1 Logging structuré
    → monitoring/ : format JSON ou structuré ? (fichier:ligne)
    → Événements critiques loggés : ordre envoyé, fill reçu,
      kill-switch déclenché, erreur broker ?
      (fichier:ligne pour chaque)

7.2 Alertes opérationnelles
    → monitoring/ : Slack / email / webhook ? (fichier:ligne)
    → Déclenchées par kill-switch T3, déconnexion,
      drawdown > seuil ? (fichier:ligne)

7.3 Métriques runtime
    → Prometheus exporter ou équivalent ? (fichier:ligne)
    → Dashboard autre que terminal Rich ? (fichier:ligne)

Verdict C7 : ✅ / ❌ / ⚠️  —  Score partiel : __/5

══════════════════════════════════════════
CRITÈRE 8 — DATA INTEGRITY  [poids 5%]
══════════════════════════════════════════

8.1 Corporate actions
    → data/loader.py : ajustements dividendes/splits ?
      (fichier:ligne)
    → delisting_guard : présent et appelé ? (fichier:ligne)
    → ibkr_invalid_symbols.txt : que contient-il ?
      Géré automatiquement ou manuellement ?

8.2 Fallback data provider
    → data/loader.py : provider autre qu'IBKR ?
      (Yahoo Finance, Polygon, CSV local) (fichier:ligne)
    → Fallback automatique ou manuel ?

8.3 Validation des données
    → NaN, gaps, données manquantes : traitement explicite ?
      (fichier:ligne dans data/ ou signal_engine/)
    → debug_load_errors.txt : types d'erreurs récurrentes ?

Verdict C8 : ✅ / ❌ / ⚠️  —  Score partiel : __/5

══════════════════════════════════════════
CRITÈRE 9 — SÉCURITÉ  [poids 3%]
══════════════════════════════════════════

9.1 Credentials dans le code
    → Scan : password=, secret=, token=, api_key=
      dans TOUS les .py (hors tests/ et .env)
    → ✅ AUCUN / ❌ liste (fichier:ligne:valeur)

9.2 Protection du mode live
    → main.py ou live_trading/runner.py :
      confirmation explicite avant démarrage live ?
      (fichier:ligne)
    → EDGECORE_ENV ou IB_PAPER_MODE vérifié au boot ?
      (fichier:ligne)

Verdict C9 : ✅ / ❌ / ⚠️  —  Score partiel : __/3

══════════════════════════════════════════════
CRITÈRE 10 — MATURITÉ OPÉRATIONNELLE  [poids 2%]
══════════════════════════════════════════════

10.1 Graceful shutdown
     → live_trading/runner.py : SIGTERM/SIGINT géré ?
       (fichier:ligne)
     → Positions fermées ou sanctuarisées avant shutdown ?

10.2 État persistant
     → persistence/ : état du portefeuille sauvegardé ?
       (fichier:ligne)
     → Réconciliation avec IBKR au redémarrage ?

10.3 Scripts opérationnels
     → scripts/ : procédures de démarrage, arrêt,
       recovery ? (fichier:ligne)

Verdict C10 : ✅ / ❌ / ⚠️  —  Score partiel : __/2

═══════════════════════════════════════════════════════════════
VERDICT FINAL
═══════════════════════════════════════════════════════════════

Tableau de scoring :
| Critère                  | Poids | Score brut | Score pondéré | Verdict |
|--------------------------|-------|------------|---------------|---------|
| 1. Résilience broker     |  20%  |    /20     |               |         |
| 2. Risk management       |  20%  |    /20     |               |         |
| 3. Intégrité backtest    |  15%  |    /15     |               |         |
| 4. Infrastructure        |  15%  |    /15     |               |         |
| 5. Qualité code          |  10%  |    /10     |               |         |
| 6. Tests                 |  10%  |    /10     |               |         |
| 7. Observabilité         |   5%  |     /5     |               |         |
| 8. Data integrity        |   5%  |     /5     |               |         |
| 9. Sécurité              |   3%  |     /3     |               |         |
| 10. Maturité ops         |   2%  |     /2     |               |         |
| **TOTAL**                | 100%  |            |   **/10**     |         |

Déductions ⚠️ appliquées : X × 0.2 = -X.X points

Blockers identifiés :
❌ BLOQUANT #1 : [description + fichier:ligne + effort correctif en jours]
❌ BLOQUANT #2 : ...

Conditionnels identifiés :
⚠️ CONDITIONNEL #1 : [action corrective + effort en jours]

CERTIFICATION FINALE :
┌──────────────────────────────────────────────────────┐
│  Score brut    : X.X / 10                            │
│  Déductions ⚠️ : -X.X                                │
│  Score final   : X.X / 10                            │
│                                                      │
│  Statut :                                            │
│    [ PRODUCTION-READY              ✅ ]              │
│    [ PRODUCTION-READY CONDITIONNEL ⚠️ ]              │
│    [ NON PRODUCTION-READY          ❌ ]              │
│                                                      │
│  Blockers restants   : X                             │
│  Conditionnels       : X                             │
│  Délai estimé        : X jours de travail            │
└──────────────────────────────────────────────────────┘

Conclusion (5 lignes max, sans complaisance) :
[Ce système peut/ne peut pas aller en production parce que...]

═══════════════════════════════════════════════════════════════
CONTRAINTES ABSOLUES
═══════════════════════════════════════════════════════════════
- Cite fichier:ligne pour CHAQUE affirmation factuelle
- Fichier absent → ❌ ABSENT, jamais de supposition sur son contenu
- Ne lis PAS les fichiers .md / .rst
- Lis les .txt UNIQUEMENT ceux listés à l'Étape 0
- "À VÉRIFIER" uniquement si la preuve est physiquement absente
- Ne jamais conclure ✅ sans la ligne de code qui prouve l'assertion
- Score calculé mécaniquement — jamais ajusté par impression générale
- La double architecture execution/ + execution_engine/ et
  risk/ + risk_engine/ doit être résolue dans le graphe d'imports
  réel, pas supposée cohérente

─────────────────────────────────────────────
SORTIE OBLIGATOIRE
─────────────────────────────────────────────
Crée le fichier :
  tasks/audits/resultats/audit_certification_edgecore.md

Crée le dossier tasks/audits/resultats/ s'il n'existe pas.

Structure du fichier :
## VERDICT FINAL
## TABLEAU DE SCORING
## BLOCKERS IDENTIFIÉS
## CONDITIONNELS
## CERTIFICATION FINALE
## CONCLUSION

Tableau synthèse :
| ID | Bloc | Description | Fichier:Ligne | Sévérité | Impact | Effort |
|----|------|-------------|---------------|----------|--------|--------|

Ce tableau récapitule UNIQUEMENT les ❌ BLOQUANT et ⚠️ CONDITIONNEL
identifiés dans les Critères 1 à 10. Les ✅ n'y figurent pas.

Sévérité : 🔴 BLOQUANT / 🟠 CONDITIONNEL / 🟡 MINEUR.

Confirme dans le chat :
"✅ tasks/audits/resultats/audit_certification_edgecore.md créé · 🔴 X · 🟠 X · 🟡 X"