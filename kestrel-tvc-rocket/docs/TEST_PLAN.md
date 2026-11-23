# Test plan: from the bench to the first E20 flight

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
| A6 | TVC centre and travel | `center`, then `servo 1 1400` / `1600`, same for servo 2 | motor hangs straight at centre; full travel without binding or touching the frame |
| A7 | TVC closed loop | `tvctest`, tilt the rocket by hand ~10° each way | nozzle swings opposite to the lean, smoothly, no buzzing; returns to centre when held still |
| A8 | Tab direction | `tabtest` | each tab's trailing edge moves **away from its servo pod**, tabs 1 → 4 in order (fin 1 has the pip) |
| A9 | Tab centre and travel | `center`; then `tabmax 15` and `servo 4` … `servo 7` at 1100 and 1900 µs (= ±15° of tab through the linkage) | every tab lines up with its fin at centre; ±15° of tab without the horn, pushrod or tab touching the pod or fin; no slop you can feel |
| A10 | Fin tabs closed loop | `fintest`: hold the rocket upright and still for 2 s, then twist it, then tilt it | twist: all four tabs swing the same way to twist it back; tilt: the tabs push the nose back up; no chatter |
| A11 | Payload door | open and close 20 times with a coin; with the door locked, push 50 g against it from inside | quarter turn opens and locks it; locked door does not move; door flush with the tube |
| A12 | Latch hold | board on (latch locked), parachute packed as for flight, nose cone pushed on | the bolt **clicks** in by hand pressure; the nose stays on for 30 min against the packed spring (about 33 N pushes on the bolt), and when you hold the rocket nose-down and give it a sharp shake |
| A13 | **Parachute ejection, × 10** | packed exactly as for flight; `deploy release` | 10 / 10 clean separations: nose cone thrown clear, parachute out of the tube, piston still in the tube, no snag on the release lead |
| A14 | Pad endurance | full LiPo, rocket READY on the bench for 60 min with GPS on | stays READY, battery > 7.4 V at the end, no warnings |
| A15 | Logging | after A14: `dump` via `kestrel_link.py`, then `plot` | log complete, no CRC failures, GPS fix logged |
| A16 | Camera | record 5 min in the pod, review | lens clear, body and one or two fins at the edge of the frame, file plays |
| A17 | Balance | E20 (or a dummy of the same mass), packed parachute, your payload | balance point ≤ 640 mm from the nose tip (BUILD_GUIDE §12) |

## B. Field tests (no motor)

| # | Test | Pass when |
|---|---|---|
| B1 | GPS cold start in the open | fix within 3 min, position within ~5 m of a phone |
| B2 | Pad set-up | rod vertical (spirit level), rocket stands on its four fin feet on the tile, slides freely on the rod |
| B3 | Full countdown rehearsal: pack, power on in the pad position, wait for READY (double chirp), step back, wait 10 min | READY all the time, no red LED |
| B4 | Recovery rehearsal: walk out 150 m and find the rocket by the landing beeps | audible at 30 m+ in wind |

## C. Flight programme

Fly at a club launch or with the landowner's permission. **Wind 3 m/s or less for flights 1–3**: in the simulator
even a rocket with every steering servo dead (`passive_wind3`) still flies and recovers normally in 3 m/s, but
not in 6 m/s (`passive_wind6`), because KESTREL-2 leaves a 1 m rod at only about 8 m/s. Once flights 1–3 have shown
that the steering works, fly in up to 6 m/s with the **1.5 m rod**; never above 9 m/s.

| Flight | Motor | Settings | Why | Simulated apogee | Go to the next flight when |
|---|---|---|---|---|---|
| 1 | TSP D20-0 | `tabs 0` (TVC only) | proves launch detect, TVC, apogee detection, latch, parachute, landing and logging, with as few active parts as possible | ≈ 30 m | deploy within 1 s of apogee; tilt in boost < 10°; rocket undamaged; the log matches the simulation (`kestrel_link.py plot`) |
| 2 | TSP D20-0 | `tabs 1` | first flight with the fin tabs: roll hold and coast steering | ≈ 30 m | as flight 1, plus roll rate in boost < 60 °/s and no tab oscillation in the log |
| 3+ | **TSP E20-0** | `tabs 1` | **the mission** | **77 m** nominal; Monte Carlo 64–103 m (5–95 %) | |

Recovery area: at least 200 m clear downwind for an E20 (simulated 95th-percentile drift 133 m in winds up to
6 m/s), 60 m for a D20.

After every flight: download and plot the log, compare apogee, deploy time, tilt and roll with the simulation,
check the gimbal pivots, the tab hinges and the latch for wear, recharge, `status` before packing again.

## D. Things that must stop a launch

- Red LED fast blinking (ERROR), or slow blinking (warning) that you cannot explain.
- No double chirp (not READY) after 30 s on the pad.
- The latch bolt did not click when the nose went on.
- Any failed ejection test since the last change to the recovery system.
- Any bench test A5–A10 failed since the last change to a servo, horn or pushrod.
- Wind above the limit for this flight (3 m/s for flights 1–3, 6 m/s afterwards, 9 m/s ever), or gusts you
  would not fly a kite in.
- People, livestock, power lines or buildings inside the recovery area.
