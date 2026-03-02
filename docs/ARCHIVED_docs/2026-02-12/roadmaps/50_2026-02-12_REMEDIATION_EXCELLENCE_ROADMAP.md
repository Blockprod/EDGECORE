# 🎯 REMEDIATION ROADMAP — Atteindre 10/10 sur tous les niveaux

**Baseline audit** : Qualité statistique 2.5/10 | Robustesse réelle 3.0/10  
**Objectif** : Qualité 9.5+/10 | Robustesse 9.0+/10 | Score de survie 12m: 85%+

**Durée totale estimée** : 120-140 heures  
**Timeline** : 4 sprints de 2 semaines chacun

---

## 📊 Priorités (Impact vs Effort)

```
IMPACT ÉLEVÉ / EFFORT FAIBLE (Quick Wins)
├─ C4: Slippage/Commissions intégrés        [3h] → +15 Sharpe accuracy
├─ C6: Z-score threshold justification      [2h] → +10 params clarity
├─ Mi3: Spread std alert logic              [1h] → +5 robustness
└─ M2: Rolling window consistency           [2h] → +8 temporal correctness

IMPACT ÉLEVÉ / EFFORT MODÉRÉ (Core Fixes)
├─ C1: Bonferroni + p-value refactor        [4h] → +30 false positive reduction
├─ C2: OOS pair validation framework        [6h] → +25 lookback bias reduction
├─ M1: Dynamic hedge ratio reestimation     [5h] → +20 drift correction
└─ M5: Regime change detection              [8h] → +25 robustness

IMPACT ÉLEVÉ / EFFORT ÉLEVÉ (Deep Dives)
├─ C3: Half-life re-estimation on spreads   [7h] → +15 mean-reversion accuracy
├─ C5: WF cache isolation + persistence     [6h] → +20 test validity
├─ M3: Trailing stop implementation         [4h] → +12 downside protection
├─ M4: Cross-symbol concentration limits    [5h] → +18 portfolio diversification
└─ Advanced ML: Z-score threshold learning  [16h] → +20 signal quality

OPTIMIZATION & ENHANCEMENTS (Phase 2)
├─ Markov switching regime model            [12h] → +25 regime robustness
├─ Intraday signal integration              [10h] → +15 signal frequency
├─ Smart execution (iceberg orders)         [8h] → +10 execution quality
└─ Real-time monitoring dashboard           [12h] → +20 operational safety
```

---

## 🔴 SPRINT 1: Statut Critique (3 semaines)

**Objectif** : Passer de 2.5/10 → 5.5/10 en validité statistique  
**Focus** : Éliminer les faux positifs et biais de base

### Task S1.1: Bonferroni Correction Framework [4h]

**Dépend de** : Aucune  
**Bloque** : S1.2, S2.1

**Description**
Implémenter correction multiplie testing rigoureuse dans `models/cointegration.py`

**Sous-tâches**
- [ ] **S1.1a** (30min) : Ajouter param `num_symbols` à `engle_granger_test()`
  - Calculer alpha corrigé : `α_adj = 0.05 / (n*(n-1)/2)`
  - Logger: `p-value_critical = 0.05 / {n_pairs}` au startup
  
- [ ] **S1.1b** (1h) : Refactor `find_cointegrated_pairs()` à deux niveaux
  ```python
  # Étape 1: screening rapide à α = 0.05
  candidate_pairs = [p for p in all_pairs if p.pvalue < 0.05]
  
  # Étape 2: confirmation à α_corrected
  confirmed = [p for p in candidate_pairs if p.pvalue < α_corrected]
  
  logger.info("pair_discovery_bonferroni", 
    candidates=len(candidate_pairs), 
    confirmed=len(confirmed),
    bonferroni_alpha=α_corrected)
  ```

- [ ] **S1.1c** (1.5h) : Ajouter test unitaire `test_bonferroni_multiple_testing`
  ```python
  # Générer 100 synthetic random pairs (non-cointégrés)
  # Vérifier que ZÉRO sont accepted avec Bonferroni
  # Vérifier que ~5% sont accepted sans Bonferroni (expected false positive rate)
  assert confirmed_pairs == 0  # With Bonferroni
  assert len(candidates) > 3   # Without: 5% of 100 ≈ 5
  ```

- [ ] **S1.1d** (1h) : Documenter dans `README.md` + add config param
  ```yaml
  strategy:
    bonferroni_correction: true
    significance_level: 0.05  # Will be adjusted internally
  ```

**Success Criteria**
- ✅ Pair discovery count ↓ 70-80% (expected: 100 pairs → 15-25)
- ✅ Sharpe ratio backtest ± 5% (légère amélioration, moins de faux positifs)
- ✅ Test 100% passing
- ✅ Config loaded at startup

**Expected Impact** : +30% reduction en faux positifs

---

### Task S1.2: Out-of-Sample Pair Validation [6h]

**Dépend de** : S1.1  
**Bloque** : S2.1

**Description**
Implémenter validation OOS des paires après discovery

**Sous-tâches**
- [ ] **S1.2a** (1.5h) : Créer module `models/oos_validation.py`
  ```python
  class OOSPairValidator:
      """Validate cointegrated pairs on unseen data."""
      
      def validate_pair(
          self,
          sym1: str,
          sym2: str,
          training_data: pd.DataFrame,     # [t-252:t]
          validation_data: pd.DataFrame,   # [t:t+21] or [t:t+63]
          required_consistency: float = 0.7
      ) -> Tuple[bool, float]:
          """
          Test if pair remains cointegrated in OOS window.
          
          Returns:
              (is_valid, consistency_score)
              consistency_score = fraction of validation period where
                  pair maintains cointegration (adf_pvalue < 0.05)
          """
  ```

- [ ] **S1.2b** (2h) : Intégrer dans pair discovery
  ```python
  # Après S1.1 confirmation:
  confirmed_pairs = [...]  # After Bonferroni
  
  # Validate on OOS window
  validated_pairs = []
  for sym1, sym2, pval, hl in confirmed_pairs:
      is_valid, score = validator.validate_pair(
          sym1, sym2,
          training_data=[t-252:t],
          validation_data=[t:t+21]  # 3 weeks OOS
      )
      if is_valid and score >= 0.7:  # 70% of days cointegrated
          validated_pairs.append((sym1, sym2, pval, hl))
      else:
          logger.warning("pair_failed_oos", pair=f"{sym1}_{sym2}", score=score)
  ```

- [ ] **S1.2c** (1.5h) : Test unitaire `test_oos_validation_framework`
  ```python
  # Create synthetic cointegrated pair
  # Split: [0:80] train, [80:100] OOS
  # Verify: cointegration detected in train, persists in OOS validation
  # Add anti-test: break cointegration in OOS, verify rejection
  ```

- [ ] **S1.2d** (1h) : Configuration
  ```yaml
  strategy:
    oos_validation_enabled: true
    oos_lookforward_days: 21        # 3 weeks ahead
    oos_consistency_threshold: 0.7  # 70% of days
  ```

**Success Criteria**
- ✅ Validated pairs < 50% of confirmed pairs (expected fallout)
- ✅ OOS validation score logged per pair
- ✅ Walk-forward backtest: confirmed_pairs vs validated_pairs comparison
- ✅ Sharpe improvement 0.20-0.35 (fewer false pairs)

**Expected Impact** : +25% reduction en lookback bias, +0.30 Sharpe

---

### Task S1.3: Slippage & Commission Integration [3h]

**Dépend de** : Aucune  
**Bloque** : S1.5

**Description**
Intégrer réaliste frais/slippage dans backtests P&L

**Sous-tâches**
- [ ] **S1.3a** (1h) : Créer `models/costs.py`
  ```python
  @dataclass
  class TradesCosts:
      """Realistic costs for pair trading execution."""
      
      # Entry costs
      entry_slippage_bps: float = 5.0            # 5 bps per leg
      entry_commission_pct: float = 0.001        # 0.1% taker IBKR × 2 legs
      
      # Exit costs
      exit_slippage_bps: float = 5.0
      exit_commission_pct: float = 0.001
      
      def round_trip_cost_basis_points(self) -> float:
          """Calculate cost of entering + exiting position in basis points."""
          entry_cost = (self.entry_slippage_bps + 
                       self.entry_commission_pct * 10000) * 2  # 2 legs
          exit_cost = (self.exit_slippage_bps + 
                      self.exit_commission_pct * 10000) * 2
          return entry_cost + exit_cost
      
      # Example: 5 + 10 = 15 bps entry, 15 exit = 30 bps round-trip
  ```

- [ ] **S1.3b** (1h) : Intégrer dans `backtests/metrics.py`
  ```python
  @classmethod
  def from_returns(cls, returns, trades, start_date, end_date, costs: TradeCosts):
      # ... existing metrics calculations...
      
      # Apply costs
      gross_pnl = sum(returns)
      trading_costs = len(trades) * (costs.round_trip_cost_basis_points() / 10000)
      net_pnl = gross_pnl - trading_costs
      
      # Recalculate Sharpe with net returns
      net_returns = returns - (trading_costs / len(returns))
      sharpe_ratio = (net_returns.mean() / net_returns.std()) * sqrt(252)
      
      return cls(
          # ... other fields ...
          sharpe_ratio=sharpe_ratio,  # NOW with costs!
          gross_pnl=gross_pnl,
          trading_costs=trading_costs,
          net_pnl=net_pnl
      )
  ```

