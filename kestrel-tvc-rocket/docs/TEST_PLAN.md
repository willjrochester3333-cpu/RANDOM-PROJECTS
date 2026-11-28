# Test plan: from the bench to the first F35 flight

The simulator has flown KESTREL-2 more than 3,000 times with the real flight code in the loop (see
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
| A5 | TVC direction | `dirtest` | servo 1: nozzle swings away from the camera door; servo 2: away from the door side |
| A6 | TVC centre and travel | `center`, then `servo 1 1400` / `1600`, same for servo 2 | motor hangs straight at centre; full travel without binding or touching the frame; both pushrods clear of the holder all the way round |
| A7 | TVC closed loop | `tvctest`, tilt the rocket by hand ~10° each way | nozzle swings opposite to the lean, smoothly, no buzzing; returns to centre when held still |
| A8 | Tab direction | `tabtest` | seen from behind (nozzle towards you), each tab's trailing edge swings **anticlockwise**, towards the fin with the next-lower number; tabs 1 → 4 in order (fin 1 has the pip) |
| A9 | Tab centre and travel | `center`; then `servo 4` … `servo 7` at 1343 and 1657 µs (= ±15° of tab: the servo turns the tab directly) | every tab lines up with its fin at centre; ±15° of tab without the tab touching the fin; no slop you can feel at the trailing edge; the root pin stays in its slot |
| A10 | Fin tabs closed loop | `fintest`: hold the rocket upright and still for 2 s, then twist it, then tilt it | twist: all four tabs swing the same way to twist it back; tilt: the tabs push the nose back up; no chatter |
| A11 | Payload door | open and close 20 times with a coin; with the door locked, push 50 g against it from inside | quarter turn opens and locks it; locked door does not move; door flush with the tube |
| A12 | Latch hold | board on (latch locked), parachute packed as for flight, nose cone pushed on | the bolt **clicks** in by hand pressure; the nose stays on for 30 min against the packed spring (about 33 N pushes on the bolt), and when you hold the rocket nose-down and give it a sharp shake |
| A13 | **Parachute ejection, × 10** | packed exactly as for flight, **ballast already in the nose**; `deploy release` | 10 / 10 clean separations: nose cone thrown clear, parachute out of the tube, piston still in the tube, no snag on the release lead. The ballast and the 36 in chute leave the spring about 65 % more to throw than in earlier versions: if the nose comes off slowly, sand the inside of its sleeve until it slides off the unlatched insert under its own weight, and repack the chute a little looser |
| A14 | Pad endurance | full LiPo, rocket READY on the bench for 60 min with GPS on | stays READY, battery > 7.4 V at the end, no warnings |
| A15 | Logging | after A14: `dump` via `kestrel_link.py`, then `plot` | log complete, no CRC failures, GPS fix logged |
| A16 | Camera | record 5 min in its cradle behind the closed camera door, review | the picture looks out and down (30°) with no dark edge from the door's port or brow; the camera does not rattle when you shake the rocket; the file plays |
| A17 | Balance | F35 (or a dummy of the same mass, 92 g), packed parachute, your payload; once with the **bay empty** to set the nose ballast | balance point ≤ 640 mm from the nose tip (BUILD_GUIDE §12) |
| A18 | 24 mm adapter | sleeve in the holder, an E20 (and a D20 with the spacer) pushed in, 24 mm retainer clicked on; turn the rocket nose-down and shake | the motor cannot slide (D20: spacer + motor fill the bore), the retainer stays locked; the F35 retainer is put away |
| A19 | **Leg break test** (two **spare** legs and `tool_leg_test_block`) | clamp the block in a vice, slide a spare leg onto its tongue and bolt it as on the rocket; pull at the foot with a luggage scale, at right angles to the leg, until it breaks: the first leg **outward** (along the span), the second **sideways** (across the fin) | it breaks **at the top of the post** at about **7.5 kg outward** and **11.5 kg sideways**. Anything from 4 to 10 kg outward and 6 to 16 kg sideways is fine. **Stronger than 10 / 16 kg: do not fly legs from that print** (they could crack the fin can's servo housing before breaking): reduce `fins.leg.post_mm` in `design.json` by 10 %, rebuild the CAD and test again. Weaker than 4 / 6 kg: poor layer bonding, print them hotter and slower |
| A20 | **Drop test** | the complete rocket as it lands: battery in, hatch shut, parachute packed, nose on, a 49 g dummy in the motor bore (a spent F35 case weighs about 49 g); hold it upright by the nose and drop it **feet-first from 1.4 m** (= the 5.2 m/s landing) onto grass, 5 times; then 5 times tilted 20° | no crack anywhere on the fin can, its servo housings or the tabs; `center` still lines the tabs up; the hatch still shut. A tilted drop may break a leg: that is what the legs are for (swap it and note it) |
| A21 | **Battery hatch** | fit and remove the door 10 times and swap the pack; slide the rocket along the whole launch rod with the door shut; with the door open, `status` over USB through the hatch with the angled cable | the door lies flat with no visible gap and does not rattle when locked; a pack swap takes under a minute without tools; the rod passes the door without touching it; USB works through the hatch. Do A4 again with the door shut: the hatch must not leak |
| A22 | **Radio set-up** | each radio in turn on the laptop's USB: Mission Control → Radio link → **Set up a radio (UK settings)…** | the table it shows after the restart reads network ID **75** and transmit power **8** on **both** radios |
| A23 | **Radio link** (bench) | rocket READY on the bench, ground radio on the laptop, Mission Control → **Connect radio**; 10 min; then `radio test` over USB | frames arrive once a second with **0 lost** in 10 min, "At the rocket: hears this station"; `radio` (USB) shows the ground station heard. During `radio test`: about 55 frames a second, under 2 % lost, and the Airtime line rises by about 29 s |
| A24 | **Camera door** | fit and remove the door 10 times with the camera in, then shake the rocket | the door locks with a quarter turn, sits flat on the tube with no gap and does not rattle; the camera stays put; only the low brow over the lens stands out (about 5 mm) |

## B. Field tests (no motor)

| # | Test | Pass when |
|---|---|---|
| B1 | GPS cold start in the open | fix within 3 min, position within ~5 m of a phone |
| B2 | Pad set-up | rod vertical (spirit level), rocket stands on its four fin feet on the tile, slides freely on the rod |
| B3 | Full countdown rehearsal: pack, power on in the pad position, wait for READY (double chirp), step back, wait 10 min | READY all the time, no red LED |
| B4 | Recovery rehearsal: walk out 150 m and find the rocket by the landing beeps | audible at 30 m+ in wind |
| B5 | **Radio range**: rocket READY standing on its pad (antenna upright), ground radio's antenna upright at head height. Type `radio test` (60 s at the flight rate) and walk away with the laptop, to the far edge of the recovery area for the next flight (500 m for an F35, 150 m for an E20); repeat `radio test` if the minute runs out. At most three tests in the hour before a flight: each uses about 29 s of the rocket's 360 s of airtime an hour | frames still arrive with under 10 % lost at that distance. If not, hold the ground radio up on a 2 m pole and repeat; this is the worst case, rocket and laptop both near the ground, and in flight the rocket is high up |
| B6 | Landing prediction: before a flight, type the wind (speed, and the direction it comes from) into Mission Control's Landing prediction panel | the predicted landing point and search ring fall inside the recovery area |

## C. Flight programme

Fly at a club launch or with the landowner's permission. **Wind 3 m/s or less for flights 1 and 2**: on the E20
KESTREL-2 leaves a 1 m rod at only about 6 m/s, and they are the flights that prove the steering. Once flights 1 and
2 have shown that the steering works, the F35 may fly in up to 6 m/s with the **1.5 m rod**; never above 9 m/s.
**The F35 flies about 157 m high and drifts a long way under the parachute** (about 135 m in a 3 m/s wind and
276 m in 6 m/s in the simulator), so the size of the recovery area, not the rocket, usually sets the wind limit
for an F35 flight.

**Why the E20 first (and not the smaller D20):** the first flights should prove everything with a parachute that has
time to open properly. On the E20 the rocket reaches about 47 m (no payload; 36 m in the worst 5 % of 300 simulated
first flights), the canopy is fully open at about 40 m (28 m in the worst 5 %, never below 18 m) and it then hangs
under the open canopy for about 7.5 s (never under 3.4 s): 600 of 600 simulated first and second flights landed
normally. A D20 only reaches about 14 m: the canopy would open with only a few metres to spare.

| Flight | Motor | Settings | Why | Simulated apogee | Go to the next flight when |
|---|---|---|---|---|---|
| 1 | TSP E20-0 in the 24 mm adapter (`motor 2`), **no payload** | `tabs 0` (TVC only) | proves launch detect, TVC, apogee detection, latch, parachute, landing, logging and the live radio, with as few active parts as possible | ≈ 47 m (36–60 m) | deploy within 1 s of apogee; tilt in boost < 10°; rocket undamaged; the log matches the simulation (`kestrel_link.py plot`); Mission Control showed the flight live and merged the full log afterwards |
| 2 | TSP E20-0 in the adapter, no payload | `tabs 1` | first flight with the fin tabs: roll hold and coast steering | ≈ 47 m | as flight 1, plus roll rate in boost < 60 °/s and no tab oscillation in the log |
| 3+ | **TSP F35-0** (`motor 5`, F35 retainer) | `tabs 1` | **the mission** | **157 m** nominal (calm, 25 g payload); Monte Carlo 135–200 m (5–95 %) | |

(The ranges are the 5th to 95th percentiles of the simulated flights; flight 1 in the simulator spins slowly in
roll with the tabs off, up to about 140 °/s in boost, which the TVC handles.)

Recovery area: at least 500 m clear downwind for an F35 in winds up to 6 m/s (simulated 95th-percentile drift
282 m, farthest 432 m), or 250 m if you fly it only in 3 m/s or less (farthest 183 m); 150 m for an E20 (up to
6 m/s: 95th percentile 67 m, farthest 101 m; flights 1–2 in 3 m/s or less: farthest 68 m) and 50 m for a D20.
Mission Control's landing prediction shows where it is heading during the flight.

After every flight: download and plot the log (USB through the battery hatch; in Mission Control **Get log over USB**
merges it with the radio recording), compare apogee, deploy time, tilt and roll with the simulation, check the gimbal pivots, the tab hinges and the latch for wear, look for cracks at the
top of each leg's post and round each fin tip (the servo housing), swap a cracked leg, swap in a charged pack,
`status` before packing again. A leg that broke on landing did its job; a crack in a servo housing did not: stop
and repair the fin can before flying again.

## D. Things that must stop a launch

- Red LED fast blinking (ERROR), or slow blinking (warning) that you cannot explain.
- No double chirp (not READY) after 30 s on the pad.
- The latch bolt did not click when the nose went on.
- Any failed ejection test since the last change to the recovery system.
- Any bench test A5–A10 failed since the last change to a servo, horn, pushrod or tab.
- The motor selected with `motor` is not the one in the rocket (F35 = `motor 5`, E20 = `motor 2`, D20 = `motor 0`),
  or a 24 mm motor is loaded without its sleeve and 24 mm retainer.
- Camera door not latched (coin slot not horizontal).
- Wind above the limit for this flight (3 m/s for flights 1 and 2, 6 m/s afterwards, 9 m/s ever), or gusts you
  would not fly a kite in; or more wind than the recovery area allows (F35: about 46 m of drift for every 1 m/s
  of wind).
- (Not a stop on its own: no radio link. The flight computer logs everything to its own memory whatever the radio
  does, and nothing the radio receives changes the flight.)
- People, livestock, power lines or buildings inside the recovery area.
