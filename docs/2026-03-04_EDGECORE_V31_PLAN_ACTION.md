<<<<<<< HEAD
﻿# EDGECORE v31 ÔÇö Plan d'Action : Scale-Up 4 Axes

**Date :** 4 mars 2026  
**Auteur :** EX├ëCUTEUR AUTOMATIQUE / GitHub Copilot  
**Baseline :** v30b ÔåÆ +5.25%, Sharpe 0.74, 25 trades, WR 60%, Max DD -2.63%  
=======
# EDGECORE v31 — Plan d'Action : Scale-Up 4 Axes

**Date :** 4 mars 2026  
**Auteur :** EXÉCUTEUR AUTOMATIQUE / GitHub Copilot  
**Baseline :** v30b → +5.25%, Sharpe 0.74, 25 trades, WR 60%, Max DD -2.63%  
>>>>>>> origin/main
**Objectif v31 :** Return > +15%, Sharpe > 1.0, Trades > 80/an, Max DD < 8%

---

## Contexte et Diagnostic

### Performance v30b vs Institutions

<<<<<<< HEAD
| Syst├¿me | Return annualis├® | PnL 3 ans ($100K) | Sharpe | Trades/an |
=======
| Système | Return annualisé | PnL 3 ans ($100K) | Sharpe | Trades/an |
>>>>>>> origin/main
|---------|----------------:|-------------------:|-------:|----------:|
| **EDGECORE v30b** | ~1.7% | +$5,249 | 0.74 | ~8 |
| Retail stat-arb moyen | 3-8% | +$9K-$26K | 0.5-1.0 | 50-200 |
| Fonds quant mid-tier (AQR, Man AHL) | 8-15% | +$26K-$52K | 1.0-2.0 | 500-5,000 |
| Top-tier (Two Sigma, DE Shaw, Citadel) | 15-30% | +$52K-$100K | 2.0-3.5 | 10K-100K |

<<<<<<< HEAD
### Les 3 Goulots d'├ëtranglement Identifi├®s

1. **Univers trop petit** : 37 symboles ÔåÆ ~81 paires intra-secteur. Un univers de 115 symboles = ~500+ paires (loi quadratique : $\binom{N}{2}$ paires).
2. **Signal unique** : le z-score cointegration est le seul alpha. Zero diversification de signal = forte corr├®lation des trades.
3. **Fr├®quence trop faible** : 8 trades/an avec barres journali├¿res = 1 d├®cision/jour/paire. La loi des grands nombres ne peut pas jouer.

### Ordre de Priorit├® (ratio impact/complexit├®)

| Levier | Impact estim├® | Complexit├® | Priorit├® |
|--------|:------------:|:----------:|:--------:|
| Univers ├®largi (mid-caps + ETFs) | +++++ | Faible | **P0** |
| Signal momentum relatif | ++++ | Faible | **P0** |
| Signal combiner/ensemble | +++ | Faible | **P1** |
| Param├¿tres agressifs | ++++ | Tr├¿s faible | **P0** |
| Timeframe 1h | ++++ | Moyenne | **P1** |
| Signal MR intraday | +++ | Moyenne | **P2** |
| Actions europ├®ennes | ++ | ├ëlev├®e | **P2** |
| Options skew | +++ | Tr├¿s ├®lev├®e | **P3** |

**D├®cisions architecturales :**
- **EU stocks report├®s ├á v33** : multi-devise (FX risk EUR/GBP/CHF), exchanges diff├®rents (IBIS/SBF/LSE), heures d├®cal├®es ÔÇö complexit├® disproportionn├®e vs alpha marginal. Les mid-caps US + ETFs donnent 4x plus de paires sans aucune complexit├® FX.
- **Options skew report├® ├á v33** : pipeline enti├¿rement nouveau (reqMktData options, chains, Greeks IV 25-delta) = 3-5 jours de dev pour un alpha incertain.
- **Timeframe intraday report├®e ├á v32** : n├®cessite refactoring de l'annualisation, des half-life en barres, et du MultiTimeframeEngine. A faire apr├¿s validation v31.

---

## Phase 1 : v31 ÔÇö Univers ├ëlargi + Signal Momentum

**Objectif :** Passer de 8 trades/an ├á 80-120 trades/an, viser +15-25% return.  
**Risque :** Faible ÔÇö aucun changement de l'infrastructure core.  
**Dur├®e estim├®e :** 2-3 jours.

---

### ├ëtape 1 ÔÇö ├ëlargir l'Univers US (mid-caps + ETFs sectoriels)

**Objectif :** 37 symboles ÔåÆ ~115 symboles ÔåÆ ~500+ paires intra-secteur.

**Symboles ├á ajouter :**

| Secteur | Symboles mid-cap ├á ajouter |
|---------|---------------------------|
| Technologie / Semi | MRVL, ON, MCHP, QCOM, TXN, AMAT, LRCX, KLAC |
| Biotechnologie / Pharma | GILD, REGN, BIIB, VRTX, BMY, ZTS, MCK |
| Banques r├®gionales | USB, PNC, TFC, RF, CFG, HBAN, KEY |
| Retail / Consumer | TGT, LOW, HD, ROST, TJX, DLTR, DG |
| Media / Communication | CMCSA, DIS, NFLX, FOXA, VZ, T |
| Energie ├®largi | VLO, MPC, PSX, DVN, HAL, BKR |
| Industriels ├®largi | MMM, EMR, ITW, ROK, CMI, PH |
| Sant├® services | CVS, CI, HUM, ELV, CNC |

**ETFs sectoriels ├á ajouter (secType="STK" sur IBKR ÔÇö z├®ro changement de code) :**
=======
### Les 3 Goulots d'Étranglement Identifiés

