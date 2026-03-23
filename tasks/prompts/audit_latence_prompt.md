---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: tasks/audits/AUDIT_LATENCE_EDGECORE.md
derniere_revision: 2026-03-23
usage: audit latence institutionnel avant mise en production live
---

#codebase

Tu es un Senior Low-Latency Engineer spécialisé en systèmes
de trading algorithmique institutionnel (stat-arb, pairs trading,
prop trading). Tu as une expérience concrète en optimisation
de latence sur des stacks Python/Cython/threading connectés à des
brokers institutionnels (IBKR TWS/Gateway, protocole API EClient).

─────────────────────────────────────────────
ÉTAPE 0 — VÉRIFICATION PRÉALABLE
─────────────────────────────────────────────
Vérifie si ce fichier existe déjà :
  tasks/audits/AUDIT_LATENCE_EDGECORE.md

Si trouvé :
"⚠️ Audit latence existant détecté :
 Fichier : tasks/audits/AUDIT_LATENCE_EDGECORE.md
 Date    : [date modification]
 Lignes  : [nombre approximatif]

 [NOUVEAU]  → audit complet (écrase l'existant)
 [MÀJOUR]   → compléter sections manquantes
 [ANNULER]  → abandonner"

Si absent → démarrer directement :
"✅ Aucun audit latence existant. Démarrage..."

─────────────────────────────────────────────
MISSION
─────────────────────────────────────────────
Réaliser un audit EXCLUSIVEMENT centré sur
la latence du système EDGECORE.

L'objectif n'est pas la performance générique —
c'est d'identifier chaque milliseconde perdue
dans le pipeline de trading pair-à-pair qui peut
impacter la qualité d'exécution et le slippage réel.

EDGECORE est un système de stat-arb (pairs trading)
basé sur la cointégration. La latence critique se situe
sur deux chemins distincts :
  A) Chemin bar → signal → ordre (temps réel)
  B) Chemin pair re-discovery (coûteux, périodique)

─────────────────────────────────────────────
PÉRIMÈTRE STRICT
─────────────────────────────────────────────
Tu analyses UNIQUEMENT :
- Le chemin critique bar → signal → ordre → confirmation
- La latence de la re-découverte de paires (PairDiscoveryEngine)
- L'utilisation réelle du module Cython vs stub Python
- La latence des appels IBKR (TWS/Gateway port 4002)
- La contention des threads (threading.Lock, ThreadPoolExecutor)
- Les I/O synchrones dans des chemins critiques
- La latence du chargement des données (IBKR + Yahoo Finance fallback)
- La qualité et la fraîcheur des données OHLCV

Tu n'analyses PAS :
- La validité statistique des signaux de cointégration
- La sécurité des credentials IBKR
- L'organisation des modules ou la couverture de tests
- Les paramètres de risque (entry_z, drawdown %)

─────────────────────────────────────────────
CONTRAINTES ABSOLUES
─────────────────────────────────────────────
- Ne lis aucun fichier .md, .txt, .rst existant
- Cite fichier:ligne pour chaque problème
- Mesure ou estime chaque latence en millisecondes
- Distingue latence MESURABLE (code) vs ESTIMÉE (archi)
- Écris "À MESURER EN PRODUCTION" si non quantifiable
  depuis le code statique
- Classe chaque problème :
  🔴 Critique (>10ms sur le chemin critique A)
  🟠 Majeur (1-10ms ou latence non déterministe)
  🟡 Mineur (<1ms ou hors chemin critique A)

─────────────────────────────────────────────
BLOC 1 — CARTOGRAPHIE DES CHEMINS CRITIQUES
─────────────────────────────────────────────
EDGECORE a deux chemins critiques de natures très
différentes. Trace-les séparément.

1.1 Chemin A — Boucle temps réel (bar → ordre)
    Trace le chemin complet depuis la réception
    d'une nouvelle barre de prix jusqu'à l'envoi
    de l'ordre chez IBKR. Chaque étape du pipeline
    defini dans LiveTradingRunner doit apparaître :

    - DataLoader.load_price_data()
    - UniverseManager (filtre liquidité)
    - SignalGenerator.generate() qui compose :
        SpreadModel → ZScoreCalculator
        → AdaptiveThresholdEngine → StationarityMonitor
        → RegimeDetector / MarkovRegimeDetector
        → MomentumOverlay (z×0.70 + momentum×0.30)
    - PositionRiskManager → PortfolioRiskManager → KillSwitch
    - PortfolioAllocator (Kelly criterion)
    - ExecutionRouter → {Paper|IBKR}ExecutionEngine
    - BrokerReconciler

    Pour chaque étape : module + fichier:ligne + latence ms.

