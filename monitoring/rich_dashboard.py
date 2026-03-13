"""EDGECORE Premium Rich Dashboard — Terminal UI for paper/live trading.

This module provides the premium Rich-based dashboard used by:
  - run_paper_tick.py (paper trading, terminal UI)
  - scripts/run_paper_trading.py (paper trading CLI)
  - main.py (live trading, terminal UI fallback)

Features:
  - SQUARE_DOUBLE_HEAD borders for professional appearance
  - Vibrant color palette (#00D9FF cyan primary, #7C3AED purple secondary)
  - Real-time equity sparkline with 60-tick history
  - Data load tracking (symbols, bars count)
  - Status badges (RUNNING/COMPUTING/STOPPED)
  - Cointegrated pairs table with sector badges
  - Open positions with unrealized PnL bars
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.columns import Columns
from rich.align import Align
from rich.live import Live
from rich.rule import Rule
from rich.padding import Padding
from rich import box

# ─────────────────────────────────────────────────────────────────────
# PALETTE — Premium Gradient Colors
# ─────────────────────────────────────────────────────────────────────
_C_PRIMARY   = "#00D9FF"   # Bright cyan - main accent
_C_SECONDARY = "#7C3AED"   # Vibrant purple
_C_ACCENT    = "#6366F1"   # Indigo
_C_SUCCESS   = "#10B981"   # Emerald green
_C_DANGER    = "#EF4444"   # Bright red
_C_WARN      = "#F59E0B"   # Amber
_C_INFO      = "#3B82F6"   # Blue
_C_LIGHT     = "#F8FAFC"   # Near white
_C_DARK      = "#0F172A"   # Dark slate
_C_MUTE      = "#64748B"   # Slate grey
_C_BORDER    = "#1E293B"   # Darker border
_C_BG_LIGHT  = "#020617"   # Almost black background

# Semantic aliases (for readability)
_C_DIM      = _C_MUTE          # Dimmed text
_C_TITLE    = _C_LIGHT         # Panel titles
_C_VAL      = _C_ACCENT        # Values/numbers
_C_GREEN    = _C_SUCCESS       # Positive (green)
_C_GREEN2   = "#34D399"        # Alt green
_C_RED      = _C_DANGER        # Negative (red)
_C_YELLOW   = _C_WARN          # Warning (yellow)
_C_CYAN     = _C_PRIMARY       # Cyan highlights
_C_BORDER2  = _C_MUTE          # Secondary border


def format_duration(seconds: float) -> str:
    """Format seconds into human-readable duration."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        m, s = divmod(int(seconds), 60)
        return f"{m}m {s}s"
    else:
        h, rem = divmod(int(seconds), 3600)
        m, s = divmod(rem, 60)
        return f"{h}h {m}m {s}s"


def sparkline(values: list, width: int = 26) -> str:
    """Render a Unicode block sparkline."""
    blocks = "▁▂▃▄▅▆▇█"
    if len(values) < 2:
        # Not enough data - show a simple line with hint
        return f"[{_C_DIM}]no history yet (waiting for ticks)[/{_C_DIM}]"
    
    mn, mx = min(values), max(values)
    rng = mx - mn
    
    # If all values are identical (flat), show a different pattern
    if rng < 0.01:
        # Show a flat sparkline or alternate
        flat_pattern = "─" * width
        return f"[{_C_YELLOW}]{flat_pattern}[/{_C_YELLOW}] [flat]"
    
    # Normal sparkline with range
    step = max(1.0, len(values) / width)
    sampled = [values[min(int(i * step), len(values) - 1)] for i in range(width)]
    trend_color = _C_GREEN if sampled[-1] >= sampled[0] else _C_RED
    chars = ""
    for v in sampled:
        idx = int((v - mn) / rng * (len(blocks) - 1)) if rng > 0 else 3
        chars += blocks[idx]
    pts = f"  [{_C_DIM}]{len(values)} pts[/{_C_DIM}]"
    return f"[{trend_color}]{chars}[/{trend_color}]{pts}"


SECTOR_COLORS: Dict[str, str] = {
    "technology":       "#38BDF8",
    "financials":       "#F59E0B",
    "energy":           "#FB923C",
    "consumer_staples": "#86EFAC",
    "industrials":      "#CBD5E1",
    "utilities":        "#C084FC",
}
SECTOR_SHORT: Dict[str, str] = {
    "technology":       "TECH",
    "financials":       "FIN",
    "energy":           "ENRG",
    "consumer_staples": "CSTA",
    "industrials":      "INDU",
    "utilities":        "UTIL",
}


