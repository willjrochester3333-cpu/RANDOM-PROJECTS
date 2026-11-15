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
BROWSER="$(command -v chromium || command -v chromium-browser || true)"
if [ -z "$BROWSER" ]; then
    echo "Chromium not found. Install it with: sudo apt-get install -y chromium" >&2
    exit 1
fi
KIOSK="$BROWSER --kiosk --noerrdialogs --disable-infobars --no-first-run --disable-session-crashed-bubble --overscroll-history-navigation=0 http://$CORE/"

# Current Raspberry Pi OS uses the labwc compositor; older releases use an XDG autostart entry.
install -d ~/.config/labwc ~/.config/autostart
grep -qs "jarvis-kiosk" ~/.config/labwc/autostart || \
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
