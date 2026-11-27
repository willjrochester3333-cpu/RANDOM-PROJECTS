# KESTREL FC v3.0: the flight-computer PCB

A 40 × 82 mm, 4-layer carrier board for the Raspberry Pi Pico 2 W, designed in **KiCad 7**. Open
`pcb/kestrel_fc.kicad_pro` in KiCad 7 or newer. Every SMD part is placed by JLCPCB and the through-hole
parts (Pico sockets, servo headers, battery plug, buzzer) are soldered by JLCPCB too, so **you never solder
anything**.

![front of the board, rendered from the gerbers by gerbv](../pcb/build/gerbv_front_check.png)

## What is on it

| Block | Parts | Notes |
|---|---|---|
| Brain | Raspberry Pi Pico 2 W (RP2350, 150 MHz Cortex-M33 with FPU) on 2 × 20 sockets | swap or upgrade without tools |
| Inertial | LSM6DSO 6-axis IMU, SPI, 833 Hz, ±16 g / ±2000 °/s | 3.3 V plane under it, decoupled |
| Altitude | Bosch BMP580 barometer, SPI, 50 Hz | static ports in the tube; av-bay sealed from the motor section |
| Position | ATGM336H-5N31 GPS + BeiDou, UART, 5 Hz, U.FL for the passive 15 mm patch antenna | recovery: last position is logged and beeped. The active-antenna bias feed is on the board but its resistor **R24 is not fitted**, so no DC reaches the antenna (a DC-shorted passive patch could otherwise burn R24) |
| Memory | W25Q128JV 16 MB SPI NOR | ≈ 30 flights of 500 Hz data |
| Power in | 2S LiPo through its **JST-XH balance plug** | reverse-polarity P-FET, 13 V TVS, both cells monitored |
| Power switch | PCM12 slide switch driving a P-FET soft switch | reachable through the slot in the airframe |
| Servo power | TPS563201 3 A buck → 5 V, switchable from GP3 | servo rail voltage monitored |
| Logic power | second TPS563201 → 5 V → Schottky → Pico VSYS | USB and battery can both be connected |
| Outputs | **7 servo headers** (TVC ring, TVC motor, parachute release, fin tabs 1–4), buzzer, 2 LEDs | v2: 3 more servo ports; the v1 AUX 5 V switch is gone (the camera has its own battery) |
| Telemetry radio | **6-pin JST-GH socket J7, Pixhawk TELEM pinout** (1 +5 V, 2 TX out, 3 RX in, 4 CTS and 5 RTS not connected, 6 GND), UART1 at 57600 baud, 5 V from VSYS with a 10 µF capacitor (C25) by the socket | v3: replaces the v2 Qwiic port. The Holybro SiK radio's own GH6 cable plugs straight in, no adapter |
| Inputs | USER and RESET buttons | |

Pico pin map (also in `firmware/pico/src/board.hpp`):

| GP | Signal | GP | Signal |
|---|---|---|---|
| 0 / 1 | GPS UART TX / RX | 14 | USER button |
| 2 | **servo 5 PWM (fin tab 2)** | 15 | **servo 7 PWM (fin tab 4)** |
| 3 | servo power off | 16 / 18 / 19 | SPI0 MISO / SCK / MOSI |
| 4 / 5 | **radio UART1 TX / RX** (J7 pins 2 / 3) | 17 / 20 / 21 | CS IMU / baro / flash |
| 6 – 9 | servo PWM 1 – 4 (TVC ring, TVC motor, release, fin tab 1) | 22 | baro INT |
| 10 | buzzer | 26 / 27 / 28 | ADC: battery / cell 1 / servo rail |
| 11 / 12 | LED green / red | 13 | **servo 6 PWM (fin tab 3)** |

The seven servo PWM pins sit on PWM slices 1, 3, 4, 6 and 7 (all at 50 Hz); GP12 (LED) shares slice 6 with
GP13 but is driven as a plain GPIO, so there is no conflict. The GPS PPS and IMU interrupt lines of v1 were not
used by the firmware and gave their pins to the new servo ports.

