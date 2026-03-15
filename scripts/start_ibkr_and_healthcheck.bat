@echo off
REM Script Windows pour lancer IBKR Gateway au d├®marrage
REM Modifie le chemin ci-dessous selon l'emplacement de ton IBKR Gateway

set IBKR_PATH="C:\Jts\ibgateway\ibgateway.exe"

REM Lancer IBKR Gateway
start "IBKR Gateway" %IBKR_PATH%

REM Attendre 10 secondes pour laisser le serveur d├®marrer
ping 127.0.0.1 -n 10 > nul

REM V├®rifier le port 4002
netstat -ano | findstr 4002

REM Lancer le healthcheck Python
cd /d C:\Users\averr\EDGECORE
python scripts\ibkr_healthcheck.py

pause