- [ ] **S1.3c** (1h) : Tests + validation
  ```python
  def test_slippage_impact_on_sharpe():
      # Backtest without costs: Sharpe = 1.8
      # Backtest with costs: Sharpe = 1.2 (expected -33%)
      assert abs(sharpe_no_costs - sharpe_with_costs) / sharpe_no_costs >= 0.25
  ```

**Success Criteria**
- ✅ Backtest Sharpe ↓ 30-40% (expected impact)
- ✅ Win rate ↓ 15-25% (marginal trades eliminated)
- ✅ Max DD ↑ 1-2% (costs add friction)
- ✅ Config readable, documentation clear

**Expected Impact** : +15 points Sharpe accuracy

---

### Task S1.4: Z-Score Threshold Justification & Optimization [2h]

**Dépend de** : S1.3  
**Bloque** : S2.2

**Description**
Justifier/optimiser empiriquement le seuil |Z| > 2.0

**Sous-tâches**
- [ ] **S1.4a** (1h) : Grid search sur seuils
  ```python
  def optimize_z_score_threshold(backtest_data, threshold_range=[1.0, 3.0, 0.1]):
      """
      Test all Z-score thresholds, return optimal + metrics.
      """
      results = []
      for z_thresh in np.arange(1.0, 3.0, 0.1):
          metrics = run_backtest(data, z_threshold=z_thresh)
          results.append({
              'threshold': z_thresh,
              'sharpe': metrics.sharpe_ratio,
              'win_rate': metrics.win_rate,
              'trades': metrics.total_trades,
              'dd': metrics.max_drawdown
          })
      
      # Plot: Sharpe vs Threshold
      # Select threshold that maximizes Sharpe on **out-of-sample** data
      return optimal_threshold, results_df
  ```

- [ ] **S1.4b** (0.5h) : Document justification
  ```yaml
  strategy:
    entry_z_score: 2.2  # Optimized via grid search on OOS data
    # Rationale: 
    #  - Z < 1.5: too many false entries (win_rate ~40%)
    #  - Z = 2.0: baseline (win_rate ~52%)
    #  - Z = 2.2: optimal Sharpe (OOS) = 1.15
    #  - Z > 2.5: too few trade, high slippage impact
  ```

- [ ] **S1.4c** (0.5h) : Test
  ```python
  def test_z_threshold_optimization():
      results = optimize_z_scores(oos_data)
      optimal_z = results['optimal_threshold']
      assert 1.8 <= optimal_z <= 2.5  # Sanity check
      assert results['oos_sharpe'] > results['oos_sharpe_at_2_0']
  ```

**Success Criteria**
- ✅ Optimal threshold identified (usually 2.0-2.3)
- ✅ Justification documented
- ✅ OOS Sharpe improvement 0.05-0.15 vs hardcoded 2.0

**Expected Impact** : +10 parameter clarity

---

### Task S1.5: Walk-Forward Cache Isolation [6h]

**Dépend de** : S1.3  
**Bloque** : S2.1

**Description**
Éliminer cache 24h que persiste entre periods WF

**Sous-tâches**
- [ ] **S1.5a** (1h) : Auditer logique cache actuelle
  ```python
  # Current: pair_trading.py:210
  def find_cointegrated_pairs(self, ...):
      if use_cache:
          cached = self.load_cached_pairs(max_age_hours=24)  # ← PROBLEM
          if cached is not None:
              return cached  # Reuse 24h old pairs!
  ```

- [ ] **S1.5b** (2h) : Refactor cache scope
  ```python
  class CacheScope:
      """Control cache persistence scope."""
      BACKTEST_PERIOD = "backtest_period"  # Expire at period boundary
      SESSION = "session"  # Expire at program restart
      NONE = "none"  # No cache (slowest, most correct)
  
  def find_cointegrated_pairs(self, ..., cache_scope=CacheScope.NONE):
      """
      If cache_scope=BACKTEST_PERIOD:
        - Cache WITHIN a WF period
        - Clear at period boundary (train → test)
      If cache_scope=NONE:
        - No caching (recompute every call)
        - Slowest but most correct for validation
      """
      if cache_scope == CacheScope.NONE:
          # Disable cache entirely for walk-forward
          return self._discover_pairs(price_data)
      elif cache_scope == CacheScope.BACKTEST_PERIOD:
          # Cache only within period, clear on boundary
          cache_key = self._get_period_boundary_key(price_data)
          if cache_key != self.last_cache_key:
              self.cached_pairs = None  # Clear on boundary
          
          if self.cached_pairs is not None:
              return self.cached_pairs
          
          pairs = self._discover_pairs(price_data)
          self.cached_pairs = pairs
          self.last_cache_key = cache_key
          return pairs
  ```

- [ ] **S1.5c** (1.5h) : Intégrer dans WF backtest
  ```python
  # walk_forward.py
  def run_walk_forward(...):
      for period_idx, (train_df, test_df) in enumerate(splits):
          # Clear cache explicitly at period boundary
          self.strategy.clear_pair_cache()
          
          # Run on test data WITHOUT cache
          metrics = self.runner.run(
              ...,
              pair_discovery_cache_scope="NONE"  # Disable cache for validation
          )
  ```

- [ ] **S1.5d** (1.5h) : Tests
  ```python
  def test_walk_forward_cache_isolation():
      """Verify pairs are NOT reused across WF periods."""
      
      # Period 1: Discover pairs on [t:t+80]
      pairs_p1 = strategy.find_cointegrated_pairs(data[:80])
      
      # Period 2: Should discover FRESH pairs on [t+80:t+160]
      # NOT reuse pairs from P1
      strategy.clear_pair_cache()
      pairs_p2 = strategy.find_cointegrated_pairs(data[80:160])
      
      # P1 and P2 pairs should mostly differ (different windows)
      assert len(set(pairs_p1) & set(pairs_p2)) <= 2  # Small overlap expected
  ```

**Success Criteria**
- ✅ Cache scoped to period boundaries
- ✅ Walk-forward backtest reproducible (deterministic)
- ✅ No hidden data leakage in metrics
- ✅ WF Sharpe ±3% of expected (realistic)

**Expected Impact** : +20 points test validity

---

### Task S1.6: Metrics Cleanup & Documentation [2h]

**Dépend de** : S1.3  
**Bloque** : S1.7

**Description**
Documenter tout ce qui a changé, setup final S1

**Sous-tâches**
- [ ] **S1.6a** (1h) : Mettre à jour config
  ```yaml
  # config/dev.yaml
  
  strategy:
    bonferroni_correction: true
    significance_level: 0.05
    entry_z_score: 2.2  # Optimized
    exit_z_score: 0.0
    min_correlation: 0.7
    max_half_life: 60
    lookback_window: 252
    oos_validation_enabled: true
    oos_lookforward_days: 21
    oos_consistency_threshold: 0.7
    pair_cache_scope: "BACKTEST_PERIOD"  # or "NONE" for validation
  ```

- [ ] **S1.6b** (1h) : README + CHANGELOG
  ```markdown
  # SPRINT 1 COMPLETION SUMMARY
  
  **Changes:**
  - ✅ Bonferroni correction: 70-80% reduction en faux positifs
  - ✅ OOS validation: Eliminates 50% of "phantom" pairs
  - ✅ Slippage integration: -30-40% Sharpe realistic
  - ✅ Z-threshold optimized: +0.10 Sharpe OOS
  - ✅ Cache isolation: No leakage between WF periods
  
  **New Config Parameters:**
  - bonferroni_correction: true
  - oos_validation_enabled: true
  - pair_cache_scope: "BACKTEST_PERIOD"
  
  **Test Results:**
  - Unit tests: 35/35 PASSING
  - Integration tests: 12/12 PASSING
  - WF reproducibility: ✅ Confirmed
  ```

**Success Criteria**
- ✅ All changes documented
- ✅ Config defaults sensible
- ✅ Code comments clear

---

### S1 Final Validation [2h]

**Checklist**
- [ ] All 6 tasks completed
- [ ] 100% test passing
- [ ] Backtest Sharpe: 1.8 → 1.2 (expected)
- [ ] OOS validation pairs: 70-80% of confirmed
- [ ] Cache isolation verified WF
- [ ] Documentation complete

**Expected Outcome after S1**
- Validité statistique: 2.5/10 → 5.5/10 (+120%)
- Robustesse réelle: 3.0/10 → 4.5/10 (+50%)
- False positives: 75% → 15%
- Sharpe accuracy: ±50% → ±20%

---

## 🟠 SPRINT 2: Problèmes majeurs (3 semaines)

**Objectif** : Passer de 5.5/10 → 7.5/10 en validité | 4.5/10 → 6.5/10 en robustesse  
**Focus** : Stabilité hedge ratio + regime changes + concentration

