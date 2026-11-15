#!/usr/bin/env bash
# One-time setup for CORE (Raspberry Pi 5, Raspberry Pi OS Lite 64-bit).
set -euo pipefail
cd "$(dirname "$0")"

if ! command -v docker >/dev/null; then
    curl -fsSL https://get.docker.com | sudo sh
fi

if [ ! -f .env ]; then
    cp .env.example .env
    sed -i "s/^MQTT_PASSWORD=.*/MQTT_PASSWORD=$(openssl rand -hex 12)/" .env
fi
set -a; . ./.env; set +a

# Broker password file, owned by the mosquitto user inside the container.
sudo docker run --rm -v "$PWD/mosquitto:/mosquitto/config" eclipse-mosquitto:2 sh -c \
    "mosquitto_passwd -b -c /mosquitto/config/passwd '$MQTT_USER' '$MQTT_PASSWORD' \
     && chown 1883:1883 /mosquitto/config/passwd && chmod 600 /mosquitto/config/passwd"

sudo docker compose up -d --build

echo
echo "CORE is running. Dashboard: http://$(hostname).local/"
echo "Every other node needs these two values:"
echo "  MQTT user:     $MQTT_USER"
echo "  MQTT password: $MQTT_PASSWORD"
