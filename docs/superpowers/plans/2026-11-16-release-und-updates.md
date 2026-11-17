# Versionierung, Updates und Veröffentlichung – Umsetzungsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eine Versionsnummer für Integration und Firmware. Die Firmware wird in CI gebaut und lässt sich in HA mit einem Klick aktualisieren. Das Repo ist unter neuem Namen bereit für die Veröffentlichung als Open Source.

**Architecture:**
- **Release:** Ein Git-Tag `vX.Y.Z` startet die CI. Sie prüft die Versionen, baut die allgemeine Firmware und veröffentlicht Manifest und Binärdateien auf GitHub Pages. Das GitHub-Release bedient HACS.
- **Box:** Die Box fragt das Manifest über `update: http_request` ab.
- **Integration:** Sie vergleicht die Firmware-Version (`sw_version` in der Geräte-Registry) mit `MIN_FIRMWARE_VERSION` und meldet Abweichungen als Reparatur-Hinweis.

**Tech Stack:**
- HA Custom Integration (Python, pytest-homeassistant-custom-component über `scripts/test.sh`);
- ESPHome 2026.10.0 (`scripts/esphome-config.sh`);
- GitHub Actions: `esphome/build-action` oder `esphome/workflows`, `home-assistant/actions/hassfest`, `hacs/action`, Pages;
- ESP Web Tools.

**Spec:** `docs/superpowers/specs/2026-11-16-release-und-updates-design.md`

## Global Constraints

- Name: Anzeige `Lumibox`, Domain und Event `lumibox` (`esphome.lumibox`), Firmware `lumibox` (+ MAC-Suffix), Repo `Simai00/lumibox`. Logo: `docs/assets/lumibox-logo.png`.
- Zielgruppe für **Updates** sind normale HA-Nutzer auf fremden Instanzen: ein Klick, ohne ESPHome Builder, Texte in Alltagssprache. Erstinstallation und Einrichtung macht der Projektautor, darauf liegt kein Fokus, also kein Web-Installer (siehe Spec, „Zielgruppe“).
- Erste öffentliche Version: **`0.2.0`**. Danach gilt SemVer:
  - Major: inkompatible Änderung an `set_led` oder Events;
  - Minor: neue Funktion;
  - Patch: Fehlerbehebung.
- Lizenz MIT, Copyright „Simon Friedli“. Doku und Texte auf Deutsch, die Oberfläche der Integration weiterhin de + en.
- Keine Secrets in eingecheckten Dateien oder in der gebauten Firmware.
- `ota: platform: esphome` bleibt neben `ota: platform: http_request` aktiv (Rettungsweg über den Builder).
- Historische Specs und Pläne unter `docs/superpowers/` werden nicht umgeschrieben. Nur der Docker-Pfad mit Benutzername in `plans/2026-11-16-figurenfarbe.md` wird neutralisiert.
- Minimale HA-Version bleibt 2025.4.0. Liegt eine benutzte API darüber, wird die Mindestversion angehoben und das im Ledger begründet.
- Docker-PATH in Bash: `export PATH="$PATH:/c/Users/simon/AppData/Local/Programs/DockerDesktop/resources/bin"`.

## Review Focus

1. **`sw_version` ohne Projektversion:** Alte Firmware liefert nur z. B. `"2026.10.0 (Nov 16 2026, 20:51:00)"`.
   - Erwartung: gilt als „zu alt“, mit Reparatur-Hinweis und ohne Exception.
   - Test in Task 3.
2. **Unvergleichbare Versionen** wie `"dev"`, `"0.3.0-beta.1"` oder Leerstring.
   - Erwartung: keine Exception; `dev` gilt als aktuell, nicht parsebar als zu alt, Vorabversionen nach SemVer.
   - Test in Task 3.
3. **Hinweis nach Update:** Nach dem Firmware-Update ändert sich `sw_version` in der Registry.
   - Erwartung: Der Hinweis verschwindet ohne HA-Neustart.
   - Test in Task 3.
4. **ESPHome-Gerät gelöscht oder noch nicht verbunden** (`sw_version` ist `None`).
   - Erwartung: kein Hinweis und kein Fehler. Das ist kein Versionsproblem.
   - Test in Task 3.
