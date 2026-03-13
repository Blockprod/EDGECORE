@echo off
chcp 65001 >nul 2>&1
title EDGECORE - Installation Tâche Planifiée
echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║     Installation de la tâche planifiée EDGECORE_PAPER       ║
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
set "TASK_NAME=EDGECORE_PAPER"
set "WORK_DIR=C:\Users\averr\EDGECORE"
set "PYTHON_EXE=C:\Users\averr\EDGECORE\venv\Scripts\pythonw.exe"
set "SCRIPT_PATH=C:\Users\averr\EDGECORE\run_paper_tick.py"
set "LOG_DIR=C:\Users\averr\EDGECORE\logs"

:: ── Créer le dossier logs ──
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

:: ── Supprimer l'ancienne tâche si elle existe ──
schtasks /query /tn "%TASK_NAME%" >nul 2>&1
if %errorlevel% equ 0 (
    echo [*] Suppression de l'ancienne tâche...
    schtasks /delete /tn "%TASK_NAME%" /f >nul 2>&1
)

:: ── Créer le fichier XML de la tâche planifiée ──
echo [*] Création de la tâche planifiée...

(
echo ^<?xml version="1.0" encoding="UTF-16"?^>
echo ^<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task"^>
echo   ^<RegistrationInfo^>
echo     ^<Description^>EDGECORE Paper Trading - Stat-arb pairs daily tick (16:05 EST / 22:05 CET)^</Description^>
echo   ^</RegistrationInfo^>
echo   ^<Triggers^>
echo     ^<CalendarTrigger^>
echo       ^<StartBoundary^>2026-03-04T22:05:00^</StartBoundary^>
echo       ^<Enabled^>true^</Enabled^>
echo       ^<ScheduleByWeek^>
echo         ^<DaysOfWeek^>
echo           ^<Monday /^>
echo           ^<Tuesday /^>
echo           ^<Wednesday /^>
echo           ^<Thursday /^>
echo           ^<Friday /^>
echo         ^</DaysOfWeek^>
echo         ^<WeeksInterval^>1^</WeeksInterval^>
echo       ^</ScheduleByWeek^>
echo     ^</CalendarTrigger^>
echo   ^</Triggers^>
echo   ^<Principals^>
echo     ^<Principal id="Author"^>
echo       ^<LogonType^>InteractiveToken^</LogonType^>
echo       ^<RunLevel^>LeastPrivilege^</RunLevel^>
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
echo     ^<ExecutionTimeLimit^>PT30M^</ExecutionTimeLimit^>
echo     ^<Priority^>7^</Priority^>
echo     ^<RestartOnFailure^>
echo       ^<Interval^>PT5M^</Interval^>
echo       ^<Count^>3^</Count^>
echo     ^</RestartOnFailure^>
echo   ^</Settings^>
echo   ^<Actions Context="Author"^>
echo     ^<Exec^>
echo       ^<Command^>%PYTHON_EXE%^</Command^>
echo       ^<Arguments^>-B "%SCRIPT_PATH%"^</Arguments^>
echo       ^<WorkingDirectory^>%WORK_DIR%^</WorkingDirectory^>
echo     ^</Exec^>
echo   ^</Actions^>
echo ^</Task^>
) > "%TEMP%\edgecore_paper_task.xml"

:: ── Importer la tâche ──
schtasks /create /tn "%TASK_NAME%" /xml "%TEMP%\edgecore_paper_task.xml" /f
if %errorlevel% neq 0 (
    echo [ERREUR] Impossible de créer la tâche planifiée !
    pause
    exit /b 1
)

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║                    Installation réussie !                    ║
echo ╠══════════════════════════════════════════════════════════════╣
echo ║  Tâche : EDGECORE_PAPER                                     ║
echo ║  Horaire : Lun-Ven à 22:05 CET (16:05 EST après clôture)   ║
echo ║  Script : run_paper_tick.py (single tick puis exit)          ║
echo ║  Timeout : 30 min max par exécution                         ║
echo ║  Retry : 3 tentatives espacées de 5 min en cas d'erreur     ║
echo ║  Logs : C:\Users\averr\EDGECORE\logs\                       ║
echo ║                                                              ║
echo ║  Utilisez manage_task.bat pour gérer la tâche.               ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.
del "%TEMP%\edgecore_paper_task.xml" >nul 2>&1
pause
