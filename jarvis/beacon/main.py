# BEACON - MicroPython for the Raspberry Pi Pico 2 W.
# 12-LED ring data on GP2, piezo buzzer on GP15, button on GP14 to GND.
import time

import machine
import neopixel
import network
from umqtt.simple import MQTTClient

import config

N_LEDS = 12
MAX_BRIGHT = 0.4                 # keeps 12 LEDs comfortably within USB power
AMBER = (255, 120, 0)
GREEN = (0, 255, 60)
BLUE = (0, 60, 255)

ring = neopixel.NeoPixel(machine.Pin(2), N_LEDS)
buzzer = machine.PWM(machine.Pin(15))
buzzer.duty_u16(0)
BTN = machine.Pin(14, machine.Pin.IN, machine.Pin.PULL_UP)

T_ALERT = b"jarvis/beacon/alert"
T_ACK = b"jarvis/beacon/ack"
T_STATUS = b"jarvis/beacon/status"

alerting = False
chime_due = False


def fill(colour, level):
    k = level * MAX_BRIGHT
    c = (int(colour[0] * k), int(colour[1] * k), int(colour[2] * k))
    for i in range(N_LEDS):
        ring[i] = c
    ring.write()


def chime():
    for freq, ms in ((880, 140), (1175, 140), (1568, 320)):
        buzzer.freq(freq)
        buzzer.duty_u16(20000)
        time.sleep_ms(ms)
        buzzer.duty_u16(0)
        time.sleep_ms(30)


def wifi_connect():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        wlan.connect(config.WIFI_SSID, config.WIFI_PASSWORD)
        start = time.ticks_ms()
        step = 0
        while not wlan.isconnected():
            if time.ticks_diff(time.ticks_ms(), start) > 20000:
                raise OSError("wifi timeout")
            for i in range(N_LEDS):          # one blue dot circles while joining
                ring[i] = (0, 6, 25) if i == step % N_LEDS else (0, 0, 0)
            ring.write()
            step += 1
            time.sleep_ms(80)
    fill(BLUE, 0)
    return wlan


def on_message(topic, msg):
    global alerting, chime_due
    if topic != T_ALERT:
        return
    if msg == b"dinner":
        if not alerting:
            chime_due = True
        alerting = True
    elif msg == b"clear":
        alerting = False


def mqtt_connect():
    client = MQTTClient("jarvis-beacon", config.MQTT_HOST, port=config.MQTT_PORT,
                        user=config.MQTT_USER, password=config.MQTT_PASSWORD, keepalive=60)
    client.set_last_will(T_STATUS, b"offline", retain=True, qos=1)
    client.set_callback(on_message)
    client.connect()
    client.subscribe(T_ALERT, qos=1)
    client.publish(T_STATUS, b"online", retain=True, qos=1)
    return client


def run():
    global alerting, chime_due
    wlan = wifi_connect()
    client = mqtt_connect()

    was_down = False
    last_press = time.ticks_add(time.ticks_ms(), -5000)
    last_ping = time.ticks_ms()
    lit = False

    while True:
        now = time.ticks_ms()
        if not wlan.isconnected():
            raise OSError("wifi lost")
        client.check_msg()

        down = BTN.value() == 0
        if down and not was_down and time.ticks_diff(now, last_press) > 800:
            last_press = now
            if alerting:
                client.publish(T_ACK, b"pressed", qos=1)
                alerting = False             # CORE will confirm with "clear"
                fill(GREEN, 1.0)
                time.sleep_ms(400)
                fill(GREEN, 0)
                lit = False
        was_down = down

        if chime_due:
            chime_due = False
            fill(AMBER, 1.0)
            chime()

        if alerting:                         # slow amber breathing, 2 s per breath
            phase = (now % 2000) / 1000.0
            level = phase if phase < 1 else 2 - phase
            fill(AMBER, 0.08 + 0.92 * level)
            lit = True
        elif lit:
            fill(AMBER, 0)
            lit = False

        if time.ticks_diff(now, last_ping) > 20000:
            client.ping()
            last_ping = now
        time.sleep_ms(25)


try:
    run()
except Exception as e:                       # any failure: wait, then start clean
    print("error:", e)
    buzzer.duty_u16(0)
    fill(AMBER, 0)
    time.sleep(5)
    machine.reset()
