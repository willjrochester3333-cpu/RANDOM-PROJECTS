# Simulation and test report (KESTREL-2)

**Bottom line.** Flown by the real flight code in a 6-DOF simulator, KESTREL-2 on a TSP F35 reaches **170 m** in
calm air with a 25 g payload (Monte Carlo mean **179 m**, 90 % of flights between 147 and 214 m).
It held its roll angle to within 13° and the launch direction to within 3.6° during the burn
(95th percentile). It released the parachute within 0.32 s of apogee (95 % within 0.13 s) and landed at about
5.1 m/s in **1000 of 1000 randomised flights** (F35, and the E20 and D20 test motors in their 24 mm adapter).
**41 of 41 graded scenario and fault cases pass.** An independent simulator (RocketPy) agrees within
0.4 % (worst 0.33 %).

You asked for 200 m. On the 29 mm F35 the airframe reached 188 m; the multiple-flight changes (replaceable legs,
stronger servo housings, battery hatch, more nose ballast) cost 48 g, so it now reaches 170 m (178 m with an empty
payload bay); section 3 shows what more height would cost. The price of height is drift: under its parachute the
rocket comes down for about 33 s, so it lands 154 m from the pad on average and up to 436 m in winds up to 6 m/s.

## 1. How the rocket is simulated

`sim/kestrel/` is a purpose-built 6-DOF simulator:

| Model | Details |
|---|---|
| Rigid body | quaternion attitude, 500 Hz; mass, CG and inertia (roll and pitch) vary as the propellant burns |
| Mass properties | printed parts from the **actual CAD meshes** with their print settings (`cad/mass_properties.json`), tubes from density, every bought part where the CAD puts it (`cad/component_positions.json`), payload 0–50 g in the bay; the 24 mm adapter sleeve, its retainer and the D spacer are added only when a 24 mm motor is loaded |
| Aerodynamics | Barrowman normal force and centre of pressure (nose, body, 4 fins with body interference), pitch and roll damping; drag build-up: roughness-limited skin friction (body, fins, legs), fin leading edges (4 mm, rounded), the wedge that fairs the 15 mm bottom band into the fin, tapered trailing edges, base drag (reduced while the motor burns), camera pod, **tab hinge gaps and fin feet**, launch lugs, gimbal gap, +8 % allowance |
| Fin tabs | each tab's force acts along its own fin's normal at its own position, so the four tabs make roll, pitch and yaw moments exactly as their geometry dictates; effectiveness 0.45 of an all-moving surface of the same area; servo model with speed limit, lag, dead-band, backlash, trim error, direct drive (the servo inside the fin turns the tab: servo angle = tab angle), and fault modes (stuck, hard-over, dead) |
| Motors | TSP F35 (mission), D20, E12, E20 and Estes thrust curves (ThrustCurve.org data via OpenRocket), **scaled to the manufacturer's rated impulse and burn time** (UKROC list); `KESTREL_MOTOR_BASIS=curve` flies the raw curves |
| Environment | ISA atmosphere at the site altitude, wind with Gauss–Markov gusts, launch rod (length and tilt) with friction |
| TVC | two-axis gimbal with 50 Hz servo frames, servo speed limit, lag, dead-band, backlash, trim error; 0.41 gimbal degrees per servo degree (9 mm horn, 22 mm gimbal arm) |
| Sensors | IMU noise, bias, bias drift, misalignment and lever-arm effects; barometer noise, rate and static-port error; GPS at 5 Hz |
| Recovery | latch delay, parachute fill time and drag; ground contact and landing detection |
| **Flight software** | **`firmware/core` compiled as a shared library and called 500 times a second, exactly as on the Pico (software-in-the-loop)**: every number on this page comes from the code that will fly |

## 2. Validation against RocketPy

The same airframe (same drag curve, mass properties, motor) flown passively in
[RocketPy](https://github.com/RocketPy-Team/RocketPy), no wind (`sim/validate_rocketpy.py` →
`sim/results/rocketpy_validation.md`):

