# Home Tonie – Design-Spezifikation (v1)

Stand: 2026-11-13 · Status: Entwurf zur Review

## 1. Ziel und Kontext

Eine physische Audio-Box für **Kleinkinder (ca. 2–5 Jahre)**: Figur mit NFC-Tag auflegen → Musik/Hörspiel läuft auf dem Lautsprecher im Kinderzimmer; Figur abnehmen → Pause. Keine Einstellungen am Gerät, robust und verzeihend.

### Rahmenbedingungen (vom Nutzer festgelegt)

- **Mehrere Boxen** (aktuell 2 Kinder), jede mit eigenem Lautsprecher.
- **Inhalte:** Spotify. **Lautsprecher:** Sonos und/oder HomePod mini.
- **Spotify erlaubt pro Account nur eine Wiedergabe gleichzeitig** (vom Nutzer bestätigt). Gleichzeitig spielende Boxen brauchen deshalb **je einen eigenen Spotify-Premium-Account** (z. B. Premium Family). Jede Box ist fest einem Account zugeordnet.
- **Home Assistant OS** vorhanden; **Music Assistant** darf/soll verwendet werden.
- **Figurenverwaltung** komfortabel in Home Assistant, inkl. Anlernen unbekannter Figuren.
- Box hängt **permanent am Strom**; ohne Figur ist der LED-Ring **aus**.
- Hardware: ESP32-WROOM-32D, PN532 V3 (SPI), WS2812B-Ring (24 LEDs), KY-040-Encoder, 2 Arcade-Buttons, NTAG215-Tags (siehe README).

### Erfolgskriterien

1. Bekannte Figur auflegen → Wiedergabe startet innerhalb von ~3 s auf dem Lautsprecher der Box, auf der sie liegt.
2. Figur abnehmen → Wiedergabe pausiert; dieselbe Figur wieder auflegen → nahtlos weiter.
3. Neue Figur kann ohne Code/YAML-Änderung und ohne Neu-Flashen über die HA-Oberfläche angelernt werden.
4. Lautstärke kann über die Box nie über das konfigurierte Box-Maximum gehen.
5. Zwei Boxen arbeiten gleichzeitig und unabhängig.

### Bewusst nicht in v1 (YAGNI)

- Fortsetzen an gespeicherter Position über Sessions hinweg (nur Datenfeld `mode` vorbereitet).
- Eigenes Sidebar-Panel, Figurenbilder, Spotify-Suche im Formular.
- Figuren, die nur auf bestimmten Boxen spielen.
- Andere Quellen als Spotify (technisch über Music Assistant meist trotzdem möglich, aber nicht getestet).

## 2. Architektur

```
┌──────────── Box (ESPHome, ESP32) – je Kinderzimmer eine ─────┐
│ PN532   ─► Event esphome.home_tonie {action: tag_on/off, uid}│
│ Encoder ─► Event esphome.home_tonie {action: rotate_cw/ccw}  │
│ Buttons ─► Event esphome.home_tonie {action: play_pause/...} │
│ LED-Ring ◄─ API-Action set_led(mode, level)                  │
└──────────────────────────────┬───────────────────────────────┘
                               │ ESPHome Native API
┌──────────────────────────────▼──────────── Home Assistant ───┐
│ Custom Integration "home_tonie"                              │
│   Haupteintrag                                               │
│   ├── Subentry-Typ "box"    (ESPHome-Gerät, Player, max Vol) │
│   └── Subentry-Typ "figure" (Name, UID, Spotify-URI, Modus)  │
└──────────────────────────────┬───────────────────────────────┘
                               │ music_assistant.play_media / media_player.*
                       Music Assistant (Spotify-Provider)
                               │
                 Sonos / HomePod mini (AirPlay-Provider)
```

**Grundprinzip:** Die Box ist „dumm“. Sie meldet nur Ereignisse und zeigt LED-Zustände an. Sämtliche Logik und alle Figurendaten liegen in der Integration. Neue Figuren oder Verhaltensänderungen erfordern **kein** Neu-Flashen.

**Figuren sind eine gemeinsame Bibliothek:** Jede Figur spielt auf jeder Box, immer auf dem Lautsprecher der Box, auf der sie liegt.

## 3. Repo-Struktur

