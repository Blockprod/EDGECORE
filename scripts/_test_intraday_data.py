<<<<<<< HEAD
﻿"""Quick test of IBKR intraday data availability."""
=======
"""Quick test of IBKR intraday data availability."""
>>>>>>> origin/main
import sys
import time

sys.path.insert(0, '.')
import pandas as pd

from execution.ibkr_engine import IBGatewaySync

engine = IBGatewaySync(host='127.0.0.1', port=4002, client_id=5010, timeout=60)

tests = [
    ('5-min  5D',  '5 D',  '5 mins'),
    ('30-min 30D', '30 D', '30 mins'),
    ('30-min 1Y',  '1 Y',  '30 mins'),
    ('1-hour 1Y',  '1 Y',  '1 hour'),
]

for label, duration, bar_size in tests:
    try:
        bars = engine.get_historical_data(symbol='SPY', duration=duration, bar_size=bar_size)
        if bars:
            df = pd.DataFrame(bars)
            bars_per_day = {'5 mins': 78, '30 mins': 13, '1 hour': 7}[bar_size]
            days = len(df) / bars_per_day
            first = df.iloc[0]['date']
            last = df.iloc[-1]['date']
            print(f"{label} | {len(df):5d} bars | ~{days:.0f} trading days | {first} -> {last}")
        else:
            print(f"{label} | NO DATA")
    except Exception as e:
        print(f"{label} | ERROR: {e}")
    time.sleep(2)

engine.disconnect()
print("Done.")
