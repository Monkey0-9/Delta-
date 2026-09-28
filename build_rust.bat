@echo off
REM Build script for DELTA Rust components on Windows
REM
REM Produces:
REM   rust\target\release\delta_native.dll  (C ABI, loaded by native/accel.py)
REM   delta_native.pyd at repo root          (PyO3 extension, `import delta_native`)

echo Building DELTA Rust components...

cd rust

REM The `python` feature enables the PyO3 extension module. The interpreter
REM that runs this build determines which libpython the extension links
REM against, so always rebuild after switching Python versions.
cargo build --release --features python
if errorlevel 1 (
    echo Rust build FAILED
    cd ..
    exit /b 1
)

copy /Y target\release\delta_native.dll ..\delta_native.pyd
if errorlevel 1 (
    echo Copy FAILED
    cd ..
    exit /b 1
)

echo Rust build complete!
python -c "import delta_native; print('delta_native OK')"
cd ..