```
esphome/
  home-tonie-common.yaml     # gesamte Box-Logik (Package)
  home-tonie-anna.yaml       # nur substitutions + packages: common
  home-tonie-ben.yaml        # dito
  secrets.yaml               # nicht eingecheckt
custom_components/home_tonie/
  __init__.py  manifest.json  const.py
  config_flow.py  library.py  box.py  player.py  led.py  sensor.py
  strings.json  translations/de.json  translations/en.json
tests/
  conftest.py  test_box.py  test_library.py  test_config_flow.py
hacs.json
README.md
```

Der bisherige Ordner `automations/` entfällt.
Die Boxnamen `anna`/`ben` sind Platzhalter.

## 4. Firmware (ESPHome)

### 4.1 Gemeinsames Package `home-tonie-common.yaml`

Enthält alles aus der heutigen `home-tonie.yaml`, mit folgenden Änderungen. Pro Box gibt es nur eine kleine Datei:

```yaml
substitutions:
  device_name: home-tonie-anna
  friendly_name: Home Tonie Anna
packages:
  common: !include home-tonie-common.yaml
```

### 4.2 Events an Home Assistant

**Ein** Event-Typ `esphome.home_tonie` mit dem Feld `action`. ESPHome/HA ergänzt automatisch `device_id`, darüber ordnet die Integration das Event einer Box zu.

| Auslöser | `action` | weitere Daten |
| :--- | :--- | :--- |
| PN532 `on_tag` | `tag_on` | `uid` |
| PN532 `on_tag_removed` | `tag_off` | `uid` |
| Encoder im Uhrzeigersinn | `rotate_cw` | – |
| Encoder gegen Uhrzeigersinn | `rotate_ccw` | – |
| Encoder-Taster | `play_pause` | – |
| Button GPIO26 | `prev` | – |
| Button GPIO27 | `next` | – |

- Encoder: `sensor: rotary_encoder` mit `on_clockwise` / `on_anticlockwise`, `internal: true`.
- Taster: `binary_sensor: gpio` mit `on_press`, `internal: true`, Entprellung wie bisher (15 ms).
- `pn532_spi.update_interval`: 250 ms (wie heute).

### 4.3 LED-Steuerung über API-Action

Die Box definiert unter `api: actions:` eine Action `set_led` mit den Variablen `mode: string` und `level: int`. In HA heisst sie `esphome.<node_name>_set_led`, z. B. `esphome.home_tonie_anna_set_led`. Die Effekte und Zeitabläufe stecken in der Firmware, damit HA keine Timer für die LEDs braucht.

| `mode` | Darstellung | Dauer |
| :--- | :--- | :--- |
| `off` | aus | dauerhaft |
| `loading` | Lade-Spinner (weiss) | bis zum nächsten Modus |
| `playing` | sanftes Pulsieren (warmweiss, gedimmt) | dauerhaft |
| `hold` | statisch warmweiss, 10 % Helligkeit (Figur liegt, per Taster pausiert) | dauerhaft |
| `paused` | kurz ausblenden, dann `off` | ~1,5 s |
| `unknown` | 3× rot blinken, dann `off` | ~2 s |
| `error` | rot, dann `off` | ~3 s |
| `volume` | `level` (0–100) als Füllstand auf 24 LEDs, danach zurück zum vorherigen Modus | ~1,5 s |

- Die Licht-Entität wird `internal: true`, da sie ausschliesslich über `set_led` gesteuert wird.
- Bestehende Effekte (Regenbogen, Funkeln …) dürfen in der Firmware bleiben, werden aber nicht genutzt.
- Ohne Figur ist der Ring aus. Nach `paused`, `unknown` und `error` landet er immer bei `off`.
- **Helligkeitsobergrenze:** `color_correct: [50%, 50%, 50%]` am `esp32_rmt_led_strip`.
  - Grund: 24 LEDs ziehen bei vollem Weiss bis ~1,44 A. Das ist zu viel für den 5V-Pfad über USB des ESP32-Boards und im Kinderzimmer zu grell.
  - Mit der Kappung liegt der schlimmste Fall bei ~0,7 A, der Normalbetrieb deutlich unter 200 mA.
  - Die Grenze gilt für alle Effekte und lässt sich auch von HA nicht überschreiten.
  - Hardware-Schutzbeschaltung siehe README.

### 4.4 Voraussetzung in HA

