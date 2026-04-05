<<<<<<< HEAD
﻿# EDGECORE ÔÇö Roadmap Institutional-Grade

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
=======
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
>>>>>>> origin/main
Fichiers : execution/slippage.py (NOUVEAU)
           backtests/strategy_simulator.py (MODIFIER)
```

<<<<<<< HEAD
**Mod├¿le ├á impl├®menter :**
```python
# Mod├¿le de slippage ├á 3 composantes
=======
**Modèle à implémenter :**
```python
# Modèle de slippage à 3 composantes
>>>>>>> origin/main

# 1. SPREAD fixe (bid-ask)
spread_cost_bps = 2.0  # ~2 bps pour mega-caps US

<<<<<<< HEAD
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
=======
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
>>>>>>> origin/main
Fichiers : risk/kelly_sizing.py (NOUVEAU)
           backtests/strategy_simulator.py (MODIFIER sizing)
```

<<<<<<< HEAD
**Impl├®mentation :**
```python
# Kelly Criterion fractionnel
# f* = (p ├ù b - q) / b   o├╣ p=win_rate, b=avg_win/avg_loss, q=1-p
# Position = f* ├ù fraction_kelly ├ù capital
=======
**Implémentation :**
```python
# Kelly Criterion fractionnel
# f* = (p × b - q) / b   où p=win_rate, b=avg_win/avg_loss, q=1-p
# Position = f* × fraction_kelly × capital
>>>>>>> origin/main
# fraction_kelly = 0.25 (quart-Kelly = standard institutionnel)

# Avec plafonds :
max_position_pct = 10.0      # Max 10% par paire (vs 50% actuel!)
max_sector_pct = 25.0        # Max 25% par secteur
max_gross_leverage = 2.0     # Levier brut max 200% (Phase 0)
```

**Livrables :**
<<<<<<< HEAD
- [ ] `KellySizer` class avec Kelly fractionnel  
- [ ] Plafonds par position, par secteur, levier brut  
=======
- [ ] `KellySizer` class avec Kelly fractionnel
- [ ] Plafonds par position, par secteur, levier brut
>>>>>>> origin/main
- [ ] **Stop-loss par trade en % du NAV total** (pas du notionnel) :
  ```
  max_loss_per_trade_nav = 0.75%   # du NAV total
  # Exemple : NAV = 100K€, max perte par trade = 750€
  # Actuel : stop 7% × 50% alloc = 3.5% du NAV = 3 500€ → trop élevé
  # Avec Kelly 10% alloc : stop 7% × 10% = 0.7% du NAV ✓
  # Le plafond NAV garantit la limite même si le sizing change
  ```
<<<<<<< HEAD
- [ ] Intégration dans le simulator  
- [ ] Re-backtest v31h avec Kelly sizing → comparer  
- [ ] **Critère** : DD < 5%, Sharpe stable ou amélioré

### ├ëtape 0.3 ÔÇö Earnings & Dividende Filter
**Les firmes ne tradent JAMAIS autour des earnings.**

```
Impact : ├ëvite 2-3 trades catastrophiques par an
=======
- [ ] Intégration dans le simulator
- [ ] Re-backtest v31h avec Kelly sizing → comparer
- [ ] **Critère** : DD < 5%, Sharpe stable ou amélioré

### Étape 0.3 — Earnings & Dividende Filter
**Les firmes ne tradent JAMAIS autour des earnings.**

```
Impact : Évite 2-3 trades catastrophiques par an
>>>>>>> origin/main
Fichiers : data/event_filter.py (NOUVEAU)
           strategies/pair_trading.py (MODIFIER)
```

**Livrables :**
<<<<<<< HEAD
- [ ] Calendrier earnings via API (Yahoo Finance gratuit)  
- [ ] Blackout ±3 jours autour de la date de reporting  
- [ ] Filtre ex-dividende (spread pollué J-1/J+1)  
- [ ] Intégration dans `generate_signals()` comme gate  
- [ ] Re-backtest pour mesurer impact

### ├ëtape 0.4 ÔÇö Short Borrow Availability Check
**Sans locate, le short leg du pair trade ├®choue en live.**

