#!/usr/bin/env python
"""Demo du EDGECORE Premium Dashboard."""

from datetime import datetime, timedelta
from monitoring.rich_dashboard import build_dashboard
from rich.console import Console

# Mock runner object with realistic demo data
class MockRunner:
    def __init__(self):
        self.config = type('obj', (object,), {'initial_capital': 100_000})()
        self._active_pairs = [
            ("AAPL", "MSFT", 0.045123, 45.2),
            ("JPM", "GS", 0.032456, 62.5),
            ("XOM", "CVX", 0.028790, 105.3),
        ]
        self._positions = {
            "AAPL_MSFT": {
                'side': 'LONG',
                'quantity': 100,
                'entry_z': 1.45,
                'current_z': 0.82,
                'unrealized_pnl_pct': 0.0342,
            },
            "JPM_GS": {
                'side': 'SHORT',
                'quantity': 150,
                'entry_z': -1.23,
                'current_z': -0.45,
                'unrealized_pnl_pct': -0.0156,
            },
        }
        self._metrics = type('obj', (object,), {
            'equity': 103_420.50,
            'max_drawdown': 0.025,
            'trades_total': 12,
            'winning_trades': 8,
            'losing_trades': 4,
        })()
        self._data_symbols_loaded = 31
        self._data_symbols_total = 31
        self._data_load_rows = 252
        self._equity_history = [
            100_000, 100_150, 100_320, 100_500, 100_680, 100_850,
            101_020, 101_200, 101_380, 101_550, 101_720, 101_850,
            102_000, 102_150, 102_280, 102_420, 102_500, 102_620,
            102_750, 102_900, 103_050, 103_150, 103_280, 103_420,
        ] + [103_420.50] * 36  # 60 ticks total

# SECTOR MAP
SECTOR_MAP = {
    "AAPL": "technology", "MSFT": "technology", "GOOGL": "technology",
    "META": "technology", "NVDA": "technology", "AMD": "technology",
    "JPM": "financials", "GS": "financials", "BAC": "financials",
    "MS": "financials", "WFC": "financials", "C": "financials",
    "XOM": "energy", "CVX": "energy", "COP": "energy",
    "KO": "consumer_staples", "PEP": "consumer_staples",
    "PG": "consumer_staples", "WMT": "consumer_staples",
    "CAT": "industrials", "HON": "industrials", "DE": "industrials",
    "GE": "industrials", "RTX": "industrials",
    "NEE": "utilities", "DUK": "utilities", "SO": "utilities",
}

def demo():
    """Display the premium dashboard with demo data."""
    console = Console()
    runner = MockRunner()
    
    start_time = datetime.now() - timedelta(hours=1, minutes=5, seconds=51)
    
    # Show the dashboard
    dashboard = build_dashboard(
        runner=runner,
        tick_count=1,
        tick_elapsed=57.8,
        start_time=start_time,
        interval=86400,
        status="RUNNING",
        next_tick_in=23*3600 + 59*60 + 55,  # ~24h countdown
        sector_map=SECTOR_MAP,
    )
    
    console.print(dashboard)

if __name__ == "__main__":
    demo()
