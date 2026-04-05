# Plan d'Action — Correction Structurelle EDGECORE

**Date:** 2026-03-04  
**Contexte:** Analyse post-backtest v27 (2023-2026). 4 causes racines identifiées. Ce document décrit les corrections à appliquer étape par étape, dans l'ordre de priorité.

---

## Résumé des Causes Racines

| # | Cause | Impact mesuré |
|---|---|---|
| 1 | Mean reversion absente (7.5% success rate) | 5 time stops = **-$17,912** (55% des pertes) |
| 2 | Asymétrie long/short en bull market | Shorts 19.4% win rate = **-$21,215** |
| 3 | Aucune blacklist de paires perdantes | GE_RTX × 6 trades, 0 gagnant = **-$6,582** |
| 4 | Entry z-score trop bas (68% entre 1.5-2.0) | Signal sur bruit, pas d'edge réel |

**Verdict structurel:** La stratégie trade en mode mean-reversion dans un marché momentum-driven (S&P +50% 2024-2025). Sans filtre de régime, elle est structurellement perdante dans ce contexte.

---

## Étapes du Plan

### Étape 1 — Filtre de Régime (P0)

**Fichiers concernés:**
- `signal_engine/` — point d'injection du filtre
- `strategies/pair_trading.py` — logique de décision d'entrée
- `config/config.yaml` + `config/schemas.py` — nouveaux paramètres

**Ce qui doit être fait:**
- Implémenter un détecteur de régime basé sur 2 indicateurs combinés:
  - **Trend momentum**: spread entre SPY 50-day MA et 200-day MA (Golden/Death Cross)
  - **Volatility regime**: VIX proxy via rolling realized vol du SPY (20j)
- 3 états: `MEAN_REVERTING` (favorable), `TRENDING` (défavorable), `NEUTRAL`
- En état `TRENDING`: bloquer toutes les nouvelles entrées (ne pas fermer les positions existantes)
- En état `NEUTRAL`: réduire le sizing de 50%
- Paramètres config: `regime.ma_fast=50`, `regime.ma_slow=200`, `regime.vol_threshold=0.18`, `regime.enabled=true`

**Validation:**
- Test unitaire: le filtre classe correctement des périodes historiques connues (COVID crash, bull 2024)
- Backtest v28: même params que v27, avec filtre de régime activé → comparer PnL et nombre de trades

---

### Étape 2 — Relèvement du Seuil d'Entrée entry_z (P0)

**Fichiers concernés:**
- `config/config.yaml` — paramètre `strategy.entry_z`
- `config/schemas.py` — validation min/max
- `scripts/run_backtest_v28.py` (nouveau script de validation)

**Ce qui doit être fait:**
- Monter `entry_z` de `1.5` à `2.0` minimum
- Ajouter un paramètre `strategy.entry_z_min_spread` (écart absolu minimum en $, pas seulement z-score) pour filtrer les micro-déviations sur les paires à faible spread
- Documenter la justification: 68% des trades entrés z < 2.0, win rate de ce sous-ensemble à analyser

**Validation:**
- Backtest v28 intégré avec Étape 1
- Comparer le nombre de trades et win rate avant/après

---

### Étape 3 — Blacklist Dynamique de Paires (P1)

**Fichiers concernés:**
- `pair_selection/` — module de gestion du candidat universe
- `persistence/` — stockage de l'état de la blacklist
- `config/config.yaml` — paramètres `pair_blacklist.max_consecutive_losses`, `pair_blacklist.cooldown_days`

**Ce qui doit être fait:**
- Implémenter un compteur de pertes consécutives par paire
- Si une paire atteint `max_consecutive_losses` (défaut: 2) pertes consécutives, la mettre en cooldown pour `cooldown_days` (défaut: 30 jours calendaires)
- Stocker l'état en JSON dans `persistence/pair_blacklist_state.json` (persistant entre les runs)
- Logguer les événements `pair_blacklisted` et `pair_cooldown_expired`
- La blacklist est consultée lors du filtre d'entrée dans `pair_selection/`

**Cas d'usage ciblé:** GE_RTX aurait été blacklisté après la 2e perte, évitant 4 trades supplémentaires (-$5,386 évités).