```
Impact : Pr├®vient les ├®checs d'ex├®cution + costs de borrow impr├®vus
=======
- [ ] Calendrier earnings via API (Yahoo Finance gratuit)
- [ ] Blackout ±3 jours autour de la date de reporting
- [ ] Filtre ex-dividende (spread pollué J-1/J+1)
- [ ] Intégration dans `generate_signals()` comme gate
- [ ] Re-backtest pour mesurer impact

### Étape 0.4 — Short Borrow Availability Check
**Sans locate, le short leg du pair trade échoue en live.**

```
Impact : Prévient les échecs d'exécution + costs de borrow imprévus
>>>>>>> origin/main
Fichiers : execution/borrow_check.py (NOUVEAU)
           execution/ibkr_execution.py (MODIFIER)
```

<<<<<<< HEAD
**Impl├®mentation :**
```python
# V├®rifier AVANT d'envoyer l'ordre :
#   1. Shortable? ÔåÆ IBKR reqContractDetails().shortableShares
#   2. Borrow fee? ÔåÆ Si fee > 3% annualis├®, REJETER le trade
#   3. Availability? ÔåÆ Si shortableShares < quantit├® requise, REJETER
=======
**Implémentation :**
```python
# Vérifier AVANT d'envoyer l'ordre :
#   1. Shortable? → IBKR reqContractDetails().shortableShares
#   2. Borrow fee? → Si fee > 3% annualisé, REJETER le trade
#   3. Availability? → Si shortableShares < quantité requise, REJETER
>>>>>>> origin/main
#
# Pour le backtest :
#   Les 37 mega-caps de v31h sont quasi-toujours shortable (HTB < 1%)
#   Mais lors de l'expansion univers (Phase 1.5), certains mid-caps
<<<<<<< HEAD
#   peuvent ├¬tre Hard-To-Borrow ÔåÆ filtre essentiel
```

**Livrables :**
- [ ] `BorrowChecker` : query IBKR shortable shares + fee rate  
- [ ] Gate dans l'exécution : rejeter si non-shortable ou fee > 3%  
- [ ] Logging : tracker les rejets pour identifier les symboles problématiques  
=======
#   peuvent être Hard-To-Borrow → filtre essentiel
```

**Livrables :**
- [ ] `BorrowChecker` : query IBKR shortable shares + fee rate
- [ ] Gate dans l'exécution : rejeter si non-shortable ou fee > 3%
- [ ] Logging : tracker les rejets pour identifier les symboles problématiques
>>>>>>> origin/main
- [ ] Intégration backtest : flag HTB historique (approximation via market cap)

---

<<<<<<< HEAD
## PHASE 1 ÔÇö AUGMENTATION DES SIGNAUX (Mois 2-4)
**Objectif : Passer de 2 signaux ├á 6-8, augmenter les trades ├á 50+/an**
**Capital requis : 0 Ôé¼ (donn├®es gratuites)**

### ├ëtape 1.1 ÔÇö Ornstein-Uhlenbeck Signal
**Le spread z-score actuel est statique. OU mod├®lise la vitesse de reversion.**

```
Alpha additionnel estim├® : +20-30% de trades qualifi├®s
=======
## PHASE 1 — AUGMENTATION DES SIGNAUX (Mois 2-4)
**Objectif : Passer de 2 signaux à 6-8, augmenter les trades à 50+/an**
**Capital requis : 0 € (données gratuites)**

### Étape 1.1 — Ornstein-Uhlenbeck Signal
**Le spread z-score actuel est statique. OU modélise la vitesse de reversion.**

```
Alpha additionnel estimé : +20-30% de trades qualifiés
>>>>>>> origin/main
Fichiers : signal_engine/ou_signal.py (NOUVEAU)
```

**Concept :**
```python
# Au lieu de simplement z = (spread - mean) / std,
<<<<<<< HEAD
# mod├®liser le processus OU : dX = ╬©(╬╝ - X)dt + ¤âdW
# ╬© = vitesse de mean-reversion (li├® ├á half-life)
# Signal = ╬© ├ù (╬╝ - X) / ¤â  ÔåÆ "expected profit velocity"
=======
# modéliser le processus OU : dX = θ(μ - X)dt + σdW
# θ = vitesse de mean-reversion (lié à half-life)
# Signal = θ × (μ - X) / σ  → "expected profit velocity"
>>>>>>> origin/main
# Entrer quand la vitesse de reversion est HAUTE, pas juste z > seuil
```

