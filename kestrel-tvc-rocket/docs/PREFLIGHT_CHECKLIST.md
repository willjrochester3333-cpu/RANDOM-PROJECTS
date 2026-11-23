# Pre-flight checklist (print this)

**Night before**
- [ ] LiPo balance-charged to 8.4 V (charger on a fire-proof surface, never unattended)
- [ ] Camera battery charged, microSD empty
- [ ] `status`: IMU / baro / flash ok, axes calibrated, correct motor selected, `tabs` setting as planned for this
      flight (test plan C), log has > 1 MB blank
- [ ] Last flight's log downloaded and plotted
- [ ] `dirtest`, `tabtest`, `fintest` all correct (after any change to a servo, horn, pushrod or tab)
- [ ] Gimbal pivots free, no play; TVC pushrods straight; every tab swings freely with its root pin in its slot and
      lines up with its fin after `center`; tape over the four fin-tip lead grooves intact
- [ ] Latch bolt slides freely (graphite); spring, piston, shock cord, parachute: no burns, knots or frays
- [ ] Payload secured to the bay floor, door locks with a quarter turn
- [ ] Field: club launch or landowner permission confirmed; not near an airfield or in controlled airspace (see
      [SAFETY_AND_LEGAL.md](SAFETY_AND_LEGAL.md))
- [ ] Pack: rocket, pad + rod (1 m, and the 1.5 m rod if it may be windy) + tile + pegs + rod cap, motors **and the
      matching retainer** (F35 retainer; or the 24 mm sleeve, 24 mm retainer and D spacer), launch controller + key, LiPo + spare,
      laptop/phone + USB cable, coin (payload door), toothpick (switch), tools, tape, spare M3 / M2.5 screws and
      M2 × 6 servo screws (never longer).
      No wadding: there is no ejection charge

**At the field**
- [ ] Wind measured: **≤ 3 m/s for flights 1–3**, ≤ 6 m/s afterwards (use the 1.5 m rod above 3 m/s), never
      above 9 m/s, and no more than the recovery area allows (F35: about 60 m of drift per 1 m/s). Note the direction
- [ ] Pad set up and pegged, rod tilted 0–5° **downwind** only, tile on, dry grass around the pad cleared
- [ ] Recovery area clear downwind: F35 ≈ «F35_AREA» m (wind up to 6 m/s) or «F35_AREA3» m (wind 3 m/s or less);
      E20 «E20_AREA» m; D20 «D20_AREA» m

**Preparing the rocket**
- [ ] Motor: **"-0" plugged motor**, the type selected with the `motor` command (F35 = `motor 5`, E20 = `motor 2`,
      D20 = `motor 0`)
- [ ] F35: motor pushed up into the holder against the penny washer, **F35 retainer** (22 mm opening) pushed up and
      twisted 45° until it clicks. E20 / D20: **adapter sleeve** in first (D20: **D spacer** in the sleeve above the
      motor), then the motor, then the **24 mm retainer** (16 mm opening)
- [ ] Payload in, **door locked** (cam arm up)
- [ ] Parachute packed, spring and piston in, cord coiled on top
- [ ] Board ON (latch locks), nose cone pushed on until the bolt **clicks**; gentle pull test; board OFF to carry
      it to the pad
- [ ] Camera recording, lens clean
- [ ] Balance point ≤ 640 mm from the nose tip

**On the pad**
- [ ] Rocket on the rod, standing on its four fin feet on the tile, slides freely on the rod
- [ ] Every tab in line with its fin, nothing touching the tabs or the nozzle
- [ ] Power switch ON through the slot (toothpick), only once the rocket is on the rod: a sharp jolt while READY
      can look like a launch
- [ ] Leave it **still**: green LED blinking (calibrating) → solid + **double chirp every 3 s = READY**
- [ ] No red LED. Red slow blink = check `status` before going on
- [ ] Igniter in (launch controller **key out**), clips on, everyone back to **40 m for an F35** (30 m for a D20 / E20)

**Launch**
- [ ] Range clear, sky clear (no aircraft), RSO / LCO go
- [ ] Key in, continuity OK, loud countdown 5–4–3–2–1, launch
- [ ] Misfire: key out, **wait 60 s** before approaching

**Recovery**
- [ ] Watch it all the way down; note where it lands
- [ ] Follow the beeps; the digits are the apogee in metres
- [ ] Once found, switch OFF (stops the beeping; the log is already safe in flash)
- [ ] Spent motor out once cool; download the log; inspect fins (legs, servo pockets), tabs, gimbal, latch and
      the nose ballast (no loose nuts rattling); note the flight in the notebook
