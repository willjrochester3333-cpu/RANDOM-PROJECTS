#!/usr/bin/env python3
"""CAMERA: streams a Raspberry Pi camera to the J.A.R.V.I.S. dashboard.

The picture is served as MJPEG (a stream of JPEG images), which a web page can show
in an ordinary <img> tag. The camera only runs while someone is watching. On start
the stream address, with a private key, is announced to CORE over MQTT, so the
dashboard finds it by itself.
"""
import hmac
import io
import os
import signal
import socket
import sys
import threading
import time
from http import server
from urllib.parse import parse_qs, urlparse

import numpy as np
import paho.mqtt.client as mqtt

MQTT_HOST = os.environ.get("MQTT_HOST", "jarvis-core.local")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
MQTT_USER = os.environ.get("MQTT_USER", "jarvis")
MQTT_PASSWORD = os.environ.get("MQTT_PASSWORD", "")
NODE = os.environ.get("CAMERA_NAME", "camera")
HTTP_PORT = int(os.environ.get("CAMERA_PORT", "8081"))
KEY = os.environ.get("CAMERA_KEY", "")
WIDTH, HEIGHT = (int(v) for v in os.environ.get("CAMERA_SIZE", "640x480").split("x"))
FPS = float(os.environ.get("CAMERA_FPS", "12"))
QUALITY = int(os.environ.get("CAMERA_QUALITY", "75"))
ROTATE = os.environ.get("CAMERA_ROTATE", "0") == "1"

T_STATUS = f"jarvis/{NODE}/status"
T_STREAM = f"jarvis/{NODE}/stream"

try:
    import simplejpeg

    def encode(bgr: np.ndarray) -> bytes:
        return simplejpeg.encode_jpeg(bgr, quality=QUALITY, colorspace="BGR")
except ImportError:
    from PIL import Image

    def encode(bgr: np.ndarray) -> bytes:
        buf = io.BytesIO()
        Image.fromarray(bgr[..., ::-1]).save(buf, "JPEG", quality=QUALITY)
        return buf.getvalue()


class Camera:
    """Owns the camera. Starts it when the first viewer arrives, stops it after the last."""

    def __init__(self):
        from picamera2 import Picamera2

        if not Picamera2.global_camera_info():
            sys.exit("No camera found. Check the ribbon cable (contacts the right way round, "
                     "latches pressed down), then test with: rpicam-hello --list-cameras")
        self.cam = Picamera2()
        extra = {}
        if ROTATE:
            from libcamera import Transform
            extra["transform"] = Transform(hflip=1, vflip=1)
        frame_us = int(1_000_000 / FPS)
        self.cam.configure(self.cam.create_video_configuration(
            main={"size": (WIDTH, HEIGHT), "format": "RGB888"},      # RGB888 arrives as B, G, R
            controls={"FrameDurationLimits": (frame_us, frame_us)},
            **extra,
        ))
        self.cond = threading.Condition()
        self.frame: bytes | None = None
        self.seq = 0
        self.viewers = 0
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self) -> None:
        running = False
        while True:
            with self.cond:
                wanted = self.viewers > 0
            if wanted and not running:
                self.cam.start()
                running = True
                print("camera on", flush=True)
            elif running and not wanted:
                self.cam.stop()
                running = False
                print("camera off", flush=True)
            if not running:
                time.sleep(0.2)
                continue
            jpeg = encode(np.ascontiguousarray(self.cam.capture_array("main")))
            with self.cond:
                self.frame = jpeg
                self.seq += 1
                self.cond.notify_all()

    def frames(self):
        """JPEG frames for one viewer, for as long as they keep reading."""
        with self.cond:
            self.viewers += 1
            seen = self.seq
        try:
            while True:
                with self.cond:
                    self.cond.wait_for(lambda: self.seq != seen, timeout=5)
                    seen = self.seq
                    frame = self.frame
                if frame:
                    yield frame
        finally:
            with self.cond:
                self.viewers -= 1


PAGE = """<!doctype html><meta name="viewport" content="width=device-width">
<title>{name}</title><body style="margin:0;background:#000">
<img src="/stream.mjpg?key={key}" style="width:100%;height:100vh;object-fit:contain">"""


class Handler(server.BaseHTTPRequestHandler):
    camera: Camera

    def do_GET(self) -> None:
        url = urlparse(self.path)
        given = parse_qs(url.query).get("key", [""])[0]
        if KEY and not hmac.compare_digest(given.encode(), KEY.encode()):
            self.send_error(403, "Wrong or missing key")
            return
        if url.path == "/stream.mjpg":
            self.stream()
        elif url.path == "/snapshot.jpg":
            self.snapshot()
        elif url.path == "/":
            body = PAGE.format(name=NODE, key=given).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_error(404)

    def stream(self) -> None:
        self.send_response(200)
        self.send_header("Cache-Control", "no-cache, private")
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=FRAME")
        self.end_headers()
        frames = self.camera.frames()
        try:
            for jpeg in frames:
                self.wfile.write(b"--FRAME\r\nContent-Type: image/jpeg\r\n")
                self.wfile.write(f"Content-Length: {len(jpeg)}\r\n\r\n".encode())
                self.wfile.write(jpeg + b"\r\n")
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            pass                                  # viewer closed the page
        finally:
            frames.close()

    def snapshot(self) -> None:
        frames = self.camera.frames()
        try:
            jpeg = next(frames)
        finally:
            frames.close()
        self.send_response(200)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Content-Length", str(len(jpeg)))
        self.end_headers()
        self.wfile.write(jpeg)

    def log_message(self, fmt, *args) -> None:
        pass


def local_ip() -> str:
    """The address other machines on the network use to reach this Pi."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect((MQTT_HOST, MQTT_PORT))       # sends nothing; just picks the route
            return s.getsockname()[0]
    except OSError:
        return socket.gethostname() + ".local"


def stream_url() -> str:
    return f"http://{local_ip()}:{HTTP_PORT}/stream.mjpg?key={KEY}"


def make_mqtt() -> mqtt.Client:
    if hasattr(mqtt, "CallbackAPIVersion"):       # paho-mqtt 2.x
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"jarvis-{NODE}")
    else:
        client = mqtt.Client(client_id=f"jarvis-{NODE}")
    client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
    client.will_set(T_STATUS, "offline", qos=1, retain=True)

    def on_connect(c, *_):
        # Re-announced on every connect, so a changed IP address is picked up.
        c.publish(T_STREAM, stream_url(), qos=1, retain=True)
        c.publish(T_STATUS, "online", qos=1, retain=True)

    client.on_connect = on_connect
    client.reconnect_delay_set(min_delay=2, max_delay=60)
    return client


def main() -> None:
    Handler.camera = Camera()
    httpd = server.ThreadingHTTPServer(("", HTTP_PORT), Handler)
    httpd.daemon_threads = True

    client = make_mqtt()
    client.connect_async(MQTT_HOST, MQTT_PORT, keepalive=60)
    client.loop_start()

    def stop(*_):
        try:
            client.publish(T_STATUS, "offline", qos=1, retain=True).wait_for_publish(2)
        except (RuntimeError, ValueError):
            pass
        client.loop_stop()
        os._exit(0)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    print(f"streaming on port {HTTP_PORT}", flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