**Validation:**
- Test unitaire: paire blacklistée après 2 pertes, réactivée après cooldown
- Backtest v28: vérifier que GE_RTX n'est pas re-tradé indéfiniment

---

### Étape 4 — Gestion du Biais Directionnel (P1)

**Fichiers concernés:**
- `strategies/pair_trading.py` — logique de sélection long/short
- `signal_engine/` — application du biais
- `config/config.yaml` — paramètre `strategy.directional_bias`

**Ce qui doit être fait:**
- Ajouter un paramètre `strategy.short_sizing_multiplier` (défaut en bull market: `0.5`, en neutral: `1.0`)
- Lier ce multiplier à l'état du régime (Étape 1): en `TRENDING` bull, réduire le sizing des shorts de 50%
- Option plus agressive (configurable): `strategy.disable_shorts_in_bull_trend = false`
- Logguer la décision de sizing ajusté avec raison

**Validation:**
- Vérifier que le sizing est effectivement réduit dans les logs de backtest
- Comparer PnL shorts avant/après dans le backtest v28

---

### Étape 5 — Resserrement du Time Stop (P2)

**Fichiers concernés:**
- `execution/position_stops.py` — logique du time stop
- `config/config.yaml` — paramètre `strategy.time_stop_multiplier`

**Ce qui doit être fait:**
- Réduire `time_stop_multiplier` de `3.0` à `2.0` (le time stop se déclenche à `2 × half_life` au lieu de `3 × half_life`)
- Justification: Les 5 time stops (moyenne 22 jours de holding) ont coûté -$17,912. Couper à 2× HL aurait déclenché la sortie ~30% plus tôt, limitant l'exposition aux spreads divergents.
- Garder le cap absolu à 60 jours inchangé

**Validation:**
- Recalculer manuellement les 5 time stops avec 2× HL vs 3× HL pour estimer l'économie
- Intégrer dans le backtest v28

---

### Étape 6 — Backtest de Validation v28 (P0 — après toutes les étapes)

**Fichier:** `scripts/run_backtest_v28.py` (nouveau)

**Paramètres v28:**
```
Période:        2023-01-01 → 2025-12-31 (même que v27)
entry_z:        2.0  (↑ de 1.5)
exit_z:         0.3
time_stop_mult: 2.0  (↓ de 3.0)
alloc:          90%
heat:           400%
fdr_q:          0.20
min_corr:       0.50
Régime:         ACTIVÉ
Blacklist:      ACTIVÉE (max 2 pertes consécutives, cooldown 30j)
Short sizing:   0.5× en bull trend
```

**Critères de succès minimum:**
- Win rate ≥ 45% (vs 35.8% en v27)
- Max drawdown ≤ 15%
- PnL net > 0 sur la période
- Time stops ≤ 2 (vs 5 en v27)
- GE_RTX: ≤ 2 trades (vs 6 en v27)

---

## Ordre d'Exécution

```
Étape 1 (Régime)  →  Étape 2 (entry_z)  →  Étape 3 (Blacklist)
                                                      ↓
                    Étape 6 (Backtest v28)  ←  Étape 4 (Biais)
                                                      ↑
                                             Étape 5 (Time stop)
```

Les étapes 1 à 5 peuvent être développées en parallèle, mais le backtest v28 (Étape 6) doit être lancé uniquement quand **toutes** les corrections sont intégrées.

---

## Décisions Architecturales

| Décision | Choix retenu | Alternative écartée | Raison |
|---|---|---|---|
| Source data régime | SPY rolling MA + realized vol (IBKR data) | VIX externe API | Cohérence avec "uniquement IBKR data" |
| Blacklist persistence | JSON file dans `persistence/` | In-memory seulement | Survivre aux redémarrages |
| Short disable vs sizing | Sizing réduit (×0.5) | Disable total shorts | Moins agressif, testable en graduel |
| Time stop: 2× vs 1.5× HL | 2× HL | 1.5× HL | 1.5× trop agressif sur les paires lentes |

---

## Périmètre Hors Plan

Les éléments suivants sont **explicitement exclus** de ce plan:
- Modification du modèle de cointegration (EG test, Kalman)
- Changement de l'universe d'actifs
- Passage à des données intra-day
- Toute utilisation de Yahoo Finance ou données synthétiques