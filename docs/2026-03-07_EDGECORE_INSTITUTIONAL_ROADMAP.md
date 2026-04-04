# EDGECORE ÔÇö Roadmap Institutional-Grade

**De v31h ÔåÆ Syst├¿me Stat-Arb Institutionnel**
**Capital de d├®part : 100 000 Ôé¼**
**Date : 7 mars 2026**

## Situation Actuelle ÔÇö v31h (Baseline)

Trades:        24 / 3 ans  Univers:   37 sym     Levier:    1├ù
Signaux:       2 (coint├® + momentum)
## Cible Institutionnelle

Trades:        500+/an     Univers:   200+ sym    Levier:    2-4├ù
Signaux:       10+         Factor-neutral: Oui
## GAP ANALYSIS ÔÇö Priorit├® par Impact

| # | Gap | Impact PnL | Effort | Priorit├® |
|---|-----|-----------|--------|----------|
| 1 | Mod├¿le de slippage absent | -30 ├á -50% du PnL r├®el | Moyen | **CRITIQUE** |
| 2 | Position sizing na├»f (50%/paire) | Risque de ruine | Moyen | **CRITIQUE** |
| 3 | Trop peu de trades (8/an) | Sharpe instable | ├ëlev├® | **HAUTE** |
| 4 | Pas de factor-neutralit├® | Prise de beta camoufl├®e | Moyen | **HAUTE** |
| 5 | Signaux alpha limit├®s (2) | Alpha fragile, single point of failure | ├ëlev├® | **HAUTE** |
| 6 | Pas d'intraday | Latence de signal | ├ëlev├® | MOYENNE |
| 7 | Pas de multi-march├® | Diversification limit├®e | ├ëlev├® | MOYENNE |
| 8 | Ex├®cution manuelle/basique | Market impact non contr├┤l├® | Moyen | MOYENNE |
| 9 | Infrastructure non scalable | Limite de croissance | ├ëlev├® | BASSE (pour l'instant) |
| 10 | Donn├®es alternatives absentes | Alpha additionnel | ├ëlev├® | BASSE (capital requis) |

---

## PHASE 0 ÔÇö FONDATIONS CRITIQUES (Mois 1-2)
**Objectif : Rendre v31h r├®aliste et deployable en live**
**Capital requis : 0 Ôé¼ (code uniquement)**

### ├ëtape 0.1 ÔÇö Mod├¿le de Slippage R├®aliste
**Priorit├® : BLOQUANTE ÔÇö sans ├ºa, tous les r├®sultats sont optimistes**
Fichiers : execution/slippage.py (NOUVEAU)
           backtests/strategy_simulator.py (MODIFIER)
```

**Mod├¿le ├á impl├®menter :**
```python
# Mod├¿le de slippage ├á 3 composantes

# 1. SPREAD fixe (bid-ask)
spread_cost_bps = 2.0  # ~2 bps pour mega-caps US

# 2. MARKET IMPACT (Almgren-Chriss simplifi├®)
# impact = ╬À ├ù ¤â_daily ├ù ÔêÜ(Q / ADV)
# ╬À = constante d'impact (~0.1 pour mega-caps)
# Q = quantit├® trad├®e, ADV = volume quotidien moyen

# 3. TIMING COST
# Delay cost = ¤â ├ù ÔêÜ(T_execution / 252)
# T_execution = temps d'ex├®cution en jours
```

**Livrables :**
- [x] `SlippageModel` class avec 3 composantes  
- [x] Intégration dans `strategy_simulator.py` (chaque entry/exit)  
- [ ] Chargement ADV (Average Daily Volume) depuis IBKR  
- [x] Re-backtest v31h avec slippage → nouveau baseline réaliste  
- [ ] **Critère de validation** : v31h + slippage doit rester PF > 1.5

### ├ëtape 0.2 ÔÇö Position Sizing Kelly/Risque
**50% du capital par paire = risque de ruine. Inacceptable.**

```
Impact : R├®duction du DD de -50%, stabilisation du Sharpe
Fichiers : risk/kelly_sizing.py (NOUVEAU)
           backtests/strategy_simulator.py (MODIFIER sizing)
```

**Impl├®mentation :**
```python
# Kelly Criterion fractionnel
# f* = (p ├ù b - q) / b   o├╣ p=win_rate, b=avg_win/avg_loss, q=1-p
# Position = f* ├ù fraction_kelly ├ù capital
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

### ├ëtape 0.3 ÔÇö Earnings & Dividende Filter
**Les firmes ne tradent JAMAIS autour des earnings.**

```
Impact : ├ëvite 2-3 trades catastrophiques par an
Fichiers : data/event_filter.py (NOUVEAU)
           strategies/pair_trading.py (MODIFIER)
```

**Livrables :**
- [ ] Calendrier earnings via API (Yahoo Finance gratuit)  
- [ ] Blackout ±3 jours autour de la date de reporting  
- [ ] Filtre ex-dividende (spread pollué J-1/J+1)  
- [ ] Intégration dans `generate_signals()` comme gate  
- [ ] Re-backtest pour mesurer impact

### ├ëtape 0.4 ÔÇö Short Borrow Availability Check
**Sans locate, le short leg du pair trade ├®choue en live.**

```
Impact : Pr├®vient les ├®checs d'ex├®cution + costs de borrow impr├®vus
Fichiers : execution/borrow_check.py (NOUVEAU)
           execution/ibkr_execution.py (MODIFIER)
```

**Impl├®mentation :**
```python
# V├®rifier AVANT d'envoyer l'ordre :
#   1. Shortable? ÔåÆ IBKR reqContractDetails().shortableShares
#   2. Borrow fee? ÔåÆ Si fee > 3% annualis├®, REJETER le trade
#   3. Availability? ÔåÆ Si shortableShares < quantit├® requise, REJETER
#
# Pour le backtest :
#   Les 37 mega-caps de v31h sont quasi-toujours shortable (HTB < 1%)
#   Mais lors de l'expansion univers (Phase 1.5), certains mid-caps
#   peuvent ├¬tre Hard-To-Borrow ÔåÆ filtre essentiel
```

**Livrables :**
- [ ] `BorrowChecker` : query IBKR shortable shares + fee rate  
- [ ] Gate dans l'exécution : rejeter si non-shortable ou fee > 3%  
- [ ] Logging : tracker les rejets pour identifier les symboles problématiques  
- [ ] Intégration backtest : flag HTB historique (approximation via market cap)

---

## PHASE 1 ÔÇö AUGMENTATION DES SIGNAUX (Mois 2-4)
**Objectif : Passer de 2 signaux ├á 6-8, augmenter les trades ├á 50+/an**
**Capital requis : 0 Ôé¼ (donn├®es gratuites)**

### ├ëtape 1.1 ÔÇö Ornstein-Uhlenbeck Signal
**Le spread z-score actuel est statique. OU mod├®lise la vitesse de reversion.**

```
Alpha additionnel estim├® : +20-30% de trades qualifi├®s
Fichiers : signal_engine/ou_signal.py (NOUVEAU)
```

**Concept :**
```python
# Au lieu de simplement z = (spread - mean) / std,
# mod├®liser le processus OU : dX = ╬©(╬╝ - X)dt + ¤âdW
# ╬© = vitesse de mean-reversion (li├® ├á half-life)
# Signal = ╬© ├ù (╬╝ - X) / ¤â  ÔåÆ "expected profit velocity"
# Entrer quand la vitesse de reversion est HAUTE, pas juste z > seuil
```

**Livrables :**
- [ ] `OUSignalGenerator` : estimation ╬©, ╬╝, ¤â par fen├¬tre glissante
- [ ] Signal : expected reversion velocity
- [ ] Int├®gration dans `SignalCombiner` (d├®j├á cr├®├® mais non wired)
- [ ] Backtest comparatif : OU seul vs z-score seul vs combin├®

### ├ëtape 1.2 ÔÇö Cross-Sectional Momentum Signal
**Le momentum overlay actuel est time-series. Ajouter cross-sectional.**

```
Alpha additionnel estim├® : +15-25% de Sharpe
Fichiers : signal_engine/cross_sectional.py (NOUVEAU)
```

**Concept :**
```python
# Ranker tous les symboles par return sur [1M, 3M, 6M, 12M]
# Pour un pair trade A/B :
#   Si rank(A) >> rank(B) ÔåÆ signal short le spread (A surperformera)
#   Si rank(A) << rank(B) ÔåÆ signal long le spread (B rattrapera)
# Combin├® avec cointegration : entr├®e quand BOTH confirment
```

**Livrables :**
- [ ] `CrossSectionalMomentum` : ranking par fen├¬tre
- [ ] Signal de confirmation crois├®e avec z-score
- [ ] Int├®gration dans `SignalCombiner`
- [ ] Backtest A/B

### ├ëtape 1.3 ÔÇö Volatilit├® Relative Signal
**Entrer quand la vol du spread est BASSE = faible risque, sortir quand haute.**

```
Fichiers : signal_engine/vol_signal.py (NOUVEAU)
```

**Concept :**
```python
# spread_vol = rolling_std(spread_returns, window=20)
# vol_ratio = spread_vol / spread_vol.rolling(60).mean()
# Entrer seulement quand vol_ratio < 0.8 (vol compress├®e)
# Sortir si vol_ratio > 1.5 (explosion de vol = r├®gime cass├®)
```

**Livrables :**
- [ ] `VolatilityRegimeSignal` class
- [ ] Gate d'entr├®e : vol_ratio < seuil
- [ ] Gate de sortie : vol explosion
- [ ] Backtest comparatif

### ├ëtape 1.4 ÔÇö Wiring du SignalCombiner
**Le `SignalCombiner` existe d├®j├á mais n'est wired nulle part.**

```
Fichiers : signal_engine/combiner.py (EXISTE)
           strategies/pair_trading.py (MODIFIER)
           backtests/strategy_simulator.py (MODIFIER)
```

**Livrables :**
- [ ] Int├®grer `SignalCombiner` dans le pipeline backtest
- [ ] Pond├®ration initiale : equal-weight entre signaux
- [ ] Seuil combin├® : entrer quand ÔëÑ 3/5 signaux confirment
- [ ] Backtest multi-signal vs v31h baseline
- [ ] **Crit├¿re** : Plus de trades (40+) avec PF ÔëÑ 2.0

### ├ëtape 1.5 ÔÇö Expansion Univers Intelligente (par Secteur)
**L'expansion brute a ├®chou├® (v31d-j). Strat├®gie : ajouter 1 secteur ├á la fois.**

```
Insight crucial de v31 : chaque ajout de symbole doit ├¬tre PROUV├ë
par backtest isol├® avant int├®gration.
```

**M├®thode :**
```
Pour chaque candidat (ex: COST, INTC, BLK, LMT...) :
  1. Ajouter UN SEUL symbole ├á l'univers v31h
  2. Backtest ÔåÆ mesurer delta Sharpe et delta PF
  3. Si delta Sharpe > 0 ET delta PF > 0 ÔåÆ GARDER
  4. Sinon ÔåÆ REJETER
  5. Apr├¿s validation, ajouter le suivant

Ordre de test (par qualit├® attendue) :
  Tech:   INTC, QCOM, TXN (semis solides)
  Fin:    BLK (mega cap)
  Energy: SLB, VLO (haute liquidit├®)
  Indust: LMT (d├®fense, d├®corr├®l├®)
  Health: LLY, TMO (mega pharma)
  ETFs:   XLK, XLF, XLE (excellent pour pairing)
```

**Livrables :**
- [ ] Script de test incr├®mental automatis├®
- [ ] Tableau symbole-par-symbole : delta Sharpe, delta PF
- [ ] Univers valid├® "v32" : v31h + symboles prouv├®s
- [ ] **Crit├¿re** : Univers 40-55 sym, Sharpe ÔëÑ 1.2, Trades ÔëÑ 40/an

---

## PHASE 2 ÔÇö RISK MANAGEMENT INSTITUTIONNEL (Mois 4-6)
**Objectif : Factor-neutralit├®, contr├┤le du risque portfolio**
**Capital requis : 0 Ôé¼ (calculs internes)**

### ├ëtape 2.1 ÔÇö Beta-Neutralit├® Portfolio
```
Fichiers : risk/factor_model.py (NOUVEAU)
           risk/portfolio_optimizer.py (NOUVEAU)
```

**Impl├®mentation :**
```python
# Pour chaque position :
#   beta_A = cov(R_A, R_SPY) / var(R_SPY)  rolling 60 jours
#   beta_B = cov(R_B, R_SPY) / var(R_SPY)
#   Ajuster les poids du pair trade pour que beta_net Ôëê 0
#   Si pair = long A, short B :
#     w_A = 1.0, w_B = -(beta_A / beta_B)  ÔåÆ beta neutral
#
# Au niveau portfolio :
#   sum(beta_i ├ù notional_i) / total_notional < 0.05
```

**Livrables :**
- [ ] Estimation beta rolling par symbole
- [ ] Ajustement des hedge ratios pour beta-neutralit├®
- [ ] Contrainte portfolio : |beta_net| < 0.05
- [ ] Monitoring du beta en temps r├®el (live trading)

### ├ëtape 2.2 ÔÇö Sector-Neutralit├® + Corr├®lation Inter-Positions
```
Fichiers : risk/sector_limits.py (NOUVEAU)
           risk/position_correlation.py (NOUVEAU)
```

**Corr├®lation inter-positions ÔÇö VITAL :**
```python
# Si pair_trade_A et pair_trade_B sont corr├®l├®s > 0.30,
# un seul ├®v├®nement (ex: choc tech) wipe les deux simultan├®ment.
# Avec sizing concentr├®, c'est catastrophique.
#
# Impl├®mentation :
#   corr_matrix = rolling_corr(spread_returns, window=60)
#   Pour chaque nouveau trade :
#     Si corr(nouveau_spread, spread_ouvert) > 0.30 ÔåÆ REJETER
#     ou r├®duire le sizing proportionnellement
#
# max_pair_correlation = 0.30  # entre les POSITIONS (retours des spreads)
# max_correlated_exposure = 15% du NAV  # ensemble corr├®l├®
```

**Livrables :**
- [ ] `PositionCorrelationMonitor` : matrice de corr├®lation rolling des spreads
- [ ] Gate d'entr├®e : rejeter si corr > 0.30 avec position existante
- [ ] Contrainte : max 25% du NAV par secteur
- [ ] Rebalancement automatique si d├®passement
- [ ] Dashboard sector exposure + correlation heatmap

### ├ëtape 2.3 ÔÇö Portfolio VaR / CVaR Limits
```
Fichiers : risk/var_monitor.py (NOUVEAU)
```

**Livrables :**
- [ ] VaR 95% historique rolling 60j
- [ ] CVaR 95% (Expected Shortfall)
- [ ] Circuit-breaker : stop trading si VaR > 2% du NAV
- [ ] Rapport quotidien de risque

### ├ëtape 2.4 ÔÇö Drawdown Management Multi-Niveaux
```
TIER 1 (DD > 3%)  : R├®duire sizing de 50%
TIER 2 (DD > 5%)  : Fermer 50% des positions
TIER 3 (DD > 8%)  : Fermer TOUTES les positions, cooldown 10 jours
TIER 4 (DD > 12%) : Arr├¬t complet, review manuelle obligatoire
```

**Livrables :**
- [ ] `DrawdownManager` multi-tier
- [ ] Int├®gration backtest + live
- [ ] Alertes email/SMS ├á chaque tier

---

## PHASE 3 ÔÇö FR├ëQUENCE & EX├ëCUTION (Mois 6-9)
**Objectif : Passer de daily ├á intraday, ex├®cution algorithmique**
**Capital requis : ~500 Ôé¼/an (donn├®es intraday + serveur)**

### ├ëtape 3.1 ÔÇö Donn├®es Intraday (5min bars)
```
Source : IBKR Historical Data (inclus dans l'abonnement)
Stockage : SQLite ou Parquet local
Fichiers : data/intraday_loader.py (NOUVEAU)
```

**Livrables :**
- [ ] Collecteur de donn├®es 5min depuis IBKR
- [ ] Stockage Parquet partitionn├® par date/symbole
- [ ] Adaptation du backtest simulator pour barres 5min
- [ ] Validation : v31h sur 5min bars vs daily

### ├ëtape 3.2 ÔÇö Signaux Intraday
```
Fichiers : signal_engine/intraday_signals.py (NOUVEAU)
```

**Nouveaux signaux possibles en intraday :**
```python
# 1. Mean-reversion intraday du spread
#    ÔåÆ z-score recalcul├® toutes les 5min
#    ÔåÆ entry/exit plus fr├®quents

# 2. Opening gap reversion
#    ÔåÆ Si le spread gap ├á l'open, mean-revert dans les 2h

# 3. Volume profile signal
#    ÔåÆ Entrer quand le volume confirme la direction du spread
```

**Livrables :**
- [ ] Adaptation du z-score pour fen├¬tres intraday
- [ ] Signal gap-reversion
- [ ] Backtest intraday
- [ ] **Crit├¿re** : Trades ÔëÑ 200/an, Sharpe ÔëÑ 1.5

### ├ëtape 3.3 ÔÇö Ex├®cution Algorithmique (TWAP/VWAP)
```
Fichiers : execution/algo_executor.py (NOUVEAU)
           execution/ibkr_algo.py (NOUVEAU)
```

**Impl├®mentation :**
```python
# TWAP : d├®couper l'ordre en N tranches sur T minutes
# VWAP : pond├®rer les tranches par le profil de volume historique
# Participation rate : max 5% du volume quotidien
# Smart routing : IBKR Smart Router (d├®j├á disponible)
```

**Livrables :**
- [ ] `TWAPExecutor` : d├®coupage temporel
- [ ] `VWAPExecutor` : pond├®ration par volume
- [ ] Contrainte participation rate
- [ ] Logs d'ex├®cution avec slippage r├®el vs estim├®

---

## PHASE 4 ÔÇö SIGNAUX AVANC├ëS & ML (Mois 9-14)
**Objectif : Signaux alpha additionnels, combinaison ML**
**Capital requis : ~1000 Ôé¼/an (APIs donn├®es)**

### ├ëtape 4.1 ÔÇö Earnings Surprise Signal
```
Source : Yahoo Finance / Alpha Vantage (gratuit)
Fichiers : signal_engine/earnings_signal.py (NOUVEAU)
```

**Concept :**
```python
# Post-earnings drift (PEAD) est un des alphas les plus document├®s
# Si earnings surprise > 0 ÔåÆ momentum haussier pendant 60 jours
# Int├®grer comme signal directionnel dans les pair trades
# Favoriser le c├┤t├® du pair avec la meilleure surprise
```

### ├ëtape 4.2 ÔÇö Options Flow Signal
```
Source : IBKR Options chain (inclus)
Fichiers : signal_engine/options_flow.py (NOUVEAU)
```

**Concept :**
```python
# Put/Call ratio du symbole
# Implied Vol skew (put IV - call IV)
# Unusual options activity (volume > 3├ù moyenne)
# Signal : smart money positioning via options
```

### ├ëtape 4.3 ÔÇö NLP Sentiment Signal
```
Source : News API (NewsAPI.org ~$50/mois) ou RSS gratuit
Fichiers : signal_engine/sentiment.py (NOUVEAU)
```

**Concept :**
```python
# FinBERT (mod├¿le HuggingFace gratuit) sur titres de news
# Score sentiment [-1, +1] par symbole par jour
# Signal : divergence sentiment vs price ÔåÆ mean-reversion signal
```

### ├ëtape 4.4 ÔÇö ML Signal Combiner
**Remplacer le `SignalCombiner` equal-weight par un mod├¿le ML.**

```
Fichiers : signal_engine/ml_combiner.py (NOUVEAU)
```

**Impl├®mentation :**
```python
# Mod├¿le : LightGBM / XGBoost
# Features : tous les signaux (z-score, momentum, OU, vol, sentiment...)
# Target : return du trade sur les N prochains jours
# Training : walk-forward (train 2 ans, test 6 mois, roll)
# Anti-overfitting : cross-validation purifi├®e, feature importance
```

**Livrables :**
- [ ] Pipeline walk-forward ML
- [ ] Feature importance analysis
- [ ] Backtest ML-combined vs equal-weight
- [ ] **Crit├¿re** : Sharpe ÔëÑ 2.0, PF ÔëÑ 2.5

---

## PHASE 5 ÔÇö MULTI-MARCH├ë & SCALING (Mois 14-20)
**Objectif : Diversification g├®ographique, levier contr├┤l├®**
**Capital requis : ~5000 Ôé¼/an (data feeds multi-march├®)**

### ├ëtape 5.1 ÔÇö Extension Europe (Euronext / LSE)
```
Univers : CAC40, DAX40, FTSE100 composants
Paires : intra-indice + cross (ex: TotalEnergies/Shell)
Broker : IBKR (d├®j├á configur├® pour Europe)
```

### ├ëtape 5.2 ÔÇö Futures Stat-Arb
```
Exemples : ES/NQ spread, CL/BZ spread, ZN/ZB spread
Avantage : pas de short-selling cost, levier naturel
```

### ├ëtape 5.3 ÔÇö Levier Progressif
```
Phase 0-2 : Levier 1.0├ù (100KÔé¼)
Phase 3   : Levier 1.5├ù (150KÔé¼ d'exposition sur 100KÔé¼)
Phase 4   : Levier 2.0├ù (200KÔé¼ d'exposition)
Phase 5   : Levier 2.5-3.0├ù (si Sharpe > 2.0 confirm├® sur 12 mois)

R├êGLE : NE JAMAIS augmenter le levier si Sharpe live < 1.5
```

---

## PHASE 6 ÔÇö INFRASTRUCTURE PRO (Mois 20-24)
**Objectif : R├®silience, monitoring, scalabilit├®**
**Capital requis : ~2000 Ôé¼/an (serveur cloud)**

### ├ëtape 6.1 ÔÇö Colocation Serveur
```
VPS d├®di├® (OVH/Hetzner) : ~50 Ôé¼/mois
Latence IBKR : <5ms (vs ~50ms depuis domicile)
Uptime 99.9% vs risques PC personnel
```

### ├ëtape 6.2 ÔÇö Monitoring & Alerting
```
Stack : Prometheus + Grafana (d├®j├á configs dans repo)
Alertes : PnL, positions, drawdown, erreurs d'ex├®cution
Dashboard temps r├®el : equity curve, risk metrics
```

### ├ëtape 6.3 ÔÇö Disaster Recovery
```
- Backup quotidien des positions et config
- Proc├®dure de failover document├®e
- Circuit-breaker automatique si perte de connexion
- Position reconciliation IBKR vs interne
```

---

## TIMELINE & OBJECTIFS CHIFFR├ëS

```
                    Sharpe   Trades/an   DD max   Capital   Levier
                    ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ   ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ   ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ   ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ   ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
ACTUEL (v31h)        1.31          8     -1.8%     100KÔé¼     1.0├ù
                      Ôöé           Ôöé        Ôöé         Ôöé        Ôöé
Phase 0 (M1-2)      ~1.0         8      -2.5%     100KÔé¼     1.0├ù
  Slippage r├®el       Ôåô          ÔöÇ        Ôåæ         ÔöÇ        ÔöÇ
  Kelly sizing        ÔöÇ          ÔöÇ        ÔåôÔåô        ÔöÇ        ÔöÇ
                      Ôöé           Ôöé        Ôöé         Ôöé        Ôöé
Phase 1 (M2-4)      ~1.3        40+     -3.0%     100KÔé¼     1.0├ù
  Multi-signal        Ôåæ          ÔåæÔåæ       ÔöÇ         ÔöÇ        ÔöÇ
  Univers ├®largi      ÔöÇ          Ôåæ        ÔöÇ         ÔöÇ        ÔöÇ
                      Ôöé           Ôöé        Ôöé         Ôöé        Ôöé
Phase 2 (M4-6)      ~1.5        50+     -2.5%     100KÔé¼     1.0├ù
  Factor-neutral      Ôåæ          ÔöÇ        Ôåô         ÔöÇ        ÔöÇ
  Risk management     Ôåæ          ÔöÇ        ÔåôÔåô        ÔöÇ        ÔöÇ
                      Ôöé           Ôöé        Ôöé         Ôöé        Ôöé
Phase 3 (M6-9)      ~1.8       200+     -3.0%     100KÔé¼     1.5├ù
  Intraday            Ôåæ          ÔåæÔåæÔåæ      ÔöÇ         ÔöÇ        Ôåæ
  Algo execution      Ôåæ          ÔöÇ        ÔöÇ         ÔöÇ        ÔöÇ
                      Ôöé           Ôöé        Ôöé         Ôöé        Ôöé
Phase 4 (M9-14)     ~2.2       300+     -4.0%     100KÔé¼     2.0├ù
  ML combiner         ÔåæÔåæ         Ôåæ        ÔöÇ         ÔöÇ        Ôåæ
  Signaux avanc├®s     Ôåæ          Ôåæ        ÔöÇ         ÔöÇ        ÔöÇ
                      Ôöé           Ôöé        Ôöé         Ôöé        Ôöé
Phase 5 (M14-20)    ~2.5       500+     -5.0%    100KÔé¼+     2.5├ù
  Multi-march├®        Ôåæ          ÔåæÔåæ       ÔöÇ        profit    Ôåæ
  Futures             Ôåæ          Ôåæ        ÔöÇ         ÔöÇ        ÔöÇ
                      Ôöé           Ôöé        Ôöé         Ôöé        Ôöé
Phase 6 (M20-24)    ~2.5       500+     -5.0%    200KÔé¼+     3.0├ù
  Infra pro           ÔöÇ          ÔöÇ        ÔöÇ        profit    Ôåæ
  Monitoring          Ôåæ          ÔöÇ        Ôåô         ÔöÇ        ÔöÇ
```

## PnL PROJET├ë (conservateur)

| Phase | Capital | Levier | Gross Exp. | Return/an | PnL/an | PnL cumul├® |
|-------|---------|--------|-----------|-----------|--------|------------|
| Actuel | 100KÔé¼ | 1.0├ù | 100KÔé¼ | +2.7% | +2 700Ôé¼ | ÔÇö |
| Phase 0 | 100KÔé¼ | 1.0├ù | 100KÔé¼ | +2.0% | +2 000Ôé¼ | +2 000Ôé¼ |
| Phase 1 | 102KÔé¼ | 1.0├ù | 102KÔé¼ | +5.0% | +5 100Ôé¼ | +7 100Ôé¼ |
| Phase 2 | 107KÔé¼ | 1.0├ù | 107KÔé¼ | +7.0% | +7 500Ôé¼ | +14 600Ôé¼ |
| Phase 3 | 115KÔé¼ | 1.5├ù | 172KÔé¼ | +12.0% | +13 800Ôé¼ | +28 400Ôé¼ |
| Phase 4 | 128KÔé¼ | 2.0├ù | 256KÔé¼ | +18.0% | +23 000Ôé¼ | +51 400Ôé¼ |
| Phase 5 | 151KÔé¼ | 2.5├ù | 378KÔé¼ | +22.0% | +33 200Ôé¼ | +84 600Ôé¼ |
| Phase 6 | 185KÔé¼ | 3.0├ù | 555KÔé¼ | +22.0% | +40 700Ôé¼ | +125 300Ôé¼ |

> ├Ç 24 mois : **~225KÔé¼** sur un d├®part de 100KÔé¼ (hypoth├¿se conservatrice).
> Sc├®nario optimiste (Sharpe 3.0+) : **300-400KÔé¼**.

---

## R├êGLES DE GOUVERNANCE

### Go / No-Go par Phase

```
R├êGLE #1 ÔÇö NE PAS passer ├á Phase N+1 si Phase N n'est pas valid├®e
R├êGLE #2 ÔÇö Validation = backtest + 3 mois de paper trading positif
R├êGLE #3 ÔÇö Jamais augmenter le levier si Sharpe live < 1.5
R├êGLE #4 ÔÇö Stop total si DD live > 12% ÔåÆ review compl├¿te obligatoire
R├êGLE #5 ÔÇö Chaque nouveau signal doit passer backtest isol├® + combin├®
```

### M├®triques de Monitoring (quotidien)

```
- PnL journalier + cumul├®
- Sharpe rolling 60 jours
- Max drawdown rolling
- Beta portfolio vs SPY
- Nombre de trades ouverts
- Slippage r├®el vs estim├®
- VaR 95% portfolio
```

### Budget Annuel

| Poste | Phase 0-2 | Phase 3-4 | Phase 5-6 |
|-------|-----------|-----------|-----------|
| IBKR commissions | ~200Ôé¼ | ~500Ôé¼ | ~1500Ôé¼ |
| IBKR data feed | 0Ôé¼ (inclus) | ~100Ôé¼ | ~300Ôé¼ |
| Serveur/VPS | 0Ôé¼ | ~300Ôé¼ | ~600Ôé¼ |
| APIs donn├®es | 0Ôé¼ | ~500Ôé¼ | ~1200Ôé¼ |
| **Total** | **~200Ôé¼** | **~1400Ôé¼** | **~3600Ôé¼** |

---

## QUICK WINS ÔÇö Actions Imm├®diates (cette semaine)

1. **[ ] Impl├®menter `SlippageModel`** dans le simulator
   ÔåÆ Re-backtest v31h ÔåÆ nouveau baseline r├®aliste
   ÔåÆ Si PF < 1.0 apr├¿s slippage : STOP, revoir la strat├®gie

2. **[ ] Impl├®menter `KellySizer`** (quart-Kelly)
   ÔåÆ R├®duire allocation de 50% ├á ~8-12% par paire
   ÔåÆ Mesurer impact sur DD et Sharpe

3. **[ ] Calendar filter** (earnings + ex-div)
   ÔåÆ Bloquer les trades ┬▒3j des earnings
   ÔåÆ Source : Yahoo Finance API (gratuit)

4. **[ ] Script de test incr├®mental par symbole**
   ÔåÆ Tester ajout 1-par-1 des meilleurs candidats ├á l'univers v31h
   ÔåÆ  Objectif : trouver les 5-10 symboles qui AM├ëLIORENT le Sharpe

---

## APPENDICE ÔÇö Stack Technique Cible (Phase 6)

```
Langage       : Python 3.11+ (calculs) + Cython/Rust (hot paths)
Broker        : IBKR Gateway (API TWS)
Data Store    : Parquet (historique) + Redis (temps r├®el)
Backtest      : EDGECORE Simulator (existant, am├®lior├®)
ML            : LightGBM + scikit-learn (features) + Optuna (HPO)
Monitoring    : Prometheus + Grafana (configs existantes)
Alerting      : Telegram Bot / Email SMTP
Serveur       : VPS Hetzner (AX41, ~40Ôé¼/mois)
CI/CD         : GitHub Actions (tests auto)
```

---

*Document g├®n├®r├® le 7 mars 2026*
*Baseline : EDGECORE v31h ÔÇö Sharpe 1.31, PF 3.88, Return +8.17%*
*Auteur : EDGECORE Team*

# R├®sultats du backtest v48 (Anticipatory Exit)

---

**R├®sum├® institutionnel (13 mars 2026)**

- **Backtest termin├®** : tous les filtres institutionnels actifs (slippage, Kelly sizing, earnings/dividend blackout, borrow check, stabilit├® cointegration).
- **R├®sultats par p├®riode** :

| P├®riode | Score (S) | Perf (%) | Win Rate | Trades | Drawdown | Statut |
|---------|-----------|----------|----------|--------|----------|--------|
| P3 2022H2 | 0.00 | +0.00% | 0.0% | 0 | +0.00% | FAIL |
| P4 2023H2 | 1.41 | +2.36% | 100.0% | 2 | -0.55% | PASS |
| P5 2024H2 | 0.00 | +0.00% | 0.0% | 0 | +0.00% | FAIL |

- **Synth├¿se** : PASS=1/5, FAIL=4/5, moyenne=0.10, min=-0.90 ÔåÆ **FAIL**

---

**Comparaison exit_z (progression v46 vs v48)**

| P├®riode | v46 exit_z=0.2 | v48 exit_z=0.5 |
|---------|----------------|---------------|
| P1 | -1.67 | +0.00 (+1.67) |
| P2 | +2.27 | -0.90 (-3.17) |
| P3 | +2.24 | +0.00 (-2.24) |
| P4 | +0.46 | +1.41 (+0.95) |
| P5 | -1.14 | +0.00 (+1.14) |

- **Diagnostic** :
  - P1/P4 : am├®lioration avec exit_z=0.5
  - P2/P3 : r├®gression, exit_z=0.5 trop ├®lev├® (profit non captur├®)
  - P5 : am├®lioration

---

**D├®cision institutionnelle** :
- Si P4 am├®lior├® mais P1 toujours FAIL : tester exit adaptatif (0.5 bull, 0.2 bear)
- Si P2/P3 r├®gressent : exit_z trop haut ÔåÆ essayer 0.35
- Si P4 inchang├® : timing exit non cause ÔåÆ tester entry threshold 1.3

---

**Prochaines ├®tapes** :
- Tester exit_z=0.35 pour valider capture profit sur P2/P3
- Tester exit adaptatif selon r├®gime
- Si ├®chec, ajuster entry threshold

---