„Allow the device to perform Home Assistant actions“ ist für das Senden von Events **nicht** nötig (verifiziert, Abschnitt 10 Punkt 1). Die Option betrifft nur Aktionen, die die Box in HA auslöst. Die Aktion `esphome.<node>_set_led` (HA → Box) braucht sie ebenfalls nicht. Die Firmware darf in Event-Daten kein Feld `device_id` senden.

## 5. Integration `home_tonie`

### 5.1 Datenmodell (Config Entries)

**Haupteintrag** (genau einer, `single_config_entry: true`): keine Felder.

**Subentry `box`**
| Feld | Typ | Beschreibung |
| :--- | :--- | :--- |
| `name` | str | z. B. „Anna“ (Default: Gerätename) |
| `esphome_device_id` | Device-Selector (Integration `esphome`) | die Box |
| `player_entity_id` | Entity-Selector (`media_player`, Integration `music_assistant`) | Ziel-Lautsprecher |
| `ma_username` | str | Music-Assistant-Benutzer des Kindes (z. B. `anna`). Sein Anbieterfilter erlaubt nur den Spotify-Account dieses Kindes. |
| `max_volume` | int 5–100 %, Default 40 | Obergrenze für Aktionen der Box |
| `volume_step` | int 1–10 %, Default 3 | Schrittweite pro Encoder-Raste |

Ein ESPHome-Gerät darf nur einer Box zugeordnet sein (Validierung im Flow). Zwei Boxen mit demselben `ma_username` erzeugen eine **Warnung** im Formular („Diese Boxen können nicht gleichzeitig spielen“), werden aber nicht blockiert.

**Subentry `figure`**
| Feld | Typ | Beschreibung |
| :--- | :--- | :--- |
| `name` | str | z. B. „Bobo Siebenschläfer“ |
| `uid` | str | normalisiert, siehe 5.3; eindeutig über alle Figuren |
| `media_uri` | str | Spotify-URI, normalisiert, siehe 5.3 |
| `mode` | select | v1 nur `restart` (Vorbereitung für `resume`) |

### 5.2 Config Flow

- **Haupteintrag anlegen:** Bestätigungsdialog. Danach erscheinen „Box hinzufügen“ und „Figur hinzufügen“.
- **Box hinzufügen/bearbeiten:** Formular mit den Feldern aus 5.1 (Reconfigure-Unterstützung).
- **Figur hinzufügen/bearbeiten:**
  - Das Feld `uid` ist mit dem Wert des Sensors „letzter unbekannter Tag“ der zuletzt meldenden Box vorbelegt, falls vorhanden.
  - Fehlermeldungen bei doppelter UID oder ungültigem Spotify-Link.

### 5.3 Normalisierung

- **UID:** Grossbuchstaben, Trennzeichen entfernt (`04-a1-b2-c3` → `04A1B2C3`). Gilt beim Speichern und beim Nachschlagen.
- **Spotify:** Akzeptiert werden
  - `https://open.spotify.com/{album|playlist|track|artist|show|episode|audiobook}/<id>[?…]`, auch mit `intl-xx/`-Präfix;
  - `spotify:{typ}:<id>`.

  Gespeichert wird immer `spotify:{typ}:<id>`.

### 5.4 Module

| Modul | Verantwortung | Abhängigkeiten |
| :--- | :--- | :--- |
| `const.py` | Domain, Event-Name, Defaults | – |
| `library.py` | Figurenbibliothek: `lookup(uid) -> Figure \| None`, Normalisierung von UID und URI (reine Funktionen) | Config Entry |
| `player.py` | `PlayerAdapter`: `play(uri)`, `resume()`, `pause()`, `next()`, `prev()`, `get_volume()`, `set_volume(v)`, `snapshot()` (aktueller `media_content_id` + Zustand) | `hass.services`, `hass.states` |
| `led.py` | `LedAdapter`: `show(mode, level=0)` → ruft `esphome.<node>_set_led` auf; ermittelt `<node>` aus dem Device Registry | `hass.services` |
| `box.py` | `BoxController` pro Box: Zustandsautomat aus Abschnitt 6 | Library, Player-/LedAdapter (injiziert) |
| `sensor.py` | Pro Box: `sensor.<box>_aktuelle_figur`, `sensor.<box>_letzter_unbekannter_tag` | BoxController (Listener) |
| `__init__.py` | Setup/Unload, abonniert `esphome.home_tonie`, verteilt per `device_id` an den richtigen `BoxController`. Bei Änderungen an Figuren wird nur die Bibliothek aktualisiert (kein Reload, laufende Wiedergabe bleibt unberührt); bei Änderungen an Boxen wird neu geladen | alle |

