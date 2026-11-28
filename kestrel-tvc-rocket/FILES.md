# Every file in the KESTREL-2 project, and what it is

Start with **README.md** (what the rocket is and how well it works), then **docs/BUILD_GUIDE.md** (how to build it).
Files marked *(generated)* are made by a script in this project: change the script or `design.json`, not the file.

## Top level

| File | What it is |
|---|---|
| `README.md` | Overview: what KESTREL-2 is, key numbers (170 m on a TSP F35), how it was checked, where everything is |
| `FILES.md` | This list |
| `WORKLOG.md` | Diary of the design work: every change, what was found and fixed, with times |
| `design.json` | **The master parameter file**: every dimension, mass and setting of the rocket (airframe, fins, tabs, TVC, recovery, payload, motors, component masses). The CAD, simulator and firmware all read it |
| `.gitignore` | Tells git which build and scratch files not to store |

## docs/ — the documents to read

| File | What it is |
|---|---|
| `BOM.md` | Shopping list: every part to buy, brand, shop link, price (≈ £312), and the motors |
| `BUILD_GUIDE.md` | Step-by-step build: printing, tubes, TVC module, fins and tabs, camera, avionics bay, recovery, firmware set-up, launch pad, loading a motor and the balance check |
| `PCB.md` | The flight-computer circuit board: what is on it, the pin map, how it was checked, and how to order it from JLCPCB |
| `FIRMWARE.md` | The flight software: how it works, every USB command, logging, how to flash it, version history |
| `TEST_PLAN.md` | Bench tests, field tests and the flight programme (D20, D20, E20, then the F35), with pass criteria |
| `PREFLIGHT_CHECKLIST.md` | Printable checklist for the night before, the field, the pad, the launch and recovery |
| `SAFETY_AND_LEGAL.md` | UK rules (UKRA/BMFA, CAA, motors, LiPo) and the safety rules this rocket needs (distances, wind, recovery area) |
| `SIMULATION_REPORT.md` | All simulation results: validation against RocketPy, apogee and drag, 44 scenario and fault cases, Monte Carlo, stress Monte Carlo, hand checks, design iterations |

## cad/ — the 3D model (Blender + manifold3d)

| File | What it is |
|---|---|
| `kestrel_cad.py` | **The CAD program.** Builds every part from `design.json`, checks fits and mechanisms, exports the STLs, renders the pictures and saves the Blender files. Run: `blender -b -P cad/kestrel_cad.py -- [--no-render]` |
| `kestrel.blend` | Main Blender file *(generated)*. Scene 1: the complete rocket, the same rocket cut open, and every part laid out with its name. Scenes 2–7: exploded view, cut-aways, payload door open, fin tabs deflected, a fin cut open, the rocket on its launch pad |
| `kestrel_rocket.blend` | Just the constructed rocket, every part in place, grouped by section *(generated)*. Hide "Body tubes" to look inside |
| `kestrel_tvc_module.blend` | The TVC (motor-steering) module on its own, plus its assembly steps *(generated)* |
| `kestrel_parachute_open.blend` | The rocket coming down under its open parachute *(generated)* |
| `check_parts.py` | Checks every STL: watertight, one body, fits a 220 × 220 × 250 mm printer, overhangs printable |
| `mass_properties.py` | Turns the part volumes into printed masses and positions for the simulator |
| `mass_properties.json` | Mass and position of every printed part *(generated)* |
| `component_positions.json` | Position and size of every bought part (servos, battery, motor…) *(generated)*; the simulator reads it |
| `avionics_layout.json` | Key positions (IMU, camera lens, fin angles, pad) shared with the simulator and the video *(generated)* |
| `interference_report.md` | Proof that no two parts overlap, and that the gimbal, tabs, payload door and release latch move through their full travel without hitting anything *(generated)* |

### cad/stl/ — print-ready parts (already in print orientation)

