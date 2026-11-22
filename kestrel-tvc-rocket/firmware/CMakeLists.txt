# Host build of the KESTREL flight core: unit tests + software-in-the-loop library.
# (The Raspberry Pi Pico 2 W firmware has its own CMake project in firmware/pico/.)
cmake_minimum_required(VERSION 3.16)
project(kestrel_core CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()
add_compile_options(-Wall -Wextra -Wpedantic -Wshadow -Wdouble-promotion -Werror)

add_library(kestrel_core STATIC core/src/flight.cpp)
target_include_directories(kestrel_core PUBLIC core/include)

add_library(kestrel_sil SHARED sil/kestrel_sil.cpp)
target_link_libraries(kestrel_sil PRIVATE kestrel_core)

enable_testing()
add_executable(core_tests core/tests/test_core.cpp)
target_link_libraries(core_tests PRIVATE kestrel_core)
add_test(NAME core_tests COMMAND core_tests)
