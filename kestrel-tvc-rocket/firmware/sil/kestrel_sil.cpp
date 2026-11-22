// C ABI around the flight core so the Python 6-DOF simulator can fly the REAL flight code
// (software-in-the-loop). Built as a shared library: libkestrel_sil.so
#include <cstring>

#include "kestrel/flight.hpp"
#include "kestrel/motor_db.hpp"

using namespace kestrel;

namespace {
struct Handle {
    FlightComputer fc;
    Config cfg;
};
}  // namespace

extern "C" {

void* ksil_create(int motor_index) {
    auto* h = new Handle();
    if (motor_index < 0 || motor_index >= kNumMotors) motor_index = kDefaultMotor;
    h->cfg.motor = &kMotors[motor_index];
    h->cfg.airframe = &kAirframe;
    h->fc.init(h->cfg);
    return h;
}

void ksil_destroy(void* p) { delete static_cast<Handle*>(p); }

int ksil_num_motors() { return kNumMotors; }
const char* ksil_motor_name(int i) { return (i >= 0 && i < kNumMotors) ? kMotors[i].name : ""; }

// Set a tunable by name; must be called before the first step (re-initialises the core).
int ksil_set_param(void* p, const char* name, float v) {
    auto* h = static_cast<Handle*>(p);
    auto& c = h->cfg;
    struct P { const char* n; float* f; };
    P table[] = {
        {"kp", &c.tvc.kp}, {"ki", &c.tvc.ki}, {"kd", &c.tvc.kd}, {"integ_limit", &c.tvc.integ_limit},
        {"max_gimbal_deg", &c.tvc.max_gimbal_deg}, {"thrust_floor_n", &c.tvc.thrust_floor_n},
        {"roll_lead_s", &c.tvc.roll_lead_s}, {"rate_lpf_hz", &c.tvc.rate_lpf_hz}, {"soft_start_s", &c.tvc.soft_start_s},
        {"launch_accel_g", &c.logic.launch_accel_g}, {"burnout_accel_g", &c.logic.burnout_accel_g},
        {"apogee_min_alt_m", &c.logic.apogee_min_alt_m}, {"deploy_lockout_after_burnout_s", &c.logic.deploy_lockout_after_burnout_s},
        {"deploy_backup_margin_s", &c.logic.deploy_backup_margin_s}, {"abort_tilt_deg", &c.logic.abort_tilt_deg},
        {"abort_deploy_speed_mps", &c.logic.abort_deploy_speed_mps}, {"calib_still_s", &c.logic.calib_still_s},
        {"accel_sigma", &c.kf.accel_sigma}, {"baro_sigma", &c.kf.baro_sigma}, {"baro_sigma_boost", &c.kf.baro_sigma_boost},
        {"roll_kp", &c.fins.roll_kp}, {"roll_kd", &c.fins.roll_kd}, {"coast_kp", &c.fins.coast_kp},
        {"coast_kd", &c.fins.coast_kd}, {"boost_share", &c.fins.boost_share}, {"max_tab_deg", &c.fins.max_tab_deg},
        {"q_floor_pa", &c.fins.q_floor_pa}, {"v_min_mps", &c.fins.v_min_mps}, {"roll_program_dps", &c.fins.roll_program_dps},
        {"fin_rate_lpf_hz", &c.fins.rate_lpf_hz}, {"spin_guard_dps", &c.fins.spin_guard_dps}, {"coast_giveup_deg", &c.fins.coast_giveup_deg},
    };
    for (auto& e : table) {
        if (std::strcmp(e.n, name) == 0) { *e.f = v; h->fc.init(c); return 0; }
    }
    if (std::strcmp(name, "hold_launch_attitude") == 0) { c.logic.hold_launch_attitude = v > 0.5f; h->fc.init(c); return 0; }
    if (std::strcmp(name, "apogee_confirm_samples") == 0) { c.logic.apogee_confirm_samples = static_cast<int>(v); h->fc.init(c); return 0; }
    if (std::strcmp(name, "fins_enabled") == 0) { c.fins.enabled = v > 0.5f; h->fc.init(c); return 0; }
    if (std::strcmp(name, "coast_hold_attitude") == 0) { c.fins.coast_hold_attitude = v > 0.5f; h->fc.init(c); return 0; }
    return -1;
}

// out[0] gimbal_y_deg, out[1] gimbal_z_deg, out[2] deploy, out[3] tvc_active, out[4] alt_est, out[5] vz_est,
// out[6] tilt_deg, out[7] deploy_reason, out[8] abort, out[9] baro_alt, out[10] max_alt,
// out[11..14] tab_deg[4], out[15] roll_deg, out[16] qbar_est, out[17] tab_share, out[18] fins_active
int ksil_step(void* p, float t, const float* gyro, const float* accel, int baro_new, float baro_pa, float vbat,
              float* out) {
    auto* h = static_cast<Handle*>(p);
    SensorFrame in;
    in.t = t;
    in.gyro = Vec3{gyro[0], gyro[1], gyro[2]};
    in.accel = Vec3{accel[0], accel[1], accel[2]};
    in.baro_new = baro_new != 0;
    in.baro_pa = baro_pa;
    in.vbat = vbat;
    ActuatorCmd o = h->fc.step(in);
    out[0] = o.gimbal_y_deg;
    out[1] = o.gimbal_z_deg;
    out[2] = o.deploy_release ? 1.0f : 0.0f;
    out[3] = o.tvc_active ? 1.0f : 0.0f;
    out[4] = h->fc.kf().h();
    out[5] = h->fc.kf().v();
    out[6] = h->fc.tilt_deg();
    out[7] = static_cast<float>(h->fc.stats().deploy_reason);
    out[8] = h->fc.stats().abort ? 1.0f : 0.0f;
    out[9] = h->fc.baro_alt();
    out[10] = h->fc.stats().max_alt_m;
    for (int k = 0; k < 4; ++k) out[11 + k] = o.tab_deg[k];
    out[15] = h->fc.roll_deg();
    out[16] = h->fc.qbar();
    out[17] = h->fc.tab_share();
    out[18] = o.fins_active ? 1.0f : 0.0f;
    out[19] = h->fc.fins_safe() ? 1.0f : 0.0f;
    return static_cast<int>(o.state);
}

}  // extern "C"
