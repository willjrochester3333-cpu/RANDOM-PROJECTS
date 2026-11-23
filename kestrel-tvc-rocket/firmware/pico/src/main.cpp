// KESTREL FC - Raspberry Pi Pico 2 W flight firmware.
//
// 500 Hz loop on core 0:  sensors -> flight core (estimators, TVC, state machine) -> servos / buzzer / LEDs
//                         -> flash log, plus a USB command line for bench set-up and log download.
// The flight core (firmware/core) is the exact code that flew 1000+ simulated flights in sim/ (SIL).
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>

#include "app/logger.hpp"
#include "app/settings_store.hpp"
#include "board.hpp"
#include "hardware/gpio.h"
#include "hardware/watchdog.h"
#include "hw/io.hpp"
#include "hw/sensors.hpp"
#include "kestrel/flight.hpp"
#include "kestrel/motor_db.hpp"
#include "logic/axis_cal.hpp"
#include "logic/servo_map.hpp"
#include "pico/bootrom.h"
#include "pico/stdlib.h"

using namespace kestrel;

namespace {

constexpr uint16_t kFwVersion = 202;            // 2.02 (KESTREL-2: direct-drive fin tabs, servos inside the fins)
constexpr uint32_t kScratchMagic = 0x4B53u;     // watchdog scratch tag ("KS")
constexpr float kPadTiltWarnDeg = 20.0f;        // pad rod tilt is 0-15 deg by design

hw::Lsm6dso imu;
hw::Bmp58x baro;
hw::W25q flash;
hw::Gps gps;
hw::Ui ui;
app::Logger logger;
Settings S;
bool settings_ok = false;
FlightComputer fc;
Config cfg;

enum class Mode : uint8_t { FLIGHT, BENCH, AXIS_CAL, TVC_TEST, DIR_TEST, TAB_TEST, FIN_TEST };
Mode mode = Mode::FLIGHT;
bool recovery_mode = false;                     // came back from a watchdog reset while flying

uint64_t t0_us = 0;
float raw_g[3]{}, raw_a[3]{};                   // latest raw IMU sample (sensor axes)
float body_g[3]{}, body_a[3]{};
float last_p = 0, last_tc = 0;
uint64_t last_baro_us = 0, last_imu_us = 0;
GpsFix last_fix{};
hw::Power pwr{};
float vbat_f = 0;
ActuatorCmd last_out{};
uint32_t loop_overruns = 0, max_loop_us = 0;
bool landed_saved = false;

// ------------------------------------------------------------------ helpers
bool on_ground_state(FlightState s) {
    return s == FlightState::BOOT || s == FlightState::CALIBRATING || s == FlightState::READY ||
           s == FlightState::ERROR || s == FlightState::LANDED;
}

void apply_config() {
    cfg = Config{};
    const int mi = S.motor_index < kNumMotors ? S.motor_index : kDefaultMotor;
    cfg.motor = &kMotors[mi];
    cfg.logic.hold_launch_attitude = S.hold_launch_attitude != 0;
    cfg.tvc.max_gimbal_deg = S.max_gimbal_deg;
    cfg.airframe = &kAirframe;
    cfg.fins.enabled = S.tabs_enabled != 0;
    cfg.fins.max_tab_deg = S.max_tab_deg;
    cfg.fins.roll_program_dps = S.roll_program_dps;
    fc.init(cfg);
    t0_us = time_us_64();
}

void write_tabs(const float* tab_deg) {      // nullptr = all four centred
    for (int k = 0; k < 4; ++k) hw::servo_write_us(SERVO_TAB1 + k, tab_to_pulse(S, k, tab_deg ? tab_deg[k] : 0.0f));
}

void outputs_safe() {
    float r, m;
    gimbal_to_pulses(S, 0, 0, r, m);
    hw::servo_write_us(SERVO_TVC_RING, r);
    hw::servo_write_us(SERVO_TVC_MOTOR, m);
    hw::servo_write_us(SERVO_DEPLOY, S.deploy_latched_us + S.trim_us[SERVO_DEPLOY]);
    write_tabs(nullptr);
}

float pad_tilt_deg() {
    const Vec3 a = fc.att().accel_avg();
    const float n = a.norm();
    if (n < 1.0f) return 0.0f;
    return std::acos(std::fmax(-1.0f, std::fmin(1.0f, a.x / n))) * 57.2958f;
}

bool warning_active(FlightState st) {
    if (vbat_f > 1.0f && vbat_f < 7.0f) return true;                 // 2S below 3.5 V/cell
    if (pwr.servo_v > 1.0f && pwr.servo_v < 4.5f) return true;       // servo rail sagging / off
    if (!S.axes_valid) return true;
    if (st == FlightState::READY && pad_tilt_deg() > kPadTiltWarnDeg) return true;
    if (st == FlightState::READY && logger.ok() && logger.ready_bytes() < 256u * 1024u) return true;
    return false;
}

// ------------------------------------------------------------------ bench state
struct Bench {
    // axis calibration
    int step{0};
    bool enter_pressed{false};
    float acc_sum[3]{};
    int n{0};
    float pose1[3]{}, pose2[3]{};
    AxisMap result{};
    // tvc test
    AttitudeEstimator att;
    TvcController tvc;
    Quat q_lock{};
    Vec3 target{1, 0, 0};
    float t_start{0};
    uint64_t t_mode_us{0};
} bench;

void leave_bench(const char* why) {
    mode = Mode::FLIGHT;
    outputs_safe();
    apply_config();
    printf("\n%s -> back to flight mode (re-calibrating)\n> ", why);
}

// ------------------------------------------------------------------ CLI
char line[96];
int line_len = 0;

void print_help() {
    printf(
        "\nKESTREL FC %u.%02u commands:\n"
        "  status                 sensors, battery, GPS, log, settings\n"
        "  calaxes                measure IMU->rocket axes (2 still poses) - REQUIRED once\n"
        "  dirtest                move each TVC axis +3 deg so you can check the direction\n"
        "  tabtest                move each fin tab +10 deg in turn so you can check the direction\n"
        "  dir <1-7> <1|-1>       flip a servo direction (1-2 TVC, 4-7 fin tabs 1-4)\n"
        "  tvctest                live closed-loop TVC on the bench (tilt the rocket, watch the nozzle)\n"
        "  fintest                live closed-loop fin tabs on the bench (twist / tilt the rocket, watch the tabs)\n"
        "  center                 TVC + tabs to centre, parachute latch locked\n"
        "  servo <1-7> <us>       raw servo pulse (bench only)\n"
        "  trim <1-7> <us>        centre offset per servo\n"
        "  tabs <1|0>             fin-tab control on / off\n"
        "  tabmax <deg>           tab deflection limit (default 15)\n"
        "  rollprog <deg/s>       camera panorama roll in the coast (0 = hold the launch roll angle)\n"
        "  deploy <lock|release>  move the parachute latch\n"
        "  deployus <lock> <rel>  latch pulse widths (us)\n"
        "  motor [n]              list / choose the motor profile\n"
        "  hold <1|0>             TVC holds the launch-rod direction (1) or vertical (0)\n"
        "  save | defaults        store settings in flash | factory settings\n"
        "  log | dump [first]     log summary | CSV dump over USB\n"
        "  erase yes              wipe the flight-log flash (~40 s)\n"
        "  reboot | bootsel       restart | USB drive for new firmware\n",
        kFwVersion / 100, kFwVersion % 100);
}

void print_status() {
    const FlightState st = fc.state();
    printf("\nstate %s%s  t=%.1fs  loop max %lu us, overruns %lu\n", state_name(st), recovery_mode ? " (RECOVERY)" : "",
           static_cast<double>((time_us_64() - t0_us) * 1e-6), static_cast<unsigned long>(max_loop_us),
           static_cast<unsigned long>(loop_overruns));
    printf("IMU %s (id %02X) axes %s  body accel %.2f %.2f %.2f m/s2  gyro %.3f %.3f %.3f rad/s  pad tilt %.1f deg\n",
           imu.ok() ? "ok" : "FAIL", imu.who_am_i(), S.axes_valid ? "calibrated" : "NOT CALIBRATED (calaxes)",
           static_cast<double>(body_a[0]), static_cast<double>(body_a[1]), static_cast<double>(body_a[2]),
           static_cast<double>(body_g[0]), static_cast<double>(body_g[1]), static_cast<double>(body_g[2]),
           static_cast<double>(pad_tilt_deg()));
    printf("baro %s (id %02X) %.1f Pa %.1f C  alt %.2f m (kf %.2f m, %.2f m/s)\n", baro.ok() ? "ok" : "FAIL", baro.chip_id(),
           static_cast<double>(last_p), static_cast<double>(last_tc), static_cast<double>(fc.baro_alt()),
           static_cast<double>(fc.kf().h()), static_cast<double>(fc.kf().v()));
    const auto& nf = gps.parser().fix();
    printf("GPS %lu baud, %s, %u sats, hdop %.1f, %.6f %.6f, %.1f m MSL (%lu good / %lu bad sentences)\n",
           static_cast<unsigned long>(gps.baud()), nf.valid ? "FIX" : "no fix", nf.sats, static_cast<double>(nf.hdop),
           nf.lat_deg, nf.lon_deg, static_cast<double>(nf.alt_m), static_cast<unsigned long>(gps.parser().good_sentences()),
           static_cast<unsigned long>(gps.parser().bad_checksums()));
    printf("battery %.2f V (cells %.2f / %.2f)  servo rail %.2f V\n", static_cast<double>(pwr.vbat), static_cast<double>(pwr.cell1),
           static_cast<double>(pwr.cell2), static_cast<double>(pwr.servo_v));
    printf("log flash %s (jedec %06lX): %lu records, %lu kB verified blank ahead, %lu dropped\n", flash.ok() ? "ok" : "FAIL",
           static_cast<unsigned long>(flash.jedec()), static_cast<unsigned long>(logger.count_records()),
           static_cast<unsigned long>(logger.ready_bytes() / 1024u), static_cast<unsigned long>(logger.dropped()));
    printf("motor %s, hold %s, max gimbal %.1f deg, deploy %.0f/%.0f us, flights %lu%s\n",
           cfg.motor->name, S.hold_launch_attitude ? "rod" : "vertical", static_cast<double>(S.max_gimbal_deg),
           static_cast<double>(S.deploy_latched_us), static_cast<double>(S.deploy_released_us), static_cast<unsigned long>(S.flights),
           settings_ok ? "" : " (defaults - not saved)");
    printf("servo trims us:");
    for (int i = 0; i < kServoCount; ++i) printf(" %d:%.0f", i + 1, static_cast<double>(S.trim_us[i]));
    printf("   dirs:");
    for (int i = 0; i < kServoCount; ++i) printf(" %d:%+d", i + 1, S.dir[i]);
    printf("\nfin tabs %s, limit %.1f deg, ", S.tabs_enabled ? "ON" : "OFF", static_cast<double>(S.max_tab_deg));
    if (std::fabs(S.tab_servo_arm_mm - S.tab_horn_mm) < 1e-3f)
        printf("direct drive (servo angle = tab angle)");
    else
        printf("linkage %.1f/%.1f mm", static_cast<double>(S.tab_servo_arm_mm), static_cast<double>(S.tab_horn_mm));
    printf(", roll programme %.0f deg/s\n", static_cast<double>(S.roll_program_dps));
    const auto& fs = fc.stats();
    if (fs.t_launch > 0)
        printf("last flight: apogee %.1f m at %.2f s, max tilt %.1f deg, max roll rate %.0f deg/s, deploy reason %u%s%s\n",
               static_cast<double>(fs.max_alt_m), static_cast<double>(fs.t_apogee - fs.t_launch), static_cast<double>(fs.max_tilt_deg),
               static_cast<double>(fs.max_roll_rate_dps), fs.deploy_reason,
               fs.abort ? " ABORT" : "", fs.unarmed_launch ? " (launched before READY)" : "");
}

void dump_log(uint32_t first) {
    const uint32_t n = logger.count_records();
    printf("t_ms,state,flags,gx_dps,gy_dps,gz_dps,ax,ay,az,alt_m,vz_ms,baro_alt_m,tilt_deg,gimbal_y,gimbal_z,vbat,lat,lon,gps_alt,sats,"
           "qx,qy,qz,tab1,tab2,tab3,tab4,roll_deg\n");
    LogRecord r;
    uint32_t bad = 0;
    for (uint32_t i = first; i < n; ++i) {
        flash.read(i * 64u, reinterpret_cast<uint8_t*>(&r), 64);
        if (r.state == app::kFillerState) continue;
        if (crc16_ccitt(&r, 62) != r.crc16) { ++bad; continue; }
        if (r.state == app::kHeaderState) {
            printf("# session: fw %d flight %d motor %s\n", r.gyro_cdps[0], r.gyro_cdps[1],
                   r.flags < kNumMotors ? kMotors[r.flags].name : "?");
            continue;
        }
        printf("%lu,%u,%u,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%.2f,%.3f,%.7f,%.7f,%d,%u,%.4f,%.4f,%.4f,"
               "%.2f,%.2f,%.2f,%.2f,%.2f\n",
               static_cast<unsigned long>(r.t_ms), r.state, r.flags, r.gyro_cdps[0] * 0.01, r.gyro_cdps[1] * 0.01,
               r.gyro_cdps[2] * 0.01, r.accel_cmss[0] * 0.01, r.accel_cmss[1] * 0.01, r.accel_cmss[2] * 0.01,
               static_cast<double>(r.alt_m), static_cast<double>(r.vz_ms), static_cast<double>(r.baro_alt_m), r.tilt_cdeg * 0.01,
               r.gimbal_y_cdeg * 0.01, r.gimbal_z_cdeg * 0.01, r.vbat_mv * 0.001, static_cast<double>(r.lat_deg),
               static_cast<double>(r.lon_deg), r.gps_alt_m, r.sats, r.q_i16[0] / 32767.0, r.q_i16[1] / 32767.0,
               r.q_i16[2] / 32767.0, r.tab_qdeg[0] * 0.25, r.tab_qdeg[1] * 0.25, r.tab_qdeg[2] * 0.25, r.tab_qdeg[3] * 0.25,
               r.roll_cdeg * 0.01);
        if ((i & 63u) == 0) watchdog_update();
    }
    printf("# end: %lu records, %lu failed CRC\n", static_cast<unsigned long>(n - first), static_cast<unsigned long>(bad));
}

void handle_command(char* cmd) {
    char* argv[4] = {};
    int argc = 0;
    for (char* tok = std::strtok(cmd, " \t"); tok && argc < 4; tok = std::strtok(nullptr, " \t")) argv[argc++] = tok;
    if (argc == 0) return;
    const char* c = argv[0];
    const FlightState st = fc.state();
    const bool ground = on_ground_state(st) && !recovery_mode;
    auto need_ground = [&]() {
        if (!ground) printf("refused: only on the ground (state %s)\n", state_name(st));
        return ground;
    };

    if (!std::strcmp(c, "help") || !std::strcmp(c, "?")) { print_help(); return; }
    if (!std::strcmp(c, "status") || !std::strcmp(c, "s")) { print_status(); return; }
    if (!std::strcmp(c, "calaxes")) {
        if (!need_ground()) return;
        mode = Mode::AXIS_CAL;
        bench = Bench{};
        printf("\nAXIS CALIBRATION\nPose 1: stand the rocket NOSE STRAIGHT UP (e.g. on the launch rod), hands off, then press Enter.\n");
        return;
    }
    if (!std::strcmp(c, "dirtest")) {
        if (!need_ground()) return;
        mode = Mode::DIR_TEST;
        bench = Bench{};
        bench.t_mode_us = time_us_64();
        printf("\nDIRECTION TEST (nozzle = bottom of the motor):\n"
               " 0-2 s  servo 1 at +3 deg: nozzle must swing AWAY from the CAMERA POD\n"
               " 3-5 s  servo 2 at +3 deg: nozzle must swing AWAY from the PAYLOAD-DOOR side\n"
               "If one is wrong: dir <1|2> -1, save, repeat.\n");
        return;
    }
    if (!std::strcmp(c, "tabtest")) {
        if (!need_ground()) return;
        mode = Mode::TAB_TEST;
        bench = Bench{};
        bench.t_mode_us = time_us_64();
        printf("\nTAB DIRECTION TEST: tabs 1-4 (fin #1 has the pip, then going round towards the launch lug)\n"
               "move to +10 deg one after another for 1.5 s. Look at the tail from behind (nozzle towards you):\n"
               "each tab's TRAILING EDGE must swing ANTICLOCKWISE, towards the fin with the next-lower number\n"
               "(tab 1 towards fin 4). If one is wrong: dir <4-7> -1 (tab 1 = servo 4), save, repeat.\n");
        return;
    }
    if (!std::strcmp(c, "fintest")) {
        if (!need_ground()) return;
        if (!S.axes_valid) { printf("run calaxes first\n"); return; }
        mode = Mode::FIN_TEST;
        bench = Bench{};
        bench.t_mode_us = time_us_64();
        printf("\nFIN-TAB BENCH TEST (gains for ~30 m/s): hold the rocket upright and still for 2 s, then\n"
               " * twist it about its long axis: all four tabs swing the same way, trying to twist it back;\n"
               " * tilt it: the tabs on the two fins nearest the tilt plane swing to push the nose back up.\n"
               "60 s limit; press Enter to stop.\n");
        return;
    }
    if (!std::strcmp(c, "tabs") && argc == 2) {
        if (!need_ground()) return;
        S.tabs_enabled = std::atoi(argv[1]) ? 1 : 0;
        apply_config();
        printf("fin-tab control %s (save to keep)\n", S.tabs_enabled ? "ON" : "OFF");
        return;
    }
    if (!std::strcmp(c, "tabmax") && argc == 2) {
        if (!need_ground()) return;
        const float v = static_cast<float>(std::atof(argv[1]));
        if (v < 2.0f || v > 15.0f) { printf("tabmax 2..15 deg\n"); return; }
        S.max_tab_deg = v;
        apply_config();
        printf("tab limit %.1f deg (save to keep)\n", static_cast<double>(v));
        return;
    }
    if (!std::strcmp(c, "rollprog") && argc == 2) {
        if (!need_ground()) return;
        const float v = static_cast<float>(std::atof(argv[1]));
        if (v < 0.0f || v > 180.0f) { printf("rollprog 0..180 deg/s\n"); return; }
        S.roll_program_dps = v;
        apply_config();
        if (v > 0.0f) printf("camera panorama: %.0f deg/s roll in the coast (save to keep)\n", static_cast<double>(v));
        else printf("roll held at the launch angle (save to keep)\n");
        return;
    }
    if (!std::strcmp(c, "tvctest")) {
        if (!need_ground()) return;
        if (!S.axes_valid) { printf("run calaxes first\n"); return; }
        mode = Mode::TVC_TEST;
        bench = Bench{};
        bench.t_mode_us = time_us_64();
        printf("\nTVC BENCH TEST: hold the rocket upright and still for 2 s, then tilt it slowly by hand.\n"
               "The nozzle must swing OPPOSITE to the way the nose leans (like balancing a broom).\n"
               "Motor OUT. 60 s limit; press Enter to stop.\n");
        return;
    }
    if (!std::strcmp(c, "center")) {
        if (!need_ground()) return;
        mode = Mode::BENCH;
        outputs_safe();
        printf("centred (bench mode: 'reboot' or any flight command returns to flight mode)\n");
        return;
    }
    if (!std::strcmp(c, "servo") && argc == 3) {
        if (!need_ground()) return;
        const int ch = std::atoi(argv[1]) - 1;
        const float us = static_cast<float>(std::atof(argv[2]));
        if (ch < 0 || ch >= kServoCount || us < 800 || us > 2200) { printf("usage: servo <1-7> <800-2200>\n"); return; }
        mode = Mode::BENCH;
        hw::servo_write_us(ch, us);
        printf("servo %d -> %.0f us\n", ch + 1, static_cast<double>(us));
        return;
    }
    if (!std::strcmp(c, "trim") && argc == 3) {
        const int ch = std::atoi(argv[1]) - 1;
        if (ch < 0 || ch >= kServoCount) { printf("usage: trim <1-7> <us>\n"); return; }
        if (!need_ground()) return;
        S.trim_us[ch] = static_cast<float>(std::atof(argv[2]));
        mode = Mode::BENCH;
        outputs_safe();
        printf("trim %d = %.0f us (save to keep)\n", ch + 1, static_cast<double>(S.trim_us[ch]));
        return;
    }
    if (!std::strcmp(c, "dir") && argc == 3) {
        const int ch = std::atoi(argv[1]) - 1;
        const int d = std::atoi(argv[2]);
        if (ch < 0 || ch >= kServoCount || ch == SERVO_DEPLOY || (d != 1 && d != -1)) { printf("usage: dir <1,2,4-7> <1|-1>\n"); return; }
        S.dir[ch] = static_cast<int8_t>(d);
        printf("servo %d direction %d (save to keep)\n", ch + 1, d);
        return;
    }
    if (!std::strcmp(c, "deploy") && argc == 2) {
        if (!need_ground()) return;
        mode = Mode::BENCH;
        const bool rel = !std::strcmp(argv[1], "release");
        hw::servo_write_us(SERVO_DEPLOY, (rel ? S.deploy_released_us : S.deploy_latched_us) + S.trim_us[SERVO_DEPLOY]);
        printf("deploy latch %s\n", rel ? "RELEASED" : "locked");
        return;
    }
    if (!std::strcmp(c, "deployus") && argc == 3) {
        S.deploy_latched_us = static_cast<float>(std::atof(argv[1]));
        S.deploy_released_us = static_cast<float>(std::atof(argv[2]));
        printf("deploy lock %.0f us, release %.0f us (save to keep)\n", static_cast<double>(S.deploy_latched_us),
               static_cast<double>(S.deploy_released_us));
        return;
    }
    if (!std::strcmp(c, "motor")) {
        if (argc == 2) {
            if (!need_ground()) return;
            const int i = std::atoi(argv[1]);
            if (i < 0 || i >= kNumMotors) { printf("no motor %d\n", i); return; }
            S.motor_index = static_cast<uint8_t>(i);
            apply_config();
        }
        for (int i = 0; i < kNumMotors; ++i)
            printf(" %d %-10s burn %.2f s, nominal apogee time %.1f s%s\n", i, kMotors[i].name,
                   static_cast<double>(kMotors[i].burn_time), static_cast<double>(kMotors[i].apogee_time_nominal),
                   cfg.motor == &kMotors[i] ? "  <- selected" : "");
        return;
    }
    if (!std::strcmp(c, "hold") && argc == 2) {
        if (!need_ground()) return;
        S.hold_launch_attitude = std::atoi(argv[1]) ? 1 : 0;
        apply_config();
        printf("TVC holds the %s\n", S.hold_launch_attitude ? "launch-rod direction" : "vertical");
        return;
    }
    if (!std::strcmp(c, "save")) {
        if (!need_ground()) return;
        settings_ok = app::settings_save(S);
        printf(settings_ok ? "saved\n" : "SAVE FAILED\n");
        return;
    }
    if (!std::strcmp(c, "defaults")) {
        if (!need_ground()) return;
        S = Settings{};
        apply_config();
        printf("factory settings loaded (not saved; IMU axes need calaxes)\n");
        return;
    }
    if (!std::strcmp(c, "log")) {
        printf("%lu records (%.1f%% of 16 MB), %lu kB blank ahead, %lu dropped\n", static_cast<unsigned long>(logger.count_records()),
               static_cast<double>(logger.write_addr() / 167772.16f), static_cast<unsigned long>(logger.ready_bytes() / 1024u),
               static_cast<unsigned long>(logger.dropped()));
        return;
    }
    if (!std::strcmp(c, "dump")) {
        if (!need_ground()) return;
        logger.flush_partial();
        for (int i = 0; i < 400 && !logger.idle(); ++i) { logger.service(false); sleep_ms(2); watchdog_update(); }
        dump_log(argc == 2 ? static_cast<uint32_t>(std::atol(argv[1])) : 0u);
        return;
    }
    if (!std::strcmp(c, "erase") && argc == 2 && !std::strcmp(argv[1], "yes")) {
        if (!need_ground()) return;
        printf("erasing 16 MB...\n");
        watchdog_disable();
        logger.erase_all_blocking();
        watchdog_enable(250, true);
        printf("done\n");
        return;
    }
    if (!std::strcmp(c, "reboot")) { watchdog_reboot(0, 0, 10); for (;;) {} }
    if (!std::strcmp(c, "bootsel")) {
        if (!need_ground()) return;
        reset_usb_boot(0, 0);
    }
    printf("unknown command '%s' (help)\n", c);
}

void poll_cli() {
    for (int k = 0; k < 16; ++k) {
        const int ch = getchar_timeout_us(0);
        if (ch == PICO_ERROR_TIMEOUT) return;
        if (ch == '\r' || ch == '\n') {
            if (mode == Mode::AXIS_CAL || mode == Mode::TVC_TEST || mode == Mode::FIN_TEST) bench.enter_pressed = true;
            line[line_len] = '\0';
            if (line_len > 0) {
                printf("\n");
                handle_command(line);
            }
            line_len = 0;
            printf("> ");
            continue;
        }
        if ((ch == 8 || ch == 127) && line_len > 0) { --line_len; printf("\b \b"); continue; }
        if (ch >= 32 && ch < 127 && line_len < static_cast<int>(sizeof(line)) - 1) {
            line[line_len++] = static_cast<char>(ch);
            putchar(ch);
        }
    }
}

// ------------------------------------------------------------------ bench modes (one step per loop)
void bench_step(uint64_t now) {
    const float dt = 1.0f / board::LOOP_HZ;
    if (mode == Mode::AXIS_CAL) {
        if (bench.step == 0 || bench.step == 2) {                 // waiting for Enter
            if (bench.enter_pressed) { bench.enter_pressed = false; bench.step++; bench.n = 0; for (float& v : bench.acc_sum) v = 0; }
        } else {                                                  // averaging 1 s of raw accelerometer
            for (int i = 0; i < 3; ++i) bench.acc_sum[i] += raw_a[i];
            if (++bench.n == static_cast<int>(board::LOOP_HZ)) {
                float* dst = bench.step == 1 ? bench.pose1 : bench.pose2;
                for (int i = 0; i < 3; ++i) dst[i] = bench.acc_sum[i] / static_cast<float>(bench.n);
                printf("  pose %d raw accel: %.2f %.2f %.2f m/s2\n", bench.step == 1 ? 1 : 2, static_cast<double>(dst[0]),
                       static_cast<double>(dst[1]), static_cast<double>(dst[2]));
                if (bench.step == 1) {
                    printf("Pose 2: lay the rocket FLAT on its side with the CAMERA POD pointing straight DOWN, hands off, press Enter.\n");
                    bench.step = 2;
                } else {
                    AxisMap m;
                    const AxisCalResult r = solve_axis_map(bench.pose1, bench.pose2, m);
                    if (r == AxisCalResult::OK) {
                        S.axes = m;
                        S.axes_valid = 1;
                        printf("OK. body = M * sensor, M = [%d %d %d; %d %d %d; %d %d %d]\nType 'save' to keep it.\n",
                               m.m[0][0], m.m[0][1], m.m[0][2], m.m[1][0], m.m[1][1], m.m[1][2], m.m[2][0], m.m[2][1], m.m[2][2]);
                    } else {
                        printf("FAILED: %s. Run calaxes again.\n", axis_cal_message(r));
                    }
                    leave_bench("axis calibration finished");
                }
            }
        }
        return;
    }
    if (mode == Mode::DIR_TEST) {
        const float t = static_cast<float>((now - bench.t_mode_us) * 1e-6);
        float gy = 0, gz = 0;
        if (t < 2.0f) gy = 3.0f;
        else if (t >= 3.0f && t < 5.0f) gz = 3.0f;
        float r, m;
        gimbal_to_pulses(S, gy, gz, r, m);
        hw::servo_write_us(SERVO_TVC_RING, r);
        hw::servo_write_us(SERVO_TVC_MOTOR, m);
        if (t > 6.0f) leave_bench("direction test finished");
        return;
    }
    if (mode == Mode::TVC_TEST) {
        const float t = static_cast<float>((now - bench.t_mode_us) * 1e-6);
        const Vec3 g{body_g[0], body_g[1], body_g[2]};
        const Vec3 a{body_a[0], body_a[1], body_a[2]};
        if (t < 2.0f) {
            bench.att.pad_update(g, a, dt);
            outputs_safe();
            return;
        }
        if (bench.t_start == 0.0f) {
            bench.att.lock_pad_attitude();
            bench.target = bench.att.q().rotate(Vec3{1, 0, 0}).normalized();
            bench.tvc.reset();
            bench.t_start = t;
            printf("locked - tilt the rocket now\n");
        }
        bench.att.propagate(g, dt);                  // subtracts the pad bias itself
        float gy = 0, gz = 0;
        // mid-burn gain schedule of the selected motor; t_active large -> no soft start
        bench.tvc.update(bench.att.q(), bench.target, g - bench.att.bias(), cfg.motor->burn_time * 0.5f, 10.0f, cfg.tvc, *cfg.motor,
                         dt, gy, gz);
        float r, m;
        gimbal_to_pulses(S, gy, gz, r, m);
        hw::servo_write_us(SERVO_TVC_RING, r);
        hw::servo_write_us(SERVO_TVC_MOTOR, m);
        static uint32_t k = 0;
        if (++k % 100 == 0)
            printf("  error %.1f deg  gimbal y %+.1f z %+.1f deg\n", static_cast<double>(bench.tvc.last_error_deg()),
                   static_cast<double>(gy), static_cast<double>(gz));
        if (t > 60.0f || bench.enter_pressed) leave_bench("TVC test stopped");
        return;
    }
    if (mode == Mode::TAB_TEST) {
        const float t = static_cast<float>((now - bench.t_mode_us) * 1e-6);
        float tabs[4] = {0, 0, 0, 0};
        const int k = static_cast<int>(t / 2.0f);
        if (k < 4 && std::fmod(t, 2.0f) < 1.5f) tabs[k] = 10.0f;
        write_tabs(tabs);
        if (t > 8.5f) leave_bench("tab direction test finished");
        return;
    }
    if (mode == Mode::FIN_TEST) {
        const float t = static_cast<float>((now - bench.t_mode_us) * 1e-6);
        const Vec3 g{body_g[0], body_g[1], body_g[2]};
        const Vec3 a{body_a[0], body_a[1], body_a[2]};
        if (t < 2.0f) {
            bench.att.pad_update(g, a, dt);
            write_tabs(nullptr);
            return;
        }
        if (bench.t_start == 0.0f) {
            bench.att.lock_pad_attitude();
            bench.target = bench.att.q().rotate(Vec3{1, 0, 0}).normalized();
            bench.q_lock = bench.att.q();
            bench.t_start = t;
            printf("locked - twist or tilt the rocket now\n");
        }
        bench.att.propagate(g, dt);
        const Vec3 w = g - bench.att.bias();
        const Vec3 e = attitude_error(bench.att.q(), bench.target);
        const float roll = twist_about_x(bench.q_lock, bench.att.q());
        Vec3 alpha{cfg.fins.roll_kp * (-roll) - cfg.fins.roll_kd * w.x, cfg.fins.coast_kp * e.y - cfg.fins.coast_kd * w.y,
                   cfg.fins.coast_kp * e.z - cfg.fins.coast_kd * w.z};
        const MotorProfile& mp = *cfg.motor;
        const float tm = mp.burn_time + 0.5f;
        float tabs[4];
        FinMixer::allocate(alpha, 600.0f, kAirframe.i_roll, motor_interp(mp, mp.i_lat, tm),
                           motor_interp(mp, mp.lever, tm) + kAirframe.tab_dz_m, kAirframe, S.max_tab_deg, tabs);
        write_tabs(tabs);
        static uint32_t k = 0;
        if (++k % 100 == 0)
            printf("  roll %+.0f deg  tilt %.1f deg  tabs %+.1f %+.1f %+.1f %+.1f\n", static_cast<double>(rad2deg(roll)),
                   static_cast<double>(rad2deg(e.norm())), static_cast<double>(tabs[0]), static_cast<double>(tabs[1]),
                   static_cast<double>(tabs[2]), static_cast<double>(tabs[3]));
        if (t > 60.0f || bench.enter_pressed) leave_bench("fin test stopped");
        return;
    }
    // Mode::BENCH: servos hold whatever the CLI set
}

}  // namespace

