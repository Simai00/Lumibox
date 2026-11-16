#!/usr/bin/env bash
# Führt die Tests der Integration im Container aus: scripts/test.sh [pytest-Argumente]
set -euo pipefail

cd "$(dirname "$0")/.."

IMAGE="lumibox-test"
REQ_HASH="$(cat requirements_test.txt Dockerfile.test | cksum | cut -d" " -f1)"

current_hash="$(docker image inspect --format '{{ index .Config.Labels "requirements-hash" }}' "$IMAGE" 2>/dev/null || true)"
if [ "$current_hash" != "$REQ_HASH" ]; then
  echo "Baue Image $IMAGE ..." >&2
  docker build -f Dockerfile.test --label "requirements-hash=$REQ_HASH" -t "$IMAGE" .
fi

# Git Bash: keine Pfadumschreibung, Windows-Pfad für den Mount verwenden.
export MSYS_NO_PATHCONV=1
REPO_DIR="$(pwd -W 2>/dev/null || pwd)"

tty_flag=""
if [ -t 0 ] && [ -t 1 ]; then
  tty_flag="-t"
fi

exec docker run --rm $tty_flag -v "$REPO_DIR:/app" -w /app "$IMAGE" python -m pytest "$@"
