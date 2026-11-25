# Build guide (KESTREL-2, no soldering)

Everything electrical is either assembled by JLCPCB or plugs together: servo plugs, the Pico 2 WH on its sockets,
the LiPo balance plug, the U.FL antenna lead. You will print, cut, drill, glue and screw.

The rocket comes apart into **three parts**:

| Part | What is in it |
|---|---|
| **1. Bottom** | fin can (4 normal 4 mm fins with a 15 mm band along the bottom that holds the tab servo, 17 mm round the servo, and a control tab at the trailing edge), 4 replaceable legs bolted under the fin tips, the TVC module (motor gimbal + 2 servos), the camera pod, the avionics bay (flight computer, battery behind a hatch, GPS antenna) and its coupler |
| **2. Middle** | payload bay with a hinged, lockable door · a wall · the parachute bay (spring, piston, parachute, shock cord) · the release latch with its servo at the very top |
| **3. Nose cone** | printed, with about 46 g of ballast (M3 nuts set in epoxy) in its tip; the spring pushes it off when the release servo pulls the latch bolt |

Time: roughly 35 h of printing for the rocket, 20 h for the launch pad and 6 h for the two drill guides
(estimates from the part volumes, depending on your printer), plus two weekends of building. **Order the PCB
first**: it takes 1–3 weeks to arrive.

Pictures that help: `cad/renders/rocket_exploded.png` (all parts), `tvc_module.png` and
`tvc_module_assembly_steps.png` (TVC), `avbay_cutaway.png`, `release_latch_cutaway.png`, `payload_bay_open.png`,
`fin_tab_closeup.png`, `fin_servo_cutaway.png` (a fin cut open: servo, horn, tab, lead), `launch_pad.png`. Open
`cad/kestrel.blend` in Blender 4 to turn any part around: scene 1 shows the complete rocket, the same rocket cut
open with everything inside it, and every part laid out on its own with its name; the scene list (top right) has
the exploded view, the cut-aways, the open payload door, the deflected tabs, a fin cut open and the rocket on its
launch pad. `cad/kestrel_rocket.blend` holds just the constructed rocket, grouped by section; hide its "Body tubes"
collection to see everything inside.

## Orientation words

Look down on the rocket from the nose. Angles go **anticlockwise**, exactly as in the CAD and the firmware:

| Angle | Name used below | What is there |
|---|---|---|
| 0° | **door side** | payload door (middle part), one av-bay screw |
| 45° | **fin 1** | the fin with a small raised **pip** near its root, on both faces |
| 90° | **lug side** | the two launch lugs (the upper one on the middle part), one middle-part joint screw, one tail screw, the **battery hatch** |
| 135° | fin 2 | |
| 180° | | the other av-bay screw; inside: the release-servo lead |
| 225° | fin 3 | |
| 270° | **camera side** | camera pod, the other joint screw |
| 315° | fin 4 | |

Each fin is a normal **4 mm fin** with a half-round leading edge. Only its **bottom band** (the 45 mm next to the
tail) is **15 mm thick**: it holds the tab's hinge, the tab servo (in a pocket open at the fin tip, its output shaft on
the tab's hinge line, so it turns the tab directly: no pods, pushrods or hinge pins) and the servo lead's channel. A
smooth 15° wedge joins the band to the thin fin, and the band and the tab taper to thin edges below the tail, so
nothing blunt faces the airflow. Round the servo the band is **17 mm** (the **servo housing**): its walls carry every
landing load on the leg, so they are 2.2 mm thick. Under each fin tip a solid **tongue** carries a **replaceable leg**
(section 5). KESTREL-2 is built to fly again and again: a hard landing breaks a 5 g leg, not the fin can.
**Up** = towards the nose. All sizes in mm.

---

## 1. Order the flight computer

