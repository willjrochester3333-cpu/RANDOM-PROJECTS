"""KESTREL-2 rocket model: geometry, mass properties, Barrowman aerodynamics, control tabs and drag build-up.

Everything is driven by the project-level ``design.json`` so that the simulator,
the Blender CAD generator and the firmware configuration never disagree.

Conventions
-----------
* ``z`` positions are measured from the nose tip, positive towards the tail (metres
  inside this module, the JSON is in millimetres).
* Body frame for the dynamics (see dynamics.py): +x along the rocket axis towards
  the nose, y/z lateral.
"""
from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
DESIGN_PATH = os.path.join(ROOT, "design.json")

PLA_DENSITY = 1240.0  # kg/m^3
G0 = 9.80665


def load_design(path: str = DESIGN_PATH) -> dict:
    with open(path) as fh:
        return json.load(fh)


def load_motors() -> dict:
    with open(os.path.join(HERE, "motors.json")) as fh:
        return json.load(fh)


# ----------------------------------------------------------------------------
# Motor
# ----------------------------------------------------------------------------
MOTOR_BASIS = os.environ.get("KESTREL_MOTOR_BASIS", "rated")


class Motor:
    """Solid motor with tabulated thrust; propellant mass burns in proportion to impulse.

    basis="rated" (default) stretches/scales the published thrust-curve file so its total impulse and burn time
    equal the manufacturer's rating in motors.json (TSP's curve files integrate to more than the rating, e.g.
    E20: 40.1 Ns / 2.2 s in the file against 36 Ns / 2.0 s rated). basis="curve" uses the file as it is."""

    def __init__(self, name: str, scale_impulse: float = 1.0, scale_time: float = 1.0, basis: str | None = None):
        data = load_motors()[name]
        self.name = name
        self.data = data
        pts = np.array(data["thrust_curve"], dtype=float)
        if pts[0, 0] > 0.0:
            pts = np.vstack([[0.0, 0.0], pts])
        self.basis = basis or MOTOR_BASIS
        if self.basis == "rated" and data.get("total_impulse_Ns") and data.get("burn_time_s"):
            i_file = float(np.sum(0.5 * (pts[1:, 1] + pts[:-1, 1]) * np.diff(pts[:, 0])))
            k_t = data["burn_time_s"] / pts[-1, 0]
            pts = np.column_stack([pts[:, 0] * k_t, pts[:, 1] * data["total_impulse_Ns"] / (i_file * k_t)])
        self.t = pts[:, 0] * scale_time
        # scale thrust so that total impulse scales by scale_impulse
        self.F = pts[:, 1] * scale_impulse / scale_time
        cum = np.concatenate([[0.0], np.cumsum(0.5 * (self.F[1:] + self.F[:-1]) * np.diff(self.t))])
        self.cum_impulse = cum
        self.total_impulse = float(cum[-1])
        self.burn_time = float(self.t[-1])
        self.m_total = data["total_mass_g"] / 1000.0
        self.m_prop = data["propellant_mass_g"] / 1000.0
        self.m_case = self.m_total - self.m_prop
        self.length = data["length_mm"] / 1000.0
        self.diameter = data["diameter_mm"] / 1000.0

    def thrust(self, t: float) -> float:
        if t <= 0.0 or t >= self.burn_time:
            return 0.0
        return float(np.interp(t, self.t, self.F))

    def prop_mass(self, t: float) -> float:
        if t <= 0.0:
            return self.m_prop
        if t >= self.burn_time:
            return 0.0
        frac = float(np.interp(t, self.t, self.cum_impulse)) / self.total_impulse
        return self.m_prop * (1.0 - frac)

    def average_thrust(self) -> float:
        return self.total_impulse / self.burn_time


# ----------------------------------------------------------------------------
# Rocket geometry / mass / aero
# ----------------------------------------------------------------------------
@dataclass
class MassProps:
    mass: float
    z_cg: float            # m from nose tip
    Ixx: float             # roll inertia, kg m^2
    Iyy: float             # pitch/yaw inertia about CG, kg m^2