| Motor | Apogee | Apogee time | Max speed | Rod-exit speed | Static margin |
|---|---|---|---|---|---|
| TSP F35 | 169.86 vs 169.79 m (+0.0 %) | 6.62 vs 6.62 s | 51.66 vs 51.65 m/s | 9.65 vs 9.65 m/s | 0.77 vs 0.77 cal |
| TSP E20 (adapter) | 46.24 vs 46.19 m (+0.1 %) | 4.06 vs 4.06 s | 21.35 vs 21.34 m/s | 6.24 vs 6.25 m/s | 0.79 vs 0.79 cal |
| TSP D20 (adapter) | 16.45 vs 16.44 m (+0.1 %) | 2.31 vs 2.31 s | 13.40 vs 13.40 m/s | 6.55 vs 6.55 m/s | 0.84 vs 0.83 cal |
| TSP E12 (adapter) | 36.04 vs 36.00 m (+0.1 %) | 4.68 vs 4.68 s | 14.60 vs 14.58 m/s | 4.77 vs 4.77 m/s | 0.79 vs 0.79 cal |

Every quantity agrees within 0.4 %. This checks the flight mechanics; the drag and mass inputs are checked in
section 3 and by real flights.

## 3. Apogee: from the ~123 m estimate to 170 m

When we chose the motor I estimated about 123 m on the 24 mm TSP E20 for a rocket of about 650 g. The finished
rocket weighed about 830 g, and the E20 is rated at 36 Ns rather than the 40 Ns of its test curve, so on the E20 it
reached only 57 m. You then asked for 200 m. No 24 mm TSP motor gets close: even 100 g lighter the E20 would reach
about 77 m. TSP's 29 mm **F35** (65 Ns, 92 g) does, so the TVC module takes 29 mm motors, and that rocket reached
188 m. Making it a **multiple-flight rocket** then added 48 g: replaceable legs on solid tongues with their bolts,
servo housings 2 mm thicker, the battery hatch and its door, and 13 g more nose ballast to keep it flying straight
if all its steering fails (section 7). On the F35 it now reaches **170 m**:

- **Mass.** **904 g** at lift-off with the F35 and 25 g of payload (879 g with an empty bay, 929 g with 50 g).
- **Stability.** +0.72 to +0.84 calibres at lift-off (empty to full bay), +0.91 to +1.03 at burn-out, with 46 g of
  nose ballast: positive with every steering servo dead, and that flight stays close to vertical (section 4,
  `passive_*`). With the old 33 g the heavier tail would have left +0.56 to +0.69, and with all steering dead the
  rocket arced right over (93 m, 175° of tilt) before its parachute opened.
- **Speed.** 51.6 m/s at burn-out: about 1.6 kPa of dynamic pressure, six times the E20's (section 6b checks the
  tab servos and the fins for it). Peak acceleration 5.6 g. It leaves a 1 m rod at 9.6 m/s.

Drag build-up at 40 m/s, coasting (`Cd0` = 0.90, every term including the 8 % allowance; `sim/whatif.py` →
`sim/results/whatif.md`):

| Term | Cd | | Term | Cd |
|---|---|---|---|---|
| body skin friction | 0.282 | | launch lugs (2) | 0.040 |
| base drag | 0.132 | | leg sleeves (short boat-tail to the post) | 0.029 |
| fin + leg skin friction | 0.080 | | nose | 0.022 |
| camera pod | 0.076 | | leg bolt heads and nuts | 0.021 |
| fin trailing edges (1.5 mm, tapered) | 0.071 | | tab hinge gaps | 0.017 |
| wedge fairing the 15 / 17 mm band into the fin | 0.063 | | feet | 0.012 |
| fin leading edges (4 mm, rounded) | 0.042 | | gimbal gap | 0.011 |
| | | | battery-hatch door edge | 0.005 |

The fin and leg terms are conservative engineering estimates (a rounded leading edge or a gentle wedge in attached
flow has very little pressure drag); they are spread over ±8 % in the Monte Carlo and ±20 % in the scenarios.

What-if flights (passive, calm, same simulator, `sim/whatif.py`):

| Change | F35 apogee |
|---|---|
| **as designed** (rated 65 Ns, 25 g payload, 36 in chute, 46 g nose ballast) | **169.9 m** |
| empty payload bay / maximum 50 g payload | 178.1 m / 161.9 m |
| F35 delivering its published test curve (67 Ns) | 176.2 m |
| without the nose ballast (46 g lighter, but then only +0.20 calibres: not recommended) | 185.4 m |
| 50 g lighter / 100 g lighter | 186.8 m / 205.2 m |
| 20 % less drag | 176.1 m |
| TSP E20 / D20 in the 24 mm adapter (the test flights) | 46.2 m / 16.4 m |

