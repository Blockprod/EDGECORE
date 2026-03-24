# Audit AI-Driven File Engineering — EDGECORE V1
*Date : 2026-03-21 | Prompt : `tasks/prompts/audit_ai_driven_prompt.md`*
**Création :** 2026-03-21 à 21:22  
*Exécuté par : GitHub Copilot (Claude Sonnet 4.6) — lecture réelle de chaque fichier*

---

## 1. Objectif de l'audit

Évaluer la maturité "AI-native" du repo EDGECORE : présence, complétude et cohérence
des fichiers de contexte destinés aux agents IA (Copilot, Claude, Cursor…).
Scanner chaque fichier, identifier ce qui est correct / obsolète / manquant,
et produire un plan d'action priorisé basé sur le contenu réel du code source.

---

## 2. Périmètre scanné — 11 fichiers

| n° | Fichier | Rôle attendu |
|----|---------|--------------|
| 1 | `.github/copilot-instructions.md` | Stack, conventions, interdictions pour Copilot VS Code |
| 2 | `.claude/context.md` | Snapshot projet complet — pipeline, modules, paramètres |
| 3 | `.claude/rules.md` | Règles strictes de modification pour Claude |
| 4 | `architecture/system_design.md` | Vue d'ensemble du système et de l'architecture |
| 5 | `architecture/decisions.md` | ADR — Architecture Decision Records |
| 6 | `knowledge/ibkr_constraints.md` | Rate limits, erreurs, contrats, ports IBKR |
| 7 | `knowledge/trading_constraints.md` | Règles métier stat-arb (z-score, half-life, risk, coûts) |
| 8 | `agents/quant_researcher.md` | Rôle & checklist chercheur quantitatif |
| 9 | `agents/risk_manager.md` | Rôle & checklist gestionnaire de risque |
| 10 | `agents/code_auditor.md` | Rôle & checklist auditeur de code |
| 11 | `agents/dev_engineer.md` | Rôle & checklist ingénieur développement |

---

## 3. ÉTAPE 0 — État des lieux (scan complet du contenu réel)

```
┌─────────────────────────────────────────────────────────────────────┐
│ ÉTAT DES LIEUX — FICHIERS AI-DRIVEN            21 mars 2026        │
├─────────────────────────────────────────────────────────────────────┤
│ .github/copilot-instructions.md   ⚠️ PARTIEL                       │
│ .claude/context.md                ✅ COMPLET                        │
│ .claude/rules.md                  ✅ COMPLET                        │
│ architecture/system_design.md     ✅ COMPLET                        │
│ architecture/decisions.md         ⚠️ PARTIEL                       │
│ knowledge/ibkr_constraints.md     ✅ COMPLET                        │
│ knowledge/trading_constraints.md  ✅ COMPLET                        │
│ agents/quant_researcher.md        ✅ COMPLET                        │
│ agents/risk_manager.md            ✅ COMPLET                        │
│ agents/code_auditor.md            ⚠️ PARTIEL                       │
│ agents/dev_engineer.md            ✅ COMPLET                        │
└─────────────────────────────────────────────────────────────────────┘

✅  8 fichiers existants et conformes
⚠️  3 fichiers partiels à corriger
❌  0 fichier absent à créer
```

---

## 4. Détail par fichier

### ✅ `.claude/context.md` — COMPLET

Contenu vérifié :
- Pipeline complet (DataLoader → AuditTrail) avec code ASCII-art précis
- Table modules avec colonnes Entrée / Sortie / Ne FAIT PAS
- Tous les paramètres `StrategyConfig`, `RiskConfig`, `KillSwitchConfig`, `CostConfig`, `SignalCombinerConfig` extraits du code réel
- Section "Ce qui ne doit PAS changer" (8 invariants)
- Table des dettes avec statuts **à jour** :
  - B5-01 → ✅ CORRIGÉ (2026-03-20)
  - B4-05 → ✅ CORRIGÉ (2026-03-20)
  - B5-02 → ✅ CORRIGÉ (2026-03-21)
  - B2-01 → ✅ CORRIGÉ (2026-03-21)
  - B2-02 → ⚠️ PARTIEL (C-01 en attente)

**→ Aucune action requise.**

---

### ✅ `.claude/rules.md` — COMPLET

Contenu vérifié :
- Ordre de priorité absolu (6 règles)
- Checklist pré-modification (4 points)
- Exemples de code pour Datetime, Logging, Config, Types d'ordres, IBKR
- Obligations post-modification (6 étapes avec commandes)
- Baseline tests : **2659 passed** ✅ (correct)
- Table interdictions complète
- Liste fichiers sensibles ("ne pas toucher sans compréhension complète")