1.2 Chemin B — Re-découverte de paires (périodique)
    PairDiscoveryEngine est le composant le plus
    computationnellement intensif du système :
    - Complexité : O(N²) paires à tester
    - Chaque test : cointegration_fast.pyx (Cython) +
      adfuller (statsmodels)
    - Fréquence : toutes les 24h (pair_rediscovery_hours)
    - Pendant la re-découverte, le reste du pipeline
      est-il bloqué ? Y a-t-il un thread séparé ?

    Estime : temps de re-découverte pour N=50 symboles
    (≈ 1225 paires possibles) vs N=20 (≈ 190 paires).

1.3 Tableau de latence estimée

```
    ÉTAPE                        | MODULE                          | LATENCE EST.
    -----------------------------|----------------------------------|-------------
    Chargement données IBKR      | data/loader.py:XX               | ~X ms/symbole
    Yahoo Finance fallback        | data/loader.py:XX               | ~X ms
    Filtre univers                | universe/manager.py:XX          | ~X ms
    SpreadModel + hedgeRatio      | models/spread.py:XX             | ~X ms
    ZScore (rolling)              | signal_engine/zscore.py:XX      | ~X ms
    AdaptiveThreshold             | signal_engine/adaptive.py:XX    | ~X ms
    RegimeDetector                | models/regime_detector.py:XX    | ~X ms
    MomentumOverlay               | signal_engine/momentum.py:XX    | ~X ms
    Risk checks (3 niveaux)       | risk_engine/...                 | ~X ms
    Kelly allocation              | portfolio_engine/allocator.py:XX| ~X ms
    ExecutionRouter submit        | execution_engine/router.py:XX   | ~X ms
    IBKR placeOrder               | execution/ibkr_engine.py:XX     | ~X ms
    BrokerReconciler (5 min)      | ...                             | ~X ms
    TOTAL chemin A                |                                  | ~X ms
```

Livrable : schéma textuel des deux chemins critiques
avec latence estimée par étape.

─────────────────────────────────────────────
BLOC 2 — CYTHON VS STUB : RISQUE DE LATENCE CACHÉ
─────────────────────────────────────────────
EDGECORE dispose d'UN SEUL module Cython critique :
  models/cointegration_fast.pyx
  → compilé en cointegration_fast.cp311-win_amd64.pyd

C'est le cœur computationnel du système —
il accélère les tests de cointégration Engle-Granger
utilisés dans PairDiscoveryEngine.

2.1 Détection du fallback Python en production
    - Dans models/__init__.py ou pair_selection/,
      comment cointegration_fast est-il importé ?
      (try/except ImportError ? import conditionnel ?)
    - Si le .pyd n'est pas disponible,
      le système bascule-t-il silencieusement sur
      models/cointegration.py (pure Python) ?
    - Y a-t-il un log CRITICAL ou une alerte si
      le stub Python est utilisé à la place du Cython ?
    - Cette vérification est-elle faite au démarrage
      de LiveTradingRunner ou seulement au premier appel ?

2.2 Quantification de l'impact latence
    Pour le module Cython vs stub Python :
    - engle_granger_fast() Cython vs Python pur :
      gain estimé par test (en ms)
    - Impact sur la re-découverte complète
      (N=50 symboles ≈ 1225 appels) :
      Cython ~X ms total vs Python ~X ms total
    - Le gain Cython est-il annulé par l'appel
      statsmodels.adfuller() qui reste Python pur
      à l'intérieur du .pyx ?

2.3 Vérification du flag CYTHON_AVAILABLE
    - Où est défini/vérifié CYTHON_AVAILABLE ou
      équivalent dans le codebase ?
    - Est-il loggé en CRITICAL si Cython est absent ?
    - Le système devrait-il refuser de démarrer en
      mode live sans le .pyd compilé ?
    - La commande de recompilation
      `venv\Scripts\python.exe setup.py build_ext --inplace`
      est-elle documentée dans le runbook ?

