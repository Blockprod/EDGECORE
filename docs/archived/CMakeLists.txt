cmake_minimum_required(VERSION 3.15)
project(edgecore_cpp LANGUAGES CXX)

# Set C++ standard
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_FLAGS_RELEASE "/O3 /DNDEBUG" CACHE STRING "Release flags")
set(CMAKE_CXX_FLAGS_DEBUG "/Zi /Od" CACHE STRING "Debug flags")

if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()

# Find Python - more flexible search
find_package(Python COMPONENTS Interpreter Development REQUIRED)

# Find pybind11
find_package(pybind11 CONFIG QUIET)
if(NOT pybind11_FOUND)
  message(STATUS "pybind11 not found via find_package, searching manually...")
  execute_process(
    COMMAND ${Python_EXECUTABLE} -c "import pybind11; import os; print(os.path.dirname(pybind11.__file__))"
    OUTPUT_VARIABLE pybind11_DIR
    OUTPUT_STRIP_TRAILING_WHITESPACE
    ERROR_QUIET
  )
  if(pybind11_DIR)
    message(STATUS "Found pybind11 at: ${pybind11_DIR}")
    set(pybind11_DIR "${pybind11_DIR}/share/cmake/pybind11")
    find_package(pybind11 CONFIG REQUIRED)
  else()
    message(FATAL_ERROR "Could not find pybind11. Please install: pip install pybind11")
  endif()
endif()

# Find Eigen - With fallback to header files only
find_package(Eigen3 3.3 QUIET NO_MODULE)
if(NOT Eigen3_FOUND)
  message(STATUS "Eigen3 not found via find_package, checking NumPy...")
  # Use NumPy approach - Eigen headers usually come with NumPy
  execute_process(
    COMMAND ${Python_EXECUTABLE} -c "import numpy; print(numpy.get_include())"
    OUTPUT_VARIABLE NUMPY_INCLUDE_DIR
    OUTPUT_STRIP_TRAILING_WHITESPACE
    ERROR_QUIET
  )
  
  # Create a simple header-only Eigen3 target
  add_library(Eigen3 INTERFACE)
  
  # Try multiple possible Eigen locations
  set(POSSIBLE_EIGEN_PATHS
    "/usr/include/eigen3"
    "/usr/local/include/eigen3"
    "C:/Program Files/Eigen/include"
    "${NUMPY_INCLUDE_DIR}"
  )
  
  set(EIGEN_FOUND FALSE)
  foreach(EIGEN_PATH ${POSSIBLE_EIGEN_PATHS})
    if(EXISTS "${EIGEN_PATH}/Eigen/Dense")
      set_target_properties(Eigen3 PROPERTIES
        INTERFACE_INCLUDE_DIRECTORIES "${EIGEN_PATH}"
      )
      message(STATUS "Found Eigen3 headers at: ${EIGEN_PATH}")
      set(EIGEN_FOUND TRUE)
      break()
    endif()
  endforeach()
  
  if(NOT EIGEN_FOUND)
    message(WARNING "Could not find Eigen3 headers. Using minimal Eigen subset.")
    # Provide path for pybind11 built-in Eigen
    set_target_properties(Eigen3 PROPERTIES
      INTERFACE_INCLUDE_DIRECTORIES "${pybind11_INCLUDE_DIR}/../../../include"
    )
  endif()
endif()

# Find OpenMP (optional but preferred for performance)
find_package(OpenMP QUIET)
if(NOT OPENMP_FOUND)
  message(WARNING "OpenMP not found - performance will be reduced")
  set(OPENMP_CXX_FOUND FALSE)
else()
  message(STATUS "OpenMP found: ${OpenMP_VERSION}")
endif()

# Summary
message(STATUS "═══════════════════════════════════════════════════")
message(STATUS "EDGECORE Hybrid Build Configuration")
message(STATUS "═══════════════════════════════════════════════════")
message(STATUS "Python: ${Python_EXECUTABLE}")
message(STATUS "Python Version: ${Python_VERSION}")
message(STATUS "pybind11 Version: ${pybind11_VERSION}")
message(STATUS "Eigen3 Version: ${EIGEN3_VERSION}")
message(STATUS "OpenMP: ${OpenMP_CXX_VERSION}")
message(STATUS "C++ Standard: ${CMAKE_CXX_STANDARD}")
message(STATUS "Build Type: ${CMAKE_BUILD_TYPE}")
message(STATUS "═══════════════════════════════════════════════════")

