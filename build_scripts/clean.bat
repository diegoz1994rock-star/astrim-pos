@echo off
setlocal enabledelayedexpansion
rem ============================================================
rem ASTRIM POS - limpia artefactos de builds anteriores.
rem Uso: clean.bat            (borra y pregunta confirmacion)
rem      clean.bat --quiet    (borra sin preguntar, usado por build.bat)
rem ============================================================

set "SCRIPT_DIR=%~dp0"
set "REPO_ROOT=%SCRIPT_DIR%.."
cd /d "%REPO_ROOT%"

if /i not "%~1"=="--quiet" (
    echo Se van a borrar: build\  dist\  installer\dist_installer\
    set /p CONFIRM="Continuar? (S/N): "
    if /i not "!CONFIRM!"=="S" (
        echo Cancelado.
        exit /b 0
    )
)

if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist "installer\dist_installer" rmdir /s /q "installer\dist_installer"

echo Listo: build\, dist\ e installer\dist_installer\ eliminados.
endlocal