`BoxController` hängt nur von den Adaptern ab. So lässt er sich ohne echte Lautsprecher testen.

### 5.5 Wiedergabe

- **Start:** `music_assistant.play_media` mit
  - `entity_id = player`,
  - `media_id = spotify://{typ}/{id}`: das Format laut Music-Assistant-Doku, erzeugt aus der gespeicherten `spotify:{typ}:{id}`,
  - `media_type = {typ}` explizit, also kein Raten durch Music Assistant,
  - `enqueue = replace`,
  - **`username = ma_username` der Box**.

  Music Assistant wählt über die Anbieterfilter dieses Benutzers den richtigen Spotify-Account. Die Figur bleibt neutral und spielt auf jeder Box über den Account des jeweiligen Kindes. Nebeneffekt: Jedes Kind hat ein eigenes Wiedergabeprotokoll in Music Assistant.
- **Später (Fortsetzen):** `play_media` kennt `start_item` (Start bei einem bestimmten Titel bzw. einer bestimmten Folge). Das ist die Grundlage für `mode = resume`.
- **Weiterspielen:** `media_player.media_play`.
- **Pause:** `media_player.media_pause`.
- **Titel:** `media_player.media_next_track` / `media_previous_track`.
- **Lautstärke:** `media_player.volume_set` mit einem berechneten Wert. Kein `volume_up`, denn dessen Schrittweite hängt vom Gerät ab.

## 6. Verhalten (pro Box)

### 6.1 Zustände

`idle` (keine Figur) · `loading` · `playing` · `paused_by_box` (Figur liegt, per Taster pausiert) · `removed` (Figur abgenommen, Pause durch Box)

Gemerkt pro Box: `current_figure`, `last_figure`, `snapshot_at_removal` (`media_content_id` des Players beim Abnehmen).

### 6.2 Ereignisse

**`tag_on(uid)`**
1. Läuft eine Entprell-Wartezeit für dieselbe UID (siehe `tag_off`), wird sie abgebrochen. Es passiert nichts weiter, da die Figur nie wirklich weg war.
2. Für eine unbekannte UID:
   - `sensor.letzter_unbekannter_tag = uid`;
   - persistente Benachrichtigung „Neue Figur auf Box {name} erkannt (UID {uid}). Unter Einstellungen → Home Tonie → Figur hinzufügen anlegen, die UID ist vorausgefüllt.“;
   - LED `unknown`. Ende.
3. Für eine bekannte Figur F wird `current_figure = F` gesetzt und der Sensor aktualisiert.
4. **Weiterspielen** statt Neustart, wenn alle drei Bedingungen gelten:
   - `F == last_figure`,
   - der Player ist `paused`,
   - sein `media_content_id` entspricht `snapshot_at_removal`.

   Dann: Lautstärke begrenzen, `resume()`, LED `playing`.
5. **Sonst:** LED `loading`, Lautstärke auf höchstens `max_volume` setzen, `play(F.media_uri)`, danach LED `playing`.
6. Schlägt der Service-Aufruf fehl oder ist der Player `unavailable`: LED `error`, Log-Warnung, Zustand `idle`.

**`tag_off(uid)`**
1. Die Integration startet eine **Entprellung von 1,0 s**, weil der PN532 kurze Aussetzer melden kann. Kommt in dieser Zeit `tag_on` mit derselben UID, wird alles ignoriert.
2. Nach Ablauf:
   - `pause()` und `snapshot_at_removal` merken;
   - `last_figure = current_figure`, danach `current_figure = None`;
   - LED `paused`, was automatisch zu `off` führt.
3. Ist die UID unbekannt oder lief nichts, wird nur LED `off` gesetzt.

**`play_pause`** (nur wenn eine Figur liegt): In `playing` folgt `pause()`, LED `hold` und Zustand `paused_by_box`. In `paused_by_box` folgt `resume()` (mit Lautstärke-Begrenzung), LED `playing` und Zustand `playing`. Die LED bleibt bei liegender Figur also nie ganz dunkel.

**`next` / `prev`** (nur wenn eine Figur liegt): `next()` / `prev()`.

