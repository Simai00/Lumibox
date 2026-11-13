# Home Tonie Integration – Umsetzungsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:**
- Eine HA-Custom-Integration `home_tonie` verwaltet Boxen und Figuren.
- Sie spielt beim Auflegen einer Figur deren Spotify-Inhalt über Music Assistant auf dem Lautsprecher der Box ab.
- Die ESPHome-Firmware liefert dazu Events und LED-Anzeige.

**Architecture:**
- Die Box (ESPHome) sendet nur Events `esphome.home_tonie` und stellt die API-Action `set_led` bereit.
- Die Integration hält Figuren und Boxen als Config-Subentries.
- Pro Box gibt es einen `BoxController` (Zustandsautomat). Er spricht über `PlayerAdapter` (Music Assistant/`media_player`) und `LedAdapter` (ESPHome-Action) mit der Aussenwelt.
- Figurenänderungen werden ohne Reload in die gemeinsame `FigureLibrary` übernommen.

**Tech Stack:**
- Python (Version gemäss aktueller `pytest-homeassistant-custom-component`), Home Assistant Config Subentries, pytest + `pytest-homeassistant-custom-component`.
- ESPHome (Arduino-Framework, `pn532_spi`, `rotary_encoder`, `esp32_rmt_led_strip`).
- Docker für Tests und `esphome config`.

**Spec:** `docs/superpowers/specs/2026-11-13-home-tonie-integration-design.md`

## Global Constraints

- Domain `home_tonie`; Event-Typ `esphome.home_tonie` mit Feld `action` ∈ {`tag_on`, `tag_off`, `rotate_cw`, `rotate_ccw`, `play_pause`, `prev`, `next`}, bei Tags zusätzlich `uid`.
- Genau ein Haupteintrag (`single_config_entry: true`); Subentry-Typen `box` und `figure`.
- Box-Defaults: `max_volume` = 40 (Bereich 5–100 %), `volume_step` = 3 (Bereich 1–10 %).
- Figur-`mode`: v1 nur `restart`.
- UID-Normalisierung: Grossbuchstaben, alle Nicht-Hex-Zeichen entfernt (`04-a1-b2-c3` → `04A1B2C3`).
- Gespeicherte Medien-URI: immer `spotify:{typ}:{id}`. Abspielen über `music_assistant.play_media` mit `media_id = spotify://{typ}/{id}`, explizitem `media_type`, `enqueue = replace` und `username = ma_username` der Box.
- Entprellung beim Abnehmen: **1,0 s**.
- LED-Modi (`set_led`): `off`, `loading`, `playing`, `hold`, `paused`, `unknown`, `error`, `volume` (+ `level` 0–100).
- LED-Helligkeit hart begrenzt mit `color_correct: [50%, 50%, 50%]`.
- Lautstärke nur per `media_player.volume_set`, nie über `max_volume` der Box; Encoder ohne aufgelegte Figur wirkungslos.
- Ohne aufgelegte Figur ist der LED-Ring aus.
- Übersetzungen: `de` und `en`.
- Kein blockierendes I/O im Event-Loop.
- `esphome/secrets.yaml` wird nie gelesen, ausgegeben oder committet.
- Umgebung: Windows mit Git Bash und Docker. Alle Tests laufen über `scripts/test.sh`, die Firmware-Validierung über `scripts/esphome-config.sh`.

## Review Focus

1. **Figur wird angelegt oder bearbeitet, während eine Box spielt:** Die Wiedergabe und der Box-Zustand dürfen nicht zurückgesetzt werden, also kein Reload. Das anschliessende Abnehmen muss trotzdem pausieren. → Test in Task 8.
2. **UID-Schreibweisen:** ESPHome liefert `04-A1-B2-…`, im Formular wird vielleicht `04:a1:b2…` oder `04 A1 B2` eingetippt. Beides muss dieselbe Figur treffen. → Tests in Task 2 und Task 8.
3. **Schneller Figurenwechsel:** Figur A wird abgenommen und innerhalb von 1 s Figur B aufgelegt. Die verzögerte Pause von A darf B nicht pausieren. → Test in Task 5.
4. **Lautsprecher nicht verfügbar** beim Abnehmen, bei Tasten oder beim Drehen: keine Exception im Event-Handler, LED `error`, Box bleibt bedienbar. → Tests in Task 5 und Task 6.
5. **Fremde oder kaputte Events:** Ein Event von einem nicht konfigurierten Gerät oder ohne `action`/`uid` wird ohne Exception ignoriert. → Test in Task 8.

---

## Dateistruktur

| Datei | Verantwortung | Task |
| :--- | :--- | :--- |
| `Dockerfile.test`, `requirements_test.txt`, `scripts/test.sh`, `pyproject.toml` | Testumgebung im Container | 1 |
| `custom_components/home_tonie/manifest.json`, `const.py`, `__init__.py` (Grundgerüst) | Integration ladbar | 1 |
| `custom_components/home_tonie/config_flow.py` | Haupteintrag (Task 1), Subentry-Flows (Task 7) | 1, 7 |
| `custom_components/home_tonie/strings.json`, `translations/de.json`, `translations/en.json` | UI-Texte | 1, 7, 8 |
| `custom_components/home_tonie/library.py` | Normalisierung, `Figure`, `FigureLibrary` | 2 |
| `custom_components/home_tonie/player.py` | `PlayerAdapter` | 3 |
| `custom_components/home_tonie/led.py` | `LedAdapter` | 4 |
| `custom_components/home_tonie/box.py` | `BoxConfig`, `BoxState`, `BoxController` | 5, 6 |
| `custom_components/home_tonie/sensor.py` | Sensoren pro Box | 8 |
| `custom_components/home_tonie/__init__.py` | Verdrahtung, Event-Routing, Hot-Update der Library | 8 |
| `tests/conftest.py`, `tests/test_*.py` | Tests | 1–8 |
| `esphome/home-tonie-common.yaml`, `esphome/home-tonie-anna.yaml`, `esphome/home-tonie-ben.yaml`, `scripts/esphome-config.sh` | Firmware | 9 |
| `hacs.json`, `README.md`; Löschen von `esphome/home-tonie.yaml` und `automations/` | Installation, Doku, Aufräumen | 10 |