Follow [PCB.md → Ordering from JLCPCB](PCB.md#ordering-from-jlcpcb): upload
`pcb/production/kestrel_fc_gerbers_jlcpcb.zip`, the BOM and the CPL file, 5 boards with assembly on 2.

## 2. Print the parts

All STLs are in `cad/stl/`, **already in print orientation: print them exactly as they load**. `cad/stl/check_report.md`
lists sizes, estimated masses and the automatic printability checks: all 35 parts are watertight, one body each,
and fit a 220 × 220 × 250 mm bed. The same report measures every overhang in that orientation. Only **three parts
need support material** (marked below); everything else is built from 45° slopes and short bridges. Print the rocket
in **PETG** (PLA softens in a hot car and near the motor), except the four legs: **tough PLA**, printed solid.

| Part | Qty | Settings | Notes |
|---|---|---|---|
| **Bottom part** | | | |
| `fin_can` | 1 | upside down (top ring on the bed), 3 walls, 20 %, **100 % infill for the last 13 mm** of the print (a height-range modifier in the slicer: that is the four leg tongues), no supports | can, 4 fins (4 mm, with the 15 mm bottom band, 17 mm round each servo, holding the servo pockets and lead channels) and the four tongues the legs bolt onto; the largest print (124 × 124 × 137 mm). The 2.2 mm walls beside each servo pocket must come out solid: 3 walls or more |
| `fin_leg` | 4 + 2 spares | **tough PLA, 100 % infill**, sleeve rim on the bed as exported, no supports | the replaceable legs. The top of the 6 × 9.2 mm post is the **designed weak point**: print them solid and in this orientation, or a leg may not break before the fin can it protects |
| `fin_control_tab` | 4 | standing on its outer end (horn pocket on the bed), 3 walls, 20 %, no supports | |
| `tvc_frame` | 1 | upright, 3 walls, 25 %; **supports under the four servo bars** | |
| `tvc_motor_holder` | 1 | upright, **4 walls, 30 %, PETG or ASA** (never PLA: motor heat); **support under the pushrod tab** | the 25 mm roof of the motor bore is a bridge; the penny washer covers it |
| `tvc_gimbal_ring`, `tvc_motor_retainer` | 1 each | 3 walls, 40 % | the retainer with the **22 mm opening** holds the 29 mm F35 |
| `tvc_motor_adapter_24mm`, `tvc_motor_retainer_24mm`, `tvc_motor_spacer_D` | 1 each | upright, 3 walls, 30–40 %, PETG | only for the 24 mm test motors (D20, E20): a sleeve that turns the 29 mm motor bore into a 24 mm one, its own retainer (16 mm opening) and a 25 mm spacer that sits above the shorter D20. Print them in a different colour from the F35 retainer so the two retainers cannot be mixed up |
| `avbay_coupler` | 1 | **upside down** (bulkhead on the bed), 4 walls, 25 % gyroid | its bulkhead is the payload-bay floor and carries the parachute load path |
| `avbay_sled` | 1 | bulkhead disc on the bed, 3 walls, 20 % | its battery pocket opens towards the battery hatch |
| `camera_pod` | 1 | floor and flange on the bed, 3 walls, 20 %, no supports | |
| `battery_hatch_door` | 1 | standing on its bottom edge as exported, **with a brim**, 3 walls, 20 %, no supports | its outer face is what you see: print it in the rocket's colour |
| `battery_hatch_latch_knob`, `battery_hatch_latch_cam` | 1 each | as exported; 100 % infill | small: print several and keep the best |
| **Middle part** | | | |
| `payload_wall` | 1 | disc on the bed, skirt up, 3 walls, 25 % | carries the parachute load |
| `spring_piston` | 1 | flat face on the bed, 3 walls, 20 % | |
| `payload_door_frame` | 1 | upright, 3 walls | |
| `payload_door` | 1 | standing on its hinge end, **with a brim** | |
| `payload_door_latch_knob`, `payload_door_latch_cam` | 1 each | knob head-down; 100 % infill | small: print several and keep the best |
| `top_latch_insert` | 1 | shoulder up, 3 walls, 25 % | |
| `upper_launch_lug` | 1 | 3 walls | glued to the middle tube (section 8) |
| `latch_bolt` | 1 | 100 % infill | must slide freely: rub it with graphite (soft pencil) |
| **Nose** | | | |
| `nose_cone` | 1 | tip up, 3 walls, 10 % gyroid, no supports | its bulkhead is a 45° cone with a cord bar inside and a 14 mm ballast fill hole at its top |
| **Launch pad** | | | |
| `pad_hub` | 1 | upright, 5 walls, 40 %; **tree supports in the leg sockets** | |
| `pad_rod_block`, `pad_rod_stop`, `rod_tip_safety_cap` | 1 each | 4 walls, 40 % | |
| `pad_leg_foot` | 3 | 4 walls, 40 % | |
| `pad_tile_clamp` | 4 | 100 % | |
| **Build tools (not flown)** | | | |
| `tool_drill_guide_bottom_tube`, `tool_drill_guide_middle_tube` | 1 each | 2 walls, 10 % | |

Printed rocket parts ≈ **420 g** (the fin can alone is ≈ 164 g, the four legs ≈ 19 g). The simulator uses the masses computed from
these exact STLs with these settings (`cad/mass_properties.py`), so print them as listed.

## 3. Body tubes

1. Cut two Estes BT-70 tubes (495 mm long): **bottom tube 340 mm**, **middle tube 380 mm**. Wrap a strip of
   paper round the tube as a straight-cut guide, use a fresh blade, sand the ends square.
2. **Bottom tube**: slide `tool_drill_guide_bottom_tube` over the **top** end until its lip sits on the tube
   end. Through the guide:
   - 2 × 3.3 mm holes, door side and 180°: av-bay screws;
   - 3 × 2 mm holes: barometer static ports (keep them clean and round: they set the altitude reading);
   - the 7 × 20 mm slot at about 204°: power switch and status LEDs;
   - the 27 × 30 mm camera window on the camera side (drill the corners, cut with a knife);
   - the **26 × 78 mm battery-hatch opening** on the lug side: cut along the guide's edges with a fresh blade. The
     door overlaps it by 2 mm all round, so the cut only has to be straight;
   - pencil along the groove on the lug side: the launch-lug line.
3. **Middle tube**: slide `tool_drill_guide_middle_tube` over its **bottom** end (lip on the tube end):
   - 2 × 3.3 mm holes on the lug and camera sides: the joint screws;
   - the 32 × 50 mm payload-door window on the door side;
   - pencil along the groove on the lug side: the upper-lug line.
4. The tail holes (2 × 3.3 mm, 16 mm from the bottom end) and the four tab-servo lead slots in the bottom
   tube are marked through the fin can later (section 5).
5. Seal all cut edges with thin CA. Sand the printed outside surfaces (240, then 400 grit), filler primer, paint.
   The drag model assumes this "regular paint" finish; an unpainted, rough rocket flies a few metres lower.

## 4. TVC module (bottom of the rocket)

It is a separate unit (`cad/kestrel_tvc_module.blend`): frame, gimbal ring, motor holder, retainer, two servos
and two pushrods. **Its two servo leads come out of the top**, straight up to the flight computer. The motor
holder takes the **29 mm TSP F35**; the 24 mm D20 and E20 for the test flights go into it in the printed adapter
sleeve (section 12).

1. **Burn-through shield:** push an M10 × 25 mm steel penny washer up the motor bore into the recess at its closed
   (top) end and fix it with a dab of epoxy: it shields the plastic from the motor's hot forward end.
2. **Holder → ring:** put the holder inside the gimbal ring. An M3 screw through each of the ring's two
   side holes (the ones with 3.3 mm clearance) threads into the holder's bosses. Tighten until there is no play,
   then back off a quarter turn: the holder must swing freely.
3. **Ring → frame:** set the ring between the frame's two pivot posts. An M3 screw through each post threads
   into the ring's other two bosses; same feel. The holder now tilts ±7° in every direction without touching
   anything (the CAD checks this all round the circle).
4. **Servos:** screw the two MG90S into the frame bars with the screws from the servo bag. **Lower servo = TVC
   ring = port 1. Upper servo = motor holder = port 2.** Put a piece of tape with the port number on each lead.
   Do not fit the horns yet.
5. Centre the servos: plug them into ports 1 and 2 of the board and type `center` (flash the board first: section
   10, steps 1–2; a USB cable powers the logic, but the servos need the LiPo on the balance socket). Now fit a
   single-arm horn on each, pointing towards its pushrod, with its hole **9 mm** from the shaft (trim the arm 2.5 mm
   beyond the hole). If no hole sits at exactly 9 mm, drill one with a 1.3 mm bit: the firmware's linkage maths
   (the gimbal moves 9/22 = 0.41° per servo degree) depends on it. The same goes for the 7 mm release horn below.
6. **Pushrods:** 1.2 mm music wire with a Z-bend at each end (pliers only). Each one runs straight down from its
   horn to the hole in the round boss on the ring (ring servo) or on the holder's arm (holder servo), 2 mm
   further out from the middle than the horn itself, so the Z-bends point inwards. Bend one end, hook it into the
   horn, mark the length so the motor holder hangs perfectly straight with the servos centred, bend the other end.
7. Route both leads up through the frame and out of its top. That completes the module.

## 5. Fin can, tab servos and control tabs

Each fin carries its own tab servo inside its 15 mm bottom band (`fin_servo_cutaway.png`): the servo slides into a
pocket that is open at the fin tip, its output shaft pointing in towards the rocket along the tab's hinge line, and its spline
goes straight into a servo horn glued inside the tab. The tab turns exactly as far as the servo does.

1. **Horns into the tabs:** take a single-arm horn from each tab servo's bag and cut its arm off **about 7 mm
   from the centre of the hub**, leaving a short stub. Trial-fit it in the pocket at the tab's **outer end** (the
   end without the printed pin): hub in the round pocket (it takes a hub up to 7.6 mm across and 5 mm long), stub
   in the slot that points towards the tab's thin trailing edge, hub face flush with the end of the tab. If your
   horn is bigger, file the stub or the hub until it sits flush. Smear a little Vaseline inside the horn's splined
   bore (it keeps the glue out), epoxy the horn in, and wipe the bore clean when the epoxy has cured.
