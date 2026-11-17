# KITCHEN CAMERA - MicroPython for the Seeed XIAO ESP32S3 Sense.
#
# Live camera and microphone for the J.A.R.V.I.S. dashboard, plus the dinner button.
#
# Firmware: MicroPython with camera support for this board, "mpy_cam-v1.27.0-XIAO_ESP32S3.zip"
# from https://github.com/cnadler86/micropython-camera-API/releases (see SETUP.md).
# Files on the board: this main.py, and config.py with your Wi-Fi and the server's details.
#
# How it works: the board serves /stream.mjpg (pictures) and /audio.wav (sound) on your home
# network, protected by a private key it makes on first start. It tells CORE where to find
# them over MQTT. CORE connects only while someone is watching or listening, and passes them
# on to every dashboard, so the board never has more than one viewer.
#
# Pins: camera and microphone are built in. Optional dinner button on D1 (to GND) and its
# light on D2. D3 is used internally by the microphone: leave it unconnected.

import array
import asyncio
import gc
import os
import struct
import time

import machine
import micropython
import network
from machine import I2S, Pin
from umqtt.simple import MQTTClient

import config

try:
    from acamera import Camera, FrameSize, PixelFormat
except ImportError:
    try:
        from camera import Camera, FrameSize, PixelFormat     # older firmware: no async capture
    except ImportError:
        Camera = None                                         # plain MicroPython: no camera


def setting(name, default):
    return getattr(config, name, default)


NAME = "kitchen"
DISPLAY_NAME = setting("CAMERA_NAME", "Kitchen camera")
FPS = setting("CAMERA_FPS", 8)              # pictures per second; lower runs cooler
SIZE = setting("CAMERA_SIZE", "VGA")        # QVGA 320x240, VGA 640x480, SVGA 800x600
QUALITY = setting("CAMERA_QUALITY", 80)     # 0-100: higher is sharper but bigger
FLIP = setting("CAMERA_FLIP", False)        # True if the picture is upside down
MIC_GAIN = setting("MIC_GAIN", 16)          # louder or quieter sound (1 to 64)
PORT = 80

T_STATUS = b"jarvis/kitchen/status"
T_STREAM = b"jarvis/kitchen/stream"
T_DINNER = b"jarvis/kitchen/dinner"
T_LED = b"jarvis/kitchen/led"

BUTTON = Pin(2, Pin.IN, Pin.PULL_UP)          # D1
LED = Pin(3, Pin.OUT, value=0)                # D2
MIC_CLOCK, MIC_DATA, MIC_SPARE = 42, 41, 4    # built-in microphone; D3 (GPIO 4) is spare

led_mode = "off"                              # off | blink | solid, set by CORE


# ------------------------------------------------------------------ private key

def private_key():
    """A random key made on first start and kept in key.txt, so only CORE can watch."""
    try:
        with open("key.txt") as f:
            key = f.read().strip()
        if len(key) >= 16:
            return key
    except OSError:
        pass
    key = "".join("%02x" % b for b in os.urandom(16))
    with open("key.txt", "w") as f:
        f.write(key)
    return key


KEY = private_key()


# ------------------------------------------------------------------ microphone

# The built-in microphone sends a fast stream of single bits (PDM). Stock MicroPython cannot
# decode that, so the I2S unit just collects the raw bits (2,048,000 a second) and
# pdm_to_pcm turns every 128 of them into one 16-bit sound sample, 16,000 a second, with a
# 4-stage CIC filter. To be quick enough, the filter takes a whole byte (8 bits) per step using
# the lookup tables below, which give exactly the same answer as going bit by bit.

MIC_BYTES_PER_SAMPLE = 16


def _cic_tables():
    t = array.array("H", bytes(2 * 1024))
    for v in range(256):
        for j in range(1, 9):                # bit 1 (the top bit) is the earliest
            if (v >> (8 - j)) & 1:
                t[v] += 1
                t[256 + v] += 9 - j
                t[512 + v] += (9 - j) * (10 - j) // 2
                t[768 + v] += (9 - j) * (10 - j) * (11 - j) // 6
    return t


