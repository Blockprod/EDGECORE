<<<<<<< HEAD
﻿@echo off
REM D├®marre IBKR Gateway
=======
@echo off
REM Démarre IBKR Gateway
>>>>>>> origin/main
start "IBKR Gateway" "C:\Jts\ibgateway\1044\ibgateway.exe" -J-DjtsConfigDir="C:\Jts\ibgateway\1044"
REM Attend 30 secondes pour la connexion
ping 127.0.0.1 -n 30 > nul
REM Lance le healthcheck Python
call ..\venv\Scripts\activate.bat
python scripts/ibkr_healthcheck.py
pause
