#!/usr/bin/env bash
# Compares language models on this Pi with Jarvis's own prompt and settings, and prints which
# one answers soonest and gets the most right. Takes about 5 to 15 minutes.
#   bash bench.sh                    the usual small models
#   bash bench.sh qwen2.5:1.5b       just these, plus the model Jarvis uses now
#   add --keep to keep the downloaded models (otherwise they're deleted again)
set -euo pipefail
cd "$(dirname "$0")"
echo "While this runs Jarvis answers slowly, because the models take turns in memory."
status=0
sudo docker compose exec -T brain python -u -m jarvis_core.bench "$@" || status=$?
echo "Putting Jarvis's own model back..."
sudo docker compose restart brain >/dev/null
exit "$status"