1. **Univers trop petit** : 37 symboles → ~81 paires intra-secteur. Un univers de 115 symboles = ~500+ paires (loi quadratique : $\binom{N}{2}$ paires).
2. **Signal unique** : le z-score cointegration est le seul alpha. Zero diversification de signal = forte corrélation des trades.
3. **Fréquence trop faible** : 8 trades/an avec barres journalières = 1 décision/jour/paire. La loi des grands nombres ne peut pas jouer.

### Ordre de Priorité (ratio impact/complexité)

| Levier | Impact estimé | Complexité | Priorité |
|--------|:------------:|:----------:|:--------:|
| Univers élargi (mid-caps + ETFs) | +++++ | Faible | **P0** |
| Signal momentum relatif | ++++ | Faible | **P0** |
| Signal combiner/ensemble | +++ | Faible | **P1** |
| Paramètres agressifs | ++++ | Très faible | **P0** |
| Timeframe 1h | ++++ | Moyenne | **P1** |
| Signal MR intraday | +++ | Moyenne | **P2** |
| Actions européennes | ++ | Élevée | **P2** |
| Options skew | +++ | Très élevée | **P3** |

**Décisions architecturales :**
- **EU stocks reportés à v33** : multi-devise (FX risk EUR/GBP/CHF), exchanges différents (IBIS/SBF/LSE), heures décalées — complexité disproportionnée vs alpha marginal. Les mid-caps US + ETFs donnent 4x plus de paires sans aucune complexité FX.
- **Options skew reporté à v33** : pipeline entièrement nouveau (reqMktData options, chains, Greeks IV 25-delta) = 3-5 jours de dev pour un alpha incertain.
- **Timeframe intraday reportée à v32** : nécessite refactoring de l'annualisation, des half-life en barres, et du MultiTimeframeEngine. A faire après validation v31.

---

## Phase 1 : v31 — Univers Élargi + Signal Momentum

**Objectif :** Passer de 8 trades/an à 80-120 trades/an, viser +15-25% return.  
**Risque :** Faible — aucun changement de l'infrastructure core.  
**Durée estimée :** 2-3 jours.

---

### Étape 1 — Élargir l'Univers US (mid-caps + ETFs sectoriels)

**Objectif :** 37 symboles → ~115 symboles → ~500+ paires intra-secteur.

**Symboles à ajouter :**

| Secteur | Symboles mid-cap à ajouter |
|---------|---------------------------|
| Technologie / Semi | MRVL, ON, MCHP, QCOM, TXN, AMAT, LRCX, KLAC |
| Biotechnologie / Pharma | GILD, REGN, BIIB, VRTX, BMY, ZTS, MCK |
| Banques régionales | USB, PNC, TFC, RF, CFG, HBAN, KEY |
| Retail / Consumer | TGT, LOW, HD, ROST, TJX, DLTR, DG |
| Media / Communication | CMCSA, DIS, NFLX, FOXA, VZ, T |
| Energie élargi | VLO, MPC, PSX, DVN, HAL, BKR |
| Industriels élargi | MMM, EMR, ITW, ROK, CMI, PH |
| Santé services | CVS, CI, HUM, ELV, CNC |

**ETFs sectoriels à ajouter (secType="STK" sur IBKR — zéro changement de code) :**
>>>>>>> origin/main

| ETF | Secteur |
|-----|---------|
| XLK | Technology |
| XLF | Financials |
| XLE | Energy |
| XLV | Healthcare |
| XLI | Industrials |
| XLU | Utilities |
| XLP | Consumer Staples |
| XLB | Materials |
| XLC | Communication |
| XLRE | Real Estate |
| SMH | Semiconductors |
| KRE | Regional Banks |
| XBI | Biotech |
| IBB | Biotech large cap |
| IYR | Real Estate |

<<<<<<< HEAD
**Fichiers ├á modifier :**
=======
**Fichiers à modifier :**
>>>>>>> origin/main

| Fichier | Modification |
|---------|-------------|
| `config/config.yaml` | Ajouter ~78 symboles dans `trading_universe.symbols` |
<<<<<<< HEAD
| `config/dev.yaml` | M├¬me ajout |
| `universe/manager.py` | ├ëtendre `DEFAULT_SECTOR_MAP` (~L80-L120) avec nouveaux symboles |
| `scripts/run_backtest_v31.py` | Nouveau script avec `SYMBOLS` et `SECTOR_MAP` ├®largis |

**Compatibilit├® infrastructure :**
- `CorrelationPreFilter` (d├®j├á vectoris├®, supporte 500+ symboles) ÔÇö aucune modification
- `DataLoader.bulk_load()` avec `ThreadPoolExecutor(3)` + rate limiter ÔÇö fonctionne pour 115 symboles (~60s de chargement)
- `IBKRRateLimiter` : 55 req/10min, pool de clients 2001-2008 ÔÇö suffisant pour 115 symboles
- ETFs : `secType="STK"`, `exchange="SMART"`, `currency="USD"` ÔÇö **identique aux actions** dans `execution/ibkr_engine.py:L133-L140`

---

### ├ëtape 2 ÔÇö Signal Momentum Relatif (nouvel alpha)

**Objectif :** Ajouter un second alpha d├®corr├®l├® du z-score cointegration.

**Logique :**
- Pour chaque paire (A, B) : `RS = return_A(N jours) - return_B(N jours)`
- Si RS confirme le z-score ÔåÆ signal renforc├® (`strength = 1.0`)
- Si RS contredit le z-score ÔåÆ signal r├®duit (`strength = 0.3`)
- Le momentum filtre les mauvais trades et amplifie les bons

**Impl├®mentation :**
=======
| `config/dev.yaml` | Même ajout |
| `universe/manager.py` | Étendre `DEFAULT_SECTOR_MAP` (~L80-L120) avec nouveaux symboles |
| `scripts/run_backtest_v31.py` | Nouveau script avec `SYMBOLS` et `SECTOR_MAP` élargis |