int main() {
    hw::io_init();
    bool valid = false;
    S = app::settings_load(&valid);
    settings_ok = valid;
    hw::servo_init();
    outputs_safe();                                  // TVC centred + parachute latch LOCKED before anything else
    stdio_init_all();

    const bool wd = watchdog_caused_reboot();
    const uint32_t scratch = watchdog_hw->scratch[0];
    if (wd && (scratch >> 16) == kScratchMagic) {
        const auto prev = static_cast<FlightState>(scratch & 0xFFu);
        // reset while flying: never try to steer again - just get the parachute out
        recovery_mode = (prev == FlightState::BOOST || prev == FlightState::COAST || prev == FlightState::DESCENT);
    }
    if (recovery_mode) hw::servo_write_us(SERVO_DEPLOY, S.deploy_released_us + S.trim_us[SERVO_DEPLOY]);

    hw::spi_init_bus();
    imu.init();
    baro.init();
    flash.init();
    logger.init(&flash);
    gps.init();
    apply_config();
    logger.start_session(S.motor_index, S.flights + 1, kFwVersion, time_us_64());

    watchdog_enable(250, true);
    uint64_t next = time_us_64();
    uint32_t tick = 0;
    for (;;) {
        next += 1000000u / board::LOOP_HZ;
        const uint64_t now = time_us_64();

        // ---------------- sensors
        SensorFrame in;
        in.t = static_cast<float>((now - t0_us) * 1e-6);
        if (imu.ok() && imu.read(raw_g, raw_a)) last_imu_us = now;
        S.axes.apply(raw_g, body_g);
        S.axes.apply(raw_a, body_a);
        in.gyro = Vec3{body_g[0], body_g[1], body_g[2]};
        in.accel = Vec3{body_a[0], body_a[1], body_a[2]};
        in.imu_ok = imu.ok() && S.axes_valid && (now - last_imu_us < 20000u);
        if (baro.ok() && baro.poll(last_p, last_tc)) {
            in.baro_new = true;
            in.baro_pa = last_p;
            last_baro_us = now;
        }
        in.baro_ok = baro.ok() && (now - last_baro_us < 500000u);
        gps.poll();
        GpsFix fx;
        if (gps.take_new_fix(fx)) { last_fix = fx; in.gps_new = true; }
        in.gps = last_fix;
        if (tick % 50 == 0) {                        // 10 Hz power monitoring
            pwr = hw::read_power();
            vbat_f = (vbat_f < 1.0f) ? pwr.vbat : vbat_f + 0.2f * (pwr.vbat - vbat_f);
        }
        in.vbat = vbat_f;

        // ---------------- control
        if (mode == Mode::FLIGHT) {
            ActuatorCmd out = fc.step(in);
            if (recovery_mode) {                     // after an in-flight reset: chute out, TVC + tabs centred, beacon
                out.gimbal_y_deg = out.gimbal_z_deg = 0;
                for (float& d : out.tab_deg) d = 0.0f;
                out.deploy_release = true;
                out.buzzer = Buzz::DESCENT_BEACON;
            }
            float ring_us, motor_us;
            gimbal_to_pulses(S, out.gimbal_y_deg, out.gimbal_z_deg, ring_us, motor_us);
            hw::servo_write_us(SERVO_TVC_RING, ring_us);
            hw::servo_write_us(SERVO_TVC_MOTOR, motor_us);
            hw::servo_write_us(SERVO_DEPLOY, (out.deploy_release ? S.deploy_released_us : S.deploy_latched_us) + S.trim_us[SERVO_DEPLOY]);
            write_tabs(out.tab_deg);
            last_out = out;
            LogRecord r;
            fc.fill_log(r, in, out);
            if (recovery_mode) r.flags |= 0x80u;
            logger.log(r, recovery_mode ? FlightState::DESCENT : out.state);
            watchdog_hw->scratch[0] = (kScratchMagic << 16) | static_cast<uint32_t>(recovery_mode ? FlightState::DESCENT : out.state);
            // landed: close the log page and count the flight (flash write is safe now - nothing to control)
            if (out.state == FlightState::LANDED && !landed_saved && in.t - fc.stats().t_landed > 5.0f) {
                landed_saved = true;
                logger.flush_partial();
                S.flights++;
                if (settings_ok) settings_ok = app::settings_save(S);
            }
        } else {
            bench_step(now);
            watchdog_hw->scratch[0] = (kScratchMagic << 16) | static_cast<uint32_t>(FlightState::BOOT);
        }
        const FlightState st = mode == Mode::FLIGHT ? last_out.state : FlightState::BOOT;
        logger.service(on_ground_state(st) && !recovery_mode);

        // ---------------- user interface
        ui.poll_button(now);
        if (ui.button_pressed_short()) ui.beep_number(static_cast<int>(vbat_f * 10.0f + 0.5f), now);   // e.g. "7-8" = 7.8 V
        if (ui.button_pressed_long()) ui.beep_number(gps.parser().fix().sats, now);                     // satellites in view
        ui.update(mode == Mode::FLIGHT ? last_out.buzzer : Buzz::OFF, st, warning_active(st), fc.stats().max_alt_m, now);
        poll_cli();

        // ---------------- timing
        watchdog_update();
        ++tick;
        const uint64_t used = time_us_64() - now;
        if (used > max_loop_us) max_loop_us = static_cast<uint32_t>(used);
        if (time_us_64() > next) {
            ++loop_overruns;
            next = time_us_64();                     // drop the missed slot instead of bursting
        }
        while (time_us_64() < next) tight_loop_contents();
    }
}
