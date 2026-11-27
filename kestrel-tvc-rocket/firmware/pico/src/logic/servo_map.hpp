// Gimbal angle -> servo pulse mapping and the persistent bench settings. Platform independent.
#pragma once
#include <cstddef>
#include <cstdint>

#include "axis_cal.hpp"

namespace kestrel {

constexpr int kServoCount = 7;
enum ServoChannel : uint8_t { SERVO_TVC_RING = 0, SERVO_TVC_MOTOR = 1, SERVO_DEPLOY = 2, SERVO_TAB1 = 3, SERVO_TAB2 = 4,
                              SERVO_TAB3 = 5, SERVO_TAB4 = 6 };

struct Settings {
    uint32_t magic{0x4B535431u};          // "KST1"
    uint16_t version{6};                  // 6 = 29 mm TVC mount (gimbal arms 22 mm); 5 = direct-drive fin tabs; 4 had pushrod tabs
    uint16_t size{sizeof(Settings)};
    AxisMap axes{};
    uint8_t axes_valid{0};                // 0 until the two-pose calibration has been done
    uint8_t motor_index{5};               // index into kMotors (motor_db.hpp); default TSP-F35 (0 = D20, 2 = E20)
    uint8_t hold_launch_attitude{1};
    uint8_t radio_off{0};                 // 1 = telemetry radio silent (was reserved0: old saved settings read 0 = on)
    float trim_us[kServoCount]{0, 0, 0, 0, 0, 0, 0};
    int8_t dir[kServoCount]{1, 1, 1, 1, 1, 1, 1};  // +1 / -1 per servo, set by the bench direction tests
    uint8_t tabs_enabled{1};              // fin-tab control on/off
    uint8_t reserved1{0};
    float us_per_servo_deg{10.5f};        // MG90S: ~1000-2000 us for ~95 deg
    float linkage_ratio{0.4091f};         // gimbal deg per servo deg: 9 mm horn / 22 mm gimbal arm (design.json tvc.linkage_ratio)
    float deploy_latched_us{1050.0f};     // latch bolts out (locked)
    float deploy_released_us{1950.0f};    // latch bolts pulled in (parachute free)
    float max_gimbal_deg{6.0f};
    float tab_servo_arm_mm{1.0f};         // design.json fins.tab.servo_arm_mm; equal to tab_horn_mm = direct drive:
    float tab_horn_mm{1.0f};              // the servo shaft is the tab hinge, servo angle = tab angle (fins.tab.horn_mm)
    float max_tab_deg{15.0f};
    float roll_program_dps{0.0f};         // >0: camera panorama roll in COAST
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
// Fin tab k (0..3) angle (deg, + = force towards +roll; seen from behind the rocket the trailing edge swings
// anticlockwise, towards the fin with the next-lower number) -> servo pulse (us).
// General linkage horn * sin(tab) = arm * sin(servo); KESTREL-2 drives its tabs directly (horn = arm, servo = tab).
// Clamps to max_tab_deg and 1000..2000 us.
float tab_to_pulse(const Settings& s, int k, float tab_deg);
float clamp_pulse(float us);

}  // namespace kestrel
