# Pre-flight checklist (print this)

**Night before**
- [ ] LiPo(s) balance-charged to 8.4 V **outside the rocket** (charger on a fire-proof surface, never unattended)
- [ ] Camera battery charged, microSD empty
- [ ] Laptop charged (it runs Mission Control for the whole session); ground radio and its antenna packed; Mission
      Control offline file (`ground/kestrel_mission_control.html`) on the laptop, opened once in Chrome or Edge
- [ ] `status`: IMU / baro / flash ok, axes calibrated, correct motor selected, `tabs` setting as planned for this
      flight (test plan C), log has > 1 MB blank
- [ ] Last flight's log downloaded and plotted
- [ ] `dirtest`, `tabtest`, `fintest` all correct (after any change to a servo, horn, pushrod or tab)
- [ ] Gimbal pivots free, no play; TVC pushrods straight; every tab swings freely with its root pin in its slot and
      lines up with its fin after `center`; tape over the four fin-tip lead grooves intact
- [ ] Latch bolt slides freely (graphite); spring, piston, shock cord, parachute: no burns, knots or frays
- [ ] Payload secured to the bay floor, door locks with a quarter turn
- [ ] Four legs on and their M3 screws snug; no crack at the top of any post or round any fin tip (servo housing)
- [ ] Battery hatch: door lies flat with no gap, latch locks (coin slot horizontal)
- [ ] Camera door: lies flat, latch locks (coin slot horizontal), lens port clean; radio held firmly by its two cable
      ties, antenna screwed on straight up
- [ ] `radio` (USB): the radio reports in (its own link report), the airtime used in the last hour is low
- [ ] Field: club launch or landowner permission confirmed; not near an airfield or in controlled airspace (see
      [SAFETY_AND_LEGAL.md](SAFETY_AND_LEGAL.md))
- [ ] Pack: rocket, pad + rod (1 m, and the 1.5 m rod if it may be windy) + tile + pegs + rod cap, motors **and the
      matching retainer** (F35 retainer; or the 24 mm sleeve, 24 mm retainer and D spacer), launch controller + key, LiPo + spare,
      laptop/phone + **angled** micro-USB cable, coin (payload door and battery hatch), toothpick (switch), tools,
      tape, **2 spare legs + 2 M3 × 18 button-head screws and nuts + hex key**, spare M3 / M2.5 screws and M2 × 6
      servo screws (never longer).
      No wadding: there is no ejection charge

**At the field**
- [ ] Wind measured: **≤ 3 m/s for flights 1 and 2**, ≤ 6 m/s afterwards (use the 1.5 m rod above 3 m/s), never
      above 9 m/s, and no more than the recovery area allows (F35: about 46 m of drift per 1 m/s). Note the direction
      and **type the wind into Mission Control's Landing prediction panel** (speed, and the direction it comes from)
- [ ] Pad set up and pegged, rod tilted 0–5° **downwind** only, tile on, dry grass around the pad cleared
- [ ] Recovery area clear downwind: F35 ≈ 500 m (wind up to 6 m/s) or 250 m (wind 3 m/s or less);
      E20 150 m; D20 50 m. The predicted landing point (Mission Control) is inside it
- [ ] Ground radio on the laptop, Mission Control → **Connect radio**; at most three `radio test` range checks in the
      hour before the flight (test plan B5)

**Preparing the rocket**
- [ ] Motor: **"-0" plugged motor**, the type selected with the `motor` command (F35 = `motor 5`, E20 = `motor 2`,
      D20 = `motor 0`)
- [ ] F35: motor pushed up into the holder against the penny washer, **F35 retainer** (22 mm opening) pushed up and
      twisted 45° until it clicks. E20 / D20: **adapter sleeve** in first (D20: **D spacer** in the sleeve above the
      motor), then the motor, then the **24 mm retainer** (16 mm opening)
- [ ] Payload in, **door locked** (cam arm up)
- [ ] Charged pack in through the battery hatch, PH plug pushed home, **hatch locked** (coin slot horizontal)
- [ ] Parachute packed, spring and piston in, cord coiled on top
- [ ] Board ON (latch locks), nose cone pushed on until the bolt **clicks**; gentle pull test; board OFF to carry
      it to the pad
- [ ] Camera recording, lens clean, **camera door locked** (coin slot horizontal)
- [ ] Balance point ≤ 640 mm from the nose tip

**On the pad**
- [ ] Rocket on the rod, standing on its four fin feet on the tile, slides freely on the rod
- [ ] Every tab in line with its fin, nothing touching the tabs or the nozzle
- [ ] Power switch ON through the slot (toothpick), only once the rocket is on the rod: a sharp jolt while READY
      can look like a launch
- [ ] Leave it **still**: green LED blinking (calibrating) → solid + **double chirp every 3 s = READY**
- [ ] Mission Control shows the rocket on the air: state READY, frames arriving, "At the rocket: hears this
      station", GPS fix, battery and servo rail as expected, the right motor
- [ ] No red LED. Red slow blink = check `status` before going on
- [ ] Igniter in (launch controller **key out**), clips on, everyone back to **40 m for an F35** (30 m for a D20 / E20)

**Launch**
- [ ] Range clear, sky clear (no aircraft), RSO / LCO go
- [ ] Key in, continuity OK, loud countdown 5–4–3–2–1, launch
- [ ] Misfire: key out, **wait 60 s** before approaching

**Recovery**
- [ ] Watch it all the way down; note where it lands. Mission Control shows the predicted and then the last
      position: **Copy position** puts it on the clipboard for a phone map
- [ ] Follow the beeps; the digits are the apogee in metres
- [ ] Once found, switch OFF (stops the beeping; the log is already safe in flash)
- [ ] Spent motor out once cool; download the log (USB through the battery hatch: **Get log over USB** in Mission
      Control merges it with the radio recording); inspect the legs (crack at the
      top of a post: swap the leg, one screw), the fin tips round the servo housings (a crack there: no more flights
      until the fin can is repaired), tabs, gimbal, latch and the nose ballast (no loose nuts rattling); note the
      flight in the notebook
- [ ] **Next flight** (no tools beyond a coin and a hex key): open the hatch, unplug and slide out the pack, slide in
      a charged one; swap any cracked leg; new motor; repack the parachute; start again at "Preparing the rocket"
