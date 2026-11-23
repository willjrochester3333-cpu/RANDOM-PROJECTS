# Simulation and test report (KESTREL-2)

**Bottom line.** Flown by the real flight code in a 6-DOF simulator, KESTREL-2 on a TSP F35 reaches **188 m** in
calm air with a 25 g payload (Monte Carlo mean **«F35_MEAN» m**, 90 % of flights between «F35_P5» and «F35_P95» m).
It held its roll angle to within «F35_ROLL95»° and the launch direction to within «F35_TILT95»° during the burn
(95th percentile). It released the parachute within «DEP_WINDOW» s of apogee and landed at about «LAND_MEAN» m/s in
**«MC_OK» of «MC_N» randomised flights** (F35, and the E20 and D20 test motors in their 24 mm adapter).
**«SC_PASS» of «SC_GRADED» graded scenario and fault cases pass.** An independent simulator (RocketPy) agrees within
«RP_WORST» %.

You asked for 200 m. With the airframe exactly as it is, the 29 mm F35 gives 188 m (198 m with an empty payload
bay); section 3 shows what the last metres would cost. The price of the height is drift: under its parachute the
rocket comes down for about 40 s, so it lands «F35_DRIFT_MEAN» m from the pad on average and up to «F35_DRIFTMAX» m
in winds up to 6 m/s.

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

«RP_TABLE»

Every quantity agrees within «RP_WORST» %. This checks the flight mechanics; the drag and mass inputs are checked in
section 3 and by real flights.

## 3. Apogee: from the ~123 m estimate to 188 m

When we chose the motor I estimated about 123 m on the 24 mm TSP E20 for a rocket of about 650 g. The finished
rocket weighs about 830 g, and the E20 is rated at 36 Ns rather than the 40 Ns of its test curve, so on the E20 it
reached only 57 m. You then asked for 200 m. No 24 mm TSP motor gets close: even 100 g lighter the E20 would reach
about 77 m. TSP's 29 mm **F35** (65 Ns, 92 g) does, so the TVC module now takes 29 mm motors:

- **Mass.** **856 g** at lift-off with the F35 and 25 g of payload (831 g with an empty bay, 881 g with 50 g). The
  F35 is 28 g heavier than the E20; the 29 mm module itself is only about 3 g heavier (bigger holder and ring,
  frame slightly lighter).
- **Stability.** +0.69 to +0.82 calibres at lift-off (empty to full bay), +0.90 to +1.03 at burn-out, with the
  same 33 g of nose ballast: lower than on the E20 (+0.84 … +0.97) because the heavier motor sits at the tail, but
  still positive with every steering servo dead (section 4, `passive_*`).
- **Speed.** 55.5 m/s at burn-out instead of 25 m/s: about 1.9 kPa of dynamic pressure, five times the E20's
  (section 6b checks the tab servos and the fins for it). It leaves a 1 m rod at 10 m/s instead of 6.8 m/s.

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

| Change | F35 apogee |
|---|---|
| **as designed** (rated 65 Ns, 25 g payload, 36 in chute) | **188.3 m** |
| empty payload bay / maximum 50 g payload | 197.6 m / 179.4 m |
| F35 delivering its published test curve (67 Ns) | 195.5 m |
| without the nose ballast (33 g lighter, but then only +0.33 calibres: not recommended) | 200.6 m |
| 50 g lighter / 100 g lighter | 207.2 m / 227.7 m |
| 20 % less drag | 196.0 m |
| TSP E20 / D20 in the 24 mm adapter (the test flights) | 53.3 m / 18.9 m |

So 200 m needs the rocket about 35 g lighter, an empty bay on a motor that performs a little above its rating, or
both. Each 10 g saved is now worth about 4 m; drag matters more than on the E20 (20 % less drag is 8 m) but still
much less than mass.

## 4. Scenario and fault-injection suite

`sim/scenarios.py`: «SC_N» deterministic cases, each flying the real flight code
(all results: `sim/results/scenarios.md`; plots: `sim/results/scenario_*.png`).

Pass criteria for normal flights: tilt during the burn < 10°, roll rate during the burn < 60 °/s (the tabs hold
roll), parachute released within 1.5 s of true apogee at < 15 m/s, landing < 7 m/s, firmware reaches LANDED.
Fault cases must end with a parachute and a landing below 7 m/s; the jammed-TVC case must also stay near the pad.

«SCENARIO_TABLE»

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

«MC_TABLE»

