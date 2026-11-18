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
2. **The same question again** within 15 minutes gets the same internet answer, instantly.
3. **Claude with live web search**, once you add an Anthropic API key (below): accurate on
   almost any question. It searches the web only when the answer could have changed (news,
   sport, prices, opening times, who holds a job now) and answers settled facts straight
   away. While it searches, Jarvis says "Let me look that up", and the dashboard lists the
   sites the answer came from.
4. **The local model** when there is no key or no internet; Jarvis says which.

Every answer is shown and spoken sentence by sentence as it is written, and **Stop** (the
Talk button, while Jarvis is busy) ends it. A spoken question also waits about 0.8 seconds
for you to finish and about a second to be turned into text, so even instant answers take
about 2 seconds by voice; typed ones appear at once. Rough estimates for Claude's first words,
not yet measured on your Pi: 1 to 3 seconds without a search, 3 to 8 with one. Each answer
writes a line with its real timings to the server log:

    sudo docker compose -f ~/jarvis/core/docker-compose.yml logs -f brain | grep timing

Without a key, questions the house can't answer go to the local model, which gets a house
report with every question (date, time, weather, forecast, dinner, devices) but otherwise only
knows what it learned in training, which for a small model is patchy. It is quick on
follow-ups because the conversation is sent to it word for word, so it only reads the new
question. Conversations are forgotten after 3 quiet minutes.

### Internet answers: adding an API key

1. Sign in to the Claude Console at platform.claude.com, add some credit, and create an API key.
2. On CORE run `bash ~/jarvis/core/set-key.sh` and paste the key (it doesn't show on screen).
   It checks the key with Anthropic, saves it in `core/.env` and restarts the server.
3. Ask something only the internet knows, such as "who won the last Formula 1 race?"

Web search is on for new accounts. If an organisation admin has turned it off (Console,
Capabilities), Jarvis says "Web search is switched off for this API account" and answers from
the local model. If Claude declines a question, Anthropic passes it to a backup model
(server-side fallbacks; on by default for `claude-opus-5-5`).

**What it costs** (Anthropic's prices in November 2026, US dollars): `claude-opus-5-5` costs $4
per million tokens read and $20 per million written. A web search costs 1 cent, and the pages
it reads count as tokens read. Roughly, a question costs about 1 cent without a search and 3 to
15 cents with searches; instant answers and repeats cost nothing. `claude-haiku-5-5` costs about
a fortieth as much per token ($0.10 and $0.50 per million). Fast mode doubles the token price.
The Console shows what you have spent.

Useful settings in `core/.env` (run `bash setup.sh` again after changing them):

| Setting | What it does |
|---|---|
| `CHAT_BACKEND` | `auto` (default: Claude when a key is set, else the local model), `claude`, `ollama` (local only) or `builtin` |
| `ANTHROPIC_API_KEY` | your key; `set-key.sh` fills it in |
| `ONLINE_MODEL` | `claude-opus-5-5` (default, most accurate), or for example `claude-haiku-5-5` (usually quicker, far cheaper, knows less) |
| `ONLINE_EFFORT` | how hard Claude thinks first: `low` (default, quickest), `medium`, `high` |
| `ONLINE_FAST_MODE` | `1`: once it starts, the answer arrives up to 2.5 times faster, at twice the price (`claude-opus-5-5`) |
| `WEB_SEARCHES` | most searches per question (default 2) |
| `SEARCH_FILTERING` | `1`: Claude runs a small program over the search results first and reads only what matters; cheaper on long searches, one more step |
| `OLLAMA_MODEL` | the local model: any model from ollama.com/library that fits in RAM |
| `OLLAMA_THREADS` | processor cores for the local model (default 3, leaving one for camera and speech) |
| `MAX_REPLY_TOKENS` | longest local answer (default 400, about 300 words); answers that reach it end on a full sentence |
| `TZ`, `LOCATION_NAME`, `LOCATION_LAT`, `LOCATION_LON` | time zone, place name and coordinates for the date, sunrise and forecast |
| `LOCATION_COUNTRY` | two-letter country for local web results, such as `GB`; blank = worked out from `TZ` |
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