---

### Task 0: Annahmen verifizieren (Recherche, kein Code)

Ausführung durch den Agent `docs-researcher`. Parallel dazu macht der Nutzer den Spotify-Test. Blockiert nur die jeweils genannten Tasks.

**Files:**
- Modify: `docs/superpowers/specs/2026-11-13-home-tonie-integration-design.md` (Abschnitt 10: Ergebnisse eintragen)

**Interfaces:**
- Produces: bestätigte oder korrigierte Fakten für die Tasks 3, 4, 7 und 8.

- [ ] **Step 1: ESPHome-Events.** Im HA-Core-Quellcode (`homeassistant/components/esphome/manager.py`) prüfen:
  - Enthält ein per `homeassistant.event` gefeuertes Event `device_id` in `event.data`?
  - Ist dafür die Option „Allow the device to perform Home Assistant actions“ nötig?
  - Relevant für Task 8. Fehlt `device_id`: Fallback aus Spec 10 verwenden. Die Firmware sendet dann `box: ${device_name}`, und Task 8 routet über `esphome_node_name`.
- [ ] **Step 2: ESPHome-Knotenname.** Wie kommt man vom Geräte-Registry-Eintrag zum ESPHome-Knotennamen (für `esphome.<node>_set_led`)? Erwartet: Der ESPHome-Config-Entry enthält `data["device_name"]`. Relevant für Task 4.
- [ ] **Step 3: Music Assistant.** Prüfen:
  - die gültigen `media_type`-Werte von `music_assistant.play_media`;
  - die URI-Form für Spotify-Shows, -Folgen und -Hörbücher (`spotify://podcast/…`? `spotify://podcast_episode/…`?).

  Erwartete Zuordnung: `album→album`, `playlist→playlist`, `track→track`, `artist→artist`, `audiobook→audiobook`, `show→podcast`, `episode→podcast_episode`. Relevant für Task 2.
- [ ] **Step 4: Config-Subentries.** Aktuelle API-Namen prüfen: `ConfigFlow.async_get_supported_subentry_types`, `ConfigSubentryFlow`, `async_step_reconfigure`, `_get_reconfigure_subentry`, `async_update_and_abort`, `async_add_entities(..., config_subentry_id=...)`. Ausserdem die erste HA-Version mit Subentry-Reconfigure ermitteln. Relevant für Task 7, 8 und 10.
- [ ] **Step 5: Manueller Test (Nutzer).**
  - Zwei Music-Assistant-Benutzer mit je eigenem Spotify-Anbieterfilter spielen per `play_media … username:` gleichzeitig auf zwei Lautsprechern, auch über einen Titelwechsel hinweg.
  - Gegenprobe ohne `username`.
  - Während eines pausierten Titels prüfen, ob sich `media_content_id` ändert.
- [ ] **Step 6: Ergebnisse in Spec Abschnitt 10 eintragen und committen.**

```bash
git add docs/superpowers/specs/2026-11-13-home-tonie-integration-design.md
git commit -m "docs: Annahmen aus Spec Abschnitt 10 verifiziert"
```

---

### Task 1: Testumgebung, Grundgerüst und Haupteintrag

**Files:**
- Create: `Dockerfile.test`, `requirements_test.txt`, `scripts/test.sh`, `pyproject.toml`
- Create: `custom_components/home_tonie/{__init__.py,manifest.json,const.py,config_flow.py,strings.json}`, `translations/{de,en}.json`
- Test: `tests/conftest.py`, `tests/test_init.py`

**Interfaces:**
- Produces in `const.py`:
  - `DOMAIN = "home_tonie"`, `EVENT_TYPE = "esphome.home_tonie"`, `SUBENTRY_BOX = "box"`, `SUBENTRY_FIGURE = "figure"`;
  - `CONF_ESPHOME_DEVICE_ID = "esphome_device_id"`, `CONF_PLAYER_ENTITY_ID = "player_entity_id"`, `CONF_MA_USERNAME = "ma_username"`, `CONF_MAX_VOLUME = "max_volume"`, `CONF_VOLUME_STEP = "volume_step"`, `CONF_UID = "uid"`, `CONF_MEDIA_URI = "media_uri"`, `CONF_MODE = "mode"`;
  - `DEFAULT_MAX_VOLUME = 40`, `DEFAULT_VOLUME_STEP = 3`, `MODE_RESTART = "restart"`, `REMOVAL_DEBOUNCE_S = 1.0`;
  - `LED_OFF, LED_LOADING, LED_PLAYING, LED_HOLD, LED_PAUSED, LED_UNKNOWN, LED_ERROR, LED_VOLUME` mit den Strings aus Global Constraints.
- Produces in `config_flow.py`: `HomeTonieConfigFlow(ConfigFlow, domain=DOMAIN)`, VERSION 1, `async_step_user` → Bestätigungsformular → `async_create_entry(title="Home Tonie", data={})`.
- Produces in `__init__.py`: `async_setup_entry` / `async_unload_entry`, vorerst ohne Logik (`return True`).

- [ ] **Step 1: Testcontainer anlegen.**
  - `requirements_test.txt`: `pytest-homeassistant-custom-component` (aktuelle Version, exakt gepinnt) und `freezegun`.
  - `Dockerfile.test`: Python-Image in der Version, die dieses Paket verlangt; Requirements installieren; `WORKDIR /app`.
  - `scripts/test.sh`:
    - baut das Image `home-tonie-test`, falls nicht vorhanden oder wenn sich `requirements_test.txt` geändert hat;
    - führt `pytest "$@"` mit gemountetem Repo aus;
    - unter Git Bash `MSYS_NO_PATHCONV=1` und `"$(pwd -W 2>/dev/null || pwd)"` für den Mount verwenden.
  - `pyproject.toml`: `[tool.pytest.ini_options] asyncio_mode = "auto"`, `testpaths = ["tests"]`.
