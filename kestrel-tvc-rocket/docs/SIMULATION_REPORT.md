# Simulation and test report (KESTREL-2)

**Bottom line.** Flown by the real flight code in a 6-DOF simulator, KESTREL-2 on a TSP E20 reaches **55 m** in
calm air with a 25 g payload (Monte Carlo mean **60 m**, 90 % of flights between 45 and 76 m). It held its roll
angle to within 4° and the launch direction to within 3.3° during the burn (95th percentile). It released the
parachute within ±0.1 s of apogee and landed at about 4.9 m/s in **1000 of 1000 randomised flights** (E20 and D20).
**40 of 40 graded scenario and fault cases pass.** An independent simulator (RocketPy) agrees within 0.3 %.

The apogee is well below the ~123 m I estimated when we chose the motor. Section 3 explains why, with numbers;
putting the tab servos inside the fins is about 20 m of it.

## 1. How the rocket is simulated

`sim/kestrel/` is a purpose-built 6-DOF simulator:

| Model | Details |
|---|---|
| Rigid body | quaternion attitude, 500 Hz; mass, CG and inertia (roll and pitch) vary as the propellant burns |
| Mass properties | printed parts from the **actual CAD meshes** with their print settings (`cad/mass_properties.json`), tubes from density, every bought part where the CAD puts it (`cad/component_positions.json`), payload 0–50 g in the bay |
| Aerodynamics | Barrowman normal force and centre of pressure (nose, body, 4 fins with body interference), pitch and roll damping; drag build-up: roughness-limited skin friction (body, fins, legs), fin leading and trailing edges (15 mm thick fins), base drag (reduced while the motor burns), camera pod, **tab hinge gaps and fin feet**, launch lugs, gimbal gap, +8 % allowance |
| Fin tabs | each tab's force acts along its own fin's normal at its own position, so the four tabs make roll, pitch and yaw moments exactly as their geometry dictates; effectiveness 0.45 of an all-moving surface of the same area; servo model with speed limit, lag, dead-band, backlash, trim error, direct drive (the servo inside the fin turns the tab: servo angle = tab angle), and fault modes (stuck, hard-over, dead) |
| Motors | TSP D20, E12, E20, F35 and Estes thrust curves (ThrustCurve.org data via OpenRocket), **scaled to the manufacturer's rated impulse and burn time** (UKROC list); `KESTREL_MOTOR_BASIS=curve` flies the raw curves |
| Environment | ISA atmosphere at the site altitude, wind with Gauss–Markov gusts, launch rod (length and tilt) with friction |
| TVC | two-axis gimbal with 50 Hz servo frames, servo speed limit, lag, dead-band, backlash, trim error |
| Sensors | IMU noise, bias, bias drift, misalignment and lever-arm effects; barometer noise, rate and static-port error; GPS at 5 Hz |
| Recovery | latch delay, parachute fill time and drag; ground contact and landing detection |
| **Flight software** | **`firmware/core` compiled as a shared library and called 500 times a second, exactly as on the Pico (software-in-the-loop)**: every number on this page comes from the code that will fly |

## 2. Validation against RocketPy

The same airframe (same drag curve, mass properties, motor) flown passively in
[RocketPy](https://github.com/RocketPy-Team/RocketPy), no wind (`sim/validate_rocketpy.py` →
`sim/results/rocketpy_validation.md`):

| Motor | Apogee | Apogee time | Max speed | Rod-exit speed | Static margin |
|---|---|---|---|---|---|
| TSP E20 | 55.46 vs 55.42 m (+0.1 %) | 4.32 vs 4.32 s | 24.25 vs 24.24 m/s | 6.72 vs 6.72 m/s | 0.90 vs 0.89 cal |
| TSP D20 | 20.16 vs 20.15 m (+0.0 %) | 2.49 vs 2.49 s | 15.30 vs 15.30 m/s | 7.09 vs 7.10 m/s | 0.98 vs 0.97 cal |
| TSP E12 | 45.83 vs 45.78 m (+0.1 %) | 4.98 vs 4.98 s | 17.68 vs 17.66 m/s | 5.22 vs 5.22 m/s | 0.90 vs 0.89 cal |

