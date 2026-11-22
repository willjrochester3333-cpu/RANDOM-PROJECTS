# Simulation and test report

**Bottom line.** Flown by the real flight code in a 6-DOF simulator, KESTREL reaches **196 m on average on a TSP
E20** (90 % of flights between 170 and 228 m). It held the launch direction to within 4.8° (95th percentile),
released its parachute within ±0.13 s of apogee and landed at 5.5 m/s in **1000 of 1000 randomised flights**
across three motors. It also stayed safe in every fault case except the deliberate "no parachute" demonstration.

## 1. How the rocket is simulated

`sim/kestrel/` is a purpose-built 6-DOF simulator:

| Model | Details |
|---|---|
| Rigid body | quaternion attitude, 500 Hz, adaptive step; mass, CG and inertia vary as propellant burns |
| Mass properties | printed parts from the **actual CAD meshes** (`cad/mass_properties.json`), tubes from density, every other component placed where the CAD puts it (`design.json`, cross-checked automatically by the CAD script) |
| Aerodynamics | Barrowman normal force and centre of pressure (nose, body, fins, body lift), pitch damping; drag build-up: roughness-limited skin friction, fin leading/trailing edges, base drag (reduced while the motor burns), camera pod, launch lugs, gimbal gap |
| Motors | TSP D20, E12, E20 and Estes E12 thrust curves (ThrustCurve.org data as shipped with OpenRocket) |
| Environment | ISA atmosphere at the site altitude, wind with Gauss–Markov gusts, 1 m launch rod with optional tilt |
| TVC | two-axis gimbal with 50 Hz servo frames, servo speed limit, lag, dead-band, backlash, trim error |
| Sensors | IMU noise, bias, bias drift, misalignment and lever-arm (centripetal) effects; barometer noise, rate and static-port pressure error; GPS at 5 Hz |
| Recovery | latch delay, parachute fill time, drag; ground contact and landing detection |
| **Flight software** | **`firmware/core` compiled as a shared library and called 500 times a second, exactly as on the Pico (software-in-the-loop)**: every number on this page comes from the code that will fly |

## 2. Validation against RocketPy

