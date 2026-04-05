<<<<<<< HEAD
﻿@echo off
chcp 65001 >nul 2>&1
title EDGECORE - Gestion de la T├óche Planifi├®e
=======
@echo off
chcp 65001 >nul 2>&1
title EDGECORE - Gestion de la Tâche Planifiée
>>>>>>> origin/main
set "TASK_NAME=EDGECORE_PAPER"
set "LOG_DIR=C:\Users\averr\EDGECORE\logs"
set "WORK_DIR=C:\Users\averr\EDGECORE"
set "PYTHON_EXE=C:\Users\averr\EDGECORE\venv\Scripts\python.exe"

:MENU
cls
echo.
<<<<<<< HEAD
echo ÔòöÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòù
echo Ôòæ        EDGECORE Paper Trading - Gestion T├óche Planifi├®e      Ôòæ
echo ÔòáÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòú
echo Ôòæ  1. Voir le statut de la t├óche                               Ôòæ
echo Ôòæ  2. Lancer un tick manuellement (arri├¿re-plan)               Ôòæ
echo Ôòæ  3. Arr├¬ter le tick en cours                                 Ôòæ
echo Ôòæ  4. Voir les derni├¿res lignes du log                         Ôòæ
echo Ôòæ  5. Suivre le log en temps r├®el                              Ôòæ
echo Ôòæ  6. Lancer un tick unique (visible, logs seulement)          Ôòæ
echo Ôòæ  7. PAPER TRADING CONTINU (logs seulement, no dashboard)    Ôòæ
echo Ôòæ  8. PAPER TRADING CONTINU avec DASHBOARD PREMIUM ÔÜí (Ctrl+C)Ôòæ
echo Ôòæ  9. Ouvrir le Planificateur de t├óches Windows                Ôòæ
echo Ôòæ  10. Quitter                                                  Ôòæ
echo ÔòÜÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòØ
=======
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
>>>>>>> origin/main
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
<<<<<<< HEAD
if %errorlevel% neq 0 echo [!] La t├óche n'existe pas. Lancez scheduler\install_task.bat.
=======
if %errorlevel% neq 0 echo [!] La tâche n'existe pas. Lancez scheduler\install_task.bat.
>>>>>>> origin/main
echo.
echo === Dernier log ===
for /f "delims=" %%F in ('dir /b /o-d "%LOG_DIR%\edgecore_paper_*.log" 2^>nul') do (
    echo [Fichier: %%F]
    powershell -Command "Get-Content '%LOG_DIR%\%%F' -Tail 5 -ErrorAction SilentlyContinue"
    goto :STATUS_DONE
)
<<<<<<< HEAD
echo [!] Aucun fichier log trouv├®.
=======
echo [!] Aucun fichier log trouvé.
>>>>>>> origin/main
:STATUS_DONE
echo.
pause
goto MENU

:START
echo.
schtasks /run /tn "%TASK_NAME%" 2>nul
if %errorlevel% equ 0 (
<<<<<<< HEAD
    echo [OK] Tick lanc├® en arri├¿re-plan. V├®rifiez les logs.
=======
    echo [OK] Tick lancé en arrière-plan. Vérifiez les logs.
>>>>>>> origin/main
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
<<<<<<< HEAD
    echo [OK] Tick arr├¬t├®.
) else (
    echo [!] Aucun tick en cours (ou t├óche inexistante).
=======
    echo [OK] Tick arrêté.
) else (
    echo [!] Aucun tick en cours (ou tâche inexistante).
>>>>>>> origin/main
)
echo.
pause
goto MENU

:LOG
echo.
<<<<<<< HEAD
echo === 50 derni├¿res lignes du log ===
=======
echo === 50 dernières lignes du log ===
>>>>>>> origin/main
echo.
for /f "delims=" %%F in ('dir /b /o-d "%LOG_DIR%\edgecore_paper_*.log" 2^>nul') do (
    echo [Fichier: %%F]
    powershell -Command "Get-Content '%LOG_DIR%\%%F' -Tail 50 -ErrorAction SilentlyContinue"
    goto :LOG_DONE
)
<<<<<<< HEAD
echo [!] Aucun fichier log trouv├® dans %LOG_DIR%
=======
echo [!] Aucun fichier log trouvé dans %LOG_DIR%
>>>>>>> origin/main
:LOG_DONE
echo.
pause
goto MENU