Every quantity agrees within 0.3 %. This checks the flight mechanics; the drag and mass inputs are checked in
section 3 and by real flights.

## 3. Why ~57 m and not the ~123 m estimate

When we chose the motor I estimated about 123 m on the E20 for a rocket of about 650 g with 50 g of payload, using
the E20's published thrust curve (40 Ns). Three things differ in the finished design:

1. **Mass.** The finished rocket weighs **825 g** at lift-off with 25 g of payload (850 g with 50 g). Seven servos
   are 99 g; the one-piece fin can is 165 g (normal 4 mm fins, but with the 15 mm bottom band that holds the tab
   servos); the nose carries 33 g of ballast; the 36 in parachute is 35 g; the latch insert and coupler are 56 g.
   Putting the tab servos inside the fins cost about 20 m of apogee compared with the old 2 mm fins with servo pods
   (77.5 m): the band puts about 50 g more at the tail, which needs the 33 g of nose ballast to keep the balance
   point where it was (+0.84 … +0.97 calibres), and the extra weight needs the 36 in parachute for gentle landings.
2. **Rated impulse.** The UK approved-motor list rates the E20 at **36 Ns**; the published test curve integrates to
   40 Ns. The simulator uses the rated value. If your motors match the curve, add about 13 m.
3. **Drag.** The fins are thin where they meet the air first, the band is faired in with a gentle wedge and every
   trailing edge tapers to 1.5 mm, so the fins add little drag; at these speeds (25 m/s at most) drag hardly matters
   anyway: 20 % less drag adds less than 1 m.

Drag build-up at 40 m/s, coasting (`Cd0` = 0.85, every term including the 8 % allowance; `sim/whatif.py` →
`sim/results/whatif.md`):

| Term | Cd | | Term | Cd |
|---|---|---|---|---|
| body skin friction | 0.282 | | fin leading edges (4 mm, rounded) | 0.042 |
| base drag | 0.132 | | launch lugs (2) | 0.040 |
| fin + leg skin friction | 0.080 | | nose | 0.022 |
| camera pod | 0.076 | | feet (tapered legs) | 0.017 |
| fin trailing edges (1.5 mm, tapered) | 0.075 | | tab hinge gaps | 0.017 |
| wedge fairing the 15 mm band into the fin | 0.057 | | gimbal gap | 0.011 |

The fin terms are conservative engineering estimates (a rounded leading edge or a gentle wedge in attached flow has
very little pressure drag); they are spread over ±8 % in the Monte Carlo and ±20 % in the scenarios.

What-if flights (passive, calm, same simulator, `sim/whatif.py`):

| Change | E20 apogee |
|---|---|
| **as designed** (rated 36 Ns, 25 g payload, 36 in chute) | **57.5 m** |
| empty payload bay / maximum 50 g payload | 61.9 m / 53.4 m |
| E20 delivering its published curve (40 Ns) | 70.7 m |
| without the nose ballast (but then only +0.47 calibres: not recommended) | 63.4 m |
| 50 g lighter / 100 g lighter | 66.7 m / 77.5 m |
| 20 % less drag | 58.2 m |
| the previous whole-fin 15 mm design (earlier today) / the 2 mm fins with servo pods (earlier version) | 55.5 m / 77.5 m |
| TSP F35 (29 mm, 65 Ns), which would need a 29 mm TVC module | 190 m |

So each 10 g saved is worth about 2 m, and drag is almost irrelevant at these speeds. Reaching ~123 m on an E20
would need the rocket to lose roughly 300 g, which it cannot do with every agreed feature on board. The motor that
would clearly exceed it is the TSP F35, at the cost of a 29 mm TVC module.