| File | Qty | What it is |
|---|---|---|
| `nose_cone.stl` | 1 | Nose cone, with the cavity for the 51 g of ballast |
| `top_latch_insert.stl` | 1 | Top of the middle part: holds the parachute-release servo and latch, the nose slides over it |
| `latch_bolt.stl` | 1 | The sliding bolt that locks the nose on; the servo pulls it to release the parachute |
| `payload_wall.stl` | 1 | Wall between the payload bay and the parachute bay |
| `spring_piston.stl` | 1 | Piston between the ejection spring and the parachute |
| `payload_door_frame.stl` | 1 | Frame glued behind the payload-door opening |
| `payload_door.stl` | 1 | The hinged payload door |
| `payload_door_latch_knob.stl`, `payload_door_latch_cam.stl` | 1 each | Quarter-turn coin lock for the door |
| `avbay_coupler.stl` | 1 | Joins the bottom and middle parts; its bulkhead is the payload-bay floor |
| `avbay_sled.stl` | 1 | Holds the flight-computer board (3 screw standoffs and a rest pad), battery and GPS antenna; the radio antenna stands in a channel through it |
| `fin_can.stl` | 1 | The four fins with the servo pockets and housings, and the four tongues the legs bolt to, in one piece |
| `fin_leg.stl` | 4 (+2 spares) | The replaceable legs (tough PLA, solid): slide over a tongue, one M3 bolt. The post is the designed weak point |
| `battery_hatch_door.stl`, `battery_hatch_latch_knob.stl`, `battery_hatch_latch_cam.stl` | 1 each | The battery hatch on the lug side: door (sits on the tube, overlaps the opening), quarter-turn latch |
| `fin_control_tab.stl` | 4 | The steerable tabs at the back of each fin |
| `camera_cradle.stl` | 1 | Holds the onboard camera inside the bottom tube, 30° down, behind the camera window |
| `camera_door.stl`, `camera_latch_knob.stl`, `camera_latch_cam.stl` | 1 each | The camera door (lens port under a low brow; sits on the tube like the battery hatch) and its quarter-turn latch |
| `radio_cradle.stl` | 1 | Holds the telemetry radio against the bottom-tube wall at 122° (two cable ties) |
| `antenna_mount.stl` | 1 | Shelf for the antenna lead's RP-SMA bulkhead socket at 30°; the antenna stands up from it |
| `upper_launch_lug.stl` | 1 | Second launch lug (guides the rocket on the rod) |
| `tvc_frame.stl` | 1 | Frame of the TVC module: holds the gimbal and its two servos |
| `tvc_gimbal_ring.stl` | 1 | Gimbal ring: tilts the motor one way |
| `tvc_motor_holder.stl` | 1 | Holds the 29 mm motor and tilts the other way |
| `tvc_motor_retainer.stl` | 1 | Twist-lock cap that holds the F35 in (22 mm opening) |
| `tvc_motor_adapter_24mm.stl` | 1 | Sleeve so the 24 mm D20 / E20 test motors fit the 29 mm holder |
| `tvc_motor_retainer_24mm.stl` | 1 | Retainer for the 24 mm motors (16 mm opening) |
| `tvc_motor_spacer_D.stl` | 1 | 25 mm spacer above the shorter D20 so it sits against the top |
| `pad_hub.stl` | 1 | Launch-pad centre: takes the three legs, the rod and the tile |
| `pad_rod_block.stl` | 1 | Clamps the launch rod and tilts it 0–15° |
| `pad_rod_stop.stl` | 1 | Holds the rocket on a tilted rod |
| `pad_leg_foot.stl` | 3 | Feet for the dowel legs (tent pegs go through them) |
| `pad_tile_clamp.stl` | 4 | Clamp the ceramic blast tile to the hub |
| `rod_tip_safety_cap.stl` | 1 | Cap for the rod tip when no rocket is on it |
| `tool_drill_guide_bottom_tube.stl`, `tool_drill_guide_middle_tube.stl` | 1 each | Drilling templates for the body tubes, including the camera window, the battery-hatch opening, both lug lines and the radio and antenna lines (not flown) |
| `tool_leg_test_block.stl` | 1 | A copy of the fin can's leg tongue on a block for a vice: break-test spare legs with a luggage scale (test plan A19; not flown) |
| `check_report.md` | | Size, mass and printability result of every part *(generated)* |
| `parts.json` | | Volume, area and position of every part *(generated)* |

### cad/renders/ — pictures *(generated)*

`rocket_on_pad.png`, `rocket_exploded.png`, `parachute_open.png`, `launch_pad.png` (the whole rocket and pad);
`tvc_module.png`, `tvc_module_assembly_steps.png`, `tvc_gimbal_cutaway.png` (motor steering);
`fin_servo_cutaway.png`, `fin_tab_closeup.png` (fins, tabs and their servos); `avbay_cutaway.png` (flight computer);
`camera_radio_cutaway.png` (the camera behind its door, the telemetry radio and its antenna);
`payload_bay_open.png`, `release_latch_cutaway.png` (payload and parachute release).

## pcb/ — the flight-computer circuit board (KiCad 7)