**Compatibilité infrastructure :**
- `CorrelationPreFilter` (déjà vectorisé, supporte 500+ symboles) — aucune modification
- `DataLoader.bulk_load()` avec `ThreadPoolExecutor(3)` + rate limiter — fonctionne pour 115 symboles (~60s de chargement)
- `IBKRRateLimiter` : 55 req/10min, pool de clients 2001-2008 — suffisant pour 115 symboles
- ETFs : `secType="STK"`, `exchange="SMART"`, `currency="USD"` — **identique aux actions** dans `execution/ibkr_engine.py:L133-L140`

---

### Étape 2 — Signal Momentum Relatif (nouvel alpha)

**Objectif :** Ajouter un second alpha décorrélé du z-score cointegration.

**Logique :**
- Pour chaque paire (A, B) : `RS = return_A(N jours) - return_B(N jours)`
- Si RS confirme le z-score → signal renforcé (`strength = 1.0`)
- Si RS contredit le z-score → signal réduit (`strength = 0.3`)
- Le momentum filtre les mauvais trades et amplifie les bons

**Implémentation :**
>>>>>>> origin/main

Nouveau fichier : `signal_engine/momentum.py`

```python
class MomentumOverlay:
    """
    Relative momentum overlay for pair signals.
    
    Calculates cross-sectional relative strength between pair legs
    and adjusts signal strength accordingly.
    
    Config params:
        enabled: bool = True
        lookback: int = 20          # Rolling return window (days)
        weight: float = 0.30        # Momentum weight in composite score
        min_strength: float = 0.3   # Floor for contra-momentum signals
        max_boost: float = 1.0      # Cap for momentum-confirmed signals
    """
    
    def compute_relative_strength(
        self, 
        prices_a: pd.Series, 
        prices_b: pd.Series, 
        lookback: int = 20,
    ) -> float:
        """Returns RS = return_A(lookback) - return_B(lookback)."""
        ...
    
    def adjust_signal_strength(
        self, 
        signal: Signal, 
        rs: float, 
        weight: float = 0.30,
    ) -> Signal:
        """
        If signal.side == 'long' (long A, short B):
<<<<<<< HEAD
            - RS > 0 means A outperformed B recently ÔåÆ CONTRA momentum ÔåÆ reduce
            - RS < 0 means A underperformed B recently ÔåÆ WITH momentum ÔåÆ boost
=======
            - RS > 0 means A outperformed B recently → CONTRA momentum → reduce
            - RS < 0 means A underperformed B recently → WITH momentum → boost
>>>>>>> origin/main
        """
        ...
```

<<<<<<< HEAD
**Fichiers ├á modifier/cr├®er :**

| Fichier | Action |
|---------|--------|
| `signal_engine/momentum.py` | **CR├ëER** ÔÇö classe `MomentumOverlay` |
| `signal_engine/generator.py` | **MODIFIER** ÔÇö int├®grer `MomentumOverlay` comme composant optionnel |
| `config/settings.py` | **MODIFIER** ÔÇö ajouter `MomentumConfig` dataclass |
| `config/config.yaml` | **MODIFIER** ÔÇö section `momentum:` |
| `config/dev.yaml` | **MODIFIER** ÔÇö section `momentum:` |
| `tests/test_momentum_signal.py` | **CR├ëER** ÔÇö tests unitaires |

**Param├¿tres configuration :**
=======
**Fichiers à modifier/créer :**

| Fichier | Action |
|---------|--------|
| `signal_engine/momentum.py` | **CRÉER** — classe `MomentumOverlay` |
| `signal_engine/generator.py` | **MODIFIER** — intégrer `MomentumOverlay` comme composant optionnel |
| `config/settings.py` | **MODIFIER** — ajouter `MomentumConfig` dataclass |
| `config/config.yaml` | **MODIFIER** — section `momentum:` |
| `config/dev.yaml` | **MODIFIER** — section `momentum:` |
| `tests/test_momentum_signal.py` | **CRÉER** — tests unitaires |

**Paramètres configuration :**
>>>>>>> origin/main
```yaml
momentum:
  enabled: true
  lookback: 20          # Rolling return window (jours)
  weight: 0.30          # Poids dans le score composite
  min_strength: 0.30    # Floor pour signaux contra-momentum
<<<<<<< HEAD
  max_boost: 1.0        # Cap pour signaux momentum-confirm├®s
=======
  max_boost: 1.0        # Cap pour signaux momentum-confirmés
>>>>>>> origin/main
```

---

<<<<<<< HEAD
### ├ëtape 3 ÔÇö Signal Combiner / Ensemble
=======
### Étape 3 — Signal Combiner / Ensemble
>>>>>>> origin/main

**Objectif :** Infrastructure pour combiner N sources de signal en score composite. Permet d'ajouter facilement les futurs signaux (intraday MR v32, options skew v33).

**Logique :**
```
composite_score = zscore_weight * z_signal + momentum_weight * m_signal
```
Le seuil composite remplace le `entry_z_score` pur.

<<<<<<< HEAD
**Impl├®mentation :**
=======
**Implémentation :**
>>>>>>> origin/main

Nouveau fichier : `signal_engine/combiner.py`

```python
@dataclass
class SignalSource:
    name: str           # "zscore", "momentum", "intraday_mr", "options_skew"
    weight: float       # Contribution to composite score
    enabled: bool = True

class SignalCombiner:
    """
    Weighted ensemble of multiple signal sources.
    
    Outputs a composite_score in [-1, 1] where:
<<<<<<< HEAD
        > threshold  ÔåÆ LONG
        < -threshold ÔåÆ SHORT
        |.| < exit_threshold ÔåÆ EXIT
=======
        > threshold  → LONG
        < -threshold → SHORT
        |.| < exit_threshold → EXIT
>>>>>>> origin/main
    """
    
    def combine(
        self,
        sources: List[Tuple[SignalSource, float]],  # (source, raw_score)
    ) -> float:
        """Returns weighted composite score."""
        ...
    
    def to_signal(
        self,
        composite_score: float,
        entry_threshold: float = 0.6,
        exit_threshold: float = 0.2,
    ) -> str:
        """Maps composite score to 'long' | 'short' | 'exit' | 'none'."""
        ...
```

