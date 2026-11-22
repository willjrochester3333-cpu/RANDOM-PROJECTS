#include "kestrel/flight.hpp"

#include <cmath>

namespace kestrel {

// ===========================================================================
float motor_interp(const MotorProfile& m, const float* table, float t) {
    if (m.n == 0) return 0.0f;
    if (t <= m.t[0]) return table[0];
    for (int i = 1; i < m.n; ++i) {
        if (t <= m.t[i]) {
            float f = (t - m.t[i - 1]) / (m.t[i] - m.t[i - 1]);
            return table[i - 1] + f * (table[i] - table[i - 1]);
        }
    }
    return table[m.n - 1];
}

// ===========================================================================
void AttitudeEstimator::reset() {
    q_ = Quat{};
    bias_ = Vec3{};
    gyro_avg_ = Vec3{};
    acc_avg_ = Vec3{0, 0, kG0};
    still_time_ = 0;
    initialised_ = false;
}

bool AttitudeEstimator::pad_update(const Vec3& gyro, const Vec3& accel, float dt) {
    // Stillness test: |a| close to 1 g and small rotation rate.
    const float an = accel.norm();
    // Generous magnitude band (accelerometer offsets of 50+ mg must not block arming); handling is
    // caught by the gyro test.
    const bool still = std::fabs(an - kG0) < 0.12f * kG0 && gyro.norm() < deg2rad(6.0f);
    if (!initialised_) {
        gyro_avg_ = gyro;
        acc_avg_ = accel;
        initialised_ = true;
    }
    if (still) {
        // exponential averages with ~1 s time constant
        const float a = clampf(dt / 1.0f, 0.0f, 1.0f);
        gyro_avg_ = gyro_avg_ * (1.0f - a) + gyro * a;
        acc_avg_ = acc_avg_ * (1.0f - a) + accel * a;
        still_time_ += dt;
    } else {
        still_time_ = 0;
    }
    // keep a live attitude estimate on the pad as well
    q_ = Quat::from_two_vectors(acc_avg_, Vec3{0, 0, 1});
    return still;
}

void AttitudeEstimator::lock_pad_attitude() {
    bias_ = gyro_avg_;
    q_ = Quat::from_two_vectors(acc_avg_, Vec3{0, 0, 1});
}

void AttitudeEstimator::propagate(const Vec3& gyro, float dt) {
    Vec3 w = gyro - bias_;
    float wn = w.norm();
    if (wn > 1e-9f) {
        Quat dq = Quat::from_axis_angle(w, wn * dt);
        q_ = q_ * dq;
        q_.normalize();
    }
}

// ===========================================================================
void AltitudeKF::reset(float h0) {
    h_ = h0; v_ = 0;
    P00_ = 1.0f; P01_ = 0.0f; P11_ = 0.25f;
}

void AltitudeKF::predict(float a_up, float dt, float s) {
    h_ += v_ * dt + 0.5f * a_up * dt * dt;
    v_ += a_up * dt;
    // P = F P F' + G q G'  with F = [1 dt; 0 1], G = [dt^2/2; dt]
    const float q = s * s;
    const float g0 = 0.5f * dt * dt, g1 = dt;
    float p00 = P00_ + dt * (2.0f * P01_ + dt * P11_) + g0 * g0 * q;
    float p01 = P01_ + dt * P11_ + g0 * g1 * q;
    float p11 = P11_ + g1 * g1 * q;
    P00_ = p00; P01_ = p01; P11_ = p11;
}

void AltitudeKF::update_baro(float z, float sigma) {
    const float r = sigma * sigma;
    const float s = P00_ + r;
    const float k0 = P00_ / s, k1 = P01_ / s;
    const float y = z - h_;
    h_ += k0 * y;
    v_ += k1 * y;
    float p00 = (1 - k0) * P00_;
    float p01 = (1 - k0) * P01_;
    float p11 = P11_ - k1 * P01_;
    P00_ = p00; P01_ = p01; P11_ = p11;
}

// ===========================================================================
void TvcController::reset() {
    integ_ = Vec3{};
    rate_f_ = Vec3{};
    err_deg_ = 0;
}

void TvcController::update(const Quat& q, const Vec3& target_w, const Vec3& gyro_corr, float t_motor,
                           float t_active, const TvcGains& g, const MotorProfile& m, float dt,
                           float& gy_deg, float& gz_deg) {
    // Target direction expressed in the body frame
    const Vec3 tb = q.rotate_inv(target_w).normalized();
    // Rotation axis that takes body x onto the target: x × t = (0, -tz, ty)
    Vec3 e{0.0f, -tb.z, tb.y};
    const float s = e.norm();
    const float ang = std::atan2(s, tb.x);
    err_deg_ = rad2deg(ang);
    Vec3 err = (s > 1e-7f) ? e * (ang / s) : Vec3{};

    // low-pass the lateral body rates for the D term
    const float a = clampf(dt * 2.0f * 3.14159265f * g.rate_lpf_hz, 0.0f, 1.0f);
    rate_f_ = rate_f_ * (1.0f - a) + gyro_corr * a;

    // gain ramp while still on the launch rod (rotation physically prevented there)
    const float ramp = clampf(t_active / g.soft_start_s, 0.3f, 1.0f);
    const bool integrate = t_active > g.soft_start_s;

    Vec3 alpha;   // desired angular acceleration (body y,z)
    alpha.y = ramp * (g.kp * err.y + g.ki * integ_.y - g.kd * rate_f_.y);
    alpha.z = ramp * (g.kp * err.z + g.ki * integ_.z - g.kd * rate_f_.z);

    const float I = motor_interp(m, m.i_lat, t_motor);
    const float l = motor_interp(m, m.lever, t_motor);
    float T = motor_interp(m, m.thrust, t_motor);
    if (T < g.thrust_floor_n) T = g.thrust_floor_n;

    // torque -> gimbal angle (small-angle): M_y = -l T sin(dy), M_z = -l T sin(dz)
    const float k = I / (l * T);
    float dy = -alpha.y * k;
    float dz = -alpha.z * k;

    // compensate actuator latency against roll: rotate the command by -p*latency about x
    const float psi = -gyro_corr.x * g.roll_lead_s;
    const float c = std::cos(psi), sn = std::sin(psi);
    const float dy2 = dy * c - dz * sn;
    const float dz2 = dy * sn + dz * c;

    const float lim = deg2rad(g.max_gimbal_deg);
    const float mag = std::sqrt(dy2 * dy2 + dz2 * dz2);
    float scale = 1.0f;
    if (mag > lim) scale = lim / mag;   // preserve direction when saturating
    gy_deg = rad2deg(std::asin(clampf(dy2 * scale, -1.0f, 1.0f)));
    gz_deg = rad2deg(std::asin(clampf(dz2 * scale, -1.0f, 1.0f)));

    // conditional integration (anti-windup)
    if (integrate && scale > 0.999f) {
        integ_.y = clampf(integ_.y + err.y * dt, -g.integ_limit, g.integ_limit);
        integ_.z = clampf(integ_.z + err.z * dt, -g.integ_limit, g.integ_limit);
    }
}

// ===========================================================================
void FlightComputer::init(const Config& cfg) {
    cfg_ = cfg;
    att_.reset();
    kf_.reset(0.0f);
    tvc_.reset();
    stats_ = FlightStats{};
    state_ = FlightState::BOOT;
    t_prev_ = -1;
    deploy_ = false;
    baro_seen_ = false;
    apogee_count_ = 0;
    v_in_ = Vec3{};
}

void FlightComputer::enter(FlightState s, float t) {
    state_ = s;
    t_state_ = t;
}

float FlightComputer::pressure_to_alt(float pa) const {
    // hypsometric approximation relative to the pad pressure p0
    return 44330.0f * (1.0f - std::pow(pa / p0_, 0.190295f));
}

ActuatorCmd FlightComputer::step(const SensorFrame& in) {
    ActuatorCmd out;
    float dt = (t_prev_ < 0) ? 0.002f : (in.t - t_prev_);
    if (dt <= 0.0f || dt > 0.05f) dt = 0.002f;
    t_prev_ = in.t;
    const MotorProfile& m = *cfg_.motor;
    const auto& L = cfg_.logic;

    vbat_f_ += (in.vbat - vbat_f_) * clampf(dt / 0.5f, 0.0f, 1.0f);

    // ---- barometer --------------------------------------------------------
    if (in.baro_new && in.baro_ok) {
        if (!baro_seen_) { p_avg_ = in.baro_pa; baro_seen_ = true; }
        if (state_ == FlightState::BOOT || state_ == FlightState::CALIBRATING || state_ == FlightState::READY) {
            p_avg_ += (in.baro_pa - p_avg_) * 0.02f;   // slow pad average
        }
        baro_alt_ = pressure_to_alt(in.baro_pa);
        t_last_baro_ = in.t;
    }

    // ---- attitude / inertial ----------------------------------------------
    const bool on_pad = state_ == FlightState::BOOT || state_ == FlightState::CALIBRATING ||
                        state_ == FlightState::READY || state_ == FlightState::ERROR;
    if (on_pad) {
        att_.pad_update(in.gyro, in.accel, dt);
    } else {
        att_.propagate(in.gyro, dt);
    }
    const Quat& q = att_.q();
    // Lever-arm correction: the IMU sits ahead of the CG, so in a fast rotation it also feels
    // centripetal acceleration w x (w x r). Remove it so burnout detection / velocity stay valid.
    const Vec3 w_corr = in.gyro - att_.bias();
    const float arm = motor_interp(m, m.imu_arm, on_pad ? 0.0f : t_motor_);
    const Vec3 r_imu{arm, 0.0f, 0.0f};
    const Vec3 f_cg = in.accel - w_corr.cross(w_corr.cross(r_imu));
    const Vec3 f_w = q.rotate(f_cg);                  // specific force at the CG, world frame
    const Vec3 a_w = f_w - Vec3{0, 0, kG0};           // kinematic acceleration
    // tilt relative to the target direction
    {
        Vec3 xb_w = q.rotate(Vec3{1, 0, 0});
        float c = clampf(xb_w.dot(target_w_), -1.0f, 1.0f);
        tilt_deg_ = rad2deg(std::acos(c));
    }

    // ---- altitude filter ----------------------------------------------------
    if (state_ == FlightState::BOOST || state_ == FlightState::COAST) {
        kf_.predict(a_w.z, dt, cfg_.kf.accel_sigma);
        v_in_ += a_w * dt;
    } else if (state_ == FlightState::DESCENT || state_ == FlightState::LANDED) {
        // under the parachute the attitude is meaningless: run a baro-only random-walk filter
        kf_.predict(0.0f, dt, 3.0f);
    } else {
        kf_.predict(0.0f, dt, 0.05f);
    }
    if (in.baro_new && in.baro_ok && baro_seen_) {
        float sig = (state_ == FlightState::BOOST) ? cfg_.kf.baro_sigma_boost : cfg_.kf.baro_sigma;
        if (state_ == FlightState::DESCENT) sig = 0.8f;   // wake turbulence under the chute
        kf_.update_baro(baro_alt_, sig);
    }

    float t_since_launch = in.t - t_launch_;
    if (state_ == FlightState::BOOST || state_ == FlightState::COAST) t_motor_ = t_since_launch + m.detect_offset;

    // ---- state machine ------------------------------------------------------
    switch (state_) {
        case FlightState::BOOT:
        case FlightState::CALIBRATING:
            // SAFETY NET: a launch while not READY still gets a parachute. Attitude is not trusted,
            // so the TVC stays centred (the fins keep the rocket stable) but apogee detection runs.
            if (in.accel.norm() > 2.5f * kG0) {
                launch_timer_ += dt;
                if (launch_timer_ >= 0.05f) {
                    t_launch_ = in.t - launch_timer_;
                    stats_.t_launch = t_launch_;
                    stats_.unarmed_launch = true;
                    p0_ = p_avg_;
                    kf_.reset(0.0f);
                    v_in_ = Vec3{};
                    tvc_.reset();
                    enter(FlightState::BOOST, in.t);
                    break;
                }
            } else {
                launch_timer_ = 0;
            }
            if (state_ == FlightState::BOOT) {
                if (in.imu_ok && baro_seen_) enter(FlightState::CALIBRATING, in.t);
                if (in.t > 5.0f && (!in.imu_ok || !baro_seen_)) enter(FlightState::ERROR, in.t);
                break;
            }
            if (!in.imu_ok || !in.baro_ok) { enter(FlightState::ERROR, in.t); break; }
            if (att_.still_time() >= L.calib_still_s && vbat_f_ > L.min_vbat_v) {
                att_.lock_pad_attitude();
                g_meas_ = att_.accel_avg().norm();
                p0_ = p_avg_;
                kf_.reset(0.0f);
                target_w_ = L.hold_launch_attitude ? att_.q().rotate(Vec3{1, 0, 0}).normalized() : Vec3{0, 0, 1};
                enter(FlightState::READY, in.t);
            }
            break;
        case FlightState::READY: {
            // keep refining bias / attitude / pad pressure while the rocket sits still
            if (att_.still_time() > 1.0f) {
                att_.lock_pad_attitude();
                p0_ = p_avg_;
                target_w_ = L.hold_launch_attitude ? att_.q().rotate(Vec3{1, 0, 0}).normalized() : Vec3{0, 0, 1};
            }
            // launch detect on body-axis specific force
            if (in.accel.x > L.launch_accel_g * g_meas_) {
                launch_timer_ += dt;
                if (launch_timer_ >= L.launch_hold_s) {
                    t_launch_ = in.t - launch_timer_;
                    stats_.t_launch = t_launch_;
                    kf_.reset(0.0f);
                    v_in_ = Vec3{};
                    tvc_.reset();
                    enter(FlightState::BOOST, in.t);
                }
            } else {
                launch_timer_ = 0;
            }
            if (!in.imu_ok || !in.baro_ok) enter(FlightState::ERROR, in.t);
            break;
        }
        case FlightState::BOOST: {
            // abort: way off target, or tumbling. TVC is centred and early deployment is allowed.
            const float lat_rate = std::sqrt(w_corr.y * w_corr.y + w_corr.z * w_corr.z);
            tumble_timer_ = lat_rate > deg2rad(L.abort_rate_dps) ? tumble_timer_ + dt : 0.0f;
            if (tilt_deg_ > L.abort_tilt_deg || tumble_timer_ > L.abort_rate_hold_s) stats_.abort = true;
            stats_.max_tilt_deg = tilt_deg_ > stats_.max_tilt_deg ? tilt_deg_ : stats_.max_tilt_deg;
            if (stats_.abort && t_since_launch > 0.3f && v_in_.norm() < L.abort_deploy_speed_mps) {
                deploy_ = true;
                stats_.deploy_reason = 4;
                stats_.t_deploy = in.t;
                still_alt_ref_ = baro_alt_;
                still_timer_ = 0;
                t_last_still_ = in.t;
                enter(FlightState::DESCENT, in.t);
                break;
            }
            const bool low_thrust = f_cg.x < L.burnout_accel_g * kG0;
            if (t_since_launch > L.min_burn_s && low_thrust) burnout_timer_ += dt; else burnout_timer_ = 0;
            if (burnout_timer_ > 0.05f || t_motor_ > m.burn_time + 0.3f) {
                stats_.t_burnout = in.t;
                enter(FlightState::COAST, in.t);
            }
            break;
        }
        case FlightState::COAST: {
            const float since_bo = in.t - stats_.t_burnout;
            bool fire = false;
            if (since_bo > L.deploy_lockout_after_burnout_s) {
                if (in.baro_new) {
                    if (kf_.v() < 0.0f && kf_.h() > L.apogee_min_alt_m) apogee_count_++; else apogee_count_ = 0;
                }
                if (apogee_count_ >= L.apogee_confirm_samples) { fire = true; stats_.deploy_reason = 1; }
                if (!fire && kf_.v() < -L.descent_rate_deploy_mps) { fire = true; stats_.deploy_reason = 3; }
                if (!fire && stats_.abort && v_in_.norm() < L.abort_deploy_speed_mps) { fire = true; stats_.deploy_reason = 4; }
            }
            if (!fire && t_motor_ > m.apogee_time_nominal + L.deploy_backup_margin_s) { fire = true; stats_.deploy_reason = 2; }
            if (fire) {
                deploy_ = true;
                stats_.t_apogee = in.t;
                stats_.t_deploy = in.t;
                still_alt_ref_ = baro_alt_;
                still_timer_ = 0;
                t_last_still_ = in.t;
                enter(FlightState::DESCENT, in.t);
            }
            break;
        }
        case FlightState::DESCENT: {
            // landed when the raw barometric altitude stays inside a small band for a few seconds
            if (in.baro_new && in.baro_ok) {
                if (std::fabs(baro_alt_ - still_alt_ref_) < L.landed_alt_band_m) {
                    still_timer_ += in.t - t_last_still_;
                } else {
                    still_alt_ref_ = baro_alt_;
                    still_timer_ = 0;
                }
                t_last_still_ = in.t;
            }
            // independent landing check from the IMU alone (works with a failed barometer)
            // (only trusted when the barometer has stopped reporting: under a steady parachute the
            //  IMU alone can look "still")
            const bool baro_dead = (in.t - t_last_baro_) > 2.0f;
            const bool imu_still = std::fabs(in.accel.norm() - kG0) < 0.08f * kG0 && in.gyro.norm() < deg2rad(8.0f);
            imu_still_timer_ = (imu_still && baro_dead) ? imu_still_timer_ + dt : 0.0f;
            if ((still_timer_ > L.landed_still_s || imu_still_timer_ > 2.0f * L.landed_still_s) && in.t - t_state_ > 3.0f) {
                stats_.t_landed = in.t;
                enter(FlightState::LANDED, in.t);
            }
            break;
        }
        case FlightState::LANDED:
        case FlightState::ERROR:
            break;
    }

    if (kf_.h() > stats_.max_alt_m && !on_pad) stats_.max_alt_m = kf_.h();

    // ---- outputs ------------------------------------------------------------
    out.state = state_;
    out.deploy_release = deploy_;
    out.camera_power = (state_ != FlightState::BOOT && state_ != FlightState::ERROR);
    switch (state_) {
        case FlightState::BOOT:
        case FlightState::CALIBRATING: out.buzzer = Buzz::CALIBRATING; break;
        case FlightState::READY: out.buzzer = Buzz::CHIRP_READY; break;
        case FlightState::ERROR: out.buzzer = Buzz::FAST_ERROR; break;
        case FlightState::DESCENT: out.buzzer = Buzz::DESCENT_BEACON; break;
        case FlightState::LANDED: out.buzzer = Buzz::LANDED_REPORT; break;
        default: out.buzzer = Buzz::OFF; break;
    }
    if (state_ == FlightState::BOOST) {
        t_since_launch = in.t - t_launch_;
        t_motor_ = t_since_launch + m.detect_offset;
        float gy = 0, gz = 0;
        Vec3 w = in.gyro - att_.bias();
        tvc_.update(q, target_w_, w, t_motor_, t_since_launch, cfg_.tvc, m, dt, gy, gz);
        if (stats_.abort || stats_.unarmed_launch) { gy = 0.0f; gz = 0.0f; }   // fly as a finned rocket
        out.gimbal_y_deg = gy;
        out.gimbal_z_deg = gz;
        out.tvc_active = !(stats_.abort || stats_.unarmed_launch);
    }
    return out;
}

static uint16_t crc16_ccitt(const uint8_t* d, int n) {
    uint16_t crc = 0xFFFF;
    for (int i = 0; i < n; ++i) {
        crc ^= static_cast<uint16_t>(d[i]) << 8;
        for (int b = 0; b < 8; ++b) crc = (crc & 0x8000) ? static_cast<uint16_t>((crc << 1) ^ 0x1021) : static_cast<uint16_t>(crc << 1);
    }
    return crc;
}

void FlightComputer::fill_log(LogRecord& r, const SensorFrame& in, const ActuatorCmd& out) const {
    auto s16 = [](float v) -> int16_t { return static_cast<int16_t>(clampf(v, -32767.0f, 32767.0f)); };
    r.t_ms = static_cast<uint32_t>(in.t * 1000.0f);
    r.state = static_cast<uint8_t>(state_);
    r.flags = (out.tvc_active ? 1 : 0) | (out.deploy_release ? 2 : 0) | (in.baro_new ? 4 : 0) |
              (in.gps.valid ? 8 : 0) | (stats_.abort ? 16 : 0);
    r.gyro_cdps[0] = s16(rad2deg(in.gyro.x) * 100); r.gyro_cdps[1] = s16(rad2deg(in.gyro.y) * 100); r.gyro_cdps[2] = s16(rad2deg(in.gyro.z) * 100);
    r.accel_cmss[0] = s16(in.accel.x * 100); r.accel_cmss[1] = s16(in.accel.y * 100); r.accel_cmss[2] = s16(in.accel.z * 100);
    r.alt_m = kf_.h();
    r.vz_ms = kf_.v();
    r.baro_alt_m = baro_alt_;
    r.tilt_cdeg = s16(tilt_deg_ * 100);
    r.gimbal_y_cdeg = s16(out.gimbal_y_deg * 100);
    r.gimbal_z_cdeg = s16(out.gimbal_z_deg * 100);
    r.vbat_mv = s16(in.vbat * 1000);
    r.lat_deg = static_cast<float>(in.gps.lat_deg);
    r.lon_deg = static_cast<float>(in.gps.lon_deg);
    r.gps_alt_m = s16(in.gps.alt_m);
    r.sats = in.gps.sats;
    r.reserved = 0;
    r.q[0] = att_.q().x; r.q[1] = att_.q().y; r.q[2] = att_.q().z;
    r.crc16 = crc16_ccitt(reinterpret_cast<const uint8_t*>(&r), 62);
}

}  // namespace kestrel
