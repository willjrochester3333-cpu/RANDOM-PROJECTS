// Host unit tests for the KESTREL flight core. Build with CMake and run `ctest`.
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <random>

#include "kestrel/flight.hpp"
#include "kestrel/motor_db.hpp"
#include "kestrel/telemetry.hpp"
#include <cstring>
#include <vector>

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
            a_kin = 24.0f;          // boost (about what an E20 gives this airframe: ~48 m/s at burnout)
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

// ---------------------------------------------------------------- radio telemetry
static void test_telemetry_crc_and_reference_frames() {
    using namespace kestrel::tlm;
    const char* chk = "123456789";
    CHECK(crc_x25(reinterpret_cast<const uint8_t*>(chk), 9) == 0x6F91, "CRC-16/MCRF4XX check value");
    // reference frames from pymavlink 2.4 (MAVLink 1.0, sys 255 comp 190, seq 0)
    const uint8_t hb_ref[] = {0xfe, 0x09, 0x00, 0xff, 0xbe, 0x00, 0x00, 0x00, 0x00, 0x00, 0x06, 0x08, 0x00, 0x04, 0x03, 0x49, 0x21};
    const uint8_t hb_payload[] = {0, 0, 0, 0, 6, 8, 0, 4, 3};
    uint8_t out[80];
    size_t n = encode(kMsgHeartbeat, 0, hb_payload, 9, out, 255, 190);
    CHECK(n == sizeof hb_ref && std::memcmp(out, hb_ref, n) == 0, "HEARTBEAT matches pymavlink");
    const uint8_t rs_ref[] = {0xfe, 0x09, 0x00, 0xff, 0xbe, 0x6d, 0x03, 0x00, 0x01, 0x00, 0xb4, 0xaa, 0x5a, 0x28, 0x2d, 0xce, 0x56};
    Decoder d;
    bool got = false;
    for (uint8_t b : rs_ref) got = d.feed(b) || got;
    CHECK(got && d.msgid() == kMsgRadioStatus && d.len() == 9, "RADIO_STATUS decoded");
    RadioStatus rs;
    std::memcpy(&rs, d.payload(), sizeof rs);
    CHECK(rs.rssi == 180 && rs.remrssi == 170 && rs.txbuf == 90 && rs.noise == 40 && rs.remnoise == 45 && rs.rxerrors == 3 &&
              rs.fixed == 1, "RADIO_STATUS fields");
}

static void test_telemetry_roundtrip_and_resync() {
    using namespace kestrel::tlm;
    LogRecord r{};
    r.t_ms = 123456; r.state = 4; r.flags = 0x21; r.alt_m = 151.25f; r.vz_ms = -3.456f; r.tilt_cdeg = 512;
    r.gyro_cdps[0] = -1500; r.accel_cmss[2] = 981; r.q_i16[1] = 1234; r.tab_qdeg[3] = -40; r.roll_cdeg = 4500;
    r.gimbal_y_cdeg = 120; r.gimbal_z_cdeg = -80;
    FastPayload f;
    make_fast(r, f);
    CHECK(f.vz_cms == -346 && f.alt_m == 151.25f && f.gimbal_cdeg[1] == -80 && f.tab_qdeg[3] == -40, "fast payload fields");
    SlowPayload sl{};
    sl.t_ms = 99; sl.lat_e7 = 515012345; sl.lon_e7 = -1234567; sl.sats = 11; sl.gps_valid = 1; sl.apogee_dm = 1702;
    // a stream: noise, fast, corrupted fast, slow, a foreign MAVLink frame, a false start byte inside noise, fast
    std::vector<uint8_t> st;
    std::mt19937 rng(7);
    for (int i = 0; i < 40; ++i) st.push_back(static_cast<uint8_t>(rng()));
    uint8_t fr[80];
    size_t n = encode(kMsgFast, 1, &f, sizeof f, fr);
    st.insert(st.end(), fr, fr + n);
    n = encode(kMsgFast, 2, &f, sizeof f, fr);
    fr[20] ^= 0x10;                                   // damaged in the air
    st.insert(st.end(), fr, fr + n);
    n = encode(kMsgSlow, 3, &sl, sizeof sl, fr);
    st.insert(st.end(), fr, fr + n);
    const uint8_t foreign[] = {0xfe, 0x03, 0x05, 0x01, 0x01, 0x1e, 0xaa, 0xbb, 0xcc, 0x12, 0x34};   // id 30, unknown here
    st.insert(st.end(), foreign, foreign + sizeof foreign);
    st.push_back(0xfe); st.push_back(0x40); st.push_back(0x00);                 // false start: claims 64 bytes
    n = encode(kMsgFast, 4, &f, sizeof f, fr);
    st.insert(st.end(), fr, fr + n);
    n = encode(kMsgFast, 5, &f, sizeof f, fr);
    st.insert(st.end(), fr, fr + n);
    Decoder d;
    std::vector<int> seqs;
    for (uint8_t b : st) {
        if (d.feed(b)) {
            seqs.push_back(d.seq());
            if (d.msgid() == kMsgSlow) {
                SlowPayload g;
                std::memcpy(&g, d.payload(), sizeof g);
                CHECK(g.lat_e7 == 515012345 && g.lon_e7 == -1234567 && g.apogee_dm == 1702, "slow payload survives");
            } else if (d.msgid() == kMsgFast) {
                FastPayload g;
                std::memcpy(&g, d.payload(), sizeof g);
                CHECK(g.t_ms == 123456 && g.roll_cdeg == 4500, "fast payload survives");
            }
        }
    }
    // the false start swallows up to 64 following bytes, which may include frame 4; frame 5 must always come through
    CHECK(seqs.size() >= 3 && seqs[0] == 1 && seqs[1] == 3 && seqs.back() == 5, "decoded %zu frames, last seq %d",
          seqs.size(), seqs.empty() ? -1 : seqs.back());
    CHECK(d.bad() >= 2, "bad candidates counted (%u)", d.bad());
}

