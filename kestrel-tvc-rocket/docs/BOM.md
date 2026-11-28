# Shopping list (KESTREL-2)

Agreed rules for this list: **mostly Amazon UK**, **UK brands or large international brands only**, with three
exceptions where unbranded is fine: **servos, camera, parachute**. Motors are **TSP** (the agreed exception).
Where Amazon UK has no branded listing for a part, the list names a UK retailer instead.

How to read the prices:

- **✔ price** = seen on the retailer's page or a UK price listing when this list was written (November 2026);
- **≈ price** = estimate for a branded item of that type. Prices move: check before you order.
- Links marked **search** open an Amazon UK search for the exact brand and type; pick the listing sold by the
  brand or by Amazon. (Product pages on Amazon change too often to link one by one.)

Assumed you already have: a 3D printer that prints PETG, a craft knife, a drill (or pin vice) with 1.3 mm, 2 mm, 3.3 mm and 6 mm bits,
needle-nose pliers, a ruler, sandpaper, and a micro-USB cable for the Pico. **No soldering iron is needed.**

## 1. Flight computer and electronics

| # | Item | Qty | Brand / exact part | Where | Price |
|---|---|---|---|---|---|
| 1 | **KESTREL FC v3 board** (v3 = with the radio socket), made and assembled by JLCPCB | 2 assembled + 3 bare | upload `pcb/production/` (see [PCB.md](PCB.md#ordering-from-jlcpcb)) | [jlcpcb.com](https://jlcpcb.com) | ≈ £80 |
| 2 | Raspberry Pi Pico 2 **W with headers** (2 WH) | 1 | Raspberry Pi (UK) | [The Pi Hut](https://thepihut.com/collections/latest-raspberry-pi-products/products/raspberry-pi-pico-2-w) (choose "with headers") | ≈ £7 |
| 3 | 2S 7.4 V 350 mAh 25C LiPo, **about 40 × 19 × 15 mm** (the pocket takes up to 16 mm; one shop lists 25 mm: check). A second pack lets you swap a charged one in through the battery hatch between flights | 1 (2 recommended) | **Overlander OL-3492** (UK) | [overlander.co.uk](https://overlander.co.uk/350mah-7-4v-2s-25c-lipo-battery.html) | ✔ about £7 |
| 4 | JST-PH → JST-XH 2S balance adapter lead | 2: one stays in the rocket, one lives with the charger (packs are charged outside the rocket) | **Overlander OL-2529** | [overlander.co.uk](https://www.overlander.co.uk/jst-ph-to-jst-xh-balance-conversion-lead-for-130x-beast.html) | ✔ £1.58 each |
| 5 | GPS antenna, passive 15 × 15 mm, U.FL | 1 | **Adafruit 2461** (US, international) | [The Pi Hut](https://www.thepihut.com/product/2461) | ✔ £3.90 |
| 6a | Micro-USB cable with an **angled** plug, USB-A, 1–2 m: reaches the Pico's socket through the battery hatch. The cable must leave the plug on the side **facing away from the Pico's board** (towards the hatch): StarTech sell an up-angle and a down-angle version, so compare the product photo with your Pico before ordering | 1 | **StarTech.com** A to up-angle micro-B, or A to down-angle micro-B (USBAUB2MD) | [up angle, 2 m (BT Business Direct)](https://www.businessdirect.bt.com/products/startech-com-2m-micro-usb-cable---a-to-up-angle-micro-b-8ZCX.html) · [down angle, 2 m (Rapid)](https://www.rapidonline.com/startech-com-usbaub2md-startech-com-2m-micro-usb-cable-a-to-down-angle-micro-b-71-1981) | ≈ £5 |
| 6 | 2S LiPo balance charger (skip if you have one) | 1 | SkyRC or ISDT USB-powered 2S/3S balance charger | Amazon UK [search](https://www.amazon.co.uk/s?k=SkyRC+lipo+balance+charger+2S) | ≈ £15–28 |

## 1b. Telemetry radio (live data to Mission Control)

| # | Item | Qty | Brand / exact part | Where | Price |
|---|---|---|---|---|---|
| R1 | SiK telemetry radio **pair, 433 MHz, the 100 mW version** (each radio has micro-USB and the 6-pin JST-GH socket; the box has the JST-GH 6-pin cable that plugs into the board's radio socket). Set to 8 dBm for the UK with Mission Control's set-up dialog before first use | 1 pair | **Holybro SiK Telemetry Radio V3, 433 MHz, 100 mW** | [Flyingtech](https://www.flyingtech.co.uk/product/holybro-100mw-500mw-telemetry-radio-set-v3/) (UK, ✔ £71.90; choose 433 MHz, 100 mW) · [Unmanned Tech](https://www.unmannedtechshop.co.uk/products/100mw-sik-telemetry-radio-kit-v3-433mhz) (UK, ✔ £52.99, sold out when checked) | £53–72 |
| R2 | Rocket antenna: a 433 MHz whip with an **RP-SMA** plug, **no longer than 125 mm** (the channel it stands in). Known fit: the 3DR one, 115 mm with a hinged base. The antennas in the Holybro box (2 dBi, RP-SMA) can be used if they are no longer than 125 mm: measure one before ordering this | 1 | **3DR** RF Antenna 433 MHz RP-SMA | [3DR store](https://store.3dr.com/rf-antenna-433mhz-rp-sma/) | price not checked |
| R3 | RP-SMA extension, RG-316, 152 mm: **bulkhead socket with nut** at one end (it goes through the antenna bracket), plug at the other (onto the radio) | 1 | **Amphenol RF 095-902-536-006** | [Digi-Key UK](https://www.digikey.co.uk/en/products/detail/amphenol-rf/095-902-536-006/13246160) | price not checked (2024 listings: about $5–22) |
| R4 | Cable ties, 150 × 2.5 mm (hold the radio in its cradle; a 100 mm tie is too short to close round it) | 2 | **HellermannTyton** or any branded pack | Amazon UK [search](https://www.amazon.co.uk/s?k=HellermannTyton+cable+ties+150mm) | ≈ £3 |

The ground radio stays at the launch field with the laptop: it plugs into the laptop's USB (Chrome or Edge) and keeps the
second antenna from the box. Why this radio, and the UK rules it is set up for: [SAFETY_AND_LEGAL.md](SAFETY_AND_LEGAL.md#radio).

## 2. Servos, wiring, linkages

| # | Item | Qty | Brand / exact part | Where | Price |
|---|---|---|---|---|---|
| 7 | MG90S metal-gear micro servo (**unbranded OK**), lead ≥ 200 mm | 7 + 3 spare (10-pack) | 2 × TVC, 1 × parachute release, 4 × fin tabs | Amazon UK [search](https://www.amazon.co.uk/s?k=MG90S+metal+gear+servo+10+pack); UK alternatives: [Cool Components](https://coolcomponents.co.uk/products/mg90s-analog-metal-gear-servo) (TowerPro MG90S, ✔ £5.99 each), [Kunkune](https://kunkune.co.uk/shop/servo-motors-and-shields/servo-motor-mg90-metal-gear/) (✔ £2.39 each at 10+) | ≈ £20–25 |
| 8 | Servo extension lead, 300 mm | 5 | 1 for the parachute-release servo (port 3 → up through the payload-bay floor; the plug joint sits in the payload bay) and 1 for each tab servo: its lead starts at the fin tip, ≈ 280 mm from the board, and the extension leaves the slack to lift the av-bay out for charging and USB | **Adafruit 972** at [The Pi Hut](https://thepihut.com/products/servo-extension-cable-30cm-12-long) | ✔ about £1.90 each, ≈ £10 |
| 9 | M2 × 6 mm pan-head self-tapping screws | 8 | 2 per tab servo. **Not longer than 6 mm**: the lower hole ends just short of the tab gap (servo bags often hold longer screws) | **Accu** (UK) [accu.co.uk](https://accu.co.uk/) or a branded M2 self-tapping assortment | ≈ £3 |
| 10 | Music (piano) wire **1.2 mm** (0.047 in) and **0.6 mm** (0.025 in) | 1 length each | **K&S Precision Metals** or **Albion Alloys** | Amazon UK [search](https://www.amazon.co.uk/s?k=K%26S+music+wire) or any model shop | ≈ £6 |

1.2 mm wire: the 2 TVC pushrods (the fin tabs are driven directly by their servos). 0.6 mm wire: the springy latch
link.

## 3. Camera

| # | Item | Qty | Brand / exact part | Where | Price |
|---|---|---|---|---|---|
| 11 | SQ12-type 23 mm cube 1080p mini camera (**unbranded OK**) | 1 | must be a ≈ 23 mm cube with the lens in the middle of one face (it sits inside the bottom tube in a cradle behind the camera door) | Amazon UK [search](https://www.amazon.co.uk/s?k=SQ12+mini+camera) | ≈ £12–15 |
| 12 | microSD card 32 GB | 1 | **SanDisk** Ultra 32 GB | Amazon UK [search](https://www.amazon.co.uk/s?k=SanDisk+Ultra+32GB+microSD) | ≈ £6 |

Some SQ12 clones stop recording in 1080p after a while; record in 720p if yours does (a reviewer reported this).

## 4. Airframe, recovery and consumables

| # | Item | Qty | Brand / exact part | Where | Price |
|---|---|---|---|---|---|
| 13 | Body tube BT-70 (56.3 mm OD, 55.2 mm ID), ≥ 400 mm long | 2 | **Estes BT-70** (19.5 in tubes: cut 340 mm and 380 mm) | UK rocketry shops, e.g. [modelrockets.co.uk](https://modelrockets.co.uk/) | ≈ £16 |
| 14 | PETG filament 1.75 mm, 1 kg | 1 | **Amazon Basics PETG** (or Prusament / Polymaker) | Amazon UK [search](https://www.amazon.co.uk/s?k=Amazon+Basics+PETG+1.75mm+1kg) | ✔ about £12.59 |
| 15 | 36 in (91 cm) rip-stop nylon parachute (**unbranded OK**); thin rip-stop that rolls to about 44 × 90 mm | 1 | e.g. **Estes** 36 in rip-stop ([302249](https://edu.estesrockets.com/products/rip-stop-parachute-36-inch)) | UK rocketry shops, or Amazon UK [search](https://www.amazon.co.uk/s?k=36+inch+rocket+parachute) | ≈ £18–25 |
| 16 | Kevlar shock cord 1.6 mm, 2 m + elastic shock cord 1 m + small swivel | 1 set | Estes [Pro Series II shock cords](https://radioshack-of-bozeman-640025.shoplightspeed.com/est3172-shock-cords-for-model-rockets-pro-series-i.html) or a UK shop's kevlar by the metre | UK rocketry shops | ≈ £10 |
| 17 | Ejection spring 110 × 17.6 mm OD, 1.3 N/mm | 1 (pack of 10) | **RS PRO 121-236** (UK) | [RS Components](https://uk.rs-online.com/web/p/compression-springs/0121236) | ✔ £20.83 for 10 |
| 18 | 5-minute epoxy | 1 | **Araldite Rapid** | Amazon UK [search](https://www.amazon.co.uk/s?k=Araldite+Rapid) | ≈ £8 |
| 19 | Superglue (CA) | 1 | **Loctite** Super Glue | Amazon UK [search](https://www.amazon.co.uk/s?k=Loctite+super+glue) | ≈ £5 |
| 20 | Filler primer spray (+ a colour if you like) | 1–2 cans | **Rust-Oleum** filler primer (or Halfords) | Amazon UK [search](https://www.amazon.co.uk/s?k=Rust-Oleum+filler+primer) | ≈ £8–14 |
| 21 | Tough PLA filament 1.75 mm for the **legs** only (4 + 2 spares ≈ 30 g, printed solid) | — | your own extra-tough PLA | — | — |
| 22 | Double-sided foam tape, 1–2 mm (also the pad inside the battery-hatch door) | 1 roll | **Tesa** or **3M** mounting tape | Amazon UK [search](https://www.amazon.co.uk/s?k=tesa+double+sided+foam+tape) | ≈ £4 |
| 23 | Screws, nuts and washers (list below), plus **two 100-packs of M3 nuts for the nose ballast** | kit | **Accu** (UK) or a branded M2.5/M3/M4 assortment | [accu.co.uk](https://accu.co.uk/) or Amazon UK [search](https://www.amazon.co.uk/s?k=M3+stainless+screw+nut+assortment) | ≈ £13 |

Screws used: M2.5 × 8 self-tapping (3, the PCB); M3 × 10–16 + nuts (14: av-bay 2, fin can 2, gimbal pivots 4,
middle-part joint 2, pad legs 3, rod stop 1; plus 4 if you screw a payload to the bay floor); **M3 × 18 button head
(ISO 7380) + M3 nut** (4 + 2 spares: one through each leg; assortments often lack this length, so check, ≈ £3); about 145 more M3 nuts
(0.33 g each, [Fabory](https://www.fabory.com/en-GB/p/01100030001)) as the ≈ 51 g nose ballast; M2 × 6 self-tapping
(8, tab servos, row 9); the small screws that come with the servos (TVC and release servos); M4 × 16 (4,
tile clamps) + an M4 thumb screw (rod clamp); M6 × 70 bolt + wing nut (pad tilt); one M10 × 25 mm penny washer
(burn-through shield on top of the motor). The payload-door hinge pin is a 22 mm piece of your 1.75 mm filament.

## 5. Launch pad

| # | Item | Qty | Brand / exact part | Where | Price |
|---|---|---|---|---|---|
| 24 | Hardwood dowel 22 mm × 2.4 m (cut 3 × 600 mm) | 1 | any (DIY store) | Wickes / B&Q | ≈ £8 |
| 25 | Steel rod 6 mm × 1 m; optional second rod 6 mm × 1.5 m for winds above 3 m/s (see the test plan) | 1 | silver steel or stainless | B&Q / Amazon UK [search](https://www.amazon.co.uk/s?k=6mm+steel+rod+1m) | ≈ £8 |
| 26 | Ceramic floor tile 200 × 200 mm (blast plate the rocket stands on) | 1 | any | Wickes / B&Q / Topps Tiles | ≈ £3 |
| 27 | Tent pegs | 3 | **Vango** or **Coleman** | Amazon UK [search](https://www.amazon.co.uk/s?k=Vango+tent+pegs) | ≈ £5 |
| 28 | Launch controller with safety key (skip if your club provides one) | 1 | e.g. **Estes** Electron Beam | UK rocketry shops | ≈ £20 |

## 6. Motors (per flight, not in the build total)

| Motor (single use, CE certified) | Rated (UKROC list) | Use | Simulated apogee, 25 g payload | Where |
|---|---|---|---|---|
| **TSP F35-0** (29 mm, twin pack) | 65 Ns, 2.0 s, 92 g | **the mission** (test plan flight 3 onwards) | **157 m** (162 m if the motor performs like its published test curve) | [modelrockets.co.uk](https://modelrockets.co.uk/rocket-motors-and-consumables/all-rocket-motors-chooser/f35-0-twin-pack-29mm-tsp-model-rocket-motors-engine-mid-power/): about £25–30 per twin pack (the prices I saw differ; most F35 delays were out of stock when checked, so order early) |
| **TSP E20-0** (24 mm, in the printed adapter) | 36 Ns, 2.0 s, 64 g | **the first two flights** (buy a twin pack or two: a spare for a repeat) | 41 m (about 47 m with the empty bay of the first flights) | same shop |
| **TSP D20-0** (24 mm, in the printed adapter) | 20 Ns, 1.0 s | optional: not in the flight programme (14 m is too low for the parachute to open with room to spare) | 14 m | same shop |

Sold in the UK by [modelrockets.co.uk](https://modelrockets.co.uk/blog/tsp-rocket-motors-d20-e20-f35-rocket-motors-engines),
which states TSP motors are CE certified and legal to buy and use in the UK. Ratings from the
[UKROC Approved Motor List](https://modelrockets.co.uk/UKROC-Approved-Motor-List-v2.pdf). Use **"-0" (no delay)**
motors: KESTREL releases its parachute with a servo and never needs an ejection charge. Igniters come with the
motors. Buying motors usually requires you to be 18+. The shop lists the F35 as class 1.4S, like the Estes motors, with no
licence needed. Not for KESTREL-2: the TSP E12 (too little thrust for its mass). The 24 mm motors need the three
small printed adapter parts (sleeve, 24 mm retainer and, for the D20, a spacer); they are in `cad/stl/` with the
rest of the prints.

## Budget

| | £ |
|---|---|
| 1. Flight computer + electronics (without charger) | ≈ 107 |
| 1b. Telemetry radio (radio pair + antenna + extension + ties; two items not price-checked, counted at ≈ £15 each) | ≈ 86–105 |
| 2. Servos, wiring, linkages | ≈ 41 |
| 3. Camera + card | ≈ 20 |
| 4. Airframe, recovery, consumables | ≈ 125 |
| 5. Launch pad (without controller) | ≈ 24 |
| **Total** | **≈ £403–422** (≈ £317 without the radio) |
| with one primer can and a cheaper 36 in chute | ≈ £391–410 |
| plus charger / launch controller if you have neither | + £35–48 |

The telemetry radio (asked for after the £270 figure was agreed) adds ≈ £86–105. Without it, the rocket is
about **£35–47 over the agreed ~£270**. The overrun comes from what KESTREL-2 added since that figure:
four more servos, the bigger 36 in parachute it needs for gentle landings at its weight, and the ejection spring,
which RS only sells in packs of 10 (£21); putting the servos inside the fins added about £11 (longer tab-servo extensions, their M2
screws, the ballast nuts, and the step from a 30 in to a 36 in parachute for the extra weight). Biggest single item: the PCB order (≈ £80), which gives you **two**
assembled flight computers. The multi-flight changes (replaceable legs, battery hatch) added about £5: the
leg screws, a second balance adapter and an angled USB cable, minus the velcro strap they replaced; a second LiPo
(≈ £7) is worth having.
