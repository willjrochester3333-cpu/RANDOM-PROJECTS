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

4. Questions are answered by the house itself where it can, and otherwise by a language model
   running on this Pi (Ollama, see "Talking to J.A.R.V.I.S." below). No accounts or keys needed.

Useful commands on CORE:

```sh
sudo docker compose logs -f brain      # what the brain is doing
sudo docker compose restart brain
```

## 2. KITCHEN CAMERA and BEACON (microcontrollers)

Both use MicroPython and Thonny.

### Kitchen camera (Seeed XIAO ESP32S3 Sense)

Live camera and microphone for the dashboard, plus the dinner button. Standard MicroPython
has no camera driver, so this board needs a MicroPython build that includes one:

1. Download `mpy_cam-v1.27.0-XIAO_ESP32S3.zip` from the Releases page of
   github.com/cnadler86/micropython-camera-API and unzip it.
2. Put the board in download mode: hold its **BOOT** button while plugging in the USB-C cable.
3. In Thonny: *Tools → Options → Interpreter*, choose *MicroPython (ESP32)*, click
   *Install or update MicroPython (esptool)*. Pick the board's port, then use the **≡** menu
   next to the Install button: *Select local MicroPython image* and choose the `.bin` file
   from the zip. Click *Install*. Unplug and plug the board back in.
4. Copy `kitchen/config.example.py` to the board as `config.py` and fill in your Wi-Fi, the
   server's IP address and the MQTT password. Copy `kitchen/main.py` to the board, then reset it.

Within a few seconds the dashboard's camera panel gets a **Kitchen camera** button. Tap
**Listen** on it to hear the kitchen. The board only streams while someone watches or listens.

- **Dinner button**: optional, as before: button from D1 to GND, its light on D2.
- **Leave D3 unconnected**: the microphone uses it internally.
- **Upside down picture**: set `CAMERA_FLIP = True` in `config.py`.
- **Too quiet or too loud**: change `MIC_GAIN` (1 to 64, default 16).
- **Board running hot**: lower `CAMERA_FPS` or use `CAMERA_SIZE = "QVGA"`.
- **Private key**: the board makes its own key on first start and keeps it in `key.txt`. Only
  the server learns it, so other devices on your network can't watch the camera directly.

The microphone is read in a way MicroPython doesn't support natively: the board collects the
microphone's raw bits and converts them to sound itself. That conversion was tested here
against a simulated microphone, not on a real board yet. If **Listen** gives only silence or
noise, tell Claude what you hear.

### Beacon (Pico 2 W)

1. Install the `RPI_PICO2_W` MicroPython build (hold BOOTSEL, plug in, drop the `.uf2` on it).
2. In Thonny: *Tools → Manage packages*, install `umqtt.simple`.
3. Copy `beacon/config.example.py` to the board as `config.py` and fill it in, then copy
   `beacon/main.py` to the board and reset it.

What you should see:

- **Kitchen button**: the button light flickers while joining Wi-Fi, then goes dark. Press it:
  it blinks, the dashboard shows "Dinner is ready".
- **Beacon**: a blue dot circles while joining, then dark. When dinner is called it chimes
  and breathes amber. Press its button: it flashes green and the kitchen light goes solid.

If either board hits an error it waits 5 seconds and restarts itself.

## 3. OUTPOST (weather)

1. Flash **Raspberry Pi OS Lite**, hostname `jarvis-outpost`, Wi-Fi set (2.4 GHz).
2. Fit the Sense HAT, copy the `outpost/` folder over, then:

   ```sh
   cd outpost
   ./install.sh <mqtt-password> <core-ip-address>
   sudo reboot
   ```

   The IP address is optional if `jarvis-core.local` works on your network; many home
   networks do not pass those names along, so the address is the safer choice.

Readings appear on the dashboard within a minute. If the temperature reads warm against a
thermometer you trust, set `TEMP_OFFSET` in `/etc/jarvis-outpost.env` and
`sudo systemctl restart jarvis-outpost`.

## 4. CONSOLE (touchscreen)

1. Flash **Raspberry Pi OS (64-bit, with desktop)**, hostname `jarvis-console`.
2. Plug in the USB speaker, copy the `console/` folder over, then:

   ```sh
   cd console
   ./install.sh <mqtt-password> <core-ip-address>
   sudo reboot
   ```

It boots into the full-screen dashboard and speaks announcements.

## Talking to J.A.R.V.I.S. (on CORE)

Plug a USB microphone and a USB speaker into the server, then run `bash setup.sh` again in
`core/` (or paste the CORE block). It adds three things to the server:

- **Ollama**, a language model running on the Pi itself. The model (`OLLAMA_MODEL` in
  `.env`, default `llama3.2:1b`, about 1.3 GB) is downloaded once by `setup.sh`.
- **Speech**, a container with Whisper (hears you) and Piper (the voice). Its models are
  downloaded while the container is built, which takes a while the first time.
- **Voice**, a small service on the Pi itself that owns the microphone and speaker. Say
  **"Hey Jarvis"**, wait for the beep, ask your question. The dashboard's **Talk** button does
  the same without the wake word, and typed questions get the same answers.

### How a question is answered

Fastest first:

