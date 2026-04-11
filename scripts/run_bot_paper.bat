@echo off
:: EDGECORE V1 — Wrapper de lancement bot paper trading (utilisé par le Planificateur de tâches)
set EDGECORE_MODE=paper
set EDGECORE_ENV=dev
set IBKR_CLIENT_ID=5
cd /d "C:\Users\averr\EDGECORE_V1"
"C:\Users\averr\EDGECORE_V1\venv\Scripts\pythonw.exe" scripts\run_paper_tick.py --continuous
