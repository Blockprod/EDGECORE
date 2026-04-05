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
Respecte toutes les contraintes absolues listées ci-dessous.
Calcule le score final mécaniquement depuis le tableau de scoring.

═══════════════════════════════════════════════════════════════
GRILLE DE CERTIFICATION — 10 CRITÈRES ÉLIMINATOIRES
═══════════════════════════════════════════════════════════════
Pour chaque critère, rends un verdict binaire :
  ✅ CERTIFIÉ      — exigence remplie, preuve dans le code
  ❌ BLOQUANT      — exigence non remplie, empêche production-ready
  ⚠️ CONDITIONNEL  — rempli partiellement, acceptable sous réserve
                     d'une action corrective listée

RÈGLE DE CERTIFICATION FINALE :
  - 0 ❌ BLOQUANT  → score possible ≥ 8/10
  - 1 ❌ BLOQUANT  → score plafonné à 7/10
  - 2 ❌ BLOQUANT  → score plafonné à 6/10
  - 3+ ❌ BLOQUANT → REJET automatique, score ≤ 5/10
  - Chaque ⚠️ CONDITIONNEL retire 0.2 point

══════════════════════
CRITÈRE 1 — RÉSILIENCE BROKER  [poids : 20%]
══════════════════════
1.1 Reconnexion automatique IBKR
    → Cherche dans execution/ibkr.py et live_trading/runner.py
    → Doit exister : logique de reconnect avec backoff
    → Cite fichier:ligne ou écris ❌ ABSENT

1.2 Rate limiting IBKR respecté
    → common/ibkr_rate_limiter.py : méthode acquire() présente ?
    → acquire() appelé AVANT chaque appel API dans execution/ ?
    → Cite au moins 2 occurrences fichier:ligne

1.3 Retry avec backoff exponentiel
    → common/retry.py : implémentation backoff ? (fichier:ligne)
    → Utilisé dans execution/ ET data/loader.py ? (fichier:ligne)

1.4 Circuit-breaker opérationnel
    → common/circuit_breaker.py : pattern CLOSED/OPEN/HALF-OPEN ?
    → Branché sur le chemin d'exécution live ? (fichier:ligne)

1.5 Gestion des positions orphelines
    → Que se passe-t-il si connexion IBKR tombe avec position ouverte ?
    → Cherche : reconciliation, position_sync, orphan dans
      live_trading/ et execution/
    → Cite fichier:ligne ou écris ❌ ABSENT

Verdict Critère 1 : ✅ / ❌ / ⚠️
Score partiel : __/20

══════════════════════
CRITÈRE 2 — RISK MANAGEMENT CÂBLÉ  [poids : 20%]
══════════════════════
2.1 Kill-switch 6 conditions
    → risk_engine/kill_switch.py : liste les 6 conditions
      effectivement implémentées (fichier:ligne pour chacune)
    → Le kill-switch est-il appelé dans la boucle live ?
      (fichier:ligne dans live_trading/runner.py)

2.2 Kill-switch niveaux T1/T2/T3
    → Niveaux distincts implémentés ou monolithique ?
    → T3 (halt total + alert) : déclenché comment ?

2.3 Synchronisation des legs de paires
    → execution_engine/router.py ou execution/ibkr.py :
    → Que se passe-t-il si leg A exécuté, leg B rejeté ?
    → Cherche : rollback, leg_sync, atomic, compensate
    → Cite fichier:ligne ou écris ❌ ABSENT — CRITIQUE

2.4 Concentration limits
    → portfolio_engine/ ou risk_engine/ : max 20% par paire,
      40% par secteur — codé en dur ou configurable ?
    → Ces limites bloquent-elles réellement un ordre ? (fichier:ligne)

2.5 Valeurs hardcodées dans risk/execution
    → Cherche dans execution_engine/router.py lignes ~162 et ~189
    → Des valeurs numériques de slippage/risk sont-elles
      hardcodées plutôt que lues depuis config/ ?
    → Lister TOUTES les occurrences trouvées (fichier:ligne:valeur)

Verdict Critère 2 : ✅ / ❌ / ⚠️
Score partiel : __/20

══════════════════════
CRITÈRE 3 — INTÉGRITÉ DU BACKTEST  [poids : 15%]
══════════════════════
3.1 Architecture event-driven réelle
    → backtests/event_driven.py : vraie queue d'événements
      (deque / asyncio.Queue / heapq) ? (fichier:ligne)
    → Ou logique loop-based classique déguisée ?

3.2 Absence de look-ahead bias
    → Les features/signaux sont-ils calculés STRICTEMENT
      sur données[t-n:t] sans accès à données[t+x] ?
    → Cherche dans signal_engine/ et strategies/ :
      tout accès .shift(-N) ou .iloc[future_index]
    → Cite chaque occurrence trouvée (fichier:ligne)

