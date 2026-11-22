# Pre-flight checklist (print this)

**Night before**
- [ ] LiPo balance-charged to 8.4 V (charger on a fire-proof surface, never unattended)
- [ ] Camera battery charged, microSD empty
- [ ] `status`: IMU / baro / flash ok, axes calibrated, correct motor selected, log has > 1 MB blank
- [ ] Last flight's log downloaded and plotted
- [ ] Gimbal pivots free, no play; pushrods straight; latch bolts slide freely
- [ ] Spring, piston, shock cord, parachute: no burns, knots or frays
- [ ] Field: club launch or landowner permission confirmed; not near an airfield or in controlled airspace (see SAFETY_AND_LEGAL.md)
- [ ] Pack: rocket, pad + rod + tile + pegs + rod cap, motors, launch controller + key, LiPo + spare, laptop/phone + USB cable, tools, tape, spare M3/M2.5 screws, wadding not needed (no ejection charge)

**At the field**
- [ ] Wind < 6 m/s for the first flights (< 9 m/s ever); note direction
- [ ] Pad set up, pegged, rod tilted 0–5° **downwind**, ceramic tile/steel plate on, area around the pad cleared of dry grass
- [ ] Recovery area clear and big enough (≈ 300 m downwind for an E20)

**Preparing the rocket**
- [ ] Motor: **"-0" plugged motor**, correct type for the selected profile (`motor` command)
- [ ] Motor into the holder (penny washer on top), retainer pushed up and twisted 45° until it clicks
- [ ] Parachute packed, spring + piston in, nose cone snug
- [ ] Board ON, upper section pushed on until both latch bolts **click**; gentle pull test; board OFF to carry it to the pad
- [ ] Camera recording, pod lid / foam in place
- [ ] Balance point ≤ 600 mm from the nose tip

**On the pad**
- [ ] Rocket on the rod, slides freely, nozzle 45 mm above the plate
- [ ] Power switch ON through the slot (toothpick) - only once the rocket is on the rod: a sharp jolt while READY can look like a launch
- [ ] Leave it **still**: green LED blinking (calibrating) → solid + **double chirp every 3 s = READY**
- [ ] No red LED. Red slow blink = check `status` before going on
- [ ] Igniter in (launch controller **key out**), clips on, everyone back to the safety distance

**Launch**
- [ ] Range clear, sky clear (no aircraft), RSO / LCO go
- [ ] Key in, continuity ok, loud countdown 5–4–3–2–1, launch
- [ ] Misfire: key out, **wait 60 s** before approaching

**Recovery**
- [ ] Watch it all the way down; note where it lands
- [ ] Follow the beeps; the digits are the apogee in metres
- [ ] Once found, switch OFF (stops the beeping; the log is already safe in flash)
- [ ] Spent motor out once cool; download the log; inspect; note the flight in the notebook