![Apogee against payload](../sim/results/montecarlo_payload.png)

«MC_NOTES»

Run time: about «MC_MIN» minutes on 4 CPU cores.

### Stress Monte Carlo: where the margins end

`sim/stress_montecarlo.py` flies 1000 more F35 flights with every error source about **twice as wide** as above
(thrust misalignment, mass, CG, drag, fin lift, gyro and accelerometer bias, servo trim and speed, tab
effectiveness 0.4–1.6, parachute Cd and fill time) and wind **0–9 m/s**, using the documented launch procedure
(1.5 m rod above 3 m/s):

«STRESS_TABLE»

«STRESS_NOTES»

## 6. What the fin tabs do

With the tabs switched off (`tabs_disabled`) the F35 rocket rolls at 258 °/s during the burn and 304 °/s in the
coast: fine for the flight, useless for the camera. With the tabs it holds its roll angle to within «F35_ROLL95»°
(95 %) and tilts less in the coast (1.1° instead of 18.8° in the baseline wind). They also steer on their own if the
TVC fails, and `rollprog` turns the coast into a slow camera panorama.

![tabs switched off](../sim/results/scenario_tabs_disabled.png)

## 6b. Hand checks of the final design

Things the simulator does not cover, checked by hand for the final fins, the F35 and the recovery set-up:

| Check | Result | Margin / what to do |
|---|---|---|
| Tab hinge moment against the MG90S (1.8 kgf·cm stall at 4.8 V, [datasheet](https://cdn.shopify.com/s/files/1/1509/1638/files/MG90S_Micro_Servo_Datenblatt_AZ-Delivery_Vertriebs_GmbH.pdf)) | at most 0.15 kgf·cm at the F35's 55.5 m/s (1.86 kPa) with a full 15° of tab, taking the whole tab-induced force (q × 22.9 cm² × δ) at the middle of the 27 mm behind the hinge | 12× (8× with tabs 40 % more effective than modelled) |
| Fin flutter (NACA TN 4197 estimate for the thin 4 mm part of the fin: root chord 110 mm, tip 60 mm, span 50 mm, sea level) | flutter speed at least 450 m/s even with a deliberately low shear modulus of 0.3 GPa for printed PETG | 8× the F35's top speed; the low aspect ratio (0.6) and the 15 mm band at the root make these fins very stiff |
| TVC pivots and servos | the F35's peak thrust (55 N on its test curve) passes through the gimbal pivot, so the servos carry only friction and the motor's inertia; the two M3 pivots each carry about 28 N | large |
| Acceleration | 6.0 g peak at lift-off (F35), 1.8 g when the parachute opens at apogee | the 50 g payload weighs about 0.3 kg-force in the boost: screw it to the bay floor |
| Tab servo speed | the simulator uses the datasheet's 0.10 s/60° (4.8 V) | matches |
| Tab effectiveness | 0.45 assumed (simulator and firmware agree); thin-aerofoil flap theory says the final, longer tab is about 20 % more effective | inside the ±40 % the scenarios test; `sim/mc_tab_effectiveness.py` flies 200 F35 Monte Carlo flights with it centred 20 % higher: «TABEFF_OK» / 200 succeed |
| Fin root, sideways load on a foot | section modulus ≈ 1900 mm³ (the 15 mm band carries it) | about 1 kN at the foot |
| Leg, where it leaves the band (12 × 15 mm, stress across the print layers) | about 225 N sideways or 180 N radially at the foot | the weakest structural point: land on grass and check the legs and the thin tab edges after every flight (the fin can and tabs reprint) |
| Spring ejection | 32.5 N packed, 0.41 J stored; 126 g to move (nose, ballast, 36 in chute, cord, piston): ideal separation 2.5 m/s | test A13 (10 of 10 ground ejections) is the real check; see the note there if separations are slow |

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
| Passive-flight scenarios | with every steering servo dead the rocket is safe in 3 m/s but not in 6 m/s on the small motors | wind limit 3 m/s for flights 1–3; 1.5 m rod above 3 m/s |
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

## 8. The launch video

`sim/results/video/kestrel2_flight_seed7.mp4` («VID_WIND» m/s wind, «VID_PAYLOAD» g payload, F35, apogee
«VID_APOGEE» m) is a randomised flight from the same simulator with the real flight code, rendered in Blender with
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
and the JLCPCB part rotations (checked visually at ordering). Compare every flight log with the simulation
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