static void test_telemetry_rates_and_budget() {
    using namespace kestrel::tlm;
    const Rates fl = rates_for(FlightState::COAST, 0, 0);
    CHECK(fl.fast_div == 10 && fl.slow_div == 100, "50 Hz + 5 Hz in flight");
    CHECK(rates_for(FlightState::READY, 0, 0).fast_div == 500, "1 Hz on the pad");
    CHECK(rates_for(FlightState::LANDED, 30, 0).slow_div == 500 && rates_for(FlightState::LANDED, 90, 0).slow_div == 2500,
          "landed beacon slows after a minute");
    CHECK(rates_for(FlightState::BOOST, 0, 2).fast_div == 0, "hard limit: no fast frames");
    // airtime of a 50-byte frame at 64 kbit/s: (117 + 52 * 8) ticks * 16 us = 8.53 ms
    NEAR(frame_airtime_s(50), 8.528e-3f, 1e-5f);
    // a busy hour: 4 flights, each 15 min on the pad then 45 s of flight at full rate and 2 min landed
    AirtimeBudget b(60.0f);
    uint32_t t = 0;
    int max_level = 0;
    float max_used = 0;
    const size_t fast_bytes = sizeof(FastPayload) + kOverhead, slow_bytes = sizeof(SlowPayload) + kOverhead;
    auto run = [&](FlightState s, float seconds, float landed0) {
        for (int i = 0; i < static_cast<int>(seconds * 500.0f); ++i, t += 2) {
            const Rates rt = rates_for(s, landed0 + i * 0.002f, b.level());
            if (rt.fast_div && (t / 2) % rt.fast_div == 0) b.add(frame_airtime_s(fast_bytes));
            if (rt.slow_div && (t / 2) % rt.slow_div == 0) b.add(frame_airtime_s(slow_bytes));
            if (i % 50 == 0) b.tick(t);
            max_used = std::fmax(max_used, b.used_s());
            max_level = std::max(max_level, b.level());
        }
    };
    for (int k = 0; k < 4; ++k) {
        run(FlightState::READY, 900, 0);
        run(FlightState::COAST, 45, 0);
        run(FlightState::LANDED, 120, 0);
    }
    CHECK(max_used < AirtimeBudget::kLimitS, "busy hour stays under 360 s (max %.0f s)", double(max_used));
    CHECK(max_level == 0, "a normal busy hour never needs the lean rates (max level %d, max %.0f s)", max_level, double(max_used));
    // stuck streaming at full rate for an hour (e.g. a firmware fault in the state machine): the budget must cap it
    AirtimeBudget c(0.0f);
    t = 0;
    float worst = 0;
    for (int i = 0; i < 3600 * 500; ++i, t += 2) {
        const Rates rt = rates_for(FlightState::COAST, 0, c.level());
        if (rt.fast_div && (t / 2) % rt.fast_div == 0) c.add(frame_airtime_s(fast_bytes));
        if (rt.slow_div && (t / 2) % rt.slow_div == 0) c.add(frame_airtime_s(slow_bytes));
        if (i % 50 == 0) c.tick(t);
        worst = std::fmax(worst, c.used_s());
    }
    CHECK(worst < AirtimeBudget::kLimitS, "continuous streaming capped below 360 s per hour (max %.0f s)", double(worst));
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
    test_telemetry_crc_and_reference_frames();
    test_telemetry_roundtrip_and_resync();
    test_telemetry_rates_and_budget();
    std::printf("%d checks passed, %d failed\n", g_pass, g_fail);
    return g_fail ? EXIT_FAILURE : EXIT_SUCCESS;
}
