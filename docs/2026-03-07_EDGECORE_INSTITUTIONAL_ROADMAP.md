# EDGECORE — Roadmap Institutional-Grade

**De v31h → Système Stat-Arb Institutionnel**
**Capital de départ : 100 000 €**
**Date : 7 mars 2026**

## Situation Actuelle — v31h (Baseline)

Trades:        24 / 3 ans  Univers:   37 sym     Levier:    1×
Signaux:       2 (cointé + momentum)
## Cible Institutionnelle

Trades:        500+/an     Univers:   200+ sym    Levier:    2-4×
Signaux:       10+         Factor-neutral: Oui
## GAP ANALYSIS — Priorité par Impact

| # | Gap | Impact PnL | Effort | Priorité |
|---|-----|-----------|--------|----------|
| 1 | Modèle de slippage absent | -30 à -50% du PnL réel | Moyen | **CRITIQUE** |
| 2 | Position sizing naïf (50%/paire) | Risque de ruine | Moyen | **CRITIQUE** |
| 3 | Trop peu de trades (8/an) | Sharpe instable | Élevé | **HAUTE** |
| 4 | Pas de factor-neutralité | Prise de beta camouflée | Moyen | **HAUTE** |
| 5 | Signaux alpha limités (2) | Alpha fragile, single point of failure | Élevé | **HAUTE** |
| 6 | Pas d'intraday | Latence de signal | Élevé | MOYENNE |
| 7 | Pas de multi-marché | Diversification limitée | Élevé | MOYENNE |
| 8 | Exécution manuelle/basique | Market impact non contrôlé | Moyen | MOYENNE |
| 9 | Infrastructure non scalable | Limite de croissance | Élevé | BASSE (pour l'instant) |
| 10 | Données alternatives absentes | Alpha additionnel | Élevé | BASSE (capital requis) |

---

## PHASE 0 — FONDATIONS CRITIQUES (Mois 1-2)
**Objectif : Rendre v31h réaliste et deployable en live**
**Capital requis : 0 € (code uniquement)**

### Étape 0.1 — Modèle de Slippage Réaliste
**Priorité : BLOQUANTE — sans ça, tous les résultats sont optimistes**
Fichiers : execution/slippage.py (NOUVEAU)
           backtests/strategy_simulator.py (MODIFIER)
```

**Modèle à implémenter :**
```python
# Modèle de slippage à 3 composantes

# 1. SPREAD fixe (bid-ask)
spread_cost_bps = 2.0  # ~2 bps pour mega-caps US

# 2. MARKET IMPACT (Almgren-Chriss simplifié)
# impact = η × σ_daily × √(Q / ADV)
# η = constante d'impact (~0.1 pour mega-caps)
# Q = quantité tradée, ADV = volume quotidien moyen

# 3. TIMING COST
# Delay cost = σ × √(T_execution / 252)
# T_execution = temps d'exécution en jours
```

**Livrables :**
- [ ] `SlippageModel` class avec 3 composantes
- [ ] Intégration dans `strategy_simulator.py` (chaque entry/exit)
- [ ] Chargement ADV (Average Daily Volume) depuis IBKR
- [ ] Re-backtest v31h avec slippage → nouveau baseline réaliste
- [ ] **Critère de validation** : v31h + slippage doit rester PF > 1.5

### Étape 0.2 — Position Sizing Kelly/Risque
**50% du capital par paire = risque de ruine. Inacceptable.**

```
Impact : Réduction du DD de -50%, stabilisation du Sharpe
Fichiers : risk/kelly_sizing.py (NOUVEAU)
           backtests/strategy_simulator.py (MODIFIER sizing)
```

**Implémentation :**
```python
# Kelly Criterion fractionnel
# f* = (p × b - q) / b   où p=win_rate, b=avg_win/avg_loss, q=1-p
# Position = f* × fraction_kelly × capital
# fraction_kelly = 0.25 (quart-Kelly = standard institutionnel)

# Avec plafonds :
max_position_pct = 10.0      # Max 10% par paire (vs 50% actuel!)
max_sector_pct = 25.0        # Max 25% par secteur
max_gross_leverage = 2.0     # Levier brut max 200% (Phase 0)
```

**Livrables :**
- [ ] `KellySizer` class avec Kelly fractionnel
- [ ] Plafonds par position, par secteur, levier brut
- [ ] **Stop-loss par trade en % du NAV total** (pas du notionnel) :
  ```
  max_loss_per_trade_nav = 0.75%   # du NAV total
  # Exemple : NAV = 100K€, max perte par trade = 750€
  # Actuel : stop 7% × 50% alloc = 3.5% du NAV = 3 500€ → trop élevé
  # Avec Kelly 10% alloc : stop 7% × 10% = 0.7% du NAV ✓
  # Le plafond NAV garantit la limite même si le sizing change
  ```
- [ ] Intégration dans le simulator
- [ ] Re-backtest v31h avec Kelly sizing → comparer
- [ ] **Critère** : DD < 5%, Sharpe stable ou amélioré

### Étape 0.3 — Earnings & Dividende Filter
**Les firmes ne tradent JAMAIS autour des earnings.**

```
Impact : Évite 2-3 trades catastrophiques par an
Fichiers : data/event_filter.py (NOUVEAU)
           strategies/pair_trading.py (MODIFIER)
```

**Livrables :**
- [ ] Calendrier earnings via API (Yahoo Finance gratuit)
- [ ] Blackout ±3 jours autour de la date de reporting
- [ ] Filtre ex-dividende (spread pollué J-1/J+1)
- [ ] Intégration dans `generate_signals()` comme gate
- [ ] Re-backtest pour mesurer impact

### Étape 0.4 — Short Borrow Availability Check
**Sans locate, le short leg du pair trade échoue en live.**

```
Impact : Prévient les échecs d'exécution + costs de borrow imprévus
Fichiers : execution/borrow_check.py (NOUVEAU)
           execution/ibkr_execution.py (MODIFIER)
```

**Implémentation :**
```python
# Vérifier AVANT d'envoyer l'ordre :
#   1. Shortable? → IBKR reqContractDetails().shortableShares
#   2. Borrow fee? → Si fee > 3% annualisé, REJETER le trade
#   3. Availability? → Si shortableShares < quantité requise, REJETER
#
# Pour le backtest :
#   Les 37 mega-caps de v31h sont quasi-toujours shortable (HTB < 1%)
#   Mais lors de l'expansion univers (Phase 1.5), certains mid-caps
#   peuvent être Hard-To-Borrow → filtre essentiel
```

**Livrables :**
- [ ] `BorrowChecker` : query IBKR shortable shares + fee rate
- [ ] Gate dans l'exécution : rejeter si non-shortable ou fee > 3%
- [ ] Logging : tracker les rejets pour identifier les symboles problématiques
- [ ] Intégration backtest : flag HTB historique (approximation via market cap)

---

## PHASE 1 — AUGMENTATION DES SIGNAUX (Mois 2-4)
**Objectif : Passer de 2 signaux à 6-8, augmenter les trades à 50+/an**
**Capital requis : 0 € (données gratuites)**

### Étape 1.1 — Ornstein-Uhlenbeck Signal
**Le spread z-score actuel est statique. OU modélise la vitesse de reversion.**

```
Alpha additionnel estimé : +20-30% de trades qualifiés
Fichiers : signal_engine/ou_signal.py (NOUVEAU)
```

**Concept :**
```python
# Au lieu de simplement z = (spread - mean) / std,
# modéliser le processus OU : dX = θ(μ - X)dt + σdW
# θ = vitesse de mean-reversion (lié à half-life)
# Signal = θ × (μ - X) / σ  → "expected profit velocity"
# Entrer quand la vitesse de reversion est HAUTE, pas juste z > seuil
```

**Livrables :**
- [ ] `OUSignalGenerator` : estimation θ, μ, σ par fenêtre glissante
- [ ] Signal : expected reversion velocity
- [ ] Intégration dans `SignalCombiner` (déjà créé mais non wired)
- [ ] Backtest comparatif : OU seul vs z-score seul vs combiné

### Étape 1.2 — Cross-Sectional Momentum Signal
**Le momentum overlay actuel est time-series. Ajouter cross-sectional.**

```
Alpha additionnel estimé : +15-25% de Sharpe
Fichiers : signal_engine/cross_sectional.py (NOUVEAU)
```

**Concept :**
```python
# Ranker tous les symboles par return sur [1M, 3M, 6M, 12M]
# Pour un pair trade A/B :
#   Si rank(A) >> rank(B) → signal short le spread (A surperformera)
#   Si rank(A) << rank(B) → signal long le spread (B rattrapera)
# Combiné avec cointegration : entrée quand BOTH confirment
```

**Livrables :**
- [ ] `CrossSectionalMomentum` : ranking par fenêtre
- [ ] Signal de confirmation croisée avec z-score
- [ ] Intégration dans `SignalCombiner`
- [ ] Backtest A/B

### Étape 1.3 — Volatilité Relative Signal
**Entrer quand la vol du spread est BASSE = faible risque, sortir quand haute.**

```
Fichiers : signal_engine/vol_signal.py (NOUVEAU)
```

**Concept :**
```python
# spread_vol = rolling_std(spread_returns, window=20)
# vol_ratio = spread_vol / spread_vol.rolling(60).mean()
# Entrer seulement quand vol_ratio < 0.8 (vol compressée)
# Sortir si vol_ratio > 1.5 (explosion de vol = régime cassé)
```

**Livrables :**
- [ ] `VolatilityRegimeSignal` class
- [ ] Gate d'entrée : vol_ratio < seuil
- [ ] Gate de sortie : vol explosion
- [ ] Backtest comparatif

### Étape 1.4 — Wiring du SignalCombiner
**Le `SignalCombiner` existe déjà mais n'est wired nulle part.**

```
Fichiers : signal_engine/combiner.py (EXISTE)
           strategies/pair_trading.py (MODIFIER)
           backtests/strategy_simulator.py (MODIFIER)
```

**Livrables :**
- [ ] Intégrer `SignalCombiner` dans le pipeline backtest
- [ ] Pondération initiale : equal-weight entre signaux
- [ ] Seuil combiné : entrer quand ≥ 3/5 signaux confirment
- [ ] Backtest multi-signal vs v31h baseline
- [ ] **Critère** : Plus de trades (40+) avec PF ≥ 2.0

### Étape 1.5 — Expansion Univers Intelligente (par Secteur)
**L'expansion brute a échoué (v31d-j). Stratégie : ajouter 1 secteur à la fois.**

```
Insight crucial de v31 : chaque ajout de symbole doit être PROUVÉ
par backtest isolé avant intégration.
```

**Méthode :**
```
Pour chaque candidat (ex: COST, INTC, BLK, LMT...) :
  1. Ajouter UN SEUL symbole à l'univers v31h
  2. Backtest → mesurer delta Sharpe et delta PF
  3. Si delta Sharpe > 0 ET delta PF > 0 → GARDER
  4. Sinon → REJETER
  5. Après validation, ajouter le suivant

Ordre de test (par qualité attendue) :
  Tech:   INTC, QCOM, TXN (semis solides)
  Fin:    BLK (mega cap)
  Energy: SLB, VLO (haute liquidité)
  Indust: LMT (défense, décorrélé)
  Health: LLY, TMO (mega pharma)
  ETFs:   XLK, XLF, XLE (excellent pour pairing)
```

**Livrables :**
- [ ] Script de test incrémental automatisé
- [ ] Tableau symbole-par-symbole : delta Sharpe, delta PF
- [ ] Univers validé "v32" : v31h + symboles prouvés
- [ ] **Critère** : Univers 40-55 sym, Sharpe ≥ 1.2, Trades ≥ 40/an

---

## PHASE 2 — RISK MANAGEMENT INSTITUTIONNEL (Mois 4-6)
**Objectif : Factor-neutralité, contrôle du risque portfolio**
**Capital requis : 0 € (calculs internes)**

### Étape 2.1 — Beta-Neutralité Portfolio
```
Fichiers : risk/factor_model.py (NOUVEAU)
           risk/portfolio_optimizer.py (NOUVEAU)
```

**Implémentation :**
```python
# Pour chaque position :
#   beta_A = cov(R_A, R_SPY) / var(R_SPY)  rolling 60 jours
#   beta_B = cov(R_B, R_SPY) / var(R_SPY)
#   Ajuster les poids du pair trade pour que beta_net ≈ 0
#   Si pair = long A, short B :
#     w_A = 1.0, w_B = -(beta_A / beta_B)  → beta neutral
#
# Au niveau portfolio :
#   sum(beta_i × notional_i) / total_notional < 0.05
```

**Livrables :**
- [ ] Estimation beta rolling par symbole
- [ ] Ajustement des hedge ratios pour beta-neutralité
- [ ] Contrainte portfolio : |beta_net| < 0.05
- [ ] Monitoring du beta en temps réel (live trading)

### Étape 2.2 — Sector-Neutralité + Corrélation Inter-Positions
```
Fichiers : risk/sector_limits.py (NOUVEAU)
           risk/position_correlation.py (NOUVEAU)
```

**Corrélation inter-positions — VITAL :**
```python
# Si pair_trade_A et pair_trade_B sont corrélés > 0.30,
# un seul événement (ex: choc tech) wipe les deux simultanément.
# Avec sizing concentré, c'est catastrophique.
#
# Implémentation :
#   corr_matrix = rolling_corr(spread_returns, window=60)
#   Pour chaque nouveau trade :
#     Si corr(nouveau_spread, spread_ouvert) > 0.30 → REJETER
#     ou réduire le sizing proportionnellement
#
# max_pair_correlation = 0.30  # entre les POSITIONS (retours des spreads)
# max_correlated_exposure = 15% du NAV  # ensemble corrélé
```

**Livrables :**
- [ ] `PositionCorrelationMonitor` : matrice de corrélation rolling des spreads
- [ ] Gate d'entrée : rejeter si corr > 0.30 avec position existante
- [ ] Contrainte : max 25% du NAV par secteur
- [ ] Rebalancement automatique si dépassement
- [ ] Dashboard sector exposure + correlation heatmap

### Étape 2.3 — Portfolio VaR / CVaR Limits
```
Fichiers : risk/var_monitor.py (NOUVEAU)
```

**Livrables :**
- [ ] VaR 95% historique rolling 60j
- [ ] CVaR 95% (Expected Shortfall)
- [ ] Circuit-breaker : stop trading si VaR > 2% du NAV
- [ ] Rapport quotidien de risque

### Étape 2.4 — Drawdown Management Multi-Niveaux
```
TIER 1 (DD > 3%)  : Réduire sizing de 50%
TIER 2 (DD > 5%)  : Fermer 50% des positions
TIER 3 (DD > 8%)  : Fermer TOUTES les positions, cooldown 10 jours
TIER 4 (DD > 12%) : Arrêt complet, review manuelle obligatoire
```

**Livrables :**
- [ ] `DrawdownManager` multi-tier
- [ ] Intégration backtest + live
- [ ] Alertes email/SMS à chaque tier

---

## PHASE 3 — FRÉQUENCE & EXÉCUTION (Mois 6-9)
**Objectif : Passer de daily à intraday, exécution algorithmique**
**Capital requis : ~500 €/an (données intraday + serveur)**

### Étape 3.1 — Données Intraday (5min bars)
```
Source : IBKR Historical Data (inclus dans l'abonnement)
Stockage : SQLite ou Parquet local
Fichiers : data/intraday_loader.py (NOUVEAU)
```

**Livrables :**
- [ ] Collecteur de données 5min depuis IBKR
- [ ] Stockage Parquet partitionné par date/symbole
- [ ] Adaptation du backtest simulator pour barres 5min
- [ ] Validation : v31h sur 5min bars vs daily

### Étape 3.2 — Signaux Intraday
```
Fichiers : signal_engine/intraday_signals.py (NOUVEAU)
```

**Nouveaux signaux possibles en intraday :**
```python
# 1. Mean-reversion intraday du spread
#    → z-score recalculé toutes les 5min
#    → entry/exit plus fréquents

# 2. Opening gap reversion
#    → Si le spread gap à l'open, mean-revert dans les 2h

# 3. Volume profile signal
#    → Entrer quand le volume confirme la direction du spread
```

**Livrables :**
- [ ] Adaptation du z-score pour fenêtres intraday
- [ ] Signal gap-reversion
- [ ] Backtest intraday
- [ ] **Critère** : Trades ≥ 200/an, Sharpe ≥ 1.5

### Étape 3.3 — Exécution Algorithmique (TWAP/VWAP)
```
Fichiers : execution/algo_executor.py (NOUVEAU)
           execution/ibkr_algo.py (NOUVEAU)
```

**Implémentation :**
```python
# TWAP : découper l'ordre en N tranches sur T minutes
# VWAP : pondérer les tranches par le profil de volume historique
# Participation rate : max 5% du volume quotidien
# Smart routing : IBKR Smart Router (déjà disponible)
```

**Livrables :**
- [ ] `TWAPExecutor` : découpage temporel
- [ ] `VWAPExecutor` : pondération par volume
- [ ] Contrainte participation rate
- [ ] Logs d'exécution avec slippage réel vs estimé

---

## PHASE 4 — SIGNAUX AVANCÉS & ML (Mois 9-14)
**Objectif : Signaux alpha additionnels, combinaison ML**
**Capital requis : ~1000 €/an (APIs données)**

### Étape 4.1 — Earnings Surprise Signal
```
Source : Yahoo Finance / Alpha Vantage (gratuit)
Fichiers : signal_engine/earnings_signal.py (NOUVEAU)
```

**Concept :**
```python
# Post-earnings drift (PEAD) est un des alphas les plus documentés
# Si earnings surprise > 0 → momentum haussier pendant 60 jours
# Intégrer comme signal directionnel dans les pair trades
# Favoriser le côté du pair avec la meilleure surprise
```

### Étape 4.2 — Options Flow Signal
```
Source : IBKR Options chain (inclus)
Fichiers : signal_engine/options_flow.py (NOUVEAU)
```

**Concept :**
```python
# Put/Call ratio du symbole
# Implied Vol skew (put IV - call IV)
# Unusual options activity (volume > 3× moyenne)
# Signal : smart money positioning via options
```

### Étape 4.3 — NLP Sentiment Signal
```
Source : News API (NewsAPI.org ~$50/mois) ou RSS gratuit
Fichiers : signal_engine/sentiment.py (NOUVEAU)
```

**Concept :**
```python
# FinBERT (modèle HuggingFace gratuit) sur titres de news
# Score sentiment [-1, +1] par symbole par jour
# Signal : divergence sentiment vs price → mean-reversion signal
```

### Étape 4.4 — ML Signal Combiner
**Remplacer le `SignalCombiner` equal-weight par un modèle ML.**

```
Fichiers : signal_engine/ml_combiner.py (NOUVEAU)
```

**Implémentation :**
```python
# Modèle : LightGBM / XGBoost
# Features : tous les signaux (z-score, momentum, OU, vol, sentiment...)
# Target : return du trade sur les N prochains jours
# Training : walk-forward (train 2 ans, test 6 mois, roll)
# Anti-overfitting : cross-validation purifiée, feature importance
```

**Livrables :**
- [ ] Pipeline walk-forward ML
- [ ] Feature importance analysis
- [ ] Backtest ML-combined vs equal-weight
- [ ] **Critère** : Sharpe ≥ 2.0, PF ≥ 2.5

---

## PHASE 5 — MULTI-MARCHÉ & SCALING (Mois 14-20)
**Objectif : Diversification géographique, levier contrôlé**
**Capital requis : ~5000 €/an (data feeds multi-marché)**

### Étape 5.1 — Extension Europe (Euronext / LSE)
```
Univers : CAC40, DAX40, FTSE100 composants
Paires : intra-indice + cross (ex: TotalEnergies/Shell)
Broker : IBKR (déjà configuré pour Europe)
```

### Étape 5.2 — Futures Stat-Arb
```
Exemples : ES/NQ spread, CL/BZ spread, ZN/ZB spread
Avantage : pas de short-selling cost, levier naturel
```

### Étape 5.3 — Levier Progressif
```
Phase 0-2 : Levier 1.0× (100K€)
Phase 3   : Levier 1.5× (150K€ d'exposition sur 100K€)
Phase 4   : Levier 2.0× (200K€ d'exposition)
Phase 5   : Levier 2.5-3.0× (si Sharpe > 2.0 confirmé sur 12 mois)

RÈGLE : NE JAMAIS augmenter le levier si Sharpe live < 1.5
```

---

## PHASE 6 — INFRASTRUCTURE PRO (Mois 20-24)
**Objectif : Résilience, monitoring, scalabilité**
**Capital requis : ~2000 €/an (serveur cloud)**

### Étape 6.1 — Colocation Serveur
```
VPS dédié (OVH/Hetzner) : ~50 €/mois
Latence IBKR : <5ms (vs ~50ms depuis domicile)
Uptime 99.9% vs risques PC personnel
```

### Étape 6.2 — Monitoring & Alerting
```
Stack : Prometheus + Grafana (déjà configs dans repo)
Alertes : PnL, positions, drawdown, erreurs d'exécution
Dashboard temps réel : equity curve, risk metrics
```

### Étape 6.3 — Disaster Recovery
```
- Backup quotidien des positions et config
- Procédure de failover documentée
- Circuit-breaker automatique si perte de connexion
- Position reconciliation IBKR vs interne
```

---

## TIMELINE & OBJECTIFS CHIFFRÉS

```
                    Sharpe   Trades/an   DD max   Capital   Levier
                    ──────   ─────────   ──────   ───────   ──────
ACTUEL (v31h)        1.31          8     -1.8%     100K€     1.0×
                      │           │        │         │        │
Phase 0 (M1-2)      ~1.0         8      -2.5%     100K€     1.0×
  Slippage réel       ↓          ─        ↑         ─        ─
  Kelly sizing        ─          ─        ↓↓        ─        ─
                      │           │        │         │        │
Phase 1 (M2-4)      ~1.3        40+     -3.0%     100K€     1.0×
  Multi-signal        ↑          ↑↑       ─         ─        ─
  Univers élargi      ─          ↑        ─         ─        ─
                      │           │        │         │        │
Phase 2 (M4-6)      ~1.5        50+     -2.5%     100K€     1.0×
  Factor-neutral      ↑          ─        ↓         ─        ─
  Risk management     ↑          ─        ↓↓        ─        ─
                      │           │        │         │        │
Phase 3 (M6-9)      ~1.8       200+     -3.0%     100K€     1.5×
  Intraday            ↑          ↑↑↑      ─         ─        ↑
  Algo execution      ↑          ─        ─         ─        ─
                      │           │        │         │        │
Phase 4 (M9-14)     ~2.2       300+     -4.0%     100K€     2.0×
  ML combiner         ↑↑         ↑        ─         ─        ↑
  Signaux avancés     ↑          ↑        ─         ─        ─
                      │           │        │         │        │
Phase 5 (M14-20)    ~2.5       500+     -5.0%    100K€+     2.5×
  Multi-marché        ↑          ↑↑       ─        profit    ↑
  Futures             ↑          ↑        ─         ─        ─
                      │           │        │         │        │
Phase 6 (M20-24)    ~2.5       500+     -5.0%    200K€+     3.0×
  Infra pro           ─          ─        ─        profit    ↑
  Monitoring          ↑          ─        ↓         ─        ─
```

## PnL PROJETÉ (conservateur)

| Phase | Capital | Levier | Gross Exp. | Return/an | PnL/an | PnL cumulé |
|-------|---------|--------|-----------|-----------|--------|------------|
| Actuel | 100K€ | 1.0× | 100K€ | +2.7% | +2 700€ | — |
| Phase 0 | 100K€ | 1.0× | 100K€ | +2.0% | +2 000€ | +2 000€ |
| Phase 1 | 102K€ | 1.0× | 102K€ | +5.0% | +5 100€ | +7 100€ |
| Phase 2 | 107K€ | 1.0× | 107K€ | +7.0% | +7 500€ | +14 600€ |
| Phase 3 | 115K€ | 1.5× | 172K€ | +12.0% | +13 800€ | +28 400€ |
| Phase 4 | 128K€ | 2.0× | 256K€ | +18.0% | +23 000€ | +51 400€ |
| Phase 5 | 151K€ | 2.5× | 378K€ | +22.0% | +33 200€ | +84 600€ |
| Phase 6 | 185K€ | 3.0× | 555K€ | +22.0% | +40 700€ | +125 300€ |

> À 24 mois : **~225K€** sur un départ de 100K€ (hypothèse conservatrice).
> Scénario optimiste (Sharpe 3.0+) : **300-400K€**.

---

## RÈGLES DE GOUVERNANCE

### Go / No-Go par Phase

```
RÈGLE #1 — NE PAS passer à Phase N+1 si Phase N n'est pas validée
RÈGLE #2 — Validation = backtest + 3 mois de paper trading positif
RÈGLE #3 — Jamais augmenter le levier si Sharpe live < 1.5
RÈGLE #4 — Stop total si DD live > 12% → review complète obligatoire
RÈGLE #5 — Chaque nouveau signal doit passer backtest isolé + combiné
```

### Métriques de Monitoring (quotidien)

```
- PnL journalier + cumulé
- Sharpe rolling 60 jours
- Max drawdown rolling
- Beta portfolio vs SPY
- Nombre de trades ouverts
- Slippage réel vs estimé
- VaR 95% portfolio
```

### Budget Annuel

| Poste | Phase 0-2 | Phase 3-4 | Phase 5-6 |
|-------|-----------|-----------|-----------|
| IBKR commissions | ~200€ | ~500€ | ~1500€ |
| IBKR data feed | 0€ (inclus) | ~100€ | ~300€ |
| Serveur/VPS | 0€ | ~300€ | ~600€ |
| APIs données | 0€ | ~500€ | ~1200€ |
| **Total** | **~200€** | **~1400€** | **~3600€** |

---

## QUICK WINS — Actions Immédiates (cette semaine)

1. **[ ] Implémenter `SlippageModel`** dans le simulator
   → Re-backtest v31h → nouveau baseline réaliste
   → Si PF < 1.0 après slippage : STOP, revoir la stratégie

2. **[ ] Implémenter `KellySizer`** (quart-Kelly)
   → Réduire allocation de 50% à ~8-12% par paire
   → Mesurer impact sur DD et Sharpe

3. **[ ] Calendar filter** (earnings + ex-div)
   → Bloquer les trades ±3j des earnings
   → Source : Yahoo Finance API (gratuit)

4. **[ ] Script de test incrémental par symbole**
   → Tester ajout 1-par-1 des meilleurs candidats à l'univers v31h
   →  Objectif : trouver les 5-10 symboles qui AMÉLIORENT le Sharpe

---

## APPENDICE — Stack Technique Cible (Phase 6)

```
Langage       : Python 3.11+ (calculs) + Cython/Rust (hot paths)
Broker        : IBKR Gateway (API TWS)
Data Store    : Parquet (historique) + Redis (temps réel)
Backtest      : EDGECORE Simulator (existant, amélioré)
ML            : LightGBM + scikit-learn (features) + Optuna (HPO)
Monitoring    : Prometheus + Grafana (configs existantes)
Alerting      : Telegram Bot / Email SMTP
Serveur       : VPS Hetzner (AX41, ~40€/mois)
CI/CD         : GitHub Actions (tests auto)
```

---

*Document généré le 7 mars 2026*
*Baseline : EDGECORE v31h — Sharpe 1.31, PF 3.88, Return +8.17%*
*Auteur : EDGECORE Team*

# Résultats du backtest v48 (Anticipatory Exit)

---

**Résumé institutionnel (13 mars 2026)**

- **Backtest terminé** : tous les filtres institutionnels actifs (slippage, Kelly sizing, earnings/dividend blackout, borrow check, stabilité cointegration).
- **Résultats par période** :

| Période | Score (S) | Perf (%) | Win Rate | Trades | Drawdown | Statut |
|---------|-----------|----------|----------|--------|----------|--------|
| P3 2022H2 | 0.00 | +0.00% | 0.0% | 0 | +0.00% | FAIL |
| P4 2023H2 | 1.41 | +2.36% | 100.0% | 2 | -0.55% | PASS |
| P5 2024H2 | 0.00 | +0.00% | 0.0% | 0 | +0.00% | FAIL |

- **Synthèse** : PASS=1/5, FAIL=4/5, moyenne=0.10, min=-0.90 → **FAIL**

---

**Comparaison exit_z (progression v46 vs v48)**

| Période | v46 exit_z=0.2 | v48 exit_z=0.5 |
|---------|----------------|---------------|
| P1 | -1.67 | +0.00 (+1.67) |
| P2 | +2.27 | -0.90 (-3.17) |
| P3 | +2.24 | +0.00 (-2.24) |
| P4 | +0.46 | +1.41 (+0.95) |
| P5 | -1.14 | +0.00 (+1.14) |

- **Diagnostic** :
  - P1/P4 : amélioration avec exit_z=0.5
  - P2/P3 : régression, exit_z=0.5 trop élevé (profit non capturé)
  - P5 : amélioration

---

**Décision institutionnelle** :
- Si P4 amélioré mais P1 toujours FAIL : tester exit adaptatif (0.5 bull, 0.2 bear)
- Si P2/P3 régressent : exit_z trop haut → essayer 0.35
- Si P4 inchangé : timing exit non cause → tester entry threshold 1.3

---

**Prochaines étapes** :
- Tester exit_z=0.35 pour valider capture profit sur P2/P3
- Tester exit adaptatif selon régime
- Si échec, ajuster entry threshold

---