## 4. Scenario and fault-injection suite

`sim/scenarios.py`: 43 deterministic cases, each flying the real flight code
(all results: `sim/results/scenarios.md`; plots: `sim/results/scenario_*.png`).

Pass criteria for normal flights: tilt during the burn < 10°, roll rate during the burn < 60 °/s (the tabs hold
roll), parachute released within 1.5 s of true apogee at < 15 m/s, landing < 7 m/s, firmware reaches LANDED.
Fault cases must end with a parachute and a landing below 7 m/s; the jammed-TVC case must also stay near the pad.

| Case | Apogee | Tilt burn / coast | Roll rate burn | Deploy − apogee | Landing | Result |
|---|---|---|---|---|---|---|
| E20, calm | 57 m | 0.3° / 0.1° | 2 °/s | +0.04 s | 4.9 m/s | PASS |
| E20, 3 m/s + gusts (baseline) | 57 m | 0.3° / 1.9° | 2 °/s | +0.04 s | 4.9 m/s | PASS |
| E20, 6 m/s + 1.5 m/s gusts (1 m rod / 1.5 m rod) | 57 / 57 m | 0.4° / 5.2° | 2 °/s | +0.05 / +0.05 s | 4.8 m/s | PASS |
| E20, 9 m/s + 2 m/s gusts (wind limit) | 57 m | 0.8° / 14.6° | 1 °/s | +0.05 s | 4.6 m/s | PASS |
| payload 0 g / 50 g / 50 g in 6 m/s wind | 62 / 53 / 53 m | ≤ 0.4° | ≤ 3 °/s | ≤ +0.05 s | 4.8–5.0 m/s | PASS |
| rod tilted 5° downwind | 57 m | 5.0° / 5.0° | 3 °/s | +0.04 s | 4.8 m/s | PASS |
| 1.5° thrust misalignment | 57 m | 1.0° / 2.1° | 2 °/s | +0.04 s | 4.9 m/s | PASS |
| 2° fin cant (strong roll torque) / crooked fins | 57 / 57 m | 0.3° / 0.3° | 10 / 4 °/s | +0.04 s | 4.9 m/s | PASS |
| CG 20 mm aft / 15 % heavier / 20 % more drag | 57 / 41 / 57 m | ≤ 0.3° | ≤ 2 °/s | ≤ +0.05 s | 4.8–5.2 m/s | PASS |
| TVC gains ×0.5 / ×2, tab gains ×0.5 / ×2 | 57 m | ≤ 0.9° | 2–6 °/s | +0.04 s | 4.9 m/s | PASS |
| tabs 40 % less / more effective | 57 m | 0.4° / 0.3° | 3 / 3 °/s | +0.04 s | 4.9 m/s | PASS |
| slow servos, IMU 2° crooked, gyro drift 10× | 57 m | ≤ 0.5° | ≤ 3 °/s | +0.04 s | 4.9 m/s | PASS |
| camera panorama roll (90 °/s in the coast) | 57 m | 0.3° / 1.4° | 2 °/s | +0.04 s | 4.9 m/s | PASS |
| tabs switched off (TVC only, like KESTREL-1) | 57 m | 0.3° / 23.4° | **75 °/s** | +0.05 s | 4.9 m/s | PASS (rolls fast) |
| TSP D20 / E20 performing like its curve (40 Ns) | 21 / 71 m | 0.4° | 1–3 °/s | +0.04 s | 4.9 m/s | PASS |
| **FAULT** launched 1 s after switch-on | 56 m | 21° / 27° | 75 °/s | +0.03 s | 4.9 m/s | PASS (steering stays centred) |
| **FAULT** TVC servos dead, calm / 3 m/s | 57 / 57 m | 3.4° / 4.1° | 2 / 3 °/s | +0.04 s | 4.9 m/s | PASS (tabs steer) |
| **FAULT** TVC pitch servo jams at full deflection at T+0.5 s | 16 m | loops | 18 °/s | −0.96 s (abort) | 4.9 m/s | PASS: abort, parachute out, lands 19 m from the pad |
| **FAULT** tab 1 jams at full deflection at T+1 s | 57 m | 0.6° / 37° | 25 °/s | +0.04 s | 4.8 m/s | PASS (give-up rule, chute at apogee) |
| **FAULT** tab 2 freezes / all four tab servos dead | 57 / 57 m | 0.4° / 0.4° | 2 / 75 °/s | +0.04 / +0.05 s | 4.9 m/s | PASS |
| **FAULT** all six steering servos dead: calm / 3 m/s / 3 m/s with an empty bay | 56 / 56 / 60 m | 17° / 23° / 22° | 73–83 °/s | +0.05 s | 4.8–4.9 m/s | PASS (passively stable) |
| **FAULT** barometer dies at T+1 s | 57 m | 0.4° / 0.4° | 4 °/s | +1.26 s | 4.8 m/s | PASS (inertial apogee) |
| **FAULT** all steering dead in 6 m/s wind | 48 m | 24° / 169° | 75 °/s | +0.03 s | 4.9 m/s | INFO: turns right over; why flights 1–3 need ≤ 3 m/s |
| **FAULT** parachute never opens | 57 m |  |  |  | **32 m/s** | INFO: why ground ejection tests matter |
| TSP E12-0 | 48 m | 0.2° | 2 °/s | +0.06 s | 4.9 m/s | INFO: leaves the rod at only 5.3 m/s, not recommended |

