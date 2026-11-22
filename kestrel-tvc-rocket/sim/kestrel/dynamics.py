"""6-DOF flight simulator for KESTREL-1 with thrust vector control.

World frame: ENU (x east, y north, z up), origin at the pad.
Body frame : +x along the rocket axis towards the nose, y/z lateral (right-handed).
Quaternion  : q = [w, x, y, z], rotates body vectors into the world frame.

The flight software is pluggable: anything with ``reset(cfg)`` and
``step(t, gyro, accel, baro_pa, baro_new, gps)`` returning an ``FswOutput`` works.
The real C++ flight core is driven through ``sil.py`` (software-in-the-loop).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict

import numpy as np

from .rocket import Rocket, Motor, load_design, G0

# ----------------------------------------------------------------------------
# small quaternion / rotation helpers
# ----------------------------------------------------------------------------

def q_mul(a, b):
    w1, x1, y1, z1 = a
    w2, x2, y2, z2 = b
    return np.array([
        w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
        w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
        w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
        w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2,
    ])


def q_to_R(q):
    w, x, y, z = q
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
        [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
        [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)],
    ])


def q_from_axis_angle(axis, angle):
    axis = np.asarray(axis, dtype=float)
    n = np.linalg.norm(axis)
    if n < 1e-12 or abs(angle) < 1e-12:
        return np.array([1.0, 0.0, 0.0, 0.0])
    axis = axis / n
    s = math.sin(angle / 2)
    return np.array([math.cos(angle / 2), axis[0] * s, axis[1] * s, axis[2] * s])


def q_between(u, v):
    """Shortest rotation taking unit vector u to unit vector v."""
    u = u / np.linalg.norm(u)
    v = v / np.linalg.norm(v)
    c = np.dot(u, v)
    if c > 1 - 1e-12:
        return np.array([1.0, 0, 0, 0])
    if c < -1 + 1e-12:
        perp = np.cross(u, [1, 0, 0]) if abs(u[0]) < 0.9 else np.cross(u, [0, 1, 0])
        return q_from_axis_angle(perp, math.pi)
    ax = np.cross(u, v)
    q = np.array([1 + c, ax[0], ax[1], ax[2]])
    return q / np.linalg.norm(q)


def tilt_deg(q):
    """Angle between body x axis and world vertical."""
    xb = q_to_R(q)[:, 0]
    return math.degrees(math.acos(max(-1.0, min(1.0, xb[2]))))


# ----------------------------------------------------------------------------
# environment
# ----------------------------------------------------------------------------

def isa(h_asl):
    T0, p0, L = 288.15, 101325.0, 0.0065
    T = T0 - L * h_asl
    p = p0 * (T / T0) ** 5.25588
    rho = p / (287.05 * T)
    mu = 1.458e-6 * T ** 1.5 / (T + 110.4)
    sos = math.sqrt(1.4 * 287.05 * T)
    return T, p, rho, mu, sos


@dataclass
class SimConfig:
    motor: str = "TSP-E20"
    seed: int = 1
    dt: float = 0.001
    t_pad: float = 4.0               # seconds of stationary pad data before ignition
    t_max: float = 120.0
    site_alt_asl: float = 100.0
    temp_offset_c: float = 0.0
    # wind
    wind_speed: float = 3.0          # m/s at 10 m AGL (mean)
    wind_toward_deg: float = 90.0    # azimuth the wind blows TOWARDS (0 = east, 90 = north)
    gust_sigma: float = 0.6          # m/s, per horizontal axis
    gust_tau: float = 1.5            # s
    # launcher
    rod_length: float = 1.0
    rod_tilt_deg: float = 0.0
    rod_tilt_az_deg: float = 0.0
    rod_friction: float = 0.25
    aft_lug_height: float = 0.06     # aft lug height above pad at rest (m)
    initial_roll_deg: float = 0.0
    # vehicle dispersions
    mass_scale: float = 1.0
    cg_shift: float = 0.0
    cd_scale: float = 1.0
    cna_scale: float = 1.0
    impulse_scale: float = 1.0
    burn_time_scale: float = 1.0
    thrust_misalign_deg: float = 0.0
    thrust_misalign_az_deg: float = 0.0
    fin_cant_deg: float = 0.0
    # TVC actuator
    tvc_enabled: bool = True
    servo_frame_hz: float = 50.0
    servo_rate_dps: float = 600.0     # servo horn slew limit (0.10 s / 60 deg)
    servo_tau: float = 0.012          # s, servo inner-loop lag
    servo_deadband_deg: float = 0.25
    linkage_ratio: float = 0.42       # gimbal deg per servo deg
    gimbal_backlash_deg: float = 0.15
    gimbal_limit_deg: float = 6.5
    servo_trim_err_deg: tuple = (0.0, 0.0)  # residual gimbal trim error after calibration
    servo_failure: str = ""           # "", "stuck_y", "stuck_z", "dead", "hardover_y" (y servo jams at +limit)
    servo_failure_t: float = 0.5      # s after ignition when a hard-over occurs
    baro_fail_after: float = 1e9      # s after ignition: barometer stops delivering data
    # sensors
    imu_rate_hz: float = 500.0
    gyro_noise_dps: float = 0.06
    gyro_bias_dps: tuple = (0.3, -0.2, 0.25)
    gyro_bias_drift_dps: float = 0.01
    accel_noise_mg: float = 1.5
    accel_bias_mg: tuple = (10.0, -8.0, 12.0)
    imu_misalign_deg: float = 0.3
    baro_rate_hz: float = 50.0
    baro_noise_pa: float = 0.5
    baro_port_cp: float = -0.02       # static-port pressure error coefficient (x dynamic pressure)
    gps_rate_hz: float = 5.0
    # recovery
    chute_diameter_m: float = 0.61
    chute_cd: float = 0.80
    deploy_latch_delay: float = 0.15  # servo travel to release the pins
    deploy_sep_time: float = 0.35     # spring separation + line stretch
    chute_fill_time: float = 0.6
    deploy_failure: bool = False
    body_cd_descent: float = 0.9      # broadside-ish tumbling body under chute
    # logging
    log_every: int = 5


@dataclass
class FswOutput:
    gimbal_y_deg: float = 0.0
    gimbal_z_deg: float = 0.0
    deploy: bool = False
    state: int = 0
    state_name: str = "IDLE"
    extra: dict = field(default_factory=dict)


class ServoAxis:
    def __init__(self, cfg: SimConfig, trim_err_deg: float, stuck: bool, hardover: bool = False):
        self.cfg = cfg
        self.theta = 0.0          # servo horn angle (deg)
        self.latched = 0.0        # command latched at the last PWM frame (servo deg)
        self.gimbal = 0.0         # gimbal angle after backlash (deg)
        self.trim = trim_err_deg
        self.stuck = stuck
        self.hardover = hardover
        self.t_next_frame = 0.0

    def update(self, t, dt, cmd_gimbal_deg):
        c = self.cfg
        if self.hardover and t >= c.servo_failure_t:
            self.gimbal = c.gimbal_limit_deg
            return self.gimbal
        if t >= self.t_next_frame:
            self.latched = cmd_gimbal_deg / c.linkage_ratio
            self.t_next_frame = t + 1.0 / c.servo_frame_hz
        if not self.stuck:
            err = self.latched - self.theta
            if abs(err) > c.servo_deadband_deg:
                rate = np.clip(err / c.servo_tau, -c.servo_rate_dps, c.servo_rate_dps)
                self.theta += rate * dt
        g_target = self.theta * c.linkage_ratio + self.trim
        # backlash: gimbal only moves once the linkage slack is taken up
        b = c.gimbal_backlash_deg / 2
        if g_target > self.gimbal + b:
            self.gimbal = g_target - b
        elif g_target < self.gimbal - b:
            self.gimbal = g_target + b
        self.gimbal = float(np.clip(self.gimbal, -c.gimbal_limit_deg, c.gimbal_limit_deg))
        return self.gimbal


class Simulation:
    def __init__(self, cfg: SimConfig, fsw, design: dict | None = None):
        self.cfg = cfg
        self.design = design or load_design()
        self.rng = np.random.default_rng(cfg.seed)
        self.motor = Motor(cfg.motor, cfg.impulse_scale, cfg.burn_time_scale)
        self.rocket = Rocket(self.design, self.motor, mass_scale=cfg.mass_scale, cg_shift=cfg.cg_shift)
        self.fsw = fsw
        self.z_imu = self.design["avbay"].get("imu_z", 445) / 1000.0   # IMU position (m from nose tip)

    # ------------------------------------------------------------------
    def wind_at(self, h, gust):
        c = self.cfg
        hh = max(h, 0.5)
        U = c.wind_speed * (hh / 10.0) ** (1.0 / 7.0)
        az = math.radians(c.wind_toward_deg)
        return np.array([U * math.cos(az) + gust[0], U * math.sin(az) + gust[1], 0.0])

    # ------------------------------------------------------------------
    def run(self):
        c = self.cfg
        rk = self.rocket
        rng = self.rng
        dt = c.dt
        # initial attitude: body x along the rod
        tilt = math.radians(c.rod_tilt_deg)
        taz = math.radians(c.rod_tilt_az_deg)
        rod_dir = np.array([math.sin(tilt) * math.cos(taz), math.sin(tilt) * math.sin(taz), math.cos(tilt)])
        q = q_between(np.array([1.0, 0, 0]), rod_dir)
        # roll about the body axis
        q = q_mul(q, q_from_axis_angle([1, 0, 0], math.radians(c.initial_roll_deg)))
        r = np.zeros(3)
        v = np.zeros(3)
        w = np.zeros(3)
        gust = np.zeros(2)
        # sensor imperfections
        gbias = np.radians(np.array(c.gyro_bias_dps, dtype=float))
        abias = np.array(c.accel_bias_mg, dtype=float) * 1e-3 * G0
        mis = q_from_axis_angle(rng.normal(size=3), math.radians(c.imu_misalign_deg))
        R_mis = q_to_R(mis)
        # static thrust misalignment (body frame direction)
        ma = math.radians(c.thrust_misalign_deg)
        maz = math.radians(c.thrust_misalign_az_deg)
        mis_dir = np.array([math.cos(ma), math.sin(ma) * math.cos(maz), math.sin(ma) * math.sin(maz)])
        # actuators
        sy = ServoAxis(c, c.servo_trim_err_deg[0], c.servo_failure in ("stuck_y", "dead"), c.servo_failure == "hardover_y")
        sz = ServoAxis(c, c.servo_trim_err_deg[1], c.servo_failure in ("stuck_z", "dead"))
        self.fsw.reset(self)
        out = FswOutput()

        T_K, p_site, rho_site, _, _ = isa(c.site_alt_asl)
        log = []
        ev = dict(liftoff=None, rod_exit=None, rod_exit_speed=None, burnout=None, apogee_t=None, apogee=0.0,
                  deploy_cmd_t=None, deploy_alt=None, deploy_speed=None, chute_full_t=None, landing_t=None,
                  landing_speed=None, landing_pos=None, max_speed=0.0, max_accel_g=0.0, max_tilt_burn=0.0,
                  tilt_burnout=None, max_gimbal=0.0, max_q=0.0, max_aoa_deg=0.0, max_rate_dps=0.0,
                  max_opening_g=0.0, fsw_apogee_err=None, deploy_vz=None)
        on_rod = True
        launched = False
        s_rod = 0.0
        s_exit = c.rod_length - c.aft_lug_height
        imu_period = 1.0 / c.imu_rate_hz
        baro_period = 1.0 / c.baro_rate_hz
        gps_period = 1.0 / c.gps_rate_hz
        t_next_imu = -c.t_pad
        t_next_baro = -c.t_pad
        t_next_gps = -c.t_pad
        deploy_cmd_t = None
        landed = False
        a_world_prev = np.zeros(3)
        w_dot = np.zeros(3)
        n = 0
        t = -c.t_pad
        apogee_reached = False
        mdot_prev_m = None
        fsw_apogee_logged = False
        gimbal = np.zeros(2)
        last_fsw_state = 0

        while t < c.t_max and not landed:
            tm = max(t, 0.0)
            T_thrust = self.motor.thrust(t) if t >= 0 else 0.0
            motor_on = T_thrust > 0
            mp = rk.mass_props(tm)
            m = mp.mass
            h = r[2]
            Tk, p_amb, rho, mu, sos = isa(c.site_alt_asl + h)
            # gusts (Gauss-Markov)
            if t > 0:
                gust += (-gust / c.gust_tau) * dt + c.gust_sigma * math.sqrt(2 * dt / c.gust_tau) * rng.normal(size=2)
            wind = self.wind_at(h, gust) if (h > 0.05 or not on_rod) else np.zeros(3)
            R = q_to_R(q)
            # ------------------------------------------------------------------
            # deployment state
            chute_area_frac = 0.0
            separated = False
            if deploy_cmd_t is not None and not c.deploy_failure:
                td = t - deploy_cmd_t - c.deploy_latch_delay
                if td > 0:
                    separated = True
                    tf = td - c.deploy_sep_time
                    if tf > 0:
                        chute_area_frac = min(1.0, tf / c.chute_fill_time) ** 2
                        if chute_area_frac >= 1.0 and ev["chute_full_t"] is None:
                            ev["chute_full_t"] = t
            # ------------------------------------------------------------------
            v_air = v - wind
            vb = R.T @ v_air
            V = float(np.linalg.norm(v_air))
            qdyn = 0.5 * rho * V * V
            ev["max_q"] = max(ev["max_q"], qdyn)
            F_world = np.array([0.0, 0.0, -m * G0])
            M_body = np.zeros(3)
            l_piv = rk.z_pivot - mp.z_cg   # pivot is aft of CG by this much (m)
            # thrust (body)
            if T_thrust > 0:
                gy, gz = math.radians(gimbal[0]), math.radians(gimbal[1])
                d = np.array([math.cos(gy) * math.cos(gz), math.sin(gz), -math.sin(gy) * math.cos(gz)])
                # add static misalignment as a small rotation of the thrust line
                d = d + (mis_dir - np.array([1.0, 0, 0]))
                d /= np.linalg.norm(d)
                Fb = T_thrust * d
                F_world += R @ Fb
                r_p = np.array([-l_piv, 0.0, 0.0])
                M_body += np.cross(r_p, Fb)
                # jet damping
                mdot = self.motor.m_prop * T_thrust / self.motor.total_impulse
                l_noz = rk.z_motor_aft - mp.z_cg
                M_body[1:] += -mdot * l_noz ** 2 * w[1:]
            # aerodynamics (only while the body flies as a rocket)
            aoa = 0.0
            if V > 0.5 and not separated:
                u = vb[0]
                lat = vb[1:]
                vlat = float(np.linalg.norm(lat))
                aoa = math.atan2(vlat, max(u, 1e-6)) if u > 0 else math.pi / 2
                cd = rk.cd0(V, motor_on, rho, mu, sos, c.cd_scale)
                cna, xcp = rk.cn_alpha_cp(V / sos, aoa)
                cna *= c.cna_scale
                CN = cna * math.sin(aoa) * math.cos(aoa) if aoa < math.pi / 2 else cna * 0.5
                Fa = np.zeros(3)
                Fa[0] = -qdyn * rk.A_ref * cd * (1.0 if u >= 0 else -1.0)
                if vlat > 1e-6:
                    Fa[1:] = -qdyn * rk.A_ref * CN * lat / vlat
                F_world += R @ Fa
                r_cp = np.array([mp.z_cg - xcp, 0.0, 0.0])
                M_body += np.cross(r_cp, Fa)
                # pitch/yaw damping
                Cdamp = rk.pitch_damping_coeff(mp)
                M_body[1:] += -Cdamp * rho * V * w[1:]
                # roll: fin cant forcing and damping
                cr, ct, s, sweep, lm = rk.fin_geometry()
                cna1 = rk.cn_alpha_components()[1][1] / rk.fin_n
                r_mac = rk.R + s / 3.0
                M_body[0] += qdyn * rk.A_ref * cna1 * rk.fin_n * math.radians(c.fin_cant_deg) * r_mac
                M_body[0] += -0.5 * rho * V * rk.A_ref * cna1 * rk.fin_n * r_mac ** 2 * w[0]
                if V > 10.0 and launched and not on_rod:
                    ev["max_aoa_deg"] = max(ev["max_aoa_deg"], math.degrees(aoa))
            elif separated:
                # descent: chute + tumbling body, treated as point drag at the CG
                A_chute = math.pi * (c.chute_diameter_m / 2) ** 2
                CdA = c.chute_cd * A_chute * chute_area_frac + c.body_cd_descent * rk.D * rk.length * 0.3
                if V > 1e-6:
                    F_world += -0.5 * rho * V * CdA * v_air
                w *= 0.98   # tumbling body: rates decay (not modelled further)
            # ------------------------------------------------------------------
            # translational dynamics
            if on_rod:
                if t >= 0 and T_thrust > 0:
                    a_along = np.dot(F_world, rod_dir) / m
                    # rod friction from lateral loads
                    F_lat = F_world - np.dot(F_world, rod_dir) * rod_dir
                    a_along -= c.rod_friction * np.linalg.norm(F_lat) / m * (1 if np.dot(v, rod_dir) > 0 or a_along > 0 else 0)
                    if a_along < 0 and np.dot(v, rod_dir) <= 0:
                        a_along = 0.0
                    if not launched and a_along > 0:
                        launched = True
                        ev["liftoff"] = t
                    a = a_along * rod_dir
                    w = np.zeros(3)
                    w_dot = np.zeros(3)
                else:
                    a = np.zeros(3)
            else:
                a = F_world / m
                # rotational dynamics (diagonal inertia, Iyy = Izz)
                I = np.array([mp.Ixx, mp.Iyy, mp.Iyy])
                w_dot = (M_body - np.cross(w, I * w)) / I
            # ------------------------------------------------------------------
            # sensors + flight software
            if t >= t_next_imu - 1e-9:
                t_next_imu = max(t_next_imu + imu_period, t)
                # specific force at the IMU (body frame), including lever-arm terms
                a_body = R.T @ (a + np.array([0, 0, G0]))
                if on_rod and not launched:
                    a_body = R.T @ np.array([0, 0, G0])  # sitting on the pad, gravity reaction
                r_imu = np.array([mp.z_cg - self.z_imu, 0.0, 0.0])
                f_imu = a_body + np.cross(w_dot, r_imu) + np.cross(w, np.cross(w, r_imu))
                gyro_true = w.copy()
                gbias = gbias + np.radians(c.gyro_bias_drift_dps) * math.sqrt(imu_period) * rng.normal(size=3) * 0.1
                gyro_m = R_mis @ gyro_true + gbias + np.radians(c.gyro_noise_dps) * rng.normal(size=3)
                acc_m = R_mis @ f_imu + abias + c.accel_noise_mg * 1e-3 * G0 * rng.normal(size=3)
                acc_m = np.clip(acc_m, -16 * G0, 16 * G0)
                gyro_m = np.clip(gyro_m, -math.radians(2000), math.radians(2000))
                baro_new = False
                baro_pa = float("nan")
                if t >= t_next_baro - 1e-9 and t < c.baro_fail_after:
                    t_next_baro += baro_period
                    baro_pa = p_amb + c.baro_port_cp * qdyn * (0 if separated else 1) + c.baro_noise_pa * rng.normal()
                    if separated:
                        baro_pa += 3.0 * rng.normal()   # turbulent wake noise under the chute
                    baro_new = True
                gps = None
                if t >= t_next_gps - 1e-9:
                    t_next_gps += gps_period
                    gps = dict(x=r[0] + 1.5 * rng.normal(), y=r[1] + 1.5 * rng.normal(), z=r[2] + 3.0 * rng.normal(),
                               fix=True)
                out = self.fsw.step(t, gyro_m, acc_m, baro_pa, baro_new, gps)
                if out.deploy and deploy_cmd_t is None and t > 0:
                    deploy_cmd_t = t
                    ev["deploy_cmd_t"] = t
                    ev["deploy_alt"] = r[2]
                    ev["deploy_speed"] = float(np.linalg.norm(v))
                    ev["deploy_vz"] = float(v[2])
                last_fsw_state = out.state
            # actuators (run every physics step)
            if c.tvc_enabled:
                gimbal[0] = sy.update(t, dt, out.gimbal_y_deg)
                gimbal[1] = sz.update(t, dt, out.gimbal_z_deg)
            else:
                gimbal[:] = 0.0
            # ------------------------------------------------------------------
            # integrate: semi-implicit Euler at 1 kHz (step-size convergence is checked in tests/test_sim.py)
            v = v + a * dt
            r = r + v * dt
            if not on_rod:
                w = w + w_dot * dt
                wn = np.linalg.norm(w)
                if wn > 1e-12:
                    dq = q_from_axis_angle(w / wn, wn * dt)
                    q = q_mul(q, dq)
                    q /= np.linalg.norm(q)
            if on_rod and launched:
                s_rod = np.dot(r, rod_dir)
                if s_rod >= s_exit:
                    on_rod = False
                    ev["rod_exit"] = t
                    ev["rod_exit_speed"] = float(np.linalg.norm(v))
            # events / bookkeeping
            if launched:
                spd = float(np.linalg.norm(v))
                ev["max_speed"] = max(ev["max_speed"], spd)
                ev["max_accel_g"] = max(ev["max_accel_g"], float(np.linalg.norm(a)) / G0)
                ev["max_rate_dps"] = max(ev["max_rate_dps"], math.degrees(float(np.linalg.norm(w[1:]))))
                if separated:
                    ev["max_opening_g"] = max(ev["max_opening_g"], float(np.linalg.norm(a + np.array([0, 0, G0]))) / G0)
                if motor_on:
                    ev["max_tilt_burn"] = max(ev["max_tilt_burn"], tilt_deg(q))
                    ev["max_gimbal"] = max(ev["max_gimbal"], abs(gimbal[0]), abs(gimbal[1]))
                if ev["burnout"] is None and t >= self.motor.burn_time:
                    ev["burnout"] = t
                    ev["tilt_burnout"] = tilt_deg(q)
                    ev["burnout_speed"] = spd
                    ev["burnout_alt"] = r[2]
                if not apogee_reached and t > 0.5 and v[2] < 0:
                    apogee_reached = True
                    ev["apogee_t"] = t
                    ev["apogee"] = float(r[2])
                    ev["apogee_xy"] = (float(r[0]), float(r[1]))
                if r[2] < 0 and t > 1.0 and launched:
                    landed = True
                    ev["landing_t"] = t
                    ev["landing_speed"] = float(np.linalg.norm(v))
                    ev["landing_vz"] = float(-v[2])
                    ev["landing_hspeed"] = float(np.hypot(v[0], v[1]))
                    ev["landing_pos"] = (float(r[0]), float(r[1]))
            if n % c.log_every == 0:
                log.append((t, r[0], r[1], r[2], v[0], v[1], v[2], tilt_deg(q), gimbal[0], gimbal[1],
                            math.degrees(w[0]), math.degrees(w[1]), math.degrees(w[2]), T_thrust, m, aoa, last_fsw_state,
                            chute_area_frac, out.extra.get("alt_est", float("nan")), out.extra.get("vz_est", float("nan"))))
            n += 1
            t += dt
            if ev["chute_full_t"] is not None and t > ev["chute_full_t"] + 1.0:
                dt = 0.01   # under a fully open chute: coarser step (FSW still sees every step)
        # ---- lie on the ground for a few seconds so the flight software can declare LANDED
        if landed:
            p_gnd = isa(c.site_alt_asl)[1]
            g_body = np.array([0.0, G0, 0.0])        # rocket lying on its side
            t_end = t + 10.0
            while t < t_end:
                if t >= t_next_imu - 1e-9:
                    t_next_imu = max(t_next_imu + 0.002, t)
                    bnew = t >= t_next_baro - 1e-9 and t < c.baro_fail_after
                    if bnew:
                        t_next_baro += baro_period
                    out = self.fsw.step(t, gbias + np.radians(c.gyro_noise_dps) * rng.normal(size=3),
                                        g_body + abias + c.accel_noise_mg * 1e-3 * G0 * rng.normal(size=3),
                                        p_gnd + c.baro_noise_pa * rng.normal() if bnew else float("nan"), bnew, None)
                    last_fsw_state = out.state
                t += 0.002
            ev["landed_detect_state"] = last_fsw_state
        cols = ["t", "x", "y", "z", "vx", "vy", "vz", "tilt", "gimbal_y", "gimbal_z", "p_dps", "q_dps", "r_dps",
                "thrust", "mass", "aoa", "fsw_state", "chute_frac", "alt_est", "vz_est"]
        self.log = {k: np.array([row[i] for row in log]) for i, k in enumerate(cols)}
        if ev["deploy_cmd_t"] is not None and ev["apogee_t"] is not None:
            ev["deploy_minus_apogee_s"] = ev["deploy_cmd_t"] - ev["apogee_t"]
        if ev["landing_pos"] is not None:
            ev["landing_dist"] = float(math.hypot(*ev["landing_pos"]))
        ev["final_state"] = last_fsw_state
        self.events = ev
        return ev
