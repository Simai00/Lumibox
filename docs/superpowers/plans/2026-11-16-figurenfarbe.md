# Figurenfarbe und Farb-Spinner – Umsetzungsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Jede Figur kann eine Farbe haben (Fallback: Standardfarbe der Box), und während sie spielt, zeigt der LED-Ring einen Spinner in dieser Farbe.

**Architecture:**
- Die Farbe wird als `[r, g, b]` in den Subentries gespeichert (Figur: `color`, optional; Box: `default_color`).
- `BoxController` ermittelt die wirksame Farbe und übergibt sie über `LedAdapter.show(..., color=(r, g, b))` an die ESPHome-Action `set_led(mode, level, r, g, b)`.
- Die Firmware zeichnet `playing` als `addressable_lambda`-Spinner.

**Tech Stack:** HA Custom Integration (Python, pytest-homeassistant-custom-component in Docker über `scripts/test.sh`), ESPHome (Validierung über `scripts/esphome-config.sh`).

**Spec:** `docs/superpowers/specs/2026-11-16-figurenfarbe-design.md` (ergänzt `docs/superpowers/specs/2026-11-13-home-tonie-integration-design.md`)

## Global Constraints

- Standardfarbe der Box: **Lila `(128, 0, 255)`**.
- Figur-`color` ist optional. Wirksame Farbe = Figurfarbe, sonst `default_color` der Box.
- `set_led` sendet immer `mode`, `level`, `r`, `g`, `b` (Ganzzahlen 0–255).
- Nur `playing` nutzt die Farbe.
  - `loading` bleibt der weisse Spinner.
  - `hold` bleibt statisch warmweiss mit 10 %.
  - `volume` kehrt zum Farb-Spinner mit derselben Farbe zurück.
- `playing`:
  - Basis ~25 % der Farbe.
  - Kopf 100 % der Farbe, Schweif 3 LEDs.
  - Ungefähr eine Runde pro 3 s (24 LEDs → ~125 ms pro Schritt).
- `color_correct: [50%, 50%, 50%]` bleibt.
- Texte de + en. Bestehende Subentries ohne die neuen Schlüssel funktionieren unverändert.
- Docker muss im PATH sein.

## Review Focus

1. **Alte Subentries ohne `color` bzw. `default_color`:**
   - Erwartung: Laden ohne KeyError, Box nutzt Lila.
   - Test in Task 1 (`figures_from_entry` ohne `color` → `None`) und Task 2 (Box-Data ohne `default_color` → Lila).
2. **Figur bearbeiten und dabei die Farbe leeren:**
   - Erwartung: Die Figur fällt auf die Boxfarbe zurück, gespeichert wird kein leerer Wert.
   - Test in Task 1.
3. **Wiederauflegen/Fortsetzen und Taster-Resume:**
   - Erwartung: Auch diese Wege senden die Figurfarbe, nicht nur der Neustart.
   - Test in Task 2.
4. **Dieselbe Figur auf zwei Boxen mit unterschiedlicher Standardfarbe:**
   - Erwartung: Jede Box nutzt ihre eigene Farbe.
   - Test in Task 2.
5. **Lautstärke-Overlay während `playing`:**
   - Erwartung: Danach wieder der Spinner in derselben Farbe, nicht Weiss.
   - Prüfung in Task 3 (manuelle Checkliste und Lambda-Review).

---

### Task 1: Farbe in Figur und Box speichern (Library, Config Flow, Texte)

**Files:**
- Modify: `custom_components/home_tonie/const.py`, `library.py`, `config_flow.py`, `strings.json`, `translations/de.json`, `translations/en.json`
- Test: `tests/test_library.py`, `tests/test_config_flow.py`

**Interfaces:**
- Produces:
  - `const.py`: `CONF_COLOR = "color"`, `CONF_DEFAULT_COLOR = "default_color"`, `DEFAULT_BOX_COLOR = (128, 0, 255)`.
  - `library.Figure`: neues letztes Feld `color: tuple[int, int, int] | None = None`.
  - `FigureLibrary.figures_from_entry` liest `sub.data.get(CONF_COLOR)` und macht daraus ein `tuple` oder `None`.
  - Box-Subentry-Data: `default_color: [r, g, b]`. Figur-Subentry-Data: `color: [r, g, b]` nur, wenn gesetzt.
