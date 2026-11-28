# KESTREL-2 status check (Saturday 28 November 2026)

**Where we are:** the rocket is fully designed, simulated, tested in software and documented, and every file you
need to build it is ready. Nothing has been built or flown yet. The next step is to order: the flight-computer
board (now v3, with the radio socket), the radio pair and the rest of the parts list.

## What this round added

| You asked for | What it is now | Where |
|---|---|---|
| A live radio link with lots of packets a second | **Holybro SiK V3 433 MHz** pair. The board (**PCB v3**) has a 6-pin radio socket in place of the Qwiic port. **Firmware 3.00** sends **50 motion + 5 status frames a second** from lift-off to landing (1.5 a second on the pad), MAVLink-framed with a CRC and a frame number, so every lost frame is counted. The full 500 Hz log is still recorded on board and **merged with the radio recording** after landing, for complete data to analyse | [FIRMWARE.md](FIRMWARE.md#radio-telemetry-300), [PCB.md](PCB.md), [ground/README.md](../ground/README.md#live-radio-link) |
| Hide the cameras to cut drag | The camera sits **inside** the bottom tube, in a cradle behind a door with a lens port, looking out **30° down**. Camera drag is down **71 %** (the 30° view needs a low 5 mm brow over the lens, so it is not perfectly flush) | [BUILD_GUIDE.md §6](BUILD_GUIDE.md#6-camera-radio-and-antenna-the-bay-between-the-tvc-module-and-the-av-bay) |
| Fly to a waypoint in the sky | Declined: steering to a chosen point is guided-weapon capability. You chose the **live landing prediction** instead: where it will come down, with a search ring and a position to copy to a phone map | [ground/README.md](../ground/README.md#landing-prediction) |
| A smaller first motor that still deploys the parachute easily | **E20 first**, twice: flight 1 with the fin tabs off, flight 2 with them on, then the F35. The D20 hops are gone. In 700 simulated first flights the canopy was **fully open at about 40 m** (28 m in the worst 5 %, never below 18 m), with about 7.5 s under it | [TEST_PLAN.md](TEST_PLAN.md#c-flight-programme) |
| Test everything, at least 200 simulations | **About 3,700 simulated flights** on the final design (and as many again on the version before the ballast fix), plus every software test | below |

## The rocket in numbers (final design)

| | |
|---|---|
| Apogee on the TSP F35 | **157 m** calm with 25 g of payload (164 m with an empty bay); Monte Carlo mean 166 m, 90 % of flights 135–200 m |
| Apogee on the TSP E20 | about 41 m with 25 g of payload; about **47 m** on the first flights (no payload) |
| Lift-off mass | 952 g (F35, 25 g payload) |
| Stability | +0.72 to +0.84 calibres at lift-off, +0.91 to +1.02 at burn-out (51 g of nose ballast) |
| Landing | 5.2 m/s under the 36 in parachute; drifts about 46 m for every 1 m/s of wind |
| Recovery area | F35: 500 m downwind (wind up to 6 m/s) or 250 m (3 m/s or less); E20: 150 m |
| Radio | 8 dBm (≈ 6 mW e.r.p., inside the UK's 10 mW), network ID 75, and never more than 360 s on air an hour (the firmware enforces it) |
| Cost | ≈ £403–422 with the radio (≈ £317 without), motors extra |

## Tests run on the final design

| Test | Result |
|---|---|
| Scenario and fault suite (47 cases) | **44 of 44** graded cases pass (+3 informational) |
| Monte Carlo (1000 F35, 400 E20, 100 D20) | **1500 of 1500** meet every normal-flight criterion |
| First-flight study (700 E20 flights) | **700 of 700** |
| Stress Monte Carlo (double error spreads, wind to 9 m/s) | 99.7 % meet every criterion; **99.9 %** land safely under the parachute |
| Tab-effectiveness Monte Carlo (200) | 200 of 200 |
| RocketPy cross-check | agrees within 0.3 % |
| Landing prediction (120 simulated flights) | F35 median miss about 25 m on the pad, 14 m at apogee, 9 m halfway down; the search ring holds the landing point about 8 in 10 times on the pad and 9 in 10 or more after that |
| Jammed TVC servo (120 runs, 4 wind directions) | always lands under the parachute: within 26 m of the pad in calm air, and in wind never more than 8 m upwind or 28 m to the side, so spectators stand 40 m **upwind or to the side** |
| Flight firmware | 375,585 flight-core checks + 148 firmware-logic checks pass; 0-warning build; UF2 ready |
| Radio frames | the page's decoder matches pymavlink reference frames and an independent Python decoder, including a damaged link |
| Mission Control | a whole flight through a simulated radio link in a headless browser: 55 frames a second, no errors |
| PCB v3 | DRC 0 violations, all 65 nets routed, schematic matches the circuit pin for pin |
| CAD | all 40 printed parts watertight and printable as exported; 2485 part pairs with no overlaps; mechanism sweeps clean |

## Problems found and fixed on the way

- The radio adds about 43 g behind the balance point: with an empty payload bay the F35 rocket would have been 0.9 mm
  past the balance limit. **Nose ballast 46 → 51 g** brings back the old stability exactly.
- The radio cradle could not actually hold the radio (no room for its cable tie). It now has 1.5 mm side gaps with
  the tie slots in them and takes two 150 mm ties.
- The landing prediction was badly wrong during the boost (it expected the F35 to stop at about 40 m). It also
  ignored that wind grows with height. Both were fixed and checked on 120 flights.
- The spectator rule became "upwind or to the side": in 6 m/s a jammed servo can bring the rocket down 47 m
  **downwind**.
- Firmware: records written after an in-flight reset would have been skipped by `dump` (CRC computed too early).
  Fixed in 3.00.
- The v2 board's Qwiic socket faced into the board. v3 replaces it with the radio socket, and a rest pad supports
  the corner whose mounting hole the socket took.

## Honest gaps

- **Height:** 157 m against the 200 m you asked for. The multi-flight changes and then the radio each cost 48 g.
- **Not tried on hardware:** the radio's range with its antenna inside the airframe, next to the wiring. The test
  plan has a bench test (A23) and a field range test (B5) before the first flight.
- **Not read directly:** Ofcom's IR 2030 (the UK limits come from the CEPT/EU rules the UK kept; the Ofcom site
  cannot be reached from this cloud environment), and the Holybro product pages, which could not be opened from here
  either (radio size, mass and pinout came from search results and the SiK firmware source). The radio parts'
  masses are estimates: the balance check sets the real ballast.
- **No UK price yet** for the antenna or the antenna extension lead (US distributors list the extension at about
  $22–29 for one; DigiKey UK stocks it).
- **Unknown:** the unbranded camera's real field of view. The lens port leaves ±62° across and 38° up / 40° down clear.
- **Landing prediction** is calibrated on simulated flights; real wind does not always follow the model.
- **Time:** the final simulations finished at 21:21 on Friday, and then the session sat idle until your "carry on"
  at 08:29, so the overnight hours were not used.

## What to do next

1. Order the PCB v3 from JLCPCB ([PCB.md](PCB.md#ordering-from-jlcpcb)).
2. Buy the parts ([BOM.md](BOM.md)). New this round: the Holybro SiK V3 433 MHz pair, a 433 MHz RP-SMA antenna no
   longer than 125 mm, the Amphenol 095-902-536-006 antenna extension, 150 mm cable ties, two TSP E20 twin packs.
3. Print the 40 parts. Five are new: the camera door with its latch knob and cam, the camera cradle, the radio cradle
   and the antenna mount.
4. Build ([BUILD_GUIDE.md](BUILD_GUIDE.md)), set up both radios with Mission Control, run bench tests A1–A24 and field
   tests B1–B6 ([TEST_PLAN.md](TEST_PLAN.md)).
5. Fly: E20 with the tabs off, E20 with the tabs on, then the F35, each in no more than 3 m/s of wind for the first two.