**`rotate_cw` / `rotate_ccw`** (nur wenn eine Figur liegt):
- Neuer Wert: `v = clamp(aktuell ± volume_step, 0, max_volume)`.
- Dann `set_volume(v)` und LED `volume` mit `level = round(v / max_volume * 100)`. Der Füllstand bezieht sich also auf das Box-Maximum, damit das Kind den vollen Ring sieht.

Liegt keine Figur auf, werden Taster und Encoder ignoriert.

### 6.3 Lautstärke-Grenze

- Wird bei jedem Start bzw. Weiterspielen und bei jeder Encoder-Aktion erzwungen.
- Änderungen von ausserhalb (z. B. Eltern in der Sonos-App) werden in v1 **nicht** zurückgeregelt.

## 7. Fehlerbehandlung

| Situation | Reaktion |
| :--- | :--- |
| Lautsprecher `unavailable` / Service-Fehler | LED `error`, `_LOGGER.warning`, Zustand `idle` |
| Event von unbekanntem `device_id` | ignorieren, Debug-Log |
| Box offline | nichts. Beim nächsten Event läuft alles normal |
| Music Assistant nicht installiert | Box-Formular zeigt Fehler „Kein Music-Assistant-Player gefunden“ |
| `set_led`-Action fehlt (alte Firmware) | einmalige Warnung im Log, Wiedergabe funktioniert trotzdem |
| Doppelte UID im Formular | Formularfehler, Speichern blockiert |

## 8. Tests

- **Framework:** `pytest` + `pytest-homeassistant-custom-component`.
- **`test_library.py`:** UID-Normalisierung, Spotify-Link-Varianten (Album, Playlist, Hörbuch, `intl-de`, Query-Parameter, ungültige Links), Lookup.
- **`test_box.py`** mit Fake-`PlayerAdapter` und Fake-`LedAdapter`, ohne echte Geräte:
  - bekannte Figur → `play` + Lautstärke begrenzt + LED `loading` → `playing`;
  - Abnehmen → nach 1 s `pause`, LED `paused`;
  - Abnehmen + Auflegen innerhalb 1 s → keine Aktion;
  - gleiche Figur wieder → `resume` statt `play`;
  - gleiche Figur, aber Player spielt inzwischen etwas anderes → `play`;
  - andere Figur → `play`;
  - unbekannte Figur → Sensor, Benachrichtigung, LED `unknown`, kein `play`;
  - Encoder → Lautstärke nie > `max_volume`, nie < 0;
  - Taster ohne Figur → keine Aktion;
  - Player-Fehler → LED `error`.
- **`test_config_flow.py`:** Haupteintrag, Box- und Figur-Subentry, Validierungsfehler, UID-Vorbelegung.
- **Integration (`__init__`):** Event mit `device_id` erreicht die richtige Box; zwei Boxen beeinflussen sich nicht.
- **Firmware:** `esphome config` für beide Box-Dateien muss fehlerfrei durchlaufen. Funktionstest manuell am Gerät (Checkliste im README).

## 9. Voraussetzungen und Inbetriebnahme

1. In Music Assistant **pro Box einen Spotify-Provider** mit je eigenem Premium-Account einrichten (z. B. die Konten eines Family-Abos). Dazu je nach Lautsprecher den **Sonos-** bzw. **AirPlay-Provider** einrichten.
2. In Music Assistant **pro Kind einen Benutzer** anlegen (z. B. `anna`, `ben`). Dessen Anbieterfilter erlaubt nur den eigenen Spotify-Account.
3. Box flashen (`home-tonie-<kind>.yaml`). In HA die Box zur ESPHome-Integration hinzufügen. „HA-Actions erlauben“ ist nicht nötig.
4. `custom_components/home_tonie` installieren (HACS als benutzerdefiniertes Repository oder manuell kopieren) und HA neu starten.
5. „Home Tonie“ hinzufügen → Box hinzufügen → Figuren durch Auflegen anlernen.

Mindestversion HA: **2025.4.0** (verifiziert, Abschnitt 10 Punkt 4). Sie wird in `hacs.json` eingetragen.

## 10. Offene Punkte / bei Umsetzung zu verifizieren

