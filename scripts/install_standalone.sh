#!/usr/bin/env bash
# ==============================================================================
# DELTA OS — 1-Click Institutional Standalone Local Installer (Linux / macOS)
# ==============================================================================
set -euo pipefail

echo "================================================================================"
echo "DELTA OS — INSTITUTIONAL STANDALONE LOCAL INSTALLER"
echo "================================================================================"

# 1. Verify Python 3.11+ is present
if ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 not found. Please install Python 3.11 or newer." >&2
    exit 1
fi

PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PY_MAJOR=$(echo "$PY_VER" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VER" | cut -d. -f2)

if [ "$PY_MAJOR" -lt 3 ] || [ "$PY_MINOR" -lt 11 ]; then
    echo "ERROR: Python 3.11+ required. Found Python $PY_VER." >&2
    exit 1
fi
echo "✓ Verified Python $PY_VER"

# 2. Setup Virtual Environment
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment in .venv..."
    python3 -m venv .venv
fi

source .venv/bin/activate
echo "✓ Activated .venv"

# 3. Install Dependencies
echo "Installing dependencies..."
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
pip install -e . --quiet
echo "✓ Dependencies installed"

# 4. Build Rust Native Kernels & TUI if cargo is available
if command -v cargo &>/dev/null; then
    echo "Building native Rust SIMD acceleration kernels & TUI..."
    cargo build --release --workspace
    echo "✓ Native Rust acceleration ready"
else
    echo "NOTICE: 'cargo' not found in PATH. Using high-performance vectorized NumPy fallbacks."
    export DELTA_ALLOW_NUMPY_FALLBACK=1
fi

# 5. Initialize secure configuration directory
mkdir -p "$HOME/.delta"
chmod 700 "$HOME/.delta"

# 6. Run Institutional Verification Doctor
echo "Running institutional verification doctor..."
python -m apps.cli.main doctor --institutional

echo "================================================================================"
echo "DELTA OS INSTALLATION COMPLETE"
echo "  Launch Native Rust TUI : cargo run --manifest-path tui/Cargo.toml"
echo "  Launch Master CLI      : python -m apps.cli.main --help"
echo "  Run Live Watchlist     : python -m apps.cli.main watchlist"
echo "================================================================================"
