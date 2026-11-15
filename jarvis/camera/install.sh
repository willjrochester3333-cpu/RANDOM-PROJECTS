#!/usr/bin/env bash
# CAMERA setup: any Raspberry Pi with a camera module plugged in.
# Usage: bash install.sh <mqtt-password> <core-ip-address>
set -euo pipefail
cd "$(dirname "$0")"
PASSWORD="${1:?usage: bash install.sh <mqtt-password> <core-ip-address>}"
CORE="${2:-jarvis-core.local}"

sudo apt-get update
sudo apt-get install -y --no-install-recommends python3-picamera2 python3-paho-mqtt

sudo install -d /opt/jarvis
sudo install -m 755 camera.py /opt/jarvis/camera.py

# Keep the same private stream key across re-installs, so saved links keep working.
KEY=""
if sudo test -f /etc/jarvis-camera.env; then
    KEY="$(sudo sed -n 's/^CAMERA_KEY=//p' /etc/jarvis-camera.env)"
fi
KEY="${KEY:-$(openssl rand -hex 16)}"

sudo install -m 600 /dev/null /etc/jarvis-camera.env
sudo tee /etc/jarvis-camera.env >/dev/null <<EOF
MQTT_HOST=$CORE
MQTT_USER=jarvis
MQTT_PASSWORD=$PASSWORD
CAMERA_KEY=$KEY
CAMERA_PORT=8081
CAMERA_SIZE=640x480
CAMERA_FPS=12
CAMERA_QUALITY=75
# Set to 1 if the picture is upside down.
CAMERA_ROTATE=0
EOF

sudo tee /etc/systemd/system/jarvis-camera.service >/dev/null <<EOF
[Unit]
Description=J.A.R.V.I.S. camera stream
After=network-online.target
Wants=network-online.target

[Service]
EnvironmentFile=/etc/jarvis-camera.env
ExecStart=/usr/bin/python3 /opt/jarvis/camera.py
Restart=always
RestartSec=15
User=$USER
SupplementaryGroups=video

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable jarvis-camera
sudo systemctl restart jarvis-camera

echo
echo "CAMERA installed. It appears on the dashboard within a few seconds."
echo "Check the camera is detected:  rpicam-hello --list-cameras"
echo "Watch the service:             journalctl -u jarvis-camera -f"
