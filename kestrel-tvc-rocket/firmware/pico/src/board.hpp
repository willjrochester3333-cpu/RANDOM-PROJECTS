// KESTREL FC v3.0 - Raspberry Pi Pico 2 W pin map (source of truth: pcb/circuit.py)
#pragma once
#include "pico/types.h"

namespace board {

constexpr uint GPS_TX = 0;          // UART0 TX -> ATGM336H RXD
constexpr uint GPS_RX = 1;          // UART0 RX <- ATGM336H TXD
constexpr uint SERVO_PWR_OFF = 3;   // high = servo 5 V buck OFF (board pull-down keeps it ON by default)
constexpr uint RADIO_TX = 4;        // UART1 TX -> radio socket J7 pin 2 (telemetry radio RX)   (v2 boards: Qwiic SDA)
constexpr uint RADIO_RX = 5;        // UART1 RX <- radio socket J7 pin 3 (telemetry radio TX)   (v2 boards: Qwiic SCL)
// Servo ports 1-7 (PWM slices 3A 3B 4A 4B 1A 6B 7B, all 50 Hz):
//   1 TVC ring, 2 TVC motor holder, 3 parachute release latch, 4-7 fin tabs 1-4 (fins at 45/135/225/315 deg)
constexpr int SERVO_COUNT = 7;
constexpr uint SERVO_PWM[SERVO_COUNT] = {6, 7, 8, 9, 2, 13, 15};
constexpr uint BUZZER = 10;         // high = on (active 3 V buzzer via AO3400A)
constexpr uint LED_GREEN = 11;      // high = on
constexpr uint LED_RED = 12;        // high = on
constexpr uint BUTTON = 14;         // USER button to GND (internal pull-up)
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
