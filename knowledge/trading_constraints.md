# EDGECORE — Contraintes de Trading

*Dernière mise à jour : 2026-03-20*

> Source de vérité : `config/settings.py` (`StrategyConfig`, `RiskConfig`, `CostConfig`, `SignalCombinerConfig`).  
> Modifier ces contraintes = benchmarker de nouveau sur out-of-sample (OOS 252 jours).

---

## 1. Contraintes de sélection de paires

### Cointégration — triple gate obligatoire

| Gate | Méthode | Seuil | Module |
|------|---------|-------|--------|
| Gate 1 | Engle-Granger (ADF) | p-value ≤ 0.05 | `models/cointegration.py` |
| Gate 2 | Johansen (trace test) | p-value ≤ 0.05 | `models/cointegration.py` |
| Gate 3 | HAC t-statistic | p-value ≤ 0.05 (HAC corr.) | `models/cointegration.py` |

**Les 3 gates doivent passer simultanément.** Échec d'un seul = paire rejetée.

### Paramètres de filtrage

| Paramètre | Valeur dev | Valeur prod | Source |
|-----------|-----------|-------------|--------|
| `min_correlation` | 0.60 | 0.70 | `StrategyConfig` |
| `min_half_life` | 2 jours | 2 jours | `StrategyConfig` |
| `max_half_life` | 60 jours | 60 jours | `StrategyConfig` |
| `lookback_days` | 252 | 252 | `StrategyConfig` |
| `max_concurrent_pairs` | 10 | 10 | `StrategyConfig` |

**Pourquoi min_half_life = 2 ?** En dessous, le spread mean-reverts trop vite (coût de transaction > alpha).  
**Pourquoi max_half_life = 60 ?** Au-delà, le capital est immobilisé trop longtemps (opportunité cost > alpha).

### Hedge ratio

- **Méthode** : Kalman filter adaptatif (`models/kalman_hedge.py`)
- **Alternative** : OLS statique (uniquement pour validation de robustesse)
- **Mise à jour** : à chaque scan (toutes les 5 min en live)
- **Interdiction** : ne jamais hardcoder le hedge ratio — toujours issu du Kalman

---

## 2. Contraintes de signal

### Seuils d'entrée/sortie

| Signal | Paramètre | Valeur | Source |
|--------|-----------|--------|--------|
| Entrée long spread | `entry_z_score` | +2.0 σ | `StrategyConfig` |
| Entrée short spread | `entry_z_score` | -2.0 σ | `StrategyConfig` |
| Sortie (mean-reversion) | `exit_z_score` | ±0.5 σ | `StrategyConfig` |
| Stop loss z-score | `stop_z_score` | ±3.5 σ | `StrategyConfig` |

### Composition du signal composite

```
composite = z_score × 0.70 + momentum × 0.30
```

- Poids configurables via `SignalCombinerConfig` — ne jamais hardcoder 0.70 / 0.30
- `momentum` = variation de z-score sur fenêtre glissante
- Le composite doit dépasser `entry_z_score` pour déclencher un ordre

### Stabilité de la cointégration

La fonction `is_cointegration_stable()` (`models/cointegration.py`) ré-évalue la cointégration avant chaque nouvelle entrée.  
Si p-value > 0.05 sur lookback récent → signal bloqué, paire mise en watchlist.

---

## 3. Contraintes de risque

### Hiérarchie 3 tiers (NE PAS MODIFIER l'ordre)

```
Tier 1 : RiskConfig.max_drawdown_pct  = 0.10  (10%)   → halt entrées uniquement
Tier 2 : KillSwitchConfig             = 0.15  (15%)   → halt global + IBKR
Tier 3 : StrategyConfig.internal      = 0.20  (20%)   → breaker interne stratégie
```

Assertion vérifiée au démarrage : `T1 ≤ T2 ≤ T3`. Toute modification doit respecter cette contrainte.

### Paramètres de position

| Paramètre | Valeur | Source |
|-----------|--------|--------|
| `risk_per_trade` | 0.5% du AUM | `RiskConfig` |
| Capital heat max | 95% | `PortfolioAllocator` |
| Max positions simultanées | 10 | `StrategyConfig.max_concurrent` |
| Levier | 1× (pas de marge) | Implicite |

### Kill-switch — 6 conditions de déclenchement

| Condition | Seuil |
|-----------|-------|
| Drawdown journalier | ≥ 15% |
| Drawdown hebdomadaire | ≥ 20% |
| Pertes consécutives | ≥ 5 trades |
| Perte de connexion IBKR | 60 s sans reconnexion |
| Latence d'exécution | > 30 s par ordre |
| Ratio Sharpe glissant (20 jours) | < -1.0 |

---

## 4. Contraintes de coût

Source de vérité : `CostConfig` (lue via `get_settings().costs`).

| Coût | Valeur | Notes |
|------|--------|-------|
| Slippage | 3 bps (0.03%) | Par leg, chaque aller-retour |
| Commission IBKR | 0.035% | Par trade (fixe) |
| Borrowing cost (short) | 0.5% / an | Approximation — varie par ticker |
| Coût total aller-retour | ~6 bps + 0.07% | 2 legs × slippage + 2 × commission |

**Règle :** `expected_edge > 2 × coût_total_aller_retour` avant de placer un ordre.

**Dette connue B5-02 :** `execution_engine/router.py` a des valeurs `slippage = 2.0` hardcodées (lignes ~162 et ~189). Ces valeurs doivent être remplacées par `get_settings().costs.slippage`.

---

## 5. Contraintes opérationnelles

### Blacklist des paires

| Paramètre | Valeur | Source |
|-----------|--------|--------|
| Cooldown après `max_consecutive_losses` | 30 jours | `StrategyConfig` |
| `max_consecutive_losses` (trigger) | 2 losses | `StrategyConfig` |
| Délistage | Surveillance via `data/delisting_guard.py` | Sortie forcée |

### Données historiques — types autorisés IBKR

| Type | Usage |
|------|-------|
| `TRADES` | Prix de clôture (principal) |
| `MIDPOINT` | Alternative si TRADES indisponible |
| `BID`, `ASK` | Calcul bid-ask spread (liquidity filter) |

**Jamais** `ADJUSTED_LAST` pour le spread (les ajustements dividendes créent de faux signaux de cointégration).

### Universe — filtres de liquidité obligatoires

| Filtre | Seuil |
|--------|-------|
| ADV (Average Daily Volume) | ≥ configuré dans `UniverseManager` |
| Bid-ask spread | ≤ configuré dans `data/liquidity_filter.py` |
| Shortable shares disponibles | ≥ taille position cible |

---

## 6. Ce qui ne doit pas changer sans re-benchmarking OOS

Les paramètres suivants ont été calibrés sur OOS 252 jours. Toute modification nécessite un nouveau `walk_forward.py` complet :

- `entry_z_score` (2.0) — calibré pour maximiser Sharpe net de coûts
- `exit_z_score` (0.5) — calibré pour minimiser holding period × coût
- `stop_z_score` (3.5) — calibré pour limiter tail risk sans over-stopping
- `min_half_life` / `max_half_life` (2 / 60) — calibrés sur distribution empirique des spreads
- `min_correlation` (0.70 prod) — seuil de robustesse backtesté
- `SignalCombiner` weights (0.70 / 0.30) — calibrés via ablation study
- `risk_per_trade` (0.5%) — calibré pour Kelly fraction conservateur

**Interdiction :** modifier ces valeurs directement dans `dev.yaml` sans valider en OOS — le dépôt `PLAN_ACTION_EDGECORE` doit tracer chaque modification.
