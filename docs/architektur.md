# Lumibox – Architektur

Wie die Teile von Lumibox zusammenspielen. Für Bedienung, Installation und Updates siehe [README](../README.md).

## Überblick

```
┌──────────── Box (ESPHome, ESP32) ─────────────────────────────┐
│ PN532    ─► Event esphome.lumibox {action: tag_on/off, uid}   │
│ Encoder  ─► Event esphome.lumibox {action: rotate_cw/ccw}     │
│ Taster   ─► Event esphome.lumibox {action: play_pause/prev/next}
│ LED-Ring ◄─ API-Action set_led(mode, level, r, g, b)          │
│ Update   ◄─ Manifest auf GitHub Pages (update: http_request)  │
└──────────────────────────────┬────────────────────────────────┘
                               │ ESPHome Native API (verschlüsselt)
┌──────────────────────────────▼─────────── Home Assistant ─────┐
│ Integration "lumibox"                                         │
│   Haupteintrag                                                │
│   ├── Subentry "box"    (ESPHome-Gerät, Player, MA-Benutzer)  │
│   └── Subentry "figure" (Name, UID, Spotify-Link, Farbe)      │
└──────────────────────────────┬────────────────────────────────┘
                               │ music_assistant.play_media / media_player.*
                       Music Assistant (ein Spotify-Account pro Kind)
                               │
                       Sonos / AirPlay-Lautsprecher
```

**Grundprinzip:** Die Box ist „dumm“. Sie meldet Ereignisse und zeigt LED-Zustände an. Logik und Figurendaten liegen in der Integration. Neue Figuren oder geändertes Verhalten brauchen kein Neu-Flashen.

**Figuren sind eine gemeinsame Bibliothek:** Jede Figur spielt auf jeder Box, immer auf dem Lautsprecher der Box, auf der sie liegt, und über den Spotify-Account des Kindes dieser Box.

## Firmware (`esphome/lumibox.yaml`)

Eine allgemeine Firmware für alle Boxen, ohne Secrets:
- **Gerätename:** `lumibox` plus MAC-Suffix (`name_add_mac_suffix`), dadurch automatisch eindeutig.
- **WLAN:** Ohne gespeichertes WLAN öffnet die Box das Setup-WLAN „Lumibox Setup“ mit Captive Portal.
- **API-Verschlüsselung:** `api: encryption:` ohne Schlüssel. Eine aktuelle HA-Version setzt beim ersten Verbinden selbst einen Schlüssel.
- **Updates:** `update: platform: http_request` fragt alle 6 h `https://simai00.github.io/lumibox/firmware/manifest.json` ab und installiert über `ota: platform: http_request`. `ota: platform: esphome` bleibt als Rettungsweg.
- **Version:** `substitutions.version` → `esphome: project: version`. HA zeigt sie als `<version> (ESPHome <x>)` in den Geräteinfos.

### Events an Home Assistant

Ein Event-Typ `esphome.lumibox` mit dem Feld `action`. HA ergänzt `device_id` selbst, darüber ordnet die Integration das Event einer Box zu. Die Firmware darf deshalb kein eigenes Feld `device_id` senden.

| Auslöser | `action` | weitere Daten |
| :--- | :--- | :--- |
| Figur aufgelegt | `tag_on` | `uid` |
| Figur abgenommen | `tag_off` | `uid` |
| Encoder rechts / links | `rotate_cw` / `rotate_ccw` | – |
| Encoder-Taster | `play_pause` | – |
| Taster GPIO26 / GPIO27 | `prev` / `next` | – |

### LED-Steuerung: `set_led`

API-Action `set_led(mode: string, level: int, r: int, g: int, b: int)`. In HA heisst sie `esphome.<gerätename>_set_led` (Bindestriche werden zu Unterstrichen). Effekte und Zeitabläufe stecken in der Firmware.

| `mode` | Darstellung | Dauer |
| :--- | :--- | :--- |
| `off` | aus | dauerhaft |
| `loading` | weisser Lade-Spinner | bis zum nächsten Modus |
| `playing` | Farb-Spinner in der Figurfarbe (`r/g/b`): Ring ~40 %, heller Kopf mit Schweif, eine Runde in ~3 s | dauerhaft |
| `hold` | statisch warmweiss, 10 % (Figur liegt, per Taster pausiert) | dauerhaft |
| `paused` | ausblenden, dann `off` | ~1,5 s |
| `unknown` | 3× rot blinken, dann `off` | ~2 s |
| `error` | rot, dann `off` | ~3 s |
| `volume` | `level` (0–100) als Füllstand, danach zurück zum vorherigen Modus | ~1,5 s |

