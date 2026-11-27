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

add_library(kestrel_core STATIC core/src/flight.cpp core/src/telemetry.cpp)
target_include_directories(kestrel_core PUBLIC core/include)

add_library(kestrel_sil SHARED sil/kestrel_sil.cpp)
target_link_libraries(kestrel_sil PRIVATE kestrel_core)

enable_testing()
add_executable(core_tests core/tests/test_core.cpp)
target_link_libraries(core_tests PRIVATE kestrel_core)
add_test(NAME core_tests COMMAND core_tests)

# Host tests for the hardware-independent parts of the Pico firmware (NMEA, axis calibration,
# servo mapping, settings CRC, flash logger against a RAM model of the W25Q128, radio telemetry link).
add_executable(pico_logic_tests
    pico/tests/test_logic.cpp
    pico/src/logic/nmea.cpp pico/src/logic/axis_cal.cpp pico/src/logic/servo_map.cpp
    pico/src/logic/radio_link.cpp pico/src/app/logger.cpp)
target_include_directories(pico_logic_tests PRIVATE pico/tests/fake pico/src core/include)
target_link_libraries(pico_logic_tests PRIVATE kestrel_core)
add_test(NAME pico_logic_tests COMMAND pico_logic_tests)
