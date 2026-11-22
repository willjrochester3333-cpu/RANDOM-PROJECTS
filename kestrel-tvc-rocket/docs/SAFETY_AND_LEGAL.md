# Safety and the rules (UK)

KESTREL is a model rocket: 40 Ns total impulse (an E motor), 0.5 kg, no pyrotechnic ejection charge. That keeps it
in the simplest category, but a rocket with active steering has one failure mode that passive rockets do not: a
servo that jams can push it sideways. Everything below assumes you take that seriously.

This page is guidance, not legal advice. Rules change; check the current versions of the sources linked here.

## Where and with whom

- **Fly with a club** for your first flights. The [UK Rocketry Association (UKRA)](https://www.ukra.org.uk/) lists
  affiliated clubs and publishes the UK safety code; clubs provide sites with landowner permission, launch
  controllers, a range safety officer and third-party insurance through membership.
  The [BMFA](https://www.bmfa.org/) also covers model rocketry for its members.
- **Anywhere else you need the landowner's permission** and a field big enough for the recovery (see below).
- **Airspace**: under the Air Navigation Order, the CAA treats a rocket like this one as a "small rocket"
  (total impulse up to 10,240 Ns). Small rockets have the lightest rules, but you still need permission to fly
  inside controlled airspace or an aerodrome traffic zone, and you must never fly where you could endanger an
  aircraft. Check a current air chart or a drone app for airspace before choosing a site. See the
  [CAA](https://www.caa.co.uk/) for the current rules.
- **Motors**: buy certified motors from a UK rocketry retailer; they will apply age (normally 18+) and storage
  rules. Store them cool and dry, away from igniters. Use **"-0" (plugged) motors only**: KESTREL has no use for
  an ejection charge, and a delay/ejection charge would fire into the TVC mount.

## Safety rules that matter most for this rocket

| Rule | Why (and what the simulator showed) |
|---|---|
| Spectators ≥ 15 m from the pad, behind the launcher | the "servo hard-over" fault case: if a TVC servo jams at full deflection 0.5 s after launch, the rocket loops over and lands about 15 m from the pad, with its parachute deployed early by the abort logic |
| Wind below 6 m/s for the first flights; never above 9 m/s | all 9 m/s simulations still passed, but drift grows to ~470 m |
| Recovery area ≥ 300 m clear downwind (E20) | Monte Carlo: 95 % of E20 flights land within 314 m (wind up to 6 m/s) |
| Rod tilt 0–5° **downwind** only, never towards people | the rocket holds the rod direction during the burn |
| Electric ignition with a key-switch controller, 5 s countdown | standard model-rocket safety code |
| Misfire: key out, wait **60 s** before approaching | |
| Never stand over the rocket, never look into the tube | |
| Rod-tip cap on whenever the rod is empty | 6 mm steel rod at eye height |
| Fire extinguisher or water and a cleared, non-flammable area around the pad | motor exhaust and hot casing |
| Power the flight computer on only when the rocket is on the rod | in READY, a hard jolt can look like a launch to the sensors |

The ten-out-of-ten ejection test in [TEST_PLAN.md](TEST_PLAN.md) is not optional: a rocket that comes down without
its parachute hits the ground at about 50 m/s (simulated "no_chute" case).

## Built-in protections (all exercised in the simulator)

- **Launch before arming** (switched on and launched within 1 s): TVC stays centred, parachute logic still works.
- **TVC servos dead**: the fins alone keep it stable (static margin 1.36 calibres at lift-off with an E20).
- **Excessive tilt (> 50°) or tumbling during the burn**: abort, parachute out as soon as it is slow enough not to
  tear.
- **Barometer failure**: apogee detected from the inertial estimate, with a backup timer.
- **No apogee detected**: backup release at the motor's nominal apogee time + 3 s, or as soon as it falls faster
  than 12 m/s.
- **Processor reset in flight**: reboots straight into "release the parachute and beep".
- **Battery**: refuses to arm below 6.6 V; warns below 7.0 V.

## LiPo battery

- Charge only with a **balance charger**, on a non-flammable surface or in a LiPo bag, never unattended.
- Do not fly a puffy, dented or hot pack. Store it at ~7.6 V (3.8 V/cell) if not used for a week.
- The board's 13 V TVS diode and reverse-polarity protection protect the electronics, not the battery.
