#!/usr/bin/env python3
"""Cross-check the KESTREL 6-DOF simulator against RocketPy (independent open-source 6-DOF).

Both simulators fly the same airframe *passively* (TVC off, no wind, vertical 1 m rod) with
the same mass properties, thrust curve and drag curve. They should agree on stability margin,
rod-exit speed, max speed, apogee and apogee time to within a few percent.
"""
import json
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kestrel.dynamics import Simulation, SimConfig, FswOutput  # noqa: E402
from kestrel.rocket import Rocket, Motor, load_design  # noqa: E402

import rocketpy  # noqa: E402
from rocketpy import Environment, SolidMotor, Flight  # noqa: E402
from rocketpy import Rocket as RPRocket  # noqa: E402


class NullFsw:
    def reset(self, sim):
        pass

    def step(self, *a, **k):
        return FswOutput()


def kestrel_run(motor):
    cfg = SimConfig(motor=motor, wind_speed=0.0, gust_sigma=0.0, tvc_enabled=False, t_pad=0.5,
                    gyro_bias_dps=(0, 0, 0), thrust_misalign_deg=0.0, fin_cant_deg=0.0, chute_diameter_m=0.01)
    sim = Simulation(cfg, NullFsw())
    ev = sim.run()
    return sim, ev


def rocketpy_run(motor_name):
    d = load_design()
    mot = Motor(motor_name)
    rk = Rocket(d, mot)
    dry = rk.dry_mass_props()
    env = Environment(latitude=52.0, longitude=-1.0, elevation=100)
    env.set_atmospheric_model(type="standard_atmosphere")
    r_grain = mot.diameter / 2 * 0.9
    # Grain sized so its mass equals the motor's propellant mass (black-powder end burner approximated as one grain)
    h_grain = mot.length * 0.6
    vol = math.pi * (r_grain ** 2 - 0.002 ** 2) * h_grain
    rp_motor = SolidMotor(
        thrust_source=np.column_stack([mot.t, mot.F]).tolist(),
        dry_mass=mot.m_case,
        dry_inertia=(mot.m_case * mot.length ** 2 / 12, mot.m_case * mot.length ** 2 / 12, mot.m_case * (mot.diameter / 2) ** 2 / 2),
        nozzle_radius=0.005,
        grain_number=1,
        grain_density=mot.m_prop / vol,
        grain_outer_radius=r_grain,
        grain_initial_inner_radius=0.002,
        grain_initial_height=h_grain,
        grain_separation=0.0,
        grains_center_of_mass_position=mot.length / 2,
        center_of_dry_mass_position=mot.length / 2,
        nozzle_position=0.0,
        burn_time=mot.burn_time,
        throat_radius=0.003,
        coordinate_system_orientation="nozzle_to_combustion_chamber",
    )
    machs = np.linspace(0.01, 0.4, 40)
    cd_off = [[m_, rk.cd0(m_ * 340.3, False)] for m_ in machs]
    cd_on = [[m_, rk.cd0(m_ * 340.3, True)] for m_ in machs]
    rocket = RPRocket(
        radius=rk.R,
        mass=dry.mass,
        inertia=(dry.Iyy, dry.Iyy, dry.Ixx),
        power_off_drag=cd_off,
        power_on_drag=cd_on,
        center_of_mass_without_motor=dry.z_cg,
        coordinate_system_orientation="nose_to_tail",
    )
    rocket.add_motor(rp_motor, position=rk.z_motor_aft)
    rocket.add_nose(length=rk.L_nose, kind="tangent", position=0.0)
    rocket.add_trapezoidal_fins(n=rk.fin_n, root_chord=rk.fin_cr, tip_chord=rk.fin_ct, span=rk.fin_s,
                                position=rk.fin_z_le, sweep_length=rk.fin_sweep)
    fl = Flight(rocket=rocket, environment=env, rail_length=1.0 - 0.06, inclination=90, heading=0,
                terminate_on_apogee=True, max_time_step=0.01)
    return rocket, fl


def main():
    rows = []
    out = {}
    for motor in ["TSP-E12", "TSP-E20", "TSP-D20"]:
        sim, ev = kestrel_run(motor)
        rocket, fl = rocketpy_run(motor)
        rk = sim.rocket
        sm_k = rk.stability_margin_cal(0.0)
        sm_r = float(rocket.static_margin(0))
        rp = dict(apogee=fl.apogee - fl.env.elevation, apogee_t=fl.apogee_time, max_speed=fl.max_speed,
                  rail_exit_speed=fl.out_of_rail_velocity, static_margin=sm_r)
        kk = dict(apogee=ev["apogee"], apogee_t=ev["apogee_t"], max_speed=ev["max_speed"],
                  rail_exit_speed=ev["rod_exit_speed"], static_margin=sm_k)
        out[motor] = dict(kestrel=kk, rocketpy=rp)
        for k in kk:
            a, b = kk[k], rp[k]
            rows.append(f"| {motor} | {k} | {a:.2f} | {b:.2f} | {100*(a-b)/b:+.1f}% |")
    table = "| motor | quantity | KESTREL sim | RocketPy | diff |\n|---|---|---|---|---|\n" + "\n".join(rows)
    print(table)
    res = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
    with open(os.path.join(res, "rocketpy_validation.json"), "w") as fh:
        json.dump(out, fh, indent=1)
    with open(os.path.join(res, "rocketpy_validation.md"), "w") as fh:
        fh.write("# KESTREL sim vs RocketPy " + str(getattr(rocketpy, "__version__", "1.x")) + " (passive flight, no wind)\n\n" + table + "\n")


if __name__ == "__main__":
    main()
