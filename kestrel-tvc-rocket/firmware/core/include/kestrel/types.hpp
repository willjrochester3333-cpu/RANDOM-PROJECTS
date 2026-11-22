// Shared types between the flight core, the Pico application and the simulator bridge.
#pragma once
#include <cstdint>
#include "vecmath.hpp"

namespace kestrel {

enum class FlightState : uint8_t {
    BOOT = 0,         // power-up, waiting for sensors
    CALIBRATING = 1,  // rocket must be still: gyro bias, gravity vector, pad pressure
    READY = 2,        // armed on the pad, waiting for launch, TVC centred
    BOOST = 3,        // motor burning, TVC active
    COAST = 4,        // motor out, TVC centred, waiting for apogee
    DESCENT = 5,      // parachute released
    LANDED = 6,       // on the ground, beeping, GPS logging
    ERROR = 7,        // self-test failed: do NOT launch
};

inline const char* state_name(FlightState s) {
    switch (s) {
        case FlightState::BOOT: return "BOOT";
        case FlightState::CALIBRATING: return "CALIBRATING";
        case FlightState::READY: return "READY";
        case FlightState::BOOST: return "BOOST";
        case FlightState::COAST: return "COAST";
        case FlightState::DESCENT: return "DESCENT";
        case FlightState::LANDED: return "LANDED";
        case FlightState::ERROR: return "ERROR";
    }
    return "?";
}

struct GpsFix {
    bool valid{false};
    double lat_deg{0}, lon_deg{0};
    float alt_m{0};
    uint8_t sats{0};
};

// One sample of sensor data handed to the flight core (body frame, SI units).
struct SensorFrame {
    float t{0};                 // seconds since boot (monotonic)
    Vec3 gyro;                  // rad/s
    Vec3 accel;                 // m/s^2, specific force (reads +1 g upwards when sitting still)
    bool imu_ok{true};
    bool baro_new{false};
    float baro_pa{0};
    bool baro_ok{true};
    bool gps_new{false};
    GpsFix gps;
    float vbat{8.0f};           // volts, 2S pack
};

enum class Buzz : uint8_t { OFF = 0, CHIRP_READY, FAST_ERROR, DESCENT_BEACON, LANDED_REPORT, CALIBRATING };

struct ActuatorCmd {
    float gimbal_y_deg{0};      // commanded rotation of the thrust line about body y
    float gimbal_z_deg{0};      // commanded rotation of the thrust line about body z
    bool deploy_release{false}; // true = latch pins retracted (parachute released)
    bool tvc_active{false};
    bool camera_power{false};
    Buzz buzzer{Buzz::OFF};
    FlightState state{FlightState::BOOT};
};

// Fixed-size binary log record (written to the W25Q128 flash, 64 bytes).
#pragma pack(push, 1)
struct LogRecord {
    uint32_t t_ms;
    uint8_t state;
    uint8_t flags;              // bit0 tvc_active, bit1 deploy_release, bit2 baro_new, bit3 gps_valid, bit4 abort
    int16_t gyro_cdps[3];       // centi-deg/s
    int16_t accel_cmss[3];      // cm/s^2
    float alt_m;                // filtered altitude above pad
    float vz_ms;                // filtered vertical velocity
    float baro_alt_m;           // raw baro altitude
    int16_t tilt_cdeg;          // angle from target direction, centi-deg
    int16_t gimbal_y_cdeg;
    int16_t gimbal_z_cdeg;
    int16_t vbat_mv;
    float lat_deg;              // GPS (float precision ~1 m is fine for recovery)
    float lon_deg;
    int16_t gps_alt_m;
    uint8_t sats;
    uint8_t reserved;
    float q[3];                 // attitude quaternion x,y,z (w recoverable)
    uint16_t crc16;             // CRC-16/CCITT of the preceding 62 bytes
};
#pragma pack(pop)
static_assert(sizeof(LogRecord) == 64, "LogRecord must stay 64 bytes");

}  // namespace kestrel
