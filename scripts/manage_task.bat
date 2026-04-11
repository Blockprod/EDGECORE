@echo off
cd /d "%~dp0.."
title EDGECORE V1 - Gestionnaire

:MENU
cls
echo.
echo  +---------------------------------------------------------+
echo  ^|  EDGECORE V1 - Gestionnaire de taches                  ^|
echo  +---------------------------------------------------------+
echo.
echo    1. Statut des taches (planificateur)
echo    2. Demarrer IB Gateway  (planificateur)
echo    3. Arreter  IB Gateway  (planificateur)
echo    4. Demarrer Bot         (planificateur)
echo    5. Arreter  Bot         (planificateur)
echo    6. Voir les dernieres lignes de log
echo    7. Lancer le bot en mode console (paper)
echo    8. Ouvrir le dashboard dans le navigateur
echo    9. Ouvrir le Planificateur de taches Windows
echo    0. Quitter
echo.
set /p CHOIX= Votre choix [0-9]: 

if "%CHOIX%"=="0" goto END
if "%CHOIX%"=="1" goto OPT_STATUS
if "%CHOIX%"=="2" goto OPT_START_IB
if "%CHOIX%"=="3" goto OPT_STOP_IB
if "%CHOIX%"=="4" goto OPT_START_BOT
if "%CHOIX%"=="5" goto OPT_STOP_BOT
if "%CHOIX%"=="6" goto OPT_LOG
if "%CHOIX%"=="7" goto OPT_CONSOLE
if "%CHOIX%"=="8" goto OPT_DASHBOARD
if "%CHOIX%"=="9" goto OPT_SCHEDULER
echo  Choix invalide.
timeout /t 1 >nul
goto MENU

:OPT_STATUS
cls
echo.
echo  == Statut IB Gateway ==
schtasks /query /tn "EDGECORE_IBGateway" /v /fo list 2>nul || echo  [!] Tache non installee
echo.
echo  == Statut Bot ==
schtasks /query /tn "EDGECORE_Bot" /v /fo list 2>nul || echo  [!] Tache non installee
echo.
pause
goto MENU

:OPT_START_IB
echo.
echo  [*] Demarrage IB Gateway...
schtasks /run /tn "EDGECORE_IBGateway"
if %errorlevel% neq 0 echo  [ERREUR] Executez install_task.bat en administrateur
pause
goto MENU

:OPT_STOP_IB
echo.
echo  [*] Arret IB Gateway...
schtasks /end /tn "EDGECORE_IBGateway" 2>nul
echo  [OK] Signal envoye.
pause
goto MENU

:OPT_START_BOT
echo.
echo  [*] Demarrage Bot...
schtasks /run /tn "EDGECORE_Bot"
if %errorlevel% neq 0 echo  [ERREUR] Executez install_task.bat en administrateur
pause
goto MENU

:OPT_STOP_BOT
echo.
echo  [*] Arret Bot...
schtasks /end /tn "EDGECORE_Bot" 2>nul
echo  [OK] Signal envoye.
pause
goto MENU

:OPT_LOG
cls
echo.
echo  == Dernieres lignes de log ==
echo.
set "LOGDIR=C:\Users\averr\EDGECORE_V1\logs"
for /f "delims=" %%F in ('dir /b /o-d "%LOGDIR%\*.log" 2^>nul') do (
    echo  Fichier: %%F
    powershell -Command "Get-Content '%LOGDIR%\%%F' -Tail 40"
    goto LOG_DONE
)
echo  Aucun log trouve dans %LOGDIR%
:LOG_DONE
echo.
pause
goto MENU

:OPT_CONSOLE
echo.
echo  [*] Lancement du bot dans une nouvelle fenetre (paper)...
start "EDGECORE Bot" "%~dp0console_bot.bat"
echo  [OK] Fenetre bot ouverte.
timeout /t 2 >nul
goto MENU

:OPT_DASHBOARD
echo.
echo  [*] Ouverture du dashboard dans le navigateur...
echo      Le bot doit etre demarre (option 4 ou 7).
start "" "http://127.0.0.1:5000/dashboard"
goto MENU

:OPT_SCHEDULER
start taskschd.msc
goto MENU

:END
exit /b 0