**Livrables :**
<<<<<<< HEAD
- [ ] `OUSignalGenerator` : estimation ╬©, ╬╝, ¤â par fen├¬tre glissante
- [ ] Signal : expected reversion velocity
- [ ] Int├®gration dans `SignalCombiner` (d├®j├á cr├®├® mais non wired)
- [ ] Backtest comparatif : OU seul vs z-score seul vs combin├®

### ├ëtape 1.2 ÔÇö Cross-Sectional Momentum Signal
**Le momentum overlay actuel est time-series. Ajouter cross-sectional.**

```
Alpha additionnel estim├® : +15-25% de Sharpe
=======
- [ ] `OUSignalGenerator` : estimation θ, μ, σ par fenêtre glissante
- [ ] Signal : expected reversion velocity
- [ ] Intégration dans `SignalCombiner` (déjà créé mais non wired)
- [ ] Backtest comparatif : OU seul vs z-score seul vs combiné

### Étape 1.2 — Cross-Sectional Momentum Signal
**Le momentum overlay actuel est time-series. Ajouter cross-sectional.**

```
Alpha additionnel estimé : +15-25% de Sharpe
>>>>>>> origin/main
Fichiers : signal_engine/cross_sectional.py (NOUVEAU)
```

**Concept :**
```python
# Ranker tous les symboles par return sur [1M, 3M, 6M, 12M]
# Pour un pair trade A/B :
<<<<<<< HEAD
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
=======
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
>>>>>>> origin/main
**Entrer quand la vol du spread est BASSE = faible risque, sortir quand haute.**

```
Fichiers : signal_engine/vol_signal.py (NOUVEAU)
```

**Concept :**
```python
# spread_vol = rolling_std(spread_returns, window=20)
# vol_ratio = spread_vol / spread_vol.rolling(60).mean()
<<<<<<< HEAD
# Entrer seulement quand vol_ratio < 0.8 (vol compress├®e)
# Sortir si vol_ratio > 1.5 (explosion de vol = r├®gime cass├®)
=======
# Entrer seulement quand vol_ratio < 0.8 (vol compressée)
# Sortir si vol_ratio > 1.5 (explosion de vol = régime cassé)
>>>>>>> origin/main
```

**Livrables :**
- [ ] `VolatilityRegimeSignal` class
<<<<<<< HEAD
- [ ] Gate d'entr├®e : vol_ratio < seuil
- [ ] Gate de sortie : vol explosion
- [ ] Backtest comparatif

### ├ëtape 1.4 ÔÇö Wiring du SignalCombiner
**Le `SignalCombiner` existe d├®j├á mais n'est wired nulle part.**
=======
- [ ] Gate d'entrée : vol_ratio < seuil
- [ ] Gate de sortie : vol explosion
- [ ] Backtest comparatif

### Étape 1.4 — Wiring du SignalCombiner
**Le `SignalCombiner` existe déjà mais n'est wired nulle part.**
>>>>>>> origin/main

```
Fichiers : signal_engine/combiner.py (EXISTE)
           strategies/pair_trading.py (MODIFIER)
           backtests/strategy_simulator.py (MODIFIER)
```

**Livrables :**
<<<<<<< HEAD
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
=======
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
>>>>>>> origin/main
  Health: LLY, TMO (mega pharma)
  ETFs:   XLK, XLF, XLE (excellent pour pairing)
```

**Livrables :**
<<<<<<< HEAD
- [ ] Script de test incr├®mental automatis├®
- [ ] Tableau symbole-par-symbole : delta Sharpe, delta PF
- [ ] Univers valid├® "v32" : v31h + symboles prouv├®s
- [ ] **Crit├¿re** : Univers 40-55 sym, Sharpe ÔëÑ 1.2, Trades ÔëÑ 40/an

---

## PHASE 2 ÔÇö RISK MANAGEMENT INSTITUTIONNEL (Mois 4-6)
**Objectif : Factor-neutralit├®, contr├┤le du risque portfolio**
**Capital requis : 0 Ôé¼ (calculs internes)**

### ├ëtape 2.1 ÔÇö Beta-Neutralit├® Portfolio
=======
- [ ] Script de test incrémental automatisé
- [ ] Tableau symbole-par-symbole : delta Sharpe, delta PF
- [ ] Univers validé "v32" : v31h + symboles prouvés
- [ ] **Critère** : Univers 40-55 sym, Sharpe ≥ 1.2, Trades ≥ 40/an

---

## PHASE 2 — RISK MANAGEMENT INSTITUTIONNEL (Mois 4-6)
**Objectif : Factor-neutralité, contrôle du risque portfolio**
**Capital requis : 0 € (calculs internes)**

### Étape 2.1 — Beta-Neutralité Portfolio
>>>>>>> origin/main
```
Fichiers : risk/factor_model.py (NOUVEAU)
           risk/portfolio_optimizer.py (NOUVEAU)
