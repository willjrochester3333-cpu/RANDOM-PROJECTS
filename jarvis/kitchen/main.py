# DINNER BELL - MicroPython for the Seeed XIAO ESP32-S3 Sense.
# Button on D1 (GPIO 2) to GND, button LED on D2 (GPIO 3).
import time

import machine
import network
from umqtt.simple import MQTTClient

import config

BTN = machine.Pin(2, machine.Pin.IN, machine.Pin.PULL_UP)
LED = machine.Pin(3, machine.Pin.OUT, value=0)

T_DINNER = b"jarvis/kitchen/dinner"
T_LED = b"jarvis/kitchen/led"
T_STATUS = b"jarvis/kitchen/status"

led_mode = "off"      # off | blink | solid


def wifi_connect():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        wlan.connect(config.WIFI_SSID, config.WIFI_PASSWORD)
        start = time.ticks_ms()
        while not wlan.isconnected():
            if time.ticks_diff(time.ticks_ms(), start) > 20000:
                raise OSError("wifi timeout")
            LED.value(not LED.value())      # fast flicker while joining
            time.sleep_ms(100)
    LED.value(0)
    return wlan


def on_message(topic, msg):
    global led_mode
    if topic == T_LED and msg in (b"off", b"blink", b"solid"):
        led_mode = msg.decode()


def mqtt_connect():
    client = MQTTClient("jarvis-kitchen", config.MQTT_HOST, port=config.MQTT_PORT,
                        user=config.MQTT_USER, password=config.MQTT_PASSWORD, keepalive=60)
    client.set_last_will(T_STATUS, b"offline", retain=True, qos=1)
    client.set_callback(on_message)
    client.connect()
    client.subscribe(T_LED, qos=1)
    client.publish(T_STATUS, b"online", retain=True, qos=1)
    return client


def run():
    global led_mode
    wlan = wifi_connect()
    client = mqtt_connect()

    was_down = False
    down_since = 0
    fired = False
    last_press = time.ticks_add(time.ticks_ms(), -5000)
    last_ping = time.ticks_ms()

    while True:
        now = time.ticks_ms()
        if not wlan.isconnected():
            raise OSError("wifi lost")
        client.check_msg()

        # Button: must be held 40 ms, then one press per 1.5 s.
        down = BTN.value() == 0
        if down and not was_down:
            down_since = now
            fired = False
        if (down and not fired and time.ticks_diff(now, down_since) > 40
                and time.ticks_diff(now, last_press) > 1500):
            fired = True
            last_press = now
            client.publish(T_DINNER, b"pressed", qos=1)
            led_mode = "blink"              # instant feedback; CORE confirms the state
        was_down = down

        if led_mode == "blink":
            LED.value((now // 350) % 2)
        else:
            LED.value(1 if led_mode == "solid" else 0)

        if time.ticks_diff(now, last_ping) > 20000:
            client.ping()
            last_ping = now
        time.sleep_ms(10)


try:
    run()
except Exception as e:                      # any failure: wait, then start clean
    print("error:", e)
    LED.value(0)
    time.sleep(5)
    machine.reset()
