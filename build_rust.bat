@echo off
REM Build script for Rust components on Windows

echo Building DELTA Rust components...

cd src\rust

REM Build release version
cargo build --release

REM Copy to Python module directory
if not exist ..\..\python\delta\rust mkdir ..\..\python\delta\rust
copy target\release\delta_rust.dll ..\..\python\delta\rust\ 2>nul || copy target\release\delta_rust.pyd ..\..\python\delta\rust\ 2>nul || echo Copy failed

echo Rust build complete!
cd ..\..