2. **Fin can on the tube:** slide the fin can over the bottom end of the bottom tube with its launch lug on the
   pencilled lug line, until the tube end is flush with the bottom of the can ring. Through the fin can, mark and
   drill the two 3.3 mm **tail holes** (16 mm from the end, lug side and 210°) and cut the **four lead slots**
   in the tube with a knife: mark them through the 9 × 5 mm lead hole in the can at the root of each fin, 38.5–43.5
   mm above the tail.
3. **Tabs in:** push each tab up into the gap at the trailing edge of its fin, **printed pin first into the slot
   at the fin root**, until its rounded front edge sits in the round top of the gap and the horn's bore lines up
   with the servo pocket. Its thin trailing edge then reaches 12 mm below the tail, level with the tapered edge of
   the band beside it. The pin only stops the tab moving sideways; the servo spline carries it.
4. **Tab servos:** centre each servo first (plug it into the board, `center`). Push its plug, then the lead, into
   the **lead channel** in the fin tip (the 9 × 5 mm hole 38.5–43.5 mm above the tail), through the fin and the
   slot in the tube, and pull the lead into the tube. Then slide the servo into its pocket from the fin tip,
   **output shaft first**, so the spline enters the horn in the tab. Hold the tab in line with the fin while the
   spline engages and pick the tooth that leaves it straightest; the trim (section 10) takes out the rest.