Livrable : tableau CYTHON ACTIF / STUB ACTIF / AMBIGU
avec impact latence estimé pour la re-découverte.

─────────────────────────────────────────────
BLOC 3 — LATENCE DES APPELS IBKR
─────────────────────────────────────────────
3.1 Architecture de connexion IBKR
    - IBGatewaySync vs ib_insync : lequel est utilisé
      pour les données historiques, lequel pour les ordres ?
    - IBGatewaySync crée-t-il une nouvelle connexion
      à chaque appel load_price_data() ou réutilise-t-il
      une connexion persistante ?
    - Quelle est la latence d'établissement de la connexion
      IBGatewaySync (port 4002, host 127.0.0.1) ?
    - Le pool de client_ids (2001-2008) est-il suffisant
      pour un chargement multi-threadé sans collision ?

3.2 Chargement séquentiel des données avec sleep hardcodé
    Dans data/loader.py, load_price_data() boucle sur
    les symboles SÉQUENTIELLEMENT avec un sleep fixe :
      `time.sleep(0.5)  # IBKR rate limiting`
    - Pour N=50 symboles, ce sleep seul = 25 secondes.
    - Ce chargement est-il sur le chemin critique A
      (exécuté à chaque bar) ?
    - Pourquoi 0.5s au lieu d'utiliser le TokenBucketRateLimiter
      existant dans execution/rate_limiter.py ?
    - DataLoader utilise-t-il ThreadPoolExecutor pour
      paralléliser les appels IBKR ? Si oui, le rate limiter
      est-il partagé entre les threads ?

3.3 🔴 VIOLATION INSTITUTIONNELLE — Sources de données tierces
    Un système de trading institutionnel utilise EXCLUSIVEMENT
    les données de son broker. Toute dépendance à une source
    externe (Yahoo Finance, yfinance, Alpha Vantage, etc.)
    constitue une violation institutionnelle grave :
      • Données non certifiées / non auditables
      • Timestamps divergents → biais de hedge ratio
      • Biais de survivorship non contrôlé
      • Latence HTTP externe non déterministe (100ms-5s)
      • Indisponibilité possible sans préavis
      • Aucun SLA de qualité ou de fraîcheur

    Audite exhaustivement la présence de ces sources :
    - Cherche dans TOUT le codebase : yfinance, yahoo,
      Alpha Vantage, Quandl, pandas_datareader, requests
      vers des URLs externes de données de marché.
    - Identifie chaque fichier:ligne où une source tierce
      est importée ou appelée.
    - Détermine si cette source est sur le chemin critique A
      (exécuté à chaque bar) ou hors-ligne (backtest only).
    - Si trouvé EN PRODUCTION ou EN LIVE : signaler 🔴 Critique
      avec recommandation de suppression immédiate et
      remplacement par reqHistoricalData IBKR exclusivement.
    - Si trouvé UNIQUEMENT dans backtests/ ou research/ :
      signaler 🟡 Mineur avec recommandation d'isolation
      stricte (jamais importé depuis un module de production).

3.4 Envoi d'ordre et confirmation de fill
    - Comment l'ordre est-il acheminé dans
      IBKRExecutionEngine ? (placeOrder IBKR API)
    - Le rate limiter (TokenBucketRateLimiter 45/s, burst 10)
      est-il appliqué AVANT chaque placeOrder ?
    - Y a-t-il une attente de confirmation de fill avant
      de continuer le cycle (blocking wait) ?
    - Les erreurs informatives IBKR (2104, 2106, 2158)
      introduisent-elles de la latence (retry, sleep) ?
    - Les erreurs de données historiques (162, 200, 354)
      déclenchent-elles un cancelHistoricalData immédiat
      ou un wait avec timeout ?

3.5 Rate limiting et priorité des ordres
    - Le TokenBucketRateLimiter est-il partagé entre
      les ordres et les requêtes de données ?
    - Si un chargement de données consomme tous les tokens
      (45/s), les ordres peuvent-ils être bloqués ?
    - Y a-t-il un mécanisme de priorité
      (ordres > données > réconciliation) ?
    - Le BrokerReconciler (toutes les 5 min) consomme
      combien de tokens IBKR par réconciliation ?

Livrable : liste des appels IBKR bloquants avec
latence estimée et fichier:ligne.

