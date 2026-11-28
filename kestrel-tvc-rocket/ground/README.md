# KESTREL Mission Control

A ground-station screen for KESTREL-2: a 3D map of the launch range with the rocket flying on it, **live over the
telemetry radio**, the flight events as they happen (liftoff, burnout, apogee, parachute, landing), live telemetry,
**where it will land**, the steering (nose direction, motor gimbal, the four fin tabs), the rocket's systems, the
radio link's health, strip charts, and a recorder that keeps every flight for replay on the same 3D map.

| File | What it is |
|---|---|
| `kestrel_mission_control.html` | **Use this one at the launch field.** One self-contained file (three.js and the demo flight built in): works without internet, from a laptop or a USB stick. Open it in **Chrome or Edge** to use USB |
| `mission_control.html` | The page itself (loads three.js from a CDN and `demo_flight.csv` from beside it); also published as a private claude.ai page |
| `demo_flight.csv` | A simulated F35 flight (Monte Carlo seed 7: 148 m, 4.9 m/s wind, 20 g payload) flown by the real flight code, in the flight computer's log format (firmware 3.00). Made by `make_demo_flight.py` |
| `build_offline.py` | Builds `kestrel_mission_control.html` from the page, the demo flight and `vendor/three-r128.min.js` (three.js r128, MIT licence in `vendor/THREE_LICENSE`) |
| `radio_frames.py` | The radio frame format in Python (a second, independent implementation): decodes a raw radio recording to CSV (`decode rec.bin out.csv`), or makes the demo flight's radio bytes (`demo out.bin`) |
| `test_radio.mjs` | Tests the page's own radio decoder against pymavlink reference frames and against `radio_frames.py`, including a damaged link (`python3 ground/radio_frames.py demo d.bin && node ground/test_radio.mjs d.bin`) |
| `prediction_test/` | The landing-prediction test: `make_flights.py a` flies 60 simulated flights into the log format, `node test_prediction.js a` runs the page's own forecast on them at five moments of each flight and scores it against where each rocket came down (set `b`: 60 fresh flights) |

## What it can show

- **Live over the radio** (Chrome or Edge, offline file): plug the ground radio into the laptop's USB, press
  **Connect radio** and choose its port. As soon as the rocket is switched on its frames arrive (1 a second on the
  pad, **50 motion frames + 5 status frames a second from liftoff to landing**), the flight appears on the map and
  follows the rocket live. See [Live radio link](#live-radio-link) below.
- **Simulated live**: the demo flight sent through a simulated radio link in real time (the same frames, rates,
  2 % lost packets and signal strength falling with distance as the real link), from the pad (calibrating, READY)
  through liftoff, burnout, apogee and the parachute to landing. After landing it merges the "full log" exactly as
  a real flight does.
- **Replay**: any flight log. Drag the file onto the page or use **Load flight**: a `dump` from the flight
  computer (`kestrel_link.py dump`) or a flight saved here. A log with several flights asks which one. Play,
  pause, 0.25–8× speed, scrub the timeline (event ticks on it), click a chart to jump, arrow keys step
  (Shift = 5 s), keys 1–4 switch the camera.
- **Connect USB** (Chrome or Edge, offline file): talks to the flight computer over its USB cable. **Get log over
  USB** sends `dump` and loads the stored flights straight into the replay, no other software needed. Any line that
  arrives in the log format (see below) is shown live.
- **Save flight** writes the flight as a `.csv` in the same log format (it loads back here, into
  `kestrel_link.py plot`, or a spreadsheet). **Flights** lists the last 12 flights kept in this browser for quick
  replays; the saved file is the copy to keep.

Camera views: **Chase** (follows the rocket), **Pad cam** (a person standing 30 m from the pad, zooming), **Orbit**
(drag to turn, scroll or pinch to zoom, right-drag or Shift-drag to pan), **Map** (from above, north up). The rocket
is drawn 8× larger than life so you can see it on a 500 m range; **True size** shows it at its real 0.9 m. The
grid is 10 m, the rings every 100 m around the pad.

Where the numbers come from: altitude and vertical speed are the flight computer's filtered estimate (barometer +
accelerometer); the position over the ground is the GPS (5 fixes a second on the real rocket), with the first fix
as the pad; the attitude is the flight computer's quaternion. On the real rocket that quaternion has "up" right but
no compass heading (the flight computer has no magnetometer), so the nose-direction dial shows tilt correctly but
its N is the estimator's own axis, not true north. The simulated flight's heading is real.
Until the flight computer reaches READY its altitude is not yet zeroed on the pad (it is pressure altitude, often
100 m or more), so altitude and vertical speed read "–" while it boots and calibrates; saved files keep the raw
values.

## Live radio link

