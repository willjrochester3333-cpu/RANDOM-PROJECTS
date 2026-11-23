# KESTREL-2: a thrust-vector-controlled model rocket with four steerable fins

A reusable, 3D-printed, ~0.9 m model rocket that **steers its motor** (two-axis thrust vector control) and its
**four fin tabs** (roll, pitch and yaw), **stands up on its own four fins**, releases its parachute **at apogee**
with a servo latch under the nose cone (no pyrotechnics), carries a **payload of up to 50 g** behind a lockable
door, films the flight with a downward-looking camera, and logs IMU, barometer and GPS data on a **custom
flight-computer PCB** built around a Raspberry Pi Pico 2 W. It comes with its own launch pad. **No soldering
anywhere**: the PCB comes assembled from JLCPCB and everything else plugs, screws or glues together. Estimated
build cost **≈ £301** (motors extra).

<p>
<img src="cad/renders/rocket_on_pad.png" width="24%" alt="KESTREL-2 standing on its fins on the launch pad">
<img src="cad/renders/rocket_exploded.png" width="25%" alt="exploded view: the three parts">
<img src="cad/renders/parachute_open.png" width="25%" alt="descending under its parachute">
<img src="cad/renders/tvc_module.png" width="22%" alt="TVC module with its two leads out of the top">
</p>
<p>
<img src="cad/renders/fin_tab_closeup.png" width="25%" alt="fin, control tab and its servo pod">
<img src="cad/renders/payload_bay_open.png" width="24%" alt="payload bay with the door open">
<img src="cad/renders/release_latch_cutaway.png" width="24%" alt="parachute release latch under the nose cone">
<img src="cad/renders/avbay_cutaway.png" width="24%" alt="avionics bay section">
</p>

**Simulated launch videos** (ground camera, onboard camera, live telemetry and graphs; every seed is a different
flight): [`kestrel2_flight_seed7.mp4`](sim/results/video/kestrel2_flight_seed7.mp4) (4.9 m/s wind, 20 g payload) and
[`kestrel2_flight_seed16.mp4`](sim/results/video/kestrel2_flight_seed16.mp4) (almost calm, 26 g payload)

| | |
|---|---|
| Parts | **3**: bottom (fin can + TVC module + camera + flight computer + battery), middle (payload bay with door · wall · parachute bay · release latch at the top), nose cone |
| Length / diameter / fin span | 903 mm (929 mm standing on its fin feet) / 56.3 mm (Estes BT-70) / 159 mm |
| Lift-off mass | 723 g with a TSP E20 and 25 g of payload (659 g without motor) |
| Motors | 24 mm TSP **E20-0** (mission), TSP D20-0 (first hops) |
| Apogee (simulated, E20) | **77 m** nominal with 25 g of payload; Monte Carlo mean 83 m, 90 % of flights 64–103 m |
| Stability | +0.70 to +0.85 calibres at lift-off (empty to full payload bay): still stable if all steering fails |
| TVC | 2-axis gimbal, ±6° vector limit, 2 × MG90S, 500 Hz control loop |
| Fin tabs | 4 trailing-edge tabs, ±15°, 4 × MG90S in streamlined pods; hold roll in boost and coast, share pitch/yaw with the TVC in the burn, steer alone in the coast |
| Recovery | 30 in parachute, spring ejection, servo-released snap-in latch, 5.4 m/s landing |
| Payload | 130 mm bay, 32 × 50 mm hinged door with a quarter-turn lock, 4 × M3 mounting holes, up to 50 g |
| Flight computer | Pico 2 W + LSM6DSO IMU + BMP580 baro + ATGM336H GPS + 16 MB log, 4-layer 40 × 82 mm PCB, 7 servo ports |
| Camera | SQ12-class 23 mm cube in an external pod, lens looking down the body |
| Launch pad | printed hub, 3 dowel legs, 1 m (or 1.5 m) × 6 mm rod, 0–15° tilt, 200 mm tile the rocket stands on |

## How it was verified

- **Simulation with the real flight code in the loop.** A 6-DOF simulator, checked against RocketPy (every
  quantity within 0.3 %), flies the actual C++ flight software 500 times a second, including the fin-tab mixer.
  **Scenario and fault suite: 40 of 40 graded cases pass** (plus 3 informational cases).
  **1000-flight Monte Carlo: 100 % success.** → [docs/SIMULATION_REPORT.md](docs/SIMULATION_REPORT.md)
- **CAD checked automatically on every run.** All 27 printed parts are watertight, single-body and fit a
  220 × 220 × 250 mm bed. Exact-geometry interference checks cover 1711 part pairs, plus sweeps of every mechanism
  through its full travel: the gimbal in 24 directions at 7°, all four tabs at ±17°, the payload door through
  0–100° and the release latch. All come back clean. Masses and positions feed the simulator, and the av-bay is
  generated from the PCB's KiCad layout.
