#Requires -Version 5.1
<#
.SYNOPSIS
    SQLite Manager PowerShell Build Script

.DESCRIPTION
    Professional build pipeline for SQLite Manager.
    Wraps scripts/build.py with a polished PowerShell interface.

.PARAMETER Mode
    Build mode: build|onefile|debug|portable|installer|all|clean|nuitka
    Default: build

.PARAMETER Sign
    Path to .pfx code signing certificate

.PARAMETER SignPassword
    Password for the signing certificate

.PARAMETER NoPause
    Skip the end pause (useful for CI)

.EXAMPLE
    .\build.ps1                     # Production one-dir
    .\build.ps1 -Mode onefile       # Single .exe
    .\build.ps1 -Mode all           # Full release pipeline
    .\build.ps1 -Mode installer     # With Inno Setup
    .\build.ps1 -Mode portable      # With portable ZIP
    .\build.ps1 -Mode clean         # Clean artifacts
#>

param(
    [ValidateSet("build","onefile","debug","portable","installer","all","clean","nuitka","verify")]
    [string]$Mode = "build",
    [string]$Sign = "",
    [string]$SignPassword = "",
    [switch]$NoPause
)

$ErrorActionPreference = "Stop"
$Host.UI.RawUI.WindowTitle = "SQLite Manager Build"

# ── Colors ────────────────────────────────────────────────────────────────────
function Write-Banner([string]$msg) {
    Write-Host ""
    Write-Host ("=" * 60) -ForegroundColor DarkCyan
    Write-Host "  $msg" -ForegroundColor Cyan
    Write-Host ("=" * 60) -ForegroundColor DarkCyan
}

function Write-Ok([string]$msg)   { Write-Host "  [OK]  $msg" -ForegroundColor Green }
function Write-Warn([string]$msg) { Write-Host "  [WARN] $msg" -ForegroundColor Yellow }
function Write-Err([string]$msg)  { Write-Host "  [ERR] $msg" -ForegroundColor Red }
function Write-Info([string]$msg) { Write-Host "  $msg" -ForegroundColor Gray }

# ── Checks ────────────────────────────────────────────────────────────────────
Write-Banner "SQLite Manager Build System"

# Python — prefer .venv (Python 3.12) over system Python to avoid 3.14 bootloader issues
$PYTHON = if (Test-Path ".venv\Scripts\python.exe") { ".venv\Scripts\python.exe" } else { "python" }
try {
    $pyVersion = & $PYTHON --version 2>&1
    Write-Ok "Python: $pyVersion  ($PYTHON)"
} catch {
    Write-Err "Python not found. Create a .venv with Python 3.12: py -3.12 -m venv .venv"
    exit 1
}

# Check we are in the right directory
if (-not (Test-Path "main.py")) {
    Write-Err "Run this script from the project root (where main.py is)."
    exit 1
}

# ── Install PyInstaller if missing ────────────────────────────────────────────
$piCheck = & python -m PyInstaller --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Warn "PyInstaller not installed. Installing..."
    & python -m pip install pyinstaller --quiet
}

# ── Read current version ──────────────────────────────────────────────────────
try {
    $version = & python -c "from app.version import VERSION; print(VERSION)" 2>&1
    Write-Ok "Version: $version"
} catch {
    $version = "unknown"
}

# ── Execution time ────────────────────────────────────────────────────────────
$startTime = Get-Date

# ── Mode dispatch ─────────────────────────────────────────────────────────────
Write-Banner "Mode: $Mode"

switch ($Mode) {
    "clean" {
        Write-Info "Cleaning build artifacts..."
        & python scripts\clean.py --full
    }
    "build" {
        Write-Info "Building production one-dir executable..."
        & python scripts\build.py
    }
    "onefile" {
        Write-Info "Building single-file executable..."
        & python scripts\build.py --onefile
    }
    "debug" {
        Write-Info "Building debug executable (console enabled)..."
        & python scripts\build.py --debug
    }
    "portable" {
        Write-Info "Building production + portable ZIP..."
        & python scripts\build.py --portable
    }
    "installer" {
        Write-Info "Building production + Inno Setup installer..."
        & python scripts\build.py --installer
    }
    "all" {
        Write-Info "Running full release pipeline..."
        $buildArgs = @("scripts\build.py", "--all")
        if ($Sign) { $buildArgs += @("--sign", $Sign, "--sign-pass", $SignPassword) }
        & python @buildArgs
    }
    "nuitka" {
        Write-Info "Building with Nuitka (optimized)..."
        & python -m pip install nuitka --quiet
        & python scripts\build.py --nuitka
    }
    "verify" {
        Write-Info "Running verification suite..."
        $env:PYTHONIOENCODING = "utf-8"
        & python verify.py
    }
}

$exitCode = $LASTEXITCODE
$elapsed = (Get-Date) - $startTime

# ── Result ────────────────────────────────────────────────────────────────────
Write-Banner "Result"
if ($exitCode -eq 0) {
    Write-Ok "Build SUCCEEDED in $([math]::Round($elapsed.TotalSeconds, 1))s"
    Write-Info "Version : $version"

    # List output files
    $distDir = "dist"
    if (Test-Path $distDir) {
        Write-Info "Output files:"
        Get-ChildItem $distDir -Recurse -File | Where-Object { $_.Extension -in ".exe",".zip" } | ForEach-Object {
            $sizeMB = [math]::Round($_.Length / 1MB, 1)
            Write-Info "  $($_.Name)  ($sizeMB MB)"
        }
    }
    $relDir = "releases"
    if (Test-Path $relDir) {
        Get-ChildItem $relDir -File | ForEach-Object {
            $sizeMB = [math]::Round($_.Length / 1MB, 1)
            Write-Ok "  releases\$($_.Name)  ($sizeMB MB)"
        }
    }
} else {
    Write-Err "Build FAILED with exit code $exitCode"
}

if (-not $NoPause) {
    Write-Host ""
    Write-Host "  Press any key to exit..." -ForegroundColor DarkGray
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
}

exit $exitCode
