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

## 1. Set up VS Code with the Raspberry Pi Pico extension

1. Install the **Raspberry Pi Pico** extension for VS Code (search
   "Raspberry Pi Pico" in the Extensions panel).
2. Use the extension's "New Project" / "Import Project" flow to create a
   project, and make sure it flashes **MicroPython** firmware for the
   **Pico 2 W** onto the board (the extension will prompt you to pick the
   board type and download firmware the first time). Use a recent firmware
   build — Bluetooth (BLE) support for Pico 2 W needs a reasonably up to
   date MicroPython release.
3. Copy these three files from this repo's `pico/` folder into the root of
   your VS Code Pico project:
   - `pico/main.py`
   - `pico/ssd1306.py`
   - `pico/ble_uart_peripheral.py`
4. Use the extension's "Run" / "Upload" button to copy all three files onto
   the Pico's filesystem, keeping the same names. Uploading `main.py` makes
   the game start automatically whenever the Pico is powered on.
5. Wire up the OLED as above and power the Pico. You should see a
   "DINO JUMP / Press UP to start / BLE: waiting.." screen — that confirms
   the display, firmware, and Bluetooth advertising are all working, even
   before you connect the keyboard controller.

## 2. Run the Bluetooth keyboard controller on your PC

Close any serial monitor / REPL terminal the Pico extension has open (it
isn't required for BLE, but it's good practice while testing).

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

This needs the Pico's serial port free — close any serial monitor / REPL
terminal the Pico extension has open first (only one program can hold the
USB serial port open at a time). It tries to auto-detect the Pico's serial
port; if it can't, it lists the available ports so you can pass the right
one as an argument (e.g. `python keyboard_controller.py COM5` on Windows,
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
- **Wired controller script can't open the port / "port is busy"**: close
  VS Code's serial monitor or any other program (Thonny, `screen`, etc.)
  connected to the Pico first.
- **Key presses don't do anything**: make sure the controller script's
  terminal window shows "Connected" — if `pynput` can't find a keyboard
  listener permission (mainly on macOS), grant your terminal app
  Accessibility / Input Monitoring permission in System Settings.
