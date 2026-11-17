<p align="center"><img src="docs/assets/lumibox-logo.png" alt="Lumibox" width="160"></p>

# Lumibox

Eine quelloffene, physische Audio-Steuerbox auf Basis eines ESP32, ESPHome und Home Assistant. Audio-Box mit NFC-Figuren für kleine Kinder: Das Auflegen und Abheben von mit NFC-Tags versehenen 3D-Druck-Figuren steuert die Musik- und Hörspielwiedergabe auf beliebigen vernetzten Smart Speakern.

Das Projekt ist unabhängig und nicht mit der Boxine GmbH (tonies) verbunden. Es steht unter der [MIT-Lizenz](LICENSE).

## Hardware

| Komponente | Spezifikation / Modell | Zweck |
| :--- | :--- | :--- |
| **Microcontroller** | ESP32-WROOM-32D (USB Type-C) | Zentrale Steuerung |
| **NFC/RFID-Leser** | PN532 NFC RFID Module V3 (SPI-Modus) | ISO 14443A Transceiver (NFC) |
| **NFC-Medien** | NTAG215 Coin-Tags (PVC, 25 mm) | Tags für Figuren und Coins |
| **Status-Beleuchtung** | WS2812B RGB-LED-Ring (24 LEDs) | Visuelle Effekte, Lautstärkeanzeige |
| **Lautstärkeregler** | KY-040 Rotary Encoder mit Taster | Lautstärke & Play/Pause |
| **Taster** | 24 mm Arcade-Buttons | Vorheriger / Nächster Titel |
| **Elko** | 470–1000 µF, ≥ 10 V | Pufferung der LED-Versorgung, direkt am Ring zwischen 5V und GND |
| **Widerstand** | 330–470 Ω | In Serie in der LED-Datenleitung, nah am Ring (DI) |
| **Pegelwandler (optional)** | 74AHCT125 / SN74AHCT1G125 | Hebt das 3,3-V-Datensignal auf 5 V; nur nötig, falls LEDs flackern oder falsche Farben zeigen |
| **Netzteil** | USB-C, 5 V, mind. 2 A | Versorgung der gesamten Box |


| ESP32-Pin | Komponente | Modul-Pin |
| :--- | :--- | :--- |
| GPIO 16 | PN532 NFC | SS (CS) |
| GPIO 18 | PN532 NFC | SCK |
| GPIO 19 | PN532 NFC | MISO |
| GPIO 21 (über 330–470 Ω, optional via 74AHCT125) | WS2812B Ring | DI (Data In) |
| GPIO 23 | PN532 NFC | MOSI |
| GPIO 25 | KY-040 Encoder | SW (Taster) |
| GPIO 26 | Button Zurück | Kontakt 1 |
| GPIO 27 | Button Weiter | Kontakt 1 |
| GPIO 32 | KY-040 Encoder | CLK |
| GPIO 33 | KY-040 Encoder | DT |
| 3V3 | PN532 NFC | VCC |
| 3V3 | KY-040 Encoder | + (VCC) |
| 5V (oder VIN) | WS2812B Ring | 5V (VCC) |
| GND | PN532 NFC | GND |
| GND | KY-040 Encoder | GND |
| GND | Button Zurück | Kontakt 2 |
| GND | Button Weiter | Kontakt 2 |
| GND | WS2812B Ring | GND |

### Hinweise zum LED-Ring

- **Helligkeit begrenzt:** Die Firmware kappt die Helligkeit mit `color_correct: [50%, 50%, 50%]`. Bei vollem Weiss würden die 24 LEDs bis zu ~1,44 A ziehen; mit der Kappung sind es höchstens ~0,7 A, im Normalbetrieb deutlich unter 200 mA.
- **Elko** (470–1000 µF) direkt am Ring zwischen 5V und GND einlöten, **auf die Polarität achten**.
- **Widerstand** (330–470 Ω) in die Datenleitung, möglichst nah am DI-Eingang des Rings.
- **Gemeinsame Masse** von ESP32, Ring und PN532 ist Pflicht.
- **Pegelwandler:** Der Ring erwartet bei 5 V ein Datensignal von mindestens ~3,5 V, der ESP32 liefert 3,3 V. Bei kurzen Kabeln funktioniert es meist trotzdem. Bei Flackern oder falschen Farben einen 74AHCT125 (mit 5 V versorgt) zwischen GPIO21 und Widerstand setzen.

