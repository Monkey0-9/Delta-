cmake_minimum_required(VERSION 3.20)
project(DELTA_CPP)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -O3 -march=native -ffast-math")

# Find Python
find_package(pybind11 REQUIRED)

# Create shared library
pybind11_add_module(delta_cpp
    order_book.cpp
    matching_engine.cpp
    bindings.cpp
)

# Link against Python
target_link_libraries(delta_cpp PRIVATE pybind11::module)

# Set output directory
set_target_properties(delta_cpp PROPERTIES
    LIBRARY_OUTPUT_DIRECTORY ${CMAKE_SOURCE_DIR}/../../python/delta/cpp
)