5. **Servo screws:** fix each servo with **2 × M2 × 6 mm self-tapping screws** through its mounting tabs,
   reaching in through the open fin tip. **Not longer than 6 mm** (servo bags often hold longer ones): the lower
   hole ends 0.35 mm short of the tab gap, and a longer screw would break through and jam the tab.
6. **Leads:** lay each lead in the groove in the fin tip, from the servo up to the channel, and put a strip of
   tape over the tip. (The groove is placed for a lead that leaves the servo case at the end away from the output
   shaft. If yours leaves at the shaft end, bring it out of the bottom of the pocket and up the fin tip under the
   tape instead.) Label the leads: **fin 1 = port 4, fin 2 = port 5, fin 3 = port 6, fin 4 = port 7**. Fit a
   300 mm extension lead to each and pull all four up and out of the top of the bottom tube. With the board on,
   `servo 4 1343` and `servo 4 1657` (±15° of tab) must swing tab 1 freely each way without touching the fin;
   the same for servos 5–7.
7. **TVC module in:** slide the TVC module into the bottom of the tube, **its two leads first**, turning it until
   its two tail-screw nut pockets line up with the tail holes. Each tab-servo lead lies in the groove on the
   outside of the frame that sits right behind its slot; pull the leads gently from the top as the module goes
   in so none gets pinched. Push an M3 nut into each nut pocket (a dab of glue holds it), then fix the fin can,
   tube and module with **2 × M3 screws**. No glue: the TVC module and the fin can come off for repairs and
   modifications.
8. **Legs:** slide a leg up over the tongue under each fin tip, sleeve first, until it sits against the band. One
   side of the sleeve has a round recess, the other a hex recess: put an **M3 nut** in the hex recess, push an
   **M3 × 18 button-head screw** through from the round side and tighten it until snug (the nut cannot turn, so one
   hex key does it). The rocket now stands on its four legs. The top of each leg's post is built to be the weakest
   point of the whole tail: after a hard landing the leg breaks there and the fin can and servo are untouched. A new
   leg is a one-screw swap: keep two spare legs and two spare screws and nuts in the field box.