- Formular:
  - Figur: `vol.Optional(CONF_COLOR): ColorRGBSelector()`.
  - Box: `vol.Required(CONF_DEFAULT_COLOR, default=list(DEFAULT_BOX_COLOR)): ColorRGBSelector()`.
  - Beim Reconfigure sind die gespeicherten Werte vorbelegt. Wird die Figurfarbe geleert, entfällt der Schlüssel.

- [ ] **Step 1: Failing tests schreiben**

```python
def test_figures_from_entry_reads_color(...):        # Figur mit color [255, 0, 0] → Figure.color == (255, 0, 0); Figur ohne color → None
async def test_add_figure_with_color(hass, loaded_entry):   # user_input mit color [0, 128, 255] → subentry.data["color"] == [0, 128, 255]
async def test_add_figure_without_color(hass, loaded_entry): # ohne color → "color" not in subentry.data
async def test_reconfigure_figure_clear_color(...):  # Figur mit color, Reconfigure ohne color → "color" not in data
async def test_add_box_default_color(...):           # ohne Eingabe → data["default_color"] == [128, 0, 255]; mit [0, 255, 0] → gespeichert
```

- [ ] **Step 2: Tests laufen lassen, Fehlschlag sehen.** `bash scripts/test.sh tests/test_library.py tests/test_config_flow.py -q`
- [ ] **Step 3: Implementieren.** Dazu gehören Labels und `data_description` in de/en, z. B. „Farbe (leer = Standardfarbe der Box)“ und „Standardfarbe“.
- [ ] **Step 4: Gesamte Suite laufen lassen.** `bash scripts/test.sh -q`. Erwartet: alles grün, keine Warnungen.
- [ ] **Step 5: Commit.** `feat: Farbe pro Figur und Standardfarbe pro Box`

---

### Task 2: Farbe an die LED übergeben (LedAdapter, BoxController, Verdrahtung)

**Files:**
- Modify: `custom_components/home_tonie/led.py`, `box.py`, `__init__.py`; `tests/fakes.py`
- Test: `tests/test_led.py`, `tests/test_box_tags.py`, `tests/test_box_controls.py`, `tests/test_integration.py`

**Interfaces:**
- Consumes: `Figure.color`, `CONF_DEFAULT_COLOR` und `DEFAULT_BOX_COLOR` aus Task 1.
- Produces:
  - `LedAdapter.show(self, mode: str, level: int = 0, color: tuple[int, int, int] = (0, 0, 0)) -> None` sendet `{"mode", "level", "r", "g", "b"}`.
  - `BoxConfig.default_color: tuple[int, int, int]`. In `__init__.py` wird es aus `data.get(CONF_DEFAULT_COLOR, DEFAULT_BOX_COLOR)` gebaut.
  - `BoxController._color_for(figure: Figure) -> tuple[int, int, int]` liefert `figure.color or self._config.default_color`.
  - **Jeder** Aufruf `self._led.show(LED_PLAYING)` in `box.py` wird zu `self._led.show(LED_PLAYING, color=self._color_for(figure))`. Das gilt für Start, Fortsetzen, Taster-Resume und das LED-Nachziehen bei doppeltem `tag_on`. Alle anderen Modi bleiben ohne Farbe.
  - `FakeLed.shows` zeichnet `(mode, level)` auf, solange keine Farbe übergeben wird, sonst `(mode, level, color)`. So bleiben bestehende Assertions gültig.

- [ ] **Step 1: Failing tests schreiben**