So 190 m would need the rocket about 60 g lighter, or an empty bay on a motor that performs above its rating and a
little less drag. Each 10 g saved is worth about 3.5 m; 20 % less drag is 6 m.

## 4. Scenario and fault-injection suite

`sim/scenarios.py`: 44 deterministic cases, each flying the real flight code
(all results: `sim/results/scenarios.md`; plots: `sim/results/scenario_*.png`).

Pass criteria for normal flights: tilt during the burn < 10°, roll rate during the burn < 60 °/s (the tabs hold
roll), parachute released within 1.5 s of true apogee at < 15 m/s, landing < 7 m/s, firmware reaches LANDED.
Fault cases must end with a parachute and a landing below 7 m/s; the jammed-TVC case must also stay near the pad.

| Case | Apogee | Tilt burn / coast | Roll rate burn | Deploy − apogee | Landing | Result |
|---|---|---|---|---|---|---|
| F35, calm | 170 m | 0.5° / 0.2° | 5 °/s | +0.04 s | 5.1 m/s | PASS |
| F35, 3 m/s + gusts (baseline) | 170 m | 0.7° / 0.9° | 8 °/s | +0.02 s | 5.1 m/s | PASS |
| F35, 6 m/s + 1.5 m/s gusts (1 m rod / 1.5 m rod) | 170 m | ≤ 0.9° / ≤ 1.4° | 9 °/s | +0.02 s | 5.0 m/s | PASS |
| F35, 9 m/s + 2 m/s gusts (wind limit) | 169 m | 1.0° / 1.5° | 5 °/s | +0.03 s | 4.9 m/s | PASS |
| payload 0 g / 50 g / 50 g in 6 m/s wind | 178 / 162 / 162 m | ≤ 0.9° / ≤ 1.5° | 6–9 °/s | +0.03 … +0.04 s | 5.0–5.1 m/s | PASS |
| rod tilted 5° downwind | 168 m | 5.0° / 5.2° | 10 °/s | +0.03 s | 5.1 m/s | PASS |
| 1.5° thrust misalignment | 169 m | 1.6° / 1.0° | 11 °/s | +0.02 s | 5.1 m/s | PASS |
| 2° fin cant (strong roll torque) / crooked fins | 170 m | ≤ 0.7° / ≤ 0.9° | 8–27 °/s | +0.02 s | 5.1 m/s | PASS |
| CG 20 mm aft / 15 % heavier / 20 % more drag | 170 / 134 / 164 m | ≤ 0.7° / ≤ 0.9° | 4–8 °/s | +0.02 … +0.03 s | 5.1–5.4 m/s | PASS |
| TVC gains ×0.5 / ×2, tab gains ×0.5 / ×2 | 170 m | ≤ 1.6° / ≤ 1.5° | 8–9 °/s | +0.02 … +0.04 s | 5.1 m/s | PASS |
| tabs 40 % less / more effective | 170 m | ≤ 0.8° / ≤ 1.6° | 7–10 °/s | +0.02 … +0.04 s | 5.1 m/s | PASS |
| slow servos, IMU 2° crooked, gyro drift 10× | 170 m | ≤ 0.9° / ≤ 1.1° | 7–9 °/s | +0.02 s | 5.1 m/s | PASS |
| camera panorama roll (90 °/s in the coast) | 170 m | 0.7° / 1.0° | 8 °/s | +0.02 s | 5.1 m/s | PASS |
| tabs only damp pitch and yaw in the coast | 170 m | 0.7° / 5.1° | 8 °/s | +0.04 s | 5.1 m/s | PASS |
| tabs switched off (TVC only, like KESTREL-1) | 170 m | 0.9° / 20.1° | 214 °/s | +0.02 s | 5.1 m/s | PASS (rolls fast) |
| TSP D20 / E20 in the 24 mm adapter (test flights) | 16 / 46 m | ≤ 0.3° / ≤ 4.2° | 1–2 °/s | +0.04 … +0.05 s | 5.1 m/s | PASS |
| F35 performing like its published curve | 176 m | 0.7° / 0.9° | 9 °/s | +0.04 s | 5.1 m/s | PASS |
| **FAULT** launched 1 s after switch-on | 161 m | 20.1° / 59.7° | 214 °/s | +0.03 s | 5.1 m/s | PASS (steering stays centred) |
| **FAULT** TVC servos dead, calm / 3 m/s | 170 m | ≤ 4.4° / ≤ 1.3° | 4 °/s | +0.02 s | 5.1 m/s | PASS (tabs steer) |
| **FAULT** TVC pitch servo jams at full deflection at T+0.5 s | 25 m | loops | 41 °/s | −0.79 s (abort) | 5.1 m/s | PASS: abort, parachute out, lands 29 m from the pad |
| **FAULT** tab 1 jams at full deflection at T+1 s | 130 m | 2.8° / 174.3° | 108 °/s | −0.05 s | 5.1 m/s | PASS (give-up rule, chute at apogee) |
| **FAULT** tab 2 freezes / all four tab servos dead | 170 m | ≤ 1.1° / ≤ 20.8° | 15–214 °/s | +0.02 … +0.04 s | 5.1 m/s | PASS |
| **FAULT** all six steering servos dead: calm / 3 m/s / 3 m/s with an empty bay | 163 / 162 / 169 m | ≤ 19.7° / ≤ 64.3° | 211–227 °/s | +0.02 s | 5.0–5.1 m/s | PASS (passively stable) |
| **FAULT** barometer dies at T+1 s | 170 m | 0.7° / 1.0° | 7 °/s | +1.28 s | 5.1 m/s | PASS (inertial apogee) |
| **FAULT** all steering dead in 6 m/s wind | 164 m | 19.1° / 67.4° | 217 °/s | +0.02 s | 5.1 m/s | INFO: tilts far over in the coast but still recovers; on the E20 it goes right over in the coast (why flights 1–3 need ≤ 3 m/s) |
| **FAULT** parachute never opens | 170 m |  |  |  | **51 m/s** | INFO: why ground ejection tests matter |
| TSP E12-0 in the adapter | 36 m | 0.2° / 2.8° | 2 °/s | +0.06 s | 5.1 m/s | INFO: leaves the rod at only 4.8 m/s, not recommended |

