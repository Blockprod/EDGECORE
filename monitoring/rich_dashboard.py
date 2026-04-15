"""EDGECORE Premium Rich Dashboard -- Terminal UI for paper/live trading.

This module provides the premium Rich-based dashboard used by:
  - run_paper_tick.py (paper trading, terminal UI)
  - scripts/run_paper_trading.py (paper trading CLI)
  - main.py (live trading, terminal UI fallback)

Features:
  - Minimalist institutional aesthetic with HEAVY box borders
  - Monochromatic palette with targeted color accents
  - Three-column KPI strip for instant situational awareness
  - Real-time equity sparkline with Unicode block characters
  - Countdown progress bar with animated fill
  - Cointegrated pairs table with sector color badges
  - Open positions with PnL magnitude bars
"""

from datetime import datetime, timedelta
from typing import Any

from rich import box
from rich.align import Align
from rich.columns import Columns
from rich.console import Group
from rich.padding import Padding
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

# =====================================================================
# PALETTE -- Institutional Monochrome + Targeted Accents
# =====================================================================
_WHITE = "#E2E8F0"
_DIM = "#64748B"
_FAINT = "#334155"
_BG_ALT = "#0F172A"

_CYAN = "#22D3EE"
_BLUE = "#60A5FA"
_INDIGO = "#818CF8"
_GREEN = "#34D399"
_RED = "#F87171"
_AMBER = "#FBBF24"
_PURPLE = "#A78BFA"

_BORDER = _FAINT
_TITLE = _WHITE

# -- Status indicator configs
_STATUS_MAP: dict[str, tuple[str, str, str]] = {
    #           (dot_color,  label,           border_override)
    "RUNNING": (_GREEN, "RUNNING", _FAINT),
    "COMPUTING": (_AMBER, "COMPUTING", "#7A5800"),
    "INITIALIZING": (_BLUE, "INITIALIZING", _FAINT),
    "STOPPED": (_RED, "STOPPED", "#7B1C1C"),
    "ERROR": (_RED, "ERROR", "#7B1C1C"),
}

SECTOR_COLORS: dict[str, str] = {
    "technology": _CYAN,
    "financials": _AMBER,
    "energy": "#FB923C",
    "consumer_staples": _GREEN,
    "industrials": "#CBD5E1",
    "utilities": _PURPLE,
}
SECTOR_SHORT: dict[str, str] = {
    "technology": "TECH",
    "financials": "FIN",
    "energy": "ENRG",
    "consumer_staples": "CSTA",
    "industrials": "INDU",
    "utilities": "UTIL",
}


# =====================================================================
# HELPERS
# =====================================================================


