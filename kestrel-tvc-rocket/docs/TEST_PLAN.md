# Test plan: from bench to 200 m

The simulator has already flown the design more than a thousand times (see
[SIMULATION_REPORT.md](SIMULATION_REPORT.md)). The real rocket still has to prove that it matches the model. Work
through these tests in order and **do not skip a failed one**. Most rocketry failures are recovery failures,
which is why half of this plan is about the parachute.

Keep a notebook: date, test, result, battery voltage, firmware version.

## A. Bench tests (indoors)

| # | Test | How | Pass when |
|---|---|---|---|
| A1 | Power and sensors | USB, then LiPo. `status` | IMU, baro, flash `ok`; battery reading within 0.1 V of a multimeter; servo rail 4.8–5.2 V |
| A2 | IMU axes | `calaxes` (two poses), `save`, then `status` standing upright | body accel ≈ +9.8 m/s² on x, < 0.5 on y/z; pad tilt < 2° |
| A3 | Barometer | `status` 10 times over a minute; then lift the rocket 2 m | altitude noise ±0.3 m; reads +2 m (±0.5) |
| A4 | Static ports | cover the 3 ports with tape, then uncover | pressure reading follows (it must not be sealed elsewhere) |
| A5 | TVC direction | `dirtest` | nozzle swings away from the camera pod (servo 1), away from fin #1 (servo 2) |
| A6 | TVC centre and travel | `center`, then `servo 1 1400` / `1600`, same for servo 2 | motor hangs straight; full travel without binding or contact |
| A7 | TVC closed loop | `tvctest`, tilt by hand ~10° each way | nozzle swings opposite to the lean, smoothly, no buzzing; returns to centre when held still |
| A8 | Snap-in and latch hold | power on (latch locked), push the upper section on; then hang 2 kg (or pull with a luggage scale) from the nose | both bolts click in by hand pressure alone; upper section stays on under 2 kg (≈ 4× the inertial and drag loads) |
| A9 | **Parachute ejection, ×10** | packed exactly as for flight; `deploy release` | 10 / 10 clean separations, nose + upper tube thrown ≥ 30 cm, chute out of the tube, no snag |
| A10 | Pad endurance | full LiPo, rocket READY on the bench for 60 min with GPS on | stays READY, battery > 7.4 V at the end, no warnings |
| A11 | Logging | after A10: `dump` via `kestrel_link.py`, then `plot` | log complete, no CRC failures, GPS fix logged |
| A12 | Camera | record 5 min, review | lens clear, body edge visible at one side of the frame, file plays |
| A13 | Balance | motor (or a dummy with the same mass) + packed chute | balance point ≤ 600 mm from the nose tip |

## B. Field tests (no motor)

| # | Test | Pass when |
|---|---|---|
| B1 | GPS cold start in the open | fix within 3 min, position within ~5 m of a phone |
| B2 | Pad set-up | rod vertical with a spirit level, rocket slides freely on the rod, nozzle 45 mm above the plate |
| B3 | Full countdown rehearsal: pack, power on in the pad position, READY double chirp, step back, wait 10 min | READY all the time, no red LED |
| B4 | Recovery rehearsal: walk out to 150 m and find the rocket by the landing beeps | audible at 30 m+ in wind |

## C. Flight programme

Fly at a club launch or with landowner permission, wind below 6 m/s for the first flights, a clear field of
≥ 300 m downwind for E20 (simulated 95th-percentile drift 314 m).

| Flight | Motor | Why | Simulated apogee | Go to the next step when |
|---|---|---|---|---|
| 1 | TSP D20-0 | short, low (82 m): proves launch detect, TVC, apogee detect, parachute, landing, logs | 82 m | deploy within 1 s of apogee; tilt in boost < 10°; rocket undamaged |
| 2 | TSP E12-0 | 3.5 s burn = the longest TVC test; still modest height | 161 m | logged tilt < 10°, gimbal never at its limit for long, logs match the sim (`kestrel_link.py plot`) |
| 3+ | **TSP E20-0** | **the 200 m mission** | **197 m** (90 % of simulated flights 170–228 m) | |

After every flight: download and plot the log, compare apogee, deploy time and tilt with the simulation, check
the gimbal pivots and latch for wear, recharge, `status` before packing again.

## D. Things that must stop a launch

- Red LED fast blinking (ERROR) or slow blinking (warning) that you cannot explain.
- No double chirp (not READY) after 30 s on the pad.
- Any ejection-test failure since the last change to the recovery system.
- Wind above 9 m/s (the limit tested in the simulator) or gusts you would not fly a kite in.
- People, livestock, power lines or buildings inside the recovery area.
