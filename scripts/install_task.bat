@echo off
chcp 65001 >nul 2>&1
title EDGECORE V1 - Installation Tâches Planifiées
echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║       Installation des tâches planifiées EDGECORE V1         ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

:: ── Vérifier les droits admin ──
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Droits administrateur requis. Relance en tant qu'admin...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

:: ── Variables ──
set "TASK_IB=EDGECORE_IBGateway"
set "TASK_BOT=EDGECORE_Bot"
set "PROJECT_DIR=C:\Users\averr\EDGECORE_V1"
set "IBGATEWAY_EXE=C:\Jts\ibgateway\1044\ibgateway.exe"
set "PYTHONW_EXE=C:\Users\averr\EDGECORE_V1\venv\Scripts\pythonw.exe"
set "LOG_DIR=C:\Users\averr\EDGECORE_V1\logs"

:: ── Vérifications préalables ──
if not exist "%IBGATEWAY_EXE%" (
    echo [ERREUR] IB Gateway introuvable : %IBGATEWAY_EXE%
    pause & exit /b 1
)
if not exist "%PYTHONW_EXE%" (
    echo [ERREUR] Python venv introuvable : %PYTHONW_EXE%
    pause & exit /b 1
)

:: ── Créer le dossier logs ──
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

:: ── Supprimer les anciennes tâches si elles existent ──
schtasks /query /tn "%TASK_IB%" >nul 2>&1
if %errorlevel% equ 0 (
    echo [*] Suppression ancienne tâche %TASK_IB%...
    schtasks /delete /tn "%TASK_IB%" /f >nul 2>&1
)
schtasks /query /tn "%TASK_BOT%" >nul 2>&1
if %errorlevel% equ 0 (
    echo [*] Suppression ancienne tâche %TASK_BOT%...
    schtasks /delete /tn "%TASK_BOT%" /f >nul 2>&1
)

:: ════════════════════════════════════════════════════════════
:: TÂCHE 1 : IB Gateway — démarrage au login
:: ════════════════════════════════════════════════════════════
echo [*] Création tâche %TASK_IB%...

(
echo ^<?xml version="1.0" encoding="UTF-16"?^>
echo ^<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task"^>
echo   ^<RegistrationInfo^>
echo     ^<Description^>IB Gateway paper trading ^(port 4002^) — EDGECORE auto-start^</Description^>
echo   ^</RegistrationInfo^>
echo   ^<Triggers^>
echo     ^<LogonTrigger^>
echo       ^<Enabled^>true^</Enabled^>
echo     ^</LogonTrigger^>
echo   ^</Triggers^>
echo   ^<Principals^>
echo     ^<Principal id="Author"^>
echo       ^<LogonType^>InteractiveToken^</LogonType^>
echo       ^<RunLevel^>HighestAvailable^</RunLevel^>
echo     ^</Principal^>
echo   ^</Principals^>
echo   ^<Settings^>
echo     ^<MultipleInstancesPolicy^>IgnoreNew^</MultipleInstancesPolicy^>
echo     ^<DisallowStartIfOnBatteries^>false^</DisallowStartIfOnBatteries^>
echo     ^<StopIfGoingOnBatteries^>false^</StopIfGoingOnBatteries^>
echo     ^<AllowHardTerminate^>true^</AllowHardTerminate^>
echo     ^<StartWhenAvailable^>true^</StartWhenAvailable^>
echo     ^<RunOnlyIfNetworkAvailable^>true^</RunOnlyIfNetworkAvailable^>
echo     ^<AllowStartOnDemand^>true^</AllowStartOnDemand^>
echo     ^<Enabled^>true^</Enabled^>
echo     ^<Hidden^>false^</Hidden^>
echo     ^<RunOnlyIfIdle^>false^</RunOnlyIfIdle^>
echo     ^<WakeToRun^>false^</WakeToRun^>
echo     ^<ExecutionTimeLimit^>PT0S^</ExecutionTimeLimit^>
echo     ^<Priority^>7^</Priority^>
echo     ^<RestartOnFailure^>
echo       ^<Interval^>PT2M^</Interval^>
echo       ^<Count^>10^</Count^>
echo     ^</RestartOnFailure^>
echo   ^</Settings^>
echo   ^<Actions Context="Author"^>
echo     ^<Exec^>
echo       ^<Command^>%IBGATEWAY_EXE%^</Command^>
echo       ^<WorkingDirectory^>C:\Jts\ibgateway\1044^</WorkingDirectory^>
echo     ^</Exec^>
echo   ^</Actions^>
echo ^</Task^>
) > "%TEMP%\edgecore_ibgateway.xml"