```

<<<<<<< HEAD
**Impl├®mentation :**
=======
**Implémentation :**
>>>>>>> origin/main
```python
# Pour chaque position :
#   beta_A = cov(R_A, R_SPY) / var(R_SPY)  rolling 60 jours
#   beta_B = cov(R_B, R_SPY) / var(R_SPY)
<<<<<<< HEAD
#   Ajuster les poids du pair trade pour que beta_net Ôëê 0
#   Si pair = long A, short B :
#     w_A = 1.0, w_B = -(beta_A / beta_B)  ÔåÆ beta neutral
#
# Au niveau portfolio :
#   sum(beta_i ├ù notional_i) / total_notional < 0.05
=======
#   Ajuster les poids du pair trade pour que beta_net ≈ 0
#   Si pair = long A, short B :
#     w_A = 1.0, w_B = -(beta_A / beta_B)  → beta neutral
#
# Au niveau portfolio :
#   sum(beta_i × notional_i) / total_notional < 0.05
>>>>>>> origin/main
```

**Livrables :**
- [ ] Estimation beta rolling par symbole
<<<<<<< HEAD
- [ ] Ajustement des hedge ratios pour beta-neutralit├®
- [ ] Contrainte portfolio : |beta_net| < 0.05
- [ ] Monitoring du beta en temps r├®el (live trading)

### ├ëtape 2.2 ÔÇö Sector-Neutralit├® + Corr├®lation Inter-Positions
=======
- [ ] Ajustement des hedge ratios pour beta-neutralité
- [ ] Contrainte portfolio : |beta_net| < 0.05
- [ ] Monitoring du beta en temps réel (live trading)

### Étape 2.2 — Sector-Neutralité + Corrélation Inter-Positions
>>>>>>> origin/main
```
Fichiers : risk/sector_limits.py (NOUVEAU)
           risk/position_correlation.py (NOUVEAU)
```

<<<<<<< HEAD
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
=======
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
>>>>>>> origin/main
```
Fichiers : risk/var_monitor.py (NOUVEAU)
```

**Livrables :**
- [ ] VaR 95% historique rolling 60j
- [ ] CVaR 95% (Expected Shortfall)
- [ ] Circuit-breaker : stop trading si VaR > 2% du NAV
- [ ] Rapport quotidien de risque

<<<<<<< HEAD
### ├ëtape 2.4 ÔÇö Drawdown Management Multi-Niveaux
```
TIER 1 (DD > 3%)  : R├®duire sizing de 50%
TIER 2 (DD > 5%)  : Fermer 50% des positions
TIER 3 (DD > 8%)  : Fermer TOUTES les positions, cooldown 10 jours
TIER 4 (DD > 12%) : Arr├¬t complet, review manuelle obligatoire
=======
### Étape 2.4 — Drawdown Management Multi-Niveaux
```
TIER 1 (DD > 3%)  : Réduire sizing de 50%
TIER 2 (DD > 5%)  : Fermer 50% des positions
TIER 3 (DD > 8%)  : Fermer TOUTES les positions, cooldown 10 jours
TIER 4 (DD > 12%) : Arrêt complet, review manuelle obligatoire
>>>>>>> origin/main
```

**Livrables :**
- [ ] `DrawdownManager` multi-tier
<<<<<<< HEAD
- [ ] Int├®gration backtest + live
- [ ] Alertes email/SMS ├á chaque tier

---

## PHASE 3 ÔÇö FR├ëQUENCE & EX├ëCUTION (Mois 6-9)
**Objectif : Passer de daily ├á intraday, ex├®cution algorithmique**
**Capital requis : ~500 Ôé¼/an (donn├®es intraday + serveur)**

### ├ëtape 3.1 ÔÇö Donn├®es Intraday (5min bars)
=======
- [ ] Intégration backtest + live
- [ ] Alertes email/SMS à chaque tier

---

## PHASE 3 — FRÉQUENCE & EXÉCUTION (Mois 6-9)
**Objectif : Passer de daily à intraday, exécution algorithmique**
**Capital requis : ~500 €/an (données intraday + serveur)**

