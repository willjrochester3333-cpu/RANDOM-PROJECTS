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
| 1 | **KESTREL FC v2 board**, made and assembled by JLCPCB | 2 assembled + 3 bare | upload `pcb/production/` (see [PCB.md](PCB.md#ordering-from-jlcpcb)) | [jlcpcb.com](https://jlcpcb.com) | ≈ £80 |
| 2 | Raspberry Pi Pico 2 **W with headers** (2 WH) | 1 | Raspberry Pi (UK) | [The Pi Hut](https://thepihut.com/collections/latest-raspberry-pi-products/products/raspberry-pi-pico-2-w) (choose "with headers") | ≈ £7 |
| 3 | 2S 7.4 V 350 mAh 25C LiPo, **about 40 × 19 × 15 mm** (the tray takes up to 16 mm; one shop lists 25 mm: check) | 1 | **Overlander OL-3492** (UK) | [overlander.co.uk](https://overlander.co.uk/350mah-7-4v-2s-25c-lipo-battery.html) | ✔ about £7 |
| 4 | JST-PH → JST-XH 2S balance adapter lead | 1 | **Overlander OL-2529** | [overlander.co.uk](https://www.overlander.co.uk/jst-ph-to-jst-xh-balance-conversion-lead-for-130x-beast.html) | ✔ £1.58 |
| 5 | GPS antenna, passive 15 × 15 mm, U.FL | 1 | **Adafruit 2461** (US, international) | [The Pi Hut](https://www.thepihut.com/product/2461) | ✔ £3.90 |
| 6 | 2S LiPo balance charger (skip if you have one) | 1 | SkyRC or ISDT USB-powered 2S/3S balance charger | Amazon UK [search](https://www.amazon.co.uk/s?k=SkyRC+lipo+balance+charger+2S) | ≈ £15–28 |

## 2. Servos, wiring, linkages

| # | Item | Qty | Brand / exact part | Where | Price |
|---|---|---|---|---|---|
| 7 | MG90S metal-gear micro servo (**unbranded OK**), lead ≥ 200 mm | 7 + 3 spare (10-pack) | 2 × TVC, 1 × parachute release, 4 × fin tabs | Amazon UK [search](https://www.amazon.co.uk/s?k=MG90S+metal+gear+servo+10+pack); UK alternatives: [Cool Components](https://coolcomponents.co.uk/products/mg90s-analog-metal-gear-servo) (TowerPro MG90S, ✔ £5.99 each), [Kunkune](https://kunkune.co.uk/shop/servo-motors-and-shields/servo-motor-mg90-metal-gear/) (✔ £2.39 each at 10+) | ≈ £20–25 |
| 8 | Servo extension lead, 300 mm | 1 | for the parachute-release servo: port 3 → up through the payload-bay floor; the plug joint sits in the payload bay | Amazon UK [search](https://www.amazon.co.uk/s?k=servo+extension+lead+300mm+JR) | ≈ £3 |
| 9 | Servo extension lead, 150 mm | 4 | for the 4 tab servos: their own ≈ 250 mm leads only just reach the board; the extensions give the slack to lift the av-bay out for charging and USB | [The Pi Hut](https://thepihut.com/products/servo-extension-cable-150mm) | ≈ £6 |
| 10 | Music (piano) wire **1.2 mm** (0.047 in) and **0.6 mm** (0.025 in) | 1 length each | **K&S Precision Metals** or **Albion Alloys** | Amazon UK [search](https://www.amazon.co.uk/s?k=K%26S+music+wire) or any model shop | ≈ £6 |

1.2 mm wire: 2 TVC pushrods, 4 tab pushrods, 4 tab hinge pins (27 mm each). 0.6 mm wire: the springy latch link.

## 3. Camera

| # | Item | Qty | Brand / exact part | Where | Price |
|---|---|---|---|---|---|
| 11 | SQ12-type 23 mm cube 1080p mini camera (**unbranded OK**) | 1 | must be a ≈ 23 mm cube with the lens in the middle of one face (fits the pod) | Amazon UK [search](https://www.amazon.co.uk/s?k=SQ12+mini+camera) | ≈ £12–15 |
| 12 | microSD card 32 GB | 1 | **SanDisk** Ultra 32 GB | Amazon UK [search](https://www.amazon.co.uk/s?k=SanDisk+Ultra+32GB+microSD) | ≈ £6 |

Some SQ12 clones stop recording in 1080p after a while; record in 720p if yours does (a reviewer reported this).

## 4. Airframe, recovery and consumables

| # | Item | Qty | Brand / exact part | Where | Price |
|---|---|---|---|---|---|
| 13 | Body tube BT-70 (56.3 mm OD, 55.2 mm ID), ≥ 400 mm long | 2 | **Estes BT-70** (19.5 in tubes: cut 340 mm and 380 mm) | UK rocketry shops, e.g. [modelrockets.co.uk](https://modelrockets.co.uk/) | ≈ £16 |
| 14 | PETG filament 1.75 mm, 1 kg | 1 | **Amazon Basics PETG** (or Prusament / Polymaker) | Amazon UK [search](https://www.amazon.co.uk/s?k=Amazon+Basics+PETG+1.75mm+1kg) | ✔ about £12.59 |
| 15 | 30 in (76 cm) nylon parachute (**unbranded OK**) | 1 | e.g. **Estes** 30 in rip-stop ([302248](https://edu.estesrockets.com/products/rip-stop-parachute-30-inch)) or Pro Series II 30 in ([002273](https://estesrockets.com/products/pro-series-ii%E2%84%A2-30-inch-nylon-parachute)) | UK rocketry shops, or Amazon UK [search](https://www.amazon.co.uk/s?k=30+inch+rocket+parachute) | ≈ £15–20 |
| 16 | Kevlar shock cord 1.6 mm, 2 m + elastic shock cord 1 m + small swivel | 1 set | Estes [Pro Series II shock cords](https://radioshack-of-bozeman-640025.shoplightspeed.com/est3172-shock-cords-for-model-rockets-pro-series-i.html) or a UK shop's kevlar by the metre | UK rocketry shops | ≈ £10 |
| 17 | Ejection spring 110 × 17.6 mm OD, 1.3 N/mm | 1 (pack of 10) | **RS PRO 121-236** (UK) | [RS Components](https://uk.rs-online.com/web/p/compression-springs/0121236) | ✔ £20.83 for 10 |
| 18 | 5-minute epoxy | 1 | **Araldite Rapid** | Amazon UK [search](https://www.amazon.co.uk/s?k=Araldite+Rapid) | ≈ £8 |
| 19 | Superglue (CA) | 1 | **Loctite** Super Glue | Amazon UK [search](https://www.amazon.co.uk/s?k=Loctite+super+glue) | ≈ £5 |
| 20 | Filler primer spray (+ a colour if you like) | 1–2 cans | **Rust-Oleum** filler primer (or Halfords) | Amazon UK [search](https://www.amazon.co.uk/s?k=Rust-Oleum+filler+primer) | ≈ £8–14 |
| 21 | Hook-and-loop strap 10–20 mm | 1 | **VELCRO** brand ONE-WRAP | Amazon UK [search](https://www.amazon.co.uk/s?k=VELCRO+ONE-WRAP) | ≈ £5 |
| 22 | Double-sided foam tape, 1–2 mm | 1 roll | **Tesa** or **3M** mounting tape | Amazon UK [search](https://www.amazon.co.uk/s?k=tesa+double+sided+foam+tape) | ≈ £4 |
| 23 | Screws, nuts and washers (list below) | kit | **Accu** (UK) or a branded M2.5/M3/M4 assortment | [accu.co.uk](https://accu.co.uk/) or Amazon UK [search](https://www.amazon.co.uk/s?k=M3+stainless+screw+nut+assortment) | ≈ £10 |

Screws used: M2.5 × 8 self-tapping (4, the PCB); M3 × 10–16 + nuts (12: av-bay 2, fin can 2, gimbal pivots 4,
middle-part joint 2, pad legs 3, rod stop 1); the small screws that come with the servos (servo tabs); M4 × 16 (4,
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

| Motor (24 mm, single use, CE certified) | Rated (UKROC list) | Use | Simulated apogee, 25 g payload |
|---|---|---|---|
| **TSP D20-0** | 20 Ns, 1.0 s | first test hops | 29 m |
| **TSP E20-0** | 36 Ns, 2.0 s, 64 g | **the mission** | **78 m** (95 m if the motor performs like its published test curve, 40 Ns) |

Sold in the UK by [modelrockets.co.uk](https://modelrockets.co.uk/blog/tsp-rocket-motors-d20-e20-f35-rocket-motors-engines),
which states TSP motors are CE certified and legal to buy and use in the UK. Ratings from the
[UKROC Approved Motor List](https://modelrockets.co.uk/UKROC-Approved-Motor-List-v2.pdf). Use **"-0" (no delay)**
motors: KESTREL releases its parachute with a servo and never needs an ejection charge. Igniters come with the
motors. Buying motors usually requires you to be 18+. Not for KESTREL-2: the TSP E12 (too little thrust for its
mass) and the 29 mm F35 (does not fit the 24 mm gimbal).

## Budget

| | £ |
|---|---|
| 1. Flight computer + electronics (without charger) | ≈ 100 |
| 2. Servos, wiring, linkages | ≈ 37 |
| 3. Camera + card | ≈ 20 |
| 4. Airframe, recovery, consumables | ≈ 120 |
| 5. Launch pad (without controller) | ≈ 24 |
| **Total** | **≈ £301** |
| with one primer can and a cheaper 30 in chute | ≈ £289 |
| plus charger / launch controller if you have neither | + £35–48 |

This is about **£20–30 over the agreed ~£270**. The overrun comes from what KESTREL-2 added since that figure:
four more servos, the bigger 30 in parachute it needs for gentle landings at its weight, and the ejection spring,
which RS only sells in packs of 10 (£21). Biggest single item: the PCB order (≈ £80), which gives you **two**
assembled flight computers.