## 6. Camera pod

Push the pod through the 27 × 30 mm window from outside and glue its saddle flange to the tube (epoxy). Foam-pad
the camera into the pocket, lens in the floor hole looking down. The lens axis sits 1.5 mm outside the tube, so
the body fills one edge of the picture; the rest is ground, fins and sky.

## 7. Avionics bay

The av-bay is the **coupler** (a tube with a bulkhead on top: the payload-bay floor) with the **sled** inside it.

1. **Board on the sled:** 4 × M2.5 × 8 self-tapping screws into the standoffs. The servo headers point down
   (towards the tail), the U.FL GPS connector up.
2. **Pico 2 WH** into its two sockets, USB connector up (as printed on the board).
3. **GPS antenna:** stick the 15 × 15 mm patch, **ceramic side up**, on the U-shaped platform at the top of the
   sled (double-sided tape on the two arms and the back bar). Its lead goes down through the open middle of the U to
   the board's U.FL connector: push the plug on straight until it clicks. The platform sits beside the Pico's USB
   socket, so a USB cable still plugs in.
4. **Battery lead:** plug the PH → XH adapter lead (Overlander OL-2529) into the 3-pin JST-XH socket marked
   `BATT 2S` (it only fits one way). It stays in the rocket; the pack itself goes in last, through the battery
   hatch (step 9). Check the pack measures about 40 × 19 × 15 mm (the pocket takes up to 16 mm; one shop lists
   this pack as 25 mm thick, which would not fit). The board runs from the balance plug; the pack's main lead is
   not used: tape its end.
5. **Release-servo extension:** plug a 300 mm extension into **port 3** and pass its free end up through the slot
   in the coupler bulkhead.
6. Push an M3 nut into each of the two pockets at the bottom of the sled. Slide the sled into the coupler from
   below; the slot in the coupler wall must line up with the power switch and the LEDs.
7. Feed the six servo leads coming up out of the bottom tube (TVC 1–2, tabs 4–7) through the big hole in the sled
   disc and plug each into its numbered port (signal wire, orange/yellow, towards the board edge marked `S`).
8. Slide the coupler (with the sled) into the top of the bottom tube until its band sits on the tube end, the
   small notch in the band on the lug side. Fix it with **2 × M3 radial screws** (door side and 180°) through tube
   and coupler into the sled's nuts. Through the switch slot you can now see the green/red LEDs and reach the
   power switch with a toothpick.
9. **Battery hatch:** press the latch **cam** onto the knob's square end (knob pushed through the door from
   outside, a drop of CA) so that the cam arm points **down when the coin slot is horizontal**: horizontal =
   locked, vertical = open. Stick a 20 × 20 mm piece of the foam tape on the pad inside the door. Slide the pack
   through the hatch into its pocket behind the Pico (it rests on the ledge at the bottom), push its small PH
   plug into the adapter lead and tuck the joined plugs beside the pack, where your fingers reach them. Fit the
   door: hold it with the bottom tilted out, put its two hooks into the top of the opening, slide it up so the
   hooks go behind the coupler wall, swing the bottom in and turn the slot horizontal with a coin. The door sits
   on the tube and overlaps the opening by 2 mm all round, so there is no gap anywhere and nothing stands proud
   on the rod side (the rod passes 1.3 mm above it).

**Between flights (no tools, nothing taken apart):** open the hatch, unplug the PH plug and slide the pack out;
slide a charged pack in. Charge the flat one **outside the rocket** on a second OL-2529 adapter that lives with
the charger. The Pico's own USB socket is just above the pack: plug in an angled micro-USB cable (the cable must
leave the plug towards the hatch: see the shopping list) to download the log or change settings.

To take the av-bay out for repairs: remove the hatch door and the middle part (section 8), remove the two av-bay
screws and slide the av-bay up out of the tube. The tab extensions give the leads enough slack.

## 8. Middle part: release latch, wall, payload bay, joint

1. **Top latch insert:** glue the insert into the **top** of the middle tube (36 mm deep, shoulder sticking out),
   its alignment rib on the door side.
