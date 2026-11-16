# Gemeinsame Helfer für check-version.sh und bump-version.sh (wird per source geladen).
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MANIFEST_FILE="${MANIFEST_FILE:-$ROOT/custom_components/lumibox/manifest.json}"
FIRMWARE_FILE="${FIRMWARE_FILE:-$ROOT/esphome/lumibox.yaml}"
VERSION_RE='^[0-9]+\.[0-9]+\.[0-9]+$'

manifest_version() {
  python3 -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["version"])' "$MANIFEST_FILE"
}

firmware_version() {
  python3 - "$FIRMWARE_FILE" <<'PY'
import re, sys
text = open(sys.argv[1], encoding="utf-8").read()
m = re.search(r'^substitutions:\s*\n(?:[ \t]+.*\n|\s*\n)*?[ \t]+version:\s*"([^"]*)"', text, re.M)
if not m:
    sys.exit("substitutions.version nicht gefunden")
print(m.group(1))
PY
}
