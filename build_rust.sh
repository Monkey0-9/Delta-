#!/bin/bash
# Build script for Rust components

set -e

echo "Building DELTA Rust components..."

cd src/rust

# Build release version
cargo build --release

# Copy to Python module directory
mkdir -p ../../python/delta/rust
cp target/release/libdelta_rust.so ../../python/delta/rust/ 2>/dev/null || cp target/release/delta_rust.dll ../../python/delta/rust/ 2>/dev/null || cp target/release/delta_rust.pyd ../../python/delta/rust/ 2>/dev/null || true

echo "Rust build complete!"
cd ../..