![baseline flight](../sim/results/scenario_nominal_wind3.png)

## 5. Monte Carlo

`sim/montecarlo.py`: 1000 flights (600 on the F35, 200 each on the E20 and D20 in the 24 mm adapter), each with
everything randomised at once: wind 0–6 m/s from any direction plus gusts, payload 0–50 g, motor impulse (mean
+3 %, 1 σ 5 %: the rated value is the conservative end) and burn time, mass (4 %), CG (8 mm), drag (8 %), fin lift
(7 %), thrust misalignment, fin cant and per-fin misalignment, rod tilt, TVC and tab servo trim/speed/lag/backlash,
tab effectiveness (15 %), gyro and accelerometer bias, IMU misalignment, baro noise and port error, parachute Cd
and fill time, latch delay, site altitude. A flight counts as a success only if it meets all the normal-flight pass
criteria above.

![Monte Carlo summary](../sim/results/montecarlo_summary.png)

| | TSP F35 (600 flights) | TSP E20 (adapter) (200 flights) | TSP D20 (adapter) (200 flights) |
|---|---|---|---|
| **Success** | **100 %** | **100 %** | **100 %** |
| Apogee mean (5–95 %) | **179 m** (147–214) | **50 m** (35–66) | **18 m** (14–22) |
| Max tilt during the burn, mean / 95 % | 1.8° / 3.6° | 1.5° / 3.3° | 1.4° / 3.2° |
| Max roll rate during the burn, mean / 95 % | 6.3 / 14.4 °/s | 1.7 / 3.7 °/s | 1.0 / 2.1 °/s |
| Largest roll-angle error before apogee, 95 % | 12.6° | 3.5° | 13.7° |
| Max gimbal, mean / 95 % | 0.9° / 1.6° | 1.0° / 1.7° | 1.2° / 3.4° |
| Deploy − apogee, 5–95 % | −0.12 … +0.13 s | −0.02 … +0.09 s | −0.00 … +0.08 s |
| Airspeed at deploy, mean / 95 % | 4.1 / 8.0 m/s | 2.5 / 5.2 m/s | 1.5 / 3.0 m/s |
| Landing speed, mean / max | 5.1 / 6.1 m/s | 5.1 / 6.2 m/s | 5.1 / 6.3 m/s |
| Landing distance, mean / 95 % / max | 154 / 312 / 436 m | 35 / 78 / 115 m | 10 / 21 / 27 m |
| Rod-exit speed, mean | 9.8 m/s | 6.4 m/s | 6.7 m/s |

