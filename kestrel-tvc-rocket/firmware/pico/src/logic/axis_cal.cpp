#include "axis_cal.hpp"

#include <cmath>

namespace kestrel {

namespace {
// index of the dominant axis, or -1 if the vector is not within ~25 deg of a sensor axis
int dominant(const float a[3], int exclude, int& sign) {
    const float n = std::sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2]);
    if (n < 1e-6f) return -1;
    int best = -1;
    float bv = 0.0f;
    for (int i = 0; i < 3; ++i) {
        if (i == exclude) continue;
        if (std::fabs(a[i]) > bv) { bv = std::fabs(a[i]); best = i; }
    }
    if (best < 0 || bv / n < 0.9f) return -1;   // cos(25.8 deg)
    sign = a[best] > 0 ? 1 : -1;
    return best;
}
}  // namespace

bool AxisMap::is_valid_rotation() const {
    int nz = 0;
    for (int r = 0; r < 3; ++r)
        for (int c = 0; c < 3; ++c) {
            if (m[r][c] != 0 && m[r][c] != 1 && m[r][c] != -1) return false;
            nz += m[r][c] != 0;
        }
    if (nz != 3) return false;
    const int det = m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1]) - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0]) +
                    m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]);
    return det == 1;
}

AxisCalResult solve_axis_map(const float a_up[3], const float a_flat[3], AxisMap& out) {
    int sx = 0, sz = 0;
    const int ix = dominant(a_up, -1, sx);
    if (ix < 0) return AxisCalResult::POSE1_NOT_VERTICAL;
    // pose 2 must be roughly perpendicular to pose 1
    int dummy = 0;
    const int iz_any = dominant(a_flat, -1, dummy);
    if (iz_any < 0) return AxisCalResult::POSE2_NOT_FLAT;
    if (iz_any == ix) return AxisCalResult::SAME_AXIS;
    const int iz = dominant(a_flat, ix, sz);
    if (iz < 0) return AxisCalResult::POSE2_NOT_FLAT;
    float ex[3] = {0, 0, 0}, ez[3] = {0, 0, 0};
    ex[ix] = static_cast<float>(sx);
    ez[iz] = static_cast<float>(sz);
    // y = z cross x
    const float ey[3] = {ez[1] * ex[2] - ez[2] * ex[1], ez[2] * ex[0] - ez[0] * ex[2], ez[0] * ex[1] - ez[1] * ex[0]};
    AxisMap m;
    for (int c = 0; c < 3; ++c) {
        m.m[0][c] = static_cast<int8_t>(ex[c]);
        m.m[1][c] = static_cast<int8_t>(std::lround(ey[c]));
        m.m[2][c] = static_cast<int8_t>(ez[c]);
    }
    if (!m.is_valid_rotation()) return AxisCalResult::SAME_AXIS;
    out = m;
    return AxisCalResult::OK;
}

const char* axis_cal_message(AxisCalResult r) {
    switch (r) {
        case AxisCalResult::OK: return "ok";
        case AxisCalResult::POSE1_NOT_VERTICAL: return "pose 1: rocket was not standing nose-up (within 25 deg)";
        case AxisCalResult::POSE2_NOT_FLAT: return "pose 2: rocket was not lying flat with the camera pod straight down";
        case AxisCalResult::SAME_AXIS: return "pose 2 is the same direction as pose 1 - lay the rocket on its side";
    }
    return "?";
}

}  // namespace kestrel
