# Home Assistant Tonie Box

Eine quelloffene, physische Audio-Steuerbox auf Basis eines ESP32, ESPHome und Home Assistant. Inspiriert vom Bedienkonzept der Toniebox steuert das Auflegen und Abheben von mit NFC-Tags versehenen 3D-Druck-Figuren die Musik- und Hörspielwiedergabe auf beliebigen vernetzten Smart Speakern.

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