![Apogee against payload](../sim/results/montecarlo_payload.png)

Three things in the histograms are expected, not faults:

- **Tabs at their 15° limit near apogee.** In wind, as the rocket slows, the coast attitude hold asks the tabs to
  keep it vertical against weathercocking. Below about 15 m/s they cannot (holding an angle of attack α needs about
  0.8 α of tab), so they saturate. Once the rocket is 25° off course the give-up rule centres them.
- **Roll on the F35.** 95 % of F35 flights stay within 13° of their launch roll angle (E20 3.5°). On the F35 the
  error builds up during the boost and peaks just after burn-out, at the highest dynamic pressure, with the tabs at
  only 3–5° (checked on the four worst flights), then the tabs bring it back in the coast (three of those four are
  within 2° by apogee). The roll rates stay far inside the criteria (95 % below 15 °/s in the boost). Tab backlash is not the cause: 0.05° and 0.6° give the same result.
  A firmer roll gain for the F35 would tighten it; it only matters for how steady the onboard video looks.
- **A few large tilts at apogee on the D20** (95 % below 40°, one above 90°). At a few metres per second near
  apogee in wind the rocket turns to follow the relative wind, as any stable rocket does. The parachute still opens
  within 0.11 s of apogee at under 3.8 m/s in every case.

**Drift on the F35** grows with the wind, by about 55 m per 1 m/s: farthest landing 156 m from the pad in 0–2 m/s
of wind, 198 m in 2–3 m/s, 266 m in 3–4 m/s, 332 m in 4–5 m/s and 436 m in 5–6 m/s. The recovery-area rules in
[SAFETY_AND_LEGAL.md](SAFETY_AND_LEGAL.md) come from these numbers.

Run time: about 18 minutes on 4 CPU cores.

### Stress Monte Carlo: where the margins end

`sim/stress_montecarlo.py` flies 1000 more F35 flights with every error source about **twice as wide** as above
(thrust misalignment, mass, CG, drag, fin lift, gyro and accelerometer bias, servo trim and speed, tab
effectiveness 0.4–1.6, parachute Cd and fill time) and wind **0–9 m/s**, using the documented launch procedure
(1.5 m rod above 3 m/s):

| Wind | Flights | Meets every normal-flight criterion |
|---|---|---|
| 0-3 m/s | 337 | 99.4 % |
| 3-6 m/s | 316 | 99.7 % |
| 6-9 m/s | 347 | 99.4 % |
| **all** | **1000** | **99.5 %**; parachute out and landing below 7 m/s in **99.9 %** |

The 5 flights that miss a criterion: three tilt 10.0–12.7° during the burn (one with a motor seated 3.7° crooked,
far beyond anything the normal spread draws; one with the weakest tabs the stress run allows, 0.4), one releases
the parachute at 15.1 m/s in 8.3 m/s of wind (the criterion is 15 m/s), and one lands at 7.1 m/s in 8.4 m/s of wind
(the criterion is 7 m/s: the multi-flight rocket is heavier and lands at 5.1 m/s on average instead of 4.9). Every
one releases its parachute; all but that one land below 7 m/s. That is why the pre-flight checklist
insists on the motor being pushed fully home against the washer and why the wind limits are 3 m/s for the first
flights and 6 m/s afterwards (9 m/s ever). Apogee 171 m mean (122–232 m); 95 % of landings within 487 m with wind up
to 9 m/s.

## 6. What the fin tabs do

