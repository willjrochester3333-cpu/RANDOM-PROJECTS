#!/usr/bin/env python3
"""CONSOLE: speaks whatever CORE publishes on jarvis/console/say, using espeak-ng."""
import os
import queue
import subprocess

import paho.mqtt.client as mqtt

HOST = os.environ.get("MQTT_HOST", "jarvis-core.local")
PORT = int(os.environ.get("MQTT_PORT", "1883"))
USER = os.environ.get("MQTT_USER", "jarvis")
PASSWORD = os.environ.get("MQTT_PASSWORD", "")
VOICE = os.environ.get("VOICE", "en-gb")
SPEED = os.environ.get("SPEED", "165")

T_SAY = "jarvis/console/say"
T_STATUS = "jarvis/console/status"

lines: "queue.Queue[str]" = queue.Queue(maxsize=10)


def on_connect(client, *_):
    client.publish(T_STATUS, "online", qos=1, retain=True)
    client.subscribe(T_SAY, qos=1)


def on_message(_client, _userdata, msg):
    text = msg.payload.decode("utf-8", "replace").strip()
    if text and not msg.retain:
        try:
            lines.put_nowait(text[:500])
        except queue.Full:
            pass   # drop rather than talk for minutes


def main() -> None:
    if hasattr(mqtt, "CallbackAPIVersion"):   # paho-mqtt 2.x
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="jarvis-console")
    else:
        client = mqtt.Client(client_id="jarvis-console")
    client.username_pw_set(USER, PASSWORD)
    client.will_set(T_STATUS, "offline", qos=1, retain=True)
    client.on_connect = on_connect
    client.on_message = on_message
    client.reconnect_delay_set(min_delay=2, max_delay=60)
    client.connect_async(HOST, PORT, keepalive=60)
    client.loop_start()

    while True:
        text = lines.get()
        # Argument list, no shell: the text can never be run as a command.
        subprocess.run(["espeak-ng", "-v", VOICE, "-s", SPEED, "--", text], check=False)


if __name__ == "__main__":
    main()