CIC_TABLES = _cic_tables()


@micropython.viper
def pdm_to_pcm(src: ptr8, n: int, dst: ptr16, st: ptr32) -> int:
    t = ptr16(CIC_TABLES)
    i1 = st[0]
    i2 = st[1]
    i3 = st[2]
    i4 = st[3]
    z1 = st[4]
    z2 = st[5]
    z3 = st[6]
    z4 = st[7]
    phase = st[8]
    last = st[9]
    hp = st[10] - 0x10000000         # stored with an offset so it is never negative in memory
    gain = st[11]
    settle = st[12]
    m = 0x3FFFFFFF                   # 30-bit arithmetic: wraps the same way on every chip
    out = 0
    w = 0
    while w < n:
        # Each 32-bit word arrives least significant byte first; its bits were heard most
        # significant byte first, so walk each word backwards.
        k = 3
        while k >= 0:
            b = src[w + k]
            i4 = (i4 + (i3 << 3) + i2 * 36 + i1 * 120 + t[768 + b]) & m
            i3 = (i3 + (i2 << 3) + i1 * 36 + t[512 + b]) & m
            i2 = (i2 + (i1 << 3) + t[256 + b]) & m
            i1 = (i1 + t[b]) & m
            k -= 1
        w += 4
        phase += 1
        if phase == 4:               # 16 bytes = 128 bits = one sample
            phase = 0
            d1 = (i4 - z1) & m
            z1 = i4
            d2 = (d1 - z2) & m
            z2 = d1
            d3 = (d2 - z3) & m
            z3 = d2
            y = (d3 - z4) & m        # 0..2^28, about 2^27 when the room is silent
            z4 = d3
            hp = y - last + hp - (hp >> 6)      # remove the resting level, keep the sound
            last = y
            if settle > 0:           # the filter needs a few samples to fill up
                settle -= 1
                hp = 0
                v = 0
            else:
                v = ((hp >> 4) * gain) >> 8
                if v > 32767:
                    v = 32767
                if v < -32767:
                    v = -32767
            dst[out] = v
            out += 1
    st[0] = i1
    st[1] = i2
    st[2] = i3
    st[3] = i4
    st[4] = z1
    st[5] = z2
    st[6] = z3
    st[7] = z4
    st[8] = phase
    st[9] = last
    st[10] = hp + 0x10000000
    st[12] = settle
    return out


def mic_state(gain):
    """Fresh filter memory: empty, resting level in the middle, settling, chosen gain."""
    st = bytearray(13 * 4)
    struct.pack_into("<13i", st, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1 << 27, 0x10000000, gain, 8)
    return st


def wav_header(rate=16000, channels=1, bits=16):
    data_size = 0x7FFF0000                      # a stream with no end
    block = channels * bits // 8
    return struct.pack("<4sI4s4sIHHIIHH4sI", b"RIFF", data_size + 36, b"WAVE", b"fmt ", 16, 1,
                       channels, rate, rate * block, block, bits, b"data", data_size)


# ------------------------------------------------------------------ HTTP helpers

async def send_head(writer, status, ctype, extra=b""):
    writer.write(b"HTTP/1.1 " + status + b"\r\nContent-Type: " + ctype
                 + b"\r\nCache-Control: no-cache\r\nConnection: close\r\n" + extra + b"\r\n")
    await writer.drain()


async def send_body(writer, status, ctype, body):
    await send_head(writer, status, ctype, b"Content-Length: " + str(len(body)).encode() + b"\r\n")
    writer.write(body)
    await writer.drain()


# ------------------------------------------------------------------ camera