def format_duration(seconds: float) -> str:
    """Format seconds into human-readable duration."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        m, s = divmod(int(seconds), 60)
        return f"{m}m {s:02d}s"
    else:
        h, rem = divmod(int(seconds), 3600)
        m, s = divmod(rem, 60)
        return f"{h}h {m:02d}m {s:02d}s"


def sparkline(values: list, width: int = 30) -> str:
    """Render a Unicode block sparkline."""
    blocks = " ▁▂▃▄▅▆▇█"
    if len(values) < 2:
        return f"[{_DIM}]awaiting data ···[/{_DIM}]"

    mn, mx = min(values), max(values)
    rng = mx - mn

    if rng < 0.01:
        return f"[{_AMBER}]{'─' * width}[/{_AMBER}]  [{_DIM}]flat[/{_DIM}]"

    step = max(1.0, len(values) / width)
    sampled = [values[min(int(i * step), len(values) - 1)] for i in range(width)]
    trend_c = _GREEN if sampled[-1] >= sampled[0] else _RED
    chars = ""
    for v in sampled:
        idx = int((v - mn) / rng * (len(blocks) - 1))
        chars += blocks[idx]
    return f"[{trend_c}]{chars}[/{trend_c}]  [{_DIM}]{len(values)} pts[/{_DIM}]"


def _progress_bar(done: int, total: int, width: int = 24) -> str:
    """Render a Unicode progress bar."""
    if total <= 0:
        return f"[{_DIM}]{'░' * width}[/{_DIM}]"
    pct = min(done / total, 1.0)
    filled = int(pct * width)
    return (
        f"[{_CYAN}]{'━' * filled}[/{_CYAN}]"
        f"[{_FAINT}]{'─' * (width - filled)}[/{_FAINT}]"
        f"  [{_DIM}]{pct * 100:.0f}%[/{_DIM}]"
    )


def _kpi_card(label: str, value: str, color: str) -> Text:
    """Render a centered KPI card (label over value)."""
    t = Text(justify="center")
    t.append(f"{label}\n", style=f"{_DIM}")
    t.append(value, style=f"bold {color}")
    return t


# =====================================================================
# MAIN BUILDER
# =====================================================================


def build_dashboard(
    runner: Any,
    tick_count: int,
    tick_elapsed: float,
    start_time: datetime,
    interval: int,
    status: str = "RUNNING",
    next_tick_in: float = 0,
    sector_map: dict[str, str] | None = None,
) -> Group:
    """Build and return a Rich renderable for the live dashboard.

    Args:
        runner: PaperTradingRunner or LiveTradingRunner instance
        tick_count: Number of ticks executed
        tick_elapsed: Duration of last tick in seconds
        start_time: When the runner started
        interval: Bar interval in seconds
        status: Current status (RUNNING, COMPUTING, STOPPED, ERROR)
        next_tick_in: Seconds until next tick (if continuous mode)
        sector_map: Mapping of symbols to sectors

    Returns:
        Rich Group containing all dashboard panels
    """
    if sector_map is None:
        sector_map = {}

    now = datetime.now()
    uptime = (now - start_time).total_seconds()

    # -- Extract runner state ------------------------------------------
    active_pairs = getattr(runner, "_active_pairs", [])
    positions = getattr(runner, "_positions", {})
    metrics = getattr(runner, "_metrics", None)
    initial_capital = runner.config.initial_capital
    equity_hist = list(getattr(runner, "_equity_history", []))
    data_loaded = getattr(runner, "_data_symbols_loaded", 0)
    data_total = getattr(runner, "_data_symbols_total", 0)
    data_rows = getattr(runner, "_data_load_rows", 0)

    equity = initial_capital
    if metrics:
        raw_equity = getattr(metrics, "equity", 0)
        if raw_equity > 0:
            equity = raw_equity
    total_pnl = equity - initial_capital
    total_pnl_pct = (total_pnl / initial_capital * 100) if initial_capital > 0 else 0
    max_dd = getattr(metrics, "max_drawdown", 0) * 100 if metrics else 0
    trades_total = getattr(metrics, "trades_total", 0) if metrics else 0
    winning = getattr(metrics, "winning_trades", 0) if metrics else 0
    losing = getattr(metrics, "losing_trades", 0) if metrics else 0
    win_rate = (winning / trades_total * 100) if trades_total > 0 else 0.0

    pnl_c = _GREEN if total_pnl >= 0 else _RED
    pnl_sign = "+" if total_pnl >= 0 else ""
    dd_c = _RED if max_dd > 10 else _AMBER if max_dd > 3 else _GREEN
    wr_c = _GREEN if win_rate >= 55 else _AMBER if win_rate >= 45 else _RED

    # -- Status indicator -----------------------------------------------
    dot_c, st_label, _brd = _STATUS_MAP.get(status, _STATUS_MAP["RUNNING"])

    # ================================================================
    #  HEADER BAR
    # ================================================================
    hdr = Table.grid(expand=True, padding=(0, 1))
    hdr.add_column(justify="left", ratio=3)
    hdr.add_column(justify="center", ratio=4)
    hdr.add_column(justify="right", ratio=3)

    hdr.add_row(
        Text.from_markup(f"[{_DIM}]{now:%Y-%m-%d}[/{_DIM}]  [bold {_WHITE}]{now:%H:%M:%S}[/bold {_WHITE}]"),
        Text.from_markup(
            f"[bold {_CYAN}]◆[/bold {_CYAN}]  "
            f"[bold {_WHITE}]EDGECORE[/bold {_WHITE}]"
            f"[{_DIM}]  ·  [/{_DIM}]"
            f"[{_INDIGO}]Stat-Arb Paper[/{_INDIGO}]"
        ),
        Text.from_markup(f"[bold {dot_c}]●[/bold {dot_c}]  [bold {dot_c}]{st_label}[/bold {dot_c}]"),
    )

    header = Panel(hdr, box=box.HEAVY, border_style=_BORDER, padding=(0, 1))

    # ================================================================
    #  KPI STRIP  (3 cards in a row)
    # ================================================================
    kpi = Table.grid(expand=True, padding=(0, 2))
    kpi.add_column(justify="center", ratio=1)
    kpi.add_column(justify="center", ratio=1)
    kpi.add_column(justify="center", ratio=1)

    # Card 1: Equity
    eq_val = f"$ {equity:,.2f}"
    eq_delta = f"  {pnl_sign}{total_pnl_pct:.2f}%"
    eq_card = Text(justify="center")
    eq_card.append("EQUITY\n", style=_DIM)
    eq_card.append(eq_val, style=f"bold {pnl_c}")
    eq_card.append(eq_delta, style=f"{pnl_c}")

    # Card 2: PnL
    pnl_card = Text(justify="center")
    pnl_card.append("P&L\n", style=_DIM)
    pnl_card.append(f"{pnl_sign}$ {total_pnl:,.2f}", style=f"bold {pnl_c}")

    # Card 3: Drawdown
    dd_card = Text(justify="center")
    dd_card.append("MAX DD\n", style=_DIM)
    dd_card.append(f"▼ {max_dd:.2f}%", style=f"bold {dd_c}")

    kpi.add_row(eq_card, pnl_card, dd_card)

    kpi_panel = Panel(kpi, box=box.HEAVY, border_style=_BORDER, padding=(0, 1))

    # ================================================================
    #  LEFT COLUMN: STATUS
    # ================================================================
    st = Table.grid(padding=(0, 2))
    st.add_column(style=_DIM, min_width=10)
    st.add_column(min_width=30)

    st.add_row(
        "Uptime",
        f"[bold {_CYAN}]{format_duration(uptime)}[/bold {_CYAN}]  [{_DIM}]since {start_time:%H:%M:%S}[/{_DIM}]",
    )
    st.add_row(
        "Tick",
        f"[bold {_WHITE}]#{tick_count}[/bold {_WHITE}]"
        + (f"  [{_DIM}]{tick_elapsed:.1f}s[/{_DIM}]" if tick_elapsed > 0 else ""),
    )

    # Data status
    if tick_count == 0 or data_total == 0:
        data_cell = f"[{_DIM}]pending ···[/{_DIM}]"
    elif data_loaded == data_total:
        data_cell = (
            f"[bold {_GREEN}]✓[/bold {_GREEN}]  "
            f"[{_WHITE}]{data_loaded}/{data_total}[/{_WHITE}]"
            f"  [{_DIM}]{data_rows} bars[/{_DIM}]"
        )
    else:
        data_cell = (
            f"[bold {_AMBER}]![/bold {_AMBER}]  "
            f"[{_AMBER}]{data_loaded}/{data_total}[/{_AMBER}]"
            f"  [{_DIM}]{data_rows} bars[/{_DIM}]"
        )
    st.add_row("Data", Text.from_markup(data_cell))

    # Next tick / countdown
    if next_tick_in > 0:
        next_time = now + timedelta(seconds=next_tick_in)
        done = max(0, interval - int(next_tick_in))
        st.add_row(
            "Next tick",
            Text.from_markup(
                f"[bold {_WHITE}]{next_time:%H:%M:%S}[/bold {_WHITE}]"
                f"  [{_DIM}]in {format_duration(next_tick_in)}[/{_DIM}]"
            ),
        )
        st.add_row("", Text.from_markup(_progress_bar(done, interval)))
    else:
        st.add_row("Interval", f"[{_WHITE}]{format_duration(interval)}[/{_WHITE}]")

    status_panel = Panel(
        st,
        title=f"[bold {_TITLE}]  STATUS  [/bold {_TITLE}]",
        border_style=_BORDER,
        box=box.HEAVY,
        padding=(0, 1),
    )

    # ================================================================
    #  RIGHT COLUMN: PORTFOLIO
    # ================================================================
    spark_row = Text(justify="center")
    spark_row.append_text(Text.from_markup(sparkline(equity_hist, width=30)))

    stats = Table.grid(expand=True, padding=(0, 2))
    stats.add_column(justify="center")
    stats.add_column(justify="center")
    stats.add_column(justify="center")

    stats.add_row(
        _kpi_card("CAPITAL", f"${initial_capital:,.0f}", _INDIGO),
        _kpi_card("TRADES", f"{trades_total}  W{winning} / L{losing}", _WHITE),
        _kpi_card("WIN RATE", f"{win_rate:.1f}%" if trades_total > 0 else "—", wr_c),
    )

    portfolio_panel = Panel(
        Group(
            Align.center(spark_row),
            Rule(style=_FAINT),
            stats,
        ),
        title=f"[bold {_TITLE}]  PORTFOLIO  [/bold {_TITLE}]",
        border_style=_BORDER,
        box=box.HEAVY,
        padding=(0, 1),
    )

    # ================================================================
    #  COINTEGRATED PAIRS
    # ================================================================
    pairs_tbl = Table(
        box=box.SIMPLE_HEAD,
        header_style=f"bold {_DIM}",
        expand=True,
        show_edge=False,
        row_styles=["", f"on {_BG_ALT}"],
        padding=(0, 1),
    )
    pairs_tbl.add_column("#", style=_DIM, width=3)
    pairs_tbl.add_column("Pair", style=f"bold {_CYAN}", min_width=14)
    pairs_tbl.add_column("Sector", justify="center", min_width=6)
    pairs_tbl.add_column("Half-Life", justify="center", min_width=9)
    pairs_tbl.add_column("P-Value", justify="right", min_width=10)
    pairs_tbl.add_column("Z-Score", justify="right", min_width=8)
    pairs_tbl.add_column("Status", justify="center", min_width=12)

    if active_pairs:
        for i, pair in enumerate(active_pairs, 1):
            if isinstance(pair, tuple) and len(pair) >= 2:
                pair_key = f"{pair[0]}_{pair[1]}"
                pval_f = pair[2] if len(pair) > 2 else None
                hl_f = pair[3] if len(pair) > 3 else None
                pval_str = f"{pval_f:.6f}" if pval_f is not None else "—"
                hl_val = f"{hl_f:.1f}d" if hl_f is not None else "—"
                hl_c = _GREEN if hl_f is not None and hl_f < 20 else _AMBER if hl_f is not None and hl_f < 60 else _DIM
                sym_sector = sector_map.get(pair[0], "")
                sec_col = SECTOR_COLORS.get(sym_sector, _DIM)
                sec_short = SECTOR_SHORT.get(sym_sector, sym_sector[:4].upper() if sym_sector else "—")
                pos_data = positions.get(pair_key, {})
                curr_z = pos_data.get("current_z", None)
                z_str = f"[bold {_WHITE}]{curr_z:+.2f}[/bold {_WHITE}]" if curr_z is not None else f"[{_DIM}]—[/{_DIM}]"
                if pair_key in positions:
                    side = pos_data.get("side", "?")
                    sc = _GREEN if side == "LONG" else _RED
                    status_cell = Text.from_markup(f"[bold {sc}]● {side}[/bold {sc}]")
                else:
                    status_cell = Text.from_markup(f"[{_DIM}]○ idle[/{_DIM}]")
                pairs_tbl.add_row(
                    f"[{_DIM}]{i}[/{_DIM}]",
                    pair_key,
                    Text.from_markup(f"[{sec_col}]{sec_short}[/{sec_col}]"),
                    f"[{hl_c}]{hl_val}[/{hl_c}]",
                    f"[{_DIM}]{pval_str}[/{_DIM}]",
                    z_str,
                    status_cell,
                )
    else:
        pairs_tbl.add_row(
            f"[{_DIM}]—[/{_DIM}]",
            Text.from_markup(f"[italic {_DIM}]no pairs discovered yet[/italic {_DIM}]"),
            "",
            "",
            "",
            "",
            "",
        )

    n_pairs = len(active_pairs)
    pairs_panel = Panel(
        pairs_tbl,
        title=(f"[bold {_TITLE}]  PAIRS  [/bold {_TITLE}]  [{_DIM}]{n_pairs} active[/{_DIM}]  "),
        border_style=_BORDER,
        box=box.HEAVY,
        padding=(0, 1),
    )

    # ================================================================
    #  OPEN POSITIONS
    # ================================================================
    n_pos = len(positions) if isinstance(positions, dict) else 0
    if positions:
        pos_tbl = Table(
            box=box.SIMPLE_HEAD,
            header_style=f"bold {_DIM}",
            expand=True,
            show_edge=False,
            row_styles=["", f"on {_BG_ALT}"],
            padding=(0, 1),
        )
        pos_tbl.add_column("Pair", style=f"bold {_CYAN}", min_width=14)
        pos_tbl.add_column("Sector", justify="center", min_width=6)
        pos_tbl.add_column("Side", justify="center", min_width=6)
        pos_tbl.add_column("Qty", justify="right", min_width=5)
        pos_tbl.add_column("Entry Z", justify="right", min_width=8)
        pos_tbl.add_column("Curr Z", justify="right", min_width=8)
        pos_tbl.add_column("Unreal. PnL", justify="right", min_width=16)

        for pair_key, pos in positions.items():
            side = pos.get("side", "?")
            sc = _GREEN if side == "LONG" else _RED
            qty = pos.get("quantity", 0)
            entry_z = pos.get("entry_z", 0.0)
            current_z = pos.get("current_z", 0.0)
            pnl_pct = pos.get("unrealized_pnl_pct", 0.0) * 100
            pc = _GREEN if pnl_pct >= 0 else _RED

            sym_a = pair_key.split("_")[0] if "_" in pair_key else pair_key
            sym_sector = sector_map.get(sym_a, "")
            sec_col = SECTOR_COLORS.get(sym_sector, _DIM)
            sec_short = SECTOR_SHORT.get(sym_sector, "—")

            bar_fill = int(min(abs(pnl_pct) / 5.0, 1.0) * 8)
            pnl_bar = f"[{pc}]{'█' * bar_fill}{'░' * (8 - bar_fill)}[/{pc}]"

            pos_tbl.add_row(
                pair_key,
                Text.from_markup(f"[{sec_col}]{sec_short}[/{sec_col}]"),
                Text.from_markup(f"[bold {sc}]{side}[/bold {sc}]"),
                f"[{_WHITE}]{qty}[/{_WHITE}]",
                f"[{_DIM}]{entry_z:+.3f}[/{_DIM}]",
                f"[bold {_WHITE}]{current_z:+.3f}[/bold {_WHITE}]",
                Text.from_markup(f"[bold {pc}]{pnl_pct:+.2f}%[/bold {pc}]  {pnl_bar}"),
            )
        pos_content: Any = pos_tbl
    else:
        pos_content = Padding(
            Align.center(Text.from_markup(f"[{_DIM}]no open positions  ·  waiting for z-score signal[/{_DIM}]")),
            pad=(1, 0),
        )

    positions_panel = Panel(
        pos_content,
        title=(f"[bold {_TITLE}]  POSITIONS  [/bold {_TITLE}]  [{_DIM}]{n_pos} open[/{_DIM}]  "),
        border_style=_BORDER,
        box=box.HEAVY,
        padding=(0, 1),
    )

    # ================================================================
    #  FOOTER
    # ================================================================
    if status == "STOPPED":
        footer_txt = Text.from_markup(f"[bold {_RED}]■  Bot stopped — terminal restored in a moment …[/bold {_RED}]")
    else:
        footer_txt = Text.from_markup(
            f"[bold {_AMBER}]Ctrl+C[/bold {_AMBER}]"
            f"[{_DIM}]  stop   │   [/{_DIM}]"
            f"[{_WHITE}]logs/[/{_WHITE}]"
            f"[{_DIM}]   │   IB Gateway [/{_DIM}]"
            f"[bold {_CYAN}]:4002[/bold {_CYAN}]"
        )

    footer = Panel(
        Align.center(footer_txt),
        box=box.HEAVY,
        border_style=_BORDER,
        padding=(0, 0),
    )

    # ================================================================
    #  LAYOUT ASSEMBLY
    # ================================================================
    two_col = Table.grid(expand=True, padding=(0, 0))
    two_col.add_column(ratio=1)
    two_col.add_column(ratio=1)
    two_col.add_row(status_panel, portfolio_panel)

    return Group(
        header,
        kpi_panel,
        two_col,
        pairs_panel,
        positions_panel,
        footer,
    )