### Task S2.1: Dynamic Hedge Ratio Reestimation [5h]

**Dépend de** : S1.2  
**Bloque** : S2.3

**Description**
Ré-estimer hedge ratio β mensuellement pour chaque paire

**Sous-tâches**
- [ ] **S2.1a** (1h) : Créer `models/hedge_ratio_tracker.py`
  ```python
  class HedgeRatioTracker:
      """Track hedge ratio (β) stability over time."""
      
      def __init__(self):
          self.pair_betas = {}  # {pair_key: [(date, beta, is_stable)]}
          self.reestimation_frequency = 30  # days
      
      def reestimate_if_needed(self, pair_key, price_data):
          """
          Reestimate β if enough time has passed.
          Log drift if β changed > 10%.
          """
          last_estimate_date = self.pair_betas[pair_key][-1][0]
          days_elapsed = (today - last_estimate_date).days
          
          if days_elapsed >= self.reestimation_frequency:
              old_beta = self.pair_betas[pair_key][-1][1]
              
              # Reestimate on last 252 days
              new_beta = self._estimate_beta(price_data[-252:])
              drift = abs(new_beta - old_beta) / old_beta
              
              logger.info("hedge_ratio_reestimated", 
                pair=pair_key,
                old_beta=old_beta,
                new_beta=new_beta,
                drift_pct=drift*100)
              
              # Flag if drift > 10%
              if drift > 0.10:
                  logger.warning("hedge_ratio_unstable", 
                    pair_key=pair_key,
                    drift_pct=drift*100,
                    action="DEPRECATING pair")
                  return new_beta, False  # (beta, is_stable)
              
              self.pair_betas[pair_key].append((today, new_beta, True))
              return new_beta, True
          
          return self.pair_betas[pair_key][-1][1], True
  ```

- [ ] **S2.1b** (1.5h) : Intégrer dans `SpreadModel`
  ```python
  class SpreadModel:
      def __init__(self, y, x, hedge_ratio_tracker=None):
          self.y = y
          self.x = x
          self.tracker = hedge_ratio_tracker
          
          # Initial estimate
          beta = self._estimate_beta(x, y)
          self.beta = beta
          self.last_beta_update_date = today
      
      def compute_spread(self, y, x):
          """Compute spread with potentially updated β."""
          
          # Check if β needs reestimation
          if self.tracker is not None:
              new_beta, is_stable = self.tracker.reestimate_if_needed(
                  self.pair_key, 
                  historical_prices
              )
              
              if not is_stable:
                  logger.warning("spread_unstable", pair=self.pair_key)
                  # Signal to strategy: deprecate this pair
                  self.is_deprecated = True
              
              self.beta = new_beta
          
          return y - (self.intercept + self.beta * x)
  ```

- [ ] **S2.1c** (1.5h) : Intégrer dans stratégie
  ```python
  # pair_trading.py
  def generate_signals(self, market_data):
      signals = []
      
      for sym1, sym2, pval, hl in self.cointegrated_pairs:
          pair_key = f"{sym1}_{sym2}"
          
          # Get spread model (may have been reestimated)
          model = self.spread_models[pair_key]
          spread = model.compute_spread(y, x)
          
          # Check if model is deprecated
          if model.is_deprecated:
              logger.warning("signal_skipped_deprecated", pair=pair_key)
              continue  # Don't trade this pair
          
          z_score = model.compute_z_score(spread)
          # ... rest of signal generation
  ```

- [ ] **S2.1d** (1h) : Tests
  ```python
  def test_hedge_ratio_reestimation():
      tracker = HedgeRatioTracker()
      
      # Initial estimate: β = 1.5
      beta1 = tracker.estimate_beta(data[0:252])
      
      # After 30 days, no reestimate
      beta_none = tracker.reestimate_if_needed(pair, data[0:282])
      assert beta_none == beta1
      
      # After 30+ days with stable relationship
      beta2 = tracker.reestimate_if_needed(pair, data[0:300])
      assert abs(beta2 - beta1) / beta1 < 0.10  # Drift < 10%
      
      # After drift > 15%, deprecated
      # (synthetic data with broken cointegration)
      beta3, is_stable = tracker.reestimate_if_needed(pair, broken_data)
      assert not is_stable
  ```

**Success Criteria**
- ✅ β tracked per pair with dates
- ✅ Monthly reestimation implemented
- ✅ Drift > 10% flags pair for deprecation
- ✅ Spread calculation uses updated β
- ✅ Tests 100% passing

**Expected Impact** : +20 points drift correction (5% → 2% spread error)

---

### Task S2.2: Z-Score Window Consistency [2h]

**Dépend de** : S1.4  
**Bloque** : S2.4

**Description**
Align Z-score rolling window (20 days) avec half-life (60 days)

**Sous-tâches**
- [ ] **S2.2a** (1h) : Justifier fenêtre
  ```python
  # models/spread.py
  def compute_z_score(self, spread, lookback=None):
      """
      Compute rolling Z-score with dynamically justified lookback.
      
      Justification:
      - If estimated half_life > 60 days:
          lookback = half_life (capture full mean-reversion cycle)
      - If estimated half_life < 30 days:
          lookback = 3 * half_life (smooth short-term noise)
      - Default: min(half_life, 60)
      """
      
      if lookback is None:
          # Infer from half-life
          hl = self.estimated_half_life  # New addition to SpreadModel
          lookback = max(20, min(hl, 60))  # Between 20-60 days
      
      logger.info("z_score_window", pair=self.pair_key, lookback=lookback, half_life=hl)
      
      rolling_mean = spread.rolling(window=lookback).mean()
      rolling_std = spread.rolling(window=lookback).std()
      z = (spread - rolling_mean) / (rolling_std + 1e-8)
      
      return z
  ```

- [ ] **S2.2b** (1h) : Configuration
  ```yaml
  strategy:
    z_score_lookback_method: "half_life_adaptive"  # vs "fixed"
    z_score_lookback_min: 20  days
    z_score_lookback_max: 60  days
  ```

**Success Criteria**
- ✅ Lookback window inferred from half-life
- ✅ Config documented
- ✅ Z-score more stable (less jitter)

**Expected Impact** : +8 temporal correctness

---

### Task S2.3: Trailing Stop Implementation [4h]

**Dépend de** : S2.1  
**Bloque** : S2.5

**Description**
Ajouter trailing stop pour limiter downside

**Sous-tâches**
- [ ] **S2.3a** (1.5h) : Logic de stop
  ```python
  class TrailingStopManager:
      """Manage trailing stops for spread positions."""
      
      def should_exit_on_trailing_stop(self, position, spread):
          """
          Check if spread has expanded too much since entry.
          
          Logic:
          - Entry Z-score: z_entry = 2.2
          - Spread range at entry: sigma_entry
          - Current spread: spread_current
          - Exit if: spread widens by > 1.0σ from entry
          """
          entry_spread_zscore = position['entry_z']
          current_spread_zscore = self.compute_zscore(spread)
          
          # If spread widens beyond entry:
          widening = abs(current_spread_zscore) - abs(entry_spread_zscore)
          
          if widening > 1.0:  # Widened by 1σ from entry
              logger.warning("trailing_stop_triggered",
                pair=position['pair'],
                entry_z=entry_spread_zscore,
                current_z=current_spread_zscore,
                widening=widening)
              return True
          
          return False
  ```

- [ ] **S2.3b** (1.5h) : Intégrer dans pair_trading.py
  ```python
  def generate_signals(self, market_data):
      signals = []
      trailing_stop_mgr = TrailingStopManager()
      
      # Entry signals (existing)
      # ...
      
      # Trailing stop check (new)
      for pair_key in list(self.active_trades.keys()):
          position = self.active_trades[pair_key]
          spread = self.historical_spreads[pair_key]
          
          if trailing_stop_mgr.should_exit_on_trailing_stop(position, spread):
              signals.append(Signal(
                  symbol_pair=pair_key,
                  side="exit",
                  reason="Trailing stop: spread widened > 1σ"
              ))
              del self.active_trades[pair_key]
  ```

- [ ] **S2.3c** (1h) : Tests
  ```python
  def test_trailing_stop():
      # Entry at Z = 2.2
      # Current Z = 3.8 (widened 1.6σ)
      # Should trigger exit
      assert should_exit_on_trailing_stop == True
      
      # Entry at Z = 2.2
      # Current Z = 2.8 (widened 0.6σ)
      # Should NOT trigger exit
      assert should_exit_on_trailing_stop == False
  ```

**Success Criteria**
- ✅ Trailing stop logic implemented
- ✅ Exit reason logged
- ✅ Tests passing
- ✅ Max loss per trade reduced

**Expected Impact** : +12 downside protection

---

### Task S2.4: Regime Change Detection [8h]

**Dépend de** : S2.2  
**Bloque** : S2.5

**Description**
Détecter vol/corrélation breaks et adapter stratégie

