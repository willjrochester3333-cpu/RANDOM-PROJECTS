// Minimal float vector / quaternion maths for the KESTREL flight core.
// Header-only, no dynamic allocation, safe for the RP2350 (single-precision FPU).
#pragma once
#include <cmath>

namespace kestrel {

struct Vec3 {
    float x{0}, y{0}, z{0};
    constexpr Vec3() = default;
    constexpr Vec3(float x_, float y_, float z_) : x(x_), y(y_), z(z_) {}
    Vec3 operator+(const Vec3& o) const { return {x + o.x, y + o.y, z + o.z}; }
    Vec3 operator-(const Vec3& o) const { return {x - o.x, y - o.y, z - o.z}; }
    Vec3 operator*(float s) const { return {x * s, y * s, z * s}; }
    Vec3 operator/(float s) const { return {x / s, y / s, z / s}; }
    Vec3& operator+=(const Vec3& o) { x += o.x; y += o.y; z += o.z; return *this; }
    Vec3& operator-=(const Vec3& o) { x -= o.x; y -= o.y; z -= o.z; return *this; }
    Vec3& operator*=(float s) { x *= s; y *= s; z *= s; return *this; }
    float dot(const Vec3& o) const { return x * o.x + y * o.y + z * o.z; }
    Vec3 cross(const Vec3& o) const { return {y * o.z - z * o.y, z * o.x - x * o.z, x * o.y - y * o.x}; }
    float norm() const { return std::sqrt(x * x + y * y + z * z); }
    Vec3 normalized() const { float n = norm(); return n > 1e-12f ? (*this) / n : Vec3{1, 0, 0}; }
};

// Unit quaternion, rotates body-frame vectors into the world frame: v_w = q * v_b * q^-1
struct Quat {
    float w{1}, x{0}, y{0}, z{0};
    constexpr Quat() = default;
    constexpr Quat(float w_, float x_, float y_, float z_) : w(w_), x(x_), y(y_), z(z_) {}

    Quat operator*(const Quat& b) const {
        return {w * b.w - x * b.x - y * b.y - z * b.z,
                w * b.x + x * b.w + y * b.z - z * b.y,
                w * b.y - x * b.z + y * b.w + z * b.x,
                w * b.z + x * b.y - y * b.x + z * b.w};
    }
    Quat conj() const { return {w, -x, -y, -z}; }
    void normalize() {
        float n = std::sqrt(w * w + x * x + y * y + z * z);
        if (n < 1e-12f) { w = 1; x = y = z = 0; return; }
        w /= n; x /= n; y /= n; z /= n;
    }
    // rotate a body vector into the world frame
    Vec3 rotate(const Vec3& v) const {
        // t = 2 * cross(q.xyz, v); v' = v + w*t + cross(q.xyz, t)
        Vec3 u{x, y, z};
        Vec3 t = u.cross(v) * 2.0f;
        return v + t * w + u.cross(t);
    }
    // rotate a world vector into the body frame
    Vec3 rotate_inv(const Vec3& v) const { return conj().rotate(v); }

    static Quat from_axis_angle(const Vec3& axis, float angle) {
        float n = axis.norm();
        if (n < 1e-12f || std::fabs(angle) < 1e-12f) return {};
        float s = std::sin(angle * 0.5f) / n;
        return {std::cos(angle * 0.5f), axis.x * s, axis.y * s, axis.z * s};
    }
    // shortest-arc rotation that maps unit vector a onto unit vector b
    static Quat from_two_vectors(const Vec3& a, const Vec3& b) {
        Vec3 an = a.normalized(), bn = b.normalized();
        float c = an.dot(bn);
        if (c > 1.0f - 1e-7f) return {};
        if (c < -1.0f + 1e-7f) {
            Vec3 perp = std::fabs(an.x) < 0.9f ? an.cross(Vec3{1, 0, 0}) : an.cross(Vec3{0, 1, 0});
            return from_axis_angle(perp, 3.14159265f);
        }
        Vec3 ax = an.cross(bn);
        Quat q{1.0f + c, ax.x, ax.y, ax.z};
        q.normalize();
        return q;
    }
};

inline float clampf(float v, float lo, float hi) { return v < lo ? lo : (v > hi ? hi : v); }
inline float deg2rad(float d) { return d * 0.017453292519943295f; }
inline float rad2deg(float r) { return r * 57.29577951308232f; }
constexpr float kG0 = 9.80665f;

}  // namespace kestrel
