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


| Komponente | Modul-Pin | ESP32-Pin |
| :--- | :--- | :--- |
| PN532 NFC | SCK | GPIO 18 |
| PN532 NFC | MISO | GPIO 19 |
| PN532 NFC | MOSI | GPIO 23 |
| PN532 NFC | SS (CS) | GPIO 16 |
| PN532 NFC | VCC | 3V3 |
| PN532 NFC | GND | GND |
| KY-040 Encoder | CLK | GPIO 32 |
| KY-040 Encoder | DT | GPIO 33 |
| KY-040 Encoder | SW (Taster) | GPIO 25 |
| KY-040 Encoder | + (VCC) | 3V3 |
| KY-040 Encoder | GND | GND |
| Button Zurück | Kontakt 1 | GPIO 26 |
| Button Zurück | Kontakt 2 | GND |
| Button Weiter | Kontakt 1 | GPIO 27 |
| Button Weiter | Kontakt 2 | GND |
| WS2812B Ring | DI (Data In) | GPIO 21 |
| WS2812B Ring | 5V (VCC) | 5V (oder VIN) |
| WS2812B Ring | GND | GND |