![baseline flight](../sim/results/scenario_nominal_wind3.png)

## 5. Monte Carlo

`sim/montecarlo.py`: 1000 flights, each with everything randomised at once: wind 0–6 m/s from any direction plus
gusts, payload 0–50 g, motor impulse (mean +3 %, 1 σ 5 %: the rated value is the conservative end) and burn time,
mass (4 %), CG (8 mm), drag (8 %), fin lift (7 %), thrust misalignment, fin cant and per-fin misalignment, rod
tilt, TVC and tab servo trim/speed/lag/backlash, tab effectiveness (15 %), gyro and accelerometer bias, IMU
misalignment, baro noise and port error, parachute Cd and fill time, latch delay, site altitude. A flight counts as
a success only if it meets all the normal-flight pass criteria above.

![Monte Carlo summary](../sim/results/montecarlo_summary.png)

| | TSP E20 (800 flights) | TSP D20 (200 flights) |
|---|---|---|
| **Success** | **100 %** | **100 %** |
| Apogee mean (5–95 %) | **60 m** (45–76) | 22 m (17–27) |
| Max tilt during the burn, mean / 95 % | 1.6° / 3.3° | 1.5° / 3.2° |
| Max roll rate during the burn, mean / 95 % | 2.1 / 4.8 °/s | 1.4 / 2.8 °/s |
| Largest roll-angle error before apogee, 95 % | 3.8° | 9.4° |
| Max gimbal, mean / 95 % | 1.0° / 1.8° | 1.0° / 1.9° |
| Deploy − apogee, 5–95 % | −0.04 … +0.10 s | −0.02 … +0.08 s |
| Airspeed at deploy, mean / 95 % | 2.9 / 5.8 m/s | 1.8 / 3.5 m/s |
| Landing speed, mean / max | 4.9 / 5.8 m/s | 4.9 / 6.0 m/s |
| Landing distance, mean / 95 % / max | 46 / 98 / 146 m | 13 / 29 / 34 m |
| Rod-exit speed, mean | 6.9 m/s | 7.3 m/s |

The first run of this Monte Carlo on the thick-fin rocket was not clean (E20 99.9 %, D20 98 %): see section 7 for
the two causes and their fixes. This table is the run after the fixes.