- **PCB**: schematic checked pin-for-pin against the circuit source, DRC 0 violations, all 65 nets routed, gerbers
  re-read by an independent viewer. → [docs/PCB.md](docs/PCB.md)
- **Firmware**: 377,489 flight-core checks, 125 firmware-logic checks, a 0-warning cross-compile and a ready-to-flash
  UF2. → [docs/FIRMWARE.md](docs/FIRMWARE.md)

Two honest gaps against what we agreed:

- **Apogee**: I estimated ~123 m on the E20 when we chose the motor. The finished rocket is heavier (723 g, not
  ~650 g), and the E20 is rated at 36 Ns, not the 40 Ns of its test curve, so it reaches 77 m (about 94 m if the
  motors match their curve). The details, with what-if numbers, are in the simulation report, section 3.
- **Budget**: ≈ £301 against the ~£270 we aimed for, because of the four extra servos, the larger 30 in parachute
  and the ejection spring that only comes in a pack of 10. → [docs/BOM.md](docs/BOM.md)

Real flights then confirm what models cannot; [docs/TEST_PLAN.md](docs/TEST_PLAN.md) takes you from the bench to
the first E20 flight in steps.

## Build it

1. **Order the PCB** (1–3 weeks): [docs/PCB.md → Ordering from JLCPCB](docs/PCB.md#ordering-from-jlcpcb)
2. **Buy the rest**: [docs/BOM.md](docs/BOM.md)
3. **Print and assemble**: [docs/BUILD_GUIDE.md](docs/BUILD_GUIDE.md)
4. **Flash and set up**: drag `firmware/pico/kestrel_fc.uf2` onto the Pico, then `calaxes`, `dirtest`, `tabtest`,
   `tvctest`, `fintest`
5. **Test**: [docs/TEST_PLAN.md](docs/TEST_PLAN.md) → **fly**: [docs/PREFLIGHT_CHECKLIST.md](docs/PREFLIGHT_CHECKLIST.md)
6. **Read first**: [docs/SAFETY_AND_LEGAL.md](docs/SAFETY_AND_LEGAL.md) (UKRA/BMFA, CAA, motors, LiPo, wind limits)

## What's where

```
design.json              master parameters: airframe, fins + tabs, TVC, payload, recovery, every component's mass/position
cad/                     Blender + manifold3d parametric model
  kestrel_cad.py           blender -b -P cad/kestrel_cad.py -- [--no-render] [--fast] [--view=NAME]
  kestrel.blend            assembly, rocket on the pad, exploded view, sections, open door, tab close-up, launch pad
  kestrel_tvc_module.blend the TVC module on its own (its two servo leads come out of the top) + assembly steps
  kestrel_parachute_open.blend  the rocket descending under its open parachute
  stl/                     27 print-ready STLs + check_report.md
  renders/                 the images above
  interference_report.md   part pairs and mechanism sweeps
pcb/                     KiCad 7 project, circuit-as-code, autorouter, production files for JLCPCB
  kestrel_fc.kicad_pro/.kicad_sch/.kicad_pcb, kestrel_fc_schematic.pdf
  production/              gerbers zip, BOM + pick-and-place CSVs, assembly drawing
firmware/
  core/                    flight core (estimation, TVC, fin-tab mixer, state machine) + unit tests
  pico/                    Pico 2 W application, drivers, host tests; kestrel_fc.uf2 = ready to flash
  sil/                     simulator bridge (software-in-the-loop)
  tools/                   kestrel_link.py (USB shell, log download, plots), gen_motor_db.py
sim/                     6-DOF simulator, scenarios, Monte Carlo, RocketPy validation, results/
  video/                   launch-video pipeline (simulation → Blender → telemetry + graphs → MP4)
docs/                    shopping list, build guide, PCB, firmware, test plan, checklist, safety, simulation report
```

## Change it

Everything is parametric and connected: edit `design.json` (or the PCB layout in `pcb/circuit.py`), then
re-run the chain. The CAD script stops with a message if `design.json` and the CAD/PCB disagree.

```bash
blender -b -P cad/kestrel_cad.py -- --no-render && python3 cad/check_parts.py && python3 cad/mass_properties.py
```

```bash
python3 firmware/tools/gen_motor_db.py && cmake --build firmware/build-host && (cd firmware/build-host && ctest)
```

```bash
cd sim && python3 scenarios.py && python3 montecarlo.py && python3 plot_montecarlo.py
```

Tools: Blender 4.0, KiCad 7, Python 3 (numpy, matplotlib, pillow, trimesh, manifold3d, rocketpy), ffmpeg,
Raspberry Pi Pico SDK 2.1, arm-none-eabi-gcc.