class Eye:
    """The camera. It is switched on only while someone watches, which keeps the board cool.
    The newest viewer always wins: a stale connection is dropped when a new one arrives."""

    def __init__(self):
        self.cam = None
        self.users = 0
        self.session = 0
        self.snapshot_wanted = None
        if Camera:
            size = getattr(FrameSize, SIZE, FrameSize.VGA)
            self.cam = Camera(frame_size=size, pixel_format=PixelFormat.JPEG,
                              jpeg_quality=QUALITY, init=False)

    def on(self):
        self.users += 1
        if self.users == 1:
            self.cam.init()
            if FLIP:
                for prop in ("vflip", "hmirror"):
                    try:
                        setattr(self.cam, prop, True)
                    except (AttributeError, ValueError):
                        pass

    def off(self):
        self.users -= 1
        if self.users == 0:
            self.cam.deinit()
            gc.collect()

    async def capture(self):
        if hasattr(self.cam, "acapture"):
            return await self.cam.acapture()
        await asyncio.sleep_ms(0)
        return self.cam.capture()

    async def stream(self, writer):
        self.session += 1
        mine = self.session
        self.on()
        try:
            await send_head(writer, b"200 OK", b"multipart/x-mixed-replace; boundary=FRAME")
            period = 1000 // max(1, FPS)
            while self.session == mine:
                started = time.ticks_ms()
                frame = await self.capture()
                if frame:
                    if self.snapshot_wanted is not None:
                        self.snapshot_wanted = bytes(frame)
                    writer.write(b"--FRAME\r\nContent-Type: image/jpeg\r\nContent-Length: "
                                 + str(len(frame)).encode() + b"\r\n\r\n")
                    writer.write(frame)
                    writer.write(b"\r\n")
                    await writer.drain()
                wait = period - time.ticks_diff(time.ticks_ms(), started)
                if wait > 0:
                    await asyncio.sleep_ms(wait)
        finally:
            self.off()

    async def snapshot(self):
        if self.users:                           # streaming: take the next picture from it
            self.snapshot_wanted = b""
            for _ in range(50):
                await asyncio.sleep_ms(50)
                if self.snapshot_wanted:
                    break
            picture, self.snapshot_wanted = self.snapshot_wanted, None
            return picture
        self.on()
        try:
            picture = None
            for _ in range(3):                   # the first pictures are often too dark
                frame = await self.capture()
                if frame:
                    picture = bytes(frame)
            return picture
        finally:
            self.off()


# ------------------------------------------------------------------ microphone stream