Die Helligkeit ist mit `color_correct: [50%, 50%, 50%]` hart begrenzt (Strom, Blendung).

### Lokale Status-Anzeige

Die Box zeigt ihre Zustände selbst an, auch ohne Home Assistant. Diese Muster kommen aus der Firmware, nicht aus `set_led`.

| Zustand | Muster | Wann / wie lange |
| :--- | :--- | :--- |
| Startet / verbindet | weiss, langsam atmend | ab Boot bis HA verbunden, höchstens ~60 s |
| Bereit | grün einmal rundherum füllen, danach wieder der letzte Modus von HA | ~1,5 s, sobald HA verbunden ist (nach Boot und nach Wiederverbindung) |
| Setup-WLAN aktiv | blau, langsam atmend | dauerhaft, solange der AP „Lumibox Setup“ offen ist und noch keine WLAN-Daten gespeichert sind |
| Firmware-Update | cyan Füllstand = Fortschritt | dauerhaft während des Updates |
| Kein WLAN | rot, 2× langsam pulsieren | ~4 s |
| WLAN ja, HA nein | orange, 2× langsam pulsieren | ~4 s |
| NFC-Leser defekt | magenta, 2× langsam pulsieren | ~4 s |

- **Fehler zeigen:** Nach dem Start (wenn die Startphase ohne HA-Verbindung endet) und bei jeder Bedienung (Figur, Taster, Encoder), solange die Box nicht mit HA verbunden ist (kein WLAN bzw. WLAN ohne HA). Danach stellt die Box den letzten Modus von HA wieder her (z. B. den Spinner); „aus“ nur, wenn der letzte Modus `off` war. Ein Verbindungsverlust im Betrieb wird nicht von selbst angezeigt (kein dauerhaftes Fehlerleuchten): Die LED bleibt, wie sie war, erst bei der nächsten Bedienung erscheint der Fehler.
- **Setup-WLAN vs. Kein WLAN:** Blau atmend gibt es nur, wenn die Box noch keine WLAN-Daten gespeichert hat. Ist das bekannte WLAN weg (der Fallback-AP ist offen), gilt das als Fehler „Kein WLAN“.
- **NFC-Leser defekt** (magenta) zeigt die Box nach jedem „Bereit“ (nach dem Start und nach jeder Wiederverbindung), nach dem Start-Timeout und bei einer Bedienung, solange HA nicht verbunden ist (nach Rot bzw. Orange). Bei einer Bedienung mit bestehender HA-Verbindung nicht.
- **Fehler-Priorität:** Kein WLAN vor „WLAN ja, HA nein“.
- **Vorrang:** Lokale Anzeigen (Start, Setup, Update, Fehler) haben Vorrang vor `set_led`. Währenddessen werden nur die Dauer-Modi (`off`, `loading`, `playing`, `hold`) gemerkt und danach wiederhergestellt; kurze Anzeigen (`volume`, `unknown`, `error`, `paused`) werden verworfen (`paused`, `unknown` und `error` setzen den Dauer-Modus auf `off`).

## Integration (`custom_components/lumibox`)

### Datenmodell

**Subentry `box`:** `name`, `esphome_device_id`, `player_entity_id` (Music-Assistant-Player), `ma_username` (MA-Benutzer des Kindes; dessen Anbieterfilter erlaubt nur den Spotify-Account dieses Kindes), `max_volume` (Default 40 %), `volume_step` (Default 3 %), `default_color` (Default Lila `[128, 0, 255]`).

**Subentry `figure`:** `name`, `uid` (normalisiert: Grossbuchstaben ohne Trennzeichen), `media_uri` (normalisiert als `spotify:{typ}:{id}`), optional `color`.

### Module

