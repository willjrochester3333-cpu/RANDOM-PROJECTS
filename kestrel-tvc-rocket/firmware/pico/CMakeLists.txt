# KESTREL FC firmware for the Raspberry Pi Pico 2 W (RP2350).
#   export PICO_SDK_PATH=/path/to/pico-sdk        (SDK 2.1.x, only lib/tinyusb submodule needed)
#   cmake -S firmware/pico -B firmware/pico/build && cmake --build firmware/pico/build -j
# -> firmware/pico/build/kestrel_fc.uf2  (hold BOOTSEL, plug in USB, drag the .uf2 onto the RP2350 drive)
cmake_minimum_required(VERSION 3.13)
set(PICO_BOARD pico2_w CACHE STRING "Board type")
include(pico_sdk_import.cmake)
project(kestrel_fc C CXX ASM)
set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)
pico_sdk_init()

set(CORE ${CMAKE_CURRENT_LIST_DIR}/../core)
add_executable(kestrel_fc
    src/main.cpp
    src/hw/sensors.cpp
    src/hw/io.cpp
    src/app/logger.cpp
    src/app/settings_store.cpp
    src/logic/nmea.cpp
    src/logic/axis_cal.cpp
    src/logic/servo_map.cpp
    ${CORE}/src/flight.cpp
)
target_include_directories(kestrel_fc PRIVATE src ${CORE}/include)
target_compile_options(kestrel_fc PRIVATE -Wall -Wextra -Wno-unused-parameter -Wdouble-promotion -fno-exceptions)
target_link_libraries(kestrel_fc
    pico_stdlib hardware_spi hardware_pwm hardware_adc hardware_uart hardware_flash hardware_sync hardware_watchdog)
pico_enable_stdio_usb(kestrel_fc 1)
pico_enable_stdio_uart(kestrel_fc 0)
pico_set_program_name(kestrel_fc "KESTREL FC")
pico_set_program_version(kestrel_fc "2.02")
pico_add_extra_outputs(kestrel_fc)
