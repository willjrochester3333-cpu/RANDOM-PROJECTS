# KESTREL rebuild: work log

Deliver between **15:30 and 16:00 GMT, Mon 23 Nov 2026**. Keep testing and adjusting until then.

## Agreed requirements (everything must be in the final rocket)

| # | Requirement | Source |
|---|---|---|
| R1 | Model rocket with 2-axis thrust vector control (TVC), ~1 m tall, reusable, modifiable | original brief |
| R2 | Parachute released at apogee, gentle landing | original brief |
| R3 | One camera pointing down (onboard footage) | original brief |
| R4 | Custom KiCad PCB with GPS, gyroscope (IMU) and barometer; **no soldering anywhere** | original brief |
| R5 | Blender 3D design; custom launch pad | original brief |
| R6 | Lots of testing, simulations, trial and error; plotted on graphs | original + follow-up |
| R7 | Three parts: (1) bottom = TVC + flight computer + all other electronics; (2) middle = two sections split by a wall: **top = parachute**, **bottom = payload bay with a small door that opens and locks**; (3) printed nose cone that pops off to release the parachute | follow-up 1 |
| R8 | Payload up to **50 g** | Q&A |
| R9 | Parachute release servo **at the top**, under the nose cone, cable down the inside wall to the flight computer | Q&A |
| R10 | Separate file for the TVC module with the **two servo wires coming out of the top**; easy to assemble | follow-up 1 |
| R11 | Model of the rocket with the **parachute open** | follow-up 1 |
| R12 | Video of a simulated launch: ground camera + onboard camera, data bottom-left, graphs below; every launch different (seeded) | follow-up 1/2 |
| R13 | **4 fins that the rocket can stand on**, each with a **control tab** so the rocket can be controlled in every axis (roll, pitch, yaw) | follow-up 2 |
| R14 | Motor: **TSP F35** (29 mm), about 190 m, airframe as it is (was TSP E20 / ~123 m until Mon 17:50). TSP allowed as the one brand exception | Q&A, Mon 17:50 |
| R15 | Shopping list: mostly Amazon UK; UK or large international brands, except unbranded servos, camera, parachute (~£270) | Q&A |
| R16 | Ground screen that runs live during the flight: everything about the rocket (parachute out, apogee reached…), a 3D map of where it is, and the 3D movement saved for replay | Mon 19:20 |
| R17 | **A multiple-flight rocket** ("that is its purpose"): replaceable legs (user prints them in extra-tough PLA), stronger servo housings, battery out and USB without taking the rocket apart (door with no gaps), full package accepted at ~170 m with 46 g of nose ballast | Wed |

## Plan / status

- [x] 1. design.json: new layout (3 parts, 4 fins + legs + tabs, payload, release latch at top, Overlander 350 mAh, spring)
- [x] 2. Simulator: 4 fins with control tabs (aero + servo model), new mass model
- [x] 3. Flight core: fin-tab controller (roll in all phases, pitch/yaw in boost+coast), log format, SIL bridge, unit tests
- [x] 4. Tune + scenarios (incl. tab faults) + big Monte Carlo + graphs
- [x] 5. PCB v2: 7 servo outputs (GP2, GP13, GP15 freed), DRC, fab files, mech export
- [x] 6. Pico firmware: 7 servos, tab mixing, bench tests, rebuild UF2, host tests
- [x] 7. CAD: bottom part, coupler, middle part (payload bay + door + lock, wall, spring/piston, parachute, top latch + release servo), nose cone, pad; checks
- [x] 8. Separate TVC module .blend (2 wires out the top); parachute-open .blend
- [x] 9. Video render (final, rated motor model; re-rendered for the F35, seed 7)
- [x] 10. Shopping list with real prices/links
- [x] 11. Docs rewritten for KESTREL-2 (README, build guide, test plan, checklist, safety, simulation report, PCB, firmware, BOM)
- [ ] 12. Test-and-adjust loop until the deadline (final renders, final regression run)

## Known gaps against the agreed requirements (report them)

