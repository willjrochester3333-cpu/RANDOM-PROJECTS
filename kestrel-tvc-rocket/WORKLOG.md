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
| R14 | Motor: **TSP E20** (~123 m with all features). TSP allowed as the one brand exception | Q&A |
| R15 | Shopping list: mostly Amazon UK; UK or large international brands, except unbranded servos, camera, parachute (~£270) | Q&A |

## Plan / status

- [x] 1. design.json: new layout (3 parts, 4 fins + legs + tabs, payload, release latch at top, Overlander 350 mAh, spring)
- [x] 2. Simulator: 4 fins with control tabs (aero + servo model), new mass model
- [x] 3. Flight core: fin-tab controller (roll in all phases, pitch/yaw in boost+coast), log format, SIL bridge, unit tests
- [x] 4. Tune + scenarios (incl. tab faults) + big Monte Carlo + graphs
- [x] 5. PCB v2: 7 servo outputs (GP2, GP13, GP15 freed), DRC, fab files, mech export
- [x] 6. Pico firmware: 7 servos, tab mixing, bench tests, rebuild UF2, host tests
- [x] 7. CAD: bottom part, coupler, middle part (payload bay + door + lock, wall, spring/piston, parachute, top latch + release servo), nose cone, pad; checks
- [x] 8. Separate TVC module .blend (2 wires out the top); parachute-open .blend
- [ ] 9. Video render (final, rated motor model) — running
- [x] 10. Shopping list with real prices/links
- [x] 11. Docs rewritten for KESTREL-2 (README, build guide, test plan, checklist, safety, simulation report, PCB, firmware, BOM)
- [ ] 12. Test-and-adjust loop until the deadline (final renders, final regression run)

## Known gaps against the agreed requirements (report them)

- R14 apogee: ~123 m was my estimate at ~650 g on the 40 Ns curve. Finished rocket 721 g, E20 rated 36 Ns: 78 m
  nominal (MC mean 83 m); 94.6 m on the curve basis. Mass is the lever (10 g ≈ 2.5 m); pods only cost ~2 m.
  TSP F35 (29 mm) would give ~226 m but needs a 29 mm TVC module -> user's decision.
- R15 budget: ≈ £297 vs ~£270 (4 more servos, 30 in chute, spring pack of 10).

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

