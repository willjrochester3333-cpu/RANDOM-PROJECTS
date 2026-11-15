# Software setup

Do the nodes in this order. CORE must be first: it prints the MQTT password every other
node needs.

| Folder | Runs on | Language |
|---|---|---|
| `core/` | CORE, Raspberry Pi 5 | Python (FastAPI) + Mosquitto, in Docker |
| `console/` | CONSOLE, Raspberry Pi 5 + touchscreen | Python + Chromium kiosk |
| `outpost/` | OUTPOST, Raspberry Pi 3 + Sense HAT | Python |
| `kitchen/` | DINNER BELL, XIAO ESP32-S3 Sense | MicroPython |
| `beacon/` | BEACON, Pico 2 W | MicroPython |

## 1. CORE (server)

1. Flash **Raspberry Pi OS Lite (64-bit)** with Raspberry Pi Imager. In the Imager settings
   set the hostname to `jarvis-core`, enable SSH and enter your Wi-Fi.
2. In your router, reserve a fixed IP address for it. Note the address: the two
   microcontrollers need it.
3. Copy the `jarvis/` folder to the Pi, then:

   ```sh
   cd jarvis/core
   ./setup.sh
   ```

   It installs Docker, generates a random MQTT password, starts the broker and the brain,
   and prints the password. The dashboard is then at `http://jarvis-core.local/`.

4. Optional: for open-ended questions, put an Anthropic API key in `core/.env`
   (`ANTHROPIC_API_KEY=...`) and run `sudo docker compose up -d`. Without a key
   J.A.R.V.I.S. still answers weather and dinner questions.

Useful commands on CORE:

```sh
sudo docker compose logs -f brain      # what the brain is doing
sudo docker compose restart brain
```

## 2. DINNER BELL and BEACON (microcontrollers)

Both use MicroPython and Thonny.

1. Install MicroPython firmware:
   - **XIAO ESP32-S3**: the generic `ESP32_GENERIC_S3` build from micropython.org.
   - **Pico 2 W**: the `RPI_PICO2_W` build (hold BOOTSEL, plug in, drop the `.uf2` on it).
2. In Thonny: *Tools → Manage packages*, install `umqtt.simple` (the ESP32 build already
   has it).
3. Copy `config.example.py` to the board as `config.py` and fill in your Wi-Fi name and
   password, CORE's IP address and the MQTT password.
4. Copy `main.py` from `kitchen/` or `beacon/` to the board and reset it.

What you should see:

- **Bell**: the button light flickers while joining Wi-Fi, then goes dark. Press it: it
  blinks, the dashboard shows "Dinner is ready".
- **Beacon**: a blue dot circles while joining, then dark. When dinner is called it chimes
  and breathes amber. Press its button: it flashes green and the kitchen light goes solid.

If either board hits an error it waits 5 seconds and restarts itself.

## 3. OUTPOST (weather)

1. Flash **Raspberry Pi OS Lite**, hostname `jarvis-outpost`, Wi-Fi set (2.4 GHz).
2. Fit the Sense HAT, copy the `outpost/` folder over, then:

   ```sh
   cd outpost
   ./install.sh <mqtt-password>
   sudo reboot
   ```

Readings appear on the dashboard within a minute. If the temperature reads warm against a
thermometer you trust, set `TEMP_OFFSET` in `/etc/jarvis-outpost.env` and
`sudo systemctl restart jarvis-outpost`.

## 4. CONSOLE (touchscreen)

1. Flash **Raspberry Pi OS (64-bit, with desktop)**, hostname `jarvis-console`.
2. Plug in the USB speaker, copy the `console/` folder over, then:

   ```sh
   cd console
   ./install.sh <mqtt-password>
   sudo reboot
   ```

It boots into the full-screen dashboard and speaks announcements.

## What is and is not here

- **Working and tested together** (on a PC, with simulated hardware): broker, brain,
  dashboard, weather publishing, the whole dinner call / answer / clear cycle, spoken
  announcements, typed questions.
- **Not tested on real boards.** Pin numbers follow the wiring table in `README.md`.
- **Not written yet:** voice input (wake word and speech-to-text). You type questions on
  the touchscreen for now. Speech output uses `espeak-ng`, which is robotic; Piper is the
  natural-sounding upgrade.
- **Chat with an API key** uses the Anthropic API and was not exercised in testing (no key
  was available).

## Installing by paste (Raspberry Pi Connect)

If you control a Pi through Raspberry Pi Connect's terminal, you can skip copying files.
`install-codes/` holds one paste block per Pi (`core.txt`, `outpost.txt`, `console.txt`),
and `install-codes/index.html` shows them with Copy buttons. Paste the whole block into
the Pi's terminal: it unpacks that Pi's folder into `~/jarvis/`, and for CORE it also starts
`setup.sh`.

After changing any code, rebuild the blocks with:

```sh
python3 jarvis/tools/make_install_codes.py
```
