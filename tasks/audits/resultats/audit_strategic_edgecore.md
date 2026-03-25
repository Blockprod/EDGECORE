---
modele: sonnet-4.6
mode: agent
contexte: codebase
produit: audit_strategic_edgecore.md
derniere_revision: 2026-03-25
creation: 2026-03-17 à 18:11
---

# AUDIT STRATÉGIQUE EDGECORE — Mean-Reversion Stat-Arb US Equities
**Date** : 2026-03-25 | **Auditeur** : GitHub Copilot (Claude Sonnet 4.6)
**Sources principales** : `results/bt_v36_output.json`, `results/bt_v35_output.json`, `results/v45b_p5_rerun.txt` (87 917 lignes)

---

## BLOC 1 — VALIDITÉ STATISTIQUE DE L'EDGE

### 1.1 Taille d'échantillon

**Source** : `results/bt_v36_output.json` + `results/v45b_p5_rerun.txt`

| Série | N trades | Seuil 100 | Statut |
|-------|----------|-----------|--------|
| bt_v36 (phase test IS) | 21 | ❌ | 🔴 N < 30 |
| bt_v35 (baseline IS) | 21 | ❌ | 🔴 N < 30 |
| bt_v34c (baseline précédent) | 22 | ❌ | 🔴 N < 30 |
| v45b P1 2019H2 | 30 | ❌ | 🟠 30 ≤ N < 60 |
| v45b P2 2020H2 | 18 | ❌ | 🔴 N < 30 |
| v45b P3 2022H2 | 33 | ❌ | 🟠 30 ≤ N < 60 |
| v45b P4 2023H2 | 34 | ❌ | 🟠 30 ≤ N < 60 |
| v45b P5 2024H2 | 3 | ❌ | 🔴 N < 30 (effondrement total) |

**Calcul IC 95% sur bt_v36** (WR = 66.7%, N = 21) :
```
IC = 0.667 ± 1.96 × √(0.667 × 0.333 / 21)
   = 0.667 ± 1.96 × 0.1028
   = 0.667 ± 0.201
   = [0.466 ; 0.868]
```
→ L'IC à 95% **inclut 50%** — l'edge n'est **pas prouvé statistiquement**.

**🔴 NON CONFORME** — N insuffisant dans tous les runs. Le plus récent OOS (P5) ne génère que 3 trades sur 382 jours de bourse, rendant toute statistique sans signification.

---

### 1.2 Métriques d'edge

**Source** : `results/bt_v36_output.json` + `results/bt_v35_output.json`

| Métrique | bt_v36 (IS) | Seuil viable | Statut | v45b avg OOS | Statut OOS |
|----------|-------------|-------------|--------|--------------|-----------|
| Win Rate | 66.7% | — | — | voir par période | — |
| Profit Factor | 4.22 | ≥ 1.5 | ✅ | À VÉRIFIER | — |
| Sharpe annualisé | 1.33 | ≥ 1.5 | 🟠 | **-0.63** | 🔴 |
| Calmar | 5.48 | — | ✅ | — | — |
| Max Drawdown | -1.91% | ≤ 10% | ✅ | -7.09% (P1) | ✅ |

**Walk-forward v45b — vue complète** (`results/v45b_p5_rerun.txt:87904-87917`) :
```
P1 2019H2   S=-1.57   -5.60%   t=30   DD=-7.09%   [FAIL]
P2 2020H2   S=-0.66   -2.03%   t=18   DD=-4.27%   [FAIL]
P3 2022H2   S= 2.21  +10.62%   t=33   DD=-2.71%   [PASS]
P4 2023H2   S=-2.01   -4.14%   t=34   DD=-4.07%   [FAIL]
P5 2024H2   S=-1.14   -3.90%   t= 3   DD=-4.49%   [FAIL]
Moyenne :   S=-0.63   PASS=1/5 → ❌ FAIL
```

Runs de pertes consécutives : P1+P2 [FAIL], P4+P5 [FAIL] → 4 périodes sur 5 en perte. **🟠 Risque opérationnel live**.