- R14 apogee: F35 **170 m** nominal with 25 g payload since the multi-flight changes (R17, user's choice: 48 g of
  legs, tongues, bolts, housings, hatch and ballast; 188 m before). ~190 m would need ~45 g off elsewhere.
- R15 budget: ≈ £317 vs ~£270 (4 more servos, 36 in chute, spring pack of 10, servos inside the fins, multi-flight
  extras ~£5).
- R16 live view: the rocket has **no radio**, so a real flight can only be shown after landing (log over USB);
  live works for the simulated flight and on the USB cable. Needs a telemetry transmitter + receiver and a
  firmware streaming command -> question to the user (which radio).

## Log
- 19:45 GMT Sun: requirements fixed (motor E20). Starting step 1.
- Sun evening–night: steps 1–8 and 10 done (see git log); first Monte Carlo 1000/1000.
- 00:51 Mon: Monte Carlo re-run on the rated-impulse motor basis: 1000/1000, E20 mean 83 m.
- 01:05 Mon: build-guide walk-through found and fixed: tab-servo lead slots too small for a plug (now 4 x 19 mm),
  only 4 of 7 servo headers in the CAD export, release lead routing, R24 GPS bias resistor (now not fitted),
  stale tube note (BT-70 is 19.5 in).
- 01:10 Mon: final video render started (seed 7).
- 01:25 Mon: 6 new scenarios (1.5 m rod, 50 g in 6 m/s, all-steering-dead calm/3 m/s/empty bay/6 m/s):
  40/40 graded pass; passive flight unsafe in 6 m/s -> first-flight wind limit 3 m/s, 1.5 m rod above 3 m/s.
  RocketPy re-validation for KESTREL-2: all within 0.3 %.
- 01:30–01:50 Mon: overhang check added to check_parts.py (every STL in print orientation). Fixed: conical nose
  bulkhead, wall skirt on top, piston/door/frame/knob/insert orientations, coupler nut wedges, GPS platform
  (gusseted, beside the USB socket, U-shaped for the lead), battery-ledge wedge, lug lead-in, camera-pod flange.
  Supports now only for tvc_frame, tvc_motor_holder tab, fin_control_tab, pad_hub.
- 01:45 Mon: new CAD<->design check found TVC linkage 0.50 (CAD) vs 0.42 (firmware/sim) and tab horn 14.3 vs 14.5.
  Fixed in design.json, sim (now reads design.json), firmware 2.01 (settings v4). Tests 377,489 + 125 pass;
  scenarios 40/40; RocketPy within 0.3 %.
- Next: video (old CAD) finishing -> final Monte Carlo -> final CAD renders -> final video re-render -> docs.
- 02:05–02:21 Mon: backup video (seed 7, pre-fix CAD) done; final Monte Carlo 1000/1000 (E20 mean 82.7 m, 64–103 m);
  final CAD renders incl. the TVC assembly-steps view.
- 02:20–07:27 Mon: session worker restarted / idle (nothing lost).
- 07:30 Mon: TVC assembly-steps view re-framed and numbered; all docs updated to the final numbers (77 m nominal,
  723 g, margins 0.70-0.85, MC table, what-ifs, hard-over 19-22 m). Next: test frames, final video, second seed.

- 07:40–08:05 Mon: user asked for thicker fins with the tab servos inside them (no separate pods, no metal rods);
  chose "whole fin ~15 mm thick". CAD: 15 mm fins with half-round LE, servo pocket open at the tip (shaft on the
  hinge line, direct drive), horn stub epoxied into the printed tab, printed root pin in a slot, lead channel +
  tip groove; no pods, pushrods or hinge pins. 27 parts PASS, 1326 pairs no overlap, all sweeps clean.
- 08:10 Mon: build checks: lower servo screw had 4.3 mm of plastic before the tab gap -> blind holes, M2 x 6 mm
  screws; lead channel 4 -> 5 mm (plug is 8 x 4 mm). Firmware 2.02: settings v5, direct-drive tabs (1:1),
  new tabtest wording (TE anticlockwise seen from behind). 376k core + 127 logic checks pass, UF2 rebuilt.
