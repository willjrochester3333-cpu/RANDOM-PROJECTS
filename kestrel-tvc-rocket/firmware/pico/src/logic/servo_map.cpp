#include "servo_map.hpp"

#include <cmath>

namespace kestrel {

uint32_t crc32(const void* data, size_t n, uint32_t crc) {
    const uint8_t* p = static_cast<const uint8_t*>(data);
    crc = ~crc;
    for (size_t i = 0; i < n; ++i) {
        crc ^= p[i];
        for (int k = 0; k < 8; ++k) crc = (crc >> 1) ^ (0xEDB88320u & (0u - (crc & 1u)));
    }
    return ~crc;
}

uint16_t crc16_ccitt(const void* data, size_t n, uint16_t crc) {
    const uint8_t* p = static_cast<const uint8_t*>(data);
    for (size_t i = 0; i < n; ++i) {
        crc ^= static_cast<uint16_t>(p[i]) << 8;
        for (int k = 0; k < 8; ++k) crc = (crc & 0x8000u) ? static_cast<uint16_t>((crc << 1) ^ 0x1021u) : static_cast<uint16_t>(crc << 1);
    }
    return crc;
}

void settings_seal(Settings& s) {
    s.size = sizeof(Settings);
    s.crc = crc32(&s, offsetof(Settings, crc));
}

bool settings_valid(const Settings& s) {
    return s.magic == 0x4B535431u && s.version == Settings{}.version && s.size == sizeof(Settings) &&
           s.crc == crc32(&s, offsetof(Settings, crc));
}

float clamp_pulse(float us) { return us < 1000.0f ? 1000.0f : (us > 2000.0f ? 2000.0f : us); }

void gimbal_to_pulses(const Settings& s, float gy, float gz, float& ring_us, float& motor_us) {
    const float lim = s.max_gimbal_deg;
    const float mag = std::sqrt(gy * gy + gz * gz);
    if (mag > lim && mag > 1e-6f) { gy *= lim / mag; gz *= lim / mag; }
    const float k = s.us_per_servo_deg / s.linkage_ratio;   // us per gimbal degree
    ring_us = clamp_pulse(1500.0f + s.trim_us[SERVO_TVC_RING] + s.dir[SERVO_TVC_RING] * k * gy);
    motor_us = clamp_pulse(1500.0f + s.trim_us[SERVO_TVC_MOTOR] + s.dir[SERVO_TVC_MOTOR] * k * gz);
}

}  // namespace kestrel