2. **Release servo:** centre it (`center`), screw it onto the two posts inside the insert, shaft up. Fit the
   single-arm horn, hole **7 mm** from the shaft. Put the **latch bolt** into its guide with the **bevel facing
   up**. Link the bolt to the horn with **0.6 mm music wire bent with a small U-kink in the middle**: the kink makes
   the link a spring. In the locked position the servo holds the bolt out with the kink slightly compressed; when
   you push the nose cone on, its chamfered edge pushes the bevelled bolt in and it snaps out into the nose's hole.
   At apogee the servo pulls it in.
3. **Release lead:** run the servo lead down the inside of the middle tube on the 180° side and tape it flat in
   three places.
4. **Wall:** thread the **Kevlar shock cord** through the bridge on top of the wall and tie it (double fisherman's
   knot, then a drop of CA on the knot). Slide the wall into the middle tube from the bottom, **bridge and skirt
   up**, with the release lead lying in the notch in its edge, until its flat underside is **160 mm** from the
   bottom end of the tube (use a stick marked at 160 mm as a depth gauge). The payload bay below it is then 130 mm
   tall. Epoxy the skirt all round: it carries the parachute load.
5. **Payload door:** epoxy the door frame inside the tube behind the door window, its hinge knuckles at the
   bottom. Fit the door with a 22 mm piece of 1.75 mm filament as the hinge pin (melt or glue the ends). Push the
   **latch knob** through the door from outside and press the **latch cam** onto its square end from inside with
   a drop of CA. Turn the knob with a coin: **cam arm up = locked**, sideways = open.
6. **Joint:** push an M3 nut into each of the two pockets inside the coupler shoulder (lug and camera sides).
   The middle tube slides down over the shoulder until it meets the band; fix it with **2 × M3 screws** through
   the joint holes. Before closing it, plug the release servo's lead onto the 300 mm extension coming up through
   the floor; the joint between them sits in the payload bay against the back wall (tape it there).
7. **Upper launch lug:** with the rocket assembled, glue the upper lug on the middle tube's lug line, just above
   the joint screw (363 mm above the tail). Slide both lugs onto the 6 mm rod while the epoxy cures, so they are
   perfectly in line; afterwards the joint's alignment notch keeps them in line every time you reassemble. (It sits
   on the middle part because the battery hatch now takes its old place.)

The payload sits on the floor of the bay: 4 × M3 holes on a 20 mm square to screw a payload down. Up to **50 g**
is allowed (the simulator flew the whole 0–50 g range).

## 9. Recovery

0. **Nose ballast (once):** the thick servo bands, the replaceable legs and their bolts put weight at the tail, so
   the nose carries **about 46 g of ballast**: roughly 130 M3 nuts (0.33 g each, two 100-packs) and 3 ml of epoxy. Hold the nose cone tip-down and
   pour the nuts in through the 14 mm hole at the top of its conical bulkhead (beside the cord bar); they settle
   into the tip. Tape over the hole for now and do the balance check (section 12) **with the payload bay empty**,
   adding or removing nuts until it passes. Then, still tip-down, pour 3 ml of 30-minute epoxy through the hole
   onto the nuts and leave it tip-down until it has cured. Leave the hole open afterwards: it also lets the nose
   breathe.
1. Shock cord: Kevlar from the wall's bridge (step 8.4), up through the notch in the **spring piston**,
   30 cm of Kevlar, the elastic section, a swivel with the **parachute's shroud lines**, then on to the bar inside
   the nose cone's conical bulkhead (reach in from the open end with long tweezers, tie a bowline, then a drop of CA).
2. Put the **spring** on the wall's spring boss, the **piston** on the spring (its notches over the release lead
   and the cord), fold the 36 in parachute (Z-fold, then roll it to about 44 mm across and 90 mm long) and put it on
   the piston, coil the cord on top.