| File | What it is |
|---|---|
| `circuit.py` | **The circuit as code**: every component, its JLCPCB part number, every connection and its position. The single source of truth for the board |
| `gen_schematic.py` | Makes the schematic from `circuit.py` |
| `board_build.py`, `export_geometry.py`, `router.py`, `gen_pcb.py` | Build the board: place parts, route the copper tracks (`router.py` is the autorouter), add the ground/power planes, run the design-rule check |
| `export_mech.py` | Exports the board's shape and connector positions to the CAD model |
| `check_netlist.py` | Checks KiCad's netlist against `circuit.py`, pin by pin, plus electrical rules |
| `jlc_fab.py` | Makes the files JLCPCB needs to manufacture and assemble the board |
| `sexp.py` | Small helper that reads and writes KiCad's file format |
| `kestrel_fc.kicad_pro`, `.kicad_sch`, `.kicad_pcb` | The KiCad project, schematic and board *(generated)*: open them in KiCad 7 |
| `kestrel_fc.net` | Netlist (list of connections) exported from the schematic |
| `kestrel_fc_schematic.pdf` | The schematic as a PDF, to read without KiCad |
| `kestrel.kicad_sym`, `kestrel.pretty/`, `fp-lib-table`, `sym-lib-table` | Custom KiCad symbol and footprint (the BMP580 barometer) and the library tables |
| `production/kestrel_fc_gerbers_jlcpcb.zip` | **Upload this to JLCPCB**: the board manufacturing files |
| `production/kestrel_fc_bom_jlcpcb.csv`, `production/kestrel_fc_cpl_jlcpcb.csv` | Parts list and placement file for JLCPCB's assembly service |
| `production/kestrel_fc_assembly_top.pdf` | Assembly drawing, to check JLCPCB's part placement |
| `build/drc_report.txt` | Design-rule check: 0 violations |
| `build/svg/front.png`, `back.png`, `front_back.png` (+ `.svg`) | Pictures of the finished board |
| `build/gerbv_front_check.png` | The gerbers re-drawn by an independent viewer, as a cross-check |
| `build/geometry.json`, `routes.json`, `mech_interface.json` | Intermediate data passed between the board scripts *(generated)* |

## firmware/ — the flight software

| File | What it is |
|---|---|
| `pico/kestrel_fc.uf2` | **Ready-to-flash firmware 3.00** (board v3): hold BOOTSEL on the Pico, plug in USB, drag this file onto it |
| `CMakeLists.txt` | Builds the flight core, its tests and the simulator library on a PC |
| `core/src/flight.cpp` | **The flight code**: attitude and altitude estimation, TVC steering, fin-tab control, flight states, parachute decision |
| `core/include/kestrel/flight.hpp` | Its interface |
| `core/include/kestrel/config.hpp` | Tunable settings (gains, limits, thresholds), tuned in the simulator |
| `core/include/kestrel/motor_db.hpp` | Thrust curves and rocket data for every supported motor (D20, E12, E20, Estes E12/D12, F35) *(generated by `tools/gen_motor_db.py`)* |
| `core/include/kestrel/types.hpp`, `vecmath.hpp` | Shared data types and vector/quaternion maths |
| `core/include/kestrel/telemetry.hpp`, `core/src/telemetry.cpp` | The radio frame format (MAVLink-v1 framing, CRC), the rates for each flight phase and the one-hour airtime budget |
| `core/tests/test_core.cpp` | 375,585 automatic checks of the flight code and the radio frames |
| `pico/src/main.cpp` | The Pico 2 W program: 500 Hz flight loop, USB command line, bench tests |
| `pico/src/board.hpp` | Which Pico pin does what (matches the circuit board) |
| `pico/src/hw/sensors.*` | Drivers for the IMU, barometer and log flash chip |
| `pico/src/hw/io.*` | Servos, GPS, buzzer, LEDs, button, battery monitoring |
| `pico/src/hw/radio.*` | The telemetry radio's serial port (UART1 on the radio socket) |
| `pico/src/logic/radio_link.*` | What goes on the radio and when: frame queue, rates, flow control, range-test mode, the link report |
| `pico/src/app/logger.*` | Flight logging to the 16 MB flash chip |
| `pico/src/app/settings_store.*` | Saves your calibration and settings in the Pico's flash |
| `pico/src/logic/servo_map.*` | Turns gimbal and tab angles into servo pulses; the saved settings |
| `pico/src/logic/axis_cal.*` | Works out how the IMU is mounted (the `calaxes` command) |
| `pico/src/logic/nmea.*` | Reads the GPS messages |
| `pico/tests/test_logic.cpp`, `pico/tests/fake/` | 148 PC-side checks of that logic (radio link included), with stand-ins for the Pico libraries |
| `pico/CMakeLists.txt`, `pico/pico_sdk_import.cmake` | Builds the UF2 with the Raspberry Pi Pico SDK |
| `sil/kestrel_sil.cpp` | Lets the Python simulator fly the real flight code ("software in the loop") |
| `tools/kestrel_link.py` | **PC tool**: talk to the rocket over USB, download the flight log, plot it, summarise it; record the ground radio (`radio`) |
| `tools/gen_motor_db.py` | Makes `motor_db.hpp` from the motor data and `design.json` |
| `tools/example_flight_sim.csv`, `example_flight_sim.png` | A simulated F35 flight log in the real log format, and its plot, to try `kestrel_link.py` on |