With the tabs switched off (`tabs_disabled`) the F35 rocket rolls at 214 °/s during the burn and 266 °/s in the
coast: fine for the flight, useless for the camera. With the tabs it holds its roll angle to within 13°
(95 %) and tilts less in the coast (0.9° instead of 20.1° in the baseline wind). They also steer on their own if the
TVC fails, and `rollprog` turns the coast into a slow camera panorama.

![tabs switched off](../sim/results/scenario_tabs_disabled.png)

## 6b. Hand checks of the final design

Things the simulator does not cover, checked by hand for the final fins, the F35 and the recovery set-up:

| Check | Result | Margin / what to do |
|---|---|---|
| Tab hinge moment against the MG90S (1.8 kgf·cm stall at 4.8 V, [datasheet](https://cdn.shopify.com/s/files/1/1509/1638/files/MG90S_Micro_Servo_Datenblatt_AZ-Delivery_Vertriebs_GmbH.pdf)) | at most 0.13 kgf·cm at the F35's 51.6 m/s (1.61 kPa) with a full 15° of tab, taking the whole tab-induced force (q × 22.9 cm² × δ) at the middle of the 27 mm behind the hinge | 14× (10× with tabs 40 % more effective than modelled) |
| Fin flutter (NACA TN 4197 estimate for the thin 4 mm part of the fin: root chord 110 mm, tip 60 mm, span 50 mm, sea level) | flutter speed at least 450 m/s even with a deliberately low shear modulus of 0.3 GPa for printed PETG | 8.7× the F35's top speed; the low aspect ratio (0.6) and the 15 mm band at the root make these fins very stiff |
| TVC pivots and servos | the F35's peak thrust (55 N on its test curve) passes through the gimbal pivot, so the servos carry only friction and the motor's inertia; the two M3 pivots each carry about 28 N | large |
| Acceleration | 5.6 g peak at lift-off (F35), 1.8 g when the parachute opens at apogee | the 50 g payload weighs about 0.3 kg-force in the boost: screw it to the bay floor |
| Tab servo speed | the simulator uses the datasheet's 0.10 s/60° (4.8 V) | matches |
| Tab effectiveness | 0.45 assumed (simulator and firmware agree); thin-aerofoil flap theory says the final, longer tab is about 20 % more effective | inside the ±40 % the scenarios test; `sim/mc_tab_effectiveness.py` flies 200 F35 Monte Carlo flights with it centred 20 % higher: 200 / 200 succeed |
| Fin root, sideways load on a foot | section modulus ≈ 1900 mm³ (the 15 mm band carries it) | about 1 kN at the foot |
| Landing loads on a foot: every section of the real fin, sliced from the CAD (`cad/kestrel_cad.py` geometry; the strength of each slice is its section modulus over its distance from the foot; 15 MPa across the print layers, as before) | the tab bay leaves the outer part of each fin (servo housing + leg) joined to the rest only above z ≈ 17 mm, so **the servo housing's two side walls carry every leg load**. With the original 1.2 mm walls they were the weakest point, at about **66 N outward / 105 N sideways at the foot**, not the leg root (the old check said 180 / 225 N there) | walls 2.2 mm (housing 17 mm): about **125 N / 204 N**. Fin-can tongue under each tip: 228 / 193 N. **Replaceable leg** (tough PLA, solid): its post breaks first, at about **73 N / 112 N**, so a hard landing costs a 5 g leg, not the fin can. TEST_PLAN A19 break-tests spare legs (≈ 7.5 / 11.5 kg), A20 drop-tests the whole rocket at the 5.1 m/s landing speed |
| Spring ejection | 32.5 N packed, 0.41 J stored; 139 g to move (nose, 46 g of ballast, 36 in chute, cord, piston): ideal separation 2.4 m/s | test A13 (10 of 10 ground ejections) is the real check; see the note there if separations are slow |

## 7. Design iterations: what testing changed

| Found by | Problem | Fix |
|---|---|---|
| Interference check (1711 part pairs) | nose sleeve and insert shoulder overlapped; door-frame arm poked through the tube; servo horns sat on the splines | shoulder shortened, arm clipped to the tube, horns bored: **no overlaps** |
| Release-latch check | the bolt engaged the nose sleeve by only 0.85 mm | bolt lengthened: 1.05 mm engagement when locked, 2.45 mm clearance when released |
| Printability check | sealed nose cavity, coincident faces, tiny gaps made several STLs non-watertight or multi-body | vent hole, merged solids: **all parts single-body and watertight** (now 30) |
| Fault scenario (jammed tab) | one tab jammed at 8° made the rocket tumble | mixer controls roll first and clips each tab on its own; spin guard; give-up rule. An 8° jam now flies normally; a full hard-over still tumbles in the coast but the parachute opens at apogee |
| Motor data check | the E20 curve file integrates to 40 Ns but the motor is rated 36 Ns | simulator scales every curve to its rated impulse (apogee 95 → 78 m) |
| PCB DRC | silkscreen overlaps after adding 3 servo ports; a starved thermal relief | labels moved, solid connection: **0 violations** |
| Build-guide walk-through | the tab-servo lead holes (4 × 7 mm) were smaller than a servo plug | full-length 4 × 19 mm slots through pod floor, fin can and tube |
| Build-guide walk-through | the CAD drew only 4 of the 7 servo plugs on the board | mechanical export fixed; the other 3 checked for interference: none |
| Build-guide walk-through | a servo plug cannot pass the notch in the parachute wall | release lead is laid along the tube before the wall is glued in |
| Build-guide walk-through | the GPS antenna bias resistor would put 3.3 V on a passive antenna | R24 not fitted |
| Passive-flight scenarios | with every steering servo dead the rocket is safe in 3 m/s, but in 6 m/s it goes right over in the coast on the small motors | wind limit 3 m/s for flights 1–3; 1.5 m rod above 3 m/s |
| Balance check | the limit did not allow for an empty payload bay | limit 640 mm from the nose tip |
| Firmware tests | a synthetic boost was too strong for the rated-impulse timing | test profile corrected |
| New overhang check (every STL in its print orientation) | flat 55 mm ceilings printed in mid-air (nose bulkhead, parachute wall), a piston and a door laid the wrong way up, an unsupported GPS shelf, hanging nut blocks and lug | 45° conical nose bulkhead, wall skirt moved up, orientations fixed, gusseted GPS platform, 45° wedges: only 4 parts still need supports, and the check now runs on every CAD build |
| GPS platform re-design | the old antenna shelf sat 20 mm above the Pico's USB socket and had no way out for the antenna lead | U-shaped platform beside the socket: a USB cable plugs in with the av-bay assembled |
| New CAD ↔ design check | the TVC linkage is 9 mm horn / 18 mm arm = 0.50 gimbal degrees per servo degree, but firmware and simulator assumed 0.42 (the gimbal would have moved 19 % more than commanded, to 7.1° at the 6° limit); the tab horn was 14.3 mm, not 14.5 | `design.json`, simulator and firmware 2.01 corrected; the CAD script now refuses to build if they disagree |
| Your change: 15 mm fins with the tab servos inside (build check) | the lower servo-mounting screw had only 4.3 mm of plastic before the tab gap: a long screw would come through and jam the tab | blind pilot holes and M2 × 6 mm screws (shopping list row 9) |
| Your change (build check) | the first 4 mm lead channel through the fin was no taller than a servo plug; the lead ran outside the fin tip | 5 mm channel; a groove in the fin tip keeps the lead below the surface |
| Your change (stability check) | the thick fins put about 70 g at the tail: static margin fell from +0.70 to +0.39 calibres | 33 g of nose ballast (M3 nuts in epoxy through a fill hole in the nose bulkhead) |
| Your change (Monte Carlo) | 3 of 200 D20 flights peaked below 15 m, the apogee detector's arming height: parachute out 1.3 s after apogee, 16 m/s landings | arming height 15 → 8 m (firmware 2.02): all D20 flights deploy at apogee |
| Your change (Monte Carlo) | the heavier rocket came down at 5.8 m/s on the 30 in chute, 2 of 1000 flights just over the 7 m/s limit | 36 in parachute (fill time modelled 20 % longer): 4.9 m/s |
| Your change: "only the part that needs it thick, the rest normal, very aerodynamic" | the whole-fin 15 mm design had a 15 mm blunt leading edge and blunt bases at the tail | fins are now 4 mm with a half-round leading edge; only the 45 mm bottom band (tab hinge, servo, lead channel) is 15 mm, joined by a 15° wedge; tab, band and legs taper to 1.5 mm trailing edges 12 mm below the tail. Fin can 181 → 165 g, drag coefficient 0.94 → 0.85, E20 apogee 55 → 57 m |
| Your change: "it should go 200 m high" → the F35 with the airframe as it is | the E20 tops out near 77 m even 100 g lighter; the 29 mm F35 needs a 29 mm gimbal, and with the holder 2.5 mm bigger the old pushrods (18 mm out) would sit inside its swing | 29 mm TVC module: holder and ring 2.5 mm larger in radius, gimbal arms 18 → 22 mm with round bosses (linkage 0.50 → 0.41 gimbal degrees per servo degree), F35 retainer with a 22 mm opening; firmware 2.03 adds the F35 (`motor 5`, the default) and settings layout 6. F35 apogee 188 m |
| Gimbal sweep (now including the pushrods and horns) | at 7° the holder's pushrod arm touched the frame just below a window; the bigger retainer would have hit the frame's bottom ring | window 2 mm lower, bottom ring opened from 24.6 to 26 mm radius: no contact in 1350 checks, both motor set-ups |
| Fit check of the motor bore | the F35's top rim would have pressed 0.1 mm into the ledge round the washer recess | 0.3 mm of play above the motor |
| Build check of the 24 mm test motors | a 70 mm D20 in the 95 mm bore had nothing above it and would have jumped 25 mm up into the washer at ignition (already true in the 24 mm version) | printed adapter sleeve and 24 mm retainer for the D20 / E20, plus a 25 mm spacer above 70 mm motors; the simulator adds their mass |
| Your change: "it needs to be a multiple-flight rocket" (section check of the real fin) | landing loads go through the 1.2 mm servo-housing walls beside the open tab bay: the fin can would crack before a leg broke; a broken leg meant reprinting the whole fin can and moving four servos | servo housings 17 mm (walls 2.2 mm, about 1.9× stronger); **replaceable legs** on a solid tongue under each fin tip, one M3 bolt each, the post the designed weak link; firmware 2.04 (tables for the heavier rocket) |
| Your change: battery and USB without taking the rocket apart | charging and USB meant removing the middle part and the av-bay | **battery hatch** on the lug side: the pack slides out, the Pico's own USB socket is reached through it with an angled cable (a panel-mount extension would have added 16 g); the door sits on the tube and overlaps the opening 2 mm all round (no gap, nothing proud on the rod side), hooks at the top and a quarter-turn latch; the upper lug moves to the middle tube |
| Stability check after the multi-flight changes | the legs, tongues, bolts and thicker housings put about 35 g at the tail: margin +0.77 → +0.63 calibres, and with **all six steering servos dead** the rocket now arced right over (93 m, 175° tilt; it still landed under its parachute) | nose ballast 33 → 46 g: margin +0.72 to +0.84 at lift-off, the all-servos-dead case back to the old behaviour. Cost of the whole multi-flight package: 48 g, 188 → 170 m |

## 8. The launch video

`sim/results/video/kestrel2_flight_seed7.mp4` (4.9 m/s wind, 20 g payload, F35, apogee
179 m) is a randomised flight from the same simulator with the real flight code, rendered in Blender with
the final CAD: ground camera and onboard camera side by side, live telemetry bottom left, graphs below. The fin tabs
move by their simulated angles; the parachute opens as the simulator says it does. Make another (each seed is a
different flight: wind, gusts, payload, motor performance, sensor errors):

```bash
cd sim && python3 video/make_flight_video.py --seed 12
```

## 9. What only real flights can confirm

The model is only as good as its inputs. The test plan ([TEST_PLAN.md](TEST_PLAN.md)) checks the uncertain ones in
order: tab effectiveness (the largest uncertainty, ±40 % tested), printed-part drag and finish (it matters more at
the F35's speed), TSP motor-to-motor variation, gimbal and tab-hinge friction, parachute opening, static-port error,
the JLCPCB part rotations (checked visually at ordering), and the strength of the printed tail: the section checks
use one assumed layer strength for the PETG fin can and the tough-PLA legs, so the leg break test (A19) and the
drop test (A20) are what prove that a leg breaks before the fin can. Compare every flight log with the simulation
(`firmware/tools/kestrel_link.py plot`) before moving to the next step.

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
