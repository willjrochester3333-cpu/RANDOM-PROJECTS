# Flight firmware

Two layers, one code base:

| Layer | Where | What it does | Tested by |
|---|---|---|---|
| **Flight core** | `firmware/core/` | attitude estimator, altitude Kalman filter, TVC controller, flight state machine, log record. Pure C++17, no hardware, no heap | 303,064 unit-test checks (`core_tests`) + **every simulated flight** (the 6-DOF simulator loads this exact code as a shared library: software-in-the-loop) |
| **Pico application** | `firmware/pico/` | drivers (LSM6DSO, BMP580, W25Q128, ATGM336H GPS, servos, buzzer/LEDs, battery ADC), 500 Hz loop, flash logger, USB command line, bench test modes | 59 host checks (`pico_logic_tests`: NMEA, IMU axis calibration in all 24 mountings, servo mapping, settings CRC, the logger against a model of the flash chip) + a clean cross-compile (`-Wall -Wextra -Wdouble-promotion`: 0 warnings) |

Ready-to-flash binary: **`firmware/pico/kestrel_fc.uf2`** (hold BOOTSEL, plug in USB, drag the file onto the
`RP2350` drive).

## Flight logic

```
BOOT ──sensors ok──▶ CALIBRATING ──still 3 s, battery ok──▶ READY ──> 2 g along the axis for 30 ms──▶ BOOST
                        │  (launch here anyway = "unarmed launch": TVC centred,       │
                        │   parachute logic still runs)                                ▼
ERROR ◀─ sensor failure / IMU axes not calibrated            COAST ◀── thrust gone (< 0.25 g after 0.4 s)
                                                                │
                      apogee: 3 baro samples falling, > 15 m   ▼
            backup: nominal apogee time + 3 s, or falling > 12 m/s,
                    or ABORT (tilt > 50° / tumbling) once below 30 m/s ──▶ DESCENT ──still 5 s──▶ LANDED
```

- **TVC** runs only in BOOST. It holds the direction the rocket had on the launch rod (`hold 1`, default) or
  vertical (`hold 0`). Gains are scheduled with the selected motor's thrust curve; the deflection is clamped as a
  vector to 6° (the CAD gimbal sweep verifies clearance to 7° in every direction).
- **Parachute** release is a servo-driven snap-in latch: bevelled bolts click into the upper section's collar
  when you push it on, and the servo only has to pull them in at apogee. There is no pyrotechnic charge, and the
  latch is commanded LOCKED from the first microsecond after power-up.
- **Watchdog**: if the processor ever resets while flying (BOOST/COAST/DESCENT), it reboots straight into a
  recovery mode: parachute released, TVC centred, locator beeping. It never tries to steer again.

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

Digits: a digit *n* is *n* short beeps, a zero is one long beep, pause between digits (197 m = 1 · 9 · 7).
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
| `dir <1\|2> <1\|-1>` | flip a TVC servo direction |
| `tvctest` | live closed-loop TVC with the flight control law (60 s, Enter stops) |
| `center` | TVC centred, latch locked |
| `servo <1-4> <µs>` | raw pulse for bench work |
| `trim <1-4> <µs>` | centre offset per servo |
| `deploy lock` / `deploy release` | move the parachute latch |
| `deployus <lock> <release>` | latch pulse widths |
| `motor [n]` | list / select the motor profile (D20, E12, E20, Estes E12) |
| `hold <1\|0>` | hold the launch-rod direction / vertical |
| `save`, `defaults` | store settings in the Pico's flash / factory settings |
| `log`, `dump [first]` | log summary / CSV of the whole log over USB |
| `erase yes` | wipe the 16 MB log (≈ 40 s) |
| `reboot`, `bootsel` | restart / USB drive for new firmware |

Download and plot: `python firmware/tools/kestrel_link.py dump --port COMx -o flight.csv`, then
`... plot flight.csv` (altitude, speed, tilt and gimbal, states, battery, GPS track with the landing point).
`firmware/tools/example_flight_sim.csv` is a simulated E20 flight in the same format to try it on.

## Flight log format

16 MB W25Q128 = 262,144 records of 64 bytes (`LogRecord` in `core/include/kestrel/types.hpp`), appended
across power cycles (≈ 30 flights). Rates: 500 Hz in BOOST/COAST (plus the 0.5 s before launch from a RAM
buffer), 50 Hz in DESCENT, 10 Hz on the pad, 5 Hz after landing for 10 minutes then every 5 s.

| Bytes | Field | Unit |
|---|---|---|
| 0–3 | `t_ms` | ms since power-on |
| 4 | `state` | 0–7 as above; **0xF0 = session header** (`flags` = motor, gyro[0] = firmware version, gyro[1] = flight number); **0xFE = filler, skip** |
| 5 | `flags` | bit0 TVC active, bit1 parachute released, bit2 new baro sample, bit3 GPS fix, bit4 abort, bit7 recovery mode |
| 6–11 | gyro x/y/z | 0.01 °/s |
| 12–17 | accel x/y/z | 0.01 m/s² |
| 18–29 | altitude (filter), vertical speed, raw baro altitude | float m, m/s, m |
| 30–35 | tilt from target, gimbal y, gimbal z | 0.01° |
| 36–37 | battery | mV |
| 38–45 | latitude, longitude | float ° |
| 46–48 | GPS altitude (m), satellites | |
| 50–61 | attitude quaternion x, y, z | |
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

After changing `design.json` or the motor list, regenerate the motor tables (`python3 firmware/tools/gen_motor_db.py`),
rebuild, and re-run `sim/scenarios.py` and `sim/montecarlo.py`.

## Modifying it

- New motor: add its thrust curve to `sim/kestrel/motors.json` and its name to `MOTORS` in
  `firmware/tools/gen_motor_db.py`, regenerate, then fly it in the simulator first.
- New sensor on the Qwiic port (I²C0 on GP4/GP5, 3.3 V): add a driver next to `src/hw/sensors.cpp` and log it in
  the reserved byte / a new record type.
- Gains and thresholds live in `core/include/kestrel/config.hpp`; every change should pass the scenario suite and
  the Monte Carlo before it flies.