- [ ] **Step 2: Failing tests schreiben.**
  - `tests/conftest.py` aktiviert `enable_custom_integrations` per autouse-Fixture.
  - `test_init.py`:

```python
async def test_user_flow_creates_single_entry(hass):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Home Tonie"
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"

async def test_setup_and_unload(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.LOADED
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED
```

- [ ] **Step 3: Tests laufen lassen.** `bash scripts/test.sh tests/test_init.py -v`. Erwartet: FAIL (Integration nicht gefunden).
- [ ] **Step 4: Grundgerüst implementieren.**
  - `manifest.json`: `domain`, `name: "Home Tonie"`, `config_flow: true`, `single_config_entry: true`, `iot_class: "local_push"`, `dependencies: []`, `after_dependencies: ["esphome", "music_assistant"]`, `version: "0.1.0"`, `codeowners`, `documentation`.
  - `strings.json`/Übersetzungen mit dem Bestätigungstext.
- [ ] **Step 5: Tests laufen lassen.** Gleicher Befehl. Erwartet: 2 passed.
- [ ] **Step 6: Commit.**

```bash
git add Dockerfile.test requirements_test.txt scripts/test.sh pyproject.toml custom_components tests
git commit -m "feat: Grundgerüst home_tonie mit Testumgebung"
```

---

### Task 2: Figurenbibliothek und Normalisierung

**Files:**
- Create: `custom_components/home_tonie/library.py`
- Test: `tests/test_library.py`

**Interfaces:**
- Consumes: Konstanten aus Task 1.
- Produces:
  - `class InvalidMediaUri(ValueError)`
  - `def normalize_uid(raw: str) -> str`
  - `def normalize_spotify_uri(raw: str) -> str`: wirft `InvalidMediaUri`.
  - `def to_ma_media(uri: str) -> tuple[str, str]`: liefert `(media_id, media_type)`, z. B. `("spotify://album/<id>", "album")`.
  - `@dataclass(frozen=True) class Figure: subentry_id: str; name: str; uid: str; media_uri: str; mode: str`
  - `class FigureLibrary` mit:
    - `__init__(self, figures: Iterable[Figure] = ())`;
    - `lookup(self, uid: str) -> Figure | None` (normalisiert intern);
    - `replace(self, figures: Iterable[Figure]) -> None`;
    - `@staticmethod figures_from_entry(entry: ConfigEntry) -> list[Figure]` (liest alle Subentries vom Typ `figure`).

- [ ] **Step 1: Failing tests schreiben.**

```python
@pytest.mark.parametrize("raw", ["04-a1-b2-c3", "04:A1:B2:C3", "04 a1 b2 c3", " 04A1B2C3 "])
def test_normalize_uid(raw):
    assert normalize_uid(raw) == "04A1B2C3"

@pytest.mark.parametrize("raw,expected", [
    ("https://open.spotify.com/album/4aawyAB9vmqN3uQ7FjRGTy?si=abc", "spotify:album:4aawyAB9vmqN3uQ7FjRGTy"),
    ("https://open.spotify.com/intl-de/playlist/37i9dQZF1DXcBWIGoYBM5M", "spotify:playlist:37i9dQZF1DXcBWIGoYBM5M"),
    ("spotify:track:11dFghVXANMlKmJXsNCbNl", "spotify:track:11dFghVXANMlKmJXsNCbNl"),
    ("https://open.spotify.com/audiobook/7iHfbu1YPACw6oZPAFJtqe", "spotify:audiobook:7iHfbu1YPACw6oZPAFJtqe"),
    ("https://open.spotify.com/show/2MAi0BvDc6GTFvKFPXnkCL", "spotify:show:2MAi0BvDc6GTFvKFPXnkCL"),
])
def test_normalize_spotify_uri(raw, expected):
    assert normalize_spotify_uri(raw) == expected

@pytest.mark.parametrize("raw", ["", "https://example.com/album/x", "spotify:album:", "https://open.spotify.com/user/abc", "spotify:album:zu-kurz"])
def test_normalize_spotify_uri_invalid(raw):
    with pytest.raises(InvalidMediaUri):
        normalize_spotify_uri(raw)

@pytest.mark.parametrize("uri,expected", [
    ("spotify:album:4aawyAB9vmqN3uQ7FjRGTy", ("spotify://album/4aawyAB9vmqN3uQ7FjRGTy", "album")),
    ("spotify:show:2MAi0BvDc6GTFvKFPXnkCL", ("spotify://podcast/2MAi0BvDc6GTFvKFPXnkCL", "podcast")),
])
def test_to_ma_media(uri, expected):
    assert to_ma_media(uri) == expected

def test_lookup_matches_any_uid_spelling():
    lib = FigureLibrary([Figure("s1", "Bobo", "04A1B2C3", "spotify:album:4aawyAB9vmqN3uQ7FjRGTy", "restart")])
    assert lib.lookup("04-a1-b2-c3").name == "Bobo"
    assert lib.lookup("FFFF") is None

def test_replace_swaps_figures():
    lib = FigureLibrary([Figure("s1", "Bobo", "04A1", "spotify:album:4aawyAB9vmqN3uQ7FjRGTy", "restart")])
    lib.replace([Figure("s2", "Feuerwehr", "04B7", "spotify:album:4aawyAB9vmqN3uQ7FjRGTy", "restart")])
    assert lib.lookup("04A1") is None
    assert lib.lookup("04b7").name == "Feuerwehr"
```

- [ ] **Step 2: Tests laufen lassen.** `bash scripts/test.sh tests/test_library.py -v`. Erwartet: FAIL (ImportError).
- [ ] **Step 3: `library.py` implementieren.**
  - Spotify-ID: genau 22 Zeichen `[A-Za-z0-9]`.
  - Erlaubte Typen: `album, playlist, track, artist, show, episode, audiobook`.
  - MA-Typzuordnung gemäss Task 0, Step 3: `show→podcast`, `episode→podcast_episode`, sonst gleich.
  - Ein reiner Regex genügt; Query-Parameter und `intl-xx/` werden ignoriert.
