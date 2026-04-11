@echo off
:: EDGECORE -- Dashboard API server launcher (options 7 et 8 de manage_task.bat)
cd /d C:\Users\averr\EDGECORE_V1
set EDGECORE_ENV=dev
set EDGECORE_MODE=paper
set IBKR_CLIENT_ID=5
C:\Users\averr\EDGECORE_V1\venv\Scripts\python.exe scripts\start_api_server.py