The rocket carries a **Holybro SiK V3 433 MHz** radio on the flight computer's radio socket; its twin plugs into the
laptop by USB. Set **both** radios up once, before the rocket's radio is built in: **Set up a radio (UK settings)…**
in the Radio link panel (one radio on USB at a time). It sets the transmit power to 8 dBm (about 6 mW e.r.p. with
the 2 dBi antennas, inside the UK's 10 mW licence-free limit) and both radios' network ID to 75, saves and
restarts the radio; everything else stays at the SiK defaults.

What arrives (firmware 3.00, details in [FIRMWARE.md](../docs/FIRMWARE.md#radio-telemetry-300)):

| From the rocket | Rate | Mission Control shows |
|---|---|---|
| motion frame: attitude, gyro, accelerometer, altitude, vertical speed, tilt, gimbal, fin tabs, roll | 50 / s in flight, 1 / s on the pad | the rocket on the map, the instruments, the strip charts |
| status frame: GPS position and satellites, battery and servo rail, motor, health, highest altitude, airtime, signal at both ends, log state | 5 / s in flight, 0.5 / s on the pad | Systems, the GPS track, the Radio link panel |
| heartbeat | 1 / s | (keeps both radios reporting their link quality) |

The **Radio link** panel: frames a second and in all, frames lost (counted from the frame numbers), the signal at
this radio (dBm and how far above the noise), the signal at the rocket and whether the rocket hears this station,
and the rocket's own airtime count against the UK's 360 s an hour. The page sends a heartbeat once a second: the
rocket only notes it (and sends "ground heard" back); **nothing sent from the laptop changes what the rocket does**.

**The full flight afterwards**: the radio frames are what you watch live; the flight computer still logs every
sample at 500 Hz to its flash memory. After landing, plug USB in through the hatch and press **Get log over USB**:
the full log is loaded and merged with the radio recording of the same flight (the replay then has every sample
plus the link statistics). Every radio flight is also kept under **Flights**; `firmware/tools/kestrel_link.py radio
--port … -o flight.bin` records the raw radio bytes on any computer (and decodes them to CSV with
`radio_frames.py` when you press Ctrl+C).

## Landing prediction

The **Landing prediction** panel says where the rocket will come down, as a distance and bearing from the pad, a
latitude/longitude you can copy (for a phone map), and an orange search ring on the 3D map:

- **On the pad**: from the motor's expected apogee (41 m on the E20, 157 m on the F35, calm air; the motor comes
  from the rocket's status frames, or from a log's session line) and the wind you type in before launch: its speed
  **measured at head height** (a hand-held meter), and the direction it comes **from**. With no wind typed in it
  assumes calm, and is then no use: type it in.
- **Going up**: in the boost, the motor's expected apogee; after burn-out, a drag-limited coast from the live
  vertical speed; then the descent.
- **Under the parachute**: the wind is **measured** from the rocket's own GPS drift (from 3 s after the canopy
  opens, over up to the last 10 s) and the descent rate from the altitude, so the forecast tightens as it comes down.
- **Landed**: the last GPS position.

Wind grows with height, so a wind measured at one height (your meter, or the rocket under its canopy) is turned
into the average wind over the rest of the fall with the 1/7 power law that open ground usually follows (the
simulator uses the same law). The search ring is 5 m + 40 % of the drift still to come + 0.4 m for every second
the rocket is still in the air (for gusts).

How good it is, tested on 120 simulated flights flown by the real flight code (`ground/prediction_test/`; the ring
was fitted on the first 60, the numbers below are the 60 fresh ones):

| Forecast made | F35: typical miss (median) | F35: inside the ring | E20: typical miss | E20: inside the ring |
|---|---|---|---|---|
| on the pad, wind typed in | 26 m | 33 of 40 | 6 m | 16 of 20 |
| 1 s into the boost | 24 m | 35 of 40 | 6 m | 18 of 20 |
| just after apogee | 14 m | 37 of 40 | 4 m | 20 of 20 |
| 8 s under the open canopy | 15 m | 36 of 40 | 0 m | 20 of 20 |
| halfway down | 9 m | 38 of 40 | 1 m | 20 of 20 |
| on the pad, **no wind typed in** | 152 m (all of the drift) | 2 of 40 | 19 m | 2 of 20 |

(The F35 flights drifted 102 m from the pad on average, up to 327 m; the E20 flights 28 m, up to 76 m. The "no
wind" row is from the first 60 flights.) It is a forecast for finding the rocket, not a promise: real wind does not
always follow the 1/7 law. The rocket itself does not steer towards it (it only ever steers straight up; see
[SAFETY_AND_LEGAL.md](../docs/SAFETY_AND_LEGAL.md#steering-straight-up-only)).

## Log line format

Lines from the flight computer's USB (`dump`, or a live line) and saved flights use the log format,

```
t_ms,state,flags,gx_dps,gy_dps,gz_dps,ax,ay,az,alt_m,vz_ms,baro_alt_m,tilt_deg,gimbal_y,gimbal_z,vbat,lat,lon,gps_alt,sats,qx,qy,qz,tab1,tab2,tab3,tab4,roll_deg,rssi
```

(`flags`: bit 0 TVC active, 1 parachute released, 2 new barometer sample, 3 GPS fix, 4 abort, 5 fin tabs active,
6 fin tabs parked after a coast give-up;
`state`: 0 BOOT, 1 CALIBRATING, 2 READY, 3 BOOST, 4 COAST, 5 DESCENT, 6 LANDED, 7 ERROR; `rssi`: the radio signal at
the rocket in SiK units, dBm ≈ rssi / 1.9 − 127, 0 = no radio report; logs from firmware before 3.00 have no `rssi`
column and load the same way).

## Rebuild

```bash
python3 ground/make_demo_flight.py
```

```bash
python3 ground/build_offline.py
```