5. **Tag und Versionen passen nicht zusammen** (`v0.2.1`, aber `manifest.json` steht auf `0.2.0`).
   - Erwartung: Der Release-Workflow bricht ab, bevor etwas veröffentlicht wird.
   - Test in Task 2 (`scripts/check-version.sh` mit Fehlfall).

---

### Task 1: Projekt umbenennen

**Files:**
- Move: `custom_components/home_tonie/` → `custom_components/lumibox/`, `esphome/home-tonie-common.yaml` → `esphome/lumibox.yaml`
- Modify: alle Dateien der Integration, `tests/*`, `README.md`, `hacs.json`, `scripts/*.sh`, `.claude/agents/*.md`, `docs/superpowers/plans/2026-11-16-figurenfarbe.md` (nur den Docker-Pfad)

**Interfaces:**
- Produces:
  - `DOMAIN = "lumibox"`;
  - Event `esphome.lumibox`, gesendet von der Firmware und gehört von der Integration;
  - `manifest.json`: `"documentation"`/`"issue_tracker"` mit `https://github.com/Simai00/lumibox`, `"version": "0.2.0"`;
  - Firmware `esphome: name: lumibox`, `friendly_name: Lumibox`.
- Texte: „Home Tonie“ → `Lumibox`. Der Satz zur Toniebox im README wird markenneutral, z. B. „Audio-Box mit NFC-Figuren für kleine Kinder“.

- [ ] **Step 1:** Mit `git mv` verschieben, dann alle Vorkommen ersetzen. Kontrolle: `git grep -niE 'tonie'` findet nur noch `docs/superpowers/specs|plans` (historisch).
- [ ] **Step 2:** `bash scripts/test.sh -q` → alles grün. `bash scripts/esphome-config.sh lumibox.yaml` → `Configuration is valid!` (mit Dummy-Secrets, falls noch nötig).
- [ ] **Step 3: Commit** `refactor: Projekt in Lumibox umbenennen`

---

### Task 2: Eine Versionsnummer und Prüfskripte

**Files:**
- Create: `scripts/bump-version.sh`, `scripts/check-version.sh`, `tests/test_version_scripts.sh` oder ein pytest-Test, der die Skripte per `subprocess` aufruft
- Modify: `esphome/lumibox.yaml`

**Interfaces:**
- Firmware:
  - `substitutions: version: "0.2.0"`;
  - `esphome: project: name: "simai00.lumibox"`, `version: "${version}"`.
- `scripts/bump-version.sh X.Y.Z` setzt die Version in `manifest.json` und in `substitutions.version` der Firmware.
- `scripts/check-version.sh [TAG]`:
  - Exit 0, wenn beide Dateien dieselbe Version haben und, falls ein `TAG` übergeben wird, `TAG == v<Version>` gilt;
  - sonst Exit 1 mit einer Meldung, welche Datei welche Version hat.

- [ ] **Step 1: Failing tests**
  - `check-version.sh v0.2.0` → 0;
  - `check-version.sh v0.2.1` → 1;
  - Manifest und Firmware unterschiedlich (temporäre Kopie) → 1;
  - `bump-version.sh 0.3.0` auf einer Kopie → beide Dateien `0.3.0`.
- [ ] **Step 2:** Implementieren (bash, `sed`/`python3 -c` für JSON). Tests grün.
- [ ] **Step 3: Commit** `build: eine Versionsnummer für Integration und Firmware`

---

### Task 3: Firmware-Versionsprüfung in der Integration

**Files:**
- Create: `custom_components/lumibox/firmware.py`, `custom_components/lumibox/repairs.py`
- Modify: `const.py`, `__init__.py`, `strings.json`, `translations/de.json`, `translations/en.json`
- Test: `tests/test_firmware.py`

**Interfaces:**
- `const.py`:
  - `MIN_FIRMWARE_VERSION = "0.2.0"`.
  - Pflegeregel als Kommentar: wird erhöht, wenn die Integration etwas von der Firmware braucht, das ältere Versionen nicht haben.
- `firmware.parse_firmware_version(sw_version: str | None) -> str | None`:
  - `"0.2.0 (ESPHome 2026.10.0)"` → `"0.2.0"`;
  - ohne `" (ESPHome "` → `None`.
