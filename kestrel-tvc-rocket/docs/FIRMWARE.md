# Flight firmware (v2.00, KESTREL-2)

Two layers, one code base:

| Layer | Where | What it does | Tested by |
|---|---|---|---|
| **Flight core** | `firmware/core/` | attitude estimator, altitude Kalman filter, TVC controller, **fin-tab controller and mixer**, flight state machine, log record. Pure C++17, no hardware, no heap | 377,492 unit-test checks (`core_tests`) + **every simulated flight** (the 6-DOF simulator loads this exact code as a shared library: software-in-the-loop) |
| **Pico application** | `firmware/pico/` | drivers (LSM6DSO, BMP580, W25Q128, ATGM336H GPS, **7 servos**, buzzer/LEDs, battery ADC), 500 Hz loop, flash logger, USB command line, bench test modes | 124 host checks (`pico_logic_tests`: NMEA, IMU axis calibration in all 24 mountings, TVC and **tab-linkage** mapping, settings CRC, the logger against a model of the flash chip) + a clean cross-compile (`-Wall -Wextra -Wdouble-promotion`: 0 warnings) |

Ready-to-flash binary: **`firmware/pico/kestrel_fc.uf2`** (hold BOOTSEL, plug in USB, drag the file onto the
`RP2350` drive).

## Flight logic

```
BOOT ──sensors ok──▶ CALIBRATING ──still 3 s, battery ok──▶ READY ──> 2 g along the axis for 30 ms──▶ BOOST
                        │  (launch here anyway = "unarmed launch": TVC + tabs centred,  │
                        │   parachute logic still runs)                                  ▼
ERROR ◀─ sensor failure / IMU axes not calibrated            COAST ◀── thrust gone (< 0.25 g after 0.4 s)
                                                                │
                      apogee: 3 baro samples falling, > 15 m   ▼
            backup: nominal apogee time + 3 s, or falling > 12 m/s,
                    or ABORT (tilt > 50° / tumbling) once below 30 m/s ──▶ DESCENT ──still 5 s──▶ LANDED
```

- **TVC** runs in BOOST. It holds the direction the rocket had on the launch rod (`hold 1`, default) or vertical
  (`hold 0`). Gains are scheduled with the selected motor's thrust curve; the deflection is clamped as a vector to
  6° (the CAD gimbal sweep verifies clearance to 7° in every direction).
- **Fin tabs** (four, one per fin, fins at 45/135/225/315°) run in BOOST and COAST:
  - **roll** is held at the launch angle in both phases (a 2-axis gimbal cannot control roll). This keeps the
    onboard camera's view steady; with the tabs off the simulated rocket rolls at 130–300 °/s.
  - **pitch/yaw in BOOST** is shared with the TVC in proportion to what each can deliver at that moment
    (gimbal authority grows with thrust, tab authority with airspeed²);
  - **pitch/yaw in COAST** is done by the tabs alone (the motor is out): they keep the rocket pointing at the
    launch direction against wind.
  - the mixer (`FinMixer`) turns the wanted roll/pitch/yaw accelerations into four tab angles: roll first, then
    pitch/yaw, each tab saturating on its own at ±15°, so one stuck tab cannot limit the other three.
  - safety rules: a **spin guard** (roll faster than 150 °/s in COAST → tabs fight only the roll), a **give-up
    rule** (more than 25° off target in COAST → all tabs centred for the rest of the flight), and tabs centred on
    the pad, under the parachute, after an abort or an unarmed launch.
  - `rollprog <°/s>` makes the camera turn a slow panorama during the coast instead of holding the roll.
- **Parachute** release: a single bevelled bolt in the top insert snaps into the nose cone's sleeve when you push
  the nose on, and the release servo pulls it in at apogee. No pyrotechnics; the latch is commanded LOCKED from the
  first microsecond after power-up.