![Apogee against payload](../sim/results/montecarlo_payload.png)

Two things in the histograms are expected, not faults:

- **Tabs at their 15° limit near apogee.** In wind, as the rocket slows, the coast attitude hold asks the tabs to
  keep it vertical against weathercocking. Below about 15 m/s they cannot (holding an angle of attack α needs about
  0.8 α of tab), so they saturate. Once the rocket is 25° off course the give-up rule centres them.
- **A few large tilts at apogee on the D20** (95 % below 29°, a handful above 60°). At 6 m/s near apogee in 5 m/s
  of wind the rocket turns to follow the relative wind, as any stable rocket does. The parachute still opens within
  0.12 s of apogee at under 5 m/s in every case.

Run time: about 13 minutes on 4 CPU cores.

## 6. What the fin tabs do

With the tabs switched off (`tabs_disabled`) the rocket rolls at 72 °/s during the burn and 94 °/s in the coast:
fine for the flight, useless for the camera. With the tabs it holds its roll angle to within 4° (95 %) and
tilts less in the coast (2.0° instead of 22.4° in the baseline wind). They also steer on their own if the TVC fails,
and `rollprog` turns the coast into a slow camera panorama.

![tabs switched off](../sim/results/scenario_tabs_disabled.png)

## 7. Design iterations: what testing changed

| Found by | Problem | Fix |
|---|---|---|
| Interference check (1711 part pairs) | nose sleeve and insert shoulder overlapped; door-frame arm poked through the tube; servo horns sat on the splines | shoulder shortened, arm clipped to the tube, horns bored: **no overlaps** |
| Release-latch check | the bolt engaged the nose sleeve by only 0.85 mm | bolt lengthened: 1.05 mm engagement when locked, 2.45 mm clearance when released |
| Printability check | sealed nose cavity, coincident faces, tiny gaps made several STLs non-watertight or multi-body | vent hole, merged solids: **all 27 parts single-body and watertight** |
| Fault scenario (jammed tab) | one tab jammed at 8° made the rocket tumble | mixer controls roll first and clips each tab on its own; spin guard; give-up rule. An 8° jam now flies normally; a full hard-over still tumbles in the coast but the parachute opens at apogee |
| Motor data check | the E20 curve file integrates to 40 Ns but the motor is rated 36 Ns | simulator scales every curve to its rated impulse (apogee 95 → 78 m) |
| PCB DRC | silkscreen overlaps after adding 3 servo ports; a starved thermal relief | labels moved, solid connection: **0 violations** |
| Build-guide walk-through | the tab-servo lead holes (4 × 7 mm) were smaller than a servo plug | full-length 4 × 19 mm slots through pod floor, fin can and tube |
| Build-guide walk-through | the CAD drew only 4 of the 7 servo plugs on the board | mechanical export fixed; the other 3 checked for interference: none |
| Build-guide walk-through | a servo plug cannot pass the notch in the parachute wall | release lead is laid along the tube before the wall is glued in |
| Build-guide walk-through | the GPS antenna bias resistor would put 3.3 V on a passive antenna | R24 not fitted |
| Passive-flight scenarios | with every steering servo dead the rocket is safe in 3 m/s but not in 6 m/s | wind limit 3 m/s for flights 1–3; 1.5 m rod above 3 m/s |
| Balance check | the limit did not allow for an empty payload bay | limit 640 mm from the nose tip |
| Firmware tests | a synthetic boost was too strong for the rated-impulse timing | test profile corrected; 377,489 core checks pass |
| New overhang check (every STL in its print orientation) | flat 55 mm ceilings printed in mid-air (nose bulkhead, parachute wall), a piston and a door laid the wrong way up, an unsupported GPS shelf, hanging nut blocks and lug | 45° conical nose bulkhead, wall skirt moved up, orientations fixed, gusseted GPS platform, 45° wedges: only 4 parts still need supports, and the check now runs on every CAD build |
| GPS platform re-design | the old antenna shelf sat 20 mm above the Pico's USB socket and had no way out for the antenna lead | U-shaped platform beside the socket: a USB cable plugs in with the av-bay assembled |
| New CAD ↔ design check | the TVC linkage is 9 mm horn / 18 mm arm = 0.50 gimbal degrees per servo degree, but firmware and simulator assumed 0.42 (the gimbal would have moved 19 % more than commanded, to 7.1° at the 6° limit); the tab horn was 14.3 mm, not 14.5 | `design.json`, simulator and firmware 2.01 corrected; the CAD script now refuses to build if they disagree |
| Your change: 15 mm fins with the tab servos inside (build check) | the lower servo-mounting screw had only 4.3 mm of plastic before the tab gap: a long screw would come through and jam the tab | blind pilot holes and M2 × 6 mm screws (shopping list row 9) |
| Your change (build check) | the first 4 mm lead channel through the fin was no taller than a servo plug; the lead ran outside the fin tip | 5 mm channel; a groove in the fin tip keeps the lead below the surface |
| Your change (stability check) | the thick fins put about 70 g at the tail: static margin fell from +0.70 to +0.39 calibres | 33 g of nose ballast (M3 nuts in epoxy through a fill hole in the nose bulkhead): +0.75 … +0.88 calibres again (+0.83 … +0.96 with the 36 in chute below) |
| Your change (Monte Carlo) | 3 of 200 D20 flights peaked below 15 m, the apogee detector's arming height: parachute out 1.3 s after apogee, 16 m/s landings | arming height 15 → 8 m (firmware 2.02): all D20 flights deploy at apogee |
| Your change (Monte Carlo) | the heavier rocket came down at 5.8 m/s on the 30 in chute, 2 of 1000 flights just over the 7 m/s limit | 36 in parachute (fill time modelled 20 % longer): 4.9 m/s |
| Your change: "only the part that needs it thick, the rest normal, very aerodynamic" | the whole-fin 15 mm design had a 15 mm blunt leading edge and blunt bases at the tail | fins are now 4 mm with a half-round leading edge; only the 45 mm bottom band (tab hinge, servo, lead channel) is 15 mm, joined by a 15° wedge; tab, band and legs taper to 1.5 mm trailing edges 12 mm below the tail. Fin can 181 → 165 g, drag coefficient 0.94 → 0.85, E20 apogee 55 → 57 m |