### Étape 3.1 — Données Intraday (5min bars)
>>>>>>> origin/main
```
Source : IBKR Historical Data (inclus dans l'abonnement)
Stockage : SQLite ou Parquet local
Fichiers : data/intraday_loader.py (NOUVEAU)
```

**Livrables :**
<<<<<<< HEAD
- [ ] Collecteur de donn├®es 5min depuis IBKR
- [ ] Stockage Parquet partitionn├® par date/symbole
- [ ] Adaptation du backtest simulator pour barres 5min
- [ ] Validation : v31h sur 5min bars vs daily

### ├ëtape 3.2 ÔÇö Signaux Intraday
=======
- [ ] Collecteur de données 5min depuis IBKR
- [ ] Stockage Parquet partitionné par date/symbole
- [ ] Adaptation du backtest simulator pour barres 5min
- [ ] Validation : v31h sur 5min bars vs daily

### Étape 3.2 — Signaux Intraday
>>>>>>> origin/main
```
Fichiers : signal_engine/intraday_signals.py (NOUVEAU)
```

**Nouveaux signaux possibles en intraday :**
```python
# 1. Mean-reversion intraday du spread
<<<<<<< HEAD
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
=======
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
>>>>>>> origin/main
```
Fichiers : execution/algo_executor.py (NOUVEAU)
           execution/ibkr_algo.py (NOUVEAU)
```

<<<<<<< HEAD
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
=======
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
>>>>>>> origin/main
```
Source : Yahoo Finance / Alpha Vantage (gratuit)
Fichiers : signal_engine/earnings_signal.py (NOUVEAU)
```

**Concept :**
```python
<<<<<<< HEAD
# Post-earnings drift (PEAD) est un des alphas les plus document├®s
# Si earnings surprise > 0 ÔåÆ momentum haussier pendant 60 jours
# Int├®grer comme signal directionnel dans les pair trades
# Favoriser le c├┤t├® du pair avec la meilleure surprise
```

### ├ëtape 4.2 ÔÇö Options Flow Signal
=======
# Post-earnings drift (PEAD) est un des alphas les plus documentés
# Si earnings surprise > 0 → momentum haussier pendant 60 jours
# Intégrer comme signal directionnel dans les pair trades
# Favoriser le côté du pair avec la meilleure surprise
```

### Étape 4.2 — Options Flow Signal
>>>>>>> origin/main
```
Source : IBKR Options chain (inclus)
Fichiers : signal_engine/options_flow.py (NOUVEAU)
```

**Concept :**
```python
# Put/Call ratio du symbole
# Implied Vol skew (put IV - call IV)
<<<<<<< HEAD
# Unusual options activity (volume > 3├ù moyenne)
# Signal : smart money positioning via options
```

### ├ëtape 4.3 ÔÇö NLP Sentiment Signal
=======
# Unusual options activity (volume > 3× moyenne)
# Signal : smart money positioning via options
```

### Étape 4.3 — NLP Sentiment Signal
>>>>>>> origin/main
```
Source : News API (NewsAPI.org ~$50/mois) ou RSS gratuit
Fichiers : signal_engine/sentiment.py (NOUVEAU)
```

**Concept :**
```python
<<<<<<< HEAD
# FinBERT (mod├¿le HuggingFace gratuit) sur titres de news
# Score sentiment [-1, +1] par symbole par jour
# Signal : divergence sentiment vs price ÔåÆ mean-reversion signal
```

### ├ëtape 4.4 ÔÇö ML Signal Combiner
**Remplacer le `SignalCombiner` equal-weight par un mod├¿le ML.**
=======
# FinBERT (modèle HuggingFace gratuit) sur titres de news
# Score sentiment [-1, +1] par symbole par jour
# Signal : divergence sentiment vs price → mean-reversion signal
```

### Étape 4.4 — ML Signal Combiner
**Remplacer le `SignalCombiner` equal-weight par un modèle ML.**
>>>>>>> origin/main

```
Fichiers : signal_engine/ml_combiner.py (NOUVEAU)
```