- **Watchdog**: if the processor ever resets while flying (BOOST/COAST/DESCENT), it reboots straight into a
  recovery mode: parachute released, TVC and tabs centred, locator beeping. It never tries to steer again.

## Servo ports (PCB v2, left to right along the bottom edge)

| Port | Pico pin | Servo |
|---|---|---|
| 1 | GP6 | TVC ring (tilts the nozzle away from / towards the camera pod) |
| 2 | GP7 | TVC motor holder (tilts the nozzle away from / towards the payload door) |
| 3 | GP8 | parachute release latch (top of the middle part, lead runs down the inside wall) |
| 4 | GP9 | fin tab 1 (the fin with the pip, at 45° between the payload door and the launch lug) |
| 5 | GP2 | fin tab 2 (135°) |
| 6 | GP13 | fin tab 3 (225°) |
| 7 | GP15 | fin tab 4 (315°) |

A tab angle is turned into a servo pulse through the real linkage geometry
(`horn × sin(tab) = arm × sin(servo)`, 14.3 mm tab horn, 6 mm servo arm): ±15° of tab is about ±38° of servo.

## Lights and beeps

| State | Green LED | Buzzer |
|---|---|---|
| BOOT | on (with red) | — |
| CALIBRATING (keep the rocket still) | blinking 2 Hz | short chirp every second |
| **READY (armed)** | **solid** | **double chirp every 3 s** |
| BOOST / COAST | solid | silent |
| DESCENT | blinking 1 Hz | 0.3 s beep every second |
| LANDED | short flash every 2 s | **apogee in metres as digits**, then locator chirps |
| ERROR: do not launch | red blinking fast | fast beeping |

**Red LED blinking slowly** = warning: battery below 7.0 V, servo rail low, IMU axes not calibrated, rocket
tilted more than 20° on the pad, or the log flash not yet prepared. Check `status`.

Digits: a digit *n* is *n* short beeps, a zero is one long beep, pause between digits (78 m = 7 · 8).
**USER button**: short press beeps the battery voltage (7.9 V = 7 · 9); long press (1.5 s) beeps the number of GPS
satellites.

## USB command line

Any serial terminal (the baud rate is ignored), or `python firmware/tools/kestrel_link.py shell --port COMx`.
Commands that move servos or write flash are refused unless the rocket is on the ground
(BOOT/CALIBRATING/READY/LANDED/ERROR).

| Command | Purpose |
|---|---|
| `status` | everything: state, sensors (body frame), pad tilt, baro, GPS, battery cells, servo rail, log, settings, last flight |
| `calaxes` | **required once**: measures the IMU orientation (pose 1 nose up, pose 2 flat with the camera pod down) |
| `dirtest` | moves each TVC axis +3° in turn so you can check the direction |
| `tabtest` | moves each fin tab +10° in turn: its trailing edge must move **away from its servo pod** |
| `dir <1,2,4-7> <1\|-1>` | flip a servo direction (1–2 TVC, 4–7 tabs 1–4) |
| `tvctest` | live closed-loop TVC with the flight control law (60 s, Enter stops) |
| `fintest` | live closed-loop fin tabs (gains for ≈ 30 m/s): twist the rocket and all four tabs fight back; tilt it and the tabs push the nose back |
| `center` | TVC and tabs centred, latch locked |
| `servo <1-7> <µs>` | raw pulse for bench work |
| `trim <1-7> <µs>` | centre offset per servo |
| `tabs <1\|0>` | fin-tab control on / off |
| `tabmax <deg>` | tab deflection limit (2–15°) |
| `rollprog <°/s>` | camera panorama roll in the coast (0 = hold the launch roll angle) |
| `deploy lock` / `deploy release` | move the parachute latch |
| `deployus <lock> <release>` | latch pulse widths |
| `motor [n]` | list / select the motor profile (TSP D20, E12, E20, Estes E12, Estes D12) |
| `hold <1\|0>` | hold the launch-rod direction / vertical |
| `save`, `defaults` | store settings in the Pico's flash / factory settings |
| `log`, `dump [first]` | log summary / CSV of the whole log over USB |
| `erase yes` | wipe the 16 MB log (≈ 40 s) |
| `reboot`, `bootsel` | restart / USB drive for new firmware |

