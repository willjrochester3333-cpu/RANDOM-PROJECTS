#!/usr/bin/env bash
# Setup and upgrade for CORE (Raspberry Pi 5, Raspberry Pi OS Lite 64-bit). Safe to re-run.
set -euo pipefail
cd "$(dirname "$0")"

if ! command -v docker >/dev/null; then
    curl -fsSL https://get.docker.com | sudo sh
fi

# ---- settings file: create it, or add any new settings an older one is missing ----
if [ ! -f .env ]; then
    cp .env.example .env
    sed -i "s/^MQTT_PASSWORD=.*/MQTT_PASSWORD=$(openssl rand -hex 12)/" .env
fi
# One-time upgrade of older settings files: the faster model becomes the default.
if ! grep -q "^JARVIS_ENV_VERSION=" .env && grep -q "^OLLAMA_MODEL=llama3.2:3b$" .env; then
    sed -i "s/^OLLAMA_MODEL=.*/OLLAMA_MODEL=llama3.2:1b/" .env
    echo "Switched to the faster model llama3.2:1b."
    echo "To go back: set OLLAMA_MODEL=llama3.2:3b in $PWD/.env and run setup.sh again."
fi
while IFS= read -r line; do
    key="${line%%=*}"
    case "$line" in ''|'#'*) continue ;; esac
    grep -q "^$key=" .env || echo "$line" >> .env
done < .env.example
set -a; . ./.env; set +a

# ---- broker password file, owned by the mosquitto user inside the container ----
sudo docker run --rm -v "$PWD/mosquitto:/mosquitto/config" eclipse-mosquitto:2 sh -c \
    "rm -f /mosquitto/config/passwd && mosquitto_passwd -b -c /mosquitto/config/passwd '$MQTT_USER' '$MQTT_PASSWORD' \
     && chown 1883:1883 /mosquitto/config/passwd && chmod 600 /mosquitto/config/passwd"

# ---- the containers: broker, brain, local language model, speech ----
echo "Building and starting the server (the first time this takes a while)..."
sudo docker compose up -d --build

echo "Downloading the language model $OLLAMA_MODEL (once; llama3.2:1b is about 1.3 GB)..."
pulled=no
for attempt in 1 2 3 4 5 6; do
    if sudo docker compose exec ollama ollama pull "$OLLAMA_MODEL"; then pulled=yes; break; fi
    echo "Language model service still starting, retrying..."; sleep 10
done
if [ "$pulled" = no ]; then
    echo "WARNING: could not download $OLLAMA_MODEL. Check the name on ollama.com/library,"
    echo "fix OLLAMA_MODEL in $PWD/.env and run setup.sh again."
fi

# ---- the voice service: microphone and speaker, on this Pi outside Docker ----
sudo apt-get install -y alsa-utils espeak-ng python3-venv python3-numpy >/dev/null
sudo install -d /opt/jarvis
sudo install -m 755 voice/voice.py /opt/jarvis/voice.py
if [ ! -x /opt/jarvis/venv/bin/python ]; then
    sudo python3 -m venv --system-site-packages /opt/jarvis/venv
fi
echo "Installing the wake-word detector..."
sudo /opt/jarvis/venv/bin/pip install -q "openwakeword==0.4.0" "onnxruntime>=1.17" "paho-mqtt>=1.6" numpy

sudo install -m 600 /dev/null /etc/jarvis-voice.env
sudo tee /etc/jarvis-voice.env >/dev/null <<EOF
CORE_URL=http://127.0.0.1
MQTT_HOST=127.0.0.1
MQTT_USER=$MQTT_USER
MQTT_PASSWORD=$MQTT_PASSWORD
MIC_DEVICE=${MIC_DEVICE:-default}
SPEAKER_DEVICE=${SPEAKER_DEVICE:-default}
WAKE_WORD=${WAKE_WORD:-1}
WAKE_THRESHOLD=${WAKE_THRESHOLD:-0.5}
EOF
sudo tee /etc/systemd/system/jarvis-voice.service >/dev/null <<EOF
[Unit]
Description=J.A.R.V.I.S. voice (microphone and speaker)
After=network-online.target docker.service
Wants=network-online.target

[Service]
EnvironmentFile=/etc/jarvis-voice.env
ExecStart=/opt/jarvis/venv/bin/python /opt/jarvis/voice.py
Restart=always
RestartSec=10
User=$USER
SupplementaryGroups=audio

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable jarvis-voice
sudo systemctl restart jarvis-voice

echo
echo "CORE is running. Dashboard: http://$(hostname -I | awk '{print $1}')/"
echo "Every other node needs these two values:"
echo "  MQTT user:     $MQTT_USER"
echo "  MQTT password: $MQTT_PASSWORD"
echo
echo "Voice: say 'Hey Jarvis', wait for the beep, then ask your question."
echo "  Sound devices found:   arecord -l   and   aplay -l"
echo "  Voice service log:     journalctl -u jarvis-voice -f"