class Ear:
    """The microphone, switched on only while someone listens. Newest listener wins."""

    def __init__(self):
        self.session = 0
        self.raw = bytearray(4096)
        self.pcm = bytearray(len(self.raw) // MIC_BYTES_PER_SAMPLE * 2)

    async def stream(self, writer):
        self.session += 1
        mine = self.session
        mic = I2S(0, sck=Pin(MIC_CLOCK), ws=Pin(MIC_SPARE), sd=Pin(MIC_DATA), mode=I2S.RX,
                  bits=32, format=I2S.STEREO, rate=32000, ibuf=64000)
        try:
            state = mic_state(MIC_GAIN)
            await send_head(writer, b"200 OK", b"audio/wav")
            writer.write(wav_header())
            reader = asyncio.StreamReader(mic)
            raw, pcm = memoryview(self.raw), memoryview(self.pcm)
            while self.session == mine:
                n = await reader.readinto(raw)
                if n:
                    count = pdm_to_pcm(raw, n - n % 4, pcm, state)
                    writer.write(pcm[:count * 2])
                    await writer.drain()
        finally:
            mic.deinit()


eye = Eye()
ear = Ear()


# ------------------------------------------------------------------ web server

async def handle(reader, writer):
    try:
        request = await reader.readline()
        while True:                                # skip the headers
            line = await reader.readline()
            if not line or line == b"\r\n":
                break
        parts = request.decode().split(" ")
        path = parts[1] if len(parts) > 1 else "/"
        route, _, query = path.partition("?")
        given = ""
        for pair in query.split("&"):
            if pair.startswith("key="):
                given = pair[4:]
        if route == "/":
            page = ("J.A.R.V.I.S. kitchen camera\ncamera: %s\nwatching: %d\nfree memory: %d\n"
                    % ("yes" if eye.cam else "no (camera firmware not installed)",
                       eye.users, gc.mem_free()))
            await send_body(writer, b"200 OK", b"text/plain", page.encode())
        elif given != KEY:
            await send_body(writer, b"403 Forbidden", b"text/plain", b"Wrong or missing key\n")
        elif route == "/stream.mjpg" and eye.cam:
            await eye.stream(writer)
        elif route == "/snapshot.jpg" and eye.cam:
            picture = await eye.snapshot()
            if picture:
                await send_body(writer, b"200 OK", b"image/jpeg", picture)
            else:
                await send_body(writer, b"503 Service Unavailable", b"text/plain", b"No picture\n")
        elif route == "/audio.wav":
            await ear.stream(writer)
        else:
            await send_body(writer, b"404 Not Found", b"text/plain", b"Not found\n")
    except OSError:
        pass                                       # the viewer went away
    except Exception as e:
        print("request error:", repr(e))
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass


# ------------------------------------------------------------------ Wi-Fi and MQTT

def wifi_connect():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    try:
        wlan.config(pm=wlan.PM_NONE)               # no Wi-Fi power saving: smoother video
    except (AttributeError, ValueError):
        pass
    if not wlan.isconnected():
        wlan.connect(config.WIFI_SSID, config.WIFI_PASSWORD)
        start = time.ticks_ms()
        while not wlan.isconnected():
            if time.ticks_diff(time.ticks_ms(), start) > 20000:
                raise OSError("wifi timeout")
            LED.value(not LED.value())             # fast flicker while joining
            time.sleep_ms(100)
    LED.value(0)
    return wlan


def on_message(topic, msg):
    global led_mode
    if topic == T_LED and msg in (b"off", b"blink", b"solid"):
        led_mode = msg.decode()


def mqtt_connect(ip):
    client = MQTTClient("jarvis-kitchen", config.MQTT_HOST, port=config.MQTT_PORT,
                        user=config.MQTT_USER, password=config.MQTT_PASSWORD, keepalive=60)
    client.set_last_will(T_STATUS, b"offline", retain=True, qos=1)
    client.set_callback(on_message)
    client.connect()
    client.subscribe(T_LED, qos=1)
    client.publish(T_STATUS, b"online", retain=True, qos=1)
    if eye.cam:
        base = "http://%s" % ip
        announce = ('{"name": "%s", "video": "%s/stream.mjpg?key=%s", "audio": "%s/audio.wav?key=%s", '
                    '"relay": true}' % (DISPLAY_NAME, base, KEY, base, KEY))
        client.publish(T_STREAM, announce.encode(), retain=True, qos=1)
    return client


async def mqtt_task(client, wlan):
    last_ping = time.ticks_ms()
    while True:
        if not wlan.isconnected():
            raise OSError("wifi lost")
        client.check_msg()
        if time.ticks_diff(time.ticks_ms(), last_ping) > 20000:
            client.ping()
            last_ping = time.ticks_ms()
        await asyncio.sleep_ms(50)


async def button_task(client):
    """The dinner button: must be held 40 ms, then one press per 1.5 s."""
    global led_mode
    was_down = False
    down_since = 0
    fired = False
    last_press = time.ticks_add(time.ticks_ms(), -5000)
    while True:
        now = time.ticks_ms()
        down = BUTTON.value() == 0
        if down and not was_down:
            down_since = now
            fired = False
        if (down and not fired and time.ticks_diff(now, down_since) > 40
                and time.ticks_diff(now, last_press) > 1500):
            fired = True
            last_press = now
            client.publish(T_DINNER, b"pressed", qos=1)
            led_mode = "blink"                     # instant feedback; CORE confirms the state
        was_down = down
        if led_mode == "blink":
            LED.value((now // 350) % 2)
        else:
            LED.value(1 if led_mode == "solid" else 0)
        await asyncio.sleep_ms(10)


async def main():
    wlan = wifi_connect()
    ip = wlan.ifconfig()[0]
    client = mqtt_connect(ip)
    await asyncio.start_server(handle, "0.0.0.0", PORT)
    print("kitchen camera ready at http://%s/" % ip)
    asyncio.create_task(button_task(client))
    await mqtt_task(client, wlan)                  # returns only by failing


try:
    asyncio.run(main())
except Exception as e:                             # any failure: wait, then start clean
    print("error:", repr(e))
    LED.value(0)
    time.sleep(5)
    machine.reset()
