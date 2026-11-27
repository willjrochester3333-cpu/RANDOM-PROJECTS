# Flight firmware (v3.00, KESTREL-2, board v3)

Two layers, one code base:

| Layer | Where | What it does | Tested by |
|---|---|---|---|
| **Flight core** | `firmware/core/` | attitude estimator, altitude Kalman filter, TVC controller, **fin-tab controller and mixer**, flight state machine, log record, **radio frame format and airtime budget** (`telemetry.hpp`). Pure C++17, no hardware, no heap | 375,585 unit-test checks (`core_tests`, including pymavlink reference frames, a damaged-stream resync test and an hour stuck at full rate against the airtime cap) + **every simulated flight** (the 6-DOF simulator loads this exact code as a shared library: software-in-the-loop) |
| **Pico application** | `firmware/pico/` | drivers (LSM6DSO, BMP580, W25Q128, ATGM336H GPS, **7 servos**, buzzer/LEDs, battery ADC, **telemetry radio on UART1**), 500 Hz loop, flash logger, USB command line, bench test modes | 148 host checks (`pico_logic_tests`: NMEA, IMU axis calibration in all 24 mountings, TVC and **fin-tab** mapping, settings CRC, the logger against a model of the flash chip, **the radio link end to end**: rates by flight phase, flow control, range-test mode) + a clean cross-compile (`-Wall -Wextra -Wdouble-promotion`: 0 warnings) |

Ready-to-flash binary: **`firmware/pico/kestrel_fc.uf2`** (hold BOOTSEL, plug in USB, drag the file onto the
`RP2350` drive).

## Flight logic

```
BOOT ──sensors ok──▶ CALIBRATING ──still 3 s, battery ok──▶ READY ──> 2 g along the axis for 30 ms──▶ BOOST
                        │  (launch here anyway = "unarmed launch": TVC + tabs centred,  │
                        │   parachute logic still runs)                                  ▼
ERROR ◀─ sensor failure / IMU axes not calibrated            COAST ◀── thrust gone (< 0.25 g after 0.4 s)
                                                                │
                      apogee: 3 baro samples falling, > 8 m    ▼
            backup: nominal apogee time + 3 s, or falling > 12 m/s,
                    or ABORT (tilt > 50° / tumbling) once below 30 m/s ──▶ DESCENT ──still 5 s──▶ LANDED
```

- **TVC** runs in BOOST. It holds the direction the rocket had on the launch rod (`hold 1`, default) or vertical
  (`hold 0`). Gains are scheduled with the selected motor's thrust curve; the deflection is clamped as a vector to
  6° (the CAD gimbal sweep verifies clearance to 7° in every direction). The linkage moves the gimbal 0.41° per
  servo degree (9 mm horn hole, 22 mm gimbal arm on the 29 mm mount; the CAD script checks that `design.json`
  agrees).
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

Each tab servo sits inside its fin with its output shaft on the tab's hinge line, so the servo turns the tab
directly: ±15° of tab is ±15° of servo (±158 µs). The mapping is still the general linkage formula
(`horn × sin(tab) = arm × sin(servo)`) with horn = arm (`tab_horn_mm` = `tab_servo_arm_mm` = 1 in the settings and
in `design.json`), so a pushrod-driven tab could be set up again without new code; the tests cover both.

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
| `calaxes` | **required once**: measures the IMU orientation (pose 1 nose up, pose 2 flat with the camera door down) |
| `dirtest` | moves each TVC axis +3° in turn so you can check the direction |
| `tabtest` | moves each fin tab +10° in turn: seen from behind (nozzle towards you) its trailing edge must swing **anticlockwise**, towards the fin with the next-lower number |
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
| `motor [n]` | list / select the motor profile: 0 TSP D20, 1 TSP E12, 2 TSP E20, 3 Estes E12, 4 Estes D12, **5 TSP F35 (default, the mission)**. The 24 mm motors fly in the printed adapter sleeve; their tables include its mass |
| `hold <1\|0>` | hold the launch-rod direction / vertical |
| `save`, `defaults` | store settings in the Pico's flash / factory settings |
| `radio` | telemetry radio: frames sent / dropped / held back, airtime in the last hour, the radio's own link report (signal here and at the ground radio, noise, its buffer), whether Mission Control's heartbeat is being heard |
| `radio on` / `radio off` | telemetry on / silent (`save` to keep; on by default) |
| `radio test` | 60 s of flight-rate frames (50 + 5 a second) on the ground, for the range test |
| `log`, `dump [first]` | log summary / CSV of the whole log over USB (a 29th column, `rssi`, is the radio signal at the rocket) |
| `erase yes` | wipe the 16 MB log (≈ 40 s) |
| `reboot`, `bootsel` | restart / USB drive for new firmware |

Download and plot: `python firmware/tools/kestrel_link.py dump --port COMx -o flight.csv`, then
`... plot flight.csv` (altitude, speed, tilt and gimbal, **fin tabs and roll rate**, states, GPS track with the
landing point). `firmware/tools/example_flight_sim.csv` is a simulated F35 flight in the same format to try it on.

## Radio telemetry (3.00)

The board's radio socket (J7, Pixhawk TELEM pinout) carries a SiK 433 MHz radio on UART1 (GP4 = TX, GP5 = RX,
57600 baud, the radio's default). The frames are **MAVLink v1 shaped** (0xFE, length, sequence, system 75, component,
message id, payload, CRC-16/MCRF4XX with a per-message extra byte), so the SiK radio in its default `MAVLINK=1` mode
keeps every frame whole inside one radio packet: a lost radio packet loses whole frames, never half of one.