─────────────────────────────────────────────
BLOC 4 — THREADING ET CONTENTION DU GIL
─────────────────────────────────────────────
⚠️ EDGECORE est un système THREAD-BASED (pas asyncio).
Le risque n'est PAS la starvation d'une event loop —
c'est la CONTENTION DU GIL Python et des locks :
un thread bloqué peut retarder tout le cycle.

4.1 Locks sur le chemin critique
    - LiveTradingRunner._positions_lock (threading.Lock) :
      quelle est la durée de la section critique protégée ?
      Le lock est-il tenu pendant les appels IBKR ou
      seulement pendant la manipulation de _positions ?
    - Y a-t-il d'autres locks dans le chemin critique A ?
      (SpreadModel, ZScoreCalculator, etc.)
    - Le ThreadPoolExecutor dans DataLoader crée-t-il
      de la contention si les threads partagent un lock ?

4.2 Sections CPU-intensives sur le thread principal
    - Les calculs du signal pipeline (SpreadModel,
      ZScoreCalculator, Kalman filter, StationarityMonitor,
      RegimeDetector, MarkovRegimeDetector) sont-ils
      exécutés sur le thread principal de LiveTradingRunner ?
    - Ces calculs bloquent-ils le thread susceptible
      de recevoir des callbacks IBKR ?
    - Kalman filter (models/kalman_hedge.py) :
      quelle est la complexité par mise à jour ?
      Pour N paires actives, le coût total est-il linéaire ?
    - MarkovRegimeDetector : est-il re-entraîné à chaque
      bar ou sur un schedule séparé ?

4.3 ThreadPoolExecutor — chargement parallèle des données
    - DataLoader utilise-t-il un pool de threads pour
      les appels IBGatewaySync ?
    - Si oui, combien de workers max ? Le pool est-il
      réutilisé entre les bars ou recréé ?
    - La création d'un ThreadPoolExecutor à chaque bar
      introduit-elle une latence d'initialisation ?
    - Les threads de données peuvent-ils contenir des
      connexions IBKR actives et épuiser le client_id pool ?

4.4 Cadence de la boucle principale
    - LiveTradingRunner boucle-t-il avec un sleep fixe
      (bar_interval_seconds = 60) ou attend-il un
      événement (nouveau bar disponible) ?
    - Si un cycle prend plus de 60s, le bar suivant
      est-il manqué ? Y a-t-il un mécanisme de catchup ?
    - Les risk checks (KillSwitch, PortfolioRiskManager)
      sont-ils exécutés à chaque bar ou sur un timer ?

─────────────────────────────────────────────
BLOC 5 — LATENCE DU PIPELINE SIGNAL
─────────────────────────────────────────────
Le signal pipeline d'EDGECORE est particulièrement
riche (6 sous-composants). Chaque composant ajoute
de la latence — certains de manière non déterministe.

5.1 SpreadModel — coût par mise à jour
    - models/spread.py : comment est calculé le hedge ratio ?
      (OLS statique, Kalman dynamique, ou les deux ?)
    - Le KalmanHedgeRatioTracker est-il mis à jour
      à chaque bar pour TOUTES les paires actives ?
    - Coût estimé d'un update Kalman pour une paire.

5.2 ZScoreCalculator — rolling window
    - signal_engine/zscore.py : quelle est la taille
      de la fenêtre rolling ? (lookback_period)
    - Le calcul rolling est-il fait via pandas
      (rolling().mean()/std()) ou numpy ?
    - Pour N=10 paires actives avec window=100,
      quel est le coût total en ms ?

5.3 StationarityMonitor — ADF test périodique
    - models/stationarity_monitor.py : à quelle
      fréquence l'ADF test est-il relancé ?
    - L'ADF (statsmodels, expensive) est-il appelé
      à chaque bar ou en cache avec TTL ?
    - Si ADF est appelé à chaque bar pour 10 paires :
      latence estimée (statsmodels adfuller ≈ 2-5ms/appel) ?

5.4 RegimeDetector + MarkovRegimeDetector
    - models/regime_detector.py et markov_regime.py :
      les deux sont-ils appelés à chaque bar ?
    - MarkovRegimeDetector nécessite-t-il un re-fit
      du modèle HMM à chaque bar ?
      (sklearn HMM fit ≈ 10-100ms selon historique)
    - Si le MarkovRegimeDetector est lent, y a-t-il
      un cache du régime courant avec TTL ?

