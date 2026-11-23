// Host unit tests for the hardware-independent parts of the Pico firmware:
// NMEA parser, IMU axis calibration, servo mapping / settings CRC, and the flash logger (against a RAM flash model).
#include <cmath>
#include <cstdio>
#include <cstring>
#include <random>
#include <vector>

#include "app/logger.hpp"
#include "logic/axis_cal.hpp"
#include "logic/nmea.hpp"
#include "logic/servo_map.hpp"

using namespace kestrel;

static int g_pass = 0, g_fail = 0;
#define CHECK(cond)                                                              \
    do {                                                                         \
        if (cond) ++g_pass;                                                      \
        else { ++g_fail; std::printf("FAIL %s:%d  %s\n", __FILE__, __LINE__, #cond); } \
    } while (0)
#define NEAR(a, b, tol) CHECK(std::fabs((a) - (b)) <= (tol))

// ============================================================ RAM model of the W25Q128 (NOR semantics)
static std::vector<uint8_t> g_flash(hw::W25q::kSize, 0xFF);
static int g_busy_polls = 0;
namespace hw {
bool W25q::init() { ok_ = true; jedec_ = 0xEF4018; return true; }
bool W25q::busy() { if (g_busy_polls > 0) { --g_busy_polls; return true; } return false; }
void W25q::read(uint32_t a, uint8_t* b, size_t n) { std::memcpy(b, &g_flash[a], n); }
void W25q::program_page_start(uint32_t a, const uint8_t* d, size_t n) {
    // page program wraps inside the 256-byte page and can only clear bits
    for (size_t i = 0; i < n; ++i) {
        const uint32_t addr = (a & ~255u) | ((a + i) & 255u);
        g_flash[addr] &= d[i];
    }
    g_busy_polls = 1;
}
void W25q::erase_sector_start(uint32_t a) { std::memset(&g_flash[a & ~4095u], 0xFF, 4096); g_busy_polls = 20; }
void W25q::erase_block_start(uint32_t a) { std::memset(&g_flash[a & ~65535u], 0xFF, 65536); g_busy_polls = 50; }
void W25q::erase_chip_start() { std::fill(g_flash.begin(), g_flash.end(), 0xFF); }
void W25q::cmd_addr(uint8_t, uint32_t) {}
void W25q::write_enable() {}
}  // namespace hw

static LogRecord make_rec(uint32_t t_ms, FlightState st) {
    LogRecord r;
    std::memset(&r, 0, sizeof r);
    r.t_ms = t_ms;
    r.state = static_cast<uint8_t>(st);
    r.alt_m = static_cast<float>(t_ms) * 0.01f;
    r.crc16 = crc16_ccitt(&r, 62);
    return r;
}

struct Decoded {
    std::vector<LogRecord> recs;
    int headers = 0, fillers = 0, bad_crc = 0, erased_inside = 0;
};

static Decoded decode_all() {
    Decoded d;
    uint32_t end = 0;   // last non-erased record
    for (uint32_t i = 0; i < hw::W25q::kSize / 64; ++i) {
        bool erased = true;
        for (int k = 0; k < 64; ++k) erased &= g_flash[i * 64 + k] == 0xFF;
        if (!erased) end = i + 1;
    }
    for (uint32_t i = 0; i < end; ++i) {
        LogRecord r;
        std::memcpy(&r, &g_flash[i * 64], 64);
        bool erased = true;
        for (int k = 0; k < 64; ++k) erased &= g_flash[i * 64 + k] == 0xFF;
        if (erased) { ++d.erased_inside; continue; }
        if (r.state == app::kFillerState) { ++d.fillers; continue; }
        if (crc16_ccitt(&r, 62) != r.crc16) { ++d.bad_crc; continue; }
        if (r.state == app::kHeaderState) { ++d.headers; continue; }
        d.recs.push_back(r);
    }
    return d;
}

// one simulated power-on: pad -> boost/coast -> descent -> landed, n_boost records at 500 Hz
static void fly_session(uint32_t flight_no, int pad_loops, int boost_loops, int descent_loops) {
    hw::W25q f;
    f.init();
    app::Logger lg;
    CHECK(lg.init(&f));
    lg.start_session(2, flight_no, 100, 0);
    uint32_t t = 0;
    for (int i = 0; i < pad_loops; ++i, t += 2) { lg.log(make_rec(t, FlightState::READY), FlightState::READY); lg.service(true); }
    for (int i = 0; i < boost_loops; ++i, t += 2) { lg.log(make_rec(t, FlightState::BOOST), FlightState::BOOST); lg.service(false); }
    for (int i = 0; i < descent_loops; ++i, t += 2) { lg.log(make_rec(t, FlightState::DESCENT), FlightState::DESCENT); lg.service(false); }
    for (int i = 0; i < 3000; ++i, t += 2) { lg.log(make_rec(t, FlightState::LANDED), FlightState::LANDED); lg.service(true); }
    lg.flush_partial();
    for (int i = 0; i < 2000 && !lg.idle(); ++i) lg.service(true);
    CHECK(lg.idle());
    CHECK(lg.dropped() == 0);
}

static void test_logger() {
    std::fill(g_flash.begin(), g_flash.end(), 0xFF);
    fly_session(1, 2500, 4000, 5000);
    Decoded d1 = decode_all();
    CHECK(d1.headers == 1);
    CHECK(d1.bad_crc == 0);
    CHECK(d1.erased_inside == 0);
    int boost = 0;
    for (auto& r : d1.recs) boost += r.state == static_cast<uint8_t>(FlightState::BOOST);
    CHECK(boost == 4000);                      // every boost/coast sample at 500 Hz
    // the pre-launch ring buffer (0.5 s) must appear just before the first boost record
    int idx_first_boost = -1;
    for (size_t i = 0; i < d1.recs.size(); ++i)
        if (d1.recs[i].state == static_cast<uint8_t>(FlightState::BOOST)) { idx_first_boost = static_cast<int>(i); break; }
    CHECK(idx_first_boost > 250);
    if (idx_first_boost > 250) {
        const uint32_t t_boost = d1.recs[idx_first_boost].t_ms;
        CHECK(d1.recs[idx_first_boost - 1].t_ms == t_boost - 2);           // contiguous 500 Hz history
        CHECK(d1.recs[idx_first_boost - 250].t_ms == t_boost - 500);
    }
    // second power-on appends exactly after the first session, no holes, nothing overwritten
    const size_t n1 = d1.recs.size();
    fly_session(2, 1200, 3000, 2000);
    Decoded d2 = decode_all();
    CHECK(d2.headers == 2);
    CHECK(d2.bad_crc == 0);
    CHECK(d2.erased_inside == 0);
    CHECK(d2.recs.size() > n1);
    bool same = true;
    for (size_t i = 0; i < n1 && i < d2.recs.size(); ++i) same &= std::memcmp(&d1.recs[i], &d2.recs[i], 64) == 0;
    CHECK(same);
    // third power-on with garbage written beyond the append point (e.g. half-finished erase): must survive
    uint32_t end = 0;
    for (uint32_t i = 0; i < hw::W25q::kSize / 64; ++i)
        if (g_flash[i * 64] != 0xFF || g_flash[i * 64 + 4] != 0xFF) end = i + 1;
    for (int k = 0; k < 40; ++k) g_flash[end * 64 + 3000 + k] = 0x5A;
    fly_session(3, 3000, 1000, 1000);
    Decoded d3 = decode_all();
    CHECK(d3.headers == 3);
    int boost3 = 0;
    for (auto& r : d3.recs) boost3 += r.state == static_cast<uint8_t>(FlightState::BOOST);
    CHECK(boost3 == 4000 + 3000 + 1000);
    std::printf("logger: %zu records after 3 sessions, %d fillers, %d CRC-rejected (planted garbage)\n", d3.recs.size(),
                d3.fillers, d3.bad_crc);
}

// ============================================================ NMEA
static void feed(NmeaParser& p, const char* s, int* gga = nullptr) {
    int n = 0;
    for (const char* c = s; *c; ++c) n += p.feed(*c);
    if (gga) *gga = n;
}

static void test_nmea() {
    NmeaParser p;
    int n = 0;
    feed(p, "$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47\r\n", &n);   // NMEA reference sentence
    CHECK(n == 1);
    CHECK(p.fix().valid);
    NEAR(p.fix().lat_deg, 48.1173, 1e-4);
    NEAR(p.fix().lon_deg, 11.516667, 1e-5);
    NEAR(p.fix().alt_m, 545.4f, 1e-3f);
    CHECK(p.fix().sats == 8);
    // corrupted checksum is rejected and does not change the fix
    feed(p, "$GPGGA,123520,4807.038,S,01131.000,W,1,08,0.9,545.4,M,46.9,M,,*00\r\n", &n);
    CHECK(n == 0);
    CHECK(p.bad_checksums() == 1);
    NEAR(p.fix().lat_deg, 48.1173, 1e-4);
    // our own sentence builder + southern/western hemispheres + BeiDou talker
    char s[100];
    NmeaParser::make_sentence("GNGGA,101010.00,5130.1234,N,00007.5000,W,1,12,0.7,35.2,M,47.0,M,,", s, sizeof s);
    feed(p, s, &n);
    CHECK(n == 1);
    NEAR(p.fix().lat_deg, 51.502057, 1e-5);
    NEAR(p.fix().lon_deg, -0.125, 1e-6);
    CHECK(p.fix().sats == 12);
    NmeaParser::make_sentence("BDGGA,101011.00,3352.0000,S,15112.0000,E,1,05,1.5,10.0,M,0,M,,", s, sizeof s);
    feed(p, s, &n);
    NEAR(p.fix().lat_deg, -33.866667, 1e-5);
    // no-fix GGA clears validity
    NmeaParser::make_sentence("GNGGA,101012.00,,,,,0,00,99.9,,,,,,", s, sizeof s);
    feed(p, s, &n);
    CHECK(n == 1);
    CHECK(!p.fix().valid);
    // RMC speed, junk and overlong lines are ignored safely
    NmeaParser::make_sentence("GNRMC,101013.00,A,5130.1234,N,00007.5000,W,10.0,90.0,221126,,,A", s, sizeof s);
    feed(p, s, &n);
    NEAR(p.fix().speed_mps, 5.14444f, 1e-4f);
    feed(p, "garbage$$$,,,*ZZ\r\n$GPGGA,1,2,3,4,5,6,7,8,9,0,1,2,3,4,5,6,7,8,9,0,1,2,3,4,5,6,7,8,9,0,1,2,3,4,5,6,7,8,9,0,1,2,3,4,5,6,7,8,9,0,1,2,3,4,5,6,7,8,9,0,1,2\r\n", &n);
    CHECK(n == 0);
}

// ============================================================ axis calibration: all 24 mounting orientations
static void test_axis_cal() {
    std::vector<AxisMap> rots;
    const int perms[6][3] = {{0, 1, 2}, {0, 2, 1}, {1, 0, 2}, {1, 2, 0}, {2, 0, 1}, {2, 1, 0}};
    for (auto& pm : perms)
        for (int s = 0; s < 8; ++s) {
            AxisMap m;
            for (int r = 0; r < 3; ++r)
                for (int c = 0; c < 3; ++c) m.m[r][c] = 0;
            for (int r = 0; r < 3; ++r) m.m[r][pm[r]] = static_cast<int8_t>((s >> r) & 1 ? -1 : 1);
            if (m.is_valid_rotation()) rots.push_back(m);
        }
    CHECK(rots.size() == 24);
    std::mt19937 rng(7);
    std::normal_distribution<float> noise(0.0f, 0.25f);   // m/s^2, plus ~5 deg of hand placement error below
    int solved = 0;
    for (const AxisMap& truth : rots) {
        // sensor reading of a body-frame vector: v_s = M^T v_b
        auto to_sensor = [&](const float vb[3], float vs[3]) {
            for (int c = 0; c < 3; ++c) vs[c] = truth.m[0][c] * vb[0] + truth.m[1][c] * vb[1] + truth.m[2][c] * vb[2];
        };
        const float up_b[3] = {9.81f, 0.6f, -0.5f};          // pose 1: nose up (a few degrees off)
        const float flat_b[3] = {0.7f, -0.4f, 9.79f};         // pose 2: camera down -> +z up
        float up_s[3], flat_s[3];
        to_sensor(up_b, up_s);
        to_sensor(flat_b, flat_s);
        for (int i = 0; i < 3; ++i) { up_s[i] += noise(rng); flat_s[i] += noise(rng); }
        AxisMap got;
        if (solve_axis_map(up_s, flat_s, got) == AxisCalResult::OK) {
            bool same = true;
            for (int r = 0; r < 3; ++r)
                for (int c = 0; c < 3; ++c) same &= got.m[r][c] == truth.m[r][c];
            solved += same;
        }
    }
    CHECK(solved == 24);
    // bad poses are refused
    AxisMap m;
    const float tilted[3] = {6.9f, 6.9f, 0.0f};               // 45 deg: not a clean pose
    const float up[3] = {0, 0, 9.8f};
    CHECK(solve_axis_map(tilted, up, m) == AxisCalResult::POSE1_NOT_VERTICAL);
    CHECK(solve_axis_map(up, up, m) == AxisCalResult::SAME_AXIS);
    const float down[3] = {0, 0, -9.8f};
    CHECK(solve_axis_map(up, down, m) == AxisCalResult::SAME_AXIS);
}

// ============================================================ servo mapping + settings
static void test_servo_settings() {
    Settings s;
    float r, m;
    gimbal_to_pulses(s, 0, 0, r, m);
    NEAR(r, 1500.0f, 1e-3f);
    NEAR(m, 1500.0f, 1e-3f);
    const float k = 10.5f / 0.5f;                             // us per gimbal degree: 1 gimbal deg = 2 servo deg = 21 us
    NEAR(s.linkage_ratio, 0.5f, 1e-6f);                       // must match design.json tvc.linkage_ratio (CAD-checked)
    gimbal_to_pulses(s, 1.0f, 0, r, m);
    NEAR(r - 1500.0f, k, 1e-3f);
    s.dir[SERVO_TVC_MOTOR] = -1;
    s.trim_us[SERVO_TVC_MOTOR] = 12.0f;
    gimbal_to_pulses(s, 0, 2.0f, r, m);
    NEAR(m, 1500.0f + 12.0f - 2.0f * k, 1e-3f);
    gimbal_to_pulses(s, 30.0f, 40.0f, r, m);                  // vector clamp to 6 deg keeps the direction
    NEAR(r - 1500.0f, k * 6.0f * 0.6f, 1e-2f);
    NEAR(m - 1512.0f, -k * 6.0f * 0.8f, 1e-2f);
    s.us_per_servo_deg = 100.0f;                              // absurd setting still cannot exceed 1000..2000 us
    gimbal_to_pulses(s, 6.0f, 0, r, m);
    CHECK(r <= 2000.0f && r >= 1000.0f);
    Settings t;
    settings_seal(t);
    CHECK(settings_valid(t));
    t.trim_us[0] = 3.0f;
    CHECK(!settings_valid(t));
    settings_seal(t);
    CHECK(settings_valid(t));
    CHECK(sizeof(Settings) <= 256);
    // fin tabs, default = direct drive (servo shaft on the hinge line): servo angle = tab angle
    Settings u;
    CHECK(u.version == 5 && u.tab_horn_mm == u.tab_servo_arm_mm);
    NEAR(tab_to_pulse(u, 0, 0.0f), 1500.0f, 1e-3f);
    NEAR(tab_to_pulse(u, 0, 15.0f) - 1500.0f, 10.5f * 15.0f, 0.05f);
    NEAR(tab_to_pulse(u, 2, -15.0f) - 1500.0f, -10.5f * 15.0f, 0.05f);
    NEAR(tab_to_pulse(u, 1, 40.0f), tab_to_pulse(u, 1, 15.0f), 1e-3f);      // clamped to max_tab_deg
    u.dir[SERVO_TAB4] = -1;
    u.trim_us[SERVO_TAB4] = -20.0f;
    NEAR(tab_to_pulse(u, 3, 5.0f), 1500.0f - 20.0f - 10.5f * 5.0f, 0.05f);
    {   // the general pushrod formula still holds: horn*sin(tab) = arm*sin(servo), 14.3/6 mm -> 15 deg tab = 38.1 deg servo
        Settings w;
        w.tab_horn_mm = 14.3f;
        w.tab_servo_arm_mm = 6.0f;
        NEAR(tab_to_pulse(w, 0, 15.0f) - 1500.0f, 10.5f * 38.09f, 0.6f);
    }
    for (float d = -15.0f; d < 14.9f; d += 0.5f) {                            // monotonic, inside the servo range
        const float a0 = tab_to_pulse(u, 0, d), a1 = tab_to_pulse(u, 0, d + 0.5f);
        CHECK(a1 > a0 && a0 >= 1000.0f && a1 <= 2000.0f);
    }
    const char* v = "123456789";
    CHECK(crc32(v, 9) == 0xCBF43926u);                        // standard check values
    CHECK(crc16_ccitt(v, 9) == 0x29B1u);
}

int main() {
    test_nmea();
    test_axis_cal();
    test_servo_settings();
    test_logger();
    std::printf("%d checks passed, %d failed\n", g_pass, g_fail);
    return g_fail ? 1 : 0;
}
