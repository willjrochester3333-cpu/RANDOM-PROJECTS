#!/usr/bin/env python3
"""Drag build-up and what-if apogees for the simulation report (section 3).

Every what-if is a passive flight (steering off, calm air, vertical 1 m rod) in the same 6-DOF simulator, so the
numbers compare designs, not control quality. Writes sim/results/whatif.md.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kestrel.dynamics import Simulation, SimConfig, FswOutput  # noqa: E402
from kestrel.rocket import Rocket, Motor, load_design  # noqa: E402

RES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")


class NullFsw:
    def reset(self, sim):
        pass

    def step(self, *a, **k):
        return FswOutput()


NOMINAL = load_design()["launch"]["nominal_motor"]      # TSP-F35


def passive(**over):
    cfg = dict(motor=NOMINAL, wind_speed=0.0, gust_sigma=0.0, tvc_enabled=False, tabs_enabled=False, t_pad=0.5,
               gyro_bias_dps=(0, 0, 0), thrust_misalign_deg=0.0, fin_cant_deg=0.0)
    cfg.update(over)
    ev = Simulation(SimConfig(**cfg), NullFsw()).run()
    return ev["apogee"], ev.get("rod_exit_speed", float("nan"))


def main():
    t0 = time.time()
    d = load_design()
    r = Rocket(d, Motor(NOMINAL))
    dry = r.dry_mass_props().mass
    # static margin at lift-off without the nose ballast (its mass removed at its own position)
    import json
    pos = json.load(open(os.path.join(os.path.dirname(RES), "..", "cad", "component_positions.json")))
    bal = next(c for c in d["components"] if c["name"].startswith("nose_ballast"))
    r_nb = Rocket(d, Motor(NOMINAL), extra_mass=[("no_ballast", -bal["mass_g"] / 1000.0,
                                                    pos[bal["cad_ref"]]["z_from_tip"] / 1000.0)])
    cn = r_nb.cn_alpha_components()
    xcp = sum(c[1] * c[2] for c in cn) / sum(c[1] for c in cn)
    nb_margin = (xcp - r_nb.mass_props(0.0).z_cg) / r_nb.D
    lines = ["# Drag build-up and what-if flights (`sim/whatif.py`)", ""]
    br = r.drag_breakdown(40.0, False)
    lines += [f"Drag build-up at 40 m/s, coasting (`Cd0` = {br['total']:.2f}, every term includes the 8 % allowance):", "",
              "| Term | Cd |", "|---|---|"]
    for k, v in sorted(((k, v) for k, v in br.items() if k != "total"), key=lambda kv: -kv[1]):
        if v > 0:
            lines.append(f"| {k} | {v:.3f} |")
    lines += ["", f"Dry mass with 25 g payload, no motor: {dry * 1000:.0f} g", "",
              f"| Change (passive, calm, 1 m rod) | {NOMINAL.split('-')[1]} apogee | rod-exit speed |", "|---|---|---|"]
    cases = [
        (f"**as designed** (rated {Motor(NOMINAL).total_impulse:.0f} Ns, 25 g payload)", {}),
        ("empty payload bay", dict(payload_g=0.0)),
        ("maximum 50 g payload", dict(payload_g=50.0)),
        (f"{NOMINAL.split('-')[1]} delivering its published curve ({Motor(NOMINAL, basis='curve').total_impulse:.0f} Ns)", dict(motor_basis="curve")),
        (f"{bal['mass_g']:.0f} g lighter (= no nose ballast; margin would fall to {nb_margin:+.2f} cal)",
         dict(mass_scale=(dry - bal["mass_g"] / 1000.0) / dry)),
        ("50 g lighter", dict(mass_scale=(dry - 0.050) / dry)),
        ("100 g lighter", dict(mass_scale=(dry - 0.100) / dry)),
        ("drag 20 % lower", dict(cd_scale=0.8)),
    ]
    for name, over in cases:
        ap, vr = passive(**over)
        lines.append(f"| {name} | {ap:.1f} m | {vr:.1f} m/s |")
        print(name, f"{ap:.1f}", flush=True)
    for m, use in (("TSP-E20", "the first two flights"), ("TSP-D20", "optional, not in the flight programme")):   # 24 mm, in the adapter sleeve
        ap, vr = passive(motor=m)
        lines.append(f"| {m.replace('-', ' ')} in the 24 mm adapter ({use}) | {ap:.1f} m | {vr:.1f} m/s |")
        print(m, f"{ap:.1f}", flush=True)
    lines += ["", f"({time.time() - t0:.0f} s)"]
    with open(os.path.join(RES, "whatif.md"), "w") as fh:
        fh.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