Stand der Recherche: 2026-11-13, gegen HA-Core `dev` (2026.12) und die Music-Assistant-Quellen (`music-assistant/server`, `music-assistant/models`). Alle Punkte ausser dem manuellen Test sind aus Primärquellen **belegt**, sofern nicht „vermutet“ steht. Details: `.superpowers/sdd/2026-11-13-home-tonie-integration/task-0-report.md`.

1. **ESPHome-Event enthält `device_id`** – ✅ verifiziert.
   - `async_on_service_call` in `esphome/manager.py` feuert bei `service.is_event` per `hass.bus.async_fire("esphome.<name>", {ATTR_DEVICE_ID: device_id, **service_data})`. `device_id` ist `entry_data.main_device_entry_id` (Geräte-Registry-ID der Box; Typ `str | None`).
   - „HA-Actions erlauben“ (`allow_service_calls`) ist für Events **nicht** nötig: Die Option gated nur den `elif`-Zweig für echte Service-Aufrufe (nicht `is_event`). Die Option ist für `esphome.<node>_set_led` (HA → Gerät) nicht relevant, weil das ein von HA registrierter Dienst ist. In Abschnitt 9 Punkt 3 kann „HA-Actions erlauben“ entfallen. Es schadet aber nicht.
   - **Firmware darf kein Feld `device_id` in den Event-Daten senden** (Tasks 8/9): Der Code baut `{ATTR_DEVICE_ID: device_id, **service_data}`, ein Gerätefeld gleichen Namens würde die echte ID überschreiben. Die Feldnamen der Firmware (z. B. `tag_uid`) so wählen, dass sie nicht kollidieren.
   - Einschränkung: Event-Name muss `esphome.*` lauten. Daten aus dem Gerät kommen als Strings/Zahlen in `event.data`.
   - Quelle: https://github.com/home-assistant/core/blob/dev/homeassistant/components/esphome/manager.py (Zeilen ~327–375)
   - Der `box`-Fallback ist nicht nötig, wird aber als Reserve behalten (`main_device_entry_id` kann `None` sein; dann Event ignorieren und loggen).
2. **ESPHome-Knotenname** – ✅ verifiziert. Der ESPHome-Config-Entry hat `entry.data["device_name"]` (`CONF_DEVICE_NAME = "device_name"`, Bindestriche wie in der YAML). Der Dienstname lautet `esphome.<device_name mit "-" → "_">_<service>`, also `esphome.home_tonie_anna_set_led` für `home-tonie-anna` (`esphome/manager.py` Zeile 1659–1661, `build_service_name`: `return f"{device_info.name.replace('-', '_')}_{service.name}"`; Stand dev, Zeilennummer kann driften). Weg: `device_registry.async_get(device_id)` → `config_entries` → Entry mit `domain == "esphome"` → `entry.data["device_name"]`. Quellen: `esphome/const.py`, `esphome/manager.py` (dev).
3. **Music Assistant `media_type`/URI** – ✅ verifiziert, mit **Korrektur**.
   - Schema von `music_assistant.play_media`: `media_id` (Liste), `media_type` optional (`Coerce(MediaType)`), `enqueue` (`play|replace|next|replace_next|add`), `radio_mode`, `shuffle`, `start_item`, `username`. Quelle: `homeassistant/components/music_assistant/services.py` (dev).
   - `MediaType`-Werte (music_assistant_models): `artist, album, track, playlist, radio, audiobook, podcast, podcast_episode, folder, …`. Unbekannte Strings werden still zu `unknown`, es gibt keinen Fehler. Die UI-Auswahl in `services.yaml` listet `podcast_episode` nicht, der Wert ist aber gültig.
   - **Die URI trägt den Typ**: MA-Form `<provider>://<media_type>/<item_id>`, z. B. `spotify://album/<id>`, `spotify://podcast/<id>`, `spotify://podcast_episode/<id>`, `spotify://audiobook/<id>`. Mit vollständiger URI wird `media_type` nicht gebraucht (nur für numerische Bibliotheks-IDs/Namenssuche). Spotify-IDs müssen 22 Zeichen Base62 sein. Quelle: `music_assistant/helpers/uri.py` (`parse_uri`, `valid_id`).
   - **Achtung:** Native Spotify-URIs/Links mit `show`/`episode` (`spotify:show:<id>`, `open.spotify.com/show/<id>`) werden **nicht** korrekt aufgelöst (`MediaType("show")` → `unknown`). Die Integration muss `show→podcast`, `episode→podcast_episode` in die URI schreiben.
   - Mapping bestätigt: `album→album`, `playlist→playlist`, `track→track`, `artist→artist`, `audiobook→audiobook`, `show→podcast`, `episode→podcast_episode`.
   - **Konsequenz Task 2:** URI als `spotify://<mapped_type>/<id>` bauen; `media_type` zusätzlich mitgeben ist harmlos, aber optional. Für den Provider-Instanz-Fallback ist `<instance_id>://<type>/<id>` zulässig. Hörbücher funktionieren nur, wenn der Account/die Region sie unterstützt (`audiobooks_supported` im Spotify-Provider).
