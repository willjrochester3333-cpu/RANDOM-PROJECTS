// Servos, GPS UART, buzzer / LEDs, button, analogue monitoring.
#pragma once
#include <cstdint>

#include "../logic/nmea.hpp"
#include "kestrel/types.hpp"
#include "pico/types.h"

namespace hw {

void io_init();                              // GPIO directions + safe defaults (servo power on)

// ------------------------------------------------------------------ servos (50 Hz, 1 us resolution)
void servo_init();
void servo_write_us(int ch, float us);       // ch 0..6, pulse clamped to 800..2200 us
float servo_last_us(int ch);
void servo_power(bool on);

// ------------------------------------------------------------------ analogue
struct Power {
    float vbat{0}, cell1{0}, cell2{0}, servo_v{0};
};
Power read_power();

// ------------------------------------------------------------------ GPS (ATGM336H on UART0)
class Gps {
public:
    void init();                             // 9600 baud NMEA, then tries to switch the module to 115200 / 5 Hz
    void poll();                             // call every loop: drains the UART FIFO into the parser
    bool take_new_fix(kestrel::GpsFix& out); // true once per new GGA
    const kestrel::NmeaParser& parser() const { return nmea_; }
    uint32_t baud() const { return baud_; }
private:
    void send(const char* body);
    kestrel::NmeaParser nmea_;
    bool fresh_{false};
    uint32_t baud_{9600};
    uint64_t t_switch_us_{0};
    uint8_t stage_{0};
    uint32_t good_at_switch_{0};
};

// ------------------------------------------------------------------ buzzer + LEDs + button
class Ui {
public:
    void update(kestrel::Buzz pattern, kestrel::FlightState st, bool warn, float apogee_m, uint64_t now_us);
    void beep_number(int n, uint64_t now_us);   // e.g. battery decivolts on request (overrides the pattern)
    void chirp(uint64_t now_us, int ms = 60);
    bool button_pressed_short();                // edge events from the USER button
    bool button_pressed_long();
    void poll_button(uint64_t now_us);
private:
    uint64_t t_override_end_{0};
    int digits_[4]{};
    int ndigits_{0};
    uint64_t t_digits_start_{0};
    bool btn_prev_{false}, short_evt_{false}, long_evt_{false}, long_fired_{false};
    uint64_t t_btn_down_{0};
    uint64_t t_chirp_end_{0};
};

}  // namespace hw