## Architektur

Die Box ist "dumm": Sie meldet nur Ereignisse (Figur aufgelegt/abgenommen, Drehen, Tasten) an Home Assistant und zeigt LED-Zustände an. Die gesamte Logik und alle Figurendaten liegen in der Home-Assistant-Integration `lumibox`. Die Wiedergabe läuft über Music Assistant (Spotify) auf Sonos oder HomePod mini. Neue Figuren oder geändertes Verhalten brauchen kein Neu-Flashen.

```
Box (ESPHome) --Events--> Home Assistant (lumibox) --> Music Assistant --> Lautsprecher
Box (ESPHome) <--set_led-- Home Assistant
```

Details: [Design-Spezifikation](docs/superpowers/specs/2026-11-13-home-tonie-integration-design.md).

## Voraussetzungen

- **Home Assistant ab 2025.4.0.**
- **Music Assistant** mit
  - **einem Spotify-Provider pro Kind**, je mit einem eigenen Spotify-Premium-Account (z. B. die Konten eines Family-Abos). Spotify erlaubt pro Account nur eine Wiedergabe gleichzeitig, daher braucht jede Box ihren eigenen Account.
  - dem **Sonos-** bzw. **AirPlay-Provider** für die Lautsprecher.
  - **einem Music-Assistant-Benutzer pro Kind** (z. B. `anna`, `ben`). Der Anbieterfilter des Benutzers erlaubt nur den Spotify-Account dieses Kindes.
- Die **ESPHome-Integration** in Home Assistant.

## Updates im Alltag

Zwei Teile werden aktualisiert: die **Integration** (läuft in Home Assistant) und die **Firmware** (läuft auf der Box). Du brauchst dafür kein ESPHome-Wissen.

**Reihenfolge:** Zuerst die Firmware der Box aktualisieren, dann die Integration, aber nur, wenn die Release Notes es verlangen. Innerhalb derselben Hauptversion (z. B. 1.x) bleibt die Integration mit älterer Firmware kompatibel.

### Integration (über HACS)

HACS zeigt ein verfügbares Update an. Dort "Aktualisieren" wählen und Home Assistant neu starten. Die Release Notes stehen auf der GitHub-Seite des Projekts unter "Releases".

### Firmware der Box

- Jede Box hat in Home Assistant eine Update-Entität **"Firmware"** (Einstellungen › Geräte & Dienste › Gerät der Box). Gibt es eine neue Version, dort auf "Installieren" drücken. Die Box lädt die Firmware selbst herunter und startet danach neu. Das dauert einige Minuten.
- Ist eine Box für die installierte Integration **zu alt**, erscheint in Home Assistant unter Einstellungen › System › Reparaturen ein Hinweis. Mit **"Jetzt aktualisieren"** startet das Update direkt aus dem Hinweis. Der Hinweis verschwindet, sobald die neue Firmware läuft.
- Während des Updates die Box nicht vom Strom trennen.

### Wenn das Update nicht startet

1. Ist die Box eingeschaltet und im WLAN? Ohne WLAN und Internet kann sie die Firmware nicht herunterladen (sie kommt von GitHub Pages).
2. Einstellungen (ganz oben erscheint das Update) bzw. Einstellungen › System › Updates: Die Liste neu laden ("Nach Updates suchen"). Die Box prüft von sich aus alle 6 Stunden.
3. Die Box neu starten (Strom trennen und wieder anstecken) und erneut versuchen.
4. Erscheint beim Installieren ein Fehler, kurz danach erneut nach Updates suchen und nochmals installieren. Online bleibt nur die neueste Firmware; ein Update, das Stunden vor einem neueren Release angeboten wurde, kann auf eine entfernte Datei zeigen.

## Installation (für den Einrichtenden)

