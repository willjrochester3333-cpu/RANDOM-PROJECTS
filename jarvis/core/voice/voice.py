#!/usr/bin/env python3
"""VOICE: the server's ears and mouth. Runs on the CORE Pi itself, outside Docker, with a
USB microphone and a USB speaker.

  * listens for the wake word "Hey Jarvis" (openWakeWord, on the CPU)
  * or starts listening when the dashboard's Talk button is pressed (MQTT jarvis/voice/listen)
  * records until you stop talking, sends the audio to CORE for speech-to-text, asks the
    question through CORE's chat, and speaks every announcement CORE makes
"""
import io
import json
import logging
import os
import queue
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import wave

import numpy as np
import paho.mqtt.client as mqtt

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("voice")

CORE_URL = os.environ.get("CORE_URL", "http://127.0.0.1").rstrip("/")
MQTT_HOST = os.environ.get("MQTT_HOST", "127.0.0.1")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
MQTT_USER = os.environ.get("MQTT_USER", "jarvis")
MQTT_PASSWORD = os.environ.get("MQTT_PASSWORD", "")
MIC = os.environ.get("MIC_DEVICE", "default")
SPEAKER = os.environ.get("SPEAKER_DEVICE", "default")


def find_device(tool: str, kind: str) -> str | None:
    """With no device set, use the USB sound card (ALSA's 'default' is usually HDMI, which has no mic)."""
    try:
        out = subprocess.run([tool, "-l"], capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.TimeoutExpired):
        return None
    cards = re.findall(r"^card \d+: (\S+) \[(.*?)\], device (\d+): (.*)$", out, re.M)
    for card_id, name, dev, rest in cards:
        if "usb" in (card_id + name + rest).lower():
            log.info("using USB %s: %s", kind, name)
            return f"plughw:CARD={card_id},DEV={dev}"
    return None


if MIC == "default":
    MIC = find_device("arecord", "microphone") or MIC
if SPEAKER == "default":
    SPEAKER = find_device("aplay", "speaker") or SPEAKER
WAKE_WORD = os.environ.get("WAKE_WORD", "1") == "1"
WAKE_THRESHOLD = float(os.environ.get("WAKE_THRESHOLD", "0.5"))
VOLUME = os.environ.get("VOLUME", "")          # e.g. "80%": set the mixer once at start

RATE = 16000
CHUNK = 1280                                     # 80 ms, the wake-word model's frame size
SILENCE_END_S = 0.8                              # stop recording after this much quiet
NO_SPEECH_S = 6.0                                # give up if nothing is said
MIN_SPEECH_LEVEL = float(os.environ.get("MIN_SPEECH_LEVEL", "120"))   # lower if your mic is quiet
MAX_UTTERANCE_S = 12.0

T_SAY = "jarvis/console/say"
T_LISTEN = "jarvis/voice/listen"
T_STATUS = "jarvis/voice/status"
T_STOP = "jarvis/voice/stop"

# Speaking is a two-stage pipeline, so sentences follow each other without gaps: the voicer
# turns the next sentence into sound while the player is still playing the current one.
say_queue: "queue.Queue[tuple[int, str]]" = queue.Queue()             # text waiting for a voice
play_queue: "queue.Queue[tuple[int, str, bytes]]" = queue.Queue()     # sound waiting to be played
generation = 0                 # bumped by Stop: anything queued before it is thrown away
player: subprocess.Popen | None = None
player_lock = threading.Lock()
listen_requested = threading.Event()
speaking = threading.Event()


# ---------------------------------------------------------------- CORE API

def core(method: str, path: str, data: bytes | None = None, ctype: str = "application/json", timeout=120):
    req = urllib.request.Request(CORE_URL + path, data=data, method=method, headers={"Content-Type": ctype})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def report(state: str, text: str = "") -> None:
    try:
        core("POST", "/api/voice/state", json.dumps({"state": state, "text": text[:2000]}).encode(), timeout=5)
    except (urllib.error.URLError, OSError):
        pass


# ---------------------------------------------------------------- speaker