**→ Aucune action requise.**

---

### ✅ `architecture/system_design.md` — COMPLET

Contenu vérifié :
- Section 1 : tableau Marché / Mode / Cadence / Instruments / Broker / Envs
- Section 2 : schéma ASCII 8 couches (DATA → UNIVERSE → PAIR → SIGNAL → RISK → SIZING → EXECUTION → PERSISTENCE)
- Section 3 : orchestrateur `LiveTradingRunner` — `_initialize()`, `_scan_loop()`, `_reconcile()`, `_risk_tick()`
- Section 4 : tableau Docker Compose 6 services avec ports
- Section 5 : stack techno complète avec compteur pytest **2659 passed** ✅
- Variable `EDGECORE_ENV=prod` mentionnée correctement

**→ Aucune action requise.**

---

### ✅ `knowledge/ibkr_constraints.md` — COMPLET

Contenu vérifié :
- Ports TWS/Gateway (7496/7497 ib_insync, 4001/4002 ibapi EClient)
- Client ID unique, registre `_active_client_ids`, RuntimeError si collision
- Rate limit : 50 req/s hard cap, 45/s sustained, burst 10 — avec code `_ibkr_rate_limiter`
- Codes erreurs informatifs (2104, 2106, 2158) et données historiques (162, 200, 354) avec patterns de code exacts
- Codes supplémentaires : 322 (duplicate ticker), 430, 366
- Types de contrats US STK SMART USD — ib_insync et ibapi
- Types d'ordres : Limit / Market (stop géré côté app)
- `reqHistoricalData` avec tous les paramètres
- Shortable shares via generic tick 236
- Request IDs : compteur début à 10, thread-safe
- Circuit breaker : 5 failures, 300s reset, delays [5, 15, 30] +jitter
- Variables d'environnement IBKR avec valeurs par défaut
- Comportement docker-compose (`host.docker.internal`)

**→ Aucune action requise.**

---

### ✅ `knowledge/trading_constraints.md` — COMPLET

Contenu vérifié :
- Triple gate (EG + Johansen + HAC) avec tableau seuils + modules
- Paramètres de filtrage dev vs prod (correlation, half-life, lookback, max_pairs)
- Seuils signal : entry ±2.0σ, exit ±0.5σ, stop ±3.5σ
- Composite signal = z×0.70 + momentum×0.30 avec règle anti-hardcode
- Risk tiers T1/T2/T3 (10%/15%/20%) avec assertion au boot
- Paramètres position : risk_per_trade 0.5%, heat max 95%, max 10 positions
- Kill-switch 6 conditions avec seuils
- Coûts : slippage 3bps, commission 0.035%, borrowing 0.5%/an, règle edge > 2×coût
- Dette B5-02 mentionnée explicitement
- Blacklist pairs : cooldown 30j après 2 losses
- Types données IBKR autorisés (TRADES/MIDPOINT/BID/ASK) avec interdiction ADJUSTED_LAST + explication

**→ Aucune action requise.**

---

### ✅ `agents/quant_researcher.md` — COMPLET

Contenu vérifié :
- frontmatter YAML avec `name`, `description`
- Pipeline sélection paires (UniverseManager → PairDiscoveryEngine, triple gate)
- Paramètres `StrategyConfig` et `SignalCombiner` extraits du code
- Kalman hedge ratio avec code d'appel standard (`KalmanHedgeRatioEstimator`)
- Protocole validation nouvelle paire (6 étapes ordonnées)
- Outils disponibles dans EDGECORE (imports précis)
- Règles de conduite (3 règles)

**→ Aucune action requise.**

---

### ✅ `agents/risk_manager.md` — COMPLET

Contenu vérifié :
- frontmatter YAML complet
- Hiérarchie 3 tiers avec sources de config exactes + commande de validation
- Kill-switch : 6 `KillReason` énumérés + conditions supplémentaires (EXCHANGE_ERROR, UNKNOWN)
- Reset avec `operator_id` obligatoire
- Stops par position : trailing (1σ), time (3×HL, max 60 bars), P&L (-10%), hedge drift (10%, 7j)
- `PortfolioRiskConfig` : tous les paramètres avec valeurs
- Contraintes sizing IBKR (100$ notionnel min, 5% equity max, 50% net, 20% margin buffer)
- Checklist pré-modification (6 points)
- Chemins de modification autorisés et interdits

**→ Aucune action requise.**

---

### ✅ `agents/dev_engineer.md` — COMPLET