<<<<<<< HEAD
**Fichiers ├á modifier/cr├®er :**

| Fichier | Action |
|---------|--------|
| `signal_engine/combiner.py` | **CR├ëER** ÔÇö classe `SignalCombiner` + `SignalSource` |
| `strategies/pair_trading.py` | **MODIFIER** ÔÇö `generate_signals()` utilise `SignalCombiner` si activ├® |
| `config/settings.py` | **MODIFIER** ÔÇö ajouter `SignalCombinerConfig` dataclass |
| `tests/test_signal_combiner.py` | **CR├ëER** ÔÇö tests unitaires |

---

### ├ëtape 4 ÔÇö Param├¿tres Agressifs pour Volume

**Objectif :** Maximiser le nombre de trades qualifiants avec l'univers ├®largi.

**Comparaison des param├¿tres :**

| Param├¿tre | v30b | v31 | Justification |
|-----------|:----:|:---:|---------------|
| `entry_z_score` | 1.8 | 1.6 | Plus d'entr├®es |
| `min_correlation` | 0.65 | 0.60 | Plus de paires qualifiantes |
| `max_half_life` | 60 | 70 | Pairs r├®vertantes plus lentes accept├®es |
| `pair_rediscovery_interval` | 2 | 1 | Recherche ├á chaque barre |
| `max_concurrent_positions` | 10 | 20 | Plus de trades simultan├®s |
| `allocation_per_pair` | 50% | 25% | Plus petit par trade, plus diversifi├® |
| `max_portfolio_heat` | 3.0 | 4.0 | Leverage pour exploiter les positions |
| `FDR q` | 0.25 | 0.30 | Plus de paires survivent le filtre statsitique |
| `fdr_q_level` | 0.25 | 0.30 | Coh├®rence avec FDR q |
| `blacklist_max_losses` | 5 | 6 | Moins restrictif |
| `blacklist_cooldown_days` | 10 | 7 | Recyclage plus rapide |
| `weekly_zscore_entry_gate` | 0.3 | 0.2 | Quasi toutes les entr├®es passent |

**Raisonnement sur l'allocation 25% :**
- 20 positions simultan├®es ├ù 25% = 500% heat total (avec levier 4x)
- Chaque trade est plus petit en capital absolu mais plus nombreux
- La corr├®lation entre trades du m├¬me secteur est g├®r├®e par `max_concurrent_positions` par secteur
- Le profit factor 2.02 de v30b + 60% WR ÔåÆ chaque trade individuel est rentable ÔåÆ plus de trades = mieux

---

### ├ëtape 5 ÔÇö Backtest v31 + Validation

**Script :** `scripts/run_backtest_v31.py`

**Param├¿tres :**
```
P├®riode : 2023-03-04 ÔåÆ 2026-03-04 (3 ans, non-n├®gociable)
=======
**Fichiers à modifier/créer :**

| Fichier | Action |
|---------|--------|
| `signal_engine/combiner.py` | **CRÉER** — classe `SignalCombiner` + `SignalSource` |
| `strategies/pair_trading.py` | **MODIFIER** — `generate_signals()` utilise `SignalCombiner` si activé |
| `config/settings.py` | **MODIFIER** — ajouter `SignalCombinerConfig` dataclass |
| `tests/test_signal_combiner.py` | **CRÉER** — tests unitaires |

---

### Étape 4 — Paramètres Agressifs pour Volume

**Objectif :** Maximiser le nombre de trades qualifiants avec l'univers élargi.

**Comparaison des paramètres :**

| Paramètre | v30b | v31 | Justification |
|-----------|:----:|:---:|---------------|
| `entry_z_score` | 1.8 | 1.6 | Plus d'entrées |
| `min_correlation` | 0.65 | 0.60 | Plus de paires qualifiantes |
| `max_half_life` | 60 | 70 | Pairs révertantes plus lentes acceptées |
| `pair_rediscovery_interval` | 2 | 1 | Recherche à chaque barre |
| `max_concurrent_positions` | 10 | 20 | Plus de trades simultanés |
| `allocation_per_pair` | 50% | 25% | Plus petit par trade, plus diversifié |
| `max_portfolio_heat` | 3.0 | 4.0 | Leverage pour exploiter les positions |
| `FDR q` | 0.25 | 0.30 | Plus de paires survivent le filtre statsitique |
| `fdr_q_level` | 0.25 | 0.30 | Cohérence avec FDR q |
| `blacklist_max_losses` | 5 | 6 | Moins restrictif |
| `blacklist_cooldown_days` | 10 | 7 | Recyclage plus rapide |
| `weekly_zscore_entry_gate` | 0.3 | 0.2 | Quasi toutes les entrées passent |

**Raisonnement sur l'allocation 25% :**
- 20 positions simultanées × 25% = 500% heat total (avec levier 4x)
- Chaque trade est plus petit en capital absolu mais plus nombreux
- La corrélation entre trades du même secteur est gérée par `max_concurrent_positions` par secteur
- Le profit factor 2.02 de v30b + 60% WR → chaque trade individuel est rentable → plus de trades = mieux

---

### Étape 5 — Backtest v31 + Validation

**Script :** `scripts/run_backtest_v31.py`

**Paramètres :**
```
Période : 2023-03-04 → 2026-03-04 (3 ans, non-négociable)
>>>>>>> origin/main
Capital : $100,000
Univers : ~115 symboles (37 v30b + 78 nouveaux)
Paires intra-secteur : ~500+
Signaux : z-score + momentum overlay + signal combiner
<<<<<<< HEAD
R├®gime : v30 adaptive bidirectionnel (inchang├®)
```

**Crit├¿res de succ├¿s v31 :**

| Crit├¿re | Seuil | Priorit├® |
=======
Régime : v30 adaptive bidirectionnel (inchangé)
```

