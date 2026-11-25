# KESTREL Mission Control

A ground-station screen for KESTREL-2: a 3D map of the launch range with the rocket flying on it, the flight
events as they happen (liftoff, burnout, apogee, parachute, landing), live telemetry, the steering (nose direction,
motor gimbal, the four fin tabs), the rocket's systems, strip charts, and a recorder that keeps every flight for
replay on the same 3D map.

| File | What it is |
|---|---|
| `kestrel_mission_control.html` | **Use this one at the launch field.** One self-contained file (three.js and the demo flight built in): works without internet, from a laptop or a USB stick. Open it in **Chrome or Edge** to use USB |
| `mission_control.html` | The page itself (loads three.js from a CDN and `demo_flight.csv` from beside it); also published as a private claude.ai page |
| `demo_flight.csv` | A simulated F35 flight (Monte Carlo seed 7: 161 m, 4.9 m/s wind, 20 g payload) flown by the real flight code, in the flight computer's log format. Made by `make_demo_flight.py` |
| `build_offline.py` | Builds `kestrel_mission_control.html` from the page, the demo flight and `vendor/three-r128.min.js` (three.js r128, MIT licence in `vendor/THREE_LICENSE`) |

## What it can show

- **Simulated live**: the demo flight streamed in real time, from the pad (calibrating, READY) through liftoff,
  burnout, apogee and the parachute to landing, exactly as a live link would feed it.
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

## Live during the flight: what is still missing

**The rocket has no radio link yet**, so today the live view works with the simulated flight, and with the rocket
on its USB cable on the bench or pad. During a real flight the screen fills in from the log after landing (Get log
over USB). To see a real flight live, the rocket needs a small telemetry transmitter and a receiver plugged into the
laptop by USB. Mission Control already accepts the receiver's lines: one line per sample in the log format,

```
t_ms,state,flags,gx_dps,gy_dps,gz_dps,ax,ay,az,alt_m,vz_ms,baro_alt_m,tilt_deg,gimbal_y,gimbal_z,vbat,lat,lon,gps_alt,sats,qx,qy,qz,tab1,tab2,tab3,tab4,roll_deg
```

(`flags`: bit 0 TVC active, 1 parachute released, 2 new barometer sample, 3 GPS fix, 4 abort, 5 fin tabs active,
6 fin tabs parked after a coast give-up;
`state`: 0 BOOT, 1 CALIBRATING, 2 READY, 3 BOOST, 4 COAST, 5 DESCENT, 6 LANDED, 7 ERROR). Choosing the radio is
an open decision: see the question in the work log.

## Rebuild

```bash
python3 ground/make_demo_flight.py
```

```bash
python3 ground/build_offline.py
```
