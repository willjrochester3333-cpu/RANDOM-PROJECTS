// Gimbal angle -> servo pulse mapping and the persistent bench settings. Platform independent.
#pragma once
#include <cstddef>
#include <cstdint>

#include "axis_cal.hpp"

namespace kestrel {

constexpr int kServoCount = 4;
enum ServoChannel : uint8_t { SERVO_TVC_RING = 0, SERVO_TVC_MOTOR = 1, SERVO_DEPLOY = 2, SERVO_AUX = 3 };

struct Settings {
    uint32_t magic{0x4B535431u};          // "KST1"
    uint16_t version{2};
    uint16_t size{sizeof(Settings)};
    AxisMap axes{};
    uint8_t axes_valid{0};                // 0 until the two-pose calibration has been done
    uint8_t motor_index{2};               // index into kMotors (motor_db.hpp); default TSP-E20
    uint8_t hold_launch_attitude{1};
    uint8_t reserved0{0};
    float trim_us[kServoCount]{0, 0, 0, 0};
    int8_t dir[kServoCount]{1, 1, 1, 1};  // +1 / -1 per servo, set by the bench direction test
    float us_per_servo_deg{10.5f};        // MG90S: ~1000-2000 us for ~95 deg
    float linkage_ratio{0.42f};           // gimbal deg per servo deg (design.json tvc.linkage_ratio)
    float deploy_latched_us{1050.0f};     // latch bolts out (locked)
    float deploy_released_us{1950.0f};    // latch bolts pulled in (parachute free)
    float max_gimbal_deg{6.0f};
    uint32_t flights{0};
    uint32_t crc{0};
};

uint32_t crc32(const void* data, size_t n, uint32_t crc = 0);
uint16_t crc16_ccitt(const void* data, size_t n, uint16_t crc = 0xFFFF);
void settings_seal(Settings& s);            // recompute crc
bool settings_valid(const Settings& s);     // magic/version/size/crc

// Gimbal (deg, about body y / z) -> pulse width (us) for the two TVC servos. Clamps the vector to
// max_gimbal_deg and the pulse to 1000..2000 us.
void gimbal_to_pulses(const Settings& s, float gy_deg, float gz_deg, float& ring_us, float& motor_us);
float clamp_pulse(float us);

}  // namespace kestrel