5.5 StructuralBreakDetector
    - models/structural_break.py : est-il appelé
      à chaque bar ou périodiquement ?
    - Tests de rupture structurelle (Chow, CUSUM) :
      coût estimé par appel.

5.6 MomentumOverlay — combinaison finale
    - signal_engine/momentum.py : la combinaison
      z-score × 0.70 + momentum × 0.30, est-elle
      calculée sur les prix bruts ou les rendements ?
    - Lookback du momentum (N barres) : quelle est
      la taille de la fenêtre de calcul ?

─────────────────────────────────────────────
BLOC 6 — I/O SYNCHRONES SUR LE CHEMIN CRITIQUE
─────────────────────────────────────────────
6.1 Logging structuré (structlog) sur le chemin critique
    - structlog.get_logger() est utilisé partout.
      Les handlers de log (console, fichier, JSON)
      sont-ils synchrones ou asynchrones ?
    - Y a-t-il des logs au niveau DEBUG actifs en
      production qui ajoutent de la latence à chaque bar ?
    - Les logs en mode prod sont-ils filtrés à INFO
      au minimum pour réduire les I/O ?

6.2 Persistance d'état sur le chemin critique
    - KillSwitch persiste son état dans
      data/kill_switch_state.bak : cet I/O est-il
      synchrone et sur le chemin critique A ?
    - AuditTrail écrit-il à chaque bar ou en batch ?
      L'écriture est-elle synchrone (fsync) ?
    - Les positions sont-elles persistées à chaque
      modification ou en batch à intervalle fixe ?

6.3 Cache de paires (cache/pairs/)
    - Les paires cointégrées sont-elles mises en cache
      sur disque entre les runs ?
    - Le chargement du cache au démarrage est-il
      synchrone et bloquant avant le premier cycle ?
    - En production, si le cache est périmé, la
      re-découverte complète est-elle déclenchée
      AVANT le premier cycle (bloque le démarrage) ?

6.4 Email/Slack alertes
    - live_trading/runner.py initialise _email_alerter
      et _slack_alerter. Les alertes sont-elles
      envoyées sur le thread principal (bloquant) ?
    - Si le serveur SMTP est lent, l'alerte peut-elle
      bloquer le cycle en cours ?

─────────────────────────────────────────────
BLOC 7 — QUALITÉ ET FRAÎCHEUR DES DONNÉES
─────────────────────────────────────────────
7.1 Fraîcheur des données OHLCV
    - Comment l'âge des données est-il mesuré ?
      Y a-t-il un seuil d'obsolescence au-delà duquel
      le pipeline refuse de générer des signaux ?
    - Les données sont-elles timestampées à la réception
      (IBGatewaySync) ou au moment du calcul du signal ?
    - Le timestamp IBKR et le timestamp local sont-ils
      synchronisés ? Un offset d'horloge peut-il
      introduire de fausses données "fraîches" ?

7.2 Source unique et certifiée : IBKR reqHistoricalData
    En production, IBKR est la SEULE source autorisée.
    - Pour les données daily (1d bars), IBKR
      reqHistoricalData retourne des données jusqu'à
      quand ? Y a-t-il un délai après la clôture du marché ?
    - Les barres IBKR sont-elles ADJUSTED_LAST (ajustées
      pour dividendes/splits) ou RAW ? Un changement
      de type peut créer une divergence silencieuse
      des hedge ratios entre sessions.
    - Les OHLCV retournés sont-ils identiques entre
      deux appels successifs au même timestamp ?
      (idempotence — critique pour la reproductibilité
      des signaux de cointégration)
    - En cas d'échec de reqHistoricalData (erreur 162,
      200, 354), le pipeline doit-il refuser de trader
      ou peut-il utiliser les données du bar précédent ?
      Quelle est la politique actuelle du code ?

7.3 Buffer et queue de données
    - Y a-t-il un buffer entre la réception IBKR
      et l'entrée dans SignalGenerator ?
    - Le buffer peut-il contenir des données périmées
      si le traitement d'un bar est trop long ?
    - DataLoader.load_price_data() retourne-t-il
      les données du bar ACTUEL ou du bar PRÉCÉDENT ?
      (risque de lookahead si mal calibré)