- 08:15 Mon: stability: fin can 181 g (+70 g at the tail) -> margin +0.39 cal. Added 33 g nose ballast (~90 M3
  nuts + epoxy through a 14 mm fill hole in the nose bulkhead): +0.75/+0.82/+0.88 cal (0/25/50 g payload).
- 08:35 Mon: Monte Carlo: E20 99.9 %, D20 98 %. Causes: D20 apogees down to 14 m < 15 m arming height (late
  deploy, 16 m/s landings) and 30 in chute at the new mass (5.8 m/s mean, 2 flights just > 7 m/s).
  Fixes: apogee arming 15 -> 8 m; 36 in Estes rip-stop chute (fill time modelled 20 % longer); sim/whatif.py and
  named drag terms added. Scenarios 40/40, landing 4.9 m/s, E20 nominal 55 m. Monte Carlo re-run.
- 08:40–09:10 Mon: second Monte Carlo after the fixes 1000/1000 (E20 mean 60 m); final CAD renders; video renders
  started, then lost when the session was rate-limited and its worker restarted (09:10–13:00).
- 13:02 Mon: user: "make only the part that needs to be thick that thick, the rest normal, very aerodynamic; thick
  at the bottom". Fins now 4 mm with a half-round LE; only the 45 mm bottom band (tab hinge, servo, lead channel)
  is 15 mm, joined by a 15-degree wedge (shorter near the tip, clear of the LE); tabs and band taper to 1.5 mm
  trailing edges 12 mm below the tail; legs taper to 11 x 7.5 mm feet. All 27 parts PASS, no overlaps, tab sweep
  clean. Fin can 181 -> 165 g, Cd0 0.94 -> 0.85 (new drag terms), margins +0.84..+0.97 cal.
  Scenarios 40/40, E20 57 m. Video render made resumable (frames on disk are kept).
- 13:15 Mon: seed-7 video and the 1000-flight Monte Carlo running.
- 13:36 Mon: Monte Carlo (thin fins + servo band) 1000/1000: E20 mean 62 m (47-79), landing 4.9 m/s, 95 % within
  101 m; RocketPy within 0.3 %; hard-over 18-23 m from the pad (6 seeds); PCB DRC 0/0.
- 14:01 Mon: stress Monte Carlo (2x spreads, wind 0-9 m/s): 99.2 % meet every criterion, 100 % safe recovery; the
  8 misses are 1.1-1.6 deg motor misalignment in 7-9 m/s wind (tilt 10-42 deg in the burn).
- 14:15 Mon: launch video seed 7 rendered with the final CAD (1920x1080, 20.8 s). Delivery 15:30-16:00.
- 15:30 Mon: final delivery summary sent. Then (user: keep testing): doc links (80) all resolve; netlist = circuit.py
  (293 pins, 65 nets), gerber zip CRC OK, DRC 0/0; fresh clone: host build 0 warnings + tests pass, scenarios
  identical, CAD rebuild byte-identical (27 STLs + reports), Pico UF2 byte-identical to the committed one; hand
  checks (tab hinge torque 29-57x vs MG90S, fin root ~1 kN, leg ~225 N sideways, spring ejection 2.5 m/s ideal ->
  A13 note); tabs 21 mm clear of the exhaust plume; example log regenerated (fw 202); 200-flight Monte Carlo with
  tabs 20 % more effective: 200/200.