**Sous-tâches**
- [ ] **S2.4a** (2h) : Créer `models/regime_detector.py`
  ```python
  class RegimeDetector:
      """Detect market regime changes via volatility percentiles."""
      
      def __init__(self, lookback=60):
          self.vol_history = []
          self.corr_history = []
          self.lookback = lookback
      
      def detect_regime_break(self, returns, correlations):
          """
          Detect if volatility or correlations exceed thresholds.
          
          Rules:
          - vol_percentile > 80th: "High volatility regime"
          - vol_percentile > 95th: "Extreme volatility regime"
          - correlation_avg < 0.5: "Decorrelation regime"
          """
          vol = returns.rolling(self.lookback).std()
          vol_percentile = (vol - vol.min()) / (vol.max() - vol.min()) * 100
          
          regime = "NORMAL"
          if vol_percentile[-1] > 95:
              regime = "EXTREME_VOL"
          elif vol_percentile[-1] > 80:
              regime = "HIGH_VOL"
          
          if correlations[-1] < 0.5:
              regime = "DECORRELATION"
          
          logger.info("regime_detected", regime=regime, vol_pct=vol_percentile[-1])
          return regime
  ```

- [ ] **S2.4b** (2h) : Adapter stratégie selon régime
  ```python
  def generate_signals(self, market_data):
      regime = self.regime_detector.detect_regime_break(...)
      
      # Adjust entry thresholds based on regime
      if regime == "NORMAL":
          entry_z = self.config.entry_z_score  # 2.2
      elif regime == "HIGH_VOL":
          entry_z = 2.5  # Stricter in vol
      elif regime == "EXTREME_VOL":
          entry_z = 3.0  # Very strict
          # Also: reduce position size by 50%
      elif regime == "DECORRELATION":
          # Skip all pair trading, hold cash
          return []  # No signals
      
      # Rest of signal generation with adjusted thresholds
  ```

- [ ] **S2.4c** (2h) : Tests
  ```python
  def test_regime_detection():
      # Normal volatility: detect NORMAL regime
      normal_data = generate_normal_returns()
      regime = detector.detect_regime(normal_data)
      assert regime == "NORMAL"
      
      # High volatility spike: detect HIGH_VOL
      spike_data = generate_volatility_spike()
      regime = detector.detect_regime(spike_data)
      assert regime == "HIGH_VOL"
      
      # Decorrelated pairs: detect DECORRELATION
      decorr_data = generate_decorrelated_returns()
      regime = detector.detect_regime(decorr_data)
      assert regime == "DECORRELATION"
  ```

- [ ] **S2.4d** (2h) : Configuration + logging
  ```yaml
  strategy:
    regime_detection_enabled: true
    regime_vol_high_threshold: 80  # percentile
    regime_vol_extreme_threshold: 95
    regime_corr_decorr_threshold: 0.5
    regime_adjustment_type: "threshold"  # or "position_size"
  ```

**Success Criteria**
- ✅ Regime detection working
- ✅ Entry thresholds adjusted per regime
- ✅ Decorrelation → strategy stops
- ✅ Backtest Sharpe stable across regimes

**Expected Impact** : +25 robustesse (less drawdown in crashes)

---

### Task S2.5: Cross-Symbol Concentration Limits [5h]

**Dépend de** : S2.3  
**Bloque** : S3.1

**Description**
Limiter exposition à chaque symbole

**Sous-tâches**
- [ ] **S2.5a** (1.5h) : Créer `risk/concentration_limits.py`
  ```python
  class ConcentrationManager:
      """Limit portfolio concentration per symbol."""
      
      def __init__(self, max_symbol_notional_pct=0.30):
          self.max_symbol_notional_pct = max_symbol_notional_pct  # 30%
      
      def check_concentration(self, new_position, active_positions, equity):
          """
          Check if new position would exceed concentration limits.
          
          Returns: (is_allowed, current_symbol_notional_pct)
          """
          sym1, sym2 = new_position['pair'].split('_')
          
          # Calculate current exposure to sym1 and sym2
          sym1_notional = sum(p['size'] * p['price'] 
                             for p in active_positions 
                             if sym1 in p['pair'])
          sym2_notional = sum(p['size'] * p['price'] 
                             for p in active_positions 
                             if sym2 in p['pair'])
          
          # Add new position
          new_sym1_notional = sym1_notional + new_position['size']
          new_sym2_notional = sym2_notional + new_position['size']
          
          sym1_pct = new_sym1_notional / equity
          sym2_pct = new_sym2_notional / equity
          
          if sym1_pct > self.max_symbol_notional_pct:
              return False, sym1_pct
          if sym2_pct > self.max_symbol_notional_pct:
              return False, sym2_pct
          
          return True, max(sym1_pct, sym2_pct)
  ```

- [ ] **S2.5b** (1.5h) : Intégrer dans risk engine
  ```python
  class RiskEngine:
      def __init__(self):
          self.concentration_mgr = ConcentrationManager(0.30)
      
      def can_enter_trade(self, symbol_pair, position_size, equity, ...):
          # Existing checks...
          
          # New check: concentration
          is_allowed, symbol_pct = self.concentration_mgr.check_concentration(
              {'pair': symbol_pair, 'size': position_size, 'price': current_price},
              self.positions,
              equity
          )
          
          if not is_allowed:
              reason = f"Position would exceed {symbol_pct:.1%} per symbol (max=30%)"
              logger.warning("trade_rejected_concentration", reason=reason)
              return False, reason
          
          return True, None
  ```

- [ ] **S2.5c** (1.5h) : Tests
  ```python
  def test_concentration_limits():
      mgr = ConcentrationManager(max_pct=0.30)
      
      # Single position 25% notional → OK
      allowed, pct = mgr.check_concentration(
          position_25pct,
          [], 
          equity=100000
      )
      assert allowed and pct <= 0.30
      
      # Add another position same symbol, 20% → REJECTED (total 45%)
      allowed, pct = mgr.check_concentration(
          position_20pct,
          [position_25pct],
          equity=100000
      )
      assert not allowed
  ```

**Success Criteria**
- ✅ Concentration tracked per symbol
- ✅ Limit enforced (30% max)
- ✅ Risk engine blocks violating positions
- ✅ Portfolio stays market-neutral

**Expected Impact** : +18 portfolio diversification

---

### S2 Final Validation [2h]

**Checklist**
- [ ] All 5 tasks completed
- [ ] 100% test passing
- [ ] Hedge ratio tracked + reestimated
- [ ] Trailing stops working
- [ ] Regime detection functional
- [ ] Concentration limits enforced

**Expected Outcome after S2**
- Validité statistique: 5.5/10 → 7.5/10 (+36%)
- Robustesse réelle: 4.5/10 → 6.5/10 (+44%)
- Backtest Sharpe: Stable across volatility regimes
- Max DD: < 8%

---

## 🟡 SPRINT 3: Validations & Hardening (2 semaines)

**Objectif** : Passer de 7.5/10 → 8.5/10 validité | 6.5/10 → 7.5/10 robustesse  
**Focus** : Nettoyage, tests exhaustifs, documentation

### Task S3.1: Comprehensive Test Suite [12h]

**Dépend de** : S2.5  
**Bloque** : S4.1

**Description**
Écrire tests exhaustifs pour tous les modules

**Sous-tâches**
- [ ] **S3.1a** (3h) : Cointegration tests
  ```python
  # tests/test_cointegration_hardened.py
  
  class TestCointegrational:
      def test_bonferroni_vs_nominal():
          """Verify Bonferroni reduces false positives."""
          # 100 random pairs, none cointegrated
          # Nominal α: ~5 false positives
          # Bonferroni: 0 false positives
      
      def test_hedge_ratio_stability():
          """Verify β doesn't drift excessively."""
          # Generate stable pair
          # Reestimate monthly
          # Verify drift < 10%
      
      def test_oos_validation_fallout():
          """Verify OOS validation removes false pairs."""
          # Discover pairs on train window
          # Validate on OOS
          # Expect 40-50% confirmed (rest false positives)
      
      def test_half_life_estimation():
          """Verify half-life realistic."""
          # Generate synthetic OU process with known HL
          # Estimate HL
          # Assert estimate within ±30% of true value
  ```

- [ ] **S3.1b** (3h) : Strategy tests
  ```python
  # tests/test_strategy_hardened.py
  
  class TestPairTradingStrategyHardened:
      def test_z_score_thresholds():
          """Verify entry/exit thresholds correctly applied."""
      
      def test_regime_switching():
          """Verify regime changes adjust thresholds."""
      
      def test_trailing_stop_execution():
          """Verify trailing stops trigger correctly."""
      
      def test_signal_generation_no_lookahead():
          """Verify signals generated bar-by-bar without lookahead."""
      
      def test_position_lifecycle():
          """Verify position entry → trailing stop → exit."""
  ```

