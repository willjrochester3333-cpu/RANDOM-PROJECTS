// Host unit tests for the KESTREL flight core. Build with CMake and run `ctest`.
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <random>

#include "kestrel/flight.hpp"
#include "kestrel/motor_db.hpp"

using namespace kestrel;

static int g_fail = 0, g_pass = 0;
#define CHECK(cond, ...)                                                       \
    do {                                                                       \
        if (cond) { ++g_pass; }                                                \
        else { ++g_fail; std::printf("FAIL %s:%d: %s  ", __FILE__, __LINE__, #cond); \
               std::printf(__VA_ARGS__); std::printf("\n"); }                  \
    } while (0)
#define NEAR(a, b, tol) CHECK(std::fabs((a) - (b)) <= (tol), "%s=%g vs %g (tol %g)", #a, double(a), double(b), double(tol))

static void test_quaternions() {
    Quat q = Quat::from_axis_angle(Vec3{0, 0, 1}, deg2rad(90));
    Vec3 v = q.rotate(Vec3{1, 0, 0});
    NEAR(v.x, 0.0f, 1e-5f); NEAR(v.y, 1.0f, 1e-5f); NEAR(v.z, 0.0f, 1e-5f);
    Vec3 b = q.rotate_inv(v);
    NEAR(b.x, 1.0f, 1e-5f);
    Vec3 a{0.3f, -0.2f, 0.93f};
    Quat r = Quat::from_two_vectors(a, Vec3{0, 0, 1});
    Vec3 u = r.rotate(a.normalized());
    NEAR(u.z, 1.0f, 1e-5f);
    Quat opp = Quat::from_two_vectors(Vec3{0, 0, 1}, Vec3{0, 0, -1});
    NEAR(opp.rotate(Vec3{0, 0, 1}).z, -1.0f, 1e-5f);
}

static void test_attitude() {
    AttitudeEstimator e;
    e.reset();
    // rocket on a rod tilted 5 deg towards world +x, rolled arbitrarily: body x is the rocket axis
    const float tilt = deg2rad(5.0f);
    Vec3 up_body{std::cos(tilt), std::sin(tilt), 0.0f};   // gravity reaction measured in body frame
    Vec3 bias{deg2rad(0.4f), deg2rad(-0.3f), deg2rad(0.2f)};
    for (int i = 0; i < 2000; ++i) e.pad_update(bias, up_body * kG0, 0.002f);
    e.lock_pad_attitude();
    NEAR(e.bias().x, bias.x, 1e-4f);
    Vec3 xw = e.q().rotate(Vec3{1, 0, 0});
    NEAR(std::acos(xw.z), tilt, 1e-3f);
    // integrate a pure 30 deg/s yaw-plane rate for 1 s (gyro still carries the bias)
    Quat q0 = e.q();
    for (int i = 0; i < 500; ++i) e.propagate(Vec3{0, deg2rad(30.0f), 0} + bias, 0.002f);
    Quat dq = q0.conj() * e.q();
    float ang = 2.0f * std::acos(clampf(dq.w, -1, 1));
    NEAR(rad2deg(ang), 30.0f, 0.05f);
}

static void test_kf() {
    AltitudeKF kf;
    kf.reset(0);
    std::mt19937 rng(3);
    std::normal_distribution<float> n(0.0f, 0.4f);
    float h = 0, v = 0;
    const float dt = 0.002f;
    for (int i = 0; i < 4000; ++i) {     // 8 s: boost 2 s at 40 m/s^2 then ballistic
        float a = (i < 1000) ? 40.0f : -9.81f;
        h += v * dt + 0.5f * a * dt * dt;
        v += a * dt;
        kf.predict(a + n(rng) * 0.5f, dt, 0.6f);
        if (i % 20 == 0) kf.update_baro(h + n(rng), 0.4f);
    }
    NEAR(kf.h(), h, 1.5f);
    NEAR(kf.v(), v, 1.0f);
}

static void test_tvc_sign_and_limits() {
    TvcController c;
    c.reset();
    TvcGains g;
    const MotorProfile& m = kMotors[kDefaultMotor];
    // Body frame aligned with world; target tilted towards world +z?? -> use target with a +z_body component.
    Quat q{};   // body == world
    // target direction: mostly +x with a small +z component
    Vec3 target = Vec3{1.0f, 0.0f, 0.05f}.normalized();
    float gy = 0, gz = 0;
    for (int i = 0; i < 200; ++i) c.update(q, target, Vec3{}, 0.5f, 0.5f, g, m, 0.002f, gy, gz);
    // To swing the nose towards +z we need a negative pitch moment M_y; plant: M_y = -l T sin(gy) => gy > 0
    CHECK(gy > 0.0f, "gy=%g", double(gy));
    NEAR(gz, 0.0f, 1e-3f);
    // A large error must saturate at the configured limit, direction preserved
    Vec3 big = Vec3{1.0f, 0.4f, 0.4f}.normalized();
    c.reset();
    c.update(q, big, Vec3{}, 0.5f, 0.5f, g, m, 0.002f, gy, gz);
    NEAR(std::sqrt(gy * gy + gz * gz), g.max_gimbal_deg, 0.05f);
    NEAR(std::fabs(gy), std::fabs(gz), 0.05f);
    // Rate damping: a positive pitch rate (nose swinging towards -z) must be opposed by a negative
    // pitch moment M_y = -l T sin(gy) < 0  =>  gy > 0 while the attitude is still on target
    c.reset();
    for (int i = 0; i < 50; ++i) c.update(q, Vec3{1, 0, 0}, Vec3{0, deg2rad(20.0f), 0}, 0.5f, 0.5f, g, m, 0.002f, gy, gz);
    CHECK(gy > 0.0f, "gy=%g", double(gy));
    // Roll-lead: with a roll rate the command is pre-rotated about x (magnitude preserved)
    c.reset();
    float gy0, gz0, gy1, gz1;
    c.update(q, target, Vec3{}, 0.5f, 0.5f, g, m, 0.002f, gy0, gz0);
    c.reset();
    c.update(q, target, Vec3{deg2rad(180.0f), 0, 0}, 0.5f, 0.5f, g, m, 0.002f, gy1, gz1);
    NEAR(std::hypot(gy0, gz0), std::hypot(gy1, gz1), 0.02f);
    CHECK(std::fabs(gz1) > 0.05f, "roll lead rotated command, gz1=%g", double(gz1));
}

// Synthetic full flight through the state machine.
static void test_state_machine(bool baro_fail, bool tilt_abort) {
    FlightComputer fc;
    Config cfg;
    cfg.motor = &kMotors[kDefaultMotor];
    fc.init(cfg);
    const float dt = 0.002f;
    float t = 0, h = 0, v = 0;
    bool deployed = false;
    float t_deploy = -1, t_apogee = -1;
    FlightState max_state = FlightState::BOOT;
    for (int i = 0; i < 200 * 500; ++i, t += dt) {
        SensorFrame s;
        s.t = t;
        s.gyro = Vec3{};
        float a_kin = 0;
        float f_axial;
        const float t_ign = 6.0f;
        if (t < t_ign) {
            f_axial = kG0;          // on the pad
        } else if (t < t_ign + 2.0f) {
            a_kin = 40.0f;          // boost
            f_axial = a_kin + kG0;
        } else if (!deployed) {
            a_kin = -kG0 - 0.002f * v * std::fabs(v);
            f_axial = a_kin + kG0;  // drag only
        } else {
            a_kin = (v < -5.0f) ? 0.0f : -kG0 * 0.5f;
            f_axial = a_kin + kG0;
        }
        if (t >= t_ign) {
            v += a_kin * dt;
            h += v * dt;
            if (h < 0) { h = 0; v = 0; }
        }
        if (t_apogee < 0 && t > t_ign + 2.5f && v < 0) t_apogee = t;
        s.accel = Vec3{f_axial, 0, 0};
        if (tilt_abort && t > t_ign + 0.5f && t < t_ign + 2.0f) s.gyro = Vec3{0, deg2rad(60.0f), 0};
        s.baro_new = (i % 20) == 0 && !(baro_fail && t > t_ign + 1.0f);
        s.baro_pa = 101325.0f * std::pow(1.0f - h / 44330.0f, 5.255f);
        ActuatorCmd o = fc.step(s);
        if (static_cast<int>(o.state) > static_cast<int>(max_state) && o.state != FlightState::ERROR) max_state = o.state;
        if (o.state == FlightState::BOOST) CHECK(!o.deploy_release, "deploy during boost");
        if (o.deploy_release && !deployed) { deployed = true; t_deploy = t; }
        CHECK(o.state != FlightState::ERROR, "unexpected ERROR at t=%g", double(t));
        if (o.state == FlightState::ERROR) return;
    }
    CHECK(deployed, "never deployed");
    CHECK(max_state == FlightState::LANDED, "max state %d", int(max_state));
    if (!baro_fail && !tilt_abort) {
        NEAR(t_deploy - t_apogee, 0.3f, 0.45f);     // within ~0.75 s after true apogee
        CHECK(fc.stats().deploy_reason == 1, "reason %d", fc.stats().deploy_reason);
    }
    // with the baro dead, the inertial descent-rate rule (3) or the backup timer (2) must deploy
    if (baro_fail) CHECK(fc.stats().deploy_reason == 2 || fc.stats().deploy_reason == 3, "baro fail reason %d", fc.stats().deploy_reason);
    if (tilt_abort) CHECK(fc.stats().abort, "abort flag");
}

static void test_logrecord() {
    FlightComputer fc;
    Config cfg;
    cfg.motor = &kMotors[0];
    fc.init(cfg);
    SensorFrame s;
    s.accel = Vec3{kG0, 0, 0};
    ActuatorCmd o = fc.step(s);
    LogRecord r;
    fc.fill_log(r, s, o);
    CHECK(sizeof(r) == 64, "size %d", int(sizeof(r)));
    uint16_t c = r.crc16;
    r.crc16 = 0;
    LogRecord r2;
    fc.fill_log(r2, s, o);
    CHECK(c == r2.crc16, "crc stable");
}

// Accelerometer with a large offset must still calibrate; a launch before READY must still deploy.
static void test_robust_arming() {
    for (int scenario = 0; scenario < 2; ++scenario) {
        FlightComputer fc;
        Config cfg;
        cfg.motor = &kMotors[kDefaultMotor];
        fc.init(cfg);
        const float dt = 0.002f;
        float t = 0, h = 0, v = 0;
        bool deployed = false;
        const float t_ign = scenario == 0 ? 6.0f : 1.5f;   // scenario 1: launch before calibration can finish
        bool was_ready = false;
        for (int i = 0; i < 120 * 500; ++i, t += dt) {
            SensorFrame s;
            s.t = t;
            float a_kin = 0, f_ax;
            if (t < t_ign) f_ax = kG0 * 0.94f;               // -60 mg offset on the axial channel
            else if (t < t_ign + 2.0f) { a_kin = 40.0f; f_ax = a_kin + kG0; }
            else if (!deployed) { a_kin = -kG0; f_ax = 0.0f; }
            else { a_kin = (v < -5.0f) ? 0.0f : -kG0 * 0.5f; f_ax = a_kin + kG0; }
            if (t >= t_ign) { v += a_kin * dt; h += v * dt; if (h < 0) { h = 0; v = 0; } }
            s.accel = Vec3{f_ax, 0, 0};
            s.baro_new = (i % 20) == 0;
            s.baro_pa = 101325.0f * std::pow(1.0f - h / 44330.0f, 5.255f);
            ActuatorCmd o = fc.step(s);
            if (o.state == FlightState::READY) was_ready = true;
            if (o.deploy_release) deployed = true;
        }
        CHECK(deployed, "scenario %d: parachute released", scenario);
        if (scenario == 0) CHECK(was_ready, "60 mg accelerometer offset still reaches READY");
        if (scenario == 1) CHECK(fc.stats().unarmed_launch, "unarmed launch flagged");
    }
}

// Fin-tab mixer: the four deflections must reproduce the requested moments exactly (when not saturated),
// roll must be common to all tabs, saturation must respect the limit, and the roll angle helper must work.
static void test_fin_mixer() {
    const Airframe& af = kAirframe;
    const float qbar = 800.0f, I_lat = 0.043f, I_roll = af.i_roll, l = 0.21f;
    std::mt19937 rng(7);
    std::uniform_real_distribution<float> u(-1.0f, 1.0f);
    for (int n = 0; n < 2000; ++n) {
        Vec3 alpha{u(rng) * 60.0f, u(rng) * 4.0f, u(rng) * 4.0f};
        float tab[4], scale = 0;
        FinMixer::allocate(alpha, qbar, I_roll, I_lat, l, af, 15.0f, tab, &scale);
        for (int k = 0; k < 4; ++k) CHECK(std::fabs(tab[k]) <= 15.0f + 1e-4f, "tab %d = %g", k, double(tab[k]));
        if (scale > 0.9999f) {
            float Mx = 0, My = 0, Mz = 0;
            for (int k = 0; k < 4; ++k) {
                const float F = qbar * af.tab_E_m2 * deg2rad(tab[k]);
                const float phi = deg2rad(af.fin_deg[k]);
                Mx += F * af.tab_r_m; My += F * l * std::cos(phi); Mz += F * l * std::sin(phi);
            }
            NEAR(Mx, I_roll * alpha.x, 2e-5f);
            NEAR(My, I_lat * alpha.y, 2e-4f);
            NEAR(Mz, I_lat * alpha.z, 2e-4f);
        }
    }
    // pure roll: all four identical, positive command for positive roll acceleration
    float tab[4];
    FinMixer::allocate(Vec3{20.0f, 0, 0}, qbar, I_roll, I_lat, l, af, 15.0f, tab);
    for (int k = 1; k < 4; ++k) NEAR(tab[k], tab[0], 1e-5f);
    CHECK(tab[0] > 0.0f, "roll sign %g", double(tab[0]));
    // pure pitch (about body y): fins at 45/315 deg push one way, 135/225 the other, sum zero (no roll)
    FinMixer::allocate(Vec3{0, 2.0f, 0}, qbar, I_roll, I_lat, l, af, 15.0f, tab);
    NEAR(tab[0] + tab[1] + tab[2] + tab[3], 0.0f, 1e-4f);
    CHECK(tab[0] > 0.0f && tab[3] > 0.0f && tab[1] < 0.0f && tab[2] < 0.0f, "pitch pattern %g %g %g %g",
          double(tab[0]), double(tab[1]), double(tab[2]), double(tab[3]));
    // a demand far beyond the authority saturates every tab at the limit, never beyond
    FinMixer::allocate(Vec3{5000.0f, 300.0f, -300.0f}, 50.0f, I_roll, I_lat, l, af, 15.0f, tab);
    for (int k = 0; k < 4; ++k) CHECK(std::fabs(tab[k]) <= 15.0f + 1e-4f, "sat tab %d = %g", k, double(tab[k]));
    // roll angle (twist about body x), independent of a small tilt
    Quat q0{};
    Quat q1 = Quat::from_axis_angle(Vec3{1, 0, 0}, deg2rad(30.0f));
    NEAR(rad2deg(twist_about_x(q0, q1)), 30.0f, 1e-3f);
    Quat q2 = Quat::from_axis_angle(Vec3{0, 1, 0}, deg2rad(5.0f)) * q1;
    NEAR(rad2deg(twist_about_x(q0, q2)), 30.0f, 0.5f);
    NEAR(rad2deg(wrap_pi(deg2rad(190.0f))), -170.0f, 1e-3f);
}

// Full computer: in BOOST and COAST the tabs must oppose a roll rate, stay centred on the pad, under the
// parachute and when the feature is switched off.
static void test_fins_in_flight() {
    for (int enabled = 0; enabled < 2; ++enabled) {
        FlightComputer fc;
        Config cfg;
        cfg.motor = &kMotors[kDefaultMotor];
        cfg.airframe = &kAirframe;
        cfg.fins.enabled = enabled != 0;
        fc.init(cfg);
        const float dt = 0.002f;
        float t = 0, v = 0, h = 0;
        bool saw_boost_tabs = false, saw_coast_tabs = false;
        for (int i = 0; i < 20 * 500; ++i, t += dt) {
            SensorFrame s;
            s.t = t;
            const float t_ign = 6.0f;
            float a_kin = 0.0f;
            if (t >= t_ign && t < t_ign + 2.0f) a_kin = 30.0f;
            else if (t >= t_ign + 2.0f) a_kin = -kG0 - 0.003f * v * std::fabs(v);
            if (t >= t_ign) { v += a_kin * dt; h += v * dt; }
            s.accel = Vec3{a_kin + kG0, 0, 0};
            s.gyro = (t > t_ign + 0.5f) ? Vec3{deg2rad(40.0f), 0, 0} : Vec3{};   // rolling at +40 deg/s
            s.baro_new = (i % 20) == 0;
            s.baro_pa = 101325.0f * std::pow(1.0f - h / 44330.0f, 5.255f);
            ActuatorCmd o = fc.step(s);
            const bool flying = o.state == FlightState::BOOST || o.state == FlightState::COAST;
            if (!flying) {
                for (int k = 0; k < 4; ++k) NEAR(o.tab_deg[k], 0.0f, 1e-6f);
            } else if (t > t_ign + 1.0f && v > 10.0f && std::fabs(fc.roll_deg()) < 150.0f) {
                // (beyond 180 deg of accumulated roll the angle-hold term legitimately takes the shorter way back)
                if (enabled) {
                    // roll +40 deg/s must be met with a negative (anti-roll) command on all four tabs
                    const float mean = 0.25f * (o.tab_deg[0] + o.tab_deg[1] + o.tab_deg[2] + o.tab_deg[3]);
                    CHECK(mean < 0.0f, "t=%g mean tab %g", double(t), double(mean));
                    if (o.state == FlightState::BOOST) saw_boost_tabs = true; else saw_coast_tabs = true;
                } else {
                    for (int k = 0; k < 4; ++k) NEAR(o.tab_deg[k], 0.0f, 1e-6f);
                }
            }
        }
        if (enabled) CHECK(saw_boost_tabs && saw_coast_tabs, "tabs used in boost %d and coast %d", int(saw_boost_tabs), int(saw_coast_tabs));
    }
}

int main() {
    test_fin_mixer();
    test_fins_in_flight();
    test_robust_arming();
    test_quaternions();
    test_attitude();
    test_kf();
    test_tvc_sign_and_limits();
    test_state_machine(false, false);
    test_state_machine(true, false);
    test_state_machine(false, true);
    test_logrecord();
    std::printf("%d checks passed, %d failed\n", g_pass, g_fail);
    return g_fail ? EXIT_FAILURE : EXIT_SUCCESS;
}
