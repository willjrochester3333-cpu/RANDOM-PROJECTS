// IMU-to-body axis mapping, MEASURED rather than assumed.
//
// Body frame used by the flight core (right-handed):
//   +x  along the rocket axis, towards the nose
//   +y  towards fin #1 (CAD +X; the TVC ring servo rotates the thrust line about this axis)
//   +z  directly away from the camera pod (CAD +Y; the motor-holder servo rotates about this axis)
//
// Two still poses on the bench give the mapping: (1) nose straight up, (2) lying flat with the camera
// pod facing straight DOWN. An accelerometer reads +1 g pointing UP, so pose 1 finds +x and pose 2 finds +z;
// +y = z cross x. The result is a signed permutation matrix M with  v_body = M * v_sensor.
// Platform independent: unit-tested on the host.
#pragma once
#include <cstdint>

namespace kestrel {

struct AxisMap {
    int8_t m[3][3]{{1, 0, 0}, {0, 1, 0}, {0, 0, 1}};
    void apply(const float in[3], float out[3]) const {
        for (int r = 0; r < 3; ++r) out[r] = m[r][0] * in[0] + m[r][1] * in[1] + m[r][2] * in[2];
    }
    bool is_valid_rotation() const;   // signed permutation with det = +1
};

enum class AxisCalResult : uint8_t { OK = 0, POSE1_NOT_VERTICAL, POSE2_NOT_FLAT, SAME_AXIS };

// a_up / a_flat: averaged accelerometer readings (sensor frame, any unit: only directions matter)
AxisCalResult solve_axis_map(const float a_up[3], const float a_flat[3], AxisMap& out);
const char* axis_cal_message(AxisCalResult r);

}  // namespace kestrel
