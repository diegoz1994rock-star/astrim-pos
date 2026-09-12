@echo off
setlocal enabledelayedexpansion
rem ============================================================
rem ASTRIM POS - build de produccion (Windows)
rem Empaqueta con PyInstaller y compila el instalador con Inno
rem Setup en un solo comando. Ver README_BUILD.md (raiz del repo)
rem para el detalle de cada paso y como solucionar problemas.
rem ============================================================

set "SCRIPT_DIR=%~dp0"
set "REPO_ROOT=%SCRIPT_DIR%.."
cd /d "%REPO_ROOT%"

echo.
echo === ASTRIM POS - build de produccion ===
echo.

rem --- 1) Verificar Python del entorno virtual del proyecto ---
if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] No existe .venv\Scripts\python.exe
    echo         Crea el entorno primero:
    echo           python -m venv .venv
    echo           .venv\Scripts\pip install -e ".[build]"
    exit /b 1
)
set "PY=%REPO_ROOT%\.venv\Scripts\python.exe"

rem --- 2) Verificar que PyInstaller este instalado en ese venv ---
"%PY%" -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] PyInstaller no esta instalado en .venv
    echo         Instalalo con: .venv\Scripts\pip install -e ".[build]"
    exit /b 1
)

rem --- 3) Localizar ISCC.exe (Inno Setup) en las rutas usuales ---
set "ISCC="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if exist "%LocalAppData%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LocalAppData%\Programs\Inno Setup 6\ISCC.exe"
if "%ISCC%"=="" (
    for /f "delims=" %%I in ('where ISCC.exe 2^>nul') do set "ISCC=%%I"
)
if "%ISCC%"=="" (
    echo [ERROR] No se encontro ISCC.exe ^(Inno Setup^).
    echo         Instalalo con: winget install --id JRSoftware.InnoSetup
    echo         o descargalo de https://jrsoftware.org/isinfo.php
    exit /b 1
)
echo Inno Setup: %ISCC%

rem --- 4) Limpiar builds anteriores (build/, dist/, dist_installer) ---
call "%SCRIPT_DIR%clean.bat" --quiet

rem --- 5) Empaquetar con PyInstaller ---
echo.
echo --- Paso 1/2: PyInstaller (empaquetando ASTRIM_POS.exe) ---
"%PY%" -m PyInstaller installer\pos.spec --noconfirm --clean
if errorlevel 1 (
    echo [ERROR] Fallo el empaquetado con PyInstaller.
    exit /b 1
)
if not exist "dist\ASTRIM_POS\ASTRIM_POS.exe" (
    echo [ERROR] PyInstaller termino pero no se genero dist\ASTRIM_POS\ASTRIM_POS.exe
    exit /b 1
)

rem --- 6) Compilar el instalador con Inno Setup ---
echo.
echo --- Paso 2/2: Inno Setup (compilando el instalador) ---
"%ISCC%" installer\setup.iss
if errorlevel 1 (
    echo [ERROR] Fallo la compilacion del instalador con Inno Setup.
    exit /b 1
)

rem --- 7) Armar la carpeta release/ con los artefactos finales ---
echo.
echo --- Ensamblando release\ ---
if not exist "release" mkdir "release"
for %%F in (installer\dist_installer\ASTRIM_POS_Setup_v*.exe) do (
    copy /y "%%F" "release\" >nul
    echo   release\%%~nxF
)
xcopy /e /i /y /q "dist\ASTRIM_POS" "release\ASTRIM_POS" >nul
echo   release\ASTRIM_POS\  (carpeta completa, para pruebas sin instalador)
copy /y "README_BUILD.md" "release\" >nul
copy /y "CHANGELOG.md" "release\" >nul

echo.
echo === Build completo ===
echo Artefactos en: %REPO_ROOT%\release\
dir /b "release"
endlocal