**Critères de succès v31 :**

| Critère | Seuil | Priorité |
>>>>>>> origin/main
|---------|:-----:|:--------:|
| Trades >= 60 | Obligatoire | P0 |
| Return > +8% | Obligatoire | P0 |
| Sharpe > 0.9 | Obligatoire | P0 |
| Win Rate >= 50% | Souhaitable | P1 |
| Max DD <= 8% | Obligatoire | P0 |
| Profit Factor > 1.5 | Obligatoire | P0 |

<<<<<<< HEAD
**Tests de r├®gression :**
- Objectif : 2400+ tests passants, 0 ├®chec
=======
**Tests de régression :**
- Objectif : 2400+ tests passants, 0 échec
>>>>>>> origin/main
- Nouveaux tests : `test_momentum_signal.py`, `test_signal_combiner.py`

---

<<<<<<< HEAD
## Phase 2 : v32 ÔÇö Timeframe Intraday 1h

**Pr├®requis :** v31 valid├® (Sharpe > 0.9, Trades > 60).  
**Objectif :** Passer de 1 d├®cision/jour/paire ├á 6-7 d├®cisions/jour/paire.  
=======
## Phase 2 : v32 — Timeframe Intraday 1h

**Prérequis :** v31 validé (Sharpe > 0.9, Trades > 60).  
**Objectif :** Passer de 1 décision/jour/paire à 6-7 décisions/jour/paire.  
>>>>>>> origin/main
**Attention IBKR :** barres 1h = max 1 an d'historique (vs 11 ans pour daily).

---

<<<<<<< HEAD
### ├ëtape 6 ÔÇö Support Timeframe 1h dans le Data Pipeline

**Fichier :** `data/loader.py`

Le `bar_size_map` existe d├®j├á ├á la ligne ~L90 :
=======
### Étape 6 — Support Timeframe 1h dans le Data Pipeline

**Fichier :** `data/loader.py`

Le `bar_size_map` existe déjà à la ligne ~L90 :
>>>>>>> origin/main
```python
bar_size_map = {"1d": "1 day", "1h": "1 hour", "4h": "4 hours", "1m": "1 min"}
```
Il faut le rendre configurable via `settings.strategy.bar_size`.

<<<<<<< HEAD
**Limite IBKR pour 1h :** max 1 an d'historique ÔåÆ `lookback_window` = max 1638 barres (252 ├ù 6.5 heures).

**Fichiers ├á modifier :**

| Fichier | Modification |
|---------|-------------|
| `config/settings.py` | Ajouter `bar_size: str = "1d"` ├á `StrategyConfig` |
| `config/config.yaml` | `strategy.bar_size: "1d"` |
| `data/loader.py` | Rendre `bar_size` param├®trable depuis settings |
| `backtests/runner.py` | Passer `bar_size` ├á `DataLoader` |

---

### ├ëtape 7 ÔÇö Annualisation Dynamique

**Probl├¿me :** `set_trading_days(252)` est hardcod├® dans `backtests/strategy_simulator.py:L183`. Pour les barres horaires, il faut 252 ├ù 6.5 = 1,638.
=======
**Limite IBKR pour 1h :** max 1 an d'historique → `lookback_window` = max 1638 barres (252 × 6.5 heures).

**Fichiers à modifier :**

| Fichier | Modification |
|---------|-------------|
| `config/settings.py` | Ajouter `bar_size: str = "1d"` à `StrategyConfig` |
| `config/config.yaml` | `strategy.bar_size: "1d"` |
| `data/loader.py` | Rendre `bar_size` paramétrable depuis settings |
| `backtests/runner.py` | Passer `bar_size` à `DataLoader` |

---

### Étape 7 — Annualisation Dynamique

**Problème :** `set_trading_days(252)` est hardcodé dans `backtests/strategy_simulator.py:L183`. Pour les barres horaires, il faut 252 × 6.5 = 1,638.
>>>>>>> origin/main

**Calcul selon timeframe :**

| Timeframe | Barres/an | Formule |
|-----------|:---------:|---------|
<<<<<<< HEAD
| `1d` | 252 | 252 ├ù 1 |
| `4h` | 819 | 252 ├ù 6.5 / 2 |
| `1h` | 1,638 | 252 ├ù 6.5 |
| `15min` | 6,552 | 252 ├ù 6.5 ├ù 4 |
| `5min` | 19,656 | 252 ├ù 6.5 ├ù 13 |

**Fichiers ├á modifier :**
=======
| `1d` | 252 | 252 × 1 |
| `4h` | 819 | 252 × 6.5 / 2 |
| `1h` | 1,638 | 252 × 6.5 |
| `15min` | 6,552 | 252 × 6.5 × 4 |
| `5min` | 19,656 | 252 × 6.5 × 13 |

**Fichiers à modifier :**
>>>>>>> origin/main

| Fichier | Modification |
|---------|-------------|
| `backtests/strategy_simulator.py` | Remplacer `set_trading_days(252)` par calcul dynamique depuis `bar_size` |
| `backtests/metrics.py` | Propager `trading_days_per_year` dans Sharpe, Sortino, VaR |

---

<<<<<<< HEAD
### ├ëtape 8 ÔÇö Half-Life en Barres (pas en Jours)

**Probl├¿me :** Partout dans le code, le half-life est en "jours". Pour les barres horaires, `half_life=25` signifie 25 heures (~4 jours de trading), pas 25 jours.
=======
### Étape 8 — Half-Life en Barres (pas en Jours)

**Problème :** Partout dans le code, le half-life est en "jours". Pour les barres horaires, `half_life=25` signifie 25 heures (~4 jours de trading), pas 25 jours.
>>>>>>> origin/main

**Impact :** `TimeStopConfig`, `max_half_life` dans StrategyConfig, `time_stop_multiplier`, cache TTL.