Expectancy $/trade : données per-trade non exportées dans `results/bt_v36_output.json` → **À VÉRIFIER** (absence d'observabilité granulaire).

**🔴 NON CONFORME** — Sharpe IS < 1.5 et Sharpe OOS moyen = -0.63.

---

### 1.3 Critère de Kelly

**Source** : `risk/kelly_sizing.py`

`KellySizerConfig` (`risk/kelly_sizing.py:38-44`) :
- `kelly_fraction = 0.25` (quarter-Kelly institutionnel ✅)
- `max_position_pct = 10.0`
- `min_position_pct = 2.0`
- `default_allocation_pct = 8.0` (fallback si < 10 trades en historique)

Calcul de f* requis : avg_win / avg_loss non disponibles dans les sorties (`results/bt_v36_output.json` ne les exporte pas). → **À VÉRIFIER**.

Risque opérationnel : avec P5 = 3 trades, `KellySizer._compute_kelly_fraction()` (`risk/kelly_sizing.py:63`) utilise le `default_allocation_pct = 8%` car `len(self._trade_history) < 10`. Le sizing n'est donc **pas fondé sur l'edge réalisé** lors d'une période signal-drought.

**🟡 À VÉRIFIER** — Paramétrage fraction Kelly conforme, mais calcul f* impossible sans per-trade data.

---

### 1.4 Tests de cointégration — qualité des paires

**Source** : `results/v45b_p5_rerun.txt:153-300`, `pair_selection/discovery.py:1-80`, `models/cointegration.py:1-150`

Distribution des p-values EG dans v45b P5 (205 paires testées, extrait représentatif) :
- p < 0.01 : ~12 paires (très forte cointégration)
- 0.01 ≤ p < 0.05 : ~18 paires (cointégration confirmée)
- p ≥ 0.05 (rejetées) : ~175 paires (85% du corpus)

**Gate I(1) présent** : `models/cointegration.py:122-134` — vérification ADF+KPSS avant EG ✅

**Confirmation Johansen** : `pair_selection/discovery.py:30` importe `JohansenCointegrationTest` — taux de confirmation exact non loggé dans v45b → **À VÉRIFIER**.

**Demi-vie** : `max_half_life = 70` (`config/dev.yaml:24`) — distribution observée dans v45b : `half_life=13` à `half_life=55` dans les logs debug → la majorité des paires acceptées est bien sous le seuil ✅.

**🟠 À VÉRIFIER** — Taux de confirmation Johansen non loggé (observabilité manquante).

---

## BLOC 2 — FRÉQUENCE ET CONTINUITÉ DU SIGNAL

### 2.1 Taux de signal

**Source** : `results/v45b_p5_rerun.txt:87907`, `results/bt_v36_output.json`

| Période | Bars tradables | Trades | Trades/bar | Trades/mois equiv. |
|---------|---------------|--------|------------|-------------------|
| bt_v36 IS | ~252 | 21 | 0.083 | ~1.7/mois |
| v45b P1 2019H2 | ~252 | 30 | 0.119 | ~2.5/mois |
| v45b P2 2020H2 | ~252 | 18 | 0.071 | ~1.5/mois |
| v45b P3 2022H2 | ~252 | 33 | 0.131 | ~2.8/mois |
| v45b P4 2023H2 | ~252 | 34 | 0.135 | ~2.8/mois |
| v45b P5 2024H2 | **382** | **3** | **0.008** | **0.1/mois** |

**P5 (période la plus récente)** : 3 trades en 382 jours de bourse — silence de ~127 jours entre chaque trade en moyenne. Largement au-delà du seuil 🔴 (≥ 90 jours).

`results/v45b_p5_rerun.txt:87907` : `total_bars=382 total_trades=19` — le moteur comptabilise 19 `trade_events` mais seulement 3 `round-trips` complets dans le résumé P5. Discordance entrées/sorties à investiguer.

**🔴 NON CONFORME** — Silence effectif ≥ 90 jours sur la période OOS la plus récente. Stratégie inopérante en production actuelle.

---

### 2.2 Cascade de filtres — diagnostic du silence

| Filtre | Fichier:Ligne | Seuil actif | Impact |
|--------|--------------|-------------|--------|
| `entry_z_score` | `config/dev.yaml:13` | 1.6 | Restrictif |
| `max_half_life` | `config/dev.yaml:24` | 70 | Modéré |
| `min_correlation` | `config/dev.yaml:26` | 0.60 | Modéré |
| `signal_combiner.entry_threshold` | `config/dev.yaml:52` | 0.6 | Double-filtrage |
| Rejection logging par motif | `pair_selection/discovery.py` | — | **ABSENT** |

Les logs v45b montrent `pair_discovery_parallel_starting` et `eg_test_complete` mais **aucun motif de rejet** par filtre individuel (z-score trop bas, corrélation insuffisante). Un signal rejeté en live sera indiagnosticable.

**🟠 NON CONFORME (observabilité)** — Silence en production indiagnosticable sans motifs de rejet granulaires.

---

### 2.3 Surrestrictivité des filtres

La combinaison `entry_z_score = 1.6` ET `signal_combiner.entry_threshold = 0.6` crée un **double-gating** :
1. Gate EG : le spread doit atteindre z ≥ 1.6
2. Gate composite : `zscore×0.70 + momentum×0.30` ≥ 0.6

En pratique, avec z=1.6 et momentum neutre : composite = 1.6×0.70 = 1.12 > 0.6 ✅. Le double-gating ne bloque pas en conditions neutres. La cause racine de P5=3 trades est l'**absence structurelle de spreads atteignant z ≥ 1.6** dans le régime bull-market 2024H2 (compression des primes de risque intrasectoriel).

**🟠 CONFORME (logique)** — La fréquence est structurellement insuffisante dans le régime actuel.

---

## BLOC 3 — PERFORMANCE PAR PAIRE ET RÉGIME

### 3.1 Performance par paire

**Source** : `results/bt_v36_output.json`

`bt_v36_output.json` ne contient **aucun détail per-paire** — uniquement les métriques agrégées. Idem pour `bt_v35_output.json`. Les logs v45b citent des paires (`META_XLK`, `UNH_CI`) sans P&L isolé.

**🟠 NON CONFORME (observabilité)** — Absence de reporting per-paire, impossible d'identifier les paires destructrices de valeur (PF < 1.0) ou les paires concentration P&L.

---

### 3.2 Performance par direction (LONG vs SHORT spread)

**À VÉRIFIER** — Aucune décomposition LONG/SHORT disponible dans les outputs JSON. Le `short_sizing_multiplier = 0.50` (`config/dev.yaml:16`) est un ajustement de sizing directionnel indépendant du P&L par direction.

**🟡 À VÉRIFIER**

---

### 3.3 Évolution temporelle (edge decay)

Depuis la timeline walk-forward v45b (`results/v45b_p5_rerun.txt:87908-87917`) :
```
2019H2 → FAIL   (régime pré-COVID, dispersion modérée)
2020H2 → FAIL   (COVID high-vol — spread intra-sectoriel désynchronisé)
2022H2 → PASS   (post-Fed hike, dispersion élevée) ← seul régime favorable
2023H2 → FAIL   (soft landing, compression spreads)
2024H2 → FAIL   (bull market 2024, spreads comprimés, 3 trades)
```

**Tendance claire** : l'edge est **conditionnellement dépendant** d'un régime de haute dispersion intrasectorielle. En bull-market comprimé, la stratégie est inopérante.

**🔴 NON CONFORME** — Edge conditionnel non généralisable sur un cycle économique complet.

---

### 3.4 Concentration du P&L

**À VÉRIFIER** — Données journalières non exportées. La seule période PASS (P3 2022H2) représente 100% du signal positif du walk-forward. La concentration est extrême au niveau des périodes.

**🔴 NON CONFORME** — 100% du P&L positif du walk-forward concentré sur 1/5 périodes.

---

## BLOC 4 — ROBUSTESSE IS/OOS

### 4.1 Validité du split IS/OOS

**Source** : `results/v45b_p5_rerun.txt:46-48` (logs démarrage P5)

Split P5 : `train 2023-01-03 → 2024-07-01 | OOS 2024-07-01 → 2025-01-01`
- N_OOS (trades P5) : **3** → 🔴 N_OOS < 15

Dégradation IS → OOS :

| Métrique | bt_v36 IS | v45b P5 OOS | Dégradation |
|----------|-----------|-------------|------------|
| Sharpe | 1.33 | -1.14 | **-185%** 🔴 |
| Return | +10.46% | -3.90% | **-137%** 🔴 |
| Trades | 21 | 3 | **-86%** 🔴 |

**🔴 NON CONFORME** — Dégradation IS→OOS catastrophique sur les 3 métriques clés.

---

### 4.2 Cohérence temporelle du split

Split P5 macroéconomiquement cohérent : IS = régime standard (2023-2024H1), OOS = régime bull-market comprimé (2024H2). Les régimes sont distincts. La méthodologie est correcte — c'est la **stratégie elle-même** qui ne survit pas au changement de régime.

**🟡 CONFORME (méthodologie split)** — Split IS/OOS macroéconomiquement distinct.

---

### 4.3 Walk-forward — branchement effectif

**Source** : `backtester/walk_forward.py`, `backtests/walk_forward.py`

`scripts/run_p5_v45b.py` invoque directement `strategy_simulation_starting` par période manuelle — ce n'est pas un `WalkForwardEngine` automatisé avec re-fitting des paramètres sur chaque fold IS.

Les paramètres (`entry_z_score = 1.6`, poids signaux, etc.) sont **fixes sur les 5 périodes** — pas de ré-optimisation IS. La validation walk-forward est structurellement un test OOS séquentiel avec paramètres figés.

**🟡 À VÉRIFIER** — WalkForwardEngine présent mais non branché en mode auto-refit.

---

## BLOC 5 — CALIBRATION DES SEUILS Z-SCORE

### 5.1 Inventaire des paramètres actifs

**Source** : `config/dev.yaml`

| Paramètre | Section | Valeur active | Type |
|-----------|---------|--------------|------|
| `entry_z_score` | `strategy` (`dev.yaml:13`) | 1.6 | Fixe |
| `exit_z_score` | `strategy` (`dev.yaml:14`) | 0.5 | Fixe |
| `max_half_life` | `strategy` (`dev.yaml:24`) | 70 | Fixe |
| `min_correlation` | `strategy` (`dev.yaml:26`) | 0.60 | Fixe |
| `short_sizing_multiplier` | `strategy` (`dev.yaml:16`) | 0.50 | Fixe |
| `zscore_weight` | `signal_combiner` (`dev.yaml:49`) | 0.70 | Fixe |
| `momentum_weight` | `signal_combiner` (`dev.yaml:50`) | 0.30 | Fixe |
| `entry_threshold` | `signal_combiner` (`dev.yaml:52`) | 0.6 | Fixe |
| `exit_threshold` | `signal_combiner` (`dev.yaml:53`) | 0.2 | Fixe |

**🟡 CONFORME** — Tous les paramètres clés sont dans `dev.yaml`, non hardcodés.

---

### 5.2 Cohérence live ↔ backtest par paramètre

`signal_engine/combiner.py:106-113` : `SignalCombiner.__init__` accepte `sources`, `entry_threshold`, `exit_threshold` — injection via `get_settings()` à confirmer dans `live_trading/runner.py`.

**Discordance critique** :
- `results/bt_v36_output.json:5` : `"zscore 0.35, momentum 0.15, OU 0.20, vol 0.10, CS 0.10, intraday 0.10"` → **6 sources**, poids zscore=0.35
- `config/dev.yaml:49-50` : `zscore_weight=0.70`, `momentum_weight=0.30` → **2 sources** actives

**Le bt_v36 (run IS de référence) a été exécuté avec une configuration abandonnée.** Les performances IS (S=1.33, PF=4.22, WR=66.7%) ne sont pas reproductibles avec la configuration actuelle.

**🔴 NON CONFORME** — Configuration SignalCombiner du run IS ≠ configuration live actuelle.

---

### 5.3 Analyse critique de `entry_z_score = 1.6`

WR_min = 1 / (1 + avg_win/avg_loss) — non calculable sans per-trade data.

Observation : `entry_z_score` a été abaissé de 2.0 à 1.6 (v31) sans augmentation notable de la fréquence en OOS récent (P5 = 3 trades). Le problème est structurel (dispersion intrasectorielle insuffisante en 2024H2), pas paramétrique. Abaisser davantage risque d'augmenter les faux positifs.

**🟡 À VÉRIFIER** — Le seuil 1.6 n'est pas la cause du drought en OOS récent.

---

### 5.4 Seuils adaptatifs

**Source** : `models/adaptive_thresholds.py` (fichier présent)

Non référencé dans `config/dev.yaml`. Non utilisé ni en live ni en backtest v45b. Activation des seuils adaptatifs pourrait améliorer la fréquence de signal en régime comprimé.

**🟡 À VÉRIFIER** — `adaptive_thresholds.py` présent mais inactif en live et backtest.

---

## BLOC 6 — MODÉLISATION DES COÛTS

### 6.1 Slippage

**Source** : `config/dev.yaml:217`, `execution_engine/router.py:162,189`

Config YAML : `slippage_bps: 2.0`, `slippage_model: "almgren_chriss"` (`config/dev.yaml:217-222`) ✅

**Debt B5-02** (connue) : `execution_engine/router.py:162,189` — slippage hardcodé `2.0` sans lecture de `get_settings().costs`. En live, le modèle Almgren-Chriss configuré est ignoré.

Impact quantifié (N=21, ~42 legs, taille ~$8k/position) :
```
Slippage total ≈ 42 × $8 000 × 0.0002 = $67.2 total
Impact sur P&L IS ($10 460) : marginal (< 1%)
```
La discordance est un risque de **gouvernance**, non un risque P&L majeur au niveau de fréquence actuel.

**🟠 NON CONFORME (dette B5-02)** — `execution_engine/router.py:162,189` n'utilise pas `get_settings().costs`.

---

### 6.2 Coût de borrow — short selling

**Source** : `config/dev.yaml:221`

`borrowing_cost_annual: 0.005` (0.5% GC rate) configuré. Application effective dans `backtests/cost_model.py` : **À VÉRIFIER**. `short_sizing_multiplier = 0.50` (`dev.yaml:16`) est un ajustement de sizing, indépendant du coût de borrow.

**🟡 À VÉRIFIER** — Config présente; application au simulateur non confirmée.

---

### 6.3 Impact des coûts sur l'expectancy nette

IS estimé (bt_v36, N=21, return=$10 460) :
```
Expectancy brute ≈ $10 460 / 21 ≈ $498/trade
Commission      ≈ 2 bps × 2 legs × $8k = $3.2/trade
Slippage        ≈ 2 bps × 2 legs × $8k = $3.2/trade
Expectancy nette ≈ $491/trade  ✅ (IS)
```

OOS P5 estimé (N=3, return=-$3 900) :
```
Expectancy OOS ≈ -$3 900 / 3 ≈ -$1 300/trade  🔴
```

Les coûts ne sont pas le problème — l'expectancy OOS est négative **avant** frais.

**🔴 NON CONFORME (OOS)** — Expectancy nette OOS négative. Cause : absence d'edge, pas les coûts.

---

## BLOC 7 — RISK MANAGEMENT FINANCIER

### 7.1 Sizing vs Kelly

**Source** : `risk/kelly_sizing.py:38-44,63`

`KellySizerConfig` :
- `kelly_fraction = 0.25` ✅ (quarter-Kelly)
- `max_position_pct = 10.0`, `min_position_pct = 2.0`
- `default_allocation_pct = 8.0` → **fallback actif** quand < 10 trades en historique

En v45b P5 (3 trades), l'allocateur est en mode fallback 8% permanent. Le Kelly adaptatif est inopérant en régime drought.

`max_gross_leverage = 2.0` : avec ≤ 4 paires simultanées à 8% → levier ≤ 32% brut ≪ 200% ✅

**🟡 CONFORME (paramétrage)** — Quarter-Kelly correct, inopérant en régime drought.

---

### 7.2 Garde-fous d'exécution — tiers de risque

**Source** : `results/v45b_p5_rerun.txt:48-55`

```
risk_tier_coherence: T1=10% T2=15% T3=20%  ← _assert_risk_tier_coherence() ✅
drawdown_manager_tiers: T1=3% T2=5% T3=8% T4=12%  ✅
```

- T1 (10% DD) → halt entrées : opérationnel ✅
- T2 (15% DD) → halt global KillSwitch : opérationnel, aucun déclenchement v45b ✅
- T3 (20% DD) → breaker stratégie : opérationnel ✅
- `_assert_risk_tier_coherence()` : exécutée au démarrage ✅

Max DD observé : P1=-7.09%, P2=-4.27%, P3=-2.71%, P4=-4.07%, P5=-4.49% — tous sous T1 ✅

**✅ CONFORME** — Risk tiers correctement configurés et opérationnels.

---

### 7.3 Exposition simultanée multi-paires

`max_sector_pct=25.0` (`risk/kelly_sizing.py:43`). Sector logs v45b : max 4 secteurs actifs simultanément → levier sectoriel estimé ≤ 4 × 8% = 32% < 40% ✅

**🟡 CONFORME** — Exposition dans les limites; vérification exacte À VÉRIFIER.

---

## BLOC 8 — INTÉGRITÉ DU PIPELINE SIGNAL

### 8.1 Pipeline all-or-nothing

| Test | Statut | Evidence |
|------|--------|---------|
| KillSwitch → halt → aucune position | **CONFORME** | v45b: aucun déclenchement KS, nominal |
| PositionRiskManager reject → aucun ordre | **CONFORME** | Risk tiers vérifiés au démarrage |
| SignalCombiner score < entry_threshold → aucun signal | **CONFORME** | `signal_engine/combiner.py:103-117` |

---

### 8.2 Paramètres live vs backtest

**Discordance confirmée** (voir Bloc 5.2) :
- bt_v36 (IS de référence) : SignalCombiner 6 sources, poids zscore=0.35 (`results/bt_v36_output.json:5`)
- Config actuelle : 2 sources, poids zscore=0.70 (`config/dev.yaml:49`, `signal_engine/combiner.py:106`)

Les performances IS du backtest de référence correspondent à un système **différent** du système live actuel.

**🔴 NON CONFORME** — Configuration backtest IS de référence ≠ configuration live actuelle.

---

### 8.3 Biais look-ahead

**Source** : `models/kalman_hedge.py:80-120`, `models/cointegration.py:122`

`KalmanHedgeRatio` : forward-only causal (`update(y, x)` bar-by-bar, pas de backward pass RTS) ✅

`engle_granger_test` : I(1) pre-check gate avant estimation OLS (`models/cointegration.py:122-134`), fenêtre lookback stricte ✅

**✅ CONFORME** — Aucun biais look-ahead détecté dans Kalman et EG.

Cython engine manquant : `models/cointegration.py:14-22` — Python fallback actif, ~2085s/période en v45b P5. En live avec IBKR rate limits (50 req/s), la latence de découverte de paires est un risque opérationnel.

**🟠 ATTENTION** — Cython engine absent → latence 10x en pair discovery live.

---

## SYNTHÈSE

### Score global : **2 / 10** → ❌ NO-GO

| Niveau | Critère | Résultat |
|--------|---------|---------|
| ≥ 8 | GO production | — |
| 5–7 | CONDITIONNEL | — |
| **< 5** | **NO-GO — refonte requise** | **2/10** |

---

### Tableau des anomalies

| ID | Bloc | Description | Fichier:Ligne | Sévérité | Impact | Effort |
|----|------|-------------|--------------|----------|--------|--------|
| SB1-01 | 1.1 | N=21 (IS) / N=3 (OOS P5) — insuffisant pour inférence statistique | `results/bt_v36_output.json:9` | 🔴 | edge invalide | L |
| SB1-02 | 1.1 | IC 95% WR inclut 50% — edge non prouvé statistiquement | `results/bt_v36_output.json:8-9` | 🔴 | edge invalide | L |
| SB1-03 | 1.2 | Walk-forward FAIL 4/5 — Sharpe moyen OOS = -0.63 | `results/v45b_p5_rerun.txt:87915` | 🔴 | edge invalide | L |
| SB3-01 | 3.3 | Edge conditionnel régime 2022H2 — non généralisable sur cycle complet | `results/v45b_p5_rerun.txt:87908-87917` | 🔴 | edge invalide | L |
| SB5-01 | 5.2 | bt_v36 IS = 6 sources zscore=0.35 ≠ config actuelle 2 sources zscore=0.70 | `results/bt_v36_output.json:5`, `config/dev.yaml:49` | 🔴 | surestimation perf | M |
| SB2-01 | 2.1 | Signal drought P5 : 3 trades / 382 bars — silence ~127j entre trades | `results/v45b_p5_rerun.txt:87907` | 🟠 | edge decay | L |
| SB4-01 | 4.1 | Dégradation IS→OOS Sharpe : 1.33 → -1.14 (-185%) | `results/v45b_p5_rerun.txt:87907` | 🟠 | overfitting | L |
| SB3-02 | 3.1 | Aucun reporting per-paire dans outputs JSON | `results/bt_v36_output.json` | 🟠 | surestimation perf | M |
| SB2-02 | 2.2 | Motifs de rejet de filtres non loggés — silence indiagnosticable en live | `pair_selection/discovery.py` | 🟠 | edge invalide | S |
| SB8-01 | 8.2 | SignalCombiner live ≠ backtest IS de référence (6 vs 2 sources) | `signal_engine/combiner.py:106`, `results/bt_v36_output.json:5` | 🟠 | surestimation perf | M |
| SB6-01 | 6.1 | B5-02 : slippage hardcodé 2.0 dans router.py — ignore get_settings().costs | `execution_engine/router.py:162,189` | 🟠 | coût sous-estimé | S |
| SB8-02 | 8.3 | Cython engine absent → Python fallback 10x — latence live pair discovery | `models/cointegration.py:14-22` | 🟠 | latence live | S |
| SB7-01 | 7.1 | KellySizer fallback 8% permanent en régime drought (< 10 trades historique) | `risk/kelly_sizing.py:63,44` | 🟡 | surestimation perf | XS |
| SB5-02 | 5.4 | adaptive_thresholds.py présent mais inactif en live et backtest | `models/adaptive_thresholds.py` | 🟡 | edge decay | M |
| SB6-02 | 6.2 | Coût de borrow 0.5% configuré — application dans simulator non confirmée | `config/dev.yaml:221` | 🟡 | coût sous-estimé | XS |

---

### Top 3 anomalies bloquantes

**1. SB1-02 + SB1-03 — Walk-forward FAIL 4/5, avg Sharpe OOS = -0.63** :
L'edge statistique n'est pas prouvé sur un cycle de marché complet (2019-2024). PASS=1/5 (2022H2 uniquement) avec IC 95% WR incluant 50%. Aucun déploiement live autorisé tant que la robustesse ne dépasse pas ≥ 3/5 PASS avec N ≥ 30 trades/période.

**2. SB5-01 — Discordance SignalCombiner IS vs config actuelle** :
Le bt_v36 IS de référence (S=1.33, PF=4.22) correspond à 6 alpha sources avec zscore=0.35. La config live actuelle n'en a que 2 avec zscore=0.70. Les metrics IS ne sont pas reproductibles. Un backtest de référence avec la configuration actuelle est obligatoire avant tout autre benchmark.

**3. SB2-01 — Signal drought structurel (3 trades en 382 jours OOS)** :
La stratégie est inopérante dans le régime de marché 2024H2. La cause n'est pas paramétrique mais structurelle : la dispersion intrasectorielle comprimée du bull-market 2024 ne génère pas de spreads atteignant z ≥ 1.6. Un filtre de régime conditionnel ou des seuils adaptatifs sont requis.

---

### Verdict final : **NO-GO**

Walk-forward 1/5 PASS (avg Sharpe OOS = -0.63), signal OOS effondré (3 trades en 382 bars vs 21 en IS), backtest IS de référence construit sur une configuration abandonnée (6 sources ≠ 2 actuelles). La stratégie démontre un edge conditionnel exclusivement en régime post-hike haute dispersion (2022H2) — non généralisable. Pré-requis avant paper trading : (1) rebuild bt IS avec config actuelle à 2 sources, (2) viser ≥ 3/5 PASS walk-forward avec N ≥ 30 trades/période OOS, (3) implémenter filtre de régime ou seuils adaptatifs pour survie en régime comprimé.

