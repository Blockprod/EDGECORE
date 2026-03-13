@echo off
chcp 65001 >nul 2>&1
title EDGECORE - Gestion de la Tâche Planifiée
set "TASK_NAME=EDGECORE_PAPER"
set "LOG_DIR=C:\Users\averr\EDGECORE\logs"
set "WORK_DIR=C:\Users\averr\EDGECORE"
set "PYTHON_EXE=C:\Users\averr\EDGECORE\venv\Scripts\python.exe"

:MENU
cls
echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║        EDGECORE Paper Trading - Gestion Tâche Planifiée      ║
echo ╠══════════════════════════════════════════════════════════════╣
echo ║  1. Voir le statut de la tâche                               ║
echo ║  2. Lancer un tick manuellement (arrière-plan)               ║
echo ║  3. Arrêter le tick en cours                                 ║
echo ║  4. Voir les dernières lignes du log                         ║
echo ║  5. Suivre le log en temps réel                              ║
echo ║  6. Lancer un tick unique (visible, logs seulement)          ║
echo ║  7. PAPER TRADING CONTINU (logs seulement, no dashboard)    ║
echo ║  8. PAPER TRADING CONTINU avec DASHBOARD PREMIUM ⚡ (Ctrl+C)║
echo ║  9. Ouvrir le Planificateur de tâches Windows                ║
echo ║  10. Quitter                                                  ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.
set /p choice="Choix : "

if "%choice%"=="1" goto STATUS
if "%choice%"=="2" goto START
if "%choice%"=="3" goto STOP
if "%choice%"=="4" goto LOG
if "%choice%"=="5" goto TAIL
if "%choice%"=="6" goto CONSOLE
if "%choice%"=="7" goto CONTINUOUS
if "%choice%"=="8" goto CONTINUOUS_DASHBOARD
if "%choice%"=="9" goto TASKSCHD
if "%choice%"=="10" exit /b
goto MENU

:STATUS
echo.
schtasks /query /tn "%TASK_NAME%" /v /fo LIST 2>nul
if %errorlevel% neq 0 echo [!] La tâche n'existe pas. Lancez scheduler\install_task.bat.
echo.
echo === Dernier log ===
for /f "delims=" %%F in ('dir /b /o-d "%LOG_DIR%\edgecore_paper_*.log" 2^>nul') do (
    echo [Fichier: %%F]
    powershell -Command "Get-Content '%LOG_DIR%\%%F' -Tail 5 -ErrorAction SilentlyContinue"
    goto :STATUS_DONE
)
echo [!] Aucun fichier log trouvé.
:STATUS_DONE
echo.
pause
goto MENU

:START
echo.
schtasks /run /tn "%TASK_NAME%" 2>nul
if %errorlevel% equ 0 (
    echo [OK] Tick lancé en arrière-plan. Vérifiez les logs.
) else (
    echo [!] Impossible de lancer. Utilisez scheduler\install_task.bat d'abord.
)
echo.
pause
goto MENU

:STOP
echo.
schtasks /end /tn "%TASK_NAME%" 2>nul
if %errorlevel% equ 0 (
    echo [OK] Tick arrêté.
) else (
    echo [!] Aucun tick en cours (ou tâche inexistante).
)
echo.
pause
goto MENU

:LOG
echo.
echo === 50 dernières lignes du log ===
echo.
for /f "delims=" %%F in ('dir /b /o-d "%LOG_DIR%\edgecore_paper_*.log" 2^>nul') do (
    echo [Fichier: %%F]
    powershell -Command "Get-Content '%LOG_DIR%\%%F' -Tail 50 -ErrorAction SilentlyContinue"
    goto :LOG_DONE
)
echo [!] Aucun fichier log trouvé dans %LOG_DIR%
:LOG_DONE
echo.
pause
goto MENU

:TAIL
echo.
echo === Suivi en temps réel (Ctrl+C pour arrêter) ===
echo.
for /f "delims=" %%F in ('dir /b /o-d "%LOG_DIR%\edgecore_paper_*.log" 2^>nul') do (
    powershell -Command "Get-Content '%LOG_DIR%\%%F' -Tail 10 -Wait -ErrorAction SilentlyContinue"
    goto :TAIL_DONE
)
echo [!] Aucun fichier log trouvé dans %LOG_DIR%
:TAIL_DONE
echo.
pause
goto MENU

:CONSOLE
echo.
echo === Lancement en mode console (tick unique) ===
echo.
cd /d "%WORK_DIR%"
"%PYTHON_EXE%" -B "%WORK_DIR%\run_paper_tick.py"
echo.
echo [Tick terminé - code retour: %errorlevel%]
echo.
pause
goto MENU

:CONTINUOUS
echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║  PAPER TRADING CONTINU (logs seulement)                      ║
echo ║  Le bot tourne en boucle, output redirigé dans les logs      ║
echo ║  Pour le DASHBOARD PREMIUM, utilisez l'option 7             ║
echo ╠══════════════════════════════════════════════════════════════╣
echo ║  Intervalle : 86400s (24h = stratégie daily)                ║
echo ║  Chaque tick : données IB → paires → signaux → trades       ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.
cd /d "%WORK_DIR%"
"%PYTHON_EXE%" -B "%WORK_DIR%\run_paper_tick.py" --continuous --interval 86400 >> "%LOG_DIR%\edgecore_paper_continuous.log" 2>&1
echo.
echo [Paper trading arrêté - code retour: %errorlevel%]
echo.
pause
goto MENU

:CONTINUOUS_DASHBOARD
echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║  PAPER TRADING CONTINU avec DASHBOARD PREMIUM ⚡            ║
echo ║  Montre l'interface Rich en temps réel avec :                ║
echo ║    • Equity et sparkline 60-tick                            ║
echo ║    • Paires cointegrated avec statut                        ║
echo ║    • Positions ouvertes et PnL                              ║
echo ║    • Status bar avec countdown                              ║
echo ║  Appuyez Ctrl+C pour arrêter proprement                     ║
echo ╠══════════════════════════════════════════════════════════════╣
echo ║  Intervalle : 86400s (24h = stratégie daily)                ║
echo ║  Chaque tick : données IB → paires → signaux → trades       ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.
cd /d "%WORK_DIR%"
"%PYTHON_EXE%" -B "%WORK_DIR%\run_paper_tick.py" --continuous --interval 86400
echo.
echo [Paper trading arrêté - code retour: %errorlevel%]
echo.
pause
goto MENU

:TASKSCHD
taskschd.msc
goto MENU