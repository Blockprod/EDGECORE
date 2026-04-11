@echo off
chcp 65001 >nul 2>&1
title EDGECORE V1 -- Gestionnaire
setlocal

set "TASK_IB=EDGECORE_IBGateway"
set "TASK_BOT=EDGECORE_Bot"
set "PROJECT_DIR=C:\Users\averr\EDGECORE_V1"
set "PYTHON_EXE=C:\Users\averr\EDGECORE_V1\venv\Scripts\python.exe"
set "LOG_DIR=C:\Users\averr\EDGECORE_V1\logs"
set "DASHBOARD_URL=http://127.0.0.1:5000/dashboard"

:MENU
cls
echo.
echo +==============================================================+
echo |             EDGECORE V1 -- Gestionnaire                     |
echo +==============================================================+
echo.

call :STATUS_INLINE %TASK_IB%  IB_STATUS
call :STATUS_INLINE %TASK_BOT% BOT_STATUS

echo   IB Gateway  : %IB_STATUS%
echo   Bot         : %BOT_STATUS%
echo.
echo   ----------------------------------------------
echo   1. Statut detaille des taches
echo   2. Demarrer IB Gateway  (planificateur)
echo   3. Arreter  IB Gateway  (planificateur)
echo   4. Demarrer Bot         (planificateur)
echo   5. Arreter  Bot         (planificateur)
echo   6. Voir les dernieres lignes de log
echo   7. Lancer le bot en mode console (paper)
echo   8. Ouvrir le dashboard web (navigateur -- port 5000)
echo   9. Ouvrir le Planificateur de taches Windows
echo   0. Quitter
echo.
set /p CHOIX=Votre choix [0-9] : 

if "%CHOIX%"=="1" goto OPT_STATUS
if "%CHOIX%"=="2" goto OPT_START_IB
if "%CHOIX%"=="3" goto OPT_STOP_IB
if "%CHOIX%"=="4" goto OPT_START_BOT
if "%CHOIX%"=="5" goto OPT_STOP_BOT
if "%CHOIX%"=="6" goto OPT_LOG
if "%CHOIX%"=="7" goto OPT_CONSOLE
if "%CHOIX%"=="8" goto OPT_DASHBOARD
if "%CHOIX%"=="9" goto OPT_SCHEDULER
if "%CHOIX%"=="0" goto END
goto MENU

:OPT_STATUS
cls
echo.
echo == Statut IB Gateway ==
schtasks /query /tn "%TASK_IB%" /v /fo list 2>nul || echo   [!] Tache introuvable
echo.
echo == Statut Bot ==
schtasks /query /tn "%TASK_BOT%" /v /fo list 2>nul || echo   [!] Tache introuvable
echo.
pause
goto MENU

:OPT_START_IB
echo.
echo [*] Demarrage IB Gateway...
schtasks /run /tn "%TASK_IB%"
if %errorlevel% neq 0 echo [ERREUR] Tache introuvable -- executez install_task.bat en admin
pause
goto MENU

:OPT_STOP_IB
echo.
echo [*] Arret IB Gateway...
schtasks /end /tn "%TASK_IB%" 2>nul
echo [OK] Signal envoye.
pause
goto MENU

:OPT_START_BOT
echo.
echo [*] Demarrage Bot...
schtasks /run /tn "%TASK_BOT%"
if %errorlevel% neq 0 echo [ERREUR] Tache introuvable -- executez install_task.bat en admin
pause
goto MENU

:OPT_STOP_BOT
echo.
echo [*] Arret Bot...
schtasks /end /tn "%TASK_BOT%" 2>nul
echo [OK] Signal envoye.
pause
goto MENU

:OPT_LOG
cls
echo.
echo == Dernieres lignes de log ==
for /f "delims=" %%F in ('dir /b /o-d "%LOG_DIR%\*.log" 2^>nul') do (
    echo [Fichier: %%F]
    powershell -Command "Get-Content '%LOG_DIR%\%%F' -Tail 40 -ErrorAction SilentlyContinue"
    goto :OPT_LOG_DONE
)
echo [!] Aucun log trouve dans %LOG_DIR%
:OPT_LOG_DONE
echo.
pause
goto MENU

:OPT_CONSOLE
echo.
echo [*] Lancement du bot dans une nouvelle fenetre (paper)...
echo     Fermez la fenetre EDGECORE Bot pour arreter le bot.
start "EDGECORE Bot" cmd /k "set EDGECORE_MODE=paper& set EDGECORE_ENV=dev& set IBKR_CLIENT_ID=5& cd /d C:\Users\averr\EDGECORE_V1& C:\Users\averr\EDGECORE_V1\venv\Scripts\python.exe scripts\run_paper_tick.py --continuous"
echo [OK] Bot demarre.
timeout /t 2 >nul
goto MENU

:OPT_DASHBOARD
echo.
echo [*] Ouverture du dashboard web (%DASHBOARD_URL%)...
echo     Le bot doit etre deja demarre (option 4 ou 7).
start "" "%DASHBOARD_URL%"
goto MENU

:OPT_SCHEDULER
start taskschd.msc
goto MENU

:STATUS_INLINE
schtasks /query /tn "%~1" /fo csv >nul 2>&1
if %errorlevel% neq 0 (
    set "%~2=[NON INSTALLEE]"
    goto :eof
)
for /f "tokens=3 delims=," %%S in ('schtasks /query /tn "%~1" /fo csv ^| findstr /v "TaskName"') do (
    set "%~2=%%~S"
    goto :eof
)
set "%~2=[inconnu]"
goto :eof

:END
endlocal