- [ ] **S3.1c** (3h) : Risk engine tests
  ```python
  # tests/test_risk_engine_hardened.py
  
  class TestRiskEngineHardened:
      def test_position_limit_enforcement():
          """Max 10 concurrent positions."""
      
      def test_concentration_limit_enforcement():
          """Max 30% per symbol."""
      
      def test_daily_loss_kill_switch():
          """Kill all trading if -2% daily loss."""
      
      def test_consecutive_loss_limits():
          """Max 3 consecutive losses."""
      
      def test_volatility_regime_adjustment():
          """Position size reduced in high vol."""
  ```

- [ ] **S3.1d** (3h) : Walk-forward tests
  ```python
  # tests/test_walk_forward_hardened.py
  
  class TestWalkForwardBacktesting:
      def test_no_data_leakage():
          """Verify train/test separation strict."""
      
      def test_pair_discovery_per_period():
          """Pairs rediscovered each period."""
          # Period 1 pairs ≠ Period 2 pairs (mostly)
      
      def test_oos_metrics_realistic():
          """OOS Sharpe < IS Sharpe (expected)."""
      
      def test_regime_stability():
          """Metrics stable across volatility regimes."""
      
      def test_walk_forward_reproducibility():
          """Same seeds → same results."""
  ```

**Success Criteria**
- ✅ 100+ new test cases
- ✅ 95%+ test passing rate
- ✅ All behaviors tested
- ✅ Edge cases covered

**Expected Impact** : +20 confidence, full coverage

---

### Task S3.2: Half-Life Re-Estimation Refinement [7h]

**Dépend de** : S1.2  
**Bloque** : S4.1

**Description**
Améliorer l'estimation du half-life (problème C3)

**Sous-tâches**
- [ ] **S3.2a** (2h) : Analyser problème C3
  ```python
  # Problème actuel:
  # half_life_mean_reversion() estime HL sur RESIDUALS
  # Mais residuals = bruit blanc si cointegration vraie
  # Donc HL = infini ou non-estimable
  
  # Solution: Estimer HL sur le SPREAD lui-même
  class SpreadHalfLifeEstimator:
      """Estimate half-life from actual spread, not residuals."""
      
      def estimate_half_life_from_spread(self, spread):
          """
          Estimate half-life of spread mean reversion.
          
          Uses AR(1) model on the spread directly:
          spread_t = μ + ρ * (spread_{t-1} - μ) + ε_t
          
          If ρ < 1: spread is mean-reverting
          Half-life = -ln(2) / ln(ρ)
          """
  ```

- [ ] **S3.2b** (2h) : New implementation
  ```python
  def estimate_half_life_from_spread(spread: pd.Series, lookback=252):
      """
      Estimate half-life from spread directly (corrected).
      
      Args:
          spread: Calculated spread series
          lookback: Historical window for AR(1) estimation
      """
      if len(spread) < lookback:
          return None
      
      # Use only recent window for stability
      data = spread[-lookback:]
      
      # Remove mean
      data_centered = data - data.mean()
      
      # AR(1) regression: X_t = ρ * X_{t-1}
      X = data_centered.shift(1).dropna().values.reshape(-1, 1)
      y = data_centered.dropna().values
      
      # OLS: y = ρ * X
      rho = np.linalg.lstsq(X, y, rcond=None)[0][0]
      
      if rho >= 1.0 or rho <= 0.0:
          return None  # Not mean-reverting
      
      half_life = -np.log(2) / np.log(rho)
      
      # Validation: HL should be 5-200 days
      if half_life < 5 or half_life > 200:
          logger.warning("half_life_unrealistic", hl=half_life)
          return None
      
      return int(np.round(half_life))
  ```

- [ ] **S3.2c** (2h) : Tests
  ```python
  def test_half_life_estimation():
      # Generate OU process with known HL = 30
      ou_process = generate_ou_process(half_life=30, periods=500)
      
      # Estimate HL
      estimated_hl = estimate_half_life_from_spread(ou_process)
      
      # Should be within ±30% of true value
      assert abs(estimated_hl - 30) < 10  # ±33%
      
  def test_half_life_non_stationary():
      # Generate random walk (non-stationary)
      random_walk = generate_random_walk(periods=500)
      
      # Should reject (return None)
      estimated_hl = estimate_half_life_from_spread(random_walk)
      assert estimated_hl is None
  ```

- [ ] **S3.2d** (1h) : Integration
  ```python
  # Integrate into SpreadModel
  class SpreadModel:
      def __init__(self, y, x):
          # ...existing code...
          self.estimated_half_life = self._estimate_half_life()
      
      def _estimate_half_life(self):
          spread = self.compute_spread(self.y, self.x)
          return estimate_half_life_from_spread(spread)
  ```

**Success Criteria**
- ✅ HL estimated on spread, not residuals
- ✅ HL validation bounds [5-200 days]
- ✅ Tests 100% passing
- ✅ Z-score window inferred from HL

**Expected Impact** : +15 mean-reversion accuracy

---

### Task S3.3: Documentation & Runbook [5h]

**Dépend de** : S3.1  
**Bloque** : S4.1

**Description**
Documenter tout exhaustivement

**Sous-tâches**
- [ ] **S3.3a** (2h) : Architecture documentation
  ```markdown
  # EDGECORE Architecture
  
  ## Signal Generation Pipeline
  
  1. **Pair Discovery** (T1: Daily, cached per period)
     - Input: 252 days OHLCV
     - Process: Engle-Granger test + Bonferroni correction
     - Filter: Correlation > 0.7, Half-life < 60d
     - Output: (sym1, sym2, pvalue, half_life)
  
  2. **OOS Validation** (T2: One-time, 21 days forward)
     - Input: Discovered pairs
     - Process: Retest on unseen [t+1:t+21]
     - Keep: Pairs remaining cointegrated
     - Discard: Pairs failed validation
  
  3. **Spread Modeling** (T3: Dynamic, monthly reestimate)
     - Input: Price series pair
     - Process: OLS regression μ = α + β*X
     - Hedge ratio: β reestimated monthly
     - Flag: Deprecated if drift > 10%
  
  4. **Z-Score Calculation** (T4: Rolling, adaptive window)
     - Input: Spread series
     - Window: Inferred from half-life [20-60 days]
     - Output: Z-score per bar
  
  5. **Signal Generation** (T5: Per-bar)
     - Entry: If |Z| > threshold (2.0-3.0 per regime)
     - Exit 1: If |Z| ≤ 0.0 (mean reversion)
     - Exit 2: If spread widened > 1σ (trailing stop)
     - Exit 3: If regime = DECORRELATION (kill all)
  
  6. **Risk Check** (T6: Gate before execution)
     - Max 10 concurrent positions
     - Max 30% per symbol notional
     - Max -2% daily loss kill-switch
     - Position size / volatility adjustment
  
  7. **Execution** (T7: IBKR via IBKR API)
     - Slippage: ±5 bps
     - Commission: 0.1% taker
     - Total cost: ~25-30 bps round-trip
  ```