- [ ] **Step 4: Tests laufen lassen.** Erwartet: alle passed.
- [ ] **Step 5: Commit.** `git commit -m "feat: Figurenbibliothek und Normalisierung"`

---

### Task 3: PlayerAdapter

**Files:**
- Create: `custom_components/home_tonie/player.py`
- Test: `tests/test_player.py`

**Interfaces:**
- Consumes: `to_ma_media` (Task 2).
- Produces:
  - `class PlayerError(Exception)`
  - `@dataclass(frozen=True) class PlayerSnapshot: state: str | None; media_content_id: str | None`
  - `class PlayerAdapter` mit `__init__(self, hass: HomeAssistant, entity_id: str, ma_username: str)` und den Methoden:
    - `is_available() -> bool`
    - `snapshot() -> PlayerSnapshot`
    - `get_volume() -> float | None` (0.0–1.0)
    - `async play(media_uri: str) -> None`
    - `async resume() -> None`
    - `async pause() -> None`
    - `async next_track() -> None`
    - `async previous_track() -> None`
    - `async set_volume(volume: float) -> None` (begrenzt auf 0.0–1.0)
  - Alle `async`-Methoden werfen `PlayerError`, wenn die Entität fehlt oder `unavailable` ist oder der Service-Aufruf `HomeAssistantError` wirft.

- [ ] **Step 1: Failing tests schreiben.** Services mit `async_mock_service` mocken; den Player-Zustand per `hass.states.async_set("media_player.kinderzimmer", "paused", {"volume_level": 0.3, "media_content_id": "spotify://track/abc"})` setzen.

```python
async def test_play_calls_music_assistant_with_username(hass):
    calls = async_mock_service(hass, "music_assistant", "play_media")
    hass.states.async_set("media_player.kinderzimmer", "idle")
    await PlayerAdapter(hass, "media_player.kinderzimmer", "anna").play("spotify:album:4aawyAB9vmqN3uQ7FjRGTy")
    assert calls[0].data == {
        "entity_id": "media_player.kinderzimmer",
        "media_id": "spotify://album/4aawyAB9vmqN3uQ7FjRGTy",
        "media_type": "album",
        "enqueue": "replace",
        "username": "anna",
    }

@pytest.mark.parametrize("method,service", [("resume", "media_play"), ("pause", "media_pause"),
    ("next_track", "media_next_track"), ("previous_track", "media_previous_track")])
async def test_transport_services(hass, method, service): ...  # Aufruf von media_player.<service> mit entity_id

async def test_set_volume_clamps(hass):  # set_volume(1.4) → volume_level 1.0; set_volume(-0.1) → 0.0
async def test_snapshot_and_volume_read_state(hass):  # state "paused", media_content_id, get_volume() == 0.3
async def test_unavailable_player_raises(hass):  # state "unavailable" → play/pause/set_volume werfen PlayerError; is_available() False
async def test_missing_entity_raises(hass):  # Entität existiert nicht → PlayerError, get_volume() is None
```

- [ ] **Step 2: Tests laufen lassen.** `bash scripts/test.sh tests/test_player.py -v`. Erwartet: FAIL.
- [ ] **Step 3: `player.py` implementieren.** Service-Aufrufe mit `blocking=True`; `HomeAssistantError` wird in `PlayerError` umgewandelt.
- [ ] **Step 4: Tests laufen lassen.** Erwartet: alle passed.
- [ ] **Step 5: Commit.** `git commit -m "feat: PlayerAdapter für Music Assistant"`

---

### Task 4: LedAdapter

**Files:**
- Create: `custom_components/home_tonie/led.py`
- Test: `tests/test_led.py`

**Interfaces:**
- Consumes: LED-Konstanten (Task 1); Ergebnis aus Task 0, Step 2.
- Produces:
  - `def esphome_node_name(hass: HomeAssistant, device_id: str) -> str | None`: Device Registry → ESPHome-Config-Entry → `entry.data["device_name"]`.
  - `class LedAdapter` mit `__init__(self, hass: HomeAssistant, device_id: str)` und `async show(mode: str, level: int = 0) -> None`.
  - `show` ruft `esphome.<node_name mit "-"→"_">_set_led` mit `{"mode": mode, "level": level}` auf.
  - `show` wirft **nie**. Fehlt der Service oder der Knotenname, gibt es **einmalig** pro Adapter `_LOGGER.warning`, danach nur noch nichts.

- [ ] **Step 1: Failing tests schreiben.** Fixture: `MockConfigEntry(domain="esphome", data={"device_name": "home-tonie-anna", ...})` plus Device-Registry-Eintrag für diesen Entry.

```python
async def test_show_calls_node_specific_action(hass, esphome_device):
    calls = async_mock_service(hass, "esphome", "home_tonie_anna_set_led")
    await LedAdapter(hass, esphome_device.id).show(LED_VOLUME, 75)
    assert calls[0].data == {"mode": "volume", "level": 75}

async def test_missing_action_warns_once(hass, esphome_device, caplog):
    led = LedAdapter(hass, esphome_device.id)
    await led.show(LED_PLAYING)
    await led.show(LED_OFF)
    assert caplog.text.count("set_led") == 1

async def test_unknown_device_does_not_raise(hass):
    await LedAdapter(hass, "does-not-exist").show(LED_OFF)
```

- [ ] **Step 2: Tests laufen lassen.** `bash scripts/test.sh tests/test_led.py -v`. Erwartet: FAIL.
- [ ] **Step 3: `led.py` implementieren.** Den Knotennamen bei jedem Aufruf neu auflösen, denn er ist billig und überlebt so ein Neu-Einrichten der Box. Service-Aufruf mit `blocking=False`.
- [ ] **Step 4: Tests laufen lassen.** Erwartet: alle passed.
- [ ] **Step 5: Commit.** `git commit -m "feat: LedAdapter für ESPHome set_led"`