## 8. The launch video

`sim/results/video/kestrel2_flight_seed7.mp4` (4.9 m/s wind, 20 g payload) is a randomised flight from the same
simulator with the real flight code, rendered in Blender with the final CAD: ground camera and onboard camera side by
side, live telemetry bottom left, graphs below. The fin tabs move by their simulated angles; the parachute opens as
the simulator says it does. Make another (each seed is a different flight: wind, gusts, payload, motor performance, sensor errors):

```bash
cd sim && python3 video/make_flight_video.py --seed 12
```

## 9. What only real flights can confirm

The model is only as good as its inputs. The test plan ([TEST_PLAN.md](TEST_PLAN.md)) checks the uncertain ones in
order: tab effectiveness (the largest uncertainty, ±40 % tested), printed-part drag and finish, TSP motor-to-motor
variation, gimbal and tab-hinge friction, parachute opening, static-port error, and the JLCPCB part rotations
(checked visually at ordering). Compare every flight log with the simulation (`firmware/tools/kestrel_link.py
plot`) before moving to the next step.

## Reproduce everything

```bash
pip install numpy matplotlib rocketpy trimesh manifold3d
```

```bash
cmake -S firmware -B firmware/build-host && cmake --build firmware/build-host -j
```

```bash
cd sim && python3 scenarios.py && python3 montecarlo.py && python3 plot_montecarlo.py && python3 validate_rocketpy.py
```
