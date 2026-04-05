<<<<<<< HEAD
﻿@echo off
chcp 65001 >nul 2>&1
title EDGECORE - D├®sinstallation T├óche Planifi├®e
echo.

:: ÔöÇÔöÇ V├®rifier les droits admin ÔöÇÔöÇ
=======
@echo off
chcp 65001 >nul 2>&1
title EDGECORE - Désinstallation Tâche Planifiée
echo.

:: ── Vérifier les droits admin ──
>>>>>>> origin/main
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Droits administrateur requis. Relance en tant qu'admin...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

<<<<<<< HEAD
echo [*] Arr├¬t de la t├óche EDGECORE_PAPER...
schtasks /end /tn "EDGECORE_PAPER" >nul 2>&1

echo [*] Suppression de la t├óche EDGECORE_PAPER...
schtasks /delete /tn "EDGECORE_PAPER" /f >nul 2>&1

if %errorlevel% equ 0 (
    echo [OK] T├óche EDGECORE_PAPER supprim├®e avec succ├¿s.
) else (
    echo [INFO] La t├óche EDGECORE_PAPER n'existait pas.
=======
echo [*] Arrêt de la tâche EDGECORE_PAPER...
schtasks /end /tn "EDGECORE_PAPER" >nul 2>&1

echo [*] Suppression de la tâche EDGECORE_PAPER...
schtasks /delete /tn "EDGECORE_PAPER" /f >nul 2>&1

if %errorlevel% equ 0 (
    echo [OK] Tâche EDGECORE_PAPER supprimée avec succès.
) else (
    echo [INFO] La tâche EDGECORE_PAPER n'existait pas.
>>>>>>> origin/main
)

echo.
pause
