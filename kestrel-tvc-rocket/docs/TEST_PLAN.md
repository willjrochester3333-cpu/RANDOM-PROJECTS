# Test plan: from the bench to the first F35 flight

The simulator has flown KESTREL-2 more than a thousand times with the real flight code in the loop (see
[SIMULATION_REPORT.md](SIMULATION_REPORT.md)). The real rocket still has to prove that it matches the model. Work
through these tests in order and **do not skip a failed one**. Most rocketry failures are recovery failures,
which is why so much of this plan is about the parachute latch.

Keep a notebook: date, test, result, battery voltage, firmware version (`status` prints it).

## A. Bench tests (indoors)

| # | Test | How | Pass when |
|---|---|---|---|
| A1 | Power and sensors | USB, then LiPo. `status` | IMU, baro, flash `ok`; battery reading within 0.1 V of a multimeter; servo rail 4.8–5.2 V |
| A2 | IMU axes | `calaxes` (two poses), `save`, then `status` with the rocket standing on its fins | body accel ≈ +9.8 m/s² on x, < 0.5 on y and z; pad tilt < 2° |
| A3 | Barometer | `status` 10 times over a minute; then lift the rocket 2 m | altitude noise ±0.3 m; reads +2 m (±0.5) |
| A4 | Static ports | cover the 3 ports with tape, then uncover | pressure reading follows (the av-bay must not be sealed anywhere else) |
| A5 | TVC direction | `dirtest` | servo 1: nozzle swings away from the camera pod; servo 2: away from the door side |
| A6 | TVC centre and travel | `center`, then `servo 1 1400` / `1600`, same for servo 2 | motor hangs straight at centre; full travel without binding or touching the frame; both pushrods clear of the holder all the way round |
| A7 | TVC closed loop | `tvctest`, tilt the rocket by hand ~10° each way | nozzle swings opposite to the lean, smoothly, no buzzing; returns to centre when held still |
| A8 | Tab direction | `tabtest` | seen from behind (nozzle towards you), each tab's trailing edge swings **anticlockwise**, towards the fin with the next-lower number; tabs 1 → 4 in order (fin 1 has the pip) |
| A9 | Tab centre and travel | `center`; then `servo 4` … `servo 7` at 1343 and 1657 µs (= ±15° of tab: the servo turns the tab directly) | every tab lines up with its fin at centre; ±15° of tab without the tab touching the fin; no slop you can feel at the trailing edge; the root pin stays in its slot |
| A10 | Fin tabs closed loop | `fintest`: hold the rocket upright and still for 2 s, then twist it, then tilt it | twist: all four tabs swing the same way to twist it back; tilt: the tabs push the nose back up; no chatter |
| A11 | Payload door | open and close 20 times with a coin; with the door locked, push 50 g against it from inside | quarter turn opens and locks it; locked door does not move; door flush with the tube |
| A12 | Latch hold | board on (latch locked), parachute packed as for flight, nose cone pushed on | the bolt **clicks** in by hand pressure; the nose stays on for 30 min against the packed spring (about 33 N pushes on the bolt), and when you hold the rocket nose-down and give it a sharp shake |
| A13 | **Parachute ejection, × 10** | packed exactly as for flight, **ballast already in the nose**; `deploy release` | 10 / 10 clean separations: nose cone thrown clear, parachute out of the tube, piston still in the tube, no snag on the release lead. The ballast and the 36 in chute leave the spring 50 % more to throw than in earlier versions: if the nose comes off slowly, sand the inside of its sleeve until it slides off the unlatched insert under its own weight, and repack the chute a little looser |
| A14 | Pad endurance | full LiPo, rocket READY on the bench for 60 min with GPS on | stays READY, battery > 7.4 V at the end, no warnings |
| A15 | Logging | after A14: `dump` via `kestrel_link.py`, then `plot` | log complete, no CRC failures, GPS fix logged |
| A16 | Camera | record 5 min in the pod, review | lens clear, body and one or two fins at the edge of the frame, file plays |
| A17 | Balance | F35 (or a dummy of the same mass, 92 g), packed parachute, your payload; once with the **bay empty** to set the nose ballast | balance point ≤ 640 mm from the nose tip (BUILD_GUIDE §12) |
| A18 | 24 mm adapter | sleeve in the holder, an E20 (and a D20 with the spacer) pushed in, 24 mm retainer clicked on; turn the rocket nose-down and shake | the motor cannot slide (D20: spacer + motor fill the bore), the retainer stays locked; the F35 retainer is put away |