**What changed in v3 (radio).** The v2 Qwiic socket (J7) and its two I²C pull-ups (R35, R36) are gone; in their
place, in the bottom-left corner, is a vertical 6-pin JST-GH socket (JST BM06B-GHS-TBT, LCSC C189892) wired like a
Pixhawk TELEM port, so a standard SiK telemetry radio plugs in with the cable it comes with. The radio draws about
100 mA when it transmits, from VSYS (≈ 4.7 V after the Schottky; the SiK radio takes 5 V and regulates its own
3.3 V) with a 10 µF capacitor right at the socket. Its 3.3 V signals match the Pico's. To make room for the socket
the bottom-left mounting hole was removed, so the board has **3 mounting holes**. The avionics sled has three
screw standoffs and, under the fourth corner (behind the socket, where the board's back is bare), a plain rest pad
of the same height, which takes the push when the radio plug goes in. The v2 Qwiic J7 also faced into the board, a layout mistake that
v3 removes.

## Design files

| File | What |
|---|---|
| `pcb/circuit.py` | the circuit as code: every part, LCSC number, pin-to-net map and placement. Single source of truth |
| `pcb/gen_schematic.py` → `kestrel_fc.kicad_sch`, `kestrel_fc_schematic.pdf` | schematic generated from `circuit.py` |
| `pcb/check_netlist.py` | exports KiCad's own netlist from the schematic and checks it pin-for-pin against `circuit.py` + electrical rules |
| `pcb/board_build.py`, `pcb/router.py`, `pcb/gen_pcb.py` | placement, a purpose-written A* autorouter (4 layers, net classes, via rules), pours, silkscreen, DRC |
| `pcb/jlc_fab.py` → `pcb/production/` | gerbers + drill (zip), BOM and pick-and-place in JLCPCB format with rotation corrections |
| `pcb/production/kestrel_fc_assembly_top.pdf` | top-side assembly drawing (part outlines + designators): use it to check the placement preview when ordering |
| `pcb/export_mech.py` → `pcb/build/mech_interface.json` | holes, pin tails, switch/LED positions for the CAD model (the av-bay is built around the real board) |

## Verification

| Check | Result |
|---|---|
| Schematic vs circuit, pin by pin (KiCad netlist export) | **matches exactly**, ERC checks pass |
| Courtyard overlaps after placement | **0** |
| Routing | **all 65 nets routed, 0 unconnected pads** (purpose-written A* router, 3 rip-up passes: 1,119 tracks, 183 vias) |
| KiCad DRC (clearance 0.13 mm, track 0.18 mm, via 0.55/0.3 mm, 0.3 mm copper-to-edge) | **0 violations, 0 unconnected** |
| Gerbers re-read by an independent viewer (gerbv) | outline 40.00 × 82.00 mm, 4 copper layers, planes and drills as designed |
| Board fits the airframe | checked in the CAD: standoffs on the real mounting holes, clearance slots behind every pin tail, switch and LEDs under the airframe slot, 7 servo plugs, GPS antenna shelf, no interference with any other part |

Stack-up: F.Cu signals · In1 solid GND · In2 +3.3 V plane · B.Cu signals + GND pour. Rules are well inside
JLCPCB's standard 4-layer capability, so no extra-cost options are needed.

## Ordering from JLCPCB

1. **jlcpcb.com → Order now → Add gerber file**: upload `pcb/production/kestrel_fc_gerbers_jlcpcb.zip`. It is
   detected as 4 layers, 40 × 82 mm. Quantity 5, thickness 1.6 mm, any colour, HASL lead-free, default 4-layer
   stack-up. "Remove order number: specify a location" (the back silkscreen has the `JLCJLCJLCJLC` marker).
2. **PCB Assembly: on.** Economic, top side, **2 boards**, tooling holes added by JLCPCB. Confirm.
3. Upload `kestrel_fc_bom_jlcpcb.csv` (BOM) and `kestrel_fc_cpl_jlcpcb.csv` (pick-and-place).
4. All 47 BOM lines should match (94 placements: 83 SMD, 11 through-hole; R24 is deliberately not fitted). If a passive is out of stock, pick the suggested equivalent with the same value
   and package. If a sensor or the GPS is out of stock, wait or ask in an issue: don't substitute blindly.
5. **Placement preview: check pin 1** of U2/U3 (TPS563201, community rotation correction applied), U4 (LSM6DSO),
   U5 (BMP580), U6 (flash), U7 (GPS module), the diodes' cathode bars, the LEDs, J7 (radio socket: its pin 1, +5 V, is
   at the end nearest the GPS; its six contacts along the board edge, its two mounting pads further in). Rotations come from the KiCad/JLCPCB community correction table; JLCPCB's engineers also check
   every order before it is built.
6. Make sure the **through-hole parts** (J1, J2–J5, J12–J14, J10, J11, BZ1) are selected for assembly. If Economic won't
   take them, switch to Standard PCBA (≈ £15 more).
7. Pay. Production is about a week, then shipping.

## First power-up

1. Look at the boards. Plug the Pico 2 WH in, USB connector towards the GPS end. The seven servo ports are
   numbered 1–7 on the front (S + − from the board edge inwards) and named on the back.
2. USB only first: green+red LEDs, then `status` over USB should show IMU, baro and log flash `ok` (servo rail and
   battery read 0 V on USB power: they run from the LiPo).
3. Plug the LiPo (switch off), switch on: `status` shows both cell voltages and ≈ 5 V on the servo rail.
4. Continue with the set-up in [BUILD_GUIDE.md §10](BUILD_GUIDE.md#10-firmware-and-set-up-usb-no-tools-needed).