4. **Config-Subentries** – ✅ verifiziert (HA-Core dev, `config_entries.py`).
   - Namen unverändert gültig: `ConfigFlow.async_get_supported_subentry_types(config_entry) -> dict[str, type[ConfigSubentryFlow]]`, `ConfigSubentryFlow` mit `async_step_reconfigure`, `self._get_reconfigure_subentry()`, `self._get_entry()`, `self.async_update_and_abort(entry, subentry, data=… | data_updates=…, title=…, unique_id=…, reason=…)`, `self.async_create_entry(title, data, unique_id=…)`. `async_add_entities(entities, config_subentry_id=…)` existiert (`helpers/entity_platform.py`).
   - **Erste Version mit Subentry-Reconfigure: 2025.3.** (`2025.2.0` hat noch kein `ConfigSubentryFlow`.) In 2025.3 hiess die Methode auf dem Subentry-Flow noch `_get_reconfigure_entry()`; sie wurde in **2025.4** (PR #141017, 2025-03-24) zu `_get_entry()` umbenannt. Der Name `_get_entry()` ist deshalb erst ab 2025.4 vorhanden.
   - **Mindestversion HA: 2025.4.0** (Task 10: `hacs.json` `"homeassistant": "2025.4.0"`, ggf. in `manifest.json`-Hinweis). Task 7: `_get_reconfigure_subentry()` für das bearbeitete Subentry und `_get_entry()` für den übergeordneten `ConfigEntry` verwenden. `_get_reconfigure_subentry()` existiert schon in 2025.3.0 (und 3.4) und in 2025.4.0 (geprüft per Tag-Vergleich von `config_entries.py`); entscheidend für 2025.4 ist `_get_entry()`: In 2025.3.x heisst es im Subentry-Flow `_get_reconfigure_entry()`, ab 2025.4.0 ist es `_get_entry()`.
   - Doku-Hinweis: Die Entwicklerdoku (contributors.home-assistant.io/core/integrations/config-flow/) beschreibt Subentry-Reconfigure nicht ausführlich; die Quelle ist der Core-Code.
   - Test-Tooling: `pytest-homeassistant-custom-component` 0.13.375 (2026-10-25, PyPI), pinnt `homeassistant==2026.10.4`, `requires_python >=3.14`. Die Test-Umgebung (Task 1/CI) braucht deshalb Python 3.14. Tests laufen gegen 2026.10.4, nicht gegen die Mindestversion.
5. **Spotify-Anbieterfilter/`username`-Spike** – offen – manueller Test durch Nutzer.
   - Zwei Music-Assistant-Benutzer mit je eigenem Spotify-Anbieterfilter spielen per `play_media … username:` **gleichzeitig** verschiedene Inhalte auf zwei Lautsprechern, auch über Titelwechsel hinweg.
   - Gegenprobe ohne `username`: Hier wird ein Abbruch erwartet.
   - Beleg aus dem Code (nicht der Test): `username` wirkt als Impersonation des MA-Benutzers (`user`), ohne `username` wird der HA-Benutzer des Aufrufs genommen (`media_player.py`, `_async_handle_play_media`); ein unbekannter Name führt zu einem Fehler.
   - **Fallback**, falls die Anbieterfilter die Account-Wahl nicht steuern: Die Box bekommt die Provider-Instanz-ID, und die `media_id` wird instanzspezifisch gebildet (`<instance_id>://<type>/<id>`).
6. **`media_content_id` beim Pausieren stabil** – offen – manueller Test durch Nutzer (Teil des Tests aus Punkt 5). **Fallback:** Die Regel nur auf `F == last_figure` und Player `paused` stützen.
7. **HomePod mini über AirPlay bei `enqueue = replace` und Titelsprung** – offen – manueller Test durch Nutzer.
