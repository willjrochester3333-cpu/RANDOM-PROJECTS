#!/usr/bin/env bash
# CONSOLE setup (Raspberry Pi 5 + touchscreen, Raspberry Pi OS with desktop).
# Makes the Pi boot straight into the full-screen dashboard and speak announcements.
# Usage: ./install.sh <mqtt-password> [core-hostname]
set -euo pipefail
cd "$(dirname "$0")"
PASSWORD="${1:?usage: ./install.sh <mqtt-password> [core-hostname]}"
CORE="${2:-jarvis-core.local}"

sudo apt-get update
sudo apt-get install -y espeak-ng python3-paho-mqtt

# --- speech service (runs as you, so it can use your audio output) ---
# Keep your user services running without a login, and make sure `systemctl --user`
# can find them even from a remote shell such as Raspberry Pi Connect.
sudo loginctl enable-linger "$USER"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
for _ in $(seq 1 20); do [ -S "$XDG_RUNTIME_DIR/systemd/private" ] && break; sleep 0.5; done

sudo install -d /opt/jarvis
sudo install -m 755 speaker.py /opt/jarvis/speaker.py
install -d ~/.config/jarvis ~/.config/systemd/user
install -m 600 /dev/null ~/.config/jarvis/console.env
cat > ~/.config/jarvis/console.env <<EOF
MQTT_HOST=$CORE
MQTT_USER=jarvis
MQTT_PASSWORD=$PASSWORD
VOICE=en-gb
SPEED=165
EOF
cat > ~/.config/systemd/user/jarvis-speaker.service <<EOF
[Unit]
Description=J.A.R.V.I.S. console speech
After=network-online.target sound.target

[Service]
EnvironmentFile=%h/.config/jarvis/console.env
ExecStart=/usr/bin/python3 /opt/jarvis/speaker.py
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
EOF
systemctl --user daemon-reload
systemctl --user enable --now jarvis-speaker

# --- kiosk: Chromium full screen on login ---
if ! command -v chromium >/dev/null && ! command -v chromium-browser >/dev/null; then
    echo "Installing the Chromium browser..."
    sudo apt-get install -y chromium || sudo apt-get install -y chromium-browser
fi
BROWSER="$(command -v chromium || command -v chromium-browser)"
KIOSK="$BROWSER --kiosk --noerrdialogs --disable-infobars --no-first-run --disable-session-crashed-bubble --overscroll-history-navigation=0 --ozone-platform-hint=auto http://$CORE/"

if command -v labwc >/dev/null; then
    # Desktop version of Raspberry Pi OS: log straight in to the desktop on power-up.
    sudo raspi-config nonint do_boot_behaviour B4 || true
else
    # Lite version has no desktop: add just enough to show one full-screen browser.
    echo "No desktop found: installing a minimal one for the dashboard..."
    sudo apt-get install -y --no-install-recommends labwc
    sudo raspi-config nonint do_boot_behaviour B2 || true    # log in on the screen automatically
    sed -i '/jarvis-kiosk/d' ~/.profile 2>/dev/null || true
    echo 'if [ -z "$WAYLAND_DISPLAY" ] && [ "$(tty)" = /dev/tty1 ]; then exec labwc; fi  # jarvis-kiosk' >> ~/.profile
fi

# labwc (current Raspberry Pi OS) starts what is in its autostart file; older releases use XDG autostart.
install -d ~/.config/labwc ~/.config/autostart
sed -i '/jarvis-kiosk/d' ~/.config/labwc/autostart 2>/dev/null || true
echo "$KIOSK &  # jarvis-kiosk" >> ~/.config/labwc/autostart
cat > ~/.config/autostart/jarvis-kiosk.desktop <<EOF
[Desktop Entry]
Type=Application
Name=J.A.R.V.I.S. dashboard
Exec=$KIOSK
OnlyShowIn=LXDE;LXDE-pi;
EOF

# Keep the screen awake: this is a wall display.
sudo raspi-config nonint do_blanking 1 || true

echo "CONSOLE installed. Reboot to start the dashboard: sudo reboot"
echo "Test speech now with: espeak-ng -v en-gb 'Console online'"
