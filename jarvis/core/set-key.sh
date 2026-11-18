#!/usr/bin/env bash
# Saves your Anthropic API key in CORE's settings, checks that it works and restarts the
# server, so questions get internet answers. The key is typed (or pasted) without showing.
set -euo pipefail
cd "$(dirname "$0")"
[ -f .env ] || { echo "Run setup.sh first."; exit 1; }

read -r -s -p "Paste your Anthropic API key (it won't show on screen), then press Enter: " key
echo
key="$(printf '%s' "$key" | tr -d '[:space:]')"
if [ -z "$key" ]; then
    echo "No key given; nothing changed."
    exit 1
fi
if ! [[ "$key" =~ ^sk-ant-[A-Za-z0-9_-]{20,}$ ]]; then
    echo "That doesn't look like an Anthropic API key (they start with sk-ant-). Nothing changed."
    exit 1
fi

# Ask Anthropic whether the key works. Listing models is free. The key goes to curl on its
# input, not its command line, so other programs on this Pi can't see it.
code="$(printf 'header = "x-api-key: %s"\n' "$key" | curl -sS -o /dev/null -w '%{http_code}' -K - \
    -H "anthropic-version: 2026-10-21" --max-time 20 "https://api.anthropic.com/v1/models?limit=1" || true)"
case "$code" in
    200) echo "The key works." ;;
    401) echo "Anthropic rejected that key. Check you copied all of it. Nothing changed."; exit 1 ;;
    403) echo "The key is valid but not allowed to use the API; check its workspace in the Claude Console. Saving it anyway." ;;
    *)   echo "Couldn't check the key (no answer from Anthropic: $code). Saving it anyway." ;;
esac

if grep -q "^ANTHROPIC_API_KEY=" .env; then
    sed -i "s|^ANTHROPIC_API_KEY=.*|ANTHROPIC_API_KEY=$key|" .env
else
    echo "ANTHROPIC_API_KEY=$key" >> .env
fi
if grep -q "^CHAT_BACKEND=ollama$" .env; then
    sed -i "s/^CHAT_BACKEND=ollama$/CHAT_BACKEND=auto/" .env
fi
chmod 600 .env

echo "Restarting the server with the key..."
sudo docker compose up -d --force-recreate brain >/dev/null
echo "Done. Try: \"Hey Jarvis, who won the last Formula 1 race?\""
echo "Timings for each answer:  sudo docker compose -f $PWD/docker-compose.yml logs -f brain | grep timing"