Contenu vérifié :
- frontmatter YAML complet
- Environnement dev (venv 3.11.9, system 3.13.1)
- Build Cython : fichiers, pattern d'import avec fallback
- Intégration IBKR : ports, rate limiter (synchrone et async), reqId, erreurs, circuit breaker
- Hiérarchie YAML (seuls {env}.yaml chargés — config.yaml non chargé)
- Docker : multi-stage, `EDGECORE_ENV=prod` corrigé
- Procédure correction dette technique
- Commandes de validation complètes

**→ Aucune action requise.**

---

### ⚠️ `.github/copilot-instructions.md` — PARTIEL

**Problème identifié :**

| Ligne | Contenu actuel | Contenu attendu |
|-------|---------------|-----------------|
| 11 | `2654 passants` | `2659 passants` |

Le compteur de tests est désynchronisé. Tous les autres fichiers AI-Driven ont été mis à jour
(`.claude/rules.md`, `architecture/system_design.md`, `agents/code_auditor.md`) mais pas celui-ci.

**Reste du contenu :** ✅ intégralement correct — stack, modules, conventions,
risk tiers, IBKR rate limit, issues connues (B5-01 ✅, B2-01 ⚠️, B2-02 ⚠️, B4-05 ✅),
interdictions absolues, commandes de validation, pipeline résumé.

**Action requise : A1** — corriger `2654` → `2659` ligne 11.

---

### ⚠️ `architecture/decisions.md` — PARTIEL

**Problème identifié :**

ADR-007 (Docker single-process) contient une section marquée "NON CORRIGÉ" pour le bug B5-01,
alors que celui-ci est corrigé depuis le 2026-03-20 :

```
Dockerfile:37  → ENV EDGECORE_ENV=prod      ✅ (vérifié en live)
docker-compose.yml:11 → EDGECORE_ENV: prod  ✅ (vérifié en live)
```

La section indique encore : *"Action requise : corriger Dockerfile ligne 34 et docker-compose.yml
ligne 11 avant tout déploiement production"* — ce qui est inexact et pourrait induire un agent
en erreur.

**Reste du contenu :** ✅ ADR-001 à ADR-006 et ADR-008 intégralement corrects.
ADR-008 (singleton Settings) est bien présent (ajouté lors du sprint précédent).

**Action requise : A2** — marquer B5-01 comme CORRIGÉ dans ADR-007, remplacer la section
"Action requise" par une note de vérification.

---

### ⚠️ `agents/code_auditor.md` — PARTIEL

**Problèmes identifiés (3) :**

| n° | Localisation | Problème | Impact |
|----|-------------|---------|--------|
| P1 | Checklist B4-05 | `- [ ] **B4-05** : backtester/__init__.py existe` non coché | Agent perd du temps à créer un fichier déjà là |
| P2 | Checklist B5-01 | `- [ ] **B5-01** : Docker utilise EDGECORE_ENV=prod` non coché | Agent perd du temps à corriger du code déjà corrigé |
| P3 | (Vérifié) Table interdictions dans `code_auditor.md` | ✅ Section absente du fichier — la table avec la note erronée est dans `.claude/rules.md` (déjà correcte) | Aucune action requise |

**Reste du contenu :** ✅ Checklist B2–B5 structurellement complète (B2-01, B2-02, B2-03,
B3-01→B3-04, B4-01→B4-04, B5-02→B5-04), conventions datetime/logging/config,
validation tests **2659** ✅ (déjà correct), format de rapport d'audit.

**Actions requises : A3** — cocher B4-05, cocher B5-01 dans la checklist.

---

## 5. ÉTAPE 1 — Nettoyage préalable

| Élément | Présent ? | Action |
|---------|-----------|--------|
| `CMakeLists.txt` à la racine | ❌ Absent | — |
| `ARCHIVED_cpp_sources/` | ❌ Absent | — |
| `ARCHIVED_crypto/` | ❌ Absent | — |
| Fichiers `debug_*.txt`, `bt_out*.txt`, `bt_errors_*.txt` | ❌ Absents | — |
| `run_backtest_v*.py` dans `scripts/` | ❌ Absents | — |
| `setup.py` + `pyproject.toml` coexistants | ✅ Les deux présents — **voulu** | ADR-006 : setup.py = Cython uniquement, pyproject.toml = metadata |

**→ Workspace propre. Aucune suppression nécessaire. ✅**

---

## 6. ÉTAPE 2 — Arborescence cible

```
EDGECORE/
├── .claude/
│   ├── context.md                   ✅ COMPLET
│   └── rules.md                     ✅ COMPLET
├── .github/
│   └── copilot-instructions.md      ⚠️ → 1 ligne à corriger (2654→2659)
├── architecture/
│   ├── system_design.md             ✅ COMPLET
│   └── decisions.md                 ⚠️ → ADR-007 B5-01 à marquer CORRIGÉ
├── knowledge/
│   ├── ibkr_constraints.md          ✅ COMPLET
│   └── trading_constraints.md       ✅ COMPLET
├── agents/
│   ├── quant_researcher.md          ✅ COMPLET
│   ├── risk_manager.md              ✅ COMPLET
│   ├── code_auditor.md              ⚠️ → B4-05 + B5-01 checklist + table interdictions
│   └── dev_engineer.md              ✅ COMPLET
```