@dataclass
class Rocket:
    design: dict
    motor: Motor
    extra_mass: list = field(default_factory=list)   # [(name, kg, z_m)] for Monte-Carlo / payload tweaks
    mass_scale: float = 1.0
    cg_shift: float = 0.0                              # m, +aft
    payload_kg: float | None = None                    # None = nominal payload from design.json

    def __post_init__(self):
        d = self.design
        af = d["airframe"]
        self.D = af["od"] / 1000.0
        self.R = self.D / 2.0
        self.A_ref = math.pi * self.R ** 2
        self.L_nose = d["nose"]["length"] / 1000.0
        self.L_upper = af["upper_tube_length"] / 1000.0
        self.L_lower = af["lower_tube_length"] / 1000.0
        self.L_band = d["avbay"].get("band", 0) / 1000.0
        self.L_sleeve = d["nose"].get("sleeve_length", 0) / 1000.0      # body-diameter sleeve at the nose base
        self.L_body = self.L_upper + self.L_lower + self.L_band + self.L_sleeve
        self.z_tail = self.L_nose + self.L_body
        self.length = self.z_tail + d["tvc"]["nozzle_protrusion"] / 1000.0
        f = d["fins"]
        self.fin_n = f["count"]
        self.fin_cr = f["root_chord"] / 1000.0
        self.fin_ct = f["tip_chord"] / 1000.0
        self.fin_s = f["span"] / 1000.0
        self.fin_sweep = f["sweep"] / 1000.0
        self.fin_t = f["thickness"] / 1000.0
        self.fin_z_le = self.z_tail - f["trailing_edge_from_tail"] / 1000.0 - self.fin_cr
        # TVC pivot and motor placement
        tvc = d["tvc"]
        self.z_pivot = self.z_tail - tvc["pivot_from_tail"] / 1000.0
        self.z_motor_aft = self.z_tail + tvc["nozzle_protrusion"] / 1000.0
        self.z_motor_cg = self.z_motor_aft - self.motor.length / 2.0
        self._build_components()

    # ---- mass model -------------------------------------------------------
    def _tube_mass(self, length: float) -> float:
        af = self.design["airframe"]
        ro, ri = af["od"] / 2000.0, af["id"] / 2000.0
        return math.pi * (ro ** 2 - ri ** 2) * length * af["tube_density_kg_m3"]

    def fin_can_mass(self) -> float:
        f = self.design["fins"]
        fin_area = 0.5 * (self.fin_cr + self.fin_ct) * self.fin_s
        fins = self.fin_n * fin_area * self.fin_t * PLA_DENSITY * 0.85  # 2 perimeters + light infill
        can = math.pi * (self.D + f["can_wall"] / 1000.0) * f["can_length"] / 1000.0 * f["can_wall"] / 1000.0 * PLA_DENSITY
        return fins + can

    def _build_components(self):
        comps = []
        pos_path = os.path.join(ROOT, "cad", "component_positions.json")
        pos = json.load(open(pos_path)) if os.path.exists(pos_path) else {}
        for c in self.design["components"]:
            if c.get("auto") == "upper_tube":
                z0 = self.L_nose + self.L_sleeve
                comps.append(("upper_tube", self._tube_mass(self.L_upper), z0 + self.L_upper / 2, self.L_upper, self.R))
            elif c.get("auto") == "lower_tube":
                z0 = self.L_nose + self.L_sleeve + self.L_upper + self.L_band
                comps.append(("lower_tube", self._tube_mass(self.L_lower), z0 + self.L_lower / 2, self.L_lower, self.R))
            elif "cad_ref" in c:
                refs = c["cad_ref"] if isinstance(c["cad_ref"], list) else [c["cad_ref"]]
                for ref in refs:
                    q = pos[ref]
                    comps.append((ref, c["mass_g"] / 1000.0, q["z_from_tip"] / 1000.0, q["length"] / 1000.0,
                                  q["radius"] / 1000.0))
            elif "z_above_tail" in c:
                comps.append((c["name"], c["mass_g"] / 1000.0, self.z_tail - c["z_above_tail"] / 1000.0, c["length"] / 1000.0,
                              c["radius"] / 1000.0))
            elif c.get("auto") == "fin_can":
                f = self.design["fins"]
                comps.append(("fin_can", self.fin_can_mass(), self.z_tail - f["can_length"] / 2000.0, f["can_length"] / 1000.0, self.R + self.fin_s / 2))
            elif c.get("auto") == "cad":
                mp_path = os.path.join(ROOT, "cad", "mass_properties.json")
                for q in json.load(open(mp_path)):
                    comps.append(("cad:" + q["name"], q["mass_g"] / 1000.0, q["z"] / 1000.0, q["length"] / 1000.0, q["radius"] / 1000.0))
            else:
                comps.append((c["name"], c["mass_g"] / 1000.0, c["z"] / 1000.0, c["length"] / 1000.0, c["radius"] / 1000.0))
        pl = self.design["payload"]["nominal_mass_g"] / 1000.0 if self.payload_kg is None else self.payload_kg
        if pl > 0:
            q = pos.get("payload_example_25g", {"z_from_tip": (self.L_nose + self.L_sleeve + self.L_upper - 0.115) * 1000,
                                                "length": 30.0, "radius": 15.0})
            comps.append(("payload", pl, q["z_from_tip"] / 1000.0, q["length"] / 1000.0, q["radius"] / 1000.0))
        for name, m, z in self.extra_mass:
            comps.append((name, m, z, 0.0, 0.0))
        self.components = comps

    def dry_mass_props(self) -> MassProps:
        return self._mass_props(include_motor=False)

    def _mass_props(self, include_motor=True, t=0.0) -> MassProps:
        m_list, z_list, k2_lat, k2_roll = [], [], [], []
        for name, m, z, L, r in self.components:
            m = m * self.mass_scale
            m_list.append(m)
            z_list.append(z)
            k2_lat.append(L ** 2 / 12.0 + r ** 2 / 4.0)
            # CAD parts and tubes are shells/plates: their radius is a radius of gyration; small parts are solid
            k2_roll.append(r ** 2 if (name.startswith("cad:") or name.endswith("_tube")) else r ** 2 / 2.0)
        if include_motor:
            mm = self.motor.m_case + self.motor.prop_mass(t)
            m_list.append(mm)
            z_list.append(self.z_motor_cg)
            k2_lat.append(self.motor.length ** 2 / 12.0 + (self.motor.diameter / 2) ** 2 / 4.0)
            k2_roll.append((self.motor.diameter / 2) ** 2 / 2.0)
        m = np.array(m_list)
        z = np.array(z_list)
        M = m.sum()
        zcg = float((m * z).sum() / M) + self.cg_shift
        Iyy = float((m * ((z - zcg) ** 2 + np.array(k2_lat))).sum())
        Ixx = float((m * np.array(k2_roll)).sum())
        return MassProps(M, zcg, Ixx, Iyy)

    def mass_props(self, t: float) -> MassProps:
        return self._mass_props(True, t)

    # ---- Barrowman normal force / centre of pressure ----------------------
    def fin_geometry(self):
        cr, ct, s, sweep = self.fin_cr, self.fin_ct, self.fin_s, self.fin_sweep
        # mid-chord line length
        lm = math.hypot(s, sweep + ct / 2.0 - cr / 2.0)
        return cr, ct, s, sweep, lm

    def cn_alpha_components(self, mach: float = 0.0):
        """Return list of (name, CNalpha, x_cp from nose tip [m]) per Barrowman."""
        beta = math.sqrt(max(1e-6, 1.0 - min(mach, 0.8) ** 2))
        out = []
        # nose: CNa = 2 (per rad), Xcp ogive = 0.466 L
        out.append(("nose", 2.0, 0.466 * self.L_nose))
        # fins
        cr, ct, s, sweep, lm = self.fin_geometry()
        d = self.D
        N = self.fin_n
        cna_f = (4.0 * N * (s / d) ** 2) / (1.0 + math.sqrt(1.0 + (2.0 * lm / (cr + ct)) ** 2))
        interference = 1.0 + self.R / (s + self.R)
        cna_f *= interference / beta
        xf = self.fin_z_le + (sweep / 3.0) * (cr + 2 * ct) / (cr + ct) + (1.0 / 6.0) * (cr + ct - cr * ct / (cr + ct))
        out.append(("fins", cna_f, xf))
        return out

    # ---- control tabs -------------------------------------------------------
    def fin_angles_deg(self):
        f = self.design["fins"]
        return [f.get("first_fin_deg", 0.0) + 360.0 * k / self.fin_n for k in range(self.fin_n)]

    def fin_cna_single(self, mach: float = 0.0) -> float:
        """normal-force slope of ONE fin along its own normal (per rad, ref. area A_ref), incl. body interference.
        For N >= 3 fins the set gives (N/2) x this in any plane."""
        return 2.0 * self.cn_alpha_components(mach)[1][1] / self.fin_n

    def tab_params(self, mach: float = 0.0):
        """(E, z_cp, r_cp): tab force = q * E * delta (delta in rad) along the fin normal, acting z_cp from the tip at
        radius r_cp. E = A_ref * CNa(one fin) * tau * (fraction of the fin planform spanned by the tab)."""
        f = self.design["fins"]
        tab = f["tab"]
        cr, ct, s = f["root_chord"], f["tip_chord"], f["span"]
        a, b = tab["r_from"], tab["r_to"]

        def area(y0, y1):          # integral of the chord between two span stations (straight taper)
            return cr * (y1 - y0) - (cr - ct) * (y1 ** 2 - y0 ** 2) / (2 * s)
        frac = area(a, b) / area(0, s)
        k_tab = tab["effectiveness"] * frac
        ym = (a + b) / 2
        chord_m = cr - (cr - ct) * ym / s
        z_cp = self.z_tail - f["trailing_edge_from_tail"] / 1000.0 - chord_m / 2000.0
        r_cp = self.R + f["can_wall"] / 1000.0 + ym / 1000.0
        return self.A_ref * self.fin_cna_single(mach) * k_tab, z_cp, r_cp

    def cn_alpha_cp(self, mach: float = 0.0, alpha: float = 0.0):
        comps = self.cn_alpha_components(mach)
        cna = sum(c[1] for c in comps)
        xcp = sum(c[1] * c[2] for c in comps) / cna
        # body lift (Galejs) for non-zero AoA: CN_body = K * (A_plan/A_ref) * alpha, acts at planform centroid
        if abs(alpha) > 1e-4:
            K = 1.1
            A_plan = self.D * self.L_body + 0.67 * self.D * self.L_nose
            cna_body = K * (A_plan / self.A_ref) * abs(alpha)
            x_body = (self.D * self.L_body * (self.L_nose + self.L_body / 2) + 0.67 * self.D * self.L_nose * 0.6 * self.L_nose) / A_plan
            xcp = (cna * xcp + cna_body * x_body) / (cna + cna_body)
            cna = cna + cna_body
        return cna, xcp

    def stability_margin_cal(self, t: float, mach: float = 0.0) -> float:
        mp = self.mass_props(t)
        _, xcp = self.cn_alpha_cp(mach)
        return (xcp - mp.z_cg) / self.D

    # ---- drag build-up (OpenRocket-style) -------------------------------
    def wetted_areas(self):
        # nose (ogive) wetted area ~ 0.9 * pi * D * L (tangent ogive, fineness ~2.7)
        S_nose = 0.86 * math.pi * self.D * self.L_nose
        S_body = math.pi * self.D * self.L_body
        cr, ct, s, sweep, lm = self.fin_geometry()
        S_fin_planform = 0.5 * (cr + ct) * s
        leg = self.design["fins"].get("leg")
        S_legs = 2.0 * self.fin_n * (leg["length"] * leg["width"] * 1e-6) if leg else 0.0
        S_fins = 2.0 * self.fin_n * S_fin_planform + S_legs
        return S_nose, S_body, S_fins, S_fin_planform

    def cd0_terms(self, v: float, motor_on: bool, rho: float = 1.225, mu: float = 1.81e-5, sos: float = 340.3) -> dict:
        """zero-lift drag build-up, term by term (before the 8 % parasitic allowance)"""
        v = max(abs(v), 1.0)
        mach = v / sos
        L = self.length
        Re = rho * v * L / mu
        rough = self.design["airframe"].get("surface_roughness_um", 60) * 1e-6
        # skin friction coefficient: turbulent, roughness-limited (OpenRocket method)
        if Re < 1e4:
            cf = 1.33e-2
        else:
            cf = 1.0 / (1.50 * math.log(Re) - 5.6) ** 2
        cf_rough = 0.032 * (rough / L) ** 0.2
        cf = max(cf, cf_rough)
        cf *= (1.0 - 0.1 * mach ** 2)
        S_nose, S_body, S_fins, S_fp = self.wetted_areas()
        fB = self.length / self.D
        t = {}
        t["body skin friction"] = cf * (1.0 + 1.0 / (2.0 * fB)) * (S_nose + S_body) / self.A_ref
        tc = self.fin_t / ((self.fin_cr + self.fin_ct) / 2)
        t["fin + leg skin friction"] = cf * (1.0 + 2.0 * tc) * S_fins / self.A_ref
        # fin pressure drag: rounded LE + square TE
        fin_frontal = self.fin_n * self.fin_t * self.fin_s
        t["fin leading edges"] = 0.12 * fin_frontal / self.A_ref            # rounded leading edge
        t["fin trailing edges"] = 0.12 * fin_frontal / self.A_ref * 0.5     # blunt trailing edge (half of it; the tabs taper)
        # nose pressure drag (tangent ogive, subsonic) ~ small
        t["nose"] = 0.02
        # base drag: annulus around nozzle; reduced while the motor is burning
        cd_base_coef = 0.12 + 0.13 * mach ** 2
        A_noz = math.pi * (self.motor.diameter / 2) ** 2
        if motor_on:
            base_area = max(self.A_ref - A_noz, 0.0) * 0.5   # exhaust entrainment fills ~half
        else:
            base_area = self.A_ref
        t["base"] = cd_base_coef * base_area / self.A_ref
        # protuberances: external camera pod (size from design.json, faired nose), 2 launch lugs, TVC gimbal gap
        pod = self.design.get("camera_pod", {"width_mm": 24.0, "protrusion_mm": 12.0, "cd": 0.45})
        pod_area = pod["width_mm"] * pod["protrusion_mm"] * 1e-6
        t["camera pod"] = pod["cd"] * pod_area / self.A_ref
        lug_area = 2 * (0.0090 ** 2 - 0.0068 ** 2) * math.pi / 4 + 2 * 0.009 * 0.0012
        t["launch lugs (2)"] = 1.2 * lug_area / self.A_ref
        t["gimbal gap"] = 0.01  # TVC gimbal gap / nozzle step
        # KESTREL-2 control fins: tab-servo pods (none since the servos moved into the fins), linkages / hinge gaps,
        # blunt feet under the legs
        fd = self.design["fins"]
        t["tab-servo pods"] = (fd["pod"]["cd"] * fd["pod"]["frontal_area_mm2"] * 1e-6 * self.fin_n / self.A_ref
                               if fd.get("pod") else 0.0)
        t["tab hinges / linkages"] = fd.get("tab", {}).get("linkage_cda_mm2", 0.0) * 1e-6 * self.fin_n / self.A_ref
        t["feet"] = (cd_base_coef * fd["leg"].get("foot_base_mm2", 0.0) * 1e-6 * self.fin_n / self.A_ref
                     if fd.get("leg") else 0.0)
        return t

    def cd0(self, v: float, motor_on: bool, rho: float = 1.225, mu: float = 1.81e-5, sos: float = 340.3,
            cd_scale: float = 1.0) -> float:
        cd = sum(self.cd0_terms(v, motor_on, rho, mu, sos).values())
        cd *= 1.08   # parasitic allowance (tape, joints, fin can step)
        return cd * cd_scale

    def drag_breakdown(self, v: float, motor_on: bool):
        """For reports: every drag term (after the 8 % allowance) and the total."""
        parts = {k: 1.08 * x for k, x in self.cd0_terms(v, motor_on).items()}
        parts["total"] = self.cd0(v, motor_on)
        return parts

    def pitch_damping_coeff(self, mp: MassProps) -> float:
        """Aerodynamic pitch damping: M_damp = -C * rho * V * omega, returns C (m^4).
        Uses Barrowman/OpenRocket body + fin damping integral approximation."""
        zcg = mp.z_cg
        # body: 0.275 * d * sum over length of (x-xcg)^3 ... approximate with a cylinder
        z0, z1 = 0.0, self.z_tail
        body = 0.275 * self.D * (abs(z1 - zcg) ** 4 + abs(zcg - z0) ** 4) / 4.0
        cr, ct, s, sweep, lm = self.fin_geometry()
        cna_f = self.cn_alpha_components()[1][1]
        xf = self.cn_alpha_components()[1][2]
        fins = 0.5 * cna_f * self.A_ref * (xf - zcg) ** 2
        return 0.5 * body + fins


