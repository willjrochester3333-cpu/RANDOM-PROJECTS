# Safety and the rules (UK)

KESTREL-2 is a model rocket: an E motor (TSP E20, rated 36 Ns), about 0.83 kg at lift-off, and no pyrotechnic
ejection charge. That keeps it in the simplest category. But a rocket that steers itself with six servos has
failure modes that a passive rocket does not have: a servo that jams can push it sideways. It also leaves its
launch rod slowly (about 7 m/s), so it relies on its steering more than a light rocket would. Everything below
assumes you take that seriously.

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
  rules. Store them cool and dry, away from igniters. Use **"-0" (plugged) motors only**: KESTREL-2 has no use for
  an ejection charge, and a delay/ejection charge would fire into the TVC mount.

## Safety rules that matter most for this rocket

Every number in this table comes from the simulator flying the real flight code (cases named in
[SIMULATION_REPORT.md](SIMULATION_REPORT.md)).

| Rule | Why |
|---|---|
| Spectators **≥ 30 m** from the pad, behind the launcher | `servo_hardover`: if a TVC servo jams at full deflection 0.5 s after launch, the rocket loops over; the abort logic releases the parachute and it comes down 18–23 m from the pad (6 wind seeds) |
| **Wind ≤ 3 m/s for the first three flights** | `passive_wind3`: even with all six steering servos dead, the rocket still flies (tilting 23–33°) and recovers normally in 3 m/s. In 6 m/s (`passive_wind6`) it weathercocks hard and turns right over before apogee |
| Afterwards ≤ 6 m/s with the **1.5 m rod**; never above 9 m/s | with working steering every case up to 9 m/s passes (`wind6_gusty`, `rod_1.5m_wind6`, `wind9_limit`); the longer rod raises the rod-exit speed from 6.8 to 7.7 m/s |
| Recovery area **≥ 200 m** clear downwind (E20), 60 m (D20) | Monte Carlo: 95 % of E20 flights land within 101 m (wind up to 6 m/s), farthest 151 m; D20 farthest 38 m |
| Rod tilt 0–5° **downwind** only, never towards people | the rocket holds the rod direction during the burn (`rod_tilt5`) |
| Electric ignition with a key-switch controller, 5 s countdown | standard model-rocket safety code |
| Misfire: key out, wait **60 s** before approaching | |
| Never stand over the rocket, never look into the tube | |
| Rod-tip cap on whenever the rod is empty | 6 mm steel rod at eye height |
| Fire extinguisher or water and a cleared, non-flammable area around the pad | motor exhaust and hot casing |
| Power the flight computer on only when the rocket is on the rod | in READY, a hard jolt can look like a launch to the sensors |

The ten-out-of-ten ejection test in [TEST_PLAN.md](TEST_PLAN.md) is not optional: a rocket that comes down without
its parachute hits the ground at about 32 m/s (`no_chute`).

## Built-in protections (all exercised in the simulator)

- **Launched before it was ready** (switched on and launched within 1 s): TVC and tabs stay centred, the parachute
  logic still works (`unarmed_launch`).
- **TVC servos dead**: the fin tabs steer alone (`tvc_off_calm`, `tvc_off_wind3`).
- **A tab jammed, frozen or dead**: roll is controlled first and each tab saturates on its own, so the others
  keep working (`tab_stuck`, `tabs_dead`); a fully jammed tab can still tumble it in the coast, so a **give-up rule**
  centres all tabs if it is more than 25° off course, and the parachute still opens at apogee (`tab_hardover`).
- **All six steering servos dead**: it is still statically stable (+0.84 to +0.97 calibres depending on payload,
  thanks to the nose ballast)
  and recovers normally in light wind (`passive_calm`, `passive_wind3`, `passive_empty_bay`).
- **Excessive tilt (> 50°) or tumbling during the burn**: abort, parachute out as soon as it is slower than 30 m/s.
- **Barometer failure**: apogee detected from the inertial estimate, with a backup timer (`baro_dead`).
- **No apogee detected**: backup release at the motor's nominal apogee time + 3 s, or as soon as it falls faster
  than 12 m/s.
- **Processor reset in flight**: reboots straight into "release the parachute and beep", never steers again.
- **Battery**: refuses to arm below 6.6 V; warns below 7.0 V.

One failure nothing on board can handle: the **servo power supply** feeds all seven servos, including the
parachute release. That is why the board checks the servo rail before it arms (red LED if it is low), and why the
pre-flight `status` check matters.

## LiPo battery

- Charge only with a **balance charger**, on a non-flammable surface or in a LiPo bag, never unattended.
- Do not fly a puffy, dented or hot pack. Store it at ~7.6 V (3.8 V per cell) if it will not be used for a week.
- The board's 13 V TVS diode and reverse-polarity protection protect the electronics, not the battery.
