#!/usr/bin/env python3
"""OUTPOST: reads the Sense HAT and publishes outdoor weather once a minute."""
import json
import os
import signal
import sys
import time

import paho.mqtt.client as mqtt
from sense_hat import SenseHat

HOST = os.environ.get("MQTT_HOST", "jarvis-core.local")
PORT = int(os.environ.get("MQTT_PORT", "1883"))
USER = os.environ.get("MQTT_USER", "jarvis")
PASSWORD = os.environ.get("MQTT_PASSWORD", "")
INTERVAL = float(os.environ.get("INTERVAL", "60"))
# Subtract this from the temperature if your station reads warm against a trusted thermometer.
TEMP_OFFSET = float(os.environ.get("TEMP_OFFSET", "0"))

T_WEATHER = "jarvis/outpost/weather"
T_STATUS = "jarvis/outpost/status"


def make_client() -> mqtt.Client:
    # paho-mqtt 2.x needs a callback API version; 1.x does not have the argument.
    if hasattr(mqtt, "CallbackAPIVersion"):
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="jarvis-outpost")
    else:
        client = mqtt.Client(client_id="jarvis-outpost")
    client.username_pw_set(USER, PASSWORD)
    client.will_set(T_STATUS, "offline", qos=1, retain=True)
    client.on_connect = lambda c, *_: c.publish(T_STATUS, "online", qos=1, retain=True)
    client.reconnect_delay_set(min_delay=2, max_delay=60)
    return client


def read(sense: SenseHat) -> dict:
    # Two independent temperature sensors on the board: average them.
    temp = (sense.get_temperature_from_humidity() + sense.get_temperature_from_pressure()) / 2
    return {
        "temp_c": round(temp - TEMP_OFFSET, 2),
        "humidity": round(min(100.0, max(0.0, sense.get_humidity())), 1),
        "pressure_hpa": round(sense.get_pressure(), 1),
    }


def main() -> None:
    sense = SenseHat()
    sense.clear()                # LED matrix off: it warms the temperature sensor
    sense.get_pressure()         # the first pressure read after power-up returns 0
    time.sleep(1)

    client = make_client()
    client.connect_async(HOST, PORT, keepalive=120)
    client.loop_start()          # background thread, reconnects by itself

    def stop(*_):
        try:
            client.publish(T_STATUS, "offline", qos=1, retain=True).wait_for_publish(2)
        except (RuntimeError, ValueError):
            pass                 # broker already gone: its last-will covers us
        client.loop_stop()
        sys.exit(0)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    while True:
        reading = read(sense)
        if reading["pressure_hpa"] > 0:
            client.publish(T_WEATHER, json.dumps(reading), qos=0)
            print(reading, flush=True)
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