1. **Integration:** HACS › Menü › "Benutzerdefinierte Repositories", `https://github.com/Simai00/lumibox` mit Kategorie "Integration" hinzufügen, "Lumibox" installieren und Home Assistant neu starten. Manuell geht auch: Den Ordner `custom_components/lumibox` nach `custom_components` kopieren.
2. **Firmware per USB flashen:** Für alle Boxen gilt dieselbe Firmware. Die Datei `lumibox-<Version>.factory.bin` aus dem neuesten [Release](https://github.com/Simai00/lumibox/releases) per USB-Kabel auf den ESP32 schreiben (z. B. mit [web.esphome.io](https://web.esphome.io)) oder `esphome/lumibox.yaml` im ESPHome Builder installieren. Der Gerätename entsteht automatisch aus `lumibox` und einem Teil der MAC-Adresse (z. B. `lumibox-1a2b3c`), eine eigene Kopie pro Box ist nicht nötig.
3. **WLAN:** Die Box öffnet das Setup-WLAN **"Lumibox Setup"**. Damit verbinden und im Captive Portal das Heim-WLAN eintragen.
4. **Box in Home Assistant hinzufügen:** Home Assistant findet die Box als ESPHome-Gerät. Mit einer aktuellen Home-Assistant-Version setzt HA den Schlüssel automatisch, es muss keiner eingegeben werden; ältere Versionen verbinden unverschlüsselt.
5. **In der Integration einrichten:** siehe Einrichtung.

**Eigene Firmware-Anpassung:** Im ESPHome Builder erscheint die Box als "Übernehmen" (`dashboard_import`). Damit lässt sich die Konfiguration übernehmen und anpassen.

## Einrichtung

1. Einstellungen › Geräte & Dienste › Integration hinzufügen › "Lumibox".
2. **Box hinzufügen:** Name, ESPHome-Gerät der Box, Ziel-Lautsprecher, Music-Assistant-Benutzer des Kindes, maximale Lautstärke, Schrittweite pro Encoder-Raste und Standardfarbe (vorbelegt Lila) festlegen.
3. **Figur hinzufügen:** Name, UID des Tags und Spotify-Link (Album, Playlist, Titel, Künstler, Podcast, Folge oder Hörbuch; `https://open.spotify.com/...` oder `spotify:...`). Optional eine **Farbe**: In dieser Farbe dreht der Spinner im LED-Ring, solange die Figur spielt. Ohne eigene Farbe gilt die Standardfarbe der Box.

**Figuren anlernen:** Eine unbekannte Figur auf eine Box legen. Die Box blinkt rot und Home Assistant zeigt eine Benachrichtigung mit der UID. Dann bei "Lumibox" "Figur hinzufügen" wählen: Die UID ist bereits eingetragen, es fehlen nur Name und Spotify-Link. Nach dem Speichern die Figur einmal abheben und wieder auflegen, damit sie zu spielen beginnt.

## Manuelle Testcheckliste

**Events (Entwicklerwerkzeuge, Ereignisse, auf `esphome.lumibox` lauschen):**
1. Figur auflegen: `action: tag_on` mit `uid` und `device_id`.
2. Figur abnehmen: `tag_off` mit derselben `uid`.
3. Encoder rechts drehen: `rotate_cw`, links: `rotate_ccw`. Ein Event pro Raste.
4. Encoder drücken: `play_pause`. Taster GPIO26: `prev`, GPIO27: `next`. Ein Event pro Druck.
5. `device_id` gehört zur richtigen Box (Anna bzw. Ben).

**LED (Entwicklerwerkzeuge, Aktionen, `esphome.<gerätename>_set_led` (der Gerätename enthält das MAC-Suffix, Bindestriche werden zu Unterstrichen, z. B. `esphome.lumibox_1a2b3c_set_led`), Felder `mode`, `level`, `r`, `g`, `b`):**
6. `off`: Ring aus (auch nach dem Booten).
7. `loading`: weisser Spinner bis zum nächsten Modus.
8. `playing` mit `r: 255, g: 0, b: 0`: Ring rot (ca. 40 %), ein hellerer roter Punkt mit Schweif dreht etwa eine Runde in 3 s, dauerhaft. Danach `volume` mit `level: 50`: nach ca. 1,5 s wieder der rote Spinner.
9. `hold`: statisches, schwaches Warmweiss, dauerhaft.
10. `paused`: blendet in ca. 1,5 s aus, dann aus.
11. `unknown`: 3x rotes Blinken, dann aus.
12. `error`: ca. 3 s rot, dann aus.
13. `volume` mit `level` 0, 50 und 100: 0, 12 und 24 LEDs für ca. 1,5 s, danach zurück zum vorherigen Modus.
14. Ein neuer Modus bricht einen laufenden Modus sauber ab.
15. Helligkeit: `loading` und `error` blenden nicht, das Netzteil bricht nicht ein.

**Ende zu Ende (mit Integration und Lautsprecher):**
16. Bekannte Figur auflegen: Musik startet auf dem Lautsprecher der Box.
17. Figur abnehmen: Pause.
18. Dieselbe Figur wieder auflegen: Wiedergabe geht weiter.
19. Andere Figur auflegen: Wiedergabe startet neu.
20. Unbekannte Figur auflegen: Benachrichtigung mit UID, Box blinkt rot.
21. Encoder: Lautstärke ändert sich in Schritten und geht nie über das Box-Maximum.
22. Zwei Boxen gleichzeitig: Beide spielen unabhängig, jeweils über den Spotify-Account des Kindes.

## Hinweise und Fehlersuche

- **Platine ausgetauscht:** Der Gerätename enthält einen Teil der MAC-Adresse und bleibt für dieselbe Hardware gleich. Eine ausgetauschte Platine ist ein neues Gerät: Sie in Home Assistant zur ESPHome-Integration hinzufügen und in der Box-Konfiguration von Lumibox neu auswählen.
- **Sicherheit des Rettungswegs:** Die Firmware enthält einen zusätzlichen ESPHome-OTA-Zugang (`ota: esphome`) ohne Passwort als Rettungsweg. Wer im selben WLAN ist, könnte darüber eine Firmware auf die Box laden. Die API zu Home Assistant ist davon getrennt und mit dem von Home Assistant gesetzten Schlüssel verschlüsselt (bei einer aktuellen Home-Assistant-Version, sonst unverschlüsselt). Ist das Heim-WLAN nicht erreichbar, öffnet die Box ausserdem das offene Setup-WLAN; wer physisch in der Nähe ist, könnte sie dann umkonfigurieren und flashen. Das ist für ein Spielzeug zu Hause ein akzeptiertes Risiko. Die Box daher nur in einem vertrauenswürdigen WLAN betreiben.
- **Keine Events im Ereignis-Monitor:** Als Fehlersuche in den Optionen des ESPHome-Geräts "Allow the device to perform Home Assistant actions" aktivieren. Normalerweise ist das nicht nötig.
- **Helligkeit im Haltemodus:** Sie ist bewusst niedrig (10 % bei 50 % Gesamtbegrenzung) und kann in `esphome/lumibox.yaml` angepasst werden.
- **Spotify-Kurzlinks** (`spotify.link`) werden nicht unterstützt. Den vollständigen Link `open.spotify.com/...` oder die URI `spotify:...` verwenden.
- **Ein Stream pro Spotify-Account:** Spotify erlaubt nur eine gleichzeitige Wiedergabe pro Account. Jede Box braucht daher ihren eigenen Account und Music-Assistant-Benutzer. Zwei Boxen mit demselben Benutzer können nicht gleichzeitig spielen.

## Entwicklung

- Tests: `bash scripts/test.sh -q` (Docker, baut ein Testimage). Firmware-Konfiguration prüfen: `bash scripts/esphome-config.sh lumibox.yaml`.
- **Release:** `bash scripts/bump-version.sh X.Y.Z` setzt die Version in Integration und Firmware, danach committen, `git tag vX.Y.Z` und den Tag pushen. Die Pipeline prüft die Versionen, baut die Firmware, erstellt das GitHub-Release mit `*.factory.bin`, `*.ota.bin` und automatischen Release Notes und veröffentlicht danach `/firmware/manifest.json` auf GitHub Pages, woher die Boxen ihre Updates holen.
- **Einmalig im GitHub-Repo:** Settings › Pages › Source auf "GitHub Actions" stellen. Unter Settings › Environments › `github-pages` eine Deployment-Regel für Tags `v*` hinzufügen, sonst wird das Deployment aus dem Tag-Lauf abgelehnt.
- **HACS-Voraussetzungen im Repo:** Beschreibung, Topics und Releases müssen gesetzt sein. Nach der Veröffentlichung prüfen, ob `topics`/`description` im HACS-Check (`.github/workflows/ci.yml`) ohne Ausnahme durchlaufen; `brands` kann nötig bleiben.
- Die Marken-Icons der Integration liegen in `custom_components/lumibox/brand/`.
