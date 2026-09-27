#!/bin/bash
# Build script for C++ components

set -e

echo "Building DELTA C++ components..."

# Create build directory
mkdir -p build/cpp
cd build/cpp

# Configure with CMake
cmake ../../src/cpp -DCMAKE_BUILD_TYPE=Release

# Build
cmake --build . --config Release

# Copy to Python module directory
mkdir -p ../../python/delta/cpp
cp delta_cpp*.so ../../python/delta/cpp/ 2>/dev/null || cp delta_cpp*.pyd ../../python/delta/cpp/ 2>/dev/null || true

echo "C++ build complete!"