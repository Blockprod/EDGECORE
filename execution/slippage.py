"""
<<<<<<< HEAD
Phase 0.1 ��� Mod+�le de Slippage R+�aliste (3 composantes).

Fournit une estimation du co++t de friction pour CHAQUE leg d'un pair trade,
en euros/dollars, +� partir de :

  1. **Spread bid-ask fixe** ��� demi-spread per transaction (~2 bps mega-caps US)
  2. **Market impact temporaire** (Almgren-Chriss simplifi+�)
        impact = +� +� ��_daily +� ���(Q / ADV)
        +�  : constante d'impact (~0.1 pour mega-caps)
        Q  : notionnel de l'ordre (USD)
        ADV: volume quotidien moyen (USD)
  3. **Timing cost** (incertitude d'ex+�cution intraday)
        timing = ��_daily +� ���(T_exec / 252)
        T_exec : d+�lai d'ex+�cution en jours (ex: 0.1 ��� 6 min)
=======
Phase 0.1 — Modèle de Slippage Réaliste (3 composantes).

Fournit une estimation du coût de friction pour CHAQUE leg d'un pair trade,
en euros/dollars, à partir de :

  1. **Spread bid-ask fixe** — demi-spread per transaction (~2 bps mega-caps US)
  2. **Market impact temporaire** (Almgren-Chriss simplifié)
        impact = η × σ_daily × √(Q / ADV)
        η  : constante d'impact (~0.1 pour mega-caps)
        Q  : notionnel de l'ordre (USD)
        ADV: volume quotidien moyen (USD)
  3. **Timing cost** (incertitude d'exécution intraday)
        timing = σ_daily × √(T_exec / 252)
        T_exec : délai d'exécution en jours (ex: 0.1 ≈ 6 min)
>>>>>>> origin/main

Utilisation ::

    model = SlippageModel()
    cost_usd = model.compute(notional=5_000, adv=500_000_000, sigma=0.02)
    cost_bps = model.compute_bps(notional=5_000, adv=500_000_000, sigma=0.02)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
<<<<<<< HEAD
=======
from typing import Optional
>>>>>>> origin/main

from structlog import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class SlippageConfig:
<<<<<<< HEAD
    """Param+�tres du mod+�le de slippage +� 3 composantes.

    Defaults calibr+�s pour US mega-cap equities via IBKR daily bars.
=======
    """Paramètres du modèle de slippage à 3 composantes.

    Defaults calibrés pour US mega-cap equities via IBKR daily bars.
>>>>>>> origin/main
    """

    # 1. Spread bid-ask (demi-spread par transaction, en bps)
    spread_bps: float = 2.0

<<<<<<< HEAD
    # 2. Almgren-Chriss: +� coefficient d'impact temporaire
    #    0.10 = valeur institutionnelle standard pour mega-caps US
    #    0.05 = lowercase/conservative (v31h default)
    #    0.30 = mid-caps / faible liquidit+�
    eta: float = 0.10

    # 3. D+�lai d'ex+�cution en jours de trading (pour timing cost)
    #    0.10 = ~6 minutes        (r+�aliste pour daily + IBKR Smart Order)
    #    0.25 = ~1.5 heures       (conservateur)
    #    0.50 = demi-journ+�e       (tr+�s conservateur)
    execution_delay_days: float = 0.10

    # Cap: +�viter des co++ts absurdes sur actifs illiquides
=======
    # 2. Almgren-Chriss: η coefficient d'impact temporaire
    #    0.10 = valeur institutionnelle standard pour mega-caps US
    #    0.05 = lowercase/conservative (v31h default)
    #    0.30 = mid-caps / faible liquidité
    eta: float = 0.10

    # 3. Délai d'exécution en jours de trading (pour timing cost)
    #    0.10 = ~6 minutes        (réaliste pour daily + IBKR Smart Order)
    #    0.25 = ~1.5 heures       (conservateur)
    #    0.50 = demi-journée       (très conservateur)
    execution_delay_days: float = 0.10

    # Cap: éviter des coûts absurdes sur actifs illiquides
>>>>>>> origin/main
    max_cost_bps: float = 100.0


# ---------------------------------------------------------------------------
# ADV estimates par tier de capitalisation
# ---------------------------------------------------------------------------

<<<<<<< HEAD
_ADV_MEGA_CAP = 500_000_000   # $500M/j ��� AAPL, MSFT, NVDA, GOOGL, AMZN, META, BRK
_ADV_LARGE_CAP = 150_000_000  # $150M/j ��� Most S&P 500 constituents
=======
_ADV_MEGA_CAP = 500_000_000   # $500M/j — AAPL, MSFT, NVDA, GOOGL, AMZN, META, BRK
_ADV_LARGE_CAP = 150_000_000  # $150M/j — Most S&P 500 constituents
>>>>>>> origin/main