The same rocket (same drag curve, mass, motor) flown passively in [RocketPy](https://github.com/RocketPy-Team/RocketPy) 1.13, no wind
(`sim/validate_rocketpy.py` → `sim/results/rocketpy_validation.md`):

| Motor | Apogee | Apogee time | Max speed | Rod-exit speed | Static margin |
|---|---|---|---|---|---|
| TSP E20 | 196.6 vs 196.6 m (0.0 %) | 7.02 vs 7.01 s | 56.9 vs 56.9 m/s | 10.18 vs 10.18 m/s | 1.36 vs 1.36 cal |
| TSP E12 | 160.9 vs 160.7 m (+0.1 %) | 7.45 vs 7.44 s | 43.6 vs 43.6 m/s | 8.06 vs 8.06 m/s | 1.36 vs 1.36 cal |
| TSP D20 | 82.2 vs 82.1 m (0.0 %) | 4.54 vs 4.54 s | 35.9 vs 35.9 m/s | 10.40 vs 10.40 m/s | 1.56 vs 1.55 cal |

Every quantity agrees within 0.3 %. (An early run showed a 10.7 % max-speed difference on the E12. It turned out
to be a bookkeeping bug in the comparison script: RocketPy stops at apogee, but the passive run had no parachute
and kept counting speed during the fall. The bug is fixed and the table above is ascent-only.)

## 3. Scenario and fault-injection suite

`sim/scenarios.py`: 24 deterministic cases, each flying the real flight code
(`sim/results/scenarios.md`, plots `sim/results/scenario_*.png`).

Pass criteria for normal flights: tilt during the burn < 10°, parachute released within 1.5 s of true apogee at
< 15 m/s, landing < 7 m/s, firmware reaches LANDED. Fault cases must end with a parachute (and, for the stuck
servo, stay near the pad).

| Case | Apogee | Max tilt (burn) | Deploy − apogee | Landing | Result |
|---|---|---|---|---|---|
| E20, calm | 197 m | 0.8° | +0.02 s | 5.5 m/s | PASS |
| E20, 3 m/s wind + gusts (baseline) | 196 m | 2.1° | +0.02 s | 5.5 m/s | PASS |
| E20, 6 m/s + 1.5 m/s gusts | 196 m | 3.3° | +0.02 s | 5.5 m/s | PASS |
| E20, 9 m/s + 2 m/s gusts (wind limit) | 196 m | 4.1° | +0.03 s | 5.4 m/s | PASS |
| rod tilted 5° downwind | 195 m | 5.0° | +0.02 s | 5.5 m/s | PASS |
| 1.5° thrust misalignment | 196 m | 3.0° | +0.03 s | 5.5 m/s | PASS |
| 2° fin cant → fast roll | 196 m | 2.9° | +0.02 s | 5.5 m/s | PASS |
| CG 20 mm further aft | 197 m | 1.8° | +0.02 s | 5.5 m/s | PASS |
| 15 % heavier | 161 m | 2.1° | +0.03 s | 5.9 m/s | PASS |
| 20 % more drag | 188 m | 2.1° | +0.03 s | 5.5 m/s | PASS |
| gains halved / doubled | 196 / 196 m | 3.2° / 1.4° | +0.02 / +0.02 s | 5.5 m/s | PASS |
| servos half speed, 25 ms lag, 0.5° backlash | 196 m | 2.3° | +0.02 s | 5.5 m/s | PASS |
| IMU mounted 2° crooked | 196 m | 4.3° | +0.02 s | 5.5 m/s | PASS |
| gyro bias drifting 10× spec | 196 m | 2.0° | +0.02 s | 5.5 m/s | PASS |
| TSP E12 / D20 / Estes E12 | 161 / 82 / 92 m | 1.5 / 1.4 / 1.2° | +0.04 / +0.03 / +0.04 s | 5.5 m/s | PASS |
| **FAULT** launched 1 s after switch-on (not calibrated) | 190 m | 14.9° (TVC off) | +0.02 s | 5.5 m/s | PASS (safe) |
| **FAULT** TVC servos dead, calm / 3 m/s | 195 / 190 m | 8.6 / 15.3° | +0.01 s | 5.5 m/s | PASS (fins keep it stable) |
| **FAULT** pitch servo jams at full deflection at T+0.5 s | 21 m | loops | −0.66 s (abort) | 5.5 m/s | PASS: abort detected, chute out, lands 15 m from the pad |
| **FAULT** barometer dies at T+1 s | 196 m | 2.0° | +1.40 s | 5.5 m/s | PASS |
| **FAULT** parachute never opens | 196 m | 2.1° | — | **52 m/s** | INFO: why ground ejection tests matter |

## 4. Monte Carlo

`sim/montecarlo.py`: 1000 flights, each with everything randomised at once: wind 0–6 m/s from any direction plus
gusts, motor impulse and burn time (1 σ 4 %), mass (4 %), CG (8 mm), drag (8 %), fin lift (7 %), thrust
misalignment, fin cant, rod tilt, servo trim/speed/backlash, gyro and accelerometer bias, IMU misalignment, baro
noise and port error, parachute Cd and fill time, latch delay, site altitude. A flight counts as a success only if
it meets all the normal-flight pass criteria above.

![Monte Carlo summary](../sim/results/montecarlo_summary.png)

| | TSP E20 (600 flights) | TSP E12 (200) | TSP D20 (200) |
|---|---|---|---|
| **Success** | **100 %** | **100 %** | **100 %** |
| Apogee mean (5–95 %) | **196 m** (170–228) | 161 m (128–194) | 82 m (68–95) |
| Max tilt during burn, mean / 95 % | 2.7° / 4.8° | 2.3° / 4.1° | 2.5° / 4.7° |
| Max gimbal, mean / 95 % | 2.9° / 5.4° | 2.4° / 4.5° | 3.0° / 5.3° |
| Deploy − apogee, 5–95 % | −0.13 … +0.13 s | −0.10 … +0.12 s | −0.09 … +0.12 s |
| Airspeed at deploy, mean / 95 % | 3.2 / 6.2 m/s | 3.3 / 6.6 m/s | 2.2 / 4.2 m/s |
| Landing speed, mean / max | 5.5 / 6.6 m/s | 5.5 / 6.7 m/s | 5.5 / 6.7 m/s |
| Landing distance, mean / 95 % | 153 / 314 m | 122 / 262 m | 58 / 114 m |

Run time: about 14 minutes on 4 CPU cores.

## 5. Design iterations: what testing changed

The design went through several loops of simulate → find a problem → fix → re-test. The main ones:

| Found by | Problem | Fix |
|---|---|---|
| CAD mass properties | first mass estimate (362 g) was 20 % light; with real printed-part masses the E12 no longer reached 200 m | nominal motor E12 → **E20**, lower tube 580 → 540 mm, lighter nose, frame and av-bay |
| Monte Carlo | false "landed" while hanging still under the parachute (IMU-only stillness) | landing detection driven by the barometer; IMU used only if the baro has failed |
| Monte Carlo | one run stuck in CALIBRATING: accelerometer bias of 59 mg pushed it out of the stillness band | wider band, gravity re-measured on the pad, plus the "launched before READY" safety net |
| Fault scenario (servo hard-over) | centripetal acceleration at the off-centre IMU looked like burnout | lever-arm compensation (IMU position vs CG from the motor tables) and an abort mode |
| Fault scenario | landing detection lagged | raw-baro window for landing |
| PCB DRC | clearance, via spacing, thermal reliefs, mask bridges, silkscreen | fixed in the router / generator (0 errors) |
| **CAD ↔ PCB integration** | sled standoffs and slots did not match the real 40 × 82 mm board; IMU position in `design.json` was stale | CAD now reads the KiCad layout; positions cross-checked on every CAD run |
| **Interference check (435 part pairs)** | camera pod poked into the av-bay after the tube was shortened; GPS patch hit the servo posts; a TVC servo bracket clipped the motor holder; gimbal pivot bosses overlapped | pod moved, 18 mm patch, servos raised 4 mm, 0.2 mm running gaps: **0 overlaps** |
| **Optics check** | the half-recessed camera's lens sat 2.5 mm *inside* the tube's outer surface: most of the picture would have been the inside of the tube | external pod with the lens axis 1.5 mm outside the tube; its extra drag is now in the model |
| **Gimbal sweep (24 directions at 7°)** | at full deflection the motor retainer hit the frame's tail nut bosses | bosses moved up into a solid band, lip opened: **no contact** |
| Wall-thickness probe | 0.2 mm sliver over the retainer's twist-lock slot | retainer 1.5 mm taller |
| Apogee re-check after all fixes | 189 m: 5 % short | 2S 200 mAh pack (−7 g) and the primed/painted finish the drag model assumes → **197 m** |
| Writing the checklist | the parachute latch needed a USB command to close, but the USB port is inside the closed av-bay | **snap-in latch**: bevelled bolts and springy links; pushing the upper section on locks it |
| Firmware unit tests | log padding with erased-looking bytes could fool the next boot's append search | filler records + mid-page resume; 3-session flash-model test |

## 6. What only real flights can confirm

The model is only as good as its inputs. The test plan ([TEST_PLAN.md](TEST_PLAN.md)) checks the uncertain ones in
order: printed-part drag and finish, TSP motor-to-motor variation, gimbal friction and servo behaviour under thrust,
parachute opening, static-port error, and the JLCPCB part rotations (checked visually at ordering). Compare every
flight log with the simulation (`firmware/tools/kestrel_link.py plot`) before moving to a bigger motor.

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