```python
async def test_show_sends_rgb(hass, esphome_device):   # show("playing", 0, (1, 2, 3)) → calls[0].data == {"mode": "playing", "level": 0, "r": 1, "g": 2, "b": 3}
async def test_show_default_color_zero(...):           # show("off") → r = g = b = 0
async def test_playing_uses_figure_color(hass, box):   # Figur mit color (255, 0, 0) → LED ("playing", 0, (255, 0, 0))
async def test_playing_falls_back_to_box_color(...):   # Figur ohne color → ("playing", 0, (128, 0, 255))
async def test_resume_and_button_resume_send_color(...):  # Review Focus 3: Fortsetzen und Taster-Resume senden die Figurfarbe
async def test_two_boxes_own_default_color(...):       # Review Focus 4 (test_integration): gleiche Figur ohne Farbe, Box A grün, Box B blau → jeweils eigene Farbe im set_led-Aufruf
async def test_box_without_default_color_key(...):     # Review Focus 1: Box-Data ohne default_color → set_led mit 128, 0, 255
```

- [ ] **Step 2: Tests laufen lassen, Fehlschlag sehen.**
- [ ] **Step 3: Implementieren.** Bestehende Tests, die `("playing", 0)` erwarten, auf `("playing", 0, <Farbe>)` umstellen und im Bericht auflisten.
- [ ] **Step 4: Gesamte Suite laufen lassen.** Erwartet: alles grün, keine Warnungen.
- [ ] **Step 5: Commit.** `feat: LED-Farbe der Figur an set_led übergeben`

---

### Task 3: Firmware – `set_led` mit Farbe und Farb-Spinner

**Files:**
- Modify: `esphome/home-tonie-common.yaml`

**Interfaces:**
- Consumes: Die Action wird mit `mode`, `level`, `r`, `g`, `b` aufgerufen (Task 2).
- Produces:
  - `api: actions: set_led` mit den Variablen `mode: string`, `level: int`, `r: int`, `g: int`, `b: int`.
  - Globals `led_r`, `led_g`, `led_b` (int), die nur bei `mode == "playing"` gesetzt werden. Bei `volume` bleiben sie stehen, damit der Spinner danach in derselben Farbe weiterläuft.
  - Neuer Effekt im Licht, z. B. `addressable_lambda` mit Namen „Farb-Spinner“ und `update_interval: 125ms`:
    - alle LEDs Basis = Farbe × ~25 %;
    - Kopf = Farbe 100 %;
    - 3 Schweif-LEDs mit abnehmender Helligkeit;
    - der Kopf wandert pro Update eine LED weiter.
  - `playing` aktiviert diesen Effekt anstelle des bisherigen Pulsierens. `loading`, `hold`, `paused`, `unknown`, `error` und `volume` bleiben inhaltlich wie bisher.
- Der Logger steht wieder auf `level: INFO` **ohne** die `pn532: VERY_VERBOSE`-Einträge. Die Diagnose ist abgeschlossen.

- [ ] **Step 1: Ändern.**
- [ ] **Step 2: Validieren.** `bash scripts/esphome-config.sh home-tonie-anna.yaml` und `… home-tonie-ben.yaml`. Erwartet: `Configuration is valid!`. Dazu ein Review der Lambdas auf Kompilierbarkeit (`Color(r, g, b)`, Skalierung mit `*` bzw. Multiplikation pro Kanal, `it.size()`).
- [ ] **Step 3: Manuelle Checkliste ins README**, Abschnitt Testcheckliste:
  - `set_led` mit `mode: playing, r: 255, g: 0, b: 0` zeigt einen roten Spinner;
  - danach `volume` → nach ~1,5 s wieder roter Spinner;
  - `hold` ist warmweiss.
- [ ] **Step 4: Commit.** `feat: Farb-Spinner für playing und set_led mit r/g/b`

---

### Task 4: Doku nachführen

**Files:**
- Modify: `docs/superpowers/specs/2026-11-13-home-tonie-integration-design.md` (Abschnitte 4.3, 5.1, 5.4), `README.md` (Einrichtung: Farbe und Standardfarbe; Hinweis: Firmware und Integration zusammen aktualisieren)

- [ ] **Step 1: Spec und README anpassen** (Werte aus Global Constraints).
- [ ] **Step 2: Commit.** `docs: Figurenfarbe in Spec und README`
