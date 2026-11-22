#include "io.hpp"

#include <cstdio>
#include <initializer_list>
#include <cstring>

#include "../board.hpp"
#include "hardware/adc.h"
#include "hardware/clocks.h"
#include "hardware/gpio.h"
#include "hardware/pwm.h"
#include "hardware/uart.h"
#include "pico/stdlib.h"

namespace hw {

using kestrel::Buzz;
using kestrel::FlightState;

void io_init() {
    const uint outs[] = {board::SERVO_PWR_OFF, board::BUZZER, board::LED_GREEN, board::LED_RED};
    for (uint p : outs) {
        gpio_init(p);
        gpio_set_dir(p, GPIO_OUT);
        gpio_put(p, 0);              // servo power ON, buzzer off, LEDs off
    }
    gpio_init(board::BUTTON);
    gpio_set_dir(board::BUTTON, GPIO_IN);
    gpio_pull_up(board::BUTTON);
    for (uint p : {board::BARO_INT}) {
        gpio_init(p);
        gpio_set_dir(p, GPIO_IN);   // driven push-pull by the sensors; no pulls (RP2350-E9)
        gpio_disable_pulls(p);
    }
    adc_init();
    adc_gpio_init(board::ADC_VBAT);
    adc_gpio_init(board::ADC_CELL1);
    adc_gpio_init(board::ADC_SERVO_V);
}

// ============================================================================ servos
namespace {
float g_last_us[board::SERVO_COUNT] = {1500, 1500, 1500, 1500, 1500, 1500, 1500};
}

void servo_init() {
    const float div = static_cast<float>(clock_get_hz(clk_sys)) / 1.0e6f;   // 1 MHz counter
    for (int ch = 0; ch < board::SERVO_COUNT; ++ch) {
        const uint pin = board::SERVO_PWM[ch];
        gpio_set_function(pin, GPIO_FUNC_PWM);
        const uint slice = pwm_gpio_to_slice_num(pin);
        pwm_config c = pwm_get_default_config();
        pwm_config_set_clkdiv(&c, div);
        pwm_config_set_wrap(&c, 19999);                                   // 20 ms frame (50 Hz)
        pwm_init(slice, &c, false);
    }
    for (int ch = 0; ch < board::SERVO_COUNT; ++ch) servo_write_us(ch, g_last_us[ch]);
    for (int ch = 0; ch < board::SERVO_COUNT; ++ch) pwm_set_enabled(pwm_gpio_to_slice_num(board::SERVO_PWM[ch]), true);
}

void servo_write_us(int ch, float us) {
    if (ch < 0 || ch >= board::SERVO_COUNT) return;
    if (us < 800.0f) us = 800.0f;
    if (us > 2200.0f) us = 2200.0f;
    g_last_us[ch] = us;
    pwm_set_gpio_level(board::SERVO_PWM[ch], static_cast<uint16_t>(us + 0.5f));
}

float servo_last_us(int ch) { return (ch >= 0 && ch < board::SERVO_COUNT) ? g_last_us[ch] : 0.0f; }

void servo_power(bool on) { gpio_put(board::SERVO_PWR_OFF, on ? 0 : 1); }

// ============================================================================ analogue
namespace {
float adc_volts(uint input) {
    adc_select_input(input);
    uint32_t acc = 0;
    for (int i = 0; i < 4; ++i) acc += adc_read();
    return static_cast<float>(acc) * (board::ADC_VREF / 4096.0f / 4.0f);
}
}  // namespace

Power read_power() {
    Power p;
    p.vbat = adc_volts(0) * board::VBAT_DIV;
    p.cell1 = adc_volts(1) * board::CELL1_DIV;
    p.cell2 = p.vbat - p.cell1;
    p.servo_v = adc_volts(2) * board::SERVO_V_DIV;
    return p;
}

// ============================================================================ GPS
void Gps::init() {
    uart_init(uart0, 9600);
    gpio_set_function(board::GPS_TX, GPIO_FUNC_UART);
    gpio_set_function(board::GPS_RX, GPIO_FUNC_UART);
    uart_set_fifo_enabled(uart0, true);
    baud_ = 9600;
    stage_ = 0;
    t_switch_us_ = time_us_64();
}

void Gps::send(const char* body) {
    char s[96];
    const size_t n = kestrel::NmeaParser::make_sentence(body, s, sizeof s);
    if (n) uart_write_blocking(uart0, reinterpret_cast<const uint8_t*>(s), n);
}

void Gps::poll() {
    while (uart_is_readable(uart0)) {
        if (nmea_.feed(static_cast<char>(uart_getc(uart0)))) fresh_ = true;
    }
    // CASIC configuration: GGA+RMC only, 5 Hz, 115200 baud; fall back to 9600 if the module does not follow
    const uint64_t now = time_us_64();
    switch (stage_) {
        case 0:   // wait for the module to talk at 9600
            if (nmea_.good_sentences() >= 3) {
                send("PCAS03,1,0,0,0,1,0,0,0,0,0,,,0,0");
                send("PCAS02,200");
                send("PCAS01,5");
                uart_tx_wait_blocking(uart0);
                sleep_ms(20);
                uart_set_baudrate(uart0, 115200);
                baud_ = 115200;
                good_at_switch_ = nmea_.good_sentences();
                t_switch_us_ = now;
                stage_ = 1;
            }
            break;
        case 1:   // did it follow us to 115200?
            if (nmea_.good_sentences() >= good_at_switch_ + 3) {
                stage_ = 2;
            } else if (now - t_switch_us_ > 3000000u) {
                uart_set_baudrate(uart0, 9600);
                baud_ = 9600;
                stage_ = 3;   // stay at 9600 (5 Hz still fits)
            }
            break;
        default:
            break;
    }
}

bool Gps::take_new_fix(kestrel::GpsFix& out) {
    if (!fresh_) return false;
    fresh_ = false;
    const auto& f = nmea_.fix();
    out.valid = f.valid;
    out.lat_deg = f.lat_deg;
    out.lon_deg = f.lon_deg;
    out.alt_m = f.alt_m;
    out.sats = f.sats;
    return true;
}

// ============================================================================ UI
namespace {
bool pattern_on(Buzz b, uint64_t t_ms) {
    switch (b) {
        case Buzz::OFF: return false;
        case Buzz::CALIBRATING: return (t_ms % 1000) < 40;
        case Buzz::CHIRP_READY: { const uint64_t m = t_ms % 3000; return m < 60 || (m >= 160 && m < 220); }
        case Buzz::FAST_ERROR: return (t_ms % 200) < 100;
        case Buzz::DESCENT_BEACON: return (t_ms % 1000) < 300;
        case Buzz::LANDED_REPORT: return false;   // handled with digits
    }
    return false;
}
// digit beeps: d>0 -> d x (200 on / 250 off), 0 -> one 700 ms beep; 900 ms between digits
bool digits_on(const int* d, int n, uint64_t t_ms, uint64_t& total_ms) {
    uint64_t t = 0;
    bool on = false;
    for (int i = 0; i < n; ++i) {
        const int k = d[i] == 0 ? 1 : d[i];
        for (int j = 0; j < k; ++j) {
            const uint64_t len = d[i] == 0 ? 700 : 200;
            if (t_ms >= t && t_ms < t + len) on = true;
            t += len + 250;
        }
        t += 900;
    }
    total_ms = t;
    return on;
}
int split_digits(int v, int* out) {
    if (v < 0) v = 0;
    if (v > 9999) v = 9999;
    int tmp[4], n = 0;
    do { tmp[n++] = v % 10; v /= 10; } while (v && n < 4);
    for (int i = 0; i < n; ++i) out[i] = tmp[n - 1 - i];
    return n;
}
}  // namespace

void Ui::chirp(uint64_t now_us, int ms) { t_chirp_end_ = now_us + static_cast<uint64_t>(ms) * 1000u; }

void Ui::beep_number(int n, uint64_t now_us) {
    ndigits_ = split_digits(n, digits_);
    t_digits_start_ = now_us + 300000u;
    uint64_t total = 0;
    digits_on(digits_, ndigits_, 0, total);
    t_override_end_ = t_digits_start_ + total * 1000u;
}

void Ui::update(Buzz b, FlightState st, bool warn, float apogee_m, uint64_t now_us) {
    const uint64_t t_ms = now_us / 1000u;
    bool buzz = false;
    if (now_us < t_override_end_) {
        uint64_t total = 0;
        buzz = now_us >= t_digits_start_ && digits_on(digits_, ndigits_, (now_us - t_digits_start_) / 1000u, total);
    } else if (b == Buzz::LANDED_REPORT) {
        // apogee in metres as digits, then 6 s of silence-with-locator-chirps, repeat
        int d[4];
        const int n = split_digits(static_cast<int>(apogee_m + 0.5f), d);
        uint64_t total = 0;
        digits_on(d, n, 0, total);
        const uint64_t cycle = total + 6000;
        const uint64_t m = t_ms % cycle;
        buzz = m < total ? digits_on(d, n, m, total) : ((m - total) % 1500) < 80;
    } else {
        buzz = pattern_on(b, t_ms);
    }
    if (now_us < t_chirp_end_) buzz = true;
    gpio_put(board::BUZZER, buzz);

    bool g = false, r = false;
    switch (st) {
        case FlightState::BOOT: g = r = true; break;
        case FlightState::CALIBRATING: g = (t_ms % 500) < 250; break;
        case FlightState::READY: g = true; break;
        case FlightState::BOOST:
        case FlightState::COAST: g = true; break;
        case FlightState::DESCENT: g = (t_ms % 1000) < 500; break;
        case FlightState::LANDED: g = (t_ms % 2000) < 150; break;
        case FlightState::ERROR: r = (t_ms % 200) < 100; break;
    }
    if (warn && st != FlightState::ERROR) r = (t_ms % 1000) < 500;
    gpio_put(board::LED_GREEN, g);
    gpio_put(board::LED_RED, r);
}

void Ui::poll_button(uint64_t now_us) {
    const bool down = !gpio_get(board::BUTTON);
    if (down && !btn_prev_) { t_btn_down_ = now_us; long_fired_ = false; }
    if (down && !long_fired_ && now_us - t_btn_down_ > 1500000u) { long_evt_ = true; long_fired_ = true; }
    if (!down && btn_prev_ && !long_fired_ && now_us - t_btn_down_ > 30000u) short_evt_ = true;
    btn_prev_ = down;
}

bool Ui::button_pressed_short() { const bool e = short_evt_; short_evt_ = false; return e; }
bool Ui::button_pressed_long() { const bool e = long_evt_; long_evt_ = false; return e; }

}  // namespace hw