# Add source files
set(BACKTEST_SOURCES cpp/src/backtest_engine.cpp)
set(COINTEGRATION_SOURCES cpp/src/cointegration_engine.cpp)

# Create pybind11 modules - BacktestEngine
pybind11_add_module(backtest_engine_cpp ${BACKTEST_SOURCES})
target_include_directories(backtest_engine_cpp PRIVATE cpp/include)

if(OPENMP_FOUND)
  target_link_libraries(backtest_engine_cpp PRIVATE OpenMP::OpenMP_CXX)
  if(MSVC)
    # On Windows with MSVC, use static OpenMP to avoid DLL dependencies
    set_target_properties(backtest_engine_cpp PROPERTIES
      MSVC_RUNTIME_LIBRARY "MultiThreadedDLL"
    )
  endif()
endif()

if(MSVC)
  target_compile_options(backtest_engine_cpp PRIVATE /O2 /W4 /GR-)
else()
  target_compile_options(backtest_engine_cpp PRIVATE -O3 -Wall -Wextra -fno-rtti)
endif()

# Create pybind11 modules - CointegrationEngine
pybind11_add_module(cointegration_cpp ${COINTEGRATION_SOURCES})
target_include_directories(cointegration_cpp PRIVATE cpp/include)

if(OPENMP_FOUND)
  target_link_libraries(cointegration_cpp PRIVATE OpenMP::OpenMP_CXX)
  if(MSVC)
    set_target_properties(cointegration_cpp PROPERTIES
      MSVC_RUNTIME_LIBRARY "MultiThreadedDLL"
    )
  endif()
endif()

if(MSVC)
  target_compile_options(cointegration_cpp PRIVATE /O2 /W4 /GR-)
else()
  target_compile_options(cointegration_cpp PRIVATE -O3 -Wall -Wextra -fno-rtti)
endif()

# Set output directories for modules
if(MSVC)
  set_target_properties(backtest_engine_cpp PROPERTIES 
    LIBRARY_OUTPUT_DIRECTORY_RELEASE "${CMAKE_SOURCE_DIR}/edgecore"
    LIBRARY_OUTPUT_DIRECTORY_DEBUG "${CMAKE_SOURCE_DIR}/edgecore"
    PREFIX ""
    SUFFIX ".pyd"
  )
  set_target_properties(cointegration_cpp PROPERTIES
    LIBRARY_OUTPUT_DIRECTORY_RELEASE "${CMAKE_SOURCE_DIR}/edgecore"
    LIBRARY_OUTPUT_DIRECTORY_DEBUG "${CMAKE_SOURCE_DIR}/edgecore"
    PREFIX ""
    SUFFIX ".pyd"
  )
else()
  set_target_properties(backtest_engine_cpp cointegration_cpp PROPERTIES
    LIBRARY_OUTPUT_DIRECTORY "${CMAKE_SOURCE_DIR}/edgecore"
    PREFIX ""
  )
endif()

# Summary
message(STATUS "═══════════════════════════════════════════════════")
message(STATUS "EDGECORE Hybrid Build Configuration")
message(STATUS "═══════════════════════════════════════════════════")
message(STATUS "Python: ${Python_EXECUTABLE}")
message(STATUS "Python Version: ${Python_VERSION}")
message(STATUS "pybind11 Version: ${pybind11_VERSION}")
message(STATUS "Eigen3 Version: ${EIGEN3_VERSION}")
message(STATUS "OpenMP: ${OpenMP_CXX_VERSION}")
message(STATUS "C++ Standard: ${CMAKE_CXX_STANDARD}")
message(STATUS "Build Type: ${CMAKE_BUILD_TYPE}")
message(STATUS "═══════════════════════════════════════════════════")
