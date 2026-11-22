// KESTREL FC v1.0 - Raspberry Pi Pico 2 W pin map (source of truth: pcb/circuit.py)
#pragma once
#include "pico/types.h"

namespace board {

constexpr uint GPS_TX = 0;          // UART0 TX -> ATGM336H RXD
constexpr uint GPS_RX = 1;          // UART0 RX <- ATGM336H TXD
constexpr uint GPS_PPS = 2;
constexpr uint SERVO_PWR_OFF = 3;   // high = servo 5 V buck OFF (board pull-down keeps it ON by default)
constexpr uint I2C_SDA = 4;         // Qwiic expansion (I2C0), 4.7k pull-ups on the board
constexpr uint I2C_SCL = 5;
constexpr uint SERVO_PWM[4] = {6, 7, 8, 9};   // 1 TVC ring, 2 TVC motor holder, 3 deploy latch, 4 aux/camera
constexpr uint BUZZER = 10;         // high = on (active 3 V buzzer via AO3400A)
constexpr uint LED_GREEN = 11;      // high = on
constexpr uint LED_RED = 12;        // high = on
constexpr uint AUX_PWR_EN = 13;     // high = AUX 5 V on (camera / Qwiic accessories)
constexpr uint BUTTON = 14;         // USER button to GND (internal pull-up)
constexpr uint IMU_INT1 = 15;
constexpr uint SPI_MISO = 16;       // SPI0 RX
constexpr uint CS_IMU = 17;         // LSM6DSO
constexpr uint SPI_SCK = 18;
constexpr uint SPI_MOSI = 19;       // SPI0 TX
constexpr uint CS_BARO = 20;        // BMP580
constexpr uint CS_FLASH = 21;       // W25Q128JV (16 MB flight log)
constexpr uint BARO_INT = 22;
constexpr uint ADC_VBAT = 26;       // ADC0: switched battery via 100k/33k
constexpr uint ADC_CELL1 = 27;      // ADC1: cell-1 tap via 1M/1M
constexpr uint ADC_SERVO_V = 28;    // ADC2: servo 5 V rail via 100k/100k

constexpr float VBAT_DIV = (100.0f + 33.0f) / 33.0f;
constexpr float CELL1_DIV = 2.0f;
constexpr float SERVO_V_DIV = 2.0f;
constexpr float ADC_VREF = 3.30f;

constexpr unsigned LOOP_HZ = 500;   // flight-core rate (matches the simulator / SIL tests)
constexpr unsigned SPI_HZ = 8000000;

}  // namespace board