Download and plot: `python firmware/tools/kestrel_link.py dump --port COMx -o flight.csv`, then
`... plot flight.csv` (altitude, speed, tilt and gimbal, **fin tabs and roll rate**, states, GPS track with the
landing point). `firmware/tools/example_flight_sim.csv` is a simulated E20 flight in the same format to try it on.

## Flight log format

16 MB W25Q128 = 262,144 records of 64 bytes (`LogRecord` in `core/include/kestrel/types.hpp`), appended
across power cycles (≈ 30 flights). Rates: 500 Hz in BOOST/COAST (plus the 0.5 s before launch from a RAM
buffer), 50 Hz in DESCENT, 10 Hz on the pad, 5 Hz after landing for 10 minutes then every 5 s.

| Bytes | Field | Unit |
|---|---|---|
| 0–3 | `t_ms` | ms since power-on |
| 4 | `state` | 0–7 as above; **0xF0 = session header** (`flags` = motor, gyro[0] = firmware version, gyro[1] = flight number); **0xFE = filler, skip** |
| 5 | `flags` | bit0 TVC active, bit1 parachute released, bit2 new baro sample, bit3 GPS fix, bit4 abort, bit5 fin tabs active, bit6 tabs given up (safe), bit7 recovery mode |
| 6–11 | gyro x/y/z | 0.01 °/s |
| 12–17 | accel x/y/z | 0.01 m/s² |
| 18–29 | altitude (filter), vertical speed, raw baro altitude | float m, m/s, m |
| 30–35 | tilt from target, gimbal y, gimbal z | 0.01° |
| 36–37 | battery | mV |
| 38–45 | latitude, longitude | float ° |
| 46–48 | GPS altitude (m), satellites | |
| 50–55 | attitude quaternion x, y, z (w ≥ 0) | ÷ 32767 |
| 56–59 | fin tab commands 1–4 | 0.25° |
| 60–61 | roll angle since launch | 0.01° |
| 62–63 | CRC-16/CCITT of bytes 0–61 | |

## Building from source

```bash
git clone --depth 1 -b 2.1.1 https://github.com/raspberrypi/pico-sdk && (cd pico-sdk && git submodule update --init --depth 1 lib/tinyusb)
```

```bash
export PICO_SDK_PATH=$PWD/pico-sdk
cmake -S firmware/pico -B firmware/pico/build && cmake --build firmware/pico/build -j
```

Host tests and the simulator library:

```bash
cmake -S firmware -B firmware/build-host && cmake --build firmware/build-host -j && (cd firmware/build-host && ctest)
```

After changing `design.json`, the CAD or the motor list, regenerate the motor and airframe tables
(`python3 firmware/tools/gen_motor_db.py`: thrust, inertia and lever arm against time for every motor, plus the
tab mixer constants), rebuild, and re-run `sim/scenarios.py` and `sim/montecarlo.py`.

## Modifying it

- New motor: add its thrust curve and rating to `sim/kestrel/motors.json` and its name to `MOTORS` in
  `firmware/tools/gen_motor_db.py`, regenerate, then fly it in the simulator first. The simulator scales every
  curve to the manufacturer's rated impulse and burn time (`KESTREL_MOTOR_BASIS=curve` uses the file as is).
- Tab gains, limits and safety rules: `FinGains` in `core/include/kestrel/config.hpp` (all settable in the SIL by
  name for experiments, e.g. `SilFsw({"roll_kp": 120})`).
- New sensor on the Qwiic port (I²C0 on GP4/GP5, 3.3 V): add a driver next to `src/hw/sensors.cpp` and log it in
  a new record type.
- Every change should pass the scenario suite and the Monte Carlo before it flies.
