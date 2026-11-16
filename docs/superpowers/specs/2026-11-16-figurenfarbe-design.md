# Figurenfarbe und Farb-Spinner – Design (kleine Änderung)

Stand: 2026-11-16 · Status: freigegeben

## Absicht
An der Box soll man sehen, welche Figur gerade spielt. Jede Figur kann deshalb eine eigene Farbe haben. Während sie spielt, dreht im LED-Ring ein Spinner in dieser Farbe.

## Verhalten (mit dem Nutzer abgestimmt)
- **Figur:** neues optionales Feld „Farbe“ (Farbwähler).
- **Box:** neues Feld „Standardfarbe“, vorbelegt mit Lila (128, 0, 255). Eine Figur ohne eigene Farbe nutzt die Standardfarbe der Box, auf der sie liegt. Bestehende Figuren und Boxen funktionieren dadurch ohne Nacharbeit.
- **LED-Modus `playing`:** Der ganze Ring leuchtet gedimmt (~25 %) in der Figurenfarbe. Ein hellerer Kopf (100 % der Farbe, innerhalb der Helligkeitsgrenze) mit kurzem Schweif von 3 LEDs dreht langsam im Kreis, etwa eine Runde in 3 s.
- **`loading`:** bleibt der schnelle weisse Spinner, damit „lädt“ und „spielt“ unterscheidbar sind.
- **`hold`:** bleibt neutral (statisch warmweiss, 10 %).
- **`volume`:** Das Overlay kehrt danach zum Farb-Spinner mit derselben Farbe zurück.
- Die Helligkeitsgrenze `color_correct: [50%, 50%, 50%]` bleibt.

## Ansätze
- **A, gewählt:** `set_led(mode, level, r, g, b)` mit drei Ganzzahlen 0–255. Gut lesbar und von Hand auslösbar, ohne Bit-Rechnung in der Firmware.
- B: eine gepackte Zahl `color` (0xRRGGBB). Kompakter, aber schlecht lesbar.
- Verworfen: eine eigene Action `set_color`, weil Farbe und Modus dann getrennt ankommen und der Ring kurz die falsche Farbe zeigen kann.

## Umsetzung
- **Integration:**
  - Figur-Subentry: optionales `color` (ColorRGBSelector, gespeichert als `[r, g, b]`).
  - Box-Subentry: `default_color` (Default Lila 128, 0, 255). Beide Felder auch beim Bearbeiten (Reconfigure); de/en-Texte.
  - `Figure.color: tuple[int, int, int] | None`.
  - `LedAdapter.show(mode, level=0, color=(0, 0, 0))` sendet immer `r`, `g`, `b`.
  - `BoxController` übergibt bei `playing` die wirksame Farbe (Figur, sonst Box).
- **Firmware:**
  - `api: actions: set_led` mit den zusätzlichen Variablen `r`, `g`, `b` (int).
  - Globals für die aktuelle Farbe.
  - `playing` wird ein `addressable_lambda`-Spinner (Basis gedimmt, Kopf heller, Schweif).
- **Tests:** Flows speichern die Farbe; Fallback auf die Box-Farbe; der LED-Aufruf trägt `r/g/b`. Bestehende LED-Tests werden angepasst.
- **Spec:** Abschnitte 4.3, 5.1 und 5.4 werden nachgeführt.

## Hinweis Inbetriebnahme
Die neue Integration sendet `r/g/b` an `set_led`. Mit alter Firmware schlägt der Aufruf vermutlich fehl, das Abspielen funktioniert trotzdem, denn LED-Fehler werden nur protokolliert. Deshalb Firmware und Integration zusammen aktualisieren.

## Vom Umsetzer zu entscheiden
Exakte Dimmstufe und Geschwindigkeit des Spinners können am Gerät nachjustiert werden. Die Farbe der Figur wird im Formular als Farbwähler angezeigt, die genaue Darstellung entscheidet der Umsetzer.