---

### Task 5: BoxController – Auflegen und Abnehmen

**Files:**
- Create: `custom_components/home_tonie/box.py`
- Test: `tests/test_box_tags.py`, Fakes in `tests/fakes.py`

**Interfaces:**
- Consumes: `FigureLibrary`, `Figure` (Task 2); Schnittstellen von `PlayerAdapter`/`PlayerError`/`PlayerSnapshot` (Task 3) und `LedAdapter` (Task 4).
- Produces:
  - `@dataclass(frozen=True) class BoxConfig: subentry_id: str; name: str; esphome_device_id: str; player_entity_id: str; ma_username: str; max_volume: int; volume_step: int`
  - `class BoxState(StrEnum): IDLE, LOADING, PLAYING, PAUSED_BY_BOX, REMOVED`
  - `class BoxController` mit:
    - `__init__(self, hass, config: BoxConfig, library: FigureLibrary, player, led, on_unknown_tag: Callable[[str], None] | None = None)`
    - Properties `state: BoxState`, `current_figure: Figure | None`, `last_unknown_uid: str | None`
    - `add_listener(cb: Callable[[], None]) -> Callable[[], None]` (gibt die Abmeldefunktion zurück)
    - `async handle_event(data: Mapping[str, Any]) -> None`: verteilt nach `action`
    - `async tag_on(uid: str)`, `async tag_off(uid: str)`
    - `async_shutdown() -> None`: bricht den Entprell-Timer ab
- `tests/fakes.py`:
  - `FakePlayer`: zeichnet Aufrufe in `calls: list[tuple]` auf; Felder `state`, `media_content_id`, `volume`, `available`.
  - `FakeLed`: zeichnet `shows: list[tuple[str, int]]` auf.

Verhalten exakt nach Spec 6.2. Ergänzend:
- **Lautstärke begrenzen** heisst: Ist `get_volume()` grösser als `max_volume/100`, dann `set_volume(max_volume/100)`.
- **Persistente Benachrichtigung** über `persistent_notification.async_create` mit `notification_id = f"home_tonie_unknown_{subentry_id}"`; Text aus Spec 6.2.
- Nach jeder Zustandsänderung werden die Listener aufgerufen.
- Der Entprell-Timer läuft über `async_call_later(hass, REMOVAL_DEBOUNCE_S, …)`.
- `tag_on` mit einer **anderen** UID während einer laufenden Entprellung bricht den Timer ab. Dabei wird die alte Figur **ohne** `pause()` zu `last_figure`, weil gleich die neue Figur abspielt.

- [ ] **Step 1: Failing tests schreiben** (`tests/test_box_tags.py`; Zeit vorspulen mit `async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=1.1))`):

```python
async def test_known_figure_plays_and_caps_volume(hass, box):      # FakePlayer.volume=0.8, max 40
    await box.ctrl.tag_on("04-A1-B2-C3")
    assert ("set_volume", 0.4) in box.player.calls
    assert ("play", "spotify:album:4aawyAB9vmqN3uQ7FjRGTy") in box.player.calls
    assert box.led.shows == [("loading", 0), ("playing", 0)]
    assert box.ctrl.state is BoxState.PLAYING and box.ctrl.current_figure.name == "Bobo"

async def test_removal_pauses_after_debounce(hass, box):   # vor 1 s: kein pause; nach 1.1 s: ("pause",), LED paused, state REMOVED
async def test_flicker_within_debounce_is_ignored(hass, box):  # tag_off + tag_on gleiche UID nach 0.5 s → keine pause, kein zweites play
async def test_same_figure_resumes(hass, box):             # abnehmen, Player bleibt paused mit gleicher media_content_id → ("resume",), kein zweites play
async def test_same_figure_restarts_if_player_changed(hass, box):  # media_content_id nach dem Abnehmen geändert → play
async def test_other_figure_starts_fresh(hass, box):       # A abnehmen (Entprellung abgelaufen), B auflegen → play(B)
async def test_quick_swap_does_not_pause_new_figure(hass, box):  # Review Focus 3: A tag_off, nach 0.3 s B tag_on, nach 1.1 s: kein ("pause",) nach play(B)
async def test_unknown_figure_notifies(hass, box):         # last_unknown_uid == "FFEE", Benachrichtigung existiert, LED unknown, kein play, state IDLE, on_unknown_tag mit "FFEE" aufgerufen
async def test_player_error_on_play_sets_error(hass, box):  # FakePlayer.available=False → LED error, state IDLE, keine Exception
async def test_player_error_on_removal_does_not_raise(hass, box):  # Review Focus 4: Player fällt nach dem Start aus; Abnehmen → keine Exception, LED off/error, state IDLE
async def test_listeners_notified(hass, box):              # Listener-Zähler steigt bei tag_on und tag_off
```

  Fixture `box`: `FigureLibrary` mit Bobo (`04A1B2C3`, `spotify:album:4aawyAB9vmqN3uQ7FjRGTy`) und Feuerwehr (`04B7C8D9`, `spotify:playlist:37i9dQZF1DXcBWIGoYBM5M`); `BoxConfig(max_volume=40, volume_step=3)`.
- [ ] **Step 2: Tests laufen lassen.** `bash scripts/test.sh tests/test_box_tags.py -v`. Erwartet: FAIL.
- [ ] **Step 3: `box.py` implementieren** (Zustandsautomat gemäss Spec 6.1/6.2 und den Ergänzungen oben).
- [ ] **Step 4: Tests laufen lassen.** Erwartet: alle passed.
- [ ] **Step 5: Commit.** `git commit -m "feat: BoxController für Auflegen und Abnehmen"`

---

### Task 6: BoxController – Taster und Encoder

**Files:**
- Modify: `custom_components/home_tonie/box.py`
- Test: `tests/test_box_controls.py`

