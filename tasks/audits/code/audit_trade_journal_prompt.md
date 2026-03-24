---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: tasks/audits/resultats/audit_trade_journal_edgecore.md
derniere_revision: 2026-03-24
creation: 2026-03-24 à 17:55
---

#codebase

Tu es un Senior Quant Engineer spécialisé en systèmes de stat-arb
institutionnel. Tu réalises un audit complet du journal de trading
d'EDGECORE : ce qui existe, ce qui manque, et ce qui doit être
implémenté.

─────────────────────────────────────────────
RAISONNEMENT
─────────────────────────────────────────────
Réfléchis profondément étape par étape avant
de produire ta sortie. Explore d'abord, planifie
ensuite, puis exécute.

─────────────────────────────────────────────
ÉTAPE 0 — VÉRIFICATION PRÉALABLE (OBLIGATOIRE)
─────────────────────────────────────────────
Vérifie si ce fichier existe déjà :
  tasks/audits/resultats/audit_trade_journal_edgecore.md

Si trouvé, affiche :
"⚠️ Audit journal existant détecté :
 Fichier : tasks/audits/resultats/audit_trade_journal_edgecore.md
 Date    : [date modification]

 [NOUVEAU]  → audit complet (écrase l'existant)
 [MÀJOUR]   → compléter sections manquantes
 [ANNULER]  → abandonner"

Si absent → démarrer directement :
"✅ Aucun audit journal existant. Démarrage..."

─────────────────────────────────────────────
PÉRIMÈTRE STRICT
─────────────────────────────────────────────
Tu analyses UNIQUEMENT :

**Traçabilité live :**
- Ce qui est loggué lors d'un trade live via structlog
- Ce qui est écrit sur disque de façon structurée (JSON, CSV)
  dans `persistence/` et `data/audit/`
- L'`AuditTrail` dans `persistence/` : ce qu'il capture,
  format des entrées, intégrité HMAC (AUDIT_HMAC_KEY)
- Le `BrokerReconciler` (toutes les 5 min) : quels champs
  sont réconciliés entre positions IBKR et état interne

**Traçabilité backtest :**
- `BacktestRunner`, `StrategyBacktestSimulator` dans `backtests/`
- `BacktestMetrics` dans `backtests/metrics.py`
- Colonnes disponibles dans les résultats vs colonnes nécessaires
  pour réconciliation live/backtest

**Données manquantes — à identifier dans le code :**
- Slippage réel entry (prix demandé vs prix obtenu)
- Spread bid/ask au moment de l'entrée
- Timestamp exact d'entrée et de sortie (UTC)
- Raison de sortie (stop loss / exit z-score / kill-switch /
  manuel)
- Contexte signal au moment de l'entrée : z-score exact,
  hedge ratio Kalman, demi-vie estimée, momentum score
- Quel tier de risk a déclenché la sortie (T1/T2/T3)

**Infrastructure de persistance :**
- Fichiers existants dans `data/audit/`, `logs/`, `results/`
- Rotation quotidienne : présente ou absente
- Atomicité des écritures : safe (.tmp → os.replace) ou risque
  de corruption
- Crash recovery : que se passe-t-il si le process meurt
  en cours d'écriture ?

**Comparaison live vs backtest :**
- Les KPIs live peuvent-ils être réconciliés avec les KPIs
  backtest ?
- Quels écarts sont normaux (slippage, spread, timing)
  vs anormaux (filtres divergents, hedge ratio drift)

─────────────────────────────────────────────
CE QUE TU N'ANALYSES PAS
─────────────────────────────────────────────
- La logique de cointégration (EG, Johansen — algorithmes propriétaires)
- Les performances statistiques du backtest
- La sécurité credentials IBKR (couvert par audit_technical)
- L'infrastructure Docker/CI/CD

─────────────────────────────────────────────
FORMAT DU RAPPORT
─────────────────────────────────────────────
Produis le rapport dans :
  tasks/audits/resultats/audit_trade_journal_edgecore.md

Avec ces sections exactes :

## 1. État actuel — Traçabilité live
[Ce qui existe aujourd'hui, avec citations fichier:ligne]

## 2. État actuel — Traçabilité backtest
[BacktestMetrics colonnes, CSV/JSON export, ce qui est exploitable]

## 3. Données manquantes — Gaps critiques
[Classés 🔴 P0 / 🟠 P1 / 🟡 P2 avec justification métier]

## 4. Risques
[Corruption, perte de données, non-auditabilité en cas
d'incident live ou de litige avec IBKR]

## 5. Recommandations
[Plan d'implémentation priorisé : module à créer ou modifier,
point d'ancrage dans le code existant, effort estimé XS/S/M/L]

## 6. Synthèse
[Score de maturité du journal 0-10, verdict go/no-go
pour passage en trading live]

─────────────────────────────────────────────
RÈGLES ABSOLUES
─────────────────────────────────────────────
- Cite toujours fichier + numéro de ligne avant toute
  affirmation sur le code
- Ne modifier JAMAIS `models/cointegration_fast.pyx`
  sans instruction explicite
- Tout nouveau fichier de persistance doit utiliser
  l'écriture atomique (.tmp → os.replace)
- Timestamps toujours en `datetime.now(timezone.utc)` —
  jamais `datetime.utcnow()`
- Logging via `structlog.get_logger(__name__)` uniquement
- Propose uniquement des solutions compatibles Python 3.11.9