---

## 7. ÉTAPE 3 — Actions décidées

### Actions sur les fichiers AI-Driven

| ID | Fichier | Type | Description | Effort |
|----|---------|------|-------------|--------|
| A1 | `.github/copilot-instructions.md` | MISE À JOUR | `2654` → `2659` (ligne 11) | 1 min |
| A2 | `architecture/decisions.md` | MISE À JOUR | ADR-007 : marquer B5-01 CORRIGÉ, supprimer "Action requise" | 2 min |
| A3 | `agents/code_auditor.md` | MISE À JOUR | Cocher B4-05 + B5-01, corriger parenthèse table interdictions | 3 min |

### Dettes techniques ouvertes (hors périmètre fichiers contexte — pas corrigées ici)

| ID | Fichier | Ligne(s) | Problème |
|----|---------|----------|---------|
| B5-02 | `execution_engine/router.py` | 148, 173 | ✅ CORRIGÉ (2026-03-21) — `get_settings().costs.slippage_bps` |
| B2-01 | `execution_engine/router.py` | — | ✅ CORRIGÉ (2026-03-21) — `class TradeOrder` absente |
| B2-02 | `live_trading/runner.py` | ~224–231 | `PositionRiskManager` + `PortfolioRiskManager` + `KillSwitch` + `RiskFacade` instanciés séparément |

---

## 8. ÉTAPE 4 — Plan de migration priorisé

| Priorité | Fichier | Statut avant | Action | Effort | % Auto | Impact |
|----------|---------|-------------|--------|--------|--------|--------|
| 1 | `.github/copilot-instructions.md` | ⚠️ | Corriger compteur tests | 1 min | 100% | Cohérence baseline agents |
| 2 | `architecture/decisions.md` | ⚠️ | Marquer B5-01 CORRIGÉ dans ADR-007 | 2 min | 100% | Évite recorrection d'un code déjà fixé |
| 3 | `agents/code_auditor.md` | ⚠️ | Cocher B4-05 + B5-01 + fix table | 3 min | 100% | Checklist d'audit fiable |
| — | `.claude/context.md` | ✅ | Inchangé | — | — | Déjà conforme |
| — | `.claude/rules.md` | ✅ | Inchangé | — | — | Déjà conforme |
| — | `architecture/system_design.md` | ✅ | Inchangé | — | — | Déjà conforme |
| — | `knowledge/ibkr_constraints.md` | ✅ | Inchangé | — | — | Déjà conforme |
| — | `knowledge/trading_constraints.md` | ✅ | Inchangé | — | — | Déjà conforme |
| — | `agents/quant_researcher.md` | ✅ | Inchangé | — | — | Déjà conforme |
| — | `agents/risk_manager.md` | ✅ | Inchangé | — | — | Déjà conforme |
| — | `agents/dev_engineer.md` | ✅ | Inchangé | — | — | Déjà conforme |

---

## 9. Résultat de l'exécution (post-audit)

| Action | Résultat |
|--------|---------|
| A1 — `.github/copilot-instructions.md` : `2654` → `2659` | ✅ APPLIQUÉ |
| A2 — `architecture/decisions.md` : ADR-007 B5-01 marqué CORRIGÉ | ✅ APPLIQUÉ |
| A3 — `agents/code_auditor.md` : B4-05 + B5-01 cochés | ✅ APPLIQUÉ |
| C-02 — Fichiers AI-Driven : B5-02 + B2-01 marqués CORRIGÉ | ✅ APPLIQUÉ (2026-03-21) |
| C-01 — `live_trading/runner.py` : consolidation via `RiskFacade` | ⏳ EN COURS |

---

## 10. Conclusion

**Maturité AI-Driven d'EDGECORE V1 : 🟢 HAUTE**

Le repo est dans un état AI-native avancé : 11 fichiers de contexte en place, tous ancrés
dans le code réel, aucun fichier manquant. Les 3 points de correction identifiés sont mineurs
(cohérence de statut et compteurs stale) — pas de lacune structurelle ni de section
fondamentale absente.

Les dettes B5-02 et B2-01 ont été vérifiées comme déjà corrigées dans le code (2026-03-21). La dette B2-02 (**C-01**) reste la seule modification substantielle à effectuer sur le code de production — elle fait l'objet du plan d'action structurel séparé.
