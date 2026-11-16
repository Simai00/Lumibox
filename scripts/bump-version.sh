#!/usr/bin/env bash
# Setzt die Version in manifest.json und in substitutions.version der Firmware.
# Aufruf: scripts/bump-version.sh X.Y.Z
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_version-common.sh"

if [ $# -ne 1 ] || ! [[ "$1" =~ $VERSION_RE ]]; then
  echo "Aufruf: $0 X.Y.Z (z. B. 0.3.0)" >&2
  exit 1
fi

python3 - "$1" "$MANIFEST_FILE" "$FIRMWARE_FILE" <<'PY'
import re, sys
version, manifest, firmware = sys.argv[1:]

text = open(manifest, encoding="utf-8", newline="").read()
text, n = re.subn(r'("version"\s*:\s*")[^"]*(")', lambda m: m.group(1) + version + m.group(2), text, count=1)
if n != 1:
    sys.exit("version in manifest.json nicht gefunden")
open(manifest, "w", encoding="utf-8", newline="").write(text)

text = open(firmware, encoding="utf-8", newline="").read()
pat = r'(^substitutions:[ \t]*\r?\n(?:[ \t]+.*\r?\n|[ \t]*\r?\n)*?[ \t]+version:\s*")[^"]*(")'
text, n = re.subn(pat, lambda m: m.group(1) + version + m.group(2), text, count=1, flags=re.M)
if n != 1:
    sys.exit("substitutions.version in der Firmware nicht gefunden")
open(firmware, "w", encoding="utf-8", newline="").write(text)
PY
echo "Version auf $1 gesetzt."
