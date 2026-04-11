@echo off
setlocal EnableDelayedExpansion

:: ============================================================
::  EDGECORE V1 — Gestionnaire de tâches
::  Modèle : AlphaEdge/scripts/manage_task.bat
:: ============================================================

set "TASK_IB=EDGECORE_IBGateway"
set "TASK_BOT=EDGECORE_Bot"
set "PROJECT_DIR=C:\Users\averr\EDGECORE_V1"
set "PYTHON_EXE=C:\Users\averr\EDGECORE_V1\venv\Scripts\python.exe"
set "LOG_DIR=C:\Users\averr\EDGECORE_V1\logs"
set "DASHBOARD_URL=http://127.0.0.1:5000/dashboard"

:: ============================================================
:MENU
cls
echo.
echo  +======================================================+
echo  |      EDGECORE V1 -- Gestionnaire                     |
echo  +======================================================+
echo.

:: Statut inline des tâches planifiées
call :STATUS_INLINE "%TASK_IB%"   "IB Gateway  "
call :STATUS_INLINE "%TASK_BOT%"  "Bot         "
echo.
echo  +------------------------------------------------------+
echo  |  1. Statut detaille des taches                       |
echo  |  2. Demarrer IB Gateway  (planificateur)             |
echo  |  3. Arreter  IB Gateway  (planificateur)             |
echo  |  4. Demarrer Bot         (planificateur)             |
echo  |  5. Arreter  Bot         (planificateur)             |
echo  |  6. Voir dernieres lignes de log                     |
echo  |  7. Lancer en mode console  (paper)          *      |
echo  |  8. Demarrer serveur dashboard web           *      |
echo  |  9. Ouvrir Planificateur de taches Windows           |
echo  |  0. Quitter                                          |
echo  | 10. Ouvrir le dashboard dans le navigateur   *      |
echo  +------------------------------------------------------+
echo.
set /p CHOIX="  Votre choix : "

if "%CHOIX%"=="1"  goto OPT_STATUS
if "%CHOIX%"=="2"  goto OPT_START_IB
if "%CHOIX%"=="3"  goto OPT_STOP_IB
if "%CHOIX%"=="4"  goto OPT_START_BOT
if "%CHOIX%"=="5"  goto OPT_STOP_BOT
if "%CHOIX%"=="6"  goto OPT_LOGS
if "%CHOIX%"=="7"  goto OPT_CONSOLE
if "%CHOIX%"=="8"  goto OPT_API_SERVER
if "%CHOIX%"=="9"  goto OPT_SCHEDULER
if "%CHOIX%"=="0"  goto OPT_QUIT
if "%CHOIX%"=="10" goto OPT_DASHBOARD

echo  [!] Choix invalide.
timeout /t 1 >nul
goto MENU

:: ============================================================
:OPT_STATUS
cls
echo.
echo  == Statut des taches planifiees ==
echo.
schtasks /query /fo TABLE /tn "%TASK_IB%"  2>nul || echo  [--] %TASK_IB% : non trouvé
echo.
schtasks /query /fo TABLE /tn "%TASK_BOT%" 2>nul || echo  [--] %TASK_BOT% : non trouvé
echo.
pause
goto MENU

:: ============================================================
:OPT_START_IB
echo.
echo  [>>] Demarrage IB Gateway via planificateur...
schtasks /run /tn "%TASK_IB%" 2>nul || echo  [!] Tâche %TASK_IB% introuvable — créez-la dans le Planificateur.
timeout /t 2 >nul
goto MENU

:: ============================================================
:OPT_STOP_IB
echo.
echo  [||] Arret IB Gateway via planificateur...
schtasks /end /tn "%TASK_IB%" 2>nul || echo  [!] Tâche %TASK_IB% introuvable.
timeout /t 2 >nul
goto MENU

:: ============================================================
:OPT_START_BOT
echo.
echo  [>>] Demarrage Bot via planificateur...
schtasks /run /tn "%TASK_BOT%" 2>nul || echo  [!] Tâche %TASK_BOT% introuvable — créez-la dans le Planificateur.
timeout /t 2 >nul
goto MENU

:: ============================================================
:OPT_STOP_BOT
echo.
echo  [||] Arret Bot via planificateur...
schtasks /end /tn "%TASK_BOT%" 2>nul || echo  [!] Tâche %TASK_BOT% introuvable.
timeout /t 2 >nul
goto MENU