3.3 Cost model réaliste
    → backtests/cost_model.py : spread, commission, slippage
      modélisés ? (fichier:ligne pour chaque composante)
    → Les coûts sont-ils lus depuis config/ ou hardcodés ?

3.4 Walk-forward sur données réelles
    → backtests/walk_forward.py : nombre de folds, taille
      IS/OOS — configurables ? (fichier:ligne)
    → Les résultats OOS sont-ils stockés et comparables ?

3.5 Résultats les plus récents
    → Lis le fichier bt_results_*.txt le plus récent
    → Extrais : Sharpe, MaxDD, Profit Factor, nb trades,
      période couverte
    → Seuils cibles : Sharpe > 1.5, MaxDD < 15%, PF > 1.8
    → Verdict sur chaque seuil : ✅ / ❌

Verdict Critère 3 : ✅ / ❌ / ⚠️
Score partiel : __/15

══════════════════════
CRITÈRE 4 — INFRASTRUCTURE PRODUCTION  [poids : 15%]
══════════════════════
4.1 Docker production-grade
    → docker-compose.yml : healthchecks présents ? (fichier:ligne)
    → restart: unless-stopped sur tous les services critiques ?
    → Volumes persistants pour cache/ et logs/ ?
    → Variable EDGECORE_ENV : valeur "prod" correcte
      ou "production" invalide ? (fichier:ligne — vérifier
      cohérence avec config/settings.py)

4.2 Séparation des environnements
    → config/prod.yaml distinct de config/dev.yaml ?
    → Les risk limits et ports IBKR sont-ils différenciés ?
    → main.py lit-il EDGECORE_ENV pour switcher la config ?

4.3 CI/CD opérationnel
    → .github/workflows/ : liste les fichiers .yml présents
    → Les tests s'exécutent-ils en CI ? (workflow:ligne)
    → Le pipeline bloque-t-il sur test failure ?
    → Présence d'un lint/mypy dans le pipeline ?

4.4 Secrets management
    → .env.example : liste les variables requises
    → Des credentials sont-ils hardcodés dans le code source ?
      (cherche : password=, api_key=, token= dans tous les .py)

Verdict Critère 4 : ✅ / ❌ / ⚠️
Score partiel : __/15

