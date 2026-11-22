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
    // returns gimbal angles (deg) about body y and z. tvc_share (0..1) is the part of the pitch/yaw demand the
    // gimbal has to deliver (the fin tabs take the rest); the full demand is returned in alpha_out (rad/s^2).
    void update(const Quat& q, const Vec3& target_w, const Vec3& gyro_corr, float t_motor, float t_active,
                const TvcGains& g, const MotorProfile& m, float dt, float& gy_deg, float& gz_deg,
                float tvc_share = 1.0f, Vec3* alpha_out = nullptr);
    float last_error_deg() const { return err_deg_; }
private:
    Vec3 integ_{};
    Vec3 rate_f_{};
    float err_deg_{0};
};

// Attitude error helper shared by the TVC and the tabs: rotation vector (body y,z) that takes body x onto target
Vec3 attitude_error(const Quat& q, const Vec3& target_w, float* ang_deg = nullptr);
// Roll angle about body x since q_ref (twist part of q_ref^-1 * q), radians in (-pi, pi]
float twist_about_x(const Quat& q_ref, const Quat& q);
float wrap_pi(float a);

// ---------------------------------------------------------------------------
// Mixer for the four fin tabs: desired angular accelerations -> tab deflections.
//   tab k (fin at angle phi_k) pushes with F_k = qbar*E*delta_k along the fin normal, giving the body moment
//   F_k * (r, l cos phi_k, l sin phi_k).  The minimum-norm solution for (Mx, My, Mz) is
//   delta_k = [Mx/(4r) + My cos phi_k/(2l) + Mz sin phi_k/(2l)] / (qbar E)
// with roll limited first, then each tab clipped on its own (scale_out reports the worst clip factor).
class FinMixer {
public:
    static void allocate(const Vec3& alpha, float qbar, float i_roll, float i_lat, float l_tab, const Airframe& af,
                         float max_tab_deg, float tab_deg[4], float* scale_out = nullptr);
    // pitch/yaw angular-acceleration authority of the tabs at full deflection (rad/s^2)
    static float pitch_authority(float qbar, float i_lat, float l_tab, const Airframe& af, float max_tab_deg);
};

// ---------------------------------------------------------------------------
struct FlightStats {
    float max_alt_m{0};
    float max_speed_est{0};
    float t_launch{0}, t_burnout{0}, t_apogee{0}, t_deploy{0}, t_landed{0};
    float max_tilt_deg{0};
    float max_roll_rate_dps{0};
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
    float roll_deg() const { return rad2deg(roll_); }
    float qbar() const { return qbar_; }
    float tab_share() const { return tab_share_; }
    bool fins_safe() const { return fins_safe_; }
    float motor_time() const { return t_motor_; }
    Vec3 vel_inertial() const { return v_in_; }
    void fill_log(LogRecord& r, const SensorFrame& in, const ActuatorCmd& out) const;
    void force_state(FlightState s) { state_ = s; }   // bench / test use only

private:
    void enter(FlightState s, float t);
    float pressure_to_alt(float pa) const;
    void fin_control(const Vec3& w_corr, const Vec3& alpha_boost, float dt, ActuatorCmd& out, const MotorProfile& m);

    Config cfg_{};
    FlightState state_{FlightState::BOOT};
    AttitudeEstimator att_;
    AltitudeKF kf_;
    TvcController tvc_;
    FlightStats stats_;
    Quat q_launch_{};
    float roll_{0}, qbar_{0}, rho_{1.2f}, tab_share_{0};
    Vec3 rate_fin_f_{};
    bool spin_guard_{false};
    bool fins_safe_{false};
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