3. **Power the board** (the latch is commanded locked from the first instant), then push the nose cone on
   (alignment groove over the insert's rib) until the bolt **clicks**. Pull gently: it must not come off.
4. On the bench, `deploy release` must make the spring throw the nose cone clear and pull the parachute out.
   Do this **ten times** before the first flight (test plan A13).

## 10. Firmware and set-up (USB, no tools needed)

1. Hold **BOOTSEL** on the Pico, plug in USB, drag `firmware/pico/kestrel_fc.uf2` onto the `RP2350` drive.
2. Open a serial terminal (PuTTY, the Arduino serial monitor, or
   `python firmware/tools/kestrel_link.py shell --port COMx`). Type `help`.
3. `status`: IMU, barometer and log flash must say `ok`; outdoors the GPS gets a fix within a few minutes.
4. **`calaxes`, required once:** the firmware measures how the board sits in the rocket instead of trusting the
   drawings. Pose 1: rocket standing on its fins on a level table. Pose 2: lying on its side with the **camera
   pod pointing straight down** (it rests on fins 3 and 4). Then `save`. Without this the board refuses to arm.
5. **`dirtest`:** servo 1 moves +3°: the nozzle must swing **away from the camera pod**; then servo 2: away from
   the **door side**. Wrong way? `dir 1 -1` (or `dir 2 -1`), `save`, repeat.
6. **`tabtest`:** tabs 1–4 move to +10° one after the other. Look at the tail from behind (nozzle towards you):
   each tab's **trailing edge must swing anticlockwise**, towards the fin with the next-lower number (tab 1
   towards fin 4, tab 2 towards fin 1). Wrong way? `dir <4-7> -1` (tab 1 = servo 4), `save`, repeat.
7. **Trims:** `trim <1-7> <µs>` until, after `center`, the motor holder hangs perfectly straight and every tab
   lines up with its fin.
8. **`deployus <lock> <release>`:** set the latch pulse widths so that at "lock" the bolt stands fully out with
   the U-kink just compressed, and at "release" it is fully in, without the servo straining (a straining servo
   hums). `save`.
9. **`tvctest`:** hold the rocket upright until it says "locked", then tilt it slowly: the nozzle must swing
   **opposite** to the way the nose leans, like balancing a broom on your hand.
10. **`fintest`:** hold it upright and still for 2 s, then twist it about its long axis: all four tabs swing the
    same way to twist it back. Tilt it: the tabs push the nose back up.
11. Choose the motor: `motor` lists them, `motor 5` selects the TSP-F35 (the mission; the TVC gains and the backup
    deploy timer depend on it), `motor 0` the TSP-D20 for the first hops and `motor 2` the TSP-E20 for the second
    test flights. `save`.

## 11. Launch pad

1. Cut the 22 mm dowel into 3 × 600 mm legs and push them into the hub sockets (M3 pin screws through the
   side holes), feet on the other ends.
2. Bolt the rod block into the hub slot with the M6 bolt and wing nut. The marks on the hub show 0/5/10/15° of
   tilt. In wind, tilt 0–5° **downwind** (never towards people).
3. Clamp the 6 mm rod in the block with the M4 thumb screw. Fix the 200 mm ceramic tile on the hub with the four
   corner clamps (M4).
4. The rocket stands on its four fin feet on the tile, the rod through both lugs, nozzle 26 mm above the tile.
   On a tilted rod, slide the rod stop up under the lower lug so the feet just clear the tile.
5. Tent pegs through the three feet. **Rod-tip cap on whenever there is no rocket on the rod.**

## 12. Loading a motor and the balance check (every flight)

Always **"-0" (plugged) motors**. Check that the penny washer is still in the top of the motor bore.

- **TSP F35 (29 mm, the mission):** push the motor up into the holder until it stops, then push the **F35
  retainer** (22 mm opening) up over the holder's two lugs and turn it 45° until it clicks. `motor 5`.
- **TSP E20 / D20 (24 mm, test flights):** slide the **adapter sleeve** into the holder first. For a D20 (70 mm
  long) drop the **D spacer** into the sleeve first so that the motor sits against the washer. Push the motor up
  into the sleeve, then fit the **24 mm retainer** (16 mm opening) the same way. `motor 2` for the E20, `motor 0`
  for the D20. Never fly a 24 mm motor without its sleeve and retainer: the F35 retainer's opening is too big to
  hold it.

With the motor in, the parachute packed and the payload loaded, balance the rocket on a finger or a string:
**the balance point must be no further than 640 mm from the nose tip** (design with the F35 and the 46 g of nose
ballast: 634 mm with 25 g of payload, 638 mm with an empty bay, 631 mm with 50 g; stability margin +0.72 to +0.84
calibres at lift-off, +0.91 to +1.03 at burn-out, so it still flies if the TVC and tabs do nothing; with the E20 or
D20 in the adapter it balances 1–4 mm further forward). The empty bay with the F35 is the closest to the limit: if
it balances further back, add M3 nuts through the fill hole in the nose bulkhead and fix them with a few drops of
epoxy (section 9, step 0). A fin can or legs that print heavier than the estimated 164 g and 4 × 5 g need more
ballast; lighter ones need less.
