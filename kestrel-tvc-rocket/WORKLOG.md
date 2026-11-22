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

- [ ] 1. design.json: new layout (3 parts, 4 fins + legs + tabs, payload, release latch at top, Overlander 350 mAh, spring)
- [ ] 2. Simulator: 4 fins with control tabs (aero + servo model), new mass model
- [ ] 3. Flight core: fin-tab controller (roll in all phases, pitch/yaw in boost+coast), log format, SIL bridge, unit tests
- [ ] 4. Tune + scenarios (incl. tab faults) + big Monte Carlo + graphs
- [ ] 5. PCB v2: 7 servo outputs (GP2, GP13, GP15 freed), DRC, fab files, mech export
- [ ] 6. Pico firmware: 7 servos, tab mixing, bench tests, rebuild UF2, host tests
- [ ] 7. CAD: bottom part (fin can, 4 fins/legs, tab pods/servos/tabs, TVC, sled, camera, lugs), mid coupler, middle part (payload bay + door + lock, wall, spring/piston, parachute, top latch ring + release servo), nose cone, pad; checks
- [ ] 8. Separate TVC module .blend (2 wires out the top); parachute-open .blend; renders
- [ ] 9. Video pipeline (EEVEE) + render
- [ ] 10. Shopping list with real prices/links
- [ ] 11. Docs update; commit/push
- [ ] 12. Test-and-adjust loop until the deadline

## Log
- 19:45 GMT Sun: requirements fixed (motor E20). Starting step 1.
