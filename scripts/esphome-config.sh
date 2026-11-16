#!/usr/bin/env bash
# Validiert eine ESPHome-Konfiguration im Container: scripts/esphome-config.sh <datei im esphome/-Ordner>
# Beispiel: bash scripts/esphome-config.sh home-tonie-common.yaml
set -euo pipefail

if [ $# -ne 1 ]; then
  echo "Aufruf: $0 <datei.yaml>" >&2
  exit 2
fi

cd "$(dirname "$0")/../esphome"

# Image-Version gepinnt (reproduzierbar); bei Bedarf per ESPHOME_IMAGE überschreiben.
ESPHOME_IMAGE="${ESPHOME_IMAGE:-ghcr.io/esphome/esphome:2026.10.0}"

# Git Bash: keine Pfadumschreibung, Windows-Pfad für den Mount verwenden.
export MSYS_NO_PATHCONV=1
ESPHOME_DIR="$(pwd -W 2>/dev/null || pwd)"

exec docker run --rm -v "$ESPHOME_DIR:/config" "$ESPHOME_IMAGE" config "/config/$1"
