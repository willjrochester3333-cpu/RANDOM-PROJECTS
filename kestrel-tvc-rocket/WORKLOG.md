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
