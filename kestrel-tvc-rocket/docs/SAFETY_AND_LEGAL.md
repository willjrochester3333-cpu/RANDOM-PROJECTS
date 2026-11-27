# Safety and the rules (UK)

KESTREL-2 is a model rocket: an F motor (TSP F35, rated 65 Ns), about 0.90 kg at lift-off, and no pyrotechnic
ejection charge. With under 160 Ns of total impulse it stays in the simplest category (UKRA's "model rocket"; no
CAA permission needed, see below). But a rocket that steers itself with six servos has failure modes that a passive
rocket does not have: a servo that jams can push it sideways. It flies about **170 m** high, so it drifts a long
way under its parachute, and on the small D20 / E20 test motors it leaves its launch rod slowly (about 6.5 m/s;
10 m/s on the F35), so it relies on its steering more than a light rocket would. Everything below assumes you take that
seriously.

This page is guidance, not legal advice. Rules change; check the current versions of the sources linked here.

## Where and with whom

- **Fly with a club** for your first flights. The [UK Rocketry Association (UKRA)](https://www.ukra.org.uk/) lists
  affiliated clubs and publishes the UK safety code; clubs provide sites with landowner permission, launch
  controllers, a range safety officer and third-party insurance through membership.
  The [BMFA](https://www.bmfa.org/) also covers model rocketry for its members.
- **Anywhere else you need the landowner's permission** and a field big enough for the recovery (see below).
- **Airspace**: under the Air Navigation Order, the CAA treats a rocket like this one as a "small rocket"
  (total impulse up to 10,240 Ns), and rockets of 160 Ns or less need no CAA permission
  ([CAA: notifications for smaller rockets](https://www.caa.co.uk/space/licences-and-permissions/large-rocket-permission/notifications-for-smaller-rockets/)).
  You still must not enter controlled airspace without permission ([UKRA](https://ukra.org.uk/safety/launching-rockets/))
  or fly inside an aerodrome traffic zone, and you must never fly where you could endanger an aircraft. The F35
  flights reach about 170 m (560 ft): check a current air chart or a drone app for airspace before choosing a site.
- **Motors**: buy certified motors from a UK rocketry retailer; they will apply age (normally 18+) and storage
  rules. Store them cool and dry, away from igniters. Use **"-0" (plugged) motors only**: KESTREL-2 has no use for
  an ejection charge, and a delay/ejection charge would fire into the TVC mount.

## Safety rules that matter most for this rocket

Every number in this table comes from the simulator flying the real flight code (cases named in
[SIMULATION_REPORT.md](SIMULATION_REPORT.md)).

| Rule | Why |
|---|---|
| Spectators **≥ 40 m** from the pad for the F35 (≥ 30 m for the D20 / E20), behind the launcher | `servo_hardover`: if a TVC servo jams at full deflection 0.5 s after launch, the rocket loops over; the abort logic releases the parachute and it comes down 23–26 m from the pad with the F35 (6 wind seeds; 20–22 m on the E20, 9–12 m on the D20) |
| **Wind ≤ 3 m/s for the first three flights** (D20, D20, E20) | with all six steering servos dead, the rocket still flies and recovers normally in 3 m/s on the D20 and the E20 (E20: tilting 20° in the boost, 45° in the coast). In 6 m/s the E20 tilts 47° in the boost and goes right over in the coast (the parachute still opens at apogee) |
| Afterwards (F35) ≤ 6 m/s with the **1.5 m rod**, never above 9 m/s, and only as much wind as the recovery area allows | with working steering every case up to 9 m/s passes (`wind6_gusty`, `rod_1.5m_wind6`, `wind9_limit`); even with every steering servo dead the F35 (10 m/s off the rod) recovers normally in 3 m/s (`passive_wind3`). It drifts about 55 m per 1 m/s of wind: 160 m in 3 m/s, 320 m in 6 m/s, 490 m in 9 m/s |
| Recovery area **≥ 500 m** clear downwind for the F35 in up to 6 m/s of wind, or **250 m** if it flies only in 3 m/s or less; 150 m (E20), 50 m (D20) | Monte Carlo: 95 % of F35 flights land within 312 m (wind up to 6 m/s), farthest 436 m; in 3 m/s or less farthest 198 m; E20 farthest 115 m; D20 farthest 27 m |
| Rod tilt 0–5° **downwind** only, never towards people | the rocket holds the rod direction during the burn (`rod_tilt5`) |
| Electric ignition with a key-switch controller, 5 s countdown | standard model-rocket safety code |
| Misfire: key out, wait **60 s** before approaching | |
| Never stand over the rocket, never look into the tube | |
| Rod-tip cap on whenever the rod is empty | 6 mm steel rod at eye height |
| Fire extinguisher or water and a cleared, non-flammable area around the pad | motor exhaust and hot casing |
| Power the flight computer on only when the rocket is on the rod | in READY, a hard jolt can look like a launch to the sensors |

The ten-out-of-ten ejection test in [TEST_PLAN.md](TEST_PLAN.md) is not optional: a rocket that comes down without
its parachute hits the ground at about 51 m/s after an F35 flight (`no_chute`).

## Built-in protections (all exercised in the simulator)

- **Launched before it was ready** (switched on and launched within 1 s): TVC and tabs stay centred, the parachute
  logic still works (`unarmed_launch`).
- **TVC servos dead**: the fin tabs steer alone (`tvc_off_calm`, `tvc_off_wind3`).
- **A tab jammed, frozen or dead**: roll is controlled first and each tab saturates on its own, so the others
  keep working (`tab_stuck`, `tabs_dead`); a fully jammed tab can still tumble it in the coast, so a **give-up rule**
  centres all tabs if it is more than 25° off course, and the parachute still opens at apogee (`tab_hardover`).
- **All six steering servos dead**: it is still statically stable (+0.72 to +0.84 calibres at lift-off with the
  F35 depending on payload, +0.91 to +1.03 at burn-out, thanks to the nose ballast) and recovers normally in light
  wind (`passive_calm`, `passive_wind3`, `passive_empty_bay`).
- **Excessive tilt (> 50°) or tumbling during the burn**: abort, parachute out as soon as it is slower than 30 m/s.
- **Barometer failure**: apogee detected from the inertial estimate, with a backup timer (`baro_dead`).
- **No apogee detected**: backup release at the motor's nominal apogee time + 3 s, or as soon as it falls faster
  than 12 m/s.
- **Processor reset in flight**: reboots straight into "release the parachute and beep", never steers again.
- **Battery**: refuses to arm below 6.6 V; warns below 7.0 V.

One failure nothing on board can handle: the **servo power supply** feeds all seven servos, including the
parachute release. That is why the board checks the servo rail before it arms (red LED if it is low), and why the
pre-flight `status` check matters.

## Steering: straight up only

KESTREL-2's steering (TVC and fin tabs) only keeps the rocket pointing the way it left the rod: straight up, or
along the rod's small downwind tilt. It never steers towards a chosen place, and the radio link carries nothing that
changes the flight: the rocket sends telemetry, and the only thing it reads from the radio is the ground station's
heartbeat and its own radio's link report. That is deliberate. A rocket that can be flown to a point you pick is a
guided weapon, whether the point is in the sky or over the ground, and the safety codes expect model rockets to fly
nearly straight up and never at targets (for example the [NAR Model Rocket Safety Code](https://nar.org/ModelRocketSafetyCode)).
Mission Control's landing prediction only *shows* where the rocket will come down, so you can walk to it.

## Radio

The telemetry radio (a Holybro SiK V3 pair on 433 MHz) is a licence-exempt short-range device. For the
433.05–434.79 MHz band the European rules (CEPT [ERC Recommendation 70-03](https://docdb.cept.org/download/4435))
allow **10 mW e.r.p.** and **10 % duty cycle**; in that framework the duty cycle is measured over **one hour** unless
stated otherwise ([EU decision 2019/1345](https://eur-lex.europa.eu/eli/dec_impl/2019/1345/oj/eng); the UK kept it as
[retained law](https://legislation.gov.uk/eudn/2019/1345/data.pdf)), i.e. at most 360 s on air per hour
([UK 433 MHz explainer](https://iottechnologies.co.uk/news-and-insights/433-mhz-ism-band-uk-explained)). Ofcom's own
interface requirement (IR 2030) was not read for this project: check it, or ask your club, if you want certainty.

How KESTREL stays inside those limits:

- **Power.** The radios leave the factory at 100 mW (TXPOWER 20), which is too much for the UK. Mission Control's
  **Set up a radio (UK settings)** dialog sets each radio to **8 dBm** (6.3 mW): with the 2 dBi antennas that is
  about 6 mW e.r.p. The next step up (11 dBm) would be about 12 mW e.r.p., over the limit. If you fit a bigger
  antenna to the ground radio, lower its power by the extra gain.
- **Airtime.** The rocket sends its 50 + 5 frames a second only between lift-off and landing (about 45 s on an F35),
  1.5 frames a second on the pad and a slow beacon after landing. The firmware keeps a rolling one-hour estimate of
  its time on air (counting the radio's own link-keeping packets as 2 % of every hour), and drops to lean rates
  above 270 s and to a beacon above 330 s, so it cannot pass 360 s even if something kept it at full rate for an
  hour (unit-tested). Four F35 flights in one hour use well under that (`radio` on the USB command line and the
  Mission Control radio card show the running total). The ground radio transmits only its link packets and a
  once-a-second heartbeat.
- **Frequencies.** The SiK radios hop over 10 channels inside 433.05–434.79 MHz (their 433 MHz defaults, which the
  set-up dialog checks), with network ID 75 so they ignore other SiK users nearby.

## LiPo battery

- Charge only with a **balance charger**, on a non-flammable surface or in a LiPo bag, never unattended, and
  **outside the rocket**: slide the pack out through the battery hatch and charge it on the second adapter lead.
  Never charge it inside the printed and cardboard airframe.
- Do not fly a puffy, dented or hot pack. Store it at ~7.6 V (3.8 V per cell) if it will not be used for a week.
- The board's 13 V TVS diode and reverse-polarity protection protect the electronics, not the battery.