| Message | Id | Bytes | Contents | Rate |
|---|---|---|---|---|
| `KESTREL_FAST` | 230 | 42 + 8 | time, state, flags, gyro, accel, altitude, vertical speed, tilt, gimbal y/z, attitude quaternion, the four tab commands, roll | 50 / s from lift-off to landing, 1 / s on the pad |
| `KESTREL_SLOW` | 231 | 46 + 8 | GPS position (1e-7°), GPS altitude and satellites, baro altitude, battery, cell 1, servo rail, flight number, firmware version, motor, health bits, highest altitude, airtime used, signal at both ends, log state, ground station heard | 5 / s in flight, 0.5 / s on the pad, 1 / s for a minute after landing, then every 5 s |
| `HEARTBEAT` | 0 | 9 + 8 | standard MAVLink; it makes the rocket's radio report its link quality (`RADIO_STATUS`) back to the board | 1 / s |

Rules: frames go into a 2 kB ring that is emptied into the UART's FIFO every loop, so the 500 Hz loop never waits;
a frame that does not fit is dropped whole; when the rocket's radio reports its buffer under 25 % free (a weak
link), motion frames are held back so it can drain. A rolling one-hour airtime estimate (one-minute buckets, 2 % of
every hour for the radio's own link packets, 60 s assumed at power-on) switches to lean rates (10 + 2 a second) above
270 s and to a 0.2 Hz beacon above 330 s: the UK limit is 360 s per hour (see
[SAFETY_AND_LEGAL.md](SAFETY_AND_LEGAL.md#radio)). Nothing the radio receives changes the flight: the board only
reads its own radio's `RADIO_STATUS` (the signal strength is logged in every flash record) and notes Mission
Control's heartbeat. The decoder in `ground/mission_control.html` is tested against frames made by a separate
Python implementation (`ground/radio_frames.py`, `ground/test_radio.mjs`).

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
| 49 | radio signal at the rocket (SiK units, dBm ≈ value / 1.9 − 127; 0 = no radio report) | fw 3.00 |
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

## Updating from 2.00 – 2.04

3.00 is for board v3 (the radio socket replaces the Qwiic port: GP4/GP5 are now UART1) and the airframe with the
camera inside and the radio installed: the rocket is 43 g heavier (947 g with the F35; CG 638 mm from the nose tip),
so the motor and airframe tables are regenerated (F35 now about 158 m at 6.5 s, E20 41 m at 3.9 s). It adds the
radio telemetry above, logs the radio signal in the record's spare byte, and fixes a bug: records written after an
in-flight reset had their recovery flag set after their CRC was computed, so `dump` would have skipped them. The
settings layout is unchanged (version 6; the spare byte that becomes `radio_off` reads 0 = radio on), so a board that
ran 2.04 keeps its calibration, trims and motor selection. 3.00 also runs on a v2 board: the radio frames then go
out on the Qwiic pins, harmlessly.

2.04 is for the multi-flight airframe (replaceable legs, thicker servo housings, battery hatch, 46 g of nose
ballast): the rocket is 48 g heavier (its CG stays at 634 mm from the nose tip), so the motor and airframe tables (pitch
inertia, CG-to-gimbal lever arm, launch-detect delay, nominal apogee time; F35 now 170 m at 6.6 s) and the tab
mixer's roll inertia are regenerated. Nothing in the settings layout changed (still version 6): a board that ran
2.03 keeps its calibration, trims and motor selection.

2.03 is for the 29 mm TVC mount and the TSP F35: the F35 is added to the motor tables (`motor 5`, now the default),
the tables and the fin-tab mixer are recomputed for the F35 at lift-off, and the TVC linkage ratio changes from 0.5
to 0.41 because the gimbal arms are 22 mm long instead of 18 mm. The settings layout version goes from 5 to 6, so
a board that ran 2.02 starts with factory settings: run `calaxes`, `dirtest`, `tabtest`, the trims and `deployus`
again, then `save`.

2.02 is for the fins with the tab servos inside their thick bottom band: the tabs are driven directly (servo angle = tab
angle), the motor and airframe tables include the heavier fin can, the nose ballast and the 36 in parachute, and
the apogee detector arms from 8 m instead of 15 m (the heavier rocket can peak at 14 m on a weak D20). 2.01 corrected the
TVC linkage ratio (0.42 → 0.5). Both changed the settings layout version, so a board that ran an older version
starts with factory settings: run `calaxes`, `dirtest`, `tabtest`, the trims and `deployus` again, then `save`.

## Modifying it

- New motor: add its thrust curve and rating to `sim/kestrel/motors.json` and its name to `MOTORS` in
  `firmware/tools/gen_motor_db.py`, regenerate, then fly it in the simulator first. The simulator scales every
  curve to the manufacturer's rated impulse and burn time (`KESTREL_MOTOR_BASIS=curve` uses the file as is).
- Tab gains, limits and safety rules: `FinGains` in `core/include/kestrel/config.hpp` (all settable in the SIL by
  name for experiments, e.g. `SilFsw({"roll_kp": 120})`).
- Board v3 has no Qwiic port (its two pins carry the radio). A new I²C sensor would need a v4 board with an
  I²C-to-serial or I²C expander chip.
- Every change should pass the scenario suite and the Monte Carlo before it flies.
