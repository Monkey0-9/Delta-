#!/bin/bash
# Build script for DELTA Rust components.
#
# Produces:
#   rust/target/release/delta_native.dll|.so  (C ABI, loaded by native/accel.py)
#   delta_native.pyd|.so at repo root         (PyO3 extension, `import delta_native`)
set -e

echo "Building DELTA Rust components..."

cd rust

# The `python` feature enables the PyO3 extension module. The interpreter that
# runs this build determines which libpython the extension links against, so
# always rebuild after switching Python versions.
cargo build --release --features python

ROOT=".."
if [ -f "target/release/delta_native.dll" ]; then
    cp target/release/delta_native.dll "$ROOT/delta_native.pyd"
elif [ -f "target/release/libdelta_native.so" ]; then
    cp target/release/libdelta_native.so "$ROOT/delta_native.so"
fi

echo "Rust build complete!"
python -c "import delta_native; print('delta_native OK:', [n for n in dir(delta_native) if not n.startswith('_')][:4])"
cd ..