**Solution :** Tout raisonner en "barres" avec conversion :
<<<<<<< HEAD
- `max_half_life_bars = max_half_life ├ù (bars_per_day)`
- `time_stop_bars = time_stop_multiplier ├ù half_life_bars`

**Fichiers ├á modifier :**

| Fichier | Modification |
|---------|-------------|
| `execution/time_stop.py` | `max_days_cap` ÔåÆ `max_bars_cap` avec conversion |
| `backtests/strategy_simulator.py` | Conversion half_life jours ÔåÆ barres |
| `config/settings.py` | Documenter unit├® (jours vs barres) dans StrategyConfig |

---

### ├ëtape 9 ÔÇö Signal Mean-Reversion Intraday

**Objectif :** Signal plus r├®actif sur donn├®es horaires.
=======
- `max_half_life_bars = max_half_life × (bars_per_day)`
- `time_stop_bars = time_stop_multiplier × half_life_bars`

**Fichiers à modifier :**

| Fichier | Modification |
|---------|-------------|
| `execution/time_stop.py` | `max_days_cap` → `max_bars_cap` avec conversion |
| `backtests/strategy_simulator.py` | Conversion half_life jours → barres |
| `config/settings.py` | Documenter unité (jours vs barres) dans StrategyConfig |

---

### Étape 9 — Signal Mean-Reversion Intraday

**Objectif :** Signal plus réactif sur données horaires.
>>>>>>> origin/main

Nouveau fichier : `signal_engine/intraday_mr.py`

```python
class IntradayMeanReversion:
    """
    Fast z-score on intraday data (lookback 10-20 barres = 2-3h).
    
    Filtre vol-of-vol : ne trader que quand la vol intraday est dans le 
<<<<<<< HEAD
    25e-75e percentile (├®viter les r├®gimes extr├¬mes).
=======
    25e-75e percentile (éviter les régimes extrêmes).
>>>>>>> origin/main
    
    Config params:
        enabled: bool = True
        fast_lookback: int = 12     # ~2h de barres 15min
        vol_of_vol_window: int = 48 # ~1 semaine de barres horaires
        vol_percentile_low: float = 0.25
        vol_percentile_high: float = 0.75
    """
    ...
```

<<<<<<< HEAD
**Int├®gration dans le `SignalCombiner` (├ëtape 3) comme 3e source.**

---

### ├ëtape 10 ÔÇö Refactorer MultiTimeframeEngine

**Fichier :** `data/multi_timeframe.py`

**├ëtat actuel :** `MTFConfig.timeframes` = `["D", "W"]` seulement.

**Cible :** `["1h", "D", "W"]` ÔÇö le signal 1h prend les d├®cisions, le daily confirme la tendance, le weekly valide la cointegration.
=======
**Intégration dans le `SignalCombiner` (Étape 3) comme 3e source.**

---

### Étape 10 — Refactorer MultiTimeframeEngine

**Fichier :** `data/multi_timeframe.py`

**État actuel :** `MTFConfig.timeframes` = `["D", "W"]` seulement.

**Cible :** `["1h", "D", "W"]` — le signal 1h prend les décisions, le daily confirme la tendance, le weekly valide la cointegration.
>>>>>>> origin/main

```python
# Cible v32
MTFConfig(
    timeframes=["1h", "D"],       # Primary=1h, Confirmation=D
<<<<<<< HEAD
    primary="1h",                  # D├®cisions sur 1h
=======
    primary="1h",                  # Décisions sur 1h
>>>>>>> origin/main
    confirmation="D",              # Gate sur daily
    weekly_gate=True,              # Filtre hebdomadaire (existant)
)
```

---

<<<<<<< HEAD
## Phase 3 : v33 ÔÇö International + Options Skew

**Pr├®requis :** v32 valid├® (Sharpe > 1.0, Trades > 200).  
**Objectif :** Ajouter les march├®s europ├®ens et le signal options skew.

---

### ├ëtape 11 ÔÇö Contract Factory pour EU/Multi-Devise

**Probl├¿me :** `secType="STK"`, `exchange="SMART"`, `currency="USD"` hardcod├®s dans `execution/ibkr_engine.py:L133-L140` (3+ locations).
=======
## Phase 3 : v33 — International + Options Skew

**Prérequis :** v32 validé (Sharpe > 1.0, Trades > 200).  
**Objectif :** Ajouter les marchés européens et le signal options skew.

---

### Étape 11 — Contract Factory pour EU/Multi-Devise

**Problème :** `secType="STK"`, `exchange="SMART"`, `currency="USD"` hardcodés dans `execution/ibkr_engine.py:L133-L140` (3+ locations).
>>>>>>> origin/main

**Solution :** Extraire une `ContractFactory` :

```python
class ContractFactory:
    """Creates IBKR Contract objects for different asset classes and regions."""
    
    EXCHANGE_MAP = {
        "US": "SMART",
        "DE": "IBIS",     # XETRA (SAP, SIE, BMW...)
        "FR": "SBF",      # Euronext Paris (TTE, SAN, BNP...)
        "UK": "LSE",      # London Stock Exchange
        "NL": "AEB",      # Euronext Amsterdam
    }
    
    CURRENCY_MAP = {
        "US": "USD",
        "DE": "EUR",
        "FR": "EUR",
        "UK": "GBP",
        "NL": "EUR",
    }
    
    @classmethod
    def create(cls, symbol: str, region: str = "US", sec_type: str = "STK") -> Contract:
        ...
```

<<<<<<< HEAD
**Symboles EU ├á ajouter :**
=======
**Symboles EU à ajouter :**
>>>>>>> origin/main

| Pays | Symboles | Secteur |
|------|----------|---------|
| Allemagne | SAP, SIE, ALV, BAS, BAYN, BMW, MBG, VOW | Tech, Industrials, Financials, Chim, Healthcare, Auto |
| France | TTE, SAN, BNP, AIR, OR, LVMH, MC, SU | Energie, Healthcare, Financials, Aerospace, Consumer |
| Pays-Bas | SHELL, ASML, PHG, ING | Energie, Tech, Healthcare, Financials |

---

<<<<<<< HEAD
### ├ëtape 12 ÔÇö Multi-Currency P&L
=======
### Étape 12 — Multi-Currency P&L
>>>>>>> origin/main

**Fichier :** `backtests/metrics.py`

**Ajouts :**
<<<<<<< HEAD
- Conversion FX EURÔåÆUSD via taux historiques IBKR (`reqHistoricalData` sur paires FX : `EURUSD`, `GBPUSD`)
- Positions EU comptabilis├®es en devise locale, P&L converti en USD pour le portefeuille
- Nouveau param├¿tre `costs.fx_spread_bps: 1.0` pour frais de change

---

### ├ëtape 13 ÔÇö Options Skew Signal
=======
- Conversion FX EUR→USD via taux historiques IBKR (`reqHistoricalData` sur paires FX : `EURUSD`, `GBPUSD`)
- Positions EU comptabilisées en devise locale, P&L converti en USD pour le portefeuille
- Nouveau paramètre `costs.fx_spread_bps: 1.0` pour frais de change

---

### Étape 13 — Options Skew Signal
>>>>>>> origin/main

**Nouveau pipeline :** `signal_engine/options_skew.py`

**Logique :**
<<<<<<< HEAD
- `reqMktData` IBKR pour options (put/call IV ├á 25-delta)
- `Skew = IV_put_25d - IV_call_25d`
- Put skew ├®lev├® = march├® craintif = mean-reversion favorable (march├® peut surr├®agir)
- Put skew faible = complaisance = risque de tendance (MR moins fiable)

**Pipeline IBKR n├®cessaire :**
```
reqContractDetails(optionChain) 
ÔåÆ s├®lectionner strikes ┬▒25 delta
ÔåÆ reqMktData(IV, Greeks)
ÔåÆ calculer skew_score
ÔåÆ int├®grer dans SignalCombiner
```

**Int├®gration dans `SignalCombiner` comme 4e source d'alpha.**

---

## R├®sum├® des Crit├¿res de Succ├¿s
=======
- `reqMktData` IBKR pour options (put/call IV à 25-delta)
- `Skew = IV_put_25d - IV_call_25d`
- Put skew élevé = marché craintif = mean-reversion favorable (marché peut surréagir)
- Put skew faible = complaisance = risque de tendance (MR moins fiable)

**Pipeline IBKR nécessaire :**
```
reqContractDetails(optionChain) 
→ sélectionner strikes ±25 delta
→ reqMktData(IV, Greeks)
→ calculer skew_score
→ intégrer dans SignalCombiner
```

**Intégration dans `SignalCombiner` comme 4e source d'alpha.**

---

## Résumé des Critères de Succès
>>>>>>> origin/main

| Version | Trades/an | Return | Sharpe | Max DD | Win Rate |
|---------|:---------:|:------:|:------:|:------:|:--------:|
| v30b (baseline) | ~8 | +5.25% | 0.74 | -2.63% | 60% |
| **v31 (cible)** | **80-120** | **>+15%** | **>1.0** | **<8%** | **>50%** |
| v32 (cible) | 200-500 | >+20% | >1.2 | <10% | >50% |
| v33 (cible) | 500-1000 | >+25% | >1.5 | <12% | >48% |

---

<<<<<<< HEAD
## R├®sum├® des Fichiers Impact├®s par Phase

### Phase 1 (v31) ÔÇö Fichiers ├á modifier/cr├®er

| Fichier | Action | ├ëtape |
|---------|--------|-------|
| `config/config.yaml` | MODIFIER ÔÇö +78 symboles universe | 1 |
| `config/dev.yaml` | MODIFIER ÔÇö +78 symboles universe | 1 |
| `universe/manager.py` | MODIFIER ÔÇö ├®tendre DEFAULT_SECTOR_MAP | 1 |
| `signal_engine/momentum.py` | **CR├ëER** ÔÇö MomentumOverlay | 2 |
| `signal_engine/generator.py` | MODIFIER ÔÇö int├®grer MomentumOverlay | 2 |
| `signal_engine/combiner.py` | **CR├ëER** ÔÇö SignalCombiner + SignalSource | 3 |
| `strategies/pair_trading.py` | MODIFIER ÔÇö utiliser SignalCombiner | 3 |
| `config/settings.py` | MODIFIER ÔÇö MomentumConfig + SignalCombinerConfig | 2, 3 |
| `config/schemas.py` | MODIFIER ÔÇö nouveaux champs schema | 2, 3 |
| `tests/test_momentum_signal.py` | **CR├ëER** ÔÇö tests unitaires momentum | 2 |
| `tests/test_signal_combiner.py` | **CR├ëER** ÔÇö tests unitaires combiner | 3 |
| `scripts/run_backtest_v31.py` | **CR├ëER** ÔÇö script backtest v31 | 5 |

### Phase 2 (v32) ÔÇö Fichiers ├á modifier/cr├®er

| Fichier | Action | ├ëtape |
|---------|--------|-------|
| `config/settings.py` | MODIFIER ÔÇö ajouter `bar_size` ├á StrategyConfig | 6 |
| `config/config.yaml` | MODIFIER ÔÇö `strategy.bar_size: "1d"` | 6 |
| `data/loader.py` | MODIFIER ÔÇö `bar_size` param├®trable depuis settings | 6 |
| `backtests/runner.py` | MODIFIER ÔÇö passer `bar_size` ├á DataLoader | 6 |
| `backtests/strategy_simulator.py` | MODIFIER ÔÇö annualisation dynamique | 7 |
| `backtests/metrics.py` | MODIFIER ÔÇö propager `trading_days_per_year` | 7 |
| `execution/time_stop.py` | MODIFIER ÔÇö `max_days_cap` ÔåÆ `max_bars_cap` | 8 |
| `signal_engine/intraday_mr.py` | **CR├ëER** ÔÇö IntradayMeanReversion | 9 |
| `data/multi_timeframe.py` | MODIFIER ÔÇö support timeframes 1h | 10 |
| `scripts/run_backtest_v32.py` | **CR├ëER** ÔÇö script backtest v32 1h | ÔÇö |

