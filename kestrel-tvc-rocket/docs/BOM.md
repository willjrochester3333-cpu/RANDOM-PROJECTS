# Bill of materials and budget

**Target: under £200 for the complete rocket, flight computer and launch pad.**
Motors are a per-flight cost on top, like fuel (see the end of this page).

Prices are typical UK prices including VAT and delivery, rounded, as estimates. Generic parts (servos, LiPo,
camera, parachute, hardware) are cheapest from AliExpress/eBay; prices on Amazon UK are typically 30–60 % higher.
**Check prices before you order.** The PCB order is the biggest and least certain item.

Assumption: you have (or can borrow) a 3D printer that prints PETG, a craft knife, a drill with 2 mm, 3.3 mm and
6 mm bits, and a USB cable for the Pico (micro-USB). No soldering iron is needed anywhere.

## Rocket + flight computer + launch pad

| # | Item | Qty | Notes / what to search for | Est. £ |
|---|---|---|---|---|
| 1 | **KESTREL FC board**, assembled by JLCPCB | 2 assembled (+3 bare) | Upload `pcb/production/` files. Economic PCBA + through-hole soldering by JLCPCB. Breakdown below | **78** |
| 2 | Raspberry Pi Pico 2 **WH** (headers already soldered) | 1 | Pimoroni / The Pi Hut. Must be the **H** version (no soldering) | 7.50 |
| 3 | BT-70 kraft body tube (56.3 mm OD), 34 in / 864 mm | 1 | UK rocketry shop. Cut 540 mm + 250 mm. Any 56 mm kraft tube with 55.2 mm ID works | 12 |
| 4 | PETG filament | ~0.55 kg | Rocket 214 g, pad ~260 g, drill guide 60 g | 10 |
| 5 | MG90S metal-gear micro servo | 3 (+1 spare) | 2 × TVC, 1 × parachute latch. Metal gears matter (motor heat, landing loads) | 8 |
| 6 | 2S 7.4 V LiPo, 200–300 mAh, 25C+, **JST-XH balance lead** | 1 | ≤ 31 × 12 × 55 mm. The balance lead plugs straight into the board | 6 |
| 7 | 2S/3S USB balance charger | 1 | Skip if you have one | 5 |
| 8 | Active GPS patch antenna, 18 × 18 mm, U.FL/IPEX lead ≥ 10 cm | 1 | "GPS active ceramic antenna IPEX 18x18" | 3 |
| 9 | SQ12-class 23 mm cube mini camera + 32 GB microSD | 1 | Lens in the middle of one face; fits the pod (23 mm cube) | 12 |
| 10 | 24 in (60 cm) nylon parachute | 1 | Descent 5.5 m/s at 500 g (simulated) | 7 |
| 11 | Kevlar shock cord 2 m + 1 m 6 mm elastic + small swivel | 1 set | | 5 |
| 12 | Compression spring ~25 mm OD × 60 mm, 0.8 mm wire | 1 | From a spring assortment | 2 |
| 13 | Screws & nuts: M2.5 × 8 self-tapping (4); M3 × 10–16 + nuts (12: av-bay 2, fin can 2, gimbal pivots 4, pad legs 3, rod stop 1); M4 × 16 (4, pad plate) + M4 thumb screw; M6 × 70 bolt + wing nut; M10 penny washer | kit | the penny washer is the burn-through shield on top of the motor | 6 |
| 14 | 1.2 mm and 0.6 mm music (piano) wire, 0.5 m each + 2 servo extension leads 30 cm | | 1.2 mm: TVC pushrods; 0.6 mm: springy latch links (bent, no solder) | 4 |
| 15 | 5-minute epoxy + medium CA glue | | | 7 |
| 16 | Filler primer spray (+ colour if you like) | 1–2 cans | Sanded + primed finish is what the drag model assumes | 6 |
| 17 | Launch pad hardware: 22 mm hardwood dowel 2.4 m (cut 3 × 600 mm), 6 mm × 1 m steel rod, 150 mm ceramic tile or 1.5 mm steel plate, 3 tent pegs | | B&Q / Wickes / hardware shop | 14 |
| | **Total** | | | **≈ £193** |

If you already own a LiPo charger, glue and primer, the total drops to about **£175**.