def describe(rocket: Rocket) -> str:
    lines = []
    mp0 = rocket.mass_props(0.0)
    mpb = rocket.mass_props(rocket.motor.burn_time + 0.01)
    dry = rocket.dry_mass_props()
    cna, xcp = rocket.cn_alpha_cp(0.1)
    lines.append(f"Rocket length         : {rocket.length*1000:.0f} mm, diameter {rocket.D*1000:.1f} mm")
    lines.append(f"Motor                 : {rocket.motor.name}  I={rocket.motor.total_impulse:.1f} Ns  tb={rocket.motor.burn_time:.2f} s")
    lines.append(f"Dry mass (no motor)   : {dry.mass*1000:.0f} g   CG {dry.z_cg*1000:.0f} mm")
    lines.append(f"Lift-off mass         : {mp0.mass*1000:.0f} g   CG {mp0.z_cg*1000:.0f} mm   Iyy {mp0.Iyy:.4f} kg m^2")
    lines.append(f"Burn-out mass         : {mpb.mass*1000:.0f} g   CG {mpb.z_cg*1000:.0f} mm   Iyy {mpb.Iyy:.4f} kg m^2")
    lines.append(f"CP (Barrowman)        : {xcp*1000:.0f} mm   CNa {cna:.2f} /rad")
    lines.append(f"Static margin lift-off: {(xcp-mp0.z_cg)/rocket.D:+.2f} cal   burn-out: {(xcp-mpb.z_cg)/rocket.D:+.2f} cal")
    lines.append(f"TVC lever arm (CG->pivot) lift-off {(rocket.z_pivot-mp0.z_cg)*1000:.0f} mm, burn-out {(rocket.z_pivot-mpb.z_cg)*1000:.0f} mm")
    lines.append(f"Cd0 @30 m/s burning {rocket.cd0(30, True):.3f}, coasting {rocket.cd0(30, False):.3f}; @70 m/s coasting {rocket.cd0(70, False):.3f}")
    T0 = rocket.motor.thrust(0.25)
    lines.append(f"Thrust/weight @0.25s  : {T0/(mp0.mass*G0):.1f}")
    return "\n".join(lines)


if __name__ == "__main__":
    d = load_design()
    for mname in ["TSP-D20", "TSP-E12", "TSP-E20", "TSP-F35"]:
        try:
            r = Rocket(d, Motor(mname))
        except Exception as e:  # motor that doesn't fit (29 mm) still evaluated for info
            print(mname, e)
            continue
        print("=" * 70)
        print(describe(r))