| Modul | Aufgabe |
| :--- | :--- |
| `__init__.py` | Setup/Unload, hört auf `esphome.lumibox` und verteilt per `device_id` an den `BoxController` |
| `config_flow.py` | Haupteintrag sowie Box- und Figur-Subentries (mit Bearbeiten) |
| `library.py` | Figurenbibliothek, Normalisierung von UID und Spotify-Link |
| `box.py` | `BoxController` pro Box: Zustandsautomat (siehe unten) |
| `player.py` | Wiedergabe über Music Assistant und `media_player.*` |
| `led.py` | Ruft `esphome.<gerät>_set_led` auf |
| `sensor.py` | Pro Box: aktuelle Figur, letzter unbekannter Tag |
| `binary_sensor.py` | Pro Box: Sensor „Verbunden“ (Klasse Konnektivität) |
| `connection.py` | `BoxConnection`: leitet aus den ESPHome-Entitäten der Box ab, ob das Gerät verbunden ist (die Dashboard-Update-Entität zählt nicht, Hilfsfunktion `is_device_entity`) |
| `firmware.py` | Prüft die Firmware-Version jeder Box gegen `MIN_FIRMWARE_VERSION` und erstellt bzw. entfernt den Reparatur-Hinweis |
| `repairs.py` | Knopf „Jetzt aktualisieren“: startet `update.install` auf der Update-Entität der Box |

### Sensor „Verbunden“

Pro Box gibt es einen Binary-Sensor „Verbunden“. Er ist an, solange das ESPHome-Gerät der Box erreichbar ist. Ist die Box nicht verbunden, sind ihre Lumibox-Sensoren „nicht verfügbar“. Ohne aufgelegte Figur zeigt „Aktuelle Figur“ den Zustand `none` (angezeigt als „Keine“).

### Verhalten pro Box

- **Figur auflegen:**
  - Bekannte Figur: LED `loading`, Lautstärke auf höchstens `max_volume`, `music_assistant.play_media` mit `username` der Box, danach LED `playing` in der Figurfarbe.
  - Unbekannte Figur: Sensor „letzter unbekannter Tag“, Benachrichtigung mit UID, LED `unknown`.
- **Figur abnehmen:** 1 s Entprellung, dann Pause. Die Box merkt sich den laufenden Titel und den Zeitpunkt.
- **Dieselbe Figur innerhalb von 30 Minuten wieder auflegen:** weiter ab dem gemerkten Titel (`start_item`). Scheitert das, einmal von vorn. `media_player.media_play` wird bewusst nicht verwendet, weil es mit Music Assistant nach einer Pause nicht zuverlässig weiterspielt.
- **Encoder:** Lautstärke in Schritten von `volume_step`, nie über `max_volume`. Die LED zeigt den Pegel relativ zum Maximum.
- **Taster:** Play/Pause (LED `hold`), vorheriger/nächster Titel. Ohne Figur werden Taster und Encoder ignoriert.
- **Fehler** (Player nicht verfügbar, Service-Fehler): LED `error`, Warnung im Log.

## Versionen und Updates

- **Eine Versionsnummer** für Integration (`manifest.json`) und Firmware (`substitutions.version`). Setzen mit `scripts/bump-version.sh X.Y.Z`, prüfen mit `scripts/check-version.sh [vX.Y.Z]`.
- **Release:** Ein Tag `vX.Y.Z` startet `.github/workflows/release.yml`:
  1. Tests laufen lassen und Versionen prüfen; bei einem Fehler Abbruch, bevor etwas veröffentlicht wird.
  2. Firmware bauen.
  3. GitHub-Release mit den `.bin`-Dateien erstellen (davon installiert der Marketplace die Integration).
  4. Erst danach Manifest und OTA-Datei auf GitHub Pages veröffentlichen (`scripts/make-ota-manifest.py`).
- **Kompatibilität:**
  - Die Integration bleibt mit jeder Firmware derselben Major-Version kompatibel.
  - `MIN_FIRMWARE_VERSION` wird nur angehoben, wenn es nötig ist.
  - Ist eine Box zu alt, erscheint ein Reparatur-Hinweis. Er verschwindet, sobald HA die neue Version in den Geräteinfos sieht.
- **Welche Update-Entität:** Der Reparatur-Knopf nimmt nur die eigene Update-Entität der Box, erkennbar an einer unique_id mit `-` oder `/`. Die Entität des ESPHome-Dashboards (unique_id = reine MAC) wird übersprungen.
