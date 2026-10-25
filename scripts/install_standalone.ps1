# ==============================================================================
# DELTA OS — 1-Click Institutional Standalone Local Installer (Windows PowerShell)
# ==============================================================================
$ErrorActionPreference = "Stop"

Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "DELTA OS — INSTITUTIONAL STANDALONE LOCAL INSTALLER (WINDOWS)" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan

# 1. Check Python
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "python was not found on PATH. Please install Python 3.11+ from python.org."
    exit 1
}

$pyVer = python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
Write-Host "✓ Verified Python $pyVer" -ForegroundColor Green

# 2. Virtual Environment
if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment in .venv..."
    python -m venv .venv
}

& .venv\Scripts\Activate.ps1
Write-Host "✓ Activated .venv" -ForegroundColor Green

# 3. Dependencies
Write-Host "Installing dependencies..."
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
pip install -e . --quiet
Write-Host "✓ Dependencies installed" -ForegroundColor Green

# 4. Build Rust Native if cargo present
if (Get-Command cargo -ErrorAction SilentlyContinue) {
    Write-Host "Building native Rust SIMD acceleration kernels & TUI..."
    cargo build --release --workspace
    Write-Host "✓ Native Rust acceleration ready" -ForegroundColor Green
} else {
    Write-Host "NOTICE: 'cargo' not found in PATH. Using high-performance NumPy fallbacks." -ForegroundColor Yellow
}

# 5. Delta Home directory
$deltaHome = Join-Path $env:USERPROFILE ".delta"
if (-not (Test-Path $deltaHome)) {
    New-Item -ItemType Directory -Path $deltaHome -Force | Out-Null
}

# 6. Run Doctor
Write-Host "Running institutional verification doctor..."
python -m apps.cli.main doctor --institutional

Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "DELTA OS INSTALLATION COMPLETE" -ForegroundColor Green
Write-Host "  Launch Native Rust TUI : cargo run --manifest-path tui/Cargo.toml"
Write-Host "  Launch Master CLI      : python -m apps.cli.main --help"
Write-Host "  Run Live Watchlist     : python -m apps.cli.main watchlist"
Write-Host "================================================================================" -ForegroundColor Cyan