─────────────────────────────────────────────
BLOC 8 — RÉSILIENCE ET LATENCE DE RÉCUPÉRATION
─────────────────────────────────────────────
8.1 Temps de reconnexion IBKR
    - En cas de déconnexion TWS/Gateway, IBGatewaySync
      gère-t-il une reconnexion automatique ?
    - Si IBGatewaySync crée une nouvelle connexion
      à chaque appel load_price_data(), une reconnexion
      n'est-elle pas automatique mais à quel coût ?
    - Les ordres envoyés juste avant une déconnexion
      sont-ils annulés ou maintenus côté IBKR ?
    - Pendant la reconnexion, le pipeline est-il
      suspendu ou continue-t-il avec des données périmées ?

8.2 Temps de démarrage à froid
    - Depuis `runner.start()` jusqu'au premier ordre :
      combien d'étapes bloquantes existent ?
      (load_price_data → pair_discovery → signal init)
    - La re-découverte au démarrage pour N=50 symboles
      est-elle réalisée en foreground (bloque) ou
      en background (permet des cycles sans paires) ?
    - Y a-t-il un mode "warm start" chargeant les
      paires depuis cache/pairs/ pour accélérer ?

8.3 Latence du KillSwitch et cycle de récupération
    - Quand KillSwitch.trigger() est appelé :
      combien de temps avant que TOUS les ordres
      ouverts soient fermés ?
    - Après un halt Tier 2 (15% drawdown), quel est
      le délai minimum de redémarrage configuré ?
    - Le BrokerReconciler (5 min) peut-il masquer
      des positions divergentes pendant ce délai ?

─────────────────────────────────────────────
SYNTHÈSE FINALE
─────────────────────────────────────────────
Tableau complet :
| ID | Bloc | Description | Fichier:Ligne |
| Sévérité | Latence estimée | Effort correction |

Sévérité :
🔴 Critique (>10ms chemin critique A ou risque de blocage)
🟠 Majeur (1-10ms ou latence non déterministe)
🟡 Mineur (<1ms ou hors chemin critique A)

Produit également :

1. Budget latence total estimé

```
   Cadence cible (bar_interval) : 60 000 ms
   Latence bar → ordre (cible)  : < 500 ms
   Latence bar → ordre (actuel) : ~ X ms
   Marge restante par cycle     : ~ X ms
   Risque de dépassement        : [OUI / NON / CONDITIONNEL]
```

2. Latence spécifique re-découverte de paires

```
   N=20 symboles (~190 paires)   : ~ X ms
   N=50 symboles (~1225 paires)  : ~ X ms
   N=100 symboles (~4950 paires) : ~ X ms
   Impact si Cython absent (stub): × X plus lent
```

3. Top 3 optimisations prioritaires
   Les 3 corrections qui réduiraient le plus
   la latence sur le chemin critique A.

4. Ce qui est déjà optimal
   Mécanismes de latence déjà bien gérés
   à ne pas modifier.

5. Recommandations de mesure en production
   Comment instrumenter le code pour mesurer
   la latence réelle (non estimée) :
   - Points de mesure recommandés (entrée/sortie
     de chaque composant du pipeline)
   - Outils : `time.perf_counter_ns()`,
     structlog avec `perf_counter_ns`,
     `py-spy` pour profiler le thread principal
   - Métriques Prometheus à ajouter pour
     `pipeline_latency_ms` et `discovery_duration_ms`

─────────────────────────────────────────────
SORTIE OBLIGATOIRE
─────────────────────────────────────────────
Crée le fichier :
  tasks/audits/audit_latence_edgecore.md
Crée le dossier tasks/audits/ s'il n'existe pas.

Structure du fichier :
## BLOC 1 — CHEMINS CRITIQUES (A ET B)
## BLOC 2 — CYTHON VS STUB (cointegration_fast)
## BLOC 3 — LATENCE IBKR
## BLOC 4 — THREADING ET CONTENTION GIL
## BLOC 5 — PIPELINE SIGNAL (6 COMPOSANTS)
## BLOC 6 — I/O SYNCHRONES
## BLOC 7 — QUALITÉ DES DONNÉES
## BLOC 8 — RÉSILIENCE
## SYNTHÈSE

Confirme dans le chat :
"✅ tasks/audits/audit_latence_edgecore.md créé
 🔴 X · 🟠 X · 🟡 X
 Latence estimée chemin critique A : ~X ms
 Latence estimée re-découverte N=50 : ~X ms
 Top optimisation : [titre]"
