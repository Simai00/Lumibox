"""Tests für scripts/check-version.sh und scripts/bump-version.sh."""

import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECK = ROOT / "scripts" / "check-version.sh"
BUMP = ROOT / "scripts" / "bump-version.sh"


def _run(script, args, env_files=None):
    env = None
    if env_files:
        import os

        env = {
            **os.environ,
            "MANIFEST_FILE": str(env_files[0]),
            "FIRMWARE_FILE": str(env_files[1]),
        }
    return subprocess.run(
        ["bash", str(script), *args],
        capture_output=True,
        text=True,
        env=env,
        cwd=ROOT,
    )


def _copies(tmp_path):
    manifest = tmp_path / "manifest.json"
    firmware = tmp_path / "lumibox.yaml"
    shutil.copy(ROOT / "custom_components/lumibox/manifest.json", manifest)
    shutil.copy(ROOT / "esphome/lumibox.yaml", firmware)
    return manifest, firmware


def _current_version():
    manifest = ROOT / "custom_components/lumibox/manifest.json"
    return json.loads(manifest.read_text(encoding="utf-8"))["version"]


def test_check_matching_tag():
    assert _run(CHECK, [f"v{_current_version()}"]).returncode == 0


def test_check_without_tag():
    assert _run(CHECK, []).returncode == 0


def test_check_wrong_tag():
    major, minor, patch = _current_version().split(".")
    result = _run(CHECK, [f"v{major}.{minor}.{int(patch) + 1}"])
    assert result.returncode == 1


def test_check_mismatch(tmp_path):
    manifest, firmware = _copies(tmp_path)
    data = json.loads(manifest.read_text())
    data["version"] = "0.9.9"
    manifest.write_text(json.dumps(data))
    result = _run(CHECK, [], (manifest, firmware))
    assert result.returncode == 1
    assert "0.9.9" in result.stderr + result.stdout
    assert "0.2.0" in result.stderr + result.stdout


def test_bump(tmp_path):
    manifest, firmware = _copies(tmp_path)
    result = _run(BUMP, ["0.3.0"], (manifest, firmware))
    assert result.returncode == 0, result.stderr
    assert json.loads(manifest.read_text())["version"] == "0.3.0"
    text = firmware.read_text()
    assert 'version: "0.3.0"' in text
    assert 'version: "${version}"' in text
    assert _run(CHECK, ["v0.3.0"], (manifest, firmware)).returncode == 0


def test_bump_rejects_invalid(tmp_path):
    manifest, firmware = _copies(tmp_path)
    before = manifest.read_text()
    for bad in ["1.2", "v1.2.3", "1.2.3-rc1", ""]:
        assert _run(BUMP, [bad], (manifest, firmware)).returncode == 1
    assert manifest.read_text() == before


def test_check_rejects_invalid_versions(tmp_path):
    for bad in ["", "abc"]:
        manifest, firmware = _copies(tmp_path)
        data = json.loads(manifest.read_text())
        data["version"] = bad
        manifest.write_text(json.dumps(data))
        firmware.write_text(
            firmware.read_text().replace('version: "0.2.0"', f'version: "{bad}"', 1)
        )
        assert _run(CHECK, [], (manifest, firmware)).returncode == 1