## B. Field tests (no motor)

| # | Test | Pass when |
|---|---|---|
| B1 | GPS cold start in the open | fix within 3 min, position within ~5 m of a phone |
| B2 | Pad set-up | rod vertical (spirit level), rocket stands on its four fin feet on the tile, slides freely on the rod |
| B3 | Full countdown rehearsal: pack, power on in the pad position, wait for READY (double chirp), step back, wait 10 min | READY all the time, no red LED |
| B4 | Recovery rehearsal: walk out 150 m and find the rocket by the landing beeps | audible at 30 m+ in wind |

## C. Flight programme

Fly at a club launch or with the landowner's permission. **Wind 3 m/s or less for flights 1–3**: on the small
test motors KESTREL-2 leaves a 1 m rod at only about 7 m/s, and they are the flights that prove the steering.
Once flights 1–3 have shown that the steering works, the F35 may fly in up to 6 m/s with the **1.5 m rod**;
never above 9 m/s. **The F35 flies about 190 m high and drifts a long way under the parachute** (about 170 m in
a 3 m/s wind and 340 m in 6 m/s in the simulator), so the size of the recovery area, not the rocket, usually
sets the wind limit for an F35 flight.

| Flight | Motor | Settings | Why | Simulated apogee | Go to the next flight when |
|---|---|---|---|---|---|
| 1 | TSP D20-0 in the 24 mm adapter (`motor 0`) | `tabs 0` (TVC only) | proves launch detect, TVC, apogee detection, latch, parachute, landing and logging, with as few active parts as possible | ≈ 19 m | deploy within 1 s of apogee; tilt in boost < 10°; rocket undamaged; the log matches the simulation (`kestrel_link.py plot`) |
| 2 | TSP D20-0 in the adapter | `tabs 1` | first flight with the fin tabs: roll hold and coast steering | ≈ 19 m | as flight 1, plus roll rate in boost < 60 °/s and no tab oscillation in the log |
| 3 | TSP E20-0 in the adapter (`motor 2`) | `tabs 1` | a full 2 s burn with steering, to about 53 m, before the big motor | ≈ 53 m | as flight 2 |
| 4+ | **TSP F35-0** (`motor 5`, F35 retainer) | `tabs 1` | **the mission** | **188 m** nominal; Monte Carlo «F35_P5»–«F35_P95» m (5–95 %) | |

Recovery area: at least «F35_AREA» m clear downwind for an F35 (simulated 95th-percentile drift «F35_DRIFT95» m,
farthest «F35_DRIFTMAX» m, in winds up to 6 m/s; less wind, less drift), «E20_AREA» m for an E20 and «D20_AREA» m for
a D20.

After every flight: download and plot the log, compare apogee, deploy time, tilt and roll with the simulation,
check the gimbal pivots, the tab hinges and the latch for wear, recharge, `status` before packing again.

## D. Things that must stop a launch

- Red LED fast blinking (ERROR), or slow blinking (warning) that you cannot explain.
- No double chirp (not READY) after 30 s on the pad.
- The latch bolt did not click when the nose went on.
- Any failed ejection test since the last change to the recovery system.
- Any bench test A5–A10 failed since the last change to a servo, horn, pushrod or tab.
- The motor selected with `motor` is not the one in the rocket (F35 = `motor 5`, E20 = `motor 2`, D20 = `motor 0`),
  or a 24 mm motor is loaded without its sleeve and 24 mm retainer.
- Wind above the limit for this flight (3 m/s for flights 1–3, 6 m/s afterwards, 9 m/s ever), or gusts you
  would not fly a kite in; or more wind than the recovery area allows (F35: about 60 m of drift for every 1 m/s
  of wind).
- People, livestock, power lines or buildings inside the recovery area.