<<<<<<< HEAD
**Impl├®mentation :**
```python
# Mod├¿le : LightGBM / XGBoost
# Features : tous les signaux (z-score, momentum, OU, vol, sentiment...)
# Target : return du trade sur les N prochains jours
# Training : walk-forward (train 2 ans, test 6 mois, roll)
# Anti-overfitting : cross-validation purifi├®e, feature importance
=======
**Implémentation :**
```python
# Modèle : LightGBM / XGBoost
# Features : tous les signaux (z-score, momentum, OU, vol, sentiment...)
# Target : return du trade sur les N prochains jours
# Training : walk-forward (train 2 ans, test 6 mois, roll)
# Anti-overfitting : cross-validation purifiée, feature importance
>>>>>>> origin/main
```

**Livrables :**
- [ ] Pipeline walk-forward ML
- [ ] Feature importance analysis
- [ ] Backtest ML-combined vs equal-weight
<<<<<<< HEAD
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
=======
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
>>>>>>> origin/main
```
Exemples : ES/NQ spread, CL/BZ spread, ZN/ZB spread
Avantage : pas de short-selling cost, levier naturel
```

<<<<<<< HEAD
### ├ëtape 5.3 ÔÇö Levier Progressif
```
Phase 0-2 : Levier 1.0├ù (100KÔé¼)
Phase 3   : Levier 1.5├ù (150KÔé¼ d'exposition sur 100KÔé¼)
Phase 4   : Levier 2.0├ù (200KÔé¼ d'exposition)
Phase 5   : Levier 2.5-3.0├ù (si Sharpe > 2.0 confirm├® sur 12 mois)

R├êGLE : NE JAMAIS augmenter le levier si Sharpe live < 1.5
=======
### Étape 5.3 — Levier Progressif
```
Phase 0-2 : Levier 1.0× (100K€)
Phase 3   : Levier 1.5× (150K€ d'exposition sur 100K€)
Phase 4   : Levier 2.0× (200K€ d'exposition)
Phase 5   : Levier 2.5-3.0× (si Sharpe > 2.0 confirmé sur 12 mois)

RÈGLE : NE JAMAIS augmenter le levier si Sharpe live < 1.5
>>>>>>> origin/main
```

---

<<<<<<< HEAD
## PHASE 6 ÔÇö INFRASTRUCTURE PRO (Mois 20-24)
**Objectif : R├®silience, monitoring, scalabilit├®**
**Capital requis : ~2000 Ôé¼/an (serveur cloud)**

### ├ëtape 6.1 ÔÇö Colocation Serveur
```
VPS d├®di├® (OVH/Hetzner) : ~50 Ôé¼/mois
=======
## PHASE 6 — INFRASTRUCTURE PRO (Mois 20-24)
**Objectif : Résilience, monitoring, scalabilité**
**Capital requis : ~2000 €/an (serveur cloud)**

### Étape 6.1 — Colocation Serveur
```
VPS dédié (OVH/Hetzner) : ~50 €/mois
>>>>>>> origin/main
Latence IBKR : <5ms (vs ~50ms depuis domicile)
Uptime 99.9% vs risques PC personnel
```

<<<<<<< HEAD
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
=======
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
>>>>>>> origin/main
- Circuit-breaker automatique si perte de connexion
- Position reconciliation IBKR vs interne
```

---

<<<<<<< HEAD
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
=======
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
>>>>>>> origin/main

### Go / No-Go par Phase

```
<<<<<<< HEAD
R├êGLE #1 ÔÇö NE PAS passer ├á Phase N+1 si Phase N n'est pas valid├®e
R├êGLE #2 ÔÇö Validation = backtest + 3 mois de paper trading positif
R├êGLE #3 ÔÇö Jamais augmenter le levier si Sharpe live < 1.5
R├êGLE #4 ÔÇö Stop total si DD live > 12% ÔåÆ review compl├¿te obligatoire
R├êGLE #5 ÔÇö Chaque nouveau signal doit passer backtest isol├® + combin├®
```

### M├®triques de Monitoring (quotidien)

```
- PnL journalier + cumul├®
=======
RÈGLE #1 — NE PAS passer à Phase N+1 si Phase N n'est pas validée
RÈGLE #2 — Validation = backtest + 3 mois de paper trading positif
RÈGLE #3 — Jamais augmenter le levier si Sharpe live < 1.5
RÈGLE #4 — Stop total si DD live > 12% → review complète obligatoire
RÈGLE #5 — Chaque nouveau signal doit passer backtest isolé + combiné
```

### Métriques de Monitoring (quotidien)

```
- PnL journalier + cumulé
>>>>>>> origin/main
- Sharpe rolling 60 jours
- Max drawdown rolling
- Beta portfolio vs SPY
- Nombre de trades ouverts
<<<<<<< HEAD
- Slippage r├®el vs estim├®
=======
- Slippage réel vs estimé
>>>>>>> origin/main
- VaR 95% portfolio
```

### Budget Annuel

| Poste | Phase 0-2 | Phase 3-4 | Phase 5-6 |
|-------|-----------|-----------|-----------|
<<<<<<< HEAD
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
=======
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
>>>>>>> origin/main

```
Langage       : Python 3.11+ (calculs) + Cython/Rust (hot paths)
Broker        : IBKR Gateway (API TWS)
<<<<<<< HEAD
Data Store    : Parquet (historique) + Redis (temps r├®el)
Backtest      : EDGECORE Simulator (existant, am├®lior├®)
ML            : LightGBM + scikit-learn (features) + Optuna (HPO)
Monitoring    : Prometheus + Grafana (configs existantes)
Alerting      : Telegram Bot / Email SMTP
Serveur       : VPS Hetzner (AX41, ~40Ôé¼/mois)
=======
Data Store    : Parquet (historique) + Redis (temps réel)
Backtest      : EDGECORE Simulator (existant, amélioré)
ML            : LightGBM + scikit-learn (features) + Optuna (HPO)
Monitoring    : Prometheus + Grafana (configs existantes)
Alerting      : Telegram Bot / Email SMTP
Serveur       : VPS Hetzner (AX41, ~40€/mois)
>>>>>>> origin/main
CI/CD         : GitHub Actions (tests auto)
```

---

<<<<<<< HEAD
*Document g├®n├®r├® le 7 mars 2026*
*Baseline : EDGECORE v31h ÔÇö Sharpe 1.31, PF 3.88, Return +8.17%*
*Auteur : EDGECORE Team*

# R├®sultats du backtest v48 (Anticipatory Exit)

---

**R├®sum├® institutionnel (13 mars 2026)**

- **Backtest termin├®** : tous les filtres institutionnels actifs (slippage, Kelly sizing, earnings/dividend blackout, borrow check, stabilit├® cointegration).
- **R├®sultats par p├®riode** :

| P├®riode | Score (S) | Perf (%) | Win Rate | Trades | Drawdown | Statut |
=======
*Document généré le 7 mars 2026*
*Baseline : EDGECORE v31h — Sharpe 1.31, PF 3.88, Return +8.17%*
*Auteur : EDGECORE Team*

# Résultats du backtest v48 (Anticipatory Exit)

---

**Résumé institutionnel (13 mars 2026)**

- **Backtest terminé** : tous les filtres institutionnels actifs (slippage, Kelly sizing, earnings/dividend blackout, borrow check, stabilité cointegration).
- **Résultats par période** :

| Période | Score (S) | Perf (%) | Win Rate | Trades | Drawdown | Statut |
>>>>>>> origin/main
|---------|-----------|----------|----------|--------|----------|--------|
| P3 2022H2 | 0.00 | +0.00% | 0.0% | 0 | +0.00% | FAIL |
| P4 2023H2 | 1.41 | +2.36% | 100.0% | 2 | -0.55% | PASS |
| P5 2024H2 | 0.00 | +0.00% | 0.0% | 0 | +0.00% | FAIL |

<<<<<<< HEAD
- **Synth├¿se** : PASS=1/5, FAIL=4/5, moyenne=0.10, min=-0.90 ÔåÆ **FAIL**
=======
- **Synthèse** : PASS=1/5, FAIL=4/5, moyenne=0.10, min=-0.90 → **FAIL**
>>>>>>> origin/main

---

**Comparaison exit_z (progression v46 vs v48)**

<<<<<<< HEAD
| P├®riode | v46 exit_z=0.2 | v48 exit_z=0.5 |
=======
| Période | v46 exit_z=0.2 | v48 exit_z=0.5 |
>>>>>>> origin/main
|---------|----------------|---------------|
| P1 | -1.67 | +0.00 (+1.67) |
| P2 | +2.27 | -0.90 (-3.17) |
| P3 | +2.24 | +0.00 (-2.24) |
| P4 | +0.46 | +1.41 (+0.95) |
| P5 | -1.14 | +0.00 (+1.14) |

- **Diagnostic** :
<<<<<<< HEAD
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
=======
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
>>>>>>> origin/main

---