def play_wav(data: bytes) -> None:
    global player
    speaking.set()
    try:
        with player_lock:
            player = subprocess.Popen(["aplay", "-q", "-D", SPEAKER, "-"],
                                      stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
        try:
            player.communicate(data, timeout=120)
        except subprocess.TimeoutExpired:
            player.kill()
    finally:
        if play_queue.empty():
            time.sleep(0.25)                     # let the room go quiet before listening again
        speaking.clear()


def say(text: str) -> None:
    """Queue something to be said."""
    if text.strip():
        say_queue.put((generation, text.strip()))


def stop_talking() -> None:
    """Stop: forget everything queued and cut off the sentence being played."""
    global generation
    generation += 1
    for q in (say_queue, play_queue):
        while not q.empty():
            try:
                q.get_nowait()
            except queue.Empty:
                break
    with player_lock:
        if player and player.poll() is None:
            player.kill()


def beep(freq: float = 988, ms: int = 100) -> None:
    t = np.arange(int(RATE * ms / 1000)) / RATE
    tone = (np.sin(2 * np.pi * freq * t) * np.minimum(1, 8 * np.minimum(t, t[-1] - t)) * 9000).astype(np.int16)
    play_wav(to_wav(tone.tobytes()))


def voice_of(text: str) -> bytes:
    try:
        return core("GET", "/api/tts?" + urllib.parse.urlencode({"text": text}), timeout=60)
    except (urllib.error.URLError, OSError) as e:
        log.warning("speech service failed (%s); using espeak", e)
        # espeak-ng makes the WAV; we play it on the right speaker ourselves.
        return subprocess.run(["espeak-ng", "-v", "en-gb", "-s", "165", "--stdout", "--", text],
                              capture_output=True, check=False).stdout


def voicer_thread() -> None:
    while True:
        gen, text = say_queue.get()
        if gen != generation:
            continue
        wav = voice_of(text)
        if wav and gen == generation:
            play_queue.put((gen, text, wav))


def player_thread() -> None:
    while True:
        gen, text, wav = play_queue.get()
        if gen != generation:
            continue
        report("speaking", text)
        play_wav(wav)
        if play_queue.empty() and say_queue.empty():
            report("idle")


# ---------------------------------------------------------------- microphone

def to_wav(pcm: bytes) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(pcm)
    return buf.getvalue()


def open_mic() -> subprocess.Popen:
    return subprocess.Popen(
        ["arecord", "-q", "-D", MIC, "-f", "S16_LE", "-r", str(RATE), "-c", "1", "-t", "raw", "-"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)   # buffered: read(n) waits for n bytes


def rms(chunk: np.ndarray) -> float:
    return float(np.sqrt(np.mean(chunk.astype(np.float32) ** 2))) if len(chunk) else 0.0


def record_utterance(read_chunk, noise_floor: float) -> bytes | None:
    """Read from the mic until the speaker goes quiet. Returns raw PCM, or None if silent."""
    threshold = max(MIN_SPEECH_LEVEL, noise_floor * 2.5)
    frames: list[bytes] = []
    started = None
    quiet_since = None
    peak = 0.0
    t0 = time.monotonic()
    while True:
        raw = read_chunk()
        if raw is None:
            return None
        chunk = np.frombuffer(raw, np.int16)
        level = rms(chunk)
        peak = max(peak, level)
        loud = level > threshold
        now = time.monotonic()
        if started is None:
            frames.append(raw)
            frames = frames[-6:]                 # keep half a second from before the first word
            if loud:
                started = now
            elif now - t0 > NO_SPEECH_S:
                log.info("nothing said: loudest %.0f, needed %.0f (noise floor %.0f). "
                         "If you did speak, the mic is too quiet: try MIN_SPEECH_LEVEL=%d or a USB mic with more gain",
                         peak, threshold, noise_floor, max(40, int(peak * 0.6)))
                return None
            continue
        frames.append(raw)
        if loud:
            quiet_since = None
        elif quiet_since is None:
            quiet_since = now
        elif now - quiet_since > SILENCE_END_S:
            break
        if now - started > MAX_UTTERANCE_S:
            break
    return b"".join(frames)


def handle_question(read_chunk, noise_floor: float) -> None:
    if speaking.is_set() or not say_queue.empty() or not play_queue.empty():
        stop_talking()                           # Talk pressed mid-answer: listen instead
    while speaking.is_set():                     # never record our own voice
        time.sleep(0.05)
    t0 = time.monotonic()
    beep()
    report("listening")
    # The mic kept recording during the beep: drop that audio (the end of "Jarvis" and the beep).
    for _ in range(int((time.monotonic() - t0) / (CHUNK / RATE)) + 1):
        read_chunk()
    pcm = record_utterance(read_chunk, noise_floor)
    if pcm is None:
        report("idle")
        return
    report("thinking")
    try:
        heard = json.loads(core("POST", "/api/transcribe", to_wav(pcm), "audio/wav", timeout=60)).get("text", "").strip()
    except (urllib.error.URLError, OSError) as e:
        log.warning("transcribe failed: %s", e)
        say("Sorry, my hearing is not working right now.")
        return
    log.info("heard: %r", heard)
    if len(heard) < 2:
        say("Sorry, I didn't catch that.")
        return
    try:
        core("POST", "/api/chat", json.dumps({"text": heard, "speak": True, "source": "voice"}).encode(), timeout=240)
        # CORE announces the answer on jarvis/console/say, which the speaker thread plays.
    except (urllib.error.URLError, OSError) as e:
        log.warning("chat failed: %s", e)
        say("Sorry, I could not think of an answer.")


def load_wake_model():
    if not WAKE_WORD:
        return None
    try:
        import openwakeword
        from openwakeword.model import Model
        paths = [p for p in openwakeword.get_pretrained_model_paths() if "hey_jarvis" in p]
        model = Model(wakeword_model_paths=paths)
        log.info("wake word ready: say 'Hey Jarvis'")
        return model
    except Exception as e:                       # missing library, bad install: fall back to the Talk button
        log.warning("wake word unavailable (%s); use the dashboard's Talk button", e)
        return None


def forget(model) -> None:
    """Clear the detector's memory of what it just heard, so it cannot fire on it twice."""
    if model:
        for _ in range(int(2 * RATE / CHUNK)):
            model.predict(np.zeros(CHUNK, np.int16))
        model.reset()


def mic_loop() -> None:
    model = load_wake_model()
    while True:
        proc = open_mic()
        log.info("microphone open (%s)", MIC)
        noise_floor = 300.0

        def read_chunk():
            raw = proc.stdout.read(CHUNK * 2)
            return raw if len(raw) == CHUNK * 2 else None

        while True:
            raw = read_chunk()
            if raw is None:
                break
            if listen_requested.is_set():
                listen_requested.clear()
                handle_question(read_chunk, noise_floor)
                forget(model)
                continue
            if speaking.is_set():
                if model:
                    model.reset()
                continue                         # ignore our own voice
            chunk = np.frombuffer(raw, np.int16)
            level = rms(chunk)
            if level < noise_floor * 2:          # track the quiet between words, not the words
                noise_floor = max(50.0, 0.95 * noise_floor + 0.05 * level)
            if model:
                score = max(model.predict(chunk).values())
                if score >= WAKE_THRESHOLD:
                    log.info("wake word heard (%.2f)", score)
                    handle_question(read_chunk, noise_floor)
                    forget(model)
        proc.kill()
        log.warning("microphone stopped; is a USB microphone plugged in? (arecord -l lists them) retrying in 10 s")
        time.sleep(10)


# ---------------------------------------------------------------- MQTT

def make_mqtt() -> mqtt.Client:
    if hasattr(mqtt, "CallbackAPIVersion"):
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="jarvis-voice")
    else:
        client = mqtt.Client(client_id="jarvis-voice")
    client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
    client.will_set(T_STATUS, "offline", qos=1, retain=True)

    def on_connect(c, *_):
        c.publish(T_STATUS, "online", qos=1, retain=True)
        c.subscribe([(T_SAY, 1), (T_LISTEN, 1), (T_STOP, 1)])

    def on_message(_c, _u, msg):
        if msg.retain:
            return
        if msg.topic == T_SAY:
            say(msg.payload.decode("utf-8", "replace"))
        elif msg.topic == T_LISTEN:
            listen_requested.set()
        elif msg.topic == T_STOP:
            stop_talking()
            report("idle")

    client.on_connect = on_connect
    client.on_message = on_message
    client.reconnect_delay_set(min_delay=2, max_delay=60)
    return client


def set_mixer() -> None:
    """Turn the USB microphone's gain and the speaker's volume up; they often start low."""
    m = re.search(r"CARD=([^,]+)", MIC)
    if m:
        for ctl in ("Mic", "Capture"):
            subprocess.run(["amixer", "-q", "-c", m.group(1), "sset", ctl, "100%"], check=False,
                           stderr=subprocess.DEVNULL)
    m = re.search(r"CARD=([^,]+)", SPEAKER)
    if m:
        for ctl in ("PCM", "Speaker", "Master"):
            subprocess.run(["amixer", "-q", "-c", m.group(1), "sset", ctl, VOLUME or "90%"], check=False,
                           stderr=subprocess.DEVNULL)


def main() -> None:
    set_mixer()
    client = make_mqtt()
    client.connect_async(MQTT_HOST, MQTT_PORT, keepalive=60)
    client.loop_start()
    threading.Thread(target=voicer_thread, daemon=True).start()
    threading.Thread(target=player_thread, daemon=True).start()
    try:
        mic_loop()
    except KeyboardInterrupt:
        pass
    finally:
        client.publish(T_STATUS, "offline", qos=1, retain=True)
        client.loop_stop()


if __name__ == "__main__":
    main()
