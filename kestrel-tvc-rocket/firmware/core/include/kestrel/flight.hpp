// KESTREL flight core: estimators, TVC controller and flight state machine.
// Pure C++17, no heap, no OS. Call FlightComputer::step() at a fixed rate (500 Hz on the Pico).
#pragma once
#include "config.hpp"
#include "types.hpp"
#include "vecmath.hpp"

namespace kestrel {

float motor_interp(const MotorProfile& m, const float* table, float t);

// ---------------------------------------------------------------------------
class AttitudeEstimator {
public:
    void reset();
    // Pad: averages gyro (bias) and accelerometer (gravity => attitude). Returns true when still.
    bool pad_update(const Vec3& gyro, const Vec3& accel, float dt);
    void lock_pad_attitude();               // freeze bias + set quaternion from averaged gravity
    void propagate(const Vec3& gyro, float dt);  // in flight: integrate bias-corrected gyro
    const Quat& q() const { return q_; }
    Vec3 bias() const { return bias_; }
    float still_time() const { return still_time_; }
    Vec3 accel_avg() const { return acc_avg_; }
private:
    Quat q_{};
    Vec3 bias_{}, gyro_avg_{}, acc_avg_{0, 0, kG0};
    float still_time_{0};
    bool initialised_{false};
};

// ---------------------------------------------------------------------------
// 2-state Kalman filter (altitude, vertical velocity) driven by world-frame acceleration
class AltitudeKF {
public:
    void reset(float h0 = 0.0f);
    void predict(float a_up, float dt, float accel_sigma);
    void update_baro(float h_meas, float sigma);
    float h() const { return h_; }
    float v() const { return v_; }
private:
    float h_{0}, v_{0};
    float P00_{1}, P01_{0}, P11_{1};
};

// ---------------------------------------------------------------------------
class TvcController {
public:
    void reset();
    // target_w: desired body-x direction in the world frame
    // returns gimbal angles (deg) about body y and z
    void update(const Quat& q, const Vec3& target_w, const Vec3& gyro_corr, float t_motor, float t_active,
                const TvcGains& g, const MotorProfile& m, float dt, float& gy_deg, float& gz_deg);
    float last_error_deg() const { return err_deg_; }
private:
    Vec3 integ_{};
    Vec3 rate_f_{};
    float err_deg_{0};
};

// ---------------------------------------------------------------------------
struct FlightStats {
    float max_alt_m{0};
    float max_speed_est{0};
    float t_launch{0}, t_burnout{0}, t_apogee{0}, t_deploy{0}, t_landed{0};
    float max_tilt_deg{0};
    bool abort{false};
    bool unarmed_launch{false};   // launched before calibration finished: TVC off, recovery still active
    uint8_t deploy_reason{0};   // 1 apogee, 2 backup timer, 3 descent-rate, 4 abort
};

class FlightComputer {
public:
    void init(const Config& cfg);
    ActuatorCmd step(const SensorFrame& in);

    FlightState state() const { return state_; }
    const FlightStats& stats() const { return stats_; }
    const AttitudeEstimator& att() const { return att_; }
    const AltitudeKF& kf() const { return kf_; }
    float baro_alt() const { return baro_alt_; }
    float tilt_deg() const { return tilt_deg_; }
    float motor_time() const { return t_motor_; }
    Vec3 vel_inertial() const { return v_in_; }
    void fill_log(LogRecord& r, const SensorFrame& in, const ActuatorCmd& out) const;
    void force_state(FlightState s) { state_ = s; }   // bench / test use only

private:
    void enter(FlightState s, float t);
    float pressure_to_alt(float pa) const;

    Config cfg_{};
    FlightState state_{FlightState::BOOT};
    AttitudeEstimator att_;
    AltitudeKF kf_;
    TvcController tvc_;
    FlightStats stats_;
    float t_prev_{-1};
    float t_state_{0};
    float p0_{101325.0f}, p_avg_{101325.0f};
    float baro_alt_{0};
    float launch_timer_{0}, burnout_timer_{0};
    float t_launch_{0}, t_motor_{0};
    Vec3 target_w_{0, 0, 1};
    Vec3 v_in_{};
    int apogee_count_{0};
    float still_alt_ref_{0}, still_timer_{0}, imu_still_timer_{0};
    float tumble_timer_{0}, t_last_baro_{0}, t_last_still_{0};
    float tilt_deg_{0};
    bool deploy_{false};
    bool baro_seen_{false};
    float vbat_f_{8.0f};
    float g_meas_{kG0};           // accelerometer's own reading of 1 g on the pad
};

}  // namespace kestrel