schtasks /create /tn "%TASK_IB%" /xml "%TEMP%\edgecore_ibgateway.xml" /f
if %errorlevel% neq 0 (
    echo [ERREUR] Impossible de créer la tâche %TASK_IB% !
    pause & exit /b 1
)
echo [OK] Tâche %TASK_IB% créée.

:: ════════════════════════════════════════════════════════════
:: TÂCHE 2 : Bot EDGECORE — démarre 90s après le login
::           Redémarrage automatique toutes les 5 min (999x)
::           Utilise pythonw.exe → pas de fenêtre console
:: ════════════════════════════════════════════════════════════
echo [*] Création tâche %TASK_BOT%...

(
echo ^<?xml version="1.0" encoding="UTF-16"?^>
echo ^<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task"^>
echo   ^<RegistrationInfo^>
echo     ^<Description^>EDGECORE Stat-Arb Pair Trading Bot — paper trading 24/7 auto-start^</Description^>
echo   ^</RegistrationInfo^>
echo   ^<Triggers^>
echo     ^<LogonTrigger^>
echo       ^<Enabled^>true^</Enabled^>
echo       ^<Delay^>PT1M30S^</Delay^>
echo     ^</LogonTrigger^>
echo   ^</Triggers^>
echo   ^<Principals^>
echo     ^<Principal id="Author"^>
echo       ^<LogonType^>InteractiveToken^</LogonType^>
echo       ^<RunLevel^>HighestAvailable^</RunLevel^>
echo     ^</Principal^>
echo   ^</Principals^>
echo   ^<Settings^>
echo     ^<MultipleInstancesPolicy^>IgnoreNew^</MultipleInstancesPolicy^>
echo     ^<DisallowStartIfOnBatteries^>false^</DisallowStartIfOnBatteries^>
echo     ^<StopIfGoingOnBatteries^>false^</StopIfGoingOnBatteries^>
echo     ^<AllowHardTerminate^>true^</AllowHardTerminate^>
echo     ^<StartWhenAvailable^>true^</StartWhenAvailable^>
echo     ^<RunOnlyIfNetworkAvailable^>true^</RunOnlyIfNetworkAvailable^>
echo     ^<AllowStartOnDemand^>true^</AllowStartOnDemand^>
echo     ^<Enabled^>true^</Enabled^>
echo     ^<Hidden^>false^</Hidden^>
echo     ^<RunOnlyIfIdle^>false^</RunOnlyIfIdle^>
echo     ^<WakeToRun^>false^</WakeToRun^>
echo     ^<ExecutionTimeLimit^>PT0S^</ExecutionTimeLimit^>
echo     ^<Priority^>7^</Priority^>
echo     ^<RestartOnFailure^>
echo       ^<Interval^>PT5M^</Interval^>
echo       ^<Count^>999^</Count^>
echo     ^</RestartOnFailure^>
echo   ^</Settings^>
echo   ^<Actions Context="Author"^>
echo     ^<Exec^>
echo       ^<Command^>cmd.exe^</Command^>
echo       ^<Arguments^>/c "%PROJECT_DIR%\scripts\run_bot_paper.bat"^</Arguments^>
echo       ^<WorkingDirectory^>%PROJECT_DIR%^</WorkingDirectory^>
echo     ^</Exec^>
echo   ^</Actions^>
echo ^</Task^>
) > "%TEMP%\edgecore_bot.xml"

schtasks /create /tn "%TASK_BOT%" /xml "%TEMP%\edgecore_bot.xml" /f
if %errorlevel% neq 0 (
    echo [ERREUR] Impossible de créer la tâche %TASK_BOT% !
    pause & exit /b 1
)
echo [OK] Tâche %TASK_BOT% créée.

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║                    Installation réussie !                    ║
echo ╠══════════════════════════════════════════════════════════════╣
echo ║  EDGECORE_IBGateway  →  démarre au login                     ║
echo ║  EDGECORE_Bot        →  démarre 90s après le login           ║
echo ║  Redémarrage auto    →  toutes les 5 min si crash           ║
echo ║  IBKR client_id      →  5  ^(AlphaEdge=3, pas de conflit^)   ║
echo ║                                                              ║
echo ║  Utilisez manage_task.bat pour démarrer/arrêter              ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.
del "%TEMP%\edgecore_ibgateway.xml" >nul 2>&1
del "%TEMP%\edgecore_bot.xml" >nul 2>&1
pause
