#!/usr/bin/env bash
# OUTPOST setup (Raspberry Pi 3 + Sense HAT, Raspberry Pi OS Lite).
# Usage: ./install.sh <mqtt-password> [core-hostname]
set -euo pipefail
cd "$(dirname "$0")"
PASSWORD="${1:?usage: ./install.sh <mqtt-password> [core-hostname]}"
CORE="${2:-jarvis-core.local}"

sudo apt-get update
sudo apt-get install -y sense-hat python3-paho-mqtt

sudo install -d /opt/jarvis
sudo install -m 755 weather.py /opt/jarvis/weather.py
sudo install -m 600 /dev/null /etc/jarvis-outpost.env
sudo tee /etc/jarvis-outpost.env >/dev/null <<EOF
MQTT_HOST=$CORE
MQTT_USER=jarvis
MQTT_PASSWORD=$PASSWORD
INTERVAL=60
TEMP_OFFSET=0
EOF

sudo tee /etc/systemd/system/jarvis-outpost.service >/dev/null <<EOF
[Unit]
Description=J.A.R.V.I.S. outdoor weather station
After=network-online.target
Wants=network-online.target

[Service]
EnvironmentFile=/etc/jarvis-outpost.env
ExecStart=/usr/bin/python3 /opt/jarvis/weather.py
Restart=always
RestartSec=10
User=$USER
SupplementaryGroups=i2c input video

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now jarvis-outpost
echo "OUTPOST installed. Watch it with: journalctl -u jarvis-outpost -f"
echo "If this is the first time the Sense HAT has been fitted, reboot once."