def build_dashboard(
    runner: Any,
    tick_count: int,
    tick_elapsed: float,
    start_time: datetime,
    interval: int,
    status: str = "RUNNING",
    next_tick_in: float = 0,
    sector_map: Optional[Dict[str, str]] = None,
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
        
    now    = datetime.now()
    uptime = (now - start_time).total_seconds()

    active_pairs    = getattr(runner, '_active_pairs', [])
    positions       = getattr(runner, '_positions', {})
    metrics         = getattr(runner, '_metrics', None)
    initial_capital = runner.config.initial_capital
    equity_hist     = list(getattr(runner, '_equity_history', []))
    data_loaded = getattr(runner, '_data_symbols_loaded', 0)
    data_total  = getattr(runner, '_data_symbols_total', 0)
    data_rows   = getattr(runner, '_data_load_rows', 0)

    equity = initial_capital
    if metrics:
        raw_equity = getattr(metrics, 'equity', 0)
        if raw_equity > 0:
            equity = raw_equity
    total_pnl     = equity - initial_capital
    total_pnl_pct = (total_pnl / initial_capital * 100) if initial_capital > 0 else 0
    max_dd        = getattr(metrics, 'max_drawdown', 0) * 100 if metrics else 0
    trades_total  = getattr(metrics, 'trades_total', 0) if metrics else 0
    winning       = getattr(metrics, 'winning_trades', 0) if metrics else 0
    losing        = getattr(metrics, 'losing_trades', 0) if metrics else 0
    win_rate      = (winning / trades_total * 100) if trades_total > 0 else 0.0

    pnl_c    = _C_GREEN if total_pnl >= 0 else _C_RED
    pnl_sign = "+" if total_pnl >= 0 else ""
    dd_c     = _C_RED if max_dd > 10 else _C_YELLOW if max_dd > 3 else _C_GREEN2
    wr_c     = _C_GREEN if win_rate >= 55 else _C_YELLOW if win_rate >= 45 else _C_RED

    # ── Status config ─────────────────────────────────────────────────
    _status_cfg = {
        "RUNNING":      ("bold " + _C_GREEN,  "⬤  RUNNING",      _C_BORDER),
        "COMPUTING":    ("bold " + _C_YELLOW, "◕  COMPUTING…",   "#7A5800"),
        "INITIALIZING": ("bold " + _C_ACCENT, "◉  INITIALIZING", "#0E3460"),
        "STOPPED":      ("bold " + _C_RED,    "◼  STOPPED",      "#7B1C1C"),
        "ERROR":        ("bold " + _C_RED,    "✖  ERROR",        "#7B1C1C"),
    }
    st_style, st_label, border_color = _status_cfg.get(status, _status_cfg["RUNNING"])

    # ════════════════════════════════════════════════════════════════
    # HEADER
    # ════════════════════════════════════════════════════════════════
    hdr = Table.grid(expand=True, padding=(0, 2))
    hdr.add_column(justify="left",   ratio=3)
    hdr.add_column(justify="center", ratio=4)
    hdr.add_column(justify="right",  ratio=3)
    hdr.add_row(
        Text.from_markup(
            f"[{_C_DIM}]{now:%Y-%m-%d}[/{_C_DIM}]"
            f"  [bold {_C_VAL}]{now:%H:%M:%S}[/bold {_C_VAL}]"
        ),
        Text.from_markup(
            f"[bold yellow]⚡[/bold yellow] "
            f"[bold white]EDGECORE[/bold white]"
            f"[{_C_DIM}]  ·  [/{_C_DIM}]"
            f"[bold {_C_ACCENT}]Paper Trading[/bold {_C_ACCENT}]"
        ),
        Text.from_markup(f"[{st_style}]{st_label}[/{st_style}]"),
    )
    header = Panel(
        hdr,
        box=box.SQUARE_DOUBLE_HEAD,
        border_style=_C_PRIMARY,
        padding=(0, 1),
    )

    # ════════════════════════════════════════════════════════════════
    # STATUS
    # ════════════════════════════════════════════════════════════════
    st_tbl = Table.grid(padding=(0, 2))
    st_tbl.add_column(style=_C_DIM, min_width=10)
    st_tbl.add_column(style=_C_VAL, min_width=28)

    st_tbl.add_row("Started",
        f"[{_C_DIM}]{start_time:%Y-%m-%d}  {start_time:%H:%M:%S}[/{_C_DIM}]")
    st_tbl.add_row("Uptime",
        f"[bold {_C_ACCENT}]{format_duration(uptime)}[/bold {_C_ACCENT}]")
    st_tbl.add_row("Tick",
        f"[bold {_C_CYAN}]#{tick_count}[/bold {_C_CYAN}]"
        + (f"   [{_C_DIM}]⏱ {tick_elapsed:.1f}s[/{_C_DIM}]" if tick_elapsed > 0 else ""))

    if tick_count == 0 or data_total == 0:
        data_cell = f"[{_C_DIM}]pending…[/{_C_DIM}]"
    elif data_loaded == data_total:
        data_cell = (f"[bold {_C_GREEN}]✓  {data_loaded}/{data_total}[/bold {_C_GREEN}]"
                     f"  [{_C_DIM}]{data_rows} bars[/{_C_DIM}]")
    else:
        data_cell = (f"[bold {_C_YELLOW}]⚠  {data_loaded}/{data_total}[/bold {_C_YELLOW}]"
                     f"  [{_C_DIM}]{data_rows} bars[/{_C_DIM}]")
    st_tbl.add_row("Data", Text.from_markup(data_cell))

    if next_tick_in > 0:
        next_time = now + timedelta(seconds=next_tick_in)
        done  = max(0, interval - int(next_tick_in))
        pct   = done / interval if interval > 0 else 0
        bar_w = 22
        filled = int(pct * bar_w)
        bar = (f"[{_C_ACCENT}]" + "█" * filled
               + f"[/{_C_ACCENT}][{_C_DIM}]" + "░" * (bar_w - filled)
               + f"[/{_C_DIM}]  [{_C_DIM}]{pct * 100:.0f}%[/{_C_DIM}]")
        st_tbl.add_row("Next tick",
            f"[bold {_C_VAL}]{next_time:%H:%M:%S}[/bold {_C_VAL}]"
            f"  [{_C_DIM}]in {format_duration(next_tick_in)}[/{_C_DIM}]")
        st_tbl.add_row("", Text.from_markup(bar))
    else:
        st_tbl.add_row("Interval", f"[{_C_VAL}]{format_duration(interval)}[/{_C_VAL}]")

    st_tbl.add_row("Log", f"[{_C_DIM}]logs/[/{_C_DIM}]")

    status_panel = Panel(
        st_tbl,
        title=f"[bold {_C_TITLE}]  STATUS  [/bold {_C_TITLE}]",
        border_style=_C_PRIMARY,
        box=box.SQUARE_DOUBLE_HEAD,
        padding=(0, 1),
    )

    # ════════════════════════════════════════════════════════════════
    # PORTFOLIO
    # ════════════════════════════════════════════════════════════════
    eq_txt = Text(justify="center")
    eq_txt.append(f"$ {equity:,.2f}", style=f"bold {pnl_c}")
    eq_txt.append("    ")
    eq_txt.append(f"{pnl_sign}{total_pnl_pct:.2f} %", style=f"bold {pnl_c}")

    pnl_txt = Text(justify="center")
    pnl_txt.append(f"PnL  {pnl_sign}$ {total_pnl:,.2f}", style=f"{pnl_c}")
    spark_txt = Text(justify="center")
    spark_txt.append_text(Text.from_markup(sparkline(equity_hist, width=28)))

    mstrip = Table.grid(padding=(0, 3), expand=True)
    mstrip.add_column(justify="center")
    mstrip.add_column(justify="center")
    mstrip.add_column(justify="center")

    def _metric(label: str, value: str, color: str) -> Text:
        t = Text(justify="center")
        t.append(f"{label}\n", style=f"{_C_DIM}")
        t.append(value, style=f"bold {color}")
        return t

    mstrip.add_row(
        _metric("CAPITAL",   f"${initial_capital:,.0f}",           _C_VAL),
        _metric("MAX DD",    f"−{max_dd:.2f}%",                    dd_c),
        _metric("TRADES",    f"{trades_total}  (W{winning}/L{losing})", _C_VAL),
    )
    if trades_total > 0:
        mstrip.add_row(
            Text(""), Text(""),
            _metric("WIN RATE", f"{win_rate:.1f}%", wr_c),
        )

    portfolio_panel = Panel(
        Group(
            Align.center(eq_txt),
            Align.center(pnl_txt),
            Align.center(spark_txt),
            Rule(style=f"{_C_DIM}"),
            mstrip,
        ),
        title=f"[bold {_C_TITLE}]  PORTFOLIO  [/bold {_C_TITLE}]",
        border_style=_C_PRIMARY,
        box=box.SQUARE_DOUBLE_HEAD,
        padding=(0, 1),
    )

    # ════════════════════════════════════════════════════════════════
    # COINTEGRATED PAIRS
    # ════════════════════════════════════════════════════════════════
    pairs_tbl = Table(
        box=box.MINIMAL_HEAVY_HEAD,
        header_style=f"bold {_C_TITLE}",
        expand=True, show_edge=False,
        row_styles=["", f"on #080F1A"],
    )
    pairs_tbl.add_column("#",         style=_C_DIM, width=3)
    pairs_tbl.add_column("Pair",      style=f"bold {_C_CYAN}", min_width=14)
    pairs_tbl.add_column("Sector",    justify="center", min_width=6)
    pairs_tbl.add_column("Half-Life", justify="center", min_width=10)
    pairs_tbl.add_column("P-Value",   justify="right",  min_width=10)
    pairs_tbl.add_column("Curr Z",    justify="right",  min_width=8)
    pairs_tbl.add_column("Status",    justify="center", min_width=12)

    if active_pairs:
        for i, pair in enumerate(active_pairs, 1):
            if isinstance(pair, tuple) and len(pair) >= 2:
                pair_key   = f"{pair[0]}_{pair[1]}"
                pval_f     = pair[2] if len(pair) > 2 else None
                hl_f       = pair[3] if len(pair) > 3 else None
                pval_str   = f"{pval_f:.6f}" if pval_f is not None else "?"
                hl_val     = f"{hl_f:.1f}d"  if hl_f   is not None else "?"
                hl_c       = (_C_GREEN  if hl_f is not None and hl_f < 20
                              else _C_YELLOW if hl_f is not None and hl_f < 60
                              else _C_VAL)
                sym_sector = sector_map.get(pair[0], "")
                sec_col    = SECTOR_COLORS.get(sym_sector, _C_DIM)
                sec_short  = SECTOR_SHORT.get(sym_sector,
                             sym_sector[:4].upper() if sym_sector else "—")
                pos_data   = positions.get(pair_key, {})
                curr_z     = pos_data.get('current_z', None)
                z_str      = f"{curr_z:+.2f}" if curr_z is not None else f"[{_C_DIM}]—[/{_C_DIM}]"
                if pair_key in positions:
                    side   = pos_data.get('side', '?')
                    sc     = _C_GREEN if side == "LONG" else _C_RED
                    status_cell = Text.from_markup(f"[bold {sc}]⬤ {side}[/bold {sc}]")
                else:
                    status_cell = Text.from_markup(f"[{_C_DIM}]◯ waiting[/{_C_DIM}]")
                pairs_tbl.add_row(
                    str(i), pair_key,
                    Text.from_markup(f"[bold {sec_col}]{sec_short}[/bold {sec_col}]"),
                    f"[{hl_c}]{hl_val}[/{hl_c}]",
                    f"[{_C_ACCENT}]{pval_str}[/{_C_ACCENT}]",
                    z_str,
                    status_cell,
                )
    else:
        pairs_tbl.add_row("—",
            Text.from_markup(f"[italic {_C_DIM}]none discovered yet[/italic {_C_DIM}]"),
            "—", "—", "—", "—", "—")

    pairs_panel = Panel(
        pairs_tbl,
        title=(f"[bold {_C_TITLE}]  COINTEGRATED PAIRS[/bold {_C_TITLE}]"
               f"  [{_C_DIM}]{len(active_pairs)} active[/{_C_DIM}]  "),
        border_style=_C_PRIMARY,
        box=box.SQUARE_DOUBLE_HEAD,
        padding=(0, 1),
    )

    # ════════════════════════════════════════════════════════════════
    # OPEN POSITIONS
    # ════════════════════════════════════════════════════════════════
    if positions:
        pos_tbl = Table(
            box=box.MINIMAL_HEAVY_HEAD,
            header_style=f"bold {_C_TITLE}",
            expand=True, show_edge=False,
            row_styles=["", f"on #080F1A"],
        )
        pos_tbl.add_column("Pair",        style=f"bold {_C_CYAN}")
        pos_tbl.add_column("Sector",      justify="center")
        pos_tbl.add_column("Side",        justify="center")
        pos_tbl.add_column("Qty",         justify="right")
        pos_tbl.add_column("Entry Z",     justify="right")
        pos_tbl.add_column("Curr Z",      justify="right")
        pos_tbl.add_column("Unreal. PnL", justify="right")

        for pair_key, pos in positions.items():
            side       = pos.get('side', '?')
            sc         = _C_GREEN if side == "LONG" else _C_RED
            qty        = pos.get('quantity', 0)
            entry_z    = pos.get('entry_z', 0.0)
            current_z  = pos.get('current_z', 0.0)
            pnl_pct    = pos.get('unrealized_pnl_pct', 0.0) * 100
            pc         = _C_GREEN if pnl_pct >= 0 else _C_RED
            sym_a      = pair_key.split("_")[0] if "_" in pair_key else pair_key
            sym_sector = sector_map.get(sym_a, "")
            sec_col    = SECTOR_COLORS.get(sym_sector, _C_DIM)
            sec_short  = SECTOR_SHORT.get(sym_sector, "—")
            bar_fill   = int(min(abs(pnl_pct) / 5.0, 1.0) * 8)
            pnl_bar    = f"[{pc}]{'█' * bar_fill}{'░' * (8 - bar_fill)}[/{pc}]"
            pos_tbl.add_row(
                pair_key,
                Text.from_markup(f"[bold {sec_col}]{sec_short}[/bold {sec_col}]"),
                Text.from_markup(f"[bold {sc}]{side}[/bold {sc}]"),
                f"[{_C_VAL}]{qty}[/{_C_VAL}]",
                f"[{_C_DIM}]{entry_z:+.3f}[/{_C_DIM}]",
                f"[bold {_C_VAL}]{current_z:+.3f}[/bold {_C_VAL}]",
                Text.from_markup(
                    f"[bold {pc}]{pnl_pct:+.2f}%[/bold {pc}]  {pnl_bar}"),
            )
        pos_content = pos_tbl
    else:
        pos_content = Padding(
            Align.center(Text(
                f"No open positions  —  waiting for signal",
                style=f"italic {_C_DIM}",
            )),
            pad=(1, 0),
        )

    positions_panel = Panel(
        pos_content,
        title=(f"[bold {_C_TITLE}]  OPEN POSITIONS[/bold {_C_TITLE}]"
               f"  [{_C_DIM}]{len(positions)} open[/{_C_DIM}]  "),
        border_style=_C_PRIMARY,
        box=box.SQUARE_DOUBLE_HEAD,
        padding=(0, 1),
    )

    # ════════════════════════════════════════════════════════════════
    # FOOTER
    # ════════════════════════════════════════════════════════════════
    if status == "STOPPED":
        footer_txt = Text.from_markup(
            f"[bold {_C_RED}]◼  Bot stopped — terminal restored in a moment…[/bold {_C_RED}]"
        )
    else:
        footer_txt = Text.from_markup(
            f"[bold {_C_YELLOW}]Ctrl+C[/bold {_C_YELLOW}]"
            f"[{_C_DIM}] to stop     ·     Logs: [/{_C_DIM}]"
            f"[bold {_C_ACCENT}]logs/[/bold {_C_ACCENT}]"
            f"[{_C_DIM}]     ·     IB Gateway [/{_C_DIM}]"
            f"[bold {_C_ACCENT}]:4002[/bold {_C_ACCENT}]"
        )
    footer = Panel(
        Align.center(footer_txt),
        box=box.SQUARE_DOUBLE_HEAD,
        border_style=_C_PRIMARY,
        padding=(0, 1),
    )

    return Group(
        header,
        Columns([status_panel, portfolio_panel], equal=True, expand=True),
        pairs_panel,
        positions_panel,
        footer,
    )