## sim/ — the simulator

| File | What it is |
|---|---|
| `kestrel/rocket.py` | The rocket model: mass, balance, aerodynamics, drag, motors |
| `kestrel/dynamics.py` | The 6-DOF flight simulation: motion, wind, servos, sensors, parachute |
| `kestrel/sil.py` | Connects the simulator to the real flight code |
| `kestrel/motors.json` | Thrust curves and ratings of the TSP and Estes motors |
| `kestrel/plots.py` | Draws the flight plots |
| `kestrel/__init__.py` | Makes `kestrel` a Python package |
| `scenarios.py` | 44 fixed test flights and fault cases (wind, crooked parts, dead servos, failed sensors…) |
| `montecarlo.py` | Randomised flights; `run_all.sh` flies 1500 (1000 F35, 400 E20, 100 D20) |
| `first_flight_mc.py` | The first-flight study: 700 E20 flights (flight 1 TVC only, flight 2 with tabs, and more wind than allowed): how high the parachute opens |
| `run_all.sh` | Runs every simulation suite in order (about 45 min on 4 cores) |
| `plot_montecarlo.py` | Draws the Monte Carlo charts |
| `stress_montecarlo.py` | 1000 flights with doubled errors and wind up to 9 m/s, to find where the margins end |
| `mc_tab_effectiveness.py` | 200 flights with the fin tabs 20 % stronger than modelled |
| `validate_rocketpy.py` | Flies the same rocket in RocketPy (an independent simulator) and compares |
| `whatif.py` | Drag breakdown and "what if it were lighter / heavier / draggier" flights |
| `make_example_log.py` | Makes `firmware/tools/example_flight_sim.csv` |
| `video/make_flight_video.py` | **Makes a launch video** of a simulated flight (`--seed N` for a different flight, `--draft` for a quick preview) |
| `video/blender_scene.py` | The Blender part of the video: field, pad, rocket, parachute, ground and onboard cameras |
| `video/compose.py` | Adds the live telemetry and graphs and makes the MP4 |

### sim/results/ — simulation results *(generated)*

| File | What it is |
|---|---|
| `scenarios.md`, `scenarios.json`, `scenarios_console.txt` | Results of the 47 scenarios (44 of 44 graded cases pass) |
| `scenario_*.png` (15) | Flight plots of the most interesting scenarios (baseline, the E20 first flight, wind limit, faults…) |
| `montecarlo.json`, `montecarlo_console.txt` | Monte Carlo results (1500 of 1500 succeed) |
| `first_flight_mc.md`, `.json`, `_console.txt` | First-flight study results (700 of 700) |
| `montecarlo_summary.png`, `montecarlo_payload.png` | Monte Carlo charts |
| `stress_montecarlo.json`, `stress_montecarlo_console.txt` | Stress Monte Carlo results (99.7 %; 99.9 % safe recovery) |
| `rocketpy_validation.md`, `.json` | Comparison with RocketPy (within 0.33 %) |
| `whatif.md` | Drag breakdown and what-if apogees |
| `video/kestrel2_flight_seed7.mp4`, `video/kestrel2_flight_seed7_poster.png` | The simulated launch video (F35, seed 7) and a still from it |

## ground/ — Mission Control, the ground-station screen

| File | What it is |
|---|---|
| `README.md` | How to use it: the views, the live radio link, the landing prediction, USB, replay, save, and the log line format |
| `kestrel_mission_control.html` | **Open this at the launch field** (Chrome or Edge): the whole screen in one file, works offline. 3D map of the range with the rocket on it, flight events (liftoff, burnout, apogee, parachute, landed), live telemetry, steering dials, strip charts, **live radio link** (and radio set-up), **landing prediction**, USB link to the flight computer, save + replay of every flight *(generated by `build_offline.py`)* |
| `mission_control.html` | The same page before it is packed into one file (loads three.js from the internet) |
| `demo_flight.csv` | The built-in demo: a simulated F35 flight (seed 7, 148 m) in the flight computer's log format *(generated)* |
| `make_demo_flight.py` | Flies the demo with the real flight code in the loop and writes `demo_flight.csv` |
| `build_offline.py` | Packs the page, the demo and three.js into `kestrel_mission_control.html` |
| `vendor/three-r128.min.js`, `vendor/THREE_LICENSE` | three.js r128 (the 3D library the screen uses) and its MIT licence |
| `radio_frames.py` | The radio frame format in Python (independent of the page): decodes a radio recording to CSV, or makes the demo flight's radio bytes |
| `test_radio.mjs` | Tests the page's radio decoder against pymavlink reference frames and `radio_frames.py`, including a damaged link |
