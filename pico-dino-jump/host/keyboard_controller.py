"""
keyboard_controller.py

Reads Up/Down arrow key presses on THIS computer and forwards them to the
Raspberry Pi Pico 2 W over USB serial, to control the Dino Jump game
running on the Pico's OLED screen (see ../pico/main.py).

The Pico can't read a PC keyboard directly, so this script does the
listening and just sends single bytes down the same USB cable used to
program the board:
    'U' -> Up arrow pressed   (jump / start / restart)
    'D' -> Down arrow pressed (start ducking)
    'd' -> Down arrow released (stop ducking)

Usage:
    pip install -r requirements.txt
    python keyboard_controller.py            # auto-detects the Pico's port
    python keyboard_controller.py COM5       # or specify it explicitly
    python keyboard_controller.py /dev/ttyACM0
"""
import sys
import time

import serial
import serial.tools.list_ports
from pynput import keyboard

BAUD_RATE = 115200


def find_pico_port():
    ports = list(serial.tools.list_ports.comports())
    for port in ports:
        desc = (port.description or "").lower()
        manufacturer = (port.manufacturer or "").lower()
        if "pico" in desc or "micropython" in desc or "raspberry pi" in manufacturer:
            return port.device
    if len(ports) == 1:
        return ports[0].device
    return None


def main():
    port_name = sys.argv[1] if len(sys.argv) > 1 else find_pico_port()
    if not port_name:
        print("Could not auto-detect the Pico's serial port.")
        print("Available ports:")
        for p in serial.tools.list_ports.comports():
            print("  {}  ({})".format(p.device, p.description))
        print("\nRun again with the port as an argument, e.g.:")
        print("  python keyboard_controller.py COM5")
        sys.exit(1)

    print("Connecting to {} at {} baud...".format(port_name, BAUD_RATE))
    try:
        ser = serial.Serial(port_name, BAUD_RATE, timeout=0)
    except serial.SerialException as exc:
        print("Could not open {}: {}".format(port_name, exc))
        print(
            "Make sure no other program (VS Code's serial monitor, Thonny, "
            "screen, etc.) is currently connected to the Pico."
        )
        sys.exit(1)

    time.sleep(0.5)  # let the OS finish settling the port
    print("Connected. Use the Up/Down arrow keys to play. Press Esc to quit.")

    def on_press(key):
        if key == keyboard.Key.up:
            ser.write(b"U")
        elif key == keyboard.Key.down:
            ser.write(b"D")
        elif key == keyboard.Key.esc:
            return False

    def on_release(key):
        if key == keyboard.Key.down:
            ser.write(b"d")

    with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
        listener.join()

    ser.close()
    print("Disconnected.")


if __name__ == "__main__":
    main()