- 17:15-17:47 Mon: user: a cheaper, lower-resolution camera (to shrink the pod): researched split / spy / FPV cameras;
  questions to the user open (exact listing, receiving device). Video code packaged as a zip (fonts fall back to
  matplotlib's DejaVu, .dylib on macOS, BLENDER env var); clean-copy draft render passed.
- 17:50-18:30 Mon: user: "it should go 200 m high" -> agreed: the airframe as it is on the 29 mm TSP F35 (about 190 m).
  29 mm TVC module: holder/ring +2.5 mm radius, gimbal arms 18 -> 22 mm with round bosses (linkage 0.5 -> 0.4091),
  F35 retainer (22 mm opening), frame window 56 -> 54 mm and bottom ring 24.6 -> 26 mm (the sweep, now with the
  pushrods and horns, found the holder arm and retainer touching at 7 deg), 0.3 mm play above the motor. 24 mm
  adapter set for the D20/E20 test flights (sleeve, 24 mm retainer, 25 mm D spacer: the 70 mm D20 had nothing
  above it in the 95 mm bore before). 30 STLs PASS, 1326 pairs no overlap, 1350 gimbal checks clean.
  Mass 856 g (F35, 25 g payload), margins +0.69..+0.82 cal (lift-off), +0.90..+1.03 (burn-out); F35 188 m.
  Firmware 2.03: F35 = motor 5 (default), settings v6, linkage 0.4091; 376,013 + 128 checks, UF2 0 warnings.
  Hand checks at 55.5 m/s: tab hinge 0.15 kgf.cm (12x), flutter >= 450 m/s (8x). Scenarios 41/41 (+3 info).
- 18:40-19:19 Mon: Monte Carlo 1000/1000 (F35 600: mean 198 m, 164-236 m, drift up to 498 m in 6 m/s and 232 m in
  <= 3 m/s; E20 200: 58 m; D20 200: 20 m). F35 roll held less tightly (p95 17 deg, peak at burn-out, tabs 3-5 deg;
  tab backlash ruled out). Stress Monte Carlo 99.3 % / 100 % safe recovery; tab effectiveness x1.2: 200/200;
  RocketPy within 0.33 % (F35 188.31 vs 188.24 m). Hard-over containment 23-26 m (F35), so spectators 40 m for
  the F35. Docs filled from the results; recovery area 550 m (6 m/s) or 300 m (3 m/s) for the F35.
- 19:20-20:30 Mon: user: a "SUPER cool" live screen with everything about the rocket, a 3D map of where it is, and
  the movement saved for replay -> ground/ Mission Control (three.js r128, one HTML file, offline build 839 kB):
  3D range (10 m grid, 100 m rings, pad, trail coloured by phase, event pins, landing marker), chase / pad /
  orbit / map cameras, event list + banners (liftoff, burnout, apogee, chute, landed, abort), state strip,
  telemetry, nose / gimbal / tab dials, 4 strip charts (hover, click to seek), timeline with event ticks,
  0.25-8x replay, sources: simulated live (real-time), USB (Web Serial; `dump` straight into the replay, live
  lines shown as they come), log files (drag-drop, several sessions); save as log-format CSV, last 12 flights
  kept in the browser. Demo = seed 7 flown by the real flight code incl. 10 s after touchdown (FSW goes LANDED).
  Found: the example-log and demo writers skipped the pad rows (`last = -1.0` vs t = 0) -> fixed, example log
  regenerated (1463 rows, 188.2 m). Tested in headless Chromium (live run to LANDED, replay, seek, load, save,
  flights list, offline file with the network blocked); published as a private claude.ai page.
- Mon 20:30 - Tue 16:30: Mission Control checked against the firmware. Before READY the flight computer's alt_m is
  pressure altitude (p0 is only set at READY), so a replay showed the rocket ~100 m up while calibrating -> the
  screen uses altitude / vertical speed from READY on ("–" before); saved files keep the raw values. USB tested
  against a simulated flight computer (echo, "> " prompts, one header, a session line per flight, one "# end"):
  the page now listens before it sends dump (a fast reply was lost before), strips prompts, shows the in-flight
  "refused: only on the ground" and gives up after 8 s of silence; choosing a downloaded flight no longer closes
  the USB link (a second dump failed), live lines during a replay bring up LIVE, unplugging resets the button.
  F35 launch video rendered (seed 7: 179.3 m, 47.9 s, 1080p; this flight drew a 7.7 % heavier rocket, 867 g
  after burn-out).