### Phase 3 (v33) ÔÇö Fichiers ├á modifier/cr├®er

| Fichier | Action | ├ëtape |
|---------|--------|-------|
| `execution/ibkr_engine.py` | MODIFIER ÔÇö ContractFactory | 11 |
| `execution/contract_factory.py` | **CR├ëER** ÔÇö ContractFactory | 11 |
| `universe/manager.py` | MODIFIER ÔÇö support r├®gions EU | 11 |
| `backtests/metrics.py` | MODIFIER ÔÇö multi-currency P&L | 12 |
| `signal_engine/options_skew.py` | **CR├ëER** ÔÇö OptionsSkewSignal | 13 |
| `config/settings.py` | MODIFIER ÔÇö FXConfig, OptionsConfig | 11, 13 |
| `scripts/run_backtest_v33.py` | **CR├ëER** ÔÇö script backtest v33 | ÔÇö |

---

## R├¿gles d'Ex├®cution

1. **Chaque ├®tape est valid├®e par les tests de r├®gression avant de passer ├á la suivante**
2. **Le backtest v31 doit tourner sur la m├¬me fen├¬tre que v30b** : 2023-03-04 ÔåÆ 2026-03-04 (r├¿gle non-n├®gociable)
3. **Les tests de r├®gression doivent rester ├á 0 ├®chec** apr├¿s chaque modification
4. **Aucune modification de code live** tant que les tests unitaires de la nouvelle fonctionnalit├® ne passent pas
5. **Le syst├¿me v30b reste fonctionnel** ├á tout moment ÔÇö aucun changement destructif

---

*Document g├®n├®r├® le 4 mars 2026. Les corrections seront appliqu├®es ├®tape par ├®tape.*
=======
## Résumé des Fichiers Impactés par Phase

### Phase 1 (v31) — Fichiers à modifier/créer

| Fichier | Action | Étape |
|---------|--------|-------|
| `config/config.yaml` | MODIFIER — +78 symboles universe | 1 |
| `config/dev.yaml` | MODIFIER — +78 symboles universe | 1 |
| `universe/manager.py` | MODIFIER — étendre DEFAULT_SECTOR_MAP | 1 |
| `signal_engine/momentum.py` | **CRÉER** — MomentumOverlay | 2 |
| `signal_engine/generator.py` | MODIFIER — intégrer MomentumOverlay | 2 |
| `signal_engine/combiner.py` | **CRÉER** — SignalCombiner + SignalSource | 3 |
| `strategies/pair_trading.py` | MODIFIER — utiliser SignalCombiner | 3 |
| `config/settings.py` | MODIFIER — MomentumConfig + SignalCombinerConfig | 2, 3 |
| `config/schemas.py` | MODIFIER — nouveaux champs schema | 2, 3 |
| `tests/test_momentum_signal.py` | **CRÉER** — tests unitaires momentum | 2 |
| `tests/test_signal_combiner.py` | **CRÉER** — tests unitaires combiner | 3 |
| `scripts/run_backtest_v31.py` | **CRÉER** — script backtest v31 | 5 |

### Phase 2 (v32) — Fichiers à modifier/créer

| Fichier | Action | Étape |
|---------|--------|-------|
| `config/settings.py` | MODIFIER — ajouter `bar_size` à StrategyConfig | 6 |
| `config/config.yaml` | MODIFIER — `strategy.bar_size: "1d"` | 6 |
| `data/loader.py` | MODIFIER — `bar_size` paramétrable depuis settings | 6 |
| `backtests/runner.py` | MODIFIER — passer `bar_size` à DataLoader | 6 |
| `backtests/strategy_simulator.py` | MODIFIER — annualisation dynamique | 7 |
| `backtests/metrics.py` | MODIFIER — propager `trading_days_per_year` | 7 |
| `execution/time_stop.py` | MODIFIER — `max_days_cap` → `max_bars_cap` | 8 |
| `signal_engine/intraday_mr.py` | **CRÉER** — IntradayMeanReversion | 9 |
| `data/multi_timeframe.py` | MODIFIER — support timeframes 1h | 10 |
| `scripts/run_backtest_v32.py` | **CRÉER** — script backtest v32 1h | — |

### Phase 3 (v33) — Fichiers à modifier/créer

| Fichier | Action | Étape |
|---------|--------|-------|
| `execution/ibkr_engine.py` | MODIFIER — ContractFactory | 11 |
| `execution/contract_factory.py` | **CRÉER** — ContractFactory | 11 |
| `universe/manager.py` | MODIFIER — support régions EU | 11 |
| `backtests/metrics.py` | MODIFIER — multi-currency P&L | 12 |
| `signal_engine/options_skew.py` | **CRÉER** — OptionsSkewSignal | 13 |
| `config/settings.py` | MODIFIER — FXConfig, OptionsConfig | 11, 13 |
| `scripts/run_backtest_v33.py` | **CRÉER** — script backtest v33 | — |

---

## Règles d'Exécution

1. **Chaque étape est validée par les tests de régression avant de passer à la suivante**
2. **Le backtest v31 doit tourner sur la même fenêtre que v30b** : 2023-03-04 → 2026-03-04 (règle non-négociable)
3. **Les tests de régression doivent rester à 0 échec** après chaque modification
4. **Aucune modification de code live** tant que les tests unitaires de la nouvelle fonctionnalité ne passent pas
5. **Le système v30b reste fonctionnel** à tout moment — aucun changement destructif

---

*Document généré le 4 mars 2026. Les corrections seront appliquées étape par étape.*
>>>>>>> origin/main
