# Pico Dino Jump

A Chrome-style "Dino Jump" endless runner for the **Raspberry Pi Pico 2 W** +
**SSD1306 OLED** (128x64, I2C) from the Raspberry Pi / Pi Hut Advent Calendar
kit — controlled with the **Up/Down arrow keys on your computer's keyboard**,
sent to the Pico **wirelessly over Bluetooth Low Energy (BLE)**.

The game itself runs entirely on the Pico. Since the Pico has no way to read
your PC's keyboard directly, a small Python script runs on your computer,
listens for arrow key presses, and forwards them to the Pico's onboard
wireless chip as BLE messages. The Pico's game loop reads those messages
non-blockingly alongside its own game logic, so the dino reacts live as you
press keys.

```
[Your keyboard] -> [host/ble_keyboard_controller.py on PC] --BLE--> [pico/main.py on Pico] -> [OLED]
```

Once it's set up, the Pico only needs **power** (not a data connection) to
your laptop — a USB power bank, USB charger, or battery pack all work, since
the control link travels over Bluetooth instead of the USB cable. A wired
USB-serial control script is also included (`host/keyboard_controller.py`)
as a simpler fallback for testing before you pair over Bluetooth — both
control paths work at the same time, the Pico just reacts to whichever
sends a command.

## Hardware

- Raspberry Pi Pico 2 W (its onboard wireless chip provides the Bluetooth)
- SSD1306 OLED display, 128x64, I2C (from the Advent Calendar kit)
- Breadboard + jumper wires
- USB cable (for programming, and for power if you're not using a battery)
- Optional: a push button from the kit, for a physical "jump" button
- Optional: a USB power bank / battery pack, once you want to run the Pico
  untethered from your laptop

## Wiring

Default pins used by `pico/main.py` (matches the common Advent Calendar OLED
wiring — change the constants at the top of `main.py` if your kit's guide
wires it differently):

| OLED pin | Pico pin      |
|----------|---------------|
| VCC      | 3V3 (pin 36)  |
| GND      | GND (any GND) |
| SDA      | GP0 (pin 1)   |
| SCL      | GP1 (pin 2)   |

Optional physical jump button (disabled by default): wire one leg to GND and
the other to GP16, then set `PHYSICAL_BUTTON_PIN = 16` near the top of
`main.py`.

## 1. Set up Thonny

1. Install [Thonny](https://thonny.org) (it bundles Python, so no separate
   install needed on most systems).
2. Plug in the Pico with a USB cable, then in Thonny go to
   **Tools → Options → Interpreter**, choose **MicroPython (Raspberry Pi
   Pico)** as the interpreter, and pick the Pico's USB/serial port.
3. If the board doesn't already have MicroPython on it (or has an old
   version), click **Install or update MicroPython (Pico)** near the
   bottom of that same Interpreter dialog. Select the **Pico 2 W** variant
   and target — Bluetooth (BLE) support needs a reasonably up to date
   firmware build. Follow the prompts (usually: hold BOOTSEL while
   plugging in, then click Install).
4. Once Thonny shows a `>>>` prompt connected to the board, open
   **View → Files** to show a Pico file panel alongside your computer's
   files.
5. Open each of these files from this repo's `pico/` folder in Thonny
   (File → Open) and use **File → Save As → Raspberry Pi Pico**, saving
   each with the *same* filename onto the board:
   - `pico/main.py` → save as `main.py` on the Pico
   - `pico/ssd1306.py` → save as `ssd1306.py` on the Pico
   - `pico/ble_uart_peripheral.py` → save as `ble_uart_peripheral.py` on
     the Pico
   Saving it as `main.py` makes the game start automatically whenever the
   Pico is powered on.
6. Wire up the OLED as above and power the Pico. You should see a
   "DINO JUMP / Press UP to start / BLE: waiting.." screen — that confirms
   the display, firmware, and Bluetooth advertising are all working, even
   before you connect the keyboard controller. (If a Thonny Shell session
   is still attached and showing the REPL instead, click the red Stop/
   Restart button, or just power-cycle the board.)

## 2. Run the Bluetooth keyboard controller on your PC

Disconnect Thonny from the board first (Run → Disconnect, or close Thonny) —
it isn't required for BLE, but it's good practice while testing, and it's
required if you want to try the wired fallback below afterwards.

```bash
cd host
pip install -r requirements.txt
python ble_keyboard_controller.py
```

It scans for a BLE device named `PicoDino` (the Pico's default advertised
name — change `BLE_NAME` at the top of `pico/main.py` and pass
`--name YourName` to the script if you rename it) and connects automatically.
Once you see "Connected", the OLED's start screen should switch from
"BLE: waiting.." to "BLE: connected", and the arrow keys will control the
game.

If Bluetooth pairing/scanning gives you trouble (permissions, drivers,
adapter issues), you can fall back to the wired option below to confirm the
game itself works, then come back to debug BLE.

### Wired fallback (USB serial)

```bash
cd host
pip install -r requirements.txt
python keyboard_controller.py
```

This needs the Pico's serial port free — make sure Thonny is disconnected
from the board first (only one program can hold the USB serial port open at
a time). It tries to auto-detect the Pico's serial port; if it can't, it
lists the available ports so you can pass the right one as an argument
(e.g. `python keyboard_controller.py COM5` on Windows,
`python keyboard_controller.py /dev/ttyACM0` on Linux, or
`python keyboard_controller.py /dev/cu.usbmodemXXXX` on macOS).

## Controls

- **Up arrow** — jump (also starts the game, and restarts after game over)
- **Down arrow** — duck (hold it down to pass under birds)
- **Esc** (in the controller script's terminal) — quit the controller

## Tuning

Near the top of `pico/main.py`:

- `GRAVITY` / `JUMP_VELOCITY` — jump feel
- `speed` (in `game_loop`) and the speed-up rate — difficulty ramp
- `PHYSICAL_BUTTON_PIN` — set to a GPIO number to enable a wired jump button
  alongside the keyboard
- `BLE_NAME` — the name the Pico advertises over Bluetooth

## Troubleshooting

- **Nothing shows on the OLED**: double-check SDA/SCL wiring and that the
  I2C address matches (`OLED_ADDR = 0x3C` is standard for these boards; a
  few are `0x3D`).
- **BLE controller can't find the Pico**: make sure `main.py` is actually
  running (power-cycle the board and check the OLED shows the start
  screen), that your laptop's Bluetooth is turned on, and that the Pico
  isn't already connected to something else — it only accepts one BLE
  connection at a time, so close any other app (like a "nRF Connect" style
  BLE scanner) that might already be connected to it.
- **Wired controller script can't open the port / "port is busy"**: make
  sure Thonny (or any other program) isn't still connected to the Pico's
  serial port — disconnect it (Run → Disconnect) or close Thonny first.
- **Key presses don't do anything**: make sure the controller script's
  terminal window shows "Connected" — if `pynput` can't find a keyboard
  listener permission (mainly on macOS), grant your terminal app
  Accessibility / Input Monitoring permission in System Settings.