1. **Instant answers from the house**, in a few thousandths of a second: the time, the date,
   the outdoor temperature, the local forecast ("will it rain tomorrow", "do I need a coat",
   sunrise, sunset), dinner, which devices are offline, sums ("what's 23 times 47", "15 percent
   of 80") and "say that again".
2. **The same question again** within 15 minutes gets the same answer, instantly (not for
   questions about the time or the house, whose answers change).
3. **The local model** (Ollama) for everything else. Its answer is shown and spoken in pieces
   as it is written, starting at the first comma, and **Stop** (the Talk button, while Jarvis is
   busy) ends it.

The local model is quick because it never reads the same thing twice. Ollama keeps what it read
last, and each request starts with exactly that: the same instructions, then the conversation
word for word. And as soon as you say "Hey Jarvis", press Talk or click in the question box, the
model reads the conversation and the house report while you are still speaking or typing, so
when your question arrives it only reads your own few words. A spoken question also waits about
0.8 seconds for you to finish and about a second to be turned into text.

With every question the model gets a house report: the date and time (`TZ`) and the outdoor
temperature, plus, when the question is about them, the weather station's details, the last 24
hours, a 3-day forecast with sunrise and sunset from Open-Meteo (needs `LOCATION_LAT` and
`LOCATION_LON` in `.env`), dinner and the devices. Everything else it knows from its training,
which for a small model is patchy; it is told to say when it isn't sure. Conversations are
forgotten after 3 quiet minutes. Each answer writes a line with its timings to the server log:

    sudo docker compose -f ~/jarvis/core/docker-compose.yml logs -f brain | grep timing

### Choosing the best model for your Pi

`bash ~/jarvis/core/bench.sh` compares small models on your Pi with Jarvis's own prompt and
settings: how soon each starts answering, how fast it writes, and how many of 14 everyday
questions it gets right. It downloads each model, tests it and deletes it again (add `--keep`
to keep them), takes about 5 to 15 minutes, and ends with a table and a recommendation. To try
other models: `bash ~/jarvis/core/bench.sh qwen2.5:1.5b llama3.2:3b`. Jarvis answers slowly while
it runs. To switch, set `OLLAMA_MODEL` in `core/.env` and run `bash setup.sh` again.

Useful settings in `core/.env` (run `bash setup.sh` again after changing them):

| Setting | What it does |
|---|---|
| `CHAT_BACKEND` | `ollama` (default, the local model) or `builtin` (no model: weather and dinner only) |
| `OLLAMA_MODEL` | any model from ollama.com/library that fits in RAM; `bench.sh` compares them |
| `OLLAMA_THREADS` | processor cores for the model (default 3, leaving one for camera and speech) |
| `MAX_REPLY_TOKENS` | longest answer (default 400, about 300 words); answers that reach it end on a full sentence |
| `TZ`, `LOCATION_NAME`, `LOCATION_LAT`, `LOCATION_LON` | time zone, place name and coordinates for the date, sunrise and forecast |
| `MIC_DEVICE`, `SPEAKER_DEVICE` | normally `default`; otherwise a name from `arecord -L` / `aplay -L` |
| `WAKE_WORD` | `0` turns the wake word off, leaving only the Talk button |
| `WAKE_THRESHOLD` | raise towards `0.8` if it wakes up by itself, lower towards `0.3` if it ignores you |

Checks: `arecord -l` and `aplay -l` list the USB devices; `journalctl -u jarvis-voice -f`
shows what the voice service hears; `arecord -d 3 test.wav && aplay test.wav` records and
plays back three seconds. If the console Pi also has a speaker, both will speak.

## 5. CAMERA (optional, any Pi with a camera module)

Plug the camera ribbon into the Pi with the power off. A Raspberry Pi 5 needs the
narrower Pi 5 camera cable; a Pi 3 uses the standard wide one. Then copy the `camera/`
folder over (or paste the CAMERA block from `install-codes/`) and run:

```sh
bash camera/install.sh <mqtt-password> <core-ip-address>
```

A Camera panel appears on the dashboard within a few seconds. Tap it to fill the screen.
The camera only switches on while someone is watching. If the picture is upside down,
set `CAMERA_ROTATE=1` in `/etc/jarvis-camera.env` and run `sudo systemctl restart jarvis-camera`.

Anyone on your home network who opens the dashboard can see the camera.

## What is and is not here

- **Working and tested together** (on a PC, with simulated hardware): broker, brain,
  dashboard, weather publishing, the whole dinner call / answer / clear cycle, spoken
  announcements, typed questions.
- **Not tested on real boards.** Pin numbers follow the wiring table in `README.md`.
- **Voice** (wake word, speech-to-text, local model, text-to-speech) was tested end to end
  with a fake microphone and stand-in speech models; the real Whisper and Piper models and
  Ollama itself have not been run here. The touchscreen's own speaker still uses `espeak-ng`.
- **Model speed and accuracy on a real Pi** have not been measured here; `bench.sh` measures
  them on yours.

## Installing with one line (Raspberry Pi Connect)

If you control a Pi through Raspberry Pi Connect's terminal, you can skip copying files.
`install-codes/index.html` shows one short line per Pi with a Copy button (the same lines are
in `install-codes/*.txt`). Paste it into the Pi's terminal: the Pi downloads this branch from
GitHub, unpacks only its own folder into `~/jarvis/`, and for CORE starts `setup.sh`. Settings
such as `core/.env` are not in the repository, so updating never touches your passwords
or other settings. The repository must be public for the download to work. (Large pasted blocks crash
Pi Connect's terminal, which is why the lines download instead.)

After changing the page text, or the branch it downloads from, rebuild it with:

```sh
python3 jarvis/tools/make_install_codes.py
```