══════════════════════
CRITÈRE 5 — QUALITÉ DU CODE  [poids : 10%]
══════════════════════
5.1 Double architecture non résolue
    → execution/ ET execution_engine/ coexistent-ils ?
    → risk/ ET risk_engine/ coexistent-ils ?
    → Si oui : qui appelle quoi ? (graph d'imports réel)
    → Y a-t-il des imports croisés incohérents ?

5.2 Fichiers de debug à la racine
    → diag.py, debug_load_errors.txt, ibkr_invalid_symbols.txt
      sont-ils trackés par git ?
    → Un .gitignore couvre-t-il les bt_results_*.txt
      et bt_errors_*.txt ?

5.3 Versioning manuel des backtests
    → run_backtest_v17d.py, run_backtest_v18.py à la racine :
      présents et trackés ?
    → Ces scripts dupliquent-ils la logique de backtester/ ?

5.4 Cohérence des types
    → Mypy configuré dans pyproject.toml ou mypy.ini ?
    → Des erreurs mypy sont-elles connues ?

5.5 Imports depuis research/ dans des modules de production
    → Cherche dans execution/, risk_engine/, live_trading/ :
      tout import depuis research/
    → Cite fichier:ligne ou confirme ✅ ABSENT

Verdict Critère 5 : ✅ / ❌ / ⚠️
Score partiel : __/10

══════════════════════
CRITÈRE 6 — TESTS ET COUVERTURE  [poids : 10%]
══════════════════════
6.1 Volume et qualité des tests
    → Nombre total de fichiers de tests dans tests/
    → Nombre de test functions (grep def test_)
    → Les tests couvrent-ils : signal, risk, execution, backtest ?

6.2 Tests meaningful vs coverage theater
    → Sélectionne 3 fichiers de test au hasard
    → Les assertions testent-elles du comportement réel
      ou juste que la fonction ne plante pas ?
    → Présence de mocks IBKR réalistes ou juste MagicMock() vide ?

6.3 Tests d'intégration
    → Existe-t-il des tests end-to-end backtest ou paper trading ?
    → Les tests de risk_engine testent-ils le kill-switch
      en conditions de drawdown simulé ?

Verdict Critère 6 : ✅ / ❌ / ⚠️
Score partiel : __/10

══════════════════════
CRITÈRE 7 — OBSERVABILITÉ  [poids : 5%]
══════════════════════
7.1 Logging structuré
    → Format JSON ou structuré dans monitoring/ ou config/ ?
    → Tous les événements critiques loggés :
      ordre envoyé, fill reçu, kill-switch déclenché,
      erreur broker ? (fichier:ligne pour chaque)

7.2 Alertes opérationnelles
    → monitoring/ : Slack/email/webhook implémenté ?
    → Alertes déclenchées par : kill-switch T3, connexion
      perdue, drawdown > seuil ? (fichier:ligne)

7.3 Métriques temps réel
    → Prometheus exporter ou équivalent dans monitoring/ ?
    → Dashboard opérationnel (pas juste un Rich terminal) ?

Verdict Critère 7 : ✅ / ❌ / ⚠️
Score partiel : __/5

══════════════════════
CRITÈRE 8 — DATA INTEGRITY  [poids : 5%]
══════════════════════
8.1 Corporate actions et delisting
    → data/loader.py : ajustements dividendes/splits gérés ?
    → data/ : delisting_guard présent et appelé ? (fichier:ligne)

8.2 Fallback data provider
    → data/loader.py supporte-t-il un provider autre qu'IBKR ?
    → Le fallback est-il automatique ou manuel ?

8.3 Validation des données en entrée
    → Données manquantes, NaN, gaps de marché :
      traitement explicite ? (fichier:ligne)
    → Validation du format OHLCV avant calcul des signaux ?

Verdict Critère 8 : ✅ / ❌ / ⚠️
Score partiel : __/5

══════════════════════
CRITÈRE 9 — SÉCURITÉ  [poids : 3%]
══════════════════════
9.1 Credentials
    → Scan complet : password=, secret=, token=, api_key=
      dans TOUS les .py (hors .env et tests/)
    → Résultat : ✅ AUCUN trouvé / ❌ liste des occurrences

9.2 Mode live protégé
    → main.py ou live_trading/runner.py : confirmation
      explicite requise avant démarrage en mode live ?
    → Variable IB_PAPER_MODE ou EDGECORE_ENV vérifiée
      au démarrage ? (fichier:ligne)

Verdict Critère 9 : ✅ / ❌ / ⚠️
Score partiel : __/3

══════════════════════
CRITÈRE 10 — MATURITÉ OPÉRATIONNELLE  [poids : 2%]
══════════════════════
10.1 Runbook opérationnel
     → NE PAS lire les .md
     → Cherche dans scripts/ : procédures de démarrage,
       arrêt propre, recovery ? (fichier:ligne)

10.2 Arrêt propre (graceful shutdown)
     → live_trading/runner.py : signal SIGTERM/SIGINT géré ?
     → Les positions sont-elles fermées ou sanctuarisées
       avant shutdown ? (fichier:ligne)

10.3 État persistant entre redémarrages
     → persistence/ : état du portefeuille sauvegardé ?
     → Au redémarrage, le système réconcilie-t-il avec IBKR ?

Verdict Critère 10 : ✅ / ❌ / ⚠️
Score partiel : __/2

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

Blockers identifiés :
❌ BLOQUANT #1 : [description + fichier:ligne]
❌ BLOQUANT #2 : [description + fichier:ligne]

Conditionnels identifiés :
⚠️ CONDITIONNEL #1 : [action corrective requise + effort en jours]

CERTIFICATION FINALE :
┌─────────────────────────────────────────────────────┐
│  Score : X.X / 10                                   │
│  Statut : [ PRODUCTION-READY ✅ ]                   │
│           [ PRODUCTION-READY SOUS CONDITIONS ⚠️ ]   │
│           [ NON PRODUCTION-READY ❌ ]                │
│                                                      │
│  Blockers restants   : X                            │
│  Conditionnels       : X                            │
│  Délai estimé        : X jours de travail           │
└─────────────────────────────────────────────────────┘

Conclusion (5 lignes max, sans complaisance) :
[Ce système peut/ne peut pas aller en production parce que...]

═══════════════════════════════════════════════════════════════
CONTRAINTES ABSOLUES
═══════════════════════════════════════════════════════════════
- Cite fichier:ligne pour CHAQUE affirmation factuelle
- Si un fichier est absent : ❌ ABSENT — ne suppose pas son contenu
- Ne lis PAS les fichiers .md / .rst
- Lis les .txt UNIQUEMENT : bt_results_*.txt, bt_errors_*.txt,
  bt_best.txt, bt_out*.txt, ibkr_invalid_symbols.txt,
  debug_load_errors.txt
- "À VÉRIFIER" uniquement si la preuve est physiquement absente
- Ne jamais conclure ✅ sans citer la ligne de code qui prouve
  l'assertion
- Le score final est calculé mécaniquement depuis le tableau —
  jamais ajusté à la hausse par impression générale

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

Sévérité : 🔴 BLOQUANT / 🟠 CONDITIONNEL / 🟡 MINEUR.

Confirme dans le chat :
"✅ tasks/audits/resultats/audit_certification_edgecore.md créé · 🔴 X · 🟠 X · 🟡 X"