- `firmware.is_outdated(sw_version: str | None) -> bool | None`:
  - `None`, wenn `sw_version` `None` ist (Gerät unbekannt, keine Aussage);
  - `True`, wenn keine Projektversion vorhanden oder nicht parsebar;
  - `"dev"` → `False`;
  - sonst Vergleich mit `MIN_FIRMWARE_VERSION` über `awesomeversion.AwesomeVersion` (in HA enthalten).
- Reparatur-Hinweis:
  - `issue_registry.async_create_issue(hass, DOMAIN, f"firmware_outdated_{subentry_id}", is_fixable=True, data={"device_id": <ESPHome-Gerät der Box>}, severity=IssueSeverity.WARNING, translation_key="firmware_outdated", translation_placeholders={"box": <Boxname>, "current": <Version oder "unbekannt">, "required": MIN_FIRMWARE_VERSION})`;
  - wird entfernt (`async_delete_issue`), sobald die Box aktuell ist.
- `repairs.async_create_fix_flow(hass, issue_id, data)` liefert einen `RepairsFlow` mit einem Bestätigungsschritt („Jetzt aktualisieren“). Bei Bestätigung:
  - Er sucht in der Entity-Registry die `update`-Entität der Plattform `esphome` mit `device_id == data["device_id"]` und ruft `update.install` auf.
  - Gibt es keine solche Entität, oder ist sie `off` (kein Update verfügbar), bricht er mit `abort` ab, Grund `no_update`. Text: „Für diese Box ist gerade kein Update verfügbar. Prüfe, ob die Box eingeschaltet und mit dem WLAN verbunden ist.“
- Die Prüfung läuft beim Setup jeder Box und bei `EVENT_DEVICE_REGISTRY_UPDATED` für das ESPHome-Gerät der Box (`changes` enthält `sw_version`). Der Listener wird beim Unload abgemeldet.
- Text de: „Die Firmware der Box {box} ist zu alt ({current}, benötigt {required}). Bitte unter Einstellungen › Geräte › {box} die Firmware aktualisieren.“ Dazu eine sinngemässe Übersetzung in en.

- [ ] **Step 1: Failing tests:**
  - `test_parse_firmware_version` (Fälle aus Review Focus 1/2);
  - `test_is_outdated_cases`;
  - `test_issue_created_for_old_firmware`;
  - `test_issue_removed_after_registry_update` (Review Focus 3: `device_registry.async_update_device(..., sw_version="0.2.0 (ESPHome x)")` → Hinweis weg);
  - `test_no_issue_when_sw_version_none` (Review Focus 4);
  - `test_unload_removes_listener`;
  - `test_fix_flow_installs_update` (`update.install` wird mit der richtigen `entity_id` aufgerufen);
  - `test_fix_flow_aborts_without_update_entity`;
  - `test_fix_flow_aborts_when_no_update_available`.
- [ ] **Step 2:** Tests laufen lassen und Fehlschlag sehen.
- [ ] **Step 3:** Implementieren.
- [ ] **Step 4:** Gesamte Suite laufen lassen. Erwartet: grün, keine Warnungen.
- [ ] **Step 5: Commit** `feat: Reparatur-Hinweis bei zu alter Box-Firmware`

---

### Task 4: Allgemeine Firmware ohne Secrets, mit Update-Entität

**Files:**
- Modify: `esphome/lumibox.yaml`, `scripts/esphome-config.sh`

**Interfaces:**
- `esphome:`:
  - `name: lumibox`, `friendly_name: Lumibox`, `name_add_mac_suffix: true`;
  - `project` aus Task 2.
- `dashboard_import: package_import_url: github://Simai00/lumibox/esphome/lumibox.yaml@main`.
- `api: encryption: {}`, ohne `key`. `actions: set_led` bleibt unverändert.
- `wifi:` ohne `ssid`/`password`. `ap:` mit `ssid: "Lumibox Setup"`, ohne Passwort. `captive_portal:` ist aktiv.
- `ota:`:
  - `- platform: esphome`
  - `- platform: http_request`
- `http_request:`: `verify_ssl` siehe Spec, Abschnitt „Dem Umsetzer überlassen“, Entscheid ins Ledger.
- `update: - platform: http_request`:
  - `name: "Firmware"`;
  - `source: https://simai00.github.io/lumibox/firmware/manifest.json`;
  - `update_interval: 6h`.
- `scripts/esphome-config.sh` braucht keine `secrets.yaml` mehr. README und Skript erwähnen sie nicht mehr.

- [ ] **Step 1:** Ändern.
- [ ] **Step 2:** Validieren mit `bash scripts/esphome-config.sh lumibox.yaml`, **ohne** `secrets.yaml`. Erwartet: `Configuration is valid!`.
- [ ] **Step 3:** Kompilieren (`esphome compile` im Container, kann im Hintergrund laufen). Erwartet: Exit 0. Die Flash- und RAM-Belegung kommt in den Bericht (wegen HTTPS auf dem ESP32).
- [ ] **Step 4: Commit** `feat: allgemeine Firmware mit Update über GitHub Pages`

---

### Task 5: CI und Release-Workflow

**Files:**
- Create: `.github/workflows/ci.yml`, `.github/workflows/release.yml`

**Interfaces:**
- `ci.yml` läuft bei Push und PR. Jobs:
  - Python 3.14 mit `pip install -r requirements_test.txt` und `pytest`;
  - `home-assistant/actions/hassfest`;
  - `hacs/action` (category `integration`);
  - ESPHome `config` für `esphome/lumibox.yaml`;
  - `scripts/check-version.sh`.
- `release.yml` läuft bei Push eines Tags `v*`:
  1. `scripts/check-version.sh "$GITHUB_REF_NAME"`, bei Fehler Abbruch (Review Focus 5).
  2. Firmware bauen. Das Ergebnis: `manifest.json` mit `builds[].ota.{path,md5}`, dazu `*.ota.bin` und `*.factory.bin`.
  3. GitHub-Release zum Tag mit automatischen Release Notes und den `.bin` als Assets.
  4. Pages-Deploy (`actions/upload-pages-artifact`, `actions/deploy-pages`): `/firmware/manifest.json` und die Binärdateien. Kein Web-Installer.
- `ota.path` im Manifest ist relativ oder eine Pages-URL, **keine** GitHub-Release-URL (Pufferproblem bei Weiterleitungen, laut ESPHome-Doku).

- [ ] **Step 1:** Workflows schreiben. Lokal mit `actionlint` prüfen (Docker-Image `rhysd/actionlint`). Erwartet: keine Fehler.
- [ ] **Step 2:** Den Build-Schritt lokal nachstellen oder in einem Fork bzw. auf einem Test-Tag laufen lassen. Erwartet: Das Manifest enthält den Abschnitt `ota`. Fehlt er, ergänzt ein Skript `md5` und `path` (Ruling ins Ledger).
- [ ] **Step 3: Commit** `ci: Tests, Validierung und Release mit Firmware auf GitHub Pages`

---

### Task 6: Repo für die Veröffentlichung aufräumen

**Files:**
- Create: `LICENSE` (MIT)
- Create:
  - `custom_components/lumibox/brand/icon.png` (256×256) und `icon@2x.png` (512×512), aus `docs/assets/lumibox-logo.png` verkleinert, transparent;
  - `logo.png` und `logo@2x.png`, gleiches Motiv (das Logo ist quadratisch).
- Modify: `README.md` (Logo oben), `hacs.json`, `.gitignore`

**Inhalt README (Deutsch, für normale HA-Nutzer zuerst, Entwickler am Schluss):**
- kurze Beschreibung, markenneutral, mit dem Hinweis „nicht verbunden mit Boxine GmbH/tonies“;
- Hardware und Pinbelegung wie bisher;
- **Updates (Hauptteil, für Nutzer ohne ESPHome-Wissen):**
  - Integration über HACS.
  - Firmware über die Entität „Firmware“ der Box. Der Reparatur-Hinweis erscheint, wenn eine Box zu alt ist.
  - Reihenfolge: zuerst die Firmware, dann die Integration, wenn das Release das verlangt. Das steht in den Release Notes.
  - Was tun, wenn das Update nicht startet: Box eingeschaltet und im WLAN? Einstellungen › Updates neu laden.
- **Installation (kurz, für den Einrichtenden):**
  - Integration über HACS (benutzerdefiniertes Repository);
  - Firmware per USB flashen (`factory.bin` aus dem Release oder ESPHome Builder);
  - WLAN über das Captive Portal „Lumibox Setup“;
  - Box in HA hinzufügen (der API-Schlüssel wird automatisch gesetzt) und in der Integration einrichten.
- **Eigene Firmware-Anpassung:** im ESPHome Builder „Übernehmen“ (`dashboard_import`).
- **Entwicklung:**
  - `scripts/test.sh`, `scripts/esphome-config.sh`;
  - Release mit `scripts/bump-version.sh X.Y.Z`, Commit, `git tag vX.Y.Z`, Push.
- Manuelle Testcheckliste wie bisher, mit neuen Namen.

**Weitere Punkte:**
- `hacs.json`: `"homeassistant": "2025.4.0"` bleibt. Im README steht, welche Angaben HACS beim Repo verlangt: Beschreibung, Topics und Releases.
- `.gitignore`: `dev/` bleibt ignoriert. Die Docker-Dev-Umgebung wird nicht veröffentlicht, das kann später nachgeholt werden.
- Kontrolle vor dem Commit:
  - `git grep -nIiE 'users/simon|192\.168|@gmail|friedli\.dev'` findet nur den Lizenzinhaber in `LICENSE`;
  - `git grep -niE 'tonie'` findet nur historische Docs.

- [ ] **Step 1:** Ändern.
- [ ] **Step 2:** Kontrollen laufen lassen. Die gesamte Suite und die ESPHome-Validierung sind grün.
- [ ] **Step 3: Commit** `docs: Lizenz und README für die Veröffentlichung`

---

### Task 7: Veröffentlichen und bestehende Boxen umstellen (Nutzer, nicht automatisierbar)

Diese Schritte macht der Nutzer selbst. Der Umsetzer hilft dabei, führt aber nichts Nach-aussen-Wirkendes ohne Bestätigung aus.

1. **Lokal aufräumen:**
   - `git update-ref -d refs/cline/checkpoints/1793405324516_h1jzz/1`;
   - `git branch -D master`;
   - `git push origin --delete figurenfarbe`.
2. **Mergen:** Den Branch nach `main` mergen und pushen.
3. **GitHub:**
   - Repo in `lumibox` umbenennen;
   - Beschreibung und Topics setzen (`home-assistant`, `hacs`, `esphome`, `nfc`);
   - Repo auf **public** stellen (zuerst, denn Pages auf privaten Repos braucht einen bezahlten Plan);
   - Pages mit Quelle „GitHub Actions“ aktivieren;
   - Settings › Environments › github-pages › Deployment branches and tags: Regel für Tags `v*` hinzufügen (sonst scheitert das Deploy bei Tag-Läufen).
4. **Release:** `git tag v0.2.0 && git push origin v0.2.0`. Danach prüfen, ob `https://simai00.github.io/lumibox/firmware/manifest.json` erreichbar ist und ob das Release Assets hat.
5. **Pro Box:**
   1. Firmware flashen. Hauptweg ist USB (`lumibox-0.2.0.factory.bin`, z. B. mit web.esphome.io). OTA aus dem Builder zielt auf `lumibox.local` statt auf den alten Gerätenamen und scheitert daher. Falls OTA gewünscht: `esphome run lumibox.yaml --device <alte IP der Box>`.
   2. Mit dem WLAN „Lumibox Setup“ verbinden und im Captive Portal das Heim-WLAN eintragen (die alte Firmware hatte die WLAN-Zugangsdaten fest eingebaut, die neue hat keine).
   3. In HA unter „Einstellungen › Geräte & Dienste › ESPHome“ den Eintrag der alten Box löschen. Danach die neu entdeckte `lumibox-xxxxxx` hinzufügen. HA setzt den Schlüssel selbst; prüfen, dass die Verbindung verschlüsselt ist (im Config Entry steht `noise_psk`).
   4. Prüfen, dass die Entität „Firmware“ die Version 0.2.0 zeigt.
6. **Integration:**
   - Die neue Integration über HACS installieren und die Boxen und Figuren neu anlegen;
   - `home_tonie` entfernen;
   - prüfen, dass kein Reparatur-Hinweis offen ist.
7. **Update-Pfad testen:** `bash scripts/bump-version.sh 0.2.1 && git commit -am "chore: Version 0.2.1" && git push && git tag v0.2.1 && git push origin v0.2.1`. In HA erscheint das Firmware-Update, Installieren klappt, und danach steht die Version 0.2.1 in den Geräteinfos.