### The PCB order in detail (item 1)

Numbers from the actual BOM in `pcb/production/kestrel_fc_bom_jlcpcb.csv`, checked against JLCPCB's part
library: **29 of the 41 unique parts are JLCPCB "basic" or "preferred" parts** (no loading fee);
**12 are "extended"** (≈ US$3 loading fee each).

| Line | US$ (estimate) |
|---|---|
| 5 × 4-layer PCB, 40 × 82 mm, 1.6 mm, HASL lead-free | 7 |
| Economic PCBA set-up + stencil | 9.5 |
| Components for 2 boards (sensors, GPS, regulators, connectors, passives) | 30 |
| Extended-part loading fees (≈ 8 SMT parts × $3) | 24 |
| Through-hole soldering by JLCPCB (Pico sockets, servo headers, battery plug, buzzer) | 5 |
| Slowest tracked shipping to the UK | 6 |
| UK VAT 20 % (charged at checkout) | 16 |
| **≈ US$98 ≈ £78** | |

Why it costs what it does: the IMU, barometer, GPS module and U.FL connector have no cheap "basic"
equivalents, and assembly needs a minimum of 2 boards. You get **2 working boards** (one is a spare or a second
rocket) and 3 bare boards. If JLCPCB moves you to "Standard PCBA" because of the through-hole parts, expect
about £15 more. Their DFM engineers check every order before production; see
[PCB.md](PCB.md#ordering-from-jlcpcb) for the exact clicks.

## Per-flight costs (not in the build total)

| Motor (24 mm, single-use) | Use | Simulated apogee |
|---|---|---|
| TSP D20-0 | first test hops, ground-truth for the logs | 82 m |
| TSP E12-0 | long 3.5 s burn: best TVC demo | 161 m |
| **TSP E20-0** | **the 200 m mission** | **197 m** (90 % of flights 170–228 m) |

Expect roughly £10–15 per motor; prices vary by retailer, so check before you plan a season.

TSP (Tendera) motors are sold in the UK through model-rocketry retailers such as
[modelrockets.co.uk](https://www.modelrockets.co.uk/). Use **"-0" (plugged / no-delay) motors**: KESTREL deploys
its parachute with a servo, so it never needs an ejection charge. Buying motors usually requires you to be 18+;
the retailer will tell you their rules. Igniters come with the motors; you also need a launch controller with a
safety key (your club has one, or ~£20 for a basic one). Club membership (UKRA via a club, or BMFA) adds insurance
and launch sites. See [SAFETY_AND_LEGAL.md](SAFETY_AND_LEGAL.md).

A typical first season (1 × D20, 1 × E12, 3 × E20) is five motors.

## Electronics on the board (for reference)

| Ref | Part | LCSC | Function |
|---|---|---|---|
| U4 | LSM6DSO | C2655100 | 6-axis IMU, ±16 g, ±2000 °/s, 833 Hz on SPI |
| U5 | Bosch BMP580 | C22391138 | barometer, 50 Hz on SPI (altitude, apogee detection) |
| U7 | ATGM336H-5N31 | C90770 | GPS + BeiDou receiver (landing position) |
| U6 | W25Q128JV | C97521 | 16 MB flight log (~30 flights) |
| U2, U3 | TPS563201 | C116592 | two 3 A buck converters: 5 V servos, 5 V logic |
| Q1 | AO3401A | C15127 | reverse-battery protection |
| Q2 + SW1 | AO3401A + PCM12 slide switch | C15127 / C221841 | soft power switch |
| BZ1 | TMB12A03 | C96222 | locator buzzer |
| J2–J5 | 3-pin 2.54 mm headers | C49257 | servo plugs (TVC ×2, deploy, aux/camera) |
| J10, J11 | 1×20 sockets | C7499336 | Pico 2 WH plugs in |
| J1 | JST-XH 3-pin | C144394 | LiPo balance lead = power input |
| J7 | JST-SH 4-pin (Qwiic) | C160404 | I²C expansion for add-ons |
| J8 | U.FL | C88374 | GPS antenna |

Full list: `pcb/production/kestrel_fc_bom_jlcpcb.csv`; schematic: `pcb/kestrel_fc_schematic.pdf`.