_MEGA_CAP_SYMBOLS = frozenset({
    "AAPL", "MSFT", "NVDA", "GOOGL", "GOOG", "AMZN", "META", "BRK.B", "LLY",
    "AVGO", "TSLA", "NFLX", "JPM", "V", "MA", "UNH", "WMT", "XOM", "JNJ",
    "PG", "HD", "ORCL", "COST", "CVX", "MRK", "KO", "PEP", "ABBV", "TMO",
})


# ---------------------------------------------------------------------------
# SlippageModel
# ---------------------------------------------------------------------------

class SlippageModel:
<<<<<<< HEAD
    """Mod+�le de slippage +� 3 composantes pour backtests d'equities US.

    Chaque appel +� ``compute()`` retourne le co++t estim+� pour UNE transaction
    unidirectionnelle (un seul leg, un seul sens).  Pour un pair trade complet
    (4 transactions = 2 entr+�es + 2 sorties), multiplier par 4.

    Args:
        config: Param+�tres du mod+�le (spread, eta, d+�lai).
    """

    def __init__(self, config: SlippageConfig | None = None):
=======
    """Modèle de slippage à 3 composantes pour backtests d'equities US.

    Chaque appel à ``compute()`` retourne le coût estimé pour UNE transaction
    unidirectionnelle (un seul leg, un seul sens).  Pour un pair trade complet
    (4 transactions = 2 entrées + 2 sorties), multiplier par 4.

    Args:
        config: Paramètres du modèle (spread, eta, délai).
    """

    def __init__(self, config: Optional[SlippageConfig] = None):
>>>>>>> origin/main
        self.config = config or SlippageConfig()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compute(
        self,
        notional: float,
        adv: float = _ADV_LARGE_CAP,
        sigma: float = 0.02,
    ) -> float:
<<<<<<< HEAD
        """Retourne le co++t de slippage en USD pour UNE transaction.

        Args:
            notional: Taille de l'ordre en USD.
            adv: Volume quotidien moyen en USD (d+�faut = large-cap US).
            sigma: Volatilit+� daily du symbole (+�cart-type des rendements).
=======
        """Retourne le coût de slippage en USD pour UNE transaction.

        Args:
            notional: Taille de l'ordre en USD.
            adv: Volume quotidien moyen en USD (défaut = large-cap US).
            sigma: Volatilité daily du symbole (écart-type des rendements).
>>>>>>> origin/main
        """
        return notional * self.compute_fraction(notional, adv, sigma)

    def compute_bps(
        self,
        notional: float,
        adv: float = _ADV_LARGE_CAP,
        sigma: float = 0.02,
    ) -> float:
<<<<<<< HEAD
        """Retourne le co++t de slippage en points de base."""
=======
        """Retourne le coût de slippage en points de base."""
>>>>>>> origin/main
        return self.compute_fraction(notional, adv, sigma) * 10_000

    def compute_fraction(
        self,
        notional: float,
        adv: float = _ADV_LARGE_CAP,
        sigma: float = 0.02,
    ) -> float:
<<<<<<< HEAD
        """Retourne le co++t de slippage en fraction d+�cimale (0.0001 = 1 bps)."""
=======
        """Retourne le coût de slippage en fraction décimale (0.0001 = 1 bps)."""
>>>>>>> origin/main
        cfg = self.config

        if adv <= 0:
            return cfg.max_cost_bps / 10_000

<<<<<<< HEAD
        # 1. Spread fixe (demi-spread = co++t d'une transaction)
        spread = cfg.spread_bps / 10_000

        # 2. Market impact temporaire (Almgren-Chriss)
        #    impact = +� +� �� +� ���(Q / ADV)
        participation = notional / adv
        market_impact = cfg.eta * sigma * math.sqrt(max(participation, 0.0))

        # 3. Timing cost : �� +� ���(T_exec / 252)
=======
        # 1. Spread fixe (demi-spread = coût d'une transaction)
        spread = cfg.spread_bps / 10_000

        # 2. Market impact temporaire (Almgren-Chriss)
        #    impact = η × σ × √(Q / ADV)
        participation = notional / adv
        market_impact = cfg.eta * sigma * math.sqrt(max(participation, 0.0))

        # 3. Timing cost : σ × √(T_exec / 252)
>>>>>>> origin/main
        timing_cost = sigma * math.sqrt(cfg.execution_delay_days / 252.0)

        total = spread + market_impact + timing_cost
        return min(total, cfg.max_cost_bps / 10_000)

    def compute_pair_entry_cost(
        self,
        notional_leg1: float,
        notional_leg2: float,
        adv1: float = _ADV_LARGE_CAP,
        adv2: float = _ADV_LARGE_CAP,
        sigma1: float = 0.02,
        sigma2: float = 0.02,
    ) -> float:
<<<<<<< HEAD
        """Co++t total d'ENTR+�E d'un pair trade (2 legs, 2 transactions)."""
=======
        """Coût total d'ENTRÉE d'un pair trade (2 legs, 2 transactions)."""
>>>>>>> origin/main
        return (
            self.compute(notional_leg1, adv1, sigma1)
            + self.compute(notional_leg2, adv2, sigma2)
        )

    def compute_pair_roundtrip_cost(
        self,
        notional_leg1: float,
        notional_leg2: float,
        adv1: float = _ADV_LARGE_CAP,
        adv2: float = _ADV_LARGE_CAP,
        sigma1: float = 0.02,
        sigma2: float = 0.02,
    ) -> float:
<<<<<<< HEAD
        """Co++t total aller-retour d'un pair trade (4 transactions)."""
