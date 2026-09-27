@echo off
REM Build script for C++ components on Windows

echo Building DELTA C++ components...

REM Create build directory
if not exist build\cpp mkdir build\cpp
cd build\cpp

REM Configure with CMake
cmake ..\..\src\cpp -G "MinGW Makefiles" -DCMAKE_BUILD_TYPE=Release

REM Build
cmake --build . --config Release

REM Copy to Python module directory
if not exist ..\..\python\delta\cpp mkdir ..\..\python\delta\cpp
copy delta_cpp*.pyd ..\..\python\delta\cpp\ 2>nul || copy delta_cpp*.dll ..\..\python\delta\cpp\ 2>nul || echo Copy failed

echo C++ build complete!
cd ..\..