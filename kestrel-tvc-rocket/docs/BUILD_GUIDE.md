# Build guide (no soldering)

Everything electrical is either assembled by JLCPCB or plugs together (servo plugs, the Pico 2 WH on sockets,
the LiPo balance lead, the U.FL antenna). You will print, cut, drill, glue and screw.

Time: about 25 h of printing and two weekends of building. Do the steps in this order: the PCB takes 1–3 weeks
to arrive, so order it first.

Orientation words used below (they match the firmware and the CAD):

- **Fin #1** has a small raised pip near its root, on both faces. It sits 90° from the camera pod (the other two fins are 30° and 150° from it).
- **Up** = towards the nose.

---

## 1. Order the flight computer

Follow [PCB.md → Ordering from JLCPCB](PCB.md#ordering-from-jlcpcb). Upload `pcb/production/kestrel_fc_gerbers_jlcpcb.zip`,
the BOM and the CPL file. Order 5 boards with assembly on 2.

## 2. Print the parts

All STLs are in `cad/stl/` already in print orientation (`cad/stl/check_report.md` lists sizes, estimated masses
and the automated printability checks — all 20 parts pass: watertight, single body, fit a 220 × 220 × 250 mm bed).

| Part | Material | Settings | Notes |
|---|---|---|---|
| `nose_cone` | PETG or PLA | tip up, 3 walls, 10 % gyroid, no supports | |
| `avbay_coupler` | PETG | bulkhead on the bed, 4 walls, 25 % gyroid, no supports | the strongest part: carries the parachute load |
| `avbay_sled` | PETG | bulkhead disc on the bed, 3 walls, 20 % | |
| `latch_collar`, `latch_bolt_pos/neg`, `spring_piston` | PETG | 3 walls, 20 % | bolts must slide freely: rub with graphite / candle wax |
| `tvc_frame` | **PETG** | upright, 3 walls, supports only under the servo bars | |
| `tvc_motor_holder` | **PETG or ASA** (not PLA: motor heat) | upright, 4 walls, 30 % | press an M10 penny washer into the top recess with a dab of epoxy |
| `tvc_gimbal_ring`, `tvc_motor_retainer` | PETG | 3 walls, 40 % | |
| `fin_can` | PETG | upright (fins vertical), 3 walls, 20 % | |
| `camera_pod`, `upper_launch_lug` | PETG | 3 walls, 20 %, supports for the pod's lens hole | |
| `pad_hub` | PETG | upright, 5 walls, 40 %, tree supports in the leg sockets | |
| `pad_rod_block`, `pad_rod_stop`, `pad_leg_foot` ×3, `rod_tip_safety_cap` | PETG | 4 walls, 40 % | |
| `tool_drill_guide_lower_tube` | anything | lip down, 2 walls, 10 % | build tool, not flown |

Total printed rocket mass ≈ 214 g. The simulation uses the masses computed from these exact STLs.

## 3. Airframe tubes

1. Cut the BT-70 tube into **540 mm** (lower) and **250 mm** (upper). Use a paper wrap as a straight-cut guide
   and a fresh blade; sand the ends square.
2. Slide the **drill guide** over the TOP end of the lower tube until its lip sits on the tube end. Through the
   guide, drill/cut:
   - 2 × 3.3 mm holes: av-bay retention screws
   - 3 × 2 mm holes: barometer static ports (keep them clean and round: they set the altitude reading)
   - the 7 × 20 mm slot: power switch + status LEDs
   - the 27 × 30 mm camera window (drill the corners, cut with a knife)
   - the groove on the guide marks the launch-lug line: pencil it along the tube.
3. Seal the cut edges with thin CA. Sand all printed parts (240 then 400 grit), then filler primer. The drag
   model assumes this "regular paint" finish; a rough, unpainted rocket (60 µm) loses about 3–4 m of altitude.

## 4. TVC module (bottom of the rocket)

1. **Holder + ring:** put the motor holder inside the gimbal ring and fit the two M3 pivot screws through the
   ring's side holes into the holder bosses. Tighten until there is no play, then back off a quarter turn: the
   holder must swing freely ±7°.
2. **Ring + frame:** fit the ring between the frame's two pivot posts with two M3 screws, same feel.
3. **Servos:** screw the two MG90S into the frame brackets (screws supplied with the servos). Ring servo =
   **port 1** (lower servo), motor-holder servo = **port 2** (upper servo). Before fitting the horns, centre both
   servos: plug them into the board and type `center` (section 9).
4. **Pushrods:** 1.2 mm wire with a Z-bend at each end (pliers only). Horn hole about 9 mm from the servo shaft;
   trim the horn 2.5 mm beyond the hole. Set the length so the motor holder hangs straight with the servos at centre.
5. Run the two servo extension leads up along the tube wall (tape them in two places).
6. Slide the frame into the lower tube from the bottom and the fin can over the tube, with the fin can's launch
   lug on the pencilled lug line. Using the fin can's two holes (16 mm from the tail) as a guide, drill 3.3 mm
   through the tube, push an M3 nut into each of the two pockets inside the frame's tail ring (a dab of glue holds
   it), then fix the fin can, tube and frame with **2 × M3 screws**. No glue: the whole TVC module comes out for repairs and modifications.
7. Glue the upper launch lug on the lug line, 30 mm below the av-bay (slide both lugs onto the 6 mm rod while the
   epoxy cures so they are perfectly in line).

## 5. Avionics bay

1. **Board on the sled:** 4 × M2.5 × 8 self-tapping screws into the printed standoffs. The servo headers point
   down (towards the tail), the U.FL GPS connector up.
2. **Pico 2 WH** into the two sockets, USB connector up (matches the "USB ^ PICO 2 W" silkscreen).
3. **LiPo** in the tray, foam pad behind it, velcro strap through the two slots. Plug the balance lead into
   the 3-pin JST-XH socket (`BATT 2S`, it only fits one way).
4. **GPS antenna:** stick the 18 × 18 mm patch, ceramic side **up**, to the underside of the coupler bulkhead
   between the two servo posts; U.FL lead down to the board (push the U.FL on straight; it clicks).
5. **Deploy servo and snap-in latch:** screw the servo to the two posts hanging under the bulkhead, shaft up (the
   horn turns just below the bulkhead). Fit the two latch bolts in their guides, **bevel facing up**. Link each
   bolt to an end of the horn with **0.6 mm music wire bent with a small U-kink in the middle**: the kink makes the
   link a spring. In the locked position the servo pushes the bolts out with the kinks slightly compressed; the
   bevel lets the collar push a bolt in when you fit the upper section, and it snaps back out into the collar's
   pocket. At apogee the servo pulls both bolts in. Servo lead to **port 3**.
6. **Camera (optional AUX power):** if your camera powers from 5 V, its lead goes to **port 4** (`AUX/CAM`); the
   firmware switches it on when the rocket is armed. SQ12-type cameras run from their own battery: just start
   recording before you close the rocket.
7. Push an M3 nut into each of the two pockets at the bottom of the sled (they open towards the middle). Slide the
   sled into the coupler from below, servo leads for the TVC through the hole in the sled disc, and fix it with the
   **2 × M3 radial screws** (through the tube and the coupler into those nuts). Line up the slot in the coupler with the slot you cut in the tube: through it you can see the green/red
   LEDs and reach the power switch with a toothpick.

## 6. Recovery

1. Epoxy the **latch collar** flush with the bottom edge of the upper tube, notch aligned with the av-bay notch.
2. Shock cord: Kevlar tied to the bridge on top of the av-bay bulkhead, elastic section, swivel, then the
   parachute, then on to the nose cone's cord bar. Leave 30 cm of Kevlar between the av-bay and the elastic.
3. Spring on the bulkhead boss, piston on the spring, folded parachute on the piston (Z-fold, then roll), cord
   coiled on top, nose cone in (snug, not tight: the spring must be able to push the upper section off).
4. With the board switched on (latch locked), push the upper tube down over the coupler shoulder: the bevelled
   bolts give way and **click** into the collar. Pull gently: it must not come off. On the bench,
   `deploy release` must make the spring throw the upper tube + nose clear by at least 30 cm. Do this **ten
   times** before the first flight (see the test plan). To open the rocket without flying it, take out the two
   av-bay screws, slide the sled out, and use `deploy release` over USB.

## 7. Camera pod

Push the pod through the 27 × 30 mm window from outside, glue the saddle flange to the tube (epoxy), then foam-pad
the camera into the pocket with the lens in the floor hole looking down. The lens axis sits 1.5 mm outside the
body tube, so the tube fills one edge of the picture, the rest is ground and sky.

## 8. Launch pad

1. Cut the 22 mm dowel into 3 × 600 mm legs, push them into the hub sockets (M3 pin screws through the side holes).
2. Bolt the rod block into the hub slot with the M6 bolt + wing nut. The engraved marks on the hub show 0/5/10/15°
   tilt. Tilt **downwind** 0–5° in wind (the simulation's `rod_tilt5` case).
3. Clamp the 6 mm rod in the block with the M4 thumb screw. Put the ceramic tile / steel plate on the hub (4 × M4).
4. Slide the rod stop onto the rod so the rocket's nozzle sits **45 mm above the plate**.
5. Tent pegs through the three feet. **Rod-tip cap on whenever there is no rocket on the rod.**

## 9. Firmware and set-up (USB, no tools needed)

1. Hold **BOOTSEL** on the Pico, plug in USB, drag `firmware/pico/kestrel_fc.uf2` onto the `RP2350` drive.
2. Open a serial terminal (any: PuTTY, the Arduino serial monitor, or `python firmware/tools/kestrel_link.py shell --port COMx`).
   Type `help`.
3. `status`: IMU, barometer, log flash must say `ok`; GPS should get a fix outdoors within a few minutes.
4. **`calaxes`, required once:** the firmware measures how the IMU sits in the rocket instead of trusting the
   drawings. Pose 1: rocket standing nose-up. Pose 2: lying flat with the **camera pod pointing straight down**.
   Then `save`. Without this the board refuses to arm (red LED + fast beeps).
5. **`dirtest`:** servo 1 moves +3°: the nozzle must swing **away from the camera pod**; then servo 2: the nozzle
   must swing **away from fin #1**. Wrong way? `dir 1 -1` (or `dir 2 -1`), `save`, repeat.
6. **`trim 1 <µs>` / `trim 2 <µs>`** until the motor holder hangs perfectly straight with `center`.
7. **`deployus <lock> <release>`**: adjust so that at "lock" the bolts stand fully out with the U-kinks just
   compressed, and at "release" they are fully in, both without the servo straining (a straining servo hums). `save`.
8. **`tvctest`:** hold the rocket upright, wait for "locked", then tilt it slowly: the nozzle must swing
   **opposite** to the way the nose leans, like balancing a broom on your hand.
9. Choose the motor: `motor` lists them, `motor 2` selects TSP-E20 (the TVC gain schedule and the backup deploy
   timer depend on it). `save`.

## 10. Balance check (every flight)

With the motor in and the parachute packed, balance the rocket on a finger or a string: **the balance point
must be no further than 600 mm from the nose tip** (design: 587 mm with an E20, stability margin 1.36 calibres
even if the TVC does nothing). If it is further back, add modelling clay inside the nose tip.