**Interfaces:**
- Consumes: alles aus Task 5.
- Produces:
  - `async play_pause()`, `async next_track()`, `async previous_track()`, `async rotate(direction: int)` (+1 bzw. −1);
  - `handle_event` ordnet zu: `play_pause` → `play_pause`, `next` → `next_track`, `prev` → `previous_track`, `rotate_cw` → `rotate(1)`, `rotate_ccw` → `rotate(-1)`.

Regeln:
- **Keine Figur** (`state` ∈ {IDLE, REMOVED}): alles ignorieren.
- **`play_pause` aus PLAYING:** `pause()`, LED `hold`, Zustand PAUSED_BY_BOX.
- **`play_pause` aus PAUSED_BY_BOX:** Lautstärke begrenzen, `resume()`, LED `playing`, Zustand PLAYING.
- **`rotate`:**
  - `v = clamp(round(get_volume()*100) ± volume_step, 0, max_volume)`; ist `get_volume()` `None`, gilt 0 als Basis.
  - Danach `set_volume(v/100)` und LED `volume` mit `level = round(v / max_volume * 100)`.
- **`PlayerError`** → LED `error`, keine Exception, Zustand unverändert.

- [ ] **Step 1: Failing tests schreiben.**

```python
async def test_controls_ignored_without_figure(hass, box):   # alle fünf Aktionen → player.calls == [], led.shows == []
async def test_play_pause_toggles(hass, box):                # nach tag_on: pause + LED hold + PAUSED_BY_BOX; nochmal: resume + LED playing + PLAYING
async def test_next_prev(hass, box):                         # ("next_track",), ("previous_track",)
async def test_rotate_up_capped_at_max(hass, box):           # volume 0.39, step 3, max 40 → set_volume(0.40), LED ("volume", 100)
async def test_rotate_down_floor_zero(hass, box):            # volume 0.02 → set_volume(0.0), LED ("volume", 0)
async def test_rotate_with_unknown_volume(hass, box):        # get_volume None → set_volume(0.03), LED ("volume", 8)
async def test_rotate_player_error(hass, box):               # Review Focus 4: available=False → LED error, keine Exception
async def test_handle_event_dispatch(hass, box):             # handle_event({"action": "rotate_cw"}) → set_volume aufgerufen; {"action": "bogus"} und {} → keine Exception, keine Aufrufe
```

- [ ] **Step 2: Tests laufen lassen.** `bash scripts/test.sh tests/test_box_controls.py -v`. Erwartet: FAIL.
- [ ] **Step 3: Implementieren.**
- [ ] **Step 4: Gesamte Testsuite laufen lassen.** `bash scripts/test.sh -q`. Erwartet: alle passed.
- [ ] **Step 5: Commit.** `git commit -m "feat: BoxController für Taster und Encoder"`

---

### Task 7: Config-Subentry-Flows für Box und Figur

**Files:**
- Modify: `custom_components/home_tonie/config_flow.py`, `strings.json`, `translations/{de,en}.json`
- Test: `tests/test_config_flow.py`

**Interfaces:**
- Consumes: `normalize_uid`, `normalize_spotify_uri`, `InvalidMediaUri` (Task 2); Konstanten (Task 1); Ergebnis aus Task 0, Step 4.
- Produces:
  - `HomeTonieConfigFlow.async_get_supported_subentry_types` → `{SUBENTRY_BOX: BoxSubentryFlow, SUBENTRY_FIGURE: FigureSubentryFlow}`.
  - `BoxSubentryFlow` mit `async_step_user`, `async_step_reconfigure`, `async_step_confirm_shared_user`.
  - `FigureSubentryFlow` mit `async_step_user` und `async_step_reconfigure`.
  - Subentry-Daten exakt mit den `CONF_*`-Schlüsseln aus Task 1; Titel = `name`.
  - Gespeichert werden immer die normalisierten Werte für `uid` und `media_uri`.
  - UID-Vorbelegung aus `entry.runtime_data.last_unknown_uid`. Das Attribut liefert Task 8; bis dahin `getattr(..., None)`, damit der Flow auch ohne Runtime-Daten funktioniert.

Formulare:
- **Box:**
  - `name` (Text);
  - `esphome_device_id` (DeviceSelector, `integration="esphome"`);
  - `player_entity_id` (EntitySelector, `domain="media_player"`, `integration="music_assistant"`);
  - `ma_username` (Text);
  - `max_volume` (NumberSelector 5–100, Schritt 1, Default 40);
  - `volume_step` (NumberSelector 1–10, Default 3).
- **Figur:**
  - `name`, `uid`, `media_uri` (Text);
  - `mode` (SelectSelector, nur `restart`, Default `restart`).

Fehlerschlüssel:
- `device_in_use`: ESPHome-Gerät ist bereits einer anderen Box zugeordnet.
- `uid_exists`: UID nach Normalisierung schon bei einer anderen Figur vorhanden; beim Reconfigure zählt die eigene Figur nicht.
- `invalid_media_uri`.
- Abbruch `no_ma_players`, wenn kein `media_player` der Integration `music_assistant` existiert.
- Gleicher `ma_username` wie eine andere Box → Schritt `confirm_shared_user` mit Warntext „Diese Boxen können nicht gleichzeitig spielen“. Bestätigen speichert.

- [ ] **Step 1: Failing tests schreiben.**

