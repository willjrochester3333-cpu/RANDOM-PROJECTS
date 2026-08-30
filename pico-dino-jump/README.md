# Pico Dino Jump

A Chrome-style "Dino Jump" endless runner for the **Raspberry Pi Pico 2 W** +
**SSD1306 OLED** (128x64, I2C) from the Raspberry Pi / Pi Hut Advent Calendar
kit — controlled with the **Up/Down arrow keys on your computer's keyboard**.

The game itself runs entirely on the Pico. Since the Pico has no way to read
your PC's keyboard directly, a small Python script runs on your computer,
listens for arrow key presses, and forwards them to the Pico over the same
USB cable you use to program it (as simple serial bytes). The Pico's game
loop reads those bytes non-blockingly alongside its own game logic.

```
[Your keyboard] -> [host/keyboard_controller.py on PC] -> USB serial -> [pico/main.py on Pico] -> [OLED]
```

## Hardware

- Raspberry Pi Pico 2 W
- SSD1306 OLED display, 128x64, I2C (from the Advent Calendar kit)
- Breadboard + jumper wires
- USB cable (Pico to PC)
- Optional: a push button from the kit, for a physical "jump" button

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
   board type and download firmware the first time).
3. Copy the two files from this repo's `pico/` folder into the root of your
   VS Code Pico project:
   - `pico/main.py`
   - `pico/ssd1306.py`
4. Use the extension's "Run" / "Upload" button to copy both files onto the
   Pico's filesystem as `main.py` and `ssd1306.py`. Uploading as `main.py`
   makes the game start automatically whenever the Pico is powered on.
5. Wire up the OLED as above and power the Pico. You should see a
   "DINO JUMP / Press UP to start" screen — that confirms the display and
   firmware are working even before you connect the keyboard controller.

## 2. Run the keyboard controller on your PC

The controller script needs the Pico's serial port free, so **close any
serial monitor / REPL terminal the Pico extension has open** before running
it (only one program can hold the USB serial port open at a time).

```bash
cd host
pip install -r requirements.txt
python keyboard_controller.py
```

It tries to auto-detect the Pico's serial port. If it can't, it will list
the available ports — pass the right one as an argument:

```bash
python keyboard_controller.py COM5          # Windows
python keyboard_controller.py /dev/ttyACM0  # Linux
python keyboard_controller.py /dev/cu.usbmodemXXXX  # macOS
```

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

## Troubleshooting

- **Nothing shows on the OLED**: double-check SDA/SCL wiring and that the
  I2C address matches (`OLED_ADDR = 0x3C` is standard for these boards; a
  few are `0x3D`).
- **Controller script can't open the port / "port is busy"**: close VS
  Code's serial monitor or any other program (Thonny, `screen`, etc.)
  connected to the Pico first.
- **Key presses don't do anything**: make sure the controller script's
  terminal window shows "Connected" — if `pynput` can't find a keyboard
  listener permission (mainly on macOS), grant your terminal app
  Accessibility / Input Monitoring permission in System Settings.
