@echo off
:: EDGECORE -- Console bot launcher (option 7 de manage_task.bat)
:: Utilise python.exe (avec sortie console visible)
cd /d C:\Users\averr\EDGECORE_V1
set EDGECORE_MODE=paper
set EDGECORE_ENV=dev
set IBKR_CLIENT_ID=5
C:\Users\averr\EDGECORE_V1\venv\Scripts\python.exe scripts\run_paper_tick.py --continuous --interval 3600
pause
