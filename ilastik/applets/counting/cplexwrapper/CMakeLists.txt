cmake_minimum_required(VERSION 2.8)
PROJECT(cplexwrapper)
set(CMAKE_MODULE_PATH ${CMAKE_CURRENT_SOURCE_DIR})
if(NOT CMAKE_BUILD_TYPE AND NOT CMAKE_CONFIGURATION_TYPES)
  message(STATUS "Setting build type to 'Debug' as none was specified.")
  set(CMAKE_BUILD_TYPE Release CACHE STRING "Choose the type of build." FORCE)
  # Set the possible values of build type for cmake-gui
  set_property(CACHE CMAKE_BUILD_TYPE PROPERTY STRINGS "Debug" "Release"
    "MinSizeRel" "RelWithDebInfo")
endif()

find_package(CPLEX REQUIRED)
include_directories(${CPLEX_INCLUDE_DIR})
set(CMAKE_C_FLAGS ${CMAKE_C_FLAGS} -fno-strict-aliasing)
add_library(cplexwrapper SHARED cplexwrapper)
target_link_libraries(cplexwrapper ${CPLEX_LIBRARY})

message(STATUS "CPlex found at: ${CPLEX_LIBRARY}")