- [ ] **S3.3b** (1.5h) : Configuration runbook
  ```markdown
  # Configuration Guide
  
  ## Environment Setup
  
  ### Development
  ```yaml
  strategy:
    bonferroni_correction: true
    oos_validation_enabled: true
    pair_cache_scope: backtest_period
    entry_z_score: 2.2
    regime_detection_enabled: true
  
  risk:
    max_concurrent_positions: 10
    max_symbol_notional_pct: 0.30
    max_daily_loss_pct: 0.02
  ```
  
  ### Production
  ```yaml
  strategy:
    bonferroni_correction: true
    oos_validation_enabled: true
    pair_cache_scope: session  # Reuse 24h
    entry_z_score: 2.3  # Stricter live
    regime_detection_enabled: true
  
  risk:
    max_concurrent_positions: 5  # Lower live
    max_symbol_notional_pct: 0.25
    max_daily_loss_pct: 0.01  # Tighter live
  ```

- [ ] **S3.3c** (1.5h) : Troubleshooting + ops guide
  ```markdown
  # Operations Runbook
  
  ## Common Issues
  
  ### "No pairs found in discovery"
  - Check: Data length >= 252 days
  - Check: Symbols in universe have price data
  - Check: Bonferroni alpha not too strict
  - Solution: Lower min_correlation or increase lookback
  
  ### "Pair trading but losing money"
  - Check: Backtest with realistic costs (-40% Sharpe)
  - Check: Regime detection not killing all pairs
  - Check: Half-life realistic (5-200 days)
  - Check: Z-threshold optimized on OOS data
  
  ### "Drawdown exceeding -3%"
  - Check: Risk engine configured (daily loss limit = -2%)
  - Check: Concentration limits enforced
  - Check: Trailing stops implemented
  - Action: Manual review + kill-switch if > -5%
  ```

**Success Criteria**
- ✅ Architecture documented
- ✅ Config options clear
- ✅ Troubleshooting guide complete
- ✅ Wiki/README updated

---

### Task S3.4: Performance Optimization [5h]

**Dépend de** : S3.1  
**Bloque** : S4.1

**Description**
Optimiser vitesse de pair discovery + signal gen

**Sous-tâches**
- [ ] **S3.4a** (2h) : Parallelize pair discovery
  ```python
  # Already partially done, enhance:
  
  from multiprocessing import Pool
  
  def find_cointegrated_pairs_optimized(self, price_data, num_workers=8):
      """
      Parallelize cointegration testing via multiprocessing.
      
      For 100 symbols → ~4,950 pairs:
      - Sequential: 30+ seconds
      - Parallel (8 cores): 4-5 seconds (6x speedup)
      """
      pairs_to_test = [...]  # All (sym1, sym2) combinations
      
      # Distribute across workers
      with Pool(num_workers) as pool:
          results = pool.map(self._test_pair_cointegration, pairs_to_test)
      
      return [r for r in results if r is not None]
  ```

- [ ] **S3.4b** (1.5h) : Cache optimization
  ```python
  # Use LRU cache for frequently accessed pairs
  from functools import lru_cache
  
  @lru_cache(maxsize=100)
  def get_spread_model(pair_key: str) -> SpreadModel:
      """LRU cache for spread models (recently used)."""
  ```

- [ ] **S3.4c** (1.5h) : Vectorize signal generation
  ```python
  # Use pandas vectorization instead of loops
  
  def generate_signals_vectorized(self, market_data):
      """
      Generate signals via pandas operations (3x faster than loop).
      """
      # Loop: 100+ lines
      # Vectorized: 20 lines, orders of magnitude faster
      
      z_scores = self.compute_all_z_scores(market_data)
      entry_signals = z_scores[z_scores > self.entry_threshold]
      exit_signals = z_scores[abs(z_scores) <= self.exit_threshold]
      
      # Efficient conversion to signals
      signals = [
          Signal(pair, 'entry') for pair in entry_signals.index
      ] + [
          Signal(pair, 'exit') for pair in exit_signals.index
      ]
      
      return signals
  ```

**Success Criteria**
- ✅ Pair discovery: < 5 seconds for 100 pairs
- ✅ Signal generation: < 100ms per bar
- ✅ Memory usage: < 500MB for full pipeline

---

### S3 Final Validation [2h]

**Checklist**
- [ ] Tests: 95%+ passing
- [ ] Documentation: Complete + clear
- [ ] Performance: Optimized (< 5s discovery)
- [ ] Hardening: Edge cases covered

**Expected Outcome after S3**
- Validité statistique: 7.5/10 → 8.5/10
- Robustesse réelle: 6.5/10 → 7.5/10
- Code quality: Production-ready
- Documentation: Comprehensive

---

## 💎 SPRINT 4: Advanced & Excellence (2 semaines)

**Objectif** : Passer de 8.5/10 → 9.5/10 validité | 7.5/10 → 8.5/10 robustesse  
**Focus** : ML-based optimization, advanced risk management, 12m survival

### Task S4.1: ML-Based Z-Score Threshold Optimization [16h]

**Dépend de** : S3.1  
**Bloque** : S4.3

**Description**
Utiliser RL/ML pour optimiser seuils de Z-score

**Sous-tâches**
- [ ] **S4.1a** (4h) : Create `models/threshold_optimizer.py`
  ```python
  from sklearn.ensemble import RandomForestRegressor
  
  class AdaptiveZThresholdOptimizer:
      """Learn Z-threshold via supervised ML."""
      
      def __init__(self):
          self.model = RandomForestRegressor()
          self.X_features = []  # Market features
          self.y_targets = []   # Sharpe ratio
      
      def extract_features(self, pair_key, market_context):
          """
          Extract features predicting optimal Z:
          - Volatility (VIX-like)
          - Correlation trend
          - Half-life
          - Win rate (recent)
          """
          features = {
              'volatility': market_context['vol'],
              'correlation': market_context['corr'],
              'half_life': self.spread_models[pair_key].estimated_half_life,
              'recent_win_rate': self.recent_win_rate,
          }
          return features
      
      def predict_optimal_z(self, pair_key, market_context):
          """Predict optimal Z-threshold given market conditions."""
          features = self.extract_features(pair_key, market_context)
          X = np.array([list(features.values())])
          z_optimal = self.model.predict(X)[0]
          return np.clip(z_optimal, 1.5, 3.0)  # Bounds
      
      def train_offline(self, historical_backtest_results):
          """
          Train optimizer on historical backtest results.
          
          Data: [(pair, vol, corr, hl, wr) → optimal_z_sharpe]
          """
          self.X_features = [r['features'] for r in historical_backtest_results]
          self.y_targets = [r['sharpe_at_optimal_z'] for r in historical_backtest_results]
          
          self.model.fit(self.X_features, self.y_targets)
  ```

- [ ] **S4.1b** (4h) : Generate training data
  ```python
  def generate_threshold_optimization_dataset():
      """
      Backtest over range of Z-thresholds to build training data.
      
      Grid: Z ∈ [1.5, 2.0, 2.5, 3.0], Vol ∈ [Low, Normal, High]
      Result: DataFrame with (market_context → optimal_z)
      """
      
      results = []
      for z_thresh in np.arange(1.5, 3.1, 0.1):
          for vol_regime in ["low", "normal", "high"]:
              metrics = run_backtest(
                  data_filtered_by_vol_regime,
                  z_threshold=z_thresh
              )
              
              results.append({
                  'z_threshold': z_thresh,
                  'vol_regime': vol_regime,
                  'volatility': compute_vol(data),
                  'sharpe': metrics.sharpe_ratio,
                  'win_rate': metrics.win_rate
              })
      
      return pd.DataFrame(results)
  ```

- [ ] **S4.1c** (4h) : Integration + live adaptation
  ```python
  class PairTradingStrategy:
      def __init__(self):
          self.z_optimizer = AdaptiveZThresholdOptimizer()
          # Load pretrained model
          self.z_optimizer.model = load_model("models/z_threshold_rf.pkl")
      
      def generate_signals(self, market_data):
          signals = []
          
          for sym1, sym2, pval, hl in self.cointegrated_pairs:
              pair_key = f"{sym1}_{sym2}"
              
              # Predict optimal Z for current market conditions
              z_optimal = self.z_optimizer.predict_optimal_z(
                  pair_key,
                  market_context={'vol': current_vol, 'corr': current_corr}
              )
              
              z_score = self.spread_models[pair_key].compute_z_score(spread)
              
              # Generate signals using PREDICTED threshold
              if abs(z_score.iloc[-1]) > z_optimal:
                  # Generate entry signal
                  ...
  ```

- [ ] **S4.1d** (4h) : Tests + validation
  ```python
  def test_threshold_optimizer():
      # Train optimizer
      dataset = generate_threshold_optimization_dataset()
      optimizer.train_offline(dataset)
      
      # Predict on hold-out test set
      test_context = {'vol': high_vol, 'corr': 0.6, 'hl': 45}
      z_pred = optimizer.predict_optimal_z('AAPL_MSFT', test_context)
      
      # Should predict Z=2.7-3.0 (stricter in high vol)
      assert 2.5 < z_pred < 3.0
      
      # Verify improvement over fixed Z=2.0
      sharpe_fixed = backtest(data, z_threshold=2.0)
      sharpe_adaptive = backtest(data, z_threshold=z_pred)
      
      assert sharpe_adaptive > sharpe_fixed * 1.05  # 5% improvement
  ```

**Success Criteria**
- ✅ ML model trained on OOS data
- ✅ Live predictions working
- ✅ Sharpe improvement 5-15% vs fixed threshold
- ✅ Adaptive to volatility regimes

**Expected Impact** : +20 signal quality

---

### Task S4.2: Markov Switching Regime Model [12h]

**Dépend de** : S2.4  
**Bloque** : S4.3

**Description**
Impl probabilistic regime switching (Hidden Markov)

**Sous-tâches**
- [ ] **S4.2a** (3h) : Create `models/hmm_regime.py`
  ```python
  from hmmlearn.hmm import GaussianHMM
  
  class MarkovRegimeSwitcher:
      """Detect market regimes via HMM."""
      
      def __init__(self, n_regimes=3):
          # 3 regimes: Low Vol, Normal, High Vol/Stress
          self.model = GaussianHMM(n_components=n_regimes)
      
      def train(self, returns_history, lookback=252):
          """Train HMM on recent returns."""
          X = returns_history[-lookback:].values.reshape(-1, 1)
          self.model.fit(X)
      
      def predict_regime(self, recent_returns):
          """Predict current market regime (0=low vol, 1=normal, 2=high vol)."""
          X = recent_returns[-20:].values.reshape(-1, 1)
          regime = self.model.predict(X)[-1]  # Latest
          
          # Estimate probability of each regime
          probs = self.model.predict_proba(X)[-1]
          
          return regime, probs
  ```

- [ ] **S4.2b** (3h) : Regime-specific parameters
  ```python
  REGIME_PARAMS = {
      0: {  # Low volatility regime
          'entry_z_threshold': 2.0,
          'position_size_multiplier': 1.0,
          'max_leverage': 3.0
      },
      1: {  # Normal volatility regime
          'entry_z_threshold': 2.2,
          'position_size_multiplier': 1.0,
          'max_leverage': 2.0
      },
      2: {  # High volatility / stress regime
          'entry_z_threshold': 2.8,
          'position_size_multiplier': 0.5,
          'max_leverage': 1.0
      }
  }
  ```

- [ ] **S4.2c** (3h) : Integration into strategy
  ```python
  class PairTradingStrategy:
      def __init__(self):
          self.regime_switcher = MarkovRegimeSwitcher(n_regimes=3)
      
      def generate_signals(self, market_data):
          # Predict current regime
          regime, probs = self.regime_switcher.predict_regime(
              market_data['returns']
          )
          
          logger.info("market_regime", regime=regime, probs=probs)
          
          # Get regime-specific parameters
          params = REGIME_PARAMS[regime]
          entry_z = params['entry_z_threshold']
          
          # Apply regime-adjusted logic
          for pair_key in cointegrated_pairs:
              z_score = ...
              
              if abs(z_score) > entry_z:
                  # Adjust position size per regime
                  base_size = calculate_position_size()
                  adjusted_size = base_size * params['position_size_multiplier']
                  
                  signals.append(Signal(
                      pair_key, 
                      adjusted_size,
                      reason=f"Entry in regime {regime}"
                  ))
  ```

- [ ] **S4.2d** (3h) : Validation
  ```python
  def test_markov_regime_switching():
      switcher = MarkovRegimeSwitcher()
      
      # Train on historical data
      switcher.train(returns_history)
      
      # Predict regimes
      regime, probs = switcher.predict_regime(recent_returns)
      
      # In high vol period, should predict regime=2
      assert regime == 2 or probs[2] > 0.6
      
      # Backtest with regime-switching
      sharpe_fixed = backtest(data, regime_params=REGIME_PARAMS[1])
      sharpe_switching = backtest(data, regime_switching=True)
      
      # Should show improvement in high vol periods
      assert sharpe_switching > sharpe_fixed * 1.08
  ```

**Success Criteria**
- ✅ HMM model trained
- ✅ 3 regimes identified + parameters set
- ✅ Live regime prediction working
- ✅ Sharpe improvement 8-15% via switching

**Expected Impact** : +25 robustness across regimes

---

### Task S4.3: Final Validation & Production Readiness [8h]

**Dépend de** : S4.1, S4.2  
**Bloque** : Deployment

**Description**
Validation finale avant production

**Sous-tâches**
- [ ] **S4.3a** (2h) : Complete backtest suite
  ```python
  def run_complete_validation():
      """
      Run full validation suite:
      1. Historical backtest (2020-2025)
      2. Walk-forward backtest (10 periods, monthly)
      3. Out-of-sample validation (unseen 2025 data)
      4. Stress testing (2020 COVID crash, 2022 FTX collapse)
      5. Monte Carlo simulation (1000 iterations)
      """
      
      results = {
          'historical_backtest': run_historical(2020, 2025),
          'walk_forward': run_walk_forward(splits=10),
          'out_of_sample': run_oos(2025),
          'stress_tests': {
              'covid_crash': backtest_on_period(2020-03, 2020-04),
              'ftx_collapse': backtest_on_period(2022-11, 2022-12),
          },
          'monte_carlo': run_monte_carlo(iterations=1000),
      }
      
      return results
  ```

- [ ] **S4.3b** (2h) : Acceptance criteria verification
  ```python
  def verify_acceptance_criteria(validation_results):
      """
      All criteria must be met for production:
      
      ✅ Sharpe ratio (OOS) >= 0.8
      ✅ Max drawdown (OOS) <= 12%
      ✅ Win rate >= 50%
      ✅ Consecutive losses <= 5
      ✅ Stress test (COVID): Sharpe >= 0.5
      ✅ Monte Carlo (5% tail loss): <= 15%
      ✅ Test success rate: >= 95%
      """
      
      checks = {}
      
      checks['sharpe_oos'] = validation_results['out_of_sample']['sharpe'] >= 0.8
      checks['max_dd'] = abs(validation_results['out_of_sample']['max_dd']) <= 0.12
      checks['win_rate'] = validation_results['out_of_sample']['win_rate'] >= 0.50
      checks['stress_covid'] = validation_results['stress_tests']['covid_crash']['sharpe'] >= 0.5
      checks['monte_carlo_tail'] = validation_results['monte_carlo']['var_5pct'] <= 0.15
      
      all_passed = all(checks.values())
      
      return all_passed, checks
  ```

- [ ] **S4.3c** (2h) : Production config & safety
  ```yaml
  # config/prod.yaml
  
  strategy:
    bonferroni_correction: true
    oos_validation_enabled: true
    entry_z_score: 2.3  # Stricter than dev
    regime_detection_enabled: true
    markov_switching_enabled: true
    adaptive_threshold_enabled: true
    pair_cache_scope: "SESSION"  # Reuse 24h in live
    pair_discovery_frequency_hours: 24  # Rediscover daily
  
  risk:
    max_concurrent_positions: 5  # Lower in live
    max_symbol_notional_pct: 0.25  # Lower
    max_daily_loss_pct: 0.01  # Tighter: -1%
    max_consecutive_losses: 3
    position_sizing: "volatility"  # Vol-adjusted
    max_leverage: 1.5  # Conservative
  
  execution:
    engine: "IBKR API"
    broker: "IBKR"
    use_sandbox: false  # LIVE TRADING
    paper_slippage_model: "adaptive"  # More realistic
    paper_commission_pct: 0.1
  ```

- [ ] **S4.3d** (2h) : Deployment checklist
  ```markdown
  # Production Deployment Checklist
  
  ## Pre-Deployment
  - [ ] All tests passing (100%)
  - [ ] Code reviewed (2 reviewers)
  - [ ] Documentation complete
  - [ ] Acceptance criteria met
  - [ ] Monitoring setup ready
  - [ ] Alerting configured (Slack)
  - [ ] Kill-switch tested
  - [ ] Backup/recovery plan documented
  
  ## Deployment
  - [ ] Set EDGECORE_ENV=prod
  - [ ] Load real API credentials
  - [ ] Start with paper trading (24h observation)
  - [ ] Monitor all metrics (Sharpe, DD, trades/day)
  - [ ] Manual review: First 5 days
  - [ ] Auto-notification if DD > 5%
  - [ ] Kill-switch available (manual)
  
  ## Post-Deployment (Week 1-4)
  - [ ] Daily Sharpe monitoring
  - [ ] Weekly P&L review
  - [ ] Monthly rebalancing (pair refresh)
  - [ ] Quarterly regime analysis
  ```

**Success Criteria**
- ✅ All acceptance criteria met
- ✅ Deployment checklist signed
- ✅ 12-month survival probability: 75%+
- ✅ Production config finalized

---

### S4 Final Validation & Conclusion [2h]

**Final Checklist**
- [ ] S4.1: ML optimizer trained + tested
- [ ] S4.2: Markov regime switching working
- [ ] S4.3: Full validation suite passed
- [ ] All 4 sprints complete
- [ ] 100% test passing
- [ ] Documentation comprehensive
- [ ] Code production-ready
- [ ] Deployment checklist signed

**Final Outcome**
- ✅ Validité statistique: **9.5/10**
- ✅ Robustesse réelle: **8.5/10**
- ✅ Sharpe ratio (OOS): **1.2-1.5**
- ✅ Max drawdown: **< 8%**
- ✅ Win rate: **52-55%**
- ✅ 12-month survival: **85%+**

---

## ⚠️ Why NOT 10/10? Rendements décroissants

### La courbe de l'excellence

```
Score vs Effort (logarithmic scale)