```python
async def test_add_box(hass, loaded_entry, esphome_device, ma_player):   # CREATE_ENTRY, subentry.data == {...normalisiert, max_volume 40, volume_step 3}
async def test_add_box_aborts_without_ma_players(hass, loaded_entry): # ABORT reason "no_ma_players"
async def test_box_device_in_use(hass, loaded_entry_with_box, esphome_device, ma_player):  # errors == {"esphome_device_id": "device_in_use"}
async def test_box_shared_username_requires_confirmation(hass, loaded_entry_with_box, other_device, ma_player):  # step_id "confirm_shared_user" → bestätigen → CREATE_ENTRY
async def test_add_figure_normalizes(hass, loaded_entry):             # uid "04-a1-b2-c3" → "04A1B2C3"; Link → "spotify:album:4aawyAB9vmqN3uQ7FjRGTy"; mode "restart"
async def test_figure_invalid_link(hass, loaded_entry):               # errors == {"media_uri": "invalid_media_uri"}
async def test_figure_duplicate_uid(hass, loaded_entry_with_figure):  # "04:A1:B2:C3" → errors == {"uid": "uid_exists"}
async def test_reconfigure_figure_keeps_own_uid(hass, loaded_entry_with_figure):  # gleiche UID, neuer Name → ABORT "reconfigure_successful", Daten aktualisiert
async def test_figure_uid_prefilled(hass, loaded_entry):              # runtime_data.last_unknown_uid = "FFEE" → Schema-Default/suggested_value von uid == "FFEE"
```

- [ ] **Step 2: Tests laufen lassen.** `bash scripts/test.sh tests/test_config_flow.py -v`. Erwartet: FAIL.
- [ ] **Step 3: Implementieren**, inklusive aller Texte und Fehlermeldungen in `strings.json`, `de.json` und `en.json`.
- [ ] **Step 4: Tests laufen lassen.** Erwartet: alle passed; die gesamte Suite grün.
- [ ] **Step 5: Commit.** `git commit -m "feat: Subentry-Flows für Box und Figur"`

---

### Task 8: Verdrahtung, Event-Routing, Sensoren und Hot-Update

**Files:**
- Modify: `custom_components/home_tonie/__init__.py`, `strings.json`, Übersetzungen
- Create: `custom_components/home_tonie/sensor.py`
- Test: `tests/test_integration.py`, `tests/test_sensor.py`

**Interfaces:**
- Consumes: alles aus Task 2 bis 7.
- Produces:
  - `@dataclass class HomeTonieData: library: FigureLibrary; controllers: dict[str, BoxController]; last_unknown_uid: str | None = None`. Die Schlüssel von `controllers` sind `esphome_device_id`.
  - `type HomeTonieConfigEntry = ConfigEntry[HomeTonieData]`; `entry.runtime_data` ist eine `HomeTonieData`.
  - **Pro Box-Subentry** ein HA-Gerät mit `identifiers {(DOMAIN, subentry_id)}`, Name „Home Tonie {name}“, und zwei Sensoren (`config_subentry_id` gesetzt, `has_entity_name=True`):
    - `translation_key="current_figure"` (de „Aktuelle Figur“): Wert = Figurname oder `None`;
    - `translation_key="last_unknown_tag"` (de „Letzter unbekannter Tag“): Wert = UID oder `None`.

Verhalten:
- **Setup:**
  - `FigureLibrary` aus `figures_from_entry` bauen;
  - pro Box `PlayerAdapter`, `LedAdapter` und `BoxController` erzeugen; `on_unknown_tag` setzt `runtime_data.last_unknown_uid`;
  - `hass.bus.async_listen(EVENT_TYPE, …)` registrieren und beim Unload abmelden;
  - Sensor-Plattform weiterleiten.
- **Routing:**
  - `event.data["device_id"]` → Controller → `handle_event(event.data)`.
  - Unbekanntes oder fehlendes `device_id` → Debug-Log, ignorieren. Dasselbe gilt für Exceptions aus Adaptern: loggen, nie nach oben werfen.
- **Update-Listener:**
  - Haben sich nur `figure`-Subentries geändert → `library.replace(figures_from_entry(entry))`, **kein** Reload.
  - Hat sich die Menge oder der Inhalt der `box`-Subentries geändert → `hass.config_entries.async_schedule_reload`.
  - Vergleichsbasis: der Stand der Box-Subentries beim letzten Setup.
- **Unload:** `async_shutdown()` aller Controller.

- [ ] **Step 1: Failing tests schreiben.** Das ESPHome-Gerät und die MA-Services werden gemockt. Die Controller werden über ihre Adapter beobachtet: Services `music_assistant.play_media` und `media_player.*` sind gemockt, der Player-Zustand per `hass.states.async_set` gesetzt.

```python
async def test_event_routed_to_correct_box(hass, two_boxes_entry):
    hass.bus.async_fire("esphome.home_tonie", {"device_id": DEV_ANNA, "action": "tag_on", "uid": "04-A1-B2-C3"})
    await hass.async_block_till_done()
    assert play_calls[-1].data["entity_id"] == "media_player.anna"
    assert play_calls[-1].data["username"] == "anna"
    # Box Ben unberührt
    assert hass.states.get("sensor.home_tonie_ben_aktuelle_figur").state == "unknown"

async def test_two_boxes_independent(hass, two_boxes_entry):  # Bobo auf Anna, Feuerwehr auf Ben → zwei play_media mit je eigenem entity_id/username; Abnehmen bei Anna pausiert nur media_player.anna
async def test_foreign_and_malformed_events_ignored(hass, two_boxes_entry):  # Review Focus 5: unbekannte device_id, ohne action, tag_on ohne uid → keine Exception, keine Service-Aufrufe
async def test_adding_figure_does_not_reset_playing_box(hass, two_boxes_entry):  # Review Focus 1: Bobo spielt; Figur-Subentry per async_add_subentry hinzufügen; Controller-Objekt identisch, state PLAYING; Abnehmen pausiert; die neue Figur ist sofort abspielbar
async def test_box_change_reloads(hass, two_boxes_entry):  # max_volume einer Box ändern → Entry neu geladen, neuer Wert wirksam
async def test_unknown_tag_prefills_flow(hass, two_boxes_entry):  # tag_on "FF:EE" → runtime_data.last_unknown_uid == "FFEE"; Figur-Flow schlägt "FFEE" vor
async def test_uid_spelling_end_to_end(hass, two_boxes_entry):  # Review Focus 2: Figur im Formular mit "04:a1:b2:c3", Event mit "04-A1-B2-C3" → play_media
async def test_unload_cleans_up(hass, two_boxes_entry):  # Unload → Event danach löst nichts aus
```

  `tests/test_sensor.py`: Nach `tag_on` zeigt der Sensor „Aktuelle Figur“ den Namen „Bobo“; nach dem Abnehmen (Entprellung abgelaufen) `unknown`; nach einer unbekannten UID zeigt „Letzter unbekannter Tag“ den Wert `FFEE`.