=======
        """Coût total aller-retour d'un pair trade (4 transactions)."""
>>>>>>> origin/main
        leg1_rt = 2.0 * self.compute(notional_leg1, adv1, sigma1)
        leg2_rt = 2.0 * self.compute(notional_leg2, adv2, sigma2)
        return leg1_rt + leg2_rt

    def adv_for_symbol(self, symbol: str) -> float:
        """Estime l'ADV default par tier de capitalisation."""
        return _ADV_MEGA_CAP if symbol in _MEGA_CAP_SYMBOLS else _ADV_LARGE_CAP

    # ------------------------------------------------------------------
    # Diagnostic / reporting
    # ------------------------------------------------------------------

    def breakdown_bps(
        self,
        notional: float,
        adv: float = _ADV_LARGE_CAP,
        sigma: float = 0.02,
    ) -> dict:
<<<<<<< HEAD
        """Retourne le d+�tail par composante (en bps) pour diagnostic."""
=======
        """Retourne le détail par composante (en bps) pour diagnostic."""
>>>>>>> origin/main
        cfg = self.config
        participation = notional / adv if adv > 0 else 1.0
        spread = cfg.spread_bps
        market_impact = cfg.eta * sigma * math.sqrt(max(participation, 0.0)) * 10_000
        timing_cost = sigma * math.sqrt(cfg.execution_delay_days / 252.0) * 10_000
        total = spread + market_impact + timing_cost
        return {
            "spread_bps": round(spread, 4),
            "market_impact_bps": round(market_impact, 4),
            "timing_cost_bps": round(timing_cost, 4),
            "total_bps": round(min(total, cfg.max_cost_bps), 4),
        }

    def log_breakdown(
        self,
        symbol: str,
        notional: float,
        adv: float = _ADV_LARGE_CAP,
        sigma: float = 0.02,
    ) -> None:
<<<<<<< HEAD
        """Log le d+�tail du slippage pour un symbole (debug)."""
=======
        """Log le détail du slippage pour un symbole (debug)."""
>>>>>>> origin/main
        bd = self.breakdown_bps(notional, adv, sigma)
        logger.debug(
            "slippage_breakdown",
            symbol=symbol,
            notional=round(notional, 0),
            adv_usd=round(adv, 0),
            sigma=round(sigma, 4),
            **bd,
        )


# ---------------------------------------------------------------------------
# Pre-built configs
# ---------------------------------------------------------------------------

def conservative_equity_slippage() -> SlippageConfig:
    """Slippage conservateur pour stress-tests institutionnels.

<<<<<<< HEAD
    Utilis+� pour valider que les r+�sultats tiennent apr+�s friction maximale.
    - spread: 2 bps (mega-cap bid-ask)
    - eta: 0.10 (standard institutional)
    - delay: 0.25 jour (~1.5h d'ex+�cution)
=======
    Utilisé pour valider que les résultats tiennent après friction maximale.
    - spread: 2 bps (mega-cap bid-ask)
    - eta: 0.10 (standard institutional)
    - delay: 0.25 jour (~1.5h d'exécution)
>>>>>>> origin/main
    """
    return SlippageConfig(
        spread_bps=2.0,
        eta=0.10,
        execution_delay_days=0.25,
    )


def realistic_equity_slippage() -> SlippageConfig:
<<<<<<< HEAD
    """Slippage r+�aliste pour usage standard en backtest daily.

    Calibr+� pour IBKR Smart Order Routing sur US mega/large-caps.
    - spread: 2 bps
    - eta: 0.10
    - delay: 0.10 jour (~6 min, r+�aliste avec IBKR SOR)
=======
    """Slippage réaliste pour usage standard en backtest daily.

    Calibré pour IBKR Smart Order Routing sur US mega/large-caps.
    - spread: 2 bps
    - eta: 0.10
    - delay: 0.10 jour (~6 min, réaliste avec IBKR SOR)
>>>>>>> origin/main
    """
    return SlippageConfig(
        spread_bps=2.0,
        eta=0.10,
        execution_delay_days=0.10,
    )


def zero_impact_slippage() -> SlippageConfig:
<<<<<<< HEAD
    """Slippage minimal (spread seul) ��� pour benchmarking."""
=======
    """Slippage minimal (spread seul) — pour benchmarking."""
>>>>>>> origin/main
    return SlippageConfig(
        spread_bps=2.0,
        eta=0.0,
        execution_delay_days=0.0,
    )
<<<<<<< HEAD

=======
>>>>>>> origin/main