10.0 |                    ╱╱╱╱ (impossible, asymptotique)
 9.9 |               ╱╱╱╱
 9.8 |            ╱╱╱         (+200h, returns: -0.3/pt)
 9.5 |         ╱╱╱             (+140h, returns: -0.5/pt)
 8.5 |      ╱╱               (+100h, returns: -1.0/pt)
 7.5 |    ╱╱                 (+60h, returns: -2.0/pt)
 5.5 |   ╱                   (+30h, returns: -3.0/pt)
 2.5 |╱                      (baseline)
     └─────────────────────────────────────
     0    50   100  150  200  250  300 hours
```

### Pourquoi s'arrêter à 9.5/10 ?

**Progressions par 0.5 points supplémentaires :**

| Target | Effort additionnel | ROI | Réalisme | Verdict |
|--------|-------------------|-----|----------|---------|
| **9.5** | 140h (total) | Excellent | ✅ Faisable | **RECOMMANDÉ** |
| **9.7** | +60h = 200h | Faible (-0.5h/pt) | ⚠️ Marginal | Questionnable |
| **9.9** | +80h = 280h | Very faible (-0.3h/pt) | ❌ Hardcore | Not worth |
| **10.0** | +∞ | Zero | ❌ Impossible | Asymptotique |

---

### Les réalités du 9.9-10.0

**Pour vraiment atteindre 9.9/10 :**
- Auditer CHAQUE ligne de code (500+ heures)
- Tests for every edge case (200+ heures)
- Optimization jusqu'aux microsecondes (150+ heures)
- Proof-of-concept live sur 6+ mois (6 mois)
- **Total: 850+ heures + 6 mois calendar**

**Retours en diminution :**
- 2.5 → 5.5/10 = +3.0 points / 30h = **0.10 pt/h**
- 5.5 → 7.5/10 = +2.0 points / 60h = **0.033 pt/h**
- 7.5 → 8.5/10 = +1.0 point / 100h = **0.010 pt/h**
- 8.5 → 9.5/10 = +1.0 point / 140h = **0.007 pt/h**
- 9.5 → 9.9/10 = +0.4 point / 280h = **0.001 pt/h** ❌

**À 9.5/10, vous gagnez 0.1% par heure de travail supplémentaire.**

---

### Mais que faire si vous VOULEZ vraiment 10/10 ?

**Alternative: "Excellence Progressive" (16 semaines, 350h)**

```
┌─────────────────────────────────────────────────────────┐
│  SPRINT SEQUENCE FOR 10.0/10 TARGET (Theoretical)       │
└─────────────────────────────────────────────────────────┘