- [ ] **Step 2: Tests laufen lassen.** `bash scripts/test.sh tests/test_integration.py tests/test_sensor.py -v`. Erwartet: FAIL.
- [ ] **Step 3: `__init__.py` und `sensor.py` implementieren.**
- [ ] **Step 4: Gesamte Suite laufen lassen.** `bash scripts/test.sh -q`. Erwartet: alle passed.
- [ ] **Step 5: Commit.** `git commit -m "feat: Event-Routing, Sensoren und Hot-Update der Figuren"`

---

### Task 9: Firmware

Ausführung durch den Agent `esphome-firmware-dev`.

**Files:**
- Create: `esphome/home-tonie-common.yaml` (aus der heutigen `esphome/home-tonie.yaml` abgeleitet), `esphome/home-tonie-anna.yaml`, `esphome/home-tonie-ben.yaml`, `scripts/esphome-config.sh`
- Delete: `esphome/home-tonie.yaml` (erst nach erfolgreicher Validierung der neuen Dateien)

**Interfaces:**
- Produces:
  - Event `esphome.home_tonie` mit den `action`-Werten und `uid` gemäss Spec 4.2.
  - API-Action `set_led` mit `mode: string`, `level: int`, gemäss Spec 4.3. In HA erscheint sie als `esphome.home_tonie_anna_set_led` bzw. `esphome.home_tonie_ben_set_led`.

Vorgaben:
- **Pro-Box-Dateien:** nur `substitutions` (`device_name`, `friendly_name`) und `packages: common: !include home-tonie-common.yaml`.
- **Encoder:** `rotary_encoder`, `internal: true`, mit `on_clockwise`/`on_anticlockwise`. Pins GPIO32/33 mit Pullup, Filter `debounce: 10ms`.
- **Taster:** GPIO25 (Encoder), GPIO26 (`prev`), GPIO27 (`next`); `internal: true`, `inverted`, Pullup, `delayed_on`/`delayed_off` 15 ms; `on_press` sendet das Event.
- **PN532:** wie heute (`pn532_spi`, CS GPIO16, 250 ms), aber mit Events `tag_on` und `tag_off`.
- **LED:**
  - Licht `internal: true`; die Modi werden in der Firmware umgesetzt (Globals + Scripts im Modus `restart`);
  - **Helligkeitsobergrenze:** `color_correct: [50%, 50%, 50%]` am `esp32_rmt_led_strip`. Das ist eine harte Kappung (Strom und Blendung), siehe Spec 4.3;
  - Dauern gemäss Spec-Tabelle 4.3;
  - `hold` = statisch warmweiss 10 %;
  - `volume` kehrt nach ca. 1,5 s zum vorherigen Dauer-Modus zurück (`playing`/`hold`/`off`);
  - nach dem Boot ist der Ring `off`.
- **`scripts/esphome-config.sh <datei>`:** `docker run --rm -v <esphome-dir>:/config ghcr.io/esphome/esphome config /config/<datei>` (Pfad-Handling wie in `scripts/test.sh`).

- [ ] **Step 1: Common-Datei und Box-Dateien anlegen.**
- [ ] **Step 2: Validieren.** `bash scripts/esphome-config.sh home-tonie-anna.yaml` und `… home-tonie-ben.yaml`. Erwartet: „Configuration is valid!“ bei beiden.
- [ ] **Step 3: `esphome/home-tonie.yaml` löschen.**
- [ ] **Step 4: Checkliste für den manuellen Gerätetest in `README.md` vorbereiten** (wird in Task 10 eingebunden):
  - Events im HA-Event-Monitor sichtbar, inklusive `device_id`;
  - jeder LED-Modus per Entwicklerwerkzeuge auslösbar.
- [ ] **Step 5: Commit.** `git commit -m "feat: Firmware mit Events und set_led, eine Datei pro Box"`

---

### Task 10: Installation, Doku und Aufräumen

**Files:**
- Create: `hacs.json`
- Modify: `README.md`
- Delete: `automations/`

- [ ] **Step 1: `hacs.json` anlegen** mit `name: "Home Tonie"`, `content_in_root: false` und `homeassistant` = Mindestversion aus Task 0, Step 4. Dieselbe Mindestversion im README unter Voraussetzungen nennen.
- [ ] **Step 2: README ergänzen.**
  - **Architektur:** kurz, mit Verweis auf den Spec.
  - **Voraussetzungen:** gemäss Spec Abschnitt 9, mit Music-Assistant-Benutzern pro Kind.
  - **Installation** über HACS (benutzerdefiniertes Repository) oder manuell.
  - **Box einrichten, Figuren anlernen.**
  - **Firmware flashen** pro Box.
  - **Manuelle Testcheckliste** (aus Task 9 plus End-to-End):
    - Figur auflegen → Musik;
    - abnehmen → Pause;
    - wieder auflegen → weiter;
    - andere Figur → neu;
    - unbekannte Figur → Benachrichtigung;
    - Encoder begrenzt;
    - zwei Boxen gleichzeitig.
- [ ] **Step 3: `automations/` löschen.** Die Integration ersetzt Lernmodus und Lautsprecher-Auswahl.
- [ ] **Step 4: Gesamte Suite und Firmware-Validierung ein letztes Mal laufen lassen.** `bash scripts/test.sh -q` und beide `esphome-config.sh`-Aufrufe. Erwartet: alles grün.
- [ ] **Step 5: Commit.** `git commit -m "docs: Installation und Inbetriebnahme; alte Automationen entfernt"`