:: ============================================================
:OPT_LOGS
cls
echo.
echo  == Dernieres lignes de log ==
echo.
if not exist "%LOG_DIR%" (
    echo  [!] Dossier logs introuvable : %LOG_DIR%
    pause
    goto MENU
)
for /f "delims=" %%F in ('dir /b /od "%LOG_DIR%\edgecore_paper_*.log" 2^>nul') do set "LAST_LOG=%%F"
if not defined LAST_LOG (
    echo  [!] Aucun fichier edgecore_paper_*.log trouvé dans %LOG_DIR%
    pause
    goto MENU
)
echo  Fichier : %LOG_DIR%\%LAST_LOG%
echo.
powershell -NoProfile -Command "Get-Content '%LOG_DIR%\%LAST_LOG%' | Select-Object -Last 40"
echo.
echo  --- Appuyez sur une touche pour suivre en temps réel (Ctrl+C pour quitter) ---
pause >nul
powershell -NoProfile -Command "Get-Content '%LOG_DIR%\%LAST_LOG%' -Wait | Select-Object -Last 1 -Wait"
goto MENU

:: ============================================================
:OPT_CONSOLE
echo.
echo  [>>] Lancement EDGECORE en mode console (paper)...
echo  [>>] Fenetre 1 : Bot (Rich terminal dashboard)
echo  [>>] Fenetre 2 : Serveur dashboard web  (port 5000)
echo.

:: Lancer le bot paper dans une fenêtre console dédiée
start "EDGECORE Bot — Paper" cmd /k "cd /d "%PROJECT_DIR%" && set EDGECORE_MODE=paper && set EDGECORE_ENV=dev && set IBKR_CLIENT_ID=5 && "%PYTHON_EXE%" scripts\run_paper_tick.py --continuous"

:: Lancer le serveur Flask API dans une 2e fenêtre
start "EDGECORE Dashboard API" cmd /k "cd /d "%PROJECT_DIR%" && set EDGECORE_ENV=dev && set EDGECORE_MODE=paper && "%PYTHON_EXE%" scripts\start_api_server.py"

echo.
echo  [OK] Deux fenetres ouvertes.
echo       Dashboard → %DASHBOARD_URL%
echo       (Option 10 pour ouvrir dans le navigateur)
echo.
timeout /t 3 >nul
goto MENU

:: ============================================================
:OPT_API_SERVER
echo.
echo  [>>] Demarrage du serveur dashboard web (port 5000)...
start "EDGECORE Dashboard API" cmd /k "cd /d "%PROJECT_DIR%" && set EDGECORE_ENV=dev && set EDGECORE_MODE=paper && set IBKR_CLIENT_ID=5 && "%PYTHON_EXE%" scripts\start_api_server.py"
echo.
echo  [OK] Serveur lance -> %DASHBOARD_URL%
timeout /t 2 >nul
goto MENU

:: ============================================================
:OPT_SCHEDULER
start taskschd.msc
goto MENU

:: ============================================================
:OPT_DASHBOARD
echo.
echo  [>>] Ouverture du dashboard dans le navigateur...
start "" "%DASHBOARD_URL%"
goto MENU

:: ============================================================
:OPT_QUIT
echo.
echo  Au revoir.
exit /b 0

:: ============================================================
:: Fonction : STATUS_INLINE <nom_tache> <label>
:STATUS_INLINE
set "_TASK=%~1"
set "_LABEL=%~2"
for /f "tokens=4 delims= " %%S in ('schtasks /query /fo CSV /tn "%_TASK%" 2^>nul ^| findstr /v "TaskName"') do (
    set "_RAW=%%S"
    goto :_STATUS_DONE
)
set "_RAW=N/A"
:_STATUS_DONE
set "_RAW=%_RAW:"=%"
if /i "%_RAW%"=="Running"  echo     [* ACTIF ]  %_LABEL%
if /i "%_RAW%"=="Ready"    echo     [- PRET  ]  %_LABEL%
if /i "%_RAW%"=="N/A"      echo     [. ABSENT]  %_LABEL%
if /i not "%_RAW%"=="Running" (
    if /i not "%_RAW%"=="Ready" (
        if /i not "%_RAW%"=="N/A" (
            echo     [? %_RAW% ]  %_LABEL%
        )
    )
)
exit /b 0
