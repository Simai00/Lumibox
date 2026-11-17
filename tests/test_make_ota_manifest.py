"""Tests für scripts/make-ota-manifest.py."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "make-ota-manifest.py"


def _run(*args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *map(str, args)],
        capture_output=True,
        text=True,
    )


def test_writes_manifest_and_copies_binary(tmp_path):
    ota = tmp_path / "firmware.ota.bin"
    ota.write_bytes(b"firmware-bytes")
    out = tmp_path / "site" / "firmware"

    result = _run(ota, "1.2.3", out)

    assert result.returncode == 0, result.stderr
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["name"] == "Lumibox"
    assert manifest["version"] == "1.2.3"
    build = manifest["builds"][0]
    assert build["chipFamily"] == "ESP32"
    assert build["ota"] == {
        "path": "lumibox-1.2.3.ota.bin",
        "md5": hashlib.md5(b"firmware-bytes").hexdigest(),
    }
    assert (out / "lumibox-1.2.3.ota.bin").read_bytes() == b"firmware-bytes"


def test_optional_release_url_and_summary(tmp_path):
    ota = tmp_path / "f.bin"
    ota.write_bytes(b"x")

    result = _run(ota, "1.2.3", tmp_path / "o", "--release-url", "https://example/r", "--summary", "Neu")

    assert result.returncode == 0, result.stderr
    manifest = json.loads((tmp_path / "o" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["builds"][0]["ota"]["release_url"] == "https://example/r"
    assert manifest["builds"][0]["ota"]["summary"] == "Neu"


def test_missing_binary_fails(tmp_path):
    result = _run(tmp_path / "nope.bin", "1.2.3", tmp_path / "o")
    assert result.returncode != 0


def test_invalid_version_fails(tmp_path):
    ota = tmp_path / "f.bin"
    ota.write_bytes(b"x")
    result = _run(ota, "v1.2", tmp_path / "o")
    assert result.returncode != 0
