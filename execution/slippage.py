"""
Phase 0.1 ÔÇö Mod├¿le de Slippage R├®aliste (3 composantes).

Fournit une estimation du co├╗t de friction pour CHAQUE leg d'un pair trade,
en euros/dollars, ├á partir de :

  1. **Spread bid-ask fixe** ÔÇö demi-spread per transaction (~2 bps mega-caps US)
  2. **Market impact temporaire** (Almgren-Chriss simplifi├®)
        impact = ╬À ├ù ¤â_daily ├ù ÔêÜ(Q / ADV)
        ╬À  : constante d'impact (~0.1 pour mega-caps)
        Q  : notionnel de l'ordre (USD)
        ADV: volume quotidien moyen (USD)
  3. **Timing cost** (incertitude d'ex├®cution intraday)
        timing = ¤â_daily ├ù ÔêÜ(T_exec / 252)
        T_exec : d├®lai d'ex├®cution en jours (ex: 0.1 Ôëê 6 min)

Utilisation ::

    model = SlippageModel()
    cost_usd = model.compute(notional=5_000, adv=500_000_000, sigma=0.02)
    cost_bps = model.compute_bps(notional=5_000, adv=500_000_000, sigma=0.02)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from structlog import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class SlippageConfig:
    """Param├¿tres du mod├¿le de slippage ├á 3 composantes.

    Defaults calibr├®s pour US mega-cap equities via IBKR daily bars.
    """

    # 1. Spread bid-ask (demi-spread par transaction, en bps)
    spread_bps: float = 2.0

    # 2. Almgren-Chriss: ╬À coefficient d'impact temporaire
    #    0.10 = valeur institutionnelle standard pour mega-caps US
    #    0.05 = lowercase/conservative (v31h default)
    #    0.30 = mid-caps / faible liquidit├®
    eta: float = 0.10

    # 3. D├®lai d'ex├®cution en jours de trading (pour timing cost)
    #    0.10 = ~6 minutes        (r├®aliste pour daily + IBKR Smart Order)
    #    0.25 = ~1.5 heures       (conservateur)
    #    0.50 = demi-journ├®e       (tr├¿s conservateur)
    execution_delay_days: float = 0.10

    # Cap: ├®viter des co├╗ts absurdes sur actifs illiquides
    max_cost_bps: float = 100.0


# ---------------------------------------------------------------------------
# ADV estimates par tier de capitalisation
# ---------------------------------------------------------------------------

_ADV_MEGA_CAP = 500_000_000   # $500M/j ÔÇö AAPL, MSFT, NVDA, GOOGL, AMZN, META, BRK
_ADV_LARGE_CAP = 150_000_000  # $150M/j ÔÇö Most S&P 500 constituents

_MEGA_CAP_SYMBOLS = frozenset({
    "AAPL", "MSFT", "NVDA", "GOOGL", "GOOG", "AMZN", "META", "BRK.B", "LLY",
    "AVGO", "TSLA", "NFLX", "JPM", "V", "MA", "UNH", "WMT", "XOM", "JNJ",
    "PG", "HD", "ORCL", "COST", "CVX", "MRK", "KO", "PEP", "ABBV", "TMO",
})


# ---------------------------------------------------------------------------
# SlippageModel
# ---------------------------------------------------------------------------

class SlippageModel:
    """Mod├¿le de slippage ├á 3 composantes pour backtests d'equities US.

    Chaque appel ├á ``compute()`` retourne le co├╗t estim├® pour UNE transaction
    unidirectionnelle (un seul leg, un seul sens).  Pour un pair trade complet
    (4 transactions = 2 entr├®es + 2 sorties), multiplier par 4.

    Args:
        config: Param├¿tres du mod├¿le (spread, eta, d├®lai).
    """

    def __init__(self, config: Optional[SlippageConfig] = None):
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
        """Retourne le co├╗t de slippage en USD pour UNE transaction.

        Args:
            notional: Taille de l'ordre en USD.
            adv: Volume quotidien moyen en USD (d├®faut = large-cap US).
            sigma: Volatilit├® daily du symbole (├®cart-type des rendements).
        """
        return notional * self.compute_fraction(notional, adv, sigma)

    def compute_bps(
        self,
        notional: float,
        adv: float = _ADV_LARGE_CAP,
        sigma: float = 0.02,
    ) -> float:
        """Retourne le co├╗t de slippage en points de base."""
        return self.compute_fraction(notional, adv, sigma) * 10_000

    def compute_fraction(
        self,
        notional: float,
        adv: float = _ADV_LARGE_CAP,
        sigma: float = 0.02,
    ) -> float:
        """Retourne le co├╗t de slippage en fraction d├®cimale (0.0001 = 1 bps)."""
        cfg = self.config

        if adv <= 0:
            return cfg.max_cost_bps / 10_000

        # 1. Spread fixe (demi-spread = co├╗t d'une transaction)
        spread = cfg.spread_bps / 10_000

        # 2. Market impact temporaire (Almgren-Chriss)
        #    impact = ╬À ├ù ¤â ├ù ÔêÜ(Q / ADV)
        participation = notional / adv
        market_impact = cfg.eta * sigma * math.sqrt(max(participation, 0.0))

        # 3. Timing cost : ¤â ├ù ÔêÜ(T_exec / 252)
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
        """Co├╗t total d'ENTR├ëE d'un pair trade (2 legs, 2 transactions)."""
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
        """Co├╗t total aller-retour d'un pair trade (4 transactions)."""
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
        """Retourne le d├®tail par composante (en bps) pour diagnostic."""
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
        """Log le d├®tail du slippage pour un symbole (debug)."""
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

    Utilis├® pour valider que les r├®sultats tiennent apr├¿s friction maximale.
    - spread: 2 bps (mega-cap bid-ask)
    - eta: 0.10 (standard institutional)
    - delay: 0.25 jour (~1.5h d'ex├®cution)
    """
    return SlippageConfig(
        spread_bps=2.0,
        eta=0.10,
        execution_delay_days=0.25,
    )


def realistic_equity_slippage() -> SlippageConfig:
    """Slippage r├®aliste pour usage standard en backtest daily.

    Calibr├® pour IBKR Smart Order Routing sur US mega/large-caps.
    - spread: 2 bps
    - eta: 0.10
    - delay: 0.10 jour (~6 min, r├®aliste avec IBKR SOR)
    """
    return SlippageConfig(
        spread_bps=2.0,
        eta=0.10,
        execution_delay_days=0.10,
    )


def zero_impact_slippage() -> SlippageConfig:
    """Slippage minimal (spread seul) ÔÇö pour benchmarking."""
    return SlippageConfig(
        spread_bps=2.0,
        eta=0.0,
        execution_delay_days=0.0,
    )