:TAIL
echo.
<<<<<<< HEAD
echo === Suivi en temps r├®el (Ctrl+C pour arr├¬ter) ===
=======
echo === Suivi en temps réel (Ctrl+C pour arrêter) ===
>>>>>>> origin/main
echo.
for /f "delims=" %%F in ('dir /b /o-d "%LOG_DIR%\edgecore_paper_*.log" 2^>nul') do (
    powershell -Command "Get-Content '%LOG_DIR%\%%F' -Tail 10 -Wait -ErrorAction SilentlyContinue"
    goto :TAIL_DONE
)
<<<<<<< HEAD
echo [!] Aucun fichier log trouv├® dans %LOG_DIR%
=======
echo [!] Aucun fichier log trouvé dans %LOG_DIR%
>>>>>>> origin/main
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
<<<<<<< HEAD
echo [Tick termin├® - code retour: %errorlevel%]
=======
echo [Tick terminé - code retour: %errorlevel%]
>>>>>>> origin/main
echo.
pause
goto MENU

:CONTINUOUS
echo.
<<<<<<< HEAD
echo ÔòöÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòù
echo Ôòæ  PAPER TRADING CONTINU (logs seulement)                      Ôòæ
echo Ôòæ  Le bot tourne en boucle, output redirig├® dans les logs      Ôòæ
echo Ôòæ  Pour le DASHBOARD PREMIUM, utilisez l'option 7             Ôòæ
echo ÔòáÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòú
echo Ôòæ  Intervalle : 86400s (24h = strat├®gie daily)                Ôòæ
echo Ôòæ  Chaque tick : donn├®es IB ÔåÆ paires ÔåÆ signaux ÔåÆ trades       Ôòæ
echo ÔòÜÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòØ
=======
echo ╔══════════════════════════════════════════════════════════════╗
echo ║  PAPER TRADING CONTINU (logs seulement)                      ║
echo ║  Le bot tourne en boucle, output redirigé dans les logs      ║
echo ║  Pour le DASHBOARD PREMIUM, utilisez l'option 7             ║
echo ╠══════════════════════════════════════════════════════════════╣
echo ║  Intervalle : 86400s (24h = stratégie daily)                ║
echo ║  Chaque tick : données IB → paires → signaux → trades       ║
echo ╚══════════════════════════════════════════════════════════════╝
>>>>>>> origin/main
echo.
cd /d "%WORK_DIR%"
"%PYTHON_EXE%" -B "%WORK_DIR%\run_paper_tick.py" --continuous --interval 86400 >> "%LOG_DIR%\edgecore_paper_continuous.log" 2>&1
echo.
<<<<<<< HEAD
echo [Paper trading arr├¬t├® - code retour: %errorlevel%]
=======
echo [Paper trading arrêté - code retour: %errorlevel%]
>>>>>>> origin/main
echo.
pause
goto MENU

:CONTINUOUS_DASHBOARD
echo.
<<<<<<< HEAD
echo ÔòöÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòù
echo Ôòæ  PAPER TRADING CONTINU avec DASHBOARD PREMIUM ÔÜí            Ôòæ
echo Ôòæ  Montre l'interface Rich en temps r├®el avec :                Ôòæ
echo Ôòæ    ÔÇó Equity et sparkline 60-tick                            Ôòæ
echo Ôòæ    ÔÇó Paires cointegrated avec statut                        Ôòæ
echo Ôòæ    ÔÇó Positions ouvertes et PnL                              Ôòæ
echo Ôòæ    ÔÇó Status bar avec countdown                              Ôòæ
echo Ôòæ  Appuyez Ctrl+C pour arr├¬ter proprement                     Ôòæ
echo ÔòáÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòú
echo Ôòæ  Intervalle : 86400s (24h = strat├®gie daily)                Ôòæ
echo Ôòæ  Chaque tick : donn├®es IB ÔåÆ paires ÔåÆ signaux ÔåÆ trades       Ôòæ
echo ÔòÜÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòØ
=======
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
>>>>>>> origin/main
echo.
cd /d "%WORK_DIR%"
"%PYTHON_EXE%" -B "%WORK_DIR%\run_paper_tick.py" --continuous --interval 86400
echo.
<<<<<<< HEAD
echo [Paper trading arr├¬t├® - code retour: %errorlevel%]
=======
echo [Paper trading arrêté - code retour: %errorlevel%]
>>>>>>> origin/main
echo.
pause
goto MENU

:TASKSCHD
taskschd.msc
<<<<<<< HEAD
goto MENU
=======
goto MENU
>>>>>>> origin/main
