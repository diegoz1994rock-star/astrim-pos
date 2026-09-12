<#
.SYNOPSIS
    Build de produccion de ASTRIM POS: empaqueta con PyInstaller y compila
    el instalador con Inno Setup en un solo comando.

.DESCRIPTION
    Equivalente PowerShell de build.bat. Ver README_BUILD.md (raiz del
    repo) para el detalle de cada paso y como resolver problemas comunes
    ("No module named", "No Qt platform plugin", "No such file").

.PARAMETER SkipClean
    No borrar build\/dist\/installer\dist_installer\ antes de compilar.
#>
param(
    [switch]$SkipClean
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

function Fail($message) {
    Write-Host "[ERROR] $message" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "=== ASTRIM POS - build de produccion ===" -ForegroundColor Cyan
Write-Host ""

# --- 1) Verificar Python del entorno virtual del proyecto ---
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    Fail "No existe .venv\Scripts\python.exe. Crea el entorno primero:`n          python -m venv .venv`n          .venv\Scripts\pip install -e `".[build]`""
}

# --- 2) Verificar que PyInstaller este instalado en ese venv ---
& $Python -c "import PyInstaller" 2>$null
if ($LASTEXITCODE -ne 0) {
    Fail 'PyInstaller no esta instalado en .venv. Instalalo con: .venv\Scripts\pip install -e ".[build]"'
}

# --- 3) Localizar ISCC.exe (Inno Setup) en las rutas usuales ---
$IsccCandidates = @(
    "$env:ProgramFiles(x86)\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
    "$env:LocalAppData\Programs\Inno Setup 6\ISCC.exe"
)
$Iscc = $IsccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $Iscc) {
    $onPath = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($onPath) { $Iscc = $onPath.Source }
}
if (-not $Iscc) {
    Fail "No se encontro ISCC.exe (Inno Setup). Instalalo con:`n          winget install --id JRSoftware.InnoSetup`n        o descargalo de https://jrsoftware.org/isinfo.php"
}
Write-Host "Inno Setup: $Iscc"

# --- 4) Limpiar builds anteriores ---
if (-not $SkipClean) {
    Write-Host ""
    Write-Host "--- Limpiando build\, dist\, installer\dist_installer\ ---"
    foreach ($dir in @("build", "dist", "installer\dist_installer")) {
        $full = Join-Path $RepoRoot $dir
        if (Test-Path $full) { Remove-Item -Recurse -Force $full }
    }
}

# --- 5) Empaquetar con PyInstaller ---
Write-Host ""
Write-Host "--- Paso 1/2: PyInstaller (empaquetando ASTRIM_POS.exe) ---" -ForegroundColor Cyan
& $Python -m PyInstaller installer\pos.spec --noconfirm --clean
if ($LASTEXITCODE -ne 0) { Fail "Fallo el empaquetado con PyInstaller." }
$ExePath = Join-Path $RepoRoot "dist\ASTRIM_POS\ASTRIM_POS.exe"
if (-not (Test-Path $ExePath)) { Fail "PyInstaller termino pero no se genero $ExePath" }

# --- 6) Compilar el instalador con Inno Setup ---
Write-Host ""
Write-Host "--- Paso 2/2: Inno Setup (compilando el instalador) ---" -ForegroundColor Cyan
& $Iscc "installer\setup.iss"
if ($LASTEXITCODE -ne 0) { Fail "Fallo la compilacion del instalador con Inno Setup." }

# --- 7) Armar la carpeta release\ con los artefactos finales ---
Write-Host ""
Write-Host "--- Ensamblando release\ ---" -ForegroundColor Cyan
$ReleaseDir = Join-Path $RepoRoot "release"
New-Item -ItemType Directory -Force -Path $ReleaseDir | Out-Null

$Setup = Get-ChildItem "installer\dist_installer\ASTRIM_POS_Setup_v*.exe" | Select-Object -First 1
if (-not $Setup) { Fail "Inno Setup termino pero no se encontro el instalador generado." }
Copy-Item $Setup.FullName -Destination $ReleaseDir -Force
Write-Host "  release\$($Setup.Name)"

$ReleaseAppDir = Join-Path $ReleaseDir "ASTRIM_POS"
if (Test-Path $ReleaseAppDir) { Remove-Item -Recurse -Force $ReleaseAppDir }
Copy-Item "dist\ASTRIM_POS" -Destination $ReleaseAppDir -Recurse -Force
Write-Host "  release\ASTRIM_POS\  (carpeta completa, para pruebas sin instalador)"

Copy-Item "README_BUILD.md" -Destination $ReleaseDir -Force
Copy-Item "CHANGELOG.md" -Destination $ReleaseDir -Force

Write-Host ""
Write-Host "=== Build completo ===" -ForegroundColor Green
Write-Host "Artefactos en: $ReleaseDir"
Get-ChildItem $ReleaseDir | ForEach-Object { Write-Host "  $($_.Name)" }
