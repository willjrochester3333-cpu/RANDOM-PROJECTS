"""
ble_keyboard_controller.py

Wireless control for Pico Dino Jump: listens for Up/Down arrow key
presses on this computer and sends them to the Raspberry Pi Pico 2 W
over Bluetooth Low Energy (BLE) - no USB data cable needed once the
Pico is powered on its own (a battery pack or a power-only USB cable).

The Pico advertises itself as a small BLE "UART" peripheral (a Nordic
UART Service) from pico/ble_uart_peripheral.py + pico/main.py. This
script scans for it by name, connects, and writes the same single-byte
commands the wired controller uses:
    b'U' -> Up arrow pressed   (jump / start / restart)
    b'D' -> Down arrow pressed (start ducking)
    b'd' -> Down arrow released (stop ducking)

Usage:
    pip install -r requirements.txt
    python ble_keyboard_controller.py
    python ble_keyboard_controller.py --name PicoDino   # match a custom name
"""
import argparse
import asyncio

from bleak import BleakClient, BleakScanner
from pynput import keyboard

UART_RX_CHAR_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"

DEFAULT_NAME = "PicoDino"
SCAN_TIMEOUT_S = 10.0


async def find_pico(name, timeout):
    print("Scanning for a BLE device named '{}' (up to {:.0f}s)...".format(name, timeout))
    return await BleakScanner.find_device_by_filter(
        lambda device, adv: device.name == name, timeout=timeout
    )


async def run(name):
    device = await find_pico(name, SCAN_TIMEOUT_S)
    if device is None:
        print("Could not find a BLE device named '{}'.".format(name))
        print(
            "Make sure the Pico is powered on, main.py is running, and it's "
            "not already connected to something else (only one central can "
            "be connected at a time)."
        )
        return

    print("Found {} ({}), connecting...".format(device.name, device.address))

    async with BleakClient(device) as client:
        print("Connected. Use the Up/Down arrow keys to play. Press Esc to quit.")

        loop = asyncio.get_running_loop()
        queue = asyncio.Queue()

        def on_press(key):
            if key == keyboard.Key.up:
                loop.call_soon_threadsafe(queue.put_nowait, b"U")
            elif key == keyboard.Key.down:
                loop.call_soon_threadsafe(queue.put_nowait, b"D")
            elif key == keyboard.Key.esc:
                loop.call_soon_threadsafe(queue.put_nowait, None)
                return False

        def on_release(key):
            if key == keyboard.Key.down:
                loop.call_soon_threadsafe(queue.put_nowait, b"d")

        listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        listener.start()

        try:
            while True:
                data = await queue.get()
                if data is None:
                    break
                await client.write_gatt_char(UART_RX_CHAR_UUID, data, response=False)
        finally:
            listener.stop()

    print("Disconnected.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--name",
        default=DEFAULT_NAME,
        help="BLE advertised name of the Pico (default: %(default)s)",
    )
    args = parser.parse_args()
    asyncio.run(run(args.name))


if __name__ == "__main__":
    main()
