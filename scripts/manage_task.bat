@echo off
chcp 65001 >nul 2>&1
title EDGECORE V1 -- Gestion des taches
setlocal

set "TASK_IB=EDGECORE_IBGateway"
set "TASK_BOT=EDGECORE_Bot"
set "LOG_DIR=C:\Users\averr\EDGECORE_V1\logs"
set "PROJECT_DIR=C:\Users\averr\EDGECORE_V1"
set "PYTHON_EXE=C:\Users\averr\EDGECORE_V1\venv\Scripts\python.exe"

:MENU
cls
echo.
echo +==============================================================+
echo |        EDGECORE V1 -- Gestion des taches                    |
echo +==============================================================+
echo.

call :STATUS_INLINE %TASK_IB%  IB_STATUS
call :STATUS_INLINE %TASK_BOT% BOT_STATUS

echo   IB Gateway  : %IB_STATUS%
echo   Bot         : %BOT_STATUS%
echo.
echo   --------------------------------------------------------------
echo   1. Statut detaille des taches
echo   2. Demarrer IB Gateway + Bot
echo   3. Arreter le bot
echo   4. Arreter IB Gateway
echo   5. Voir les dernieres lignes du log
echo   6. Suivre le log en temps reel (Ctrl+C pour sortir)
echo   7. Lancer le bot en mode console (paper)
echo   8. Ouvrir le Planificateur de taches Windows
echo   9. Quitter
echo  10. Ouvrir le dashboard web (navigateur -- port 5000)
echo.
set /p CHOICE=Votre choix [1-10] :

if "%CHOICE%"=="1" goto OPT_STATUS
if "%CHOICE%"=="2" goto OPT_START
if "%CHOICE%"=="3" goto OPT_STOP_BOT
if "%CHOICE%"=="4" goto OPT_STOP_IB
if "%CHOICE%"=="5" goto OPT_LOG
if "%CHOICE%"=="6" goto OPT_TAIL
if "%CHOICE%"=="7" goto OPT_CONSOLE
if "%CHOICE%"=="8" goto OPT_TASKSCHD
if "%CHOICE%"=="9" goto END
if "%CHOICE%"=="10" goto OPT_DASHBOARD
goto MENU

:OPT_STATUS
cls
echo.
echo == Statut IB Gateway ==========================================
schtasks /query /tn "%TASK_IB%" /v /fo list 2>nul || echo   [!] Tache introuvable
echo.
echo == Statut Bot =================================================
schtasks /query /tn "%TASK_BOT%" /v /fo list 2>nul || echo   [!] Tache introuvable
echo.
pause
goto MENU

:OPT_START
echo.
echo [*] Verification IB Gateway...
tasklist /fi "ImageName eq ibgateway.exe" 2>nul | find /i "ibgateway.exe" >nul
if %errorlevel% equ 0 (
    echo [OK] IB Gateway deja en cours d'execution.
) else (
    schtasks /run /tn "%TASK_IB%"
    if %errorlevel% neq 0 (
        echo [ERREUR] Impossible de demarrer %TASK_IB%.
        echo          Avez-vous execute install_task.bat en admin ?
    ) else (
        echo [OK] IB Gateway demarre.
    )
)
timeout /t 5 >nul
echo [*] Demarrage Bot...
schtasks /run /tn "%TASK_BOT%"
if %errorlevel% neq 0 (
    echo [ERREUR] Impossible de demarrer %TASK_BOT%.
) else (
    echo [OK] Bot demarre.
)
pause
goto MENU

:OPT_STOP_BOT
echo.
echo [*] Arret du bot...
schtasks /end /tn "%TASK_BOT%" >nul 2>&1
echo [OK] Signal d'arret envoye au bot.
pause
goto MENU

:OPT_STOP_IB
echo.
echo [!] Attention : arreter IB Gateway coupera aussi le bot.
set /p CONFIRM=Confirmer ? (o/N) :
if /i "%CONFIRM%"=="o" (
    schtasks /end /tn "%TASK_BOT%" >nul 2>&1
    schtasks /end /tn "%TASK_IB%" >nul 2>&1
    echo [OK] IB Gateway et Bot arretes.
) else (
    echo Annule.
)
pause
goto MENU

:OPT_LOG
cls
echo.
echo == Dernieres lignes de log ====================================
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

:OPT_TAIL
cls
echo Ctrl+C pour revenir au menu.
echo ==============================================================
for /f "delims=" %%F in ('dir /b /o-d "%LOG_DIR%\*.log" 2^>nul') do (
    powershell -Command "Get-Content '%LOG_DIR%\%%F' -Tail 20 -Wait -ErrorAction SilentlyContinue"
    goto :OPT_TAIL_DONE
)
echo [!] Aucun log pour l'instant. Le bot est-il demarre ?
pause
:OPT_TAIL_DONE
goto MENU

:OPT_CONSOLE
echo.
set EDGECORE_MODE=paper
set EDGECORE_ENV=dev
set IBKR_CLIENT_ID=5
echo [*] Lancement du bot dans une nouvelle fenetre (paper)...
echo     Fermez la fenetre "EDGECORE Bot" pour arreter le bot.
start "EDGECORE Bot" cmd /k "cd /d "%PROJECT_DIR%" && "%PYTHON_EXE%" scripts\run_paper_tick.py --continuous"
echo [OK] Bot demarre. Vous pouvez maintenant lancer l'option 10.
timeout /t 2 >nul
goto MENU

:OPT_TASKSCHD
start taskschd.msc
goto MENU

:OPT_DASHBOARD
echo.
echo [*] Ouverture du dashboard web (http://127.0.0.1:5000/dashboard)...
echo     Le bot doit etre deja demarre (option 2 ou 7).
start "" "http://127.0.0.1:5000/dashboard"
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