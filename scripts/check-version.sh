#!/usr/bin/env bash
# Prüft, dass Integration und Firmware dieselbe Version haben (und optional das Tag v<Version> passt).
# Aufruf: scripts/check-version.sh [TAG]
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_version-common.sh"

manifest="$(manifest_version)"
firmware="$(firmware_version)"
status=0

for entry in "$MANIFEST_FILE:$manifest" "$FIRMWARE_FILE:$firmware"; do
  if ! [[ "${entry##*:}" =~ $VERSION_RE ]]; then
    echo "Ungültige Version '${entry##*:}' in ${entry%:*} (erwartet X.Y.Z)." >&2
    exit 1
  fi
done

if [ "$manifest" != "$firmware" ]; then
  echo "Versionen stimmen nicht überein:" >&2
  echo "  $MANIFEST_FILE: $manifest" >&2
  echo "  $FIRMWARE_FILE: $firmware" >&2
  status=1
fi

if [ $# -ge 1 ] && [ "$1" != "v$manifest" ]; then
  echo "Tag '$1' passt nicht zur Version von $MANIFEST_FILE ($manifest, erwartet 'v$manifest')." >&2
  status=1
fi

if [ "$status" -eq 0 ]; then
  echo "Version $manifest in Integration und Firmware konsistent."
fi
exit "$status"
