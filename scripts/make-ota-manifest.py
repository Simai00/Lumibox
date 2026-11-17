#!/usr/bin/env python3
"""Erzeugt manifest.json (ESP-Web-Tools-Format) für das HTTP-OTA-Update der Box.

Aufruf: make-ota-manifest.py <ota.bin> <version> <ausgabeordner> [--release-url URL] [--summary TEXT]

Kopiert die OTA-Binärdatei als lumibox-<version>.ota.bin in den Ausgabeordner und
schreibt daneben manifest.json mit relativem ota.path und md5.
"""
import argparse
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ota_bin", type=Path)
    parser.add_argument("version")
    parser.add_argument("out_dir", type=Path)
    parser.add_argument("--release-url")
    parser.add_argument("--summary")
    args = parser.parse_args()

    if not re.fullmatch(r"\d+\.\d+\.\d+", args.version):
        print(f"Ungültige Version '{args.version}' (erwartet X.Y.Z).", file=sys.stderr)
        return 1
    if not args.ota_bin.is_file():
        print(f"OTA-Datei nicht gefunden: {args.ota_bin}", file=sys.stderr)
        return 1

    data = args.ota_bin.read_bytes()
    name = f"lumibox-{args.version}.ota.bin"
    args.out_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(args.ota_bin, args.out_dir / name)

    ota = {"path": name, "md5": hashlib.md5(data).hexdigest()}  # noqa: S324 - vom ESPHome-Format verlangt
    if args.release_url:
        ota["release_url"] = args.release_url
    if args.summary:
        ota["summary"] = args.summary
    manifest = {
        "name": "Lumibox",
        "version": args.version,
        "builds": [{"chipFamily": "ESP32", "ota": ota}],
    }
    (args.out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