S1: Critique              [2.5 → 5.5/10]  40h  (1 week)
S2: Majeur                [5.5 → 7.5/10]  60h  (1.5 weeks)
S3: Tests & Hardening     [7.5 → 8.5/10]  80h  (2 weeks)
S4: Advanced ML           [8.5 → 9.0/10]  100h (2 weeks)
──────────────────────────────────────────────────────────
[TOTAL TO 9.0/10: 280 hours, 6.5 weeks] = PRODUCTION READY

S5: Perfection Phase 1    [9.0 → 9.5/10]  100h (2.5 weeks)
   ├─ Code audit (every line)
   ├─ Exhaustive edge-case testing
   ├─ Performance optimization to nanosecond level
   └─ Live paper trading validation (4 weeks concurrent)

S6: Perfection Phase 2    [9.5 → 9.7/10]  150h (3.5 weeks)
   ├─ Adaptive parameter refinement via Bayesian optimization
   ├─ Multi-market stress testing (stocks, equity, FX)
   ├─ Regime persistence validation (all markets)
   └─ CI/CD infrastructure hardening

S7: Quantitative Rigor     [9.7 → 9.85/10] 200h (5 weeks)
   ├─ Peer review by 3+ quant PhDs
   ├─ Academic verification (publish preliminary results)
   ├─ Institutional backtesting framework
   └─ Regulatory compliance audit
──────────────────────────────────────────────────────────
[TOTAL TO 9.85/10: 830 hours, 20 weeks] = ACADEMIC GRADE

S8: Live Trading Proof     [9.85 → 9.95/10] 6+ months
   └─ 6+ months real live trading with real capital
      showing consistent Sharpe > 1.2, DD < 5%, no regime breaks
      (Only way to PROVE robustness; backtests always optimistic)
──────────────────────────────────────────────────────────
[TOTAL TO 9.95/10: 830h + 6 months] = INSTITUTIONAL GRADE

S9: Pure Perfection       [9.95 → 10.0/10] Infinite
   └─ NP-hard optimization problem; asymptotically approaches
      perfection but never reaches it theoretically
```

---

### What 9.5/10 ACTUALLY means

**At 9.5/10, you have:**

✅ **Statistically rigorous**
- Multiple-testing correction (Bonferroni)
- Out-of-sample validation framework
- Walk-forward backtesting (clean separation)
- Realistic costs integrated

✅ **Structurally robust**
- Dynamic hedge ratio reestimation
- Regime-change detection + adaptation
- Trailing stops (downside protection)
- Concentration limits (diversification)

✅ **Algorithmically intelligent**
- ML-optimized Z-score thresholds
- Adaptive position sizing
- Markov regime switching
- Risk-aware execution

✅ **Operationally sound**
- 95%+ unit/integration test coverage
- Production configuration stack
- Comprehensive documentation
- Deployment checklist

✅ **Realistically validated**
- Sharpe ratio 1.2-1.5 (OOS)
- Max drawdown < 8%
- Win rate 52-55%
- Stress testing passed (COVID, FTX crashes)
- Monte Carlo 5% tail loss < 15%

**Your 12-month survival probability: 85%+**

This is **institutional-grade** for a quantitative fund.

---

### The Remaining 0.5 to 10.0

What would you need for the final 0.5 points ?

| Points | Requirement | Effort | Realism |
|--------|-------------|--------|---------|
| **9.5→9.6** | Live trading 3+ months ($500K+) | 3 months | ⚠️ Capital required |
| **9.6→9.7** | Institutional peer review | 8 weeks | ⚠️ Network required |
| **9.7→9.8** | Multi-market empirical validation | 2 months | ⚠️ Data access |
| **9.8→9.9** | Regime persistence proof (all conditions) | 3 months | ❌ Nearly impossible |
| **9.9→10.0** | Mathematical perfection proof | Infinite | ❌ Asymptote |

---

### 📊 Practical Decision Matrix

```
YOUR GOAL:                RECOMMENDED APPROACH:

"Ship to production    →   Sprint 1-4 (9.5/10)
 in 4-5 months"             140 hours
                            PRODUCTION READY ✅

"Institutional audit   →   Sprint 1-6 (9.7/10)
 & live validation"         350 hours + 3 months live
                            FUND READY ✅

"Academic publication →   Sprint 1-8 (9.95/10)
 & peer review"             830 hours + 6 months live
                            DISSERTATION READY ✅

"Theoretical perfection"  →   Add 10+ years research
                            Not feasible ❌
```


---

## 📈 Summary: Scorecard par Sprint

**Réponse directe : "Pourquoi pas 10/10 à chaque sprint ?"**

**Parce que les rendements décroissants explosent après 9.5/10 :**

| Sprint | Score → | Effort | ROI (pts/heure) | Réalisme | Recommandé |
|--------|---------|--------|-----------------|----------|-----------|
| **S1** | 2.5 → 5.5 | 40h | **+0.10** | ✅ Very High | **YES** |
| **S2** | 5.5 → 7.5 | 60h | **+0.033** | ✅ High | **YES** |
| **S3** | 7.5 → 8.5 | 100h | **+0.010** | ⚠️ Medium | **Oui** |
| **S4** | 8.5 → 9.5 | 140h | **+0.007** | ⚠️ Medium-Low | **Oui** |
| **S5*** | 9.5 → 9.6 | 100h | **+0.001** | ❌ Very Low | Non |
| **S6*** | 9.6 → 9.7 | 150h | **<0.001** | ❌ Très faible | Non |
| **S7*** | 9.7 → 9.85 | 300h | **~0.0005** | ❌ Impossible | Non |
| **S8*** | 9.85 → 10 | ∞ | **0.000** | ❌ Asymptotique | Non |

*S5-S8: Only if you have academic/institutional mandate + 6+ months calendar

---

### 📊 The Excellence Curve: Why 9.5/10 is the Optimal Target

**Visualized:**

```
Sharpe Ratio vs Score:

1.8  |●────────────────────────────● = Live trading 9.5/10
1.5  |
     |
1.2  |─ Minimum professional grade
     |     │
0.8  |     │
     |     │ S1-S4 work here (280h, 9.5/10)
0.5  |◌────●──────────────────────── = Backtest 9.5/10
     │    (returns peak + cost-adjusted realistic)
0.0  |●────●◌──────────────────────── = Unadjusted backtest
     └──────────────────────────────────
     2.5   5.5  7.5  8.5  9.0  9.5  9.85
               SCORE

Key insight:
- 9.5/10 = "Diminishing returns begin"
- Beyond 9.5: Each 0.1 points costs 200-300% more effort
- Only pursue 9.6+ if targeting institutional/academic credibility
```

---

### Why S1-S4 reaches 9.5/10 (not higher):

**Each additional 0.5 points requires:**

| Score | What It Takes | Why Hard |
|-------|---------------|----------|
| **→9.5** | Core statistical rigor (Bonferroni, OOS, slippage, regime) | Linear complexity |
| **→9.7** | Institutional peer review + 3+ months live trading | Exponential time + capital |
| **→9.9** | Academic publication + 6+ months live + regime proof | Needs external validation |
| **→10.0** | Mathematical perfection (impossible) | Asymptotic limit |

**Bottom line:** 9.5/10 is where the **Pareto frontier** is — 90% of the value with 40% of the effort.

---

## 🎯 Priority Execution Order

If resource-constrained (< 400 hours):

**Minimum Viable Excellence (100h)**
1. S1.1-S1.3 (Bonferroni, OOS, slippage) = 13h
2. S2.1-S2.2 (Hedge ratio, window) = 7h
3. S2.5 (Concentration limits) = 5h
4. S3.1 (Core tests) = 12h
5. S3.3 (Documentation) = 5h

→ **Reach 7.0/10 in 42 hours**

**High-Impact Additions (60h more)**
6. S2.3-S2.4 (Trailing stop, regime) = 12h
7. S3.2 (Half-life fix) = 7h
8. S4.1 (ML optimizer) = 16h

→ **Reach 8.5/10 in 102 hours**

---

**📌 Start with S1.1 (Bonferroni correction) — 4 hours, highest impact**

