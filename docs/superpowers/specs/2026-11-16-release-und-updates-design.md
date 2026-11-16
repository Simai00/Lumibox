# Versionierung, Updates und Veröffentlichung – Design

Stand: 2026-11-16 · Status: Entwurf, wartet auf Freigabe

## Absicht
Das Projekt wird öffentlich und Open Source. Integration und Firmware sollen sich ohne Handarbeit pro Box aktualisieren lassen.
- **Integration:** kommt wie bisher über HACS.
- **Firmware:** Jede Box zeigt in Home Assistant eine Update-Entität und lässt sich mit einem Klick aktualisieren. Dafür braucht es weder den ESPHome Builder noch eine eigene YAML-Datei pro Box.
- **Versionsprüfung:** Ist die Firmware einer Box zu alt für die installierte Integration, meldet Home Assistant das als Reparatur-Hinweis.

## Zielgruppe
Die Box läuft auch bei anderen Leuten, auf deren eigener HA-Instanz. Das sind normale HA-Nutzer ohne ESPHome-Wissen.
- **Erstinstallation und Einrichtung macht der Projektautor selbst vor Ort.** Darauf liegt kein Fokus: Flashen per USB (ESPHome Builder oder web.esphome.io mit dem `factory.bin` aus dem Release), WLAN über das Captive Portal, dann die Box in HA hinzufügen.
- **Der Fokus liegt auf Updates im laufenden Betrieb**, die der Nutzer selbst ausführt:
- **Firmware-Update mit einem Klick, ohne ESPHome-Wissen:**
  - Die Update-Entität der Box erscheint wie jedes andere Update unter Einstellungen › Updates.
  - Ist eine Box zu alt für die Integration, erscheint ein Reparatur-Hinweis mit dem Knopf „Jetzt aktualisieren“. Er startet das Firmware-Update der Box.
- **Integration-Update** wie gewohnt über HACS.
- **Kompatibilität:** Die Integration bleibt mit jeder Firmware derselben Major-Version kompatibel. `MIN_FIRMWARE_VERSION` wird nur angehoben, wenn es nicht anders geht, und die Release Notes sagen es dann klar. Die Nutzer sollen nie raten müssen, in welcher Reihenfolge sie aktualisieren.
- **Fehlertexte** in der Oberfläche sind in Alltagssprache formuliert und sagen, was zu tun ist.

## Ziele
- **Eine Versionsnummer für alles:** Ein Git-Tag `vX.Y.Z` bestimmt das GitHub-Release (für HACS), `manifest.json` der Integration und `project: version` der Firmware. CI prüft, dass alle drei übereinstimmen.
- **Eine allgemeine Firmware für alle Boxen.** Sie enthält keine Secrets und wird von GitHub Actions gebaut.
- **Firmware-Updates über HTTP:** `update: platform: http_request` mit Manifest auf GitHub Pages, installiert über `ota: platform: http_request`.
- **API-Verschlüsselung ohne Schlüssel in der Firmware:** `api: encryption:` ohne `key`. Home Assistant erzeugt beim ersten Verbinden einen Schlüssel und setzt ihn auf der Box (`noise_encryption_set_key`, im HA-Core-Code `esphome/manager.py`, `_handle_dynamic_encryption_key`).
- **Erstinstallation:** WLAN über das Captive Portal; kein eigener Web-Installer, denn die Erstinstallation macht der Projektautor.
- **Neuer Projektname** ohne „Tonie“, eine Marke der Boxine GmbH. Der Name betrifft Repo, Domain der Integration, Event, Firmware und Texte.
- **Repo bereit für die Veröffentlichung:** MIT-Lizenz, Doku auf Deutsch, keine persönlichen Daten, CI mit Tests, hassfest und HACS-Validierung.

## Nicht-Ziele
- Automatisches Installieren der Firmware ohne Klick, denn ein Kind könnte gerade hören. Die Integration meldet nur, das Update löst der Mensch aus.
- Migration bestehender Einrichtungen von `home_tonie` auf die neue Domain. Es gibt nur zwei Boxen und wenige Figuren, die Einrichtung wird einmal neu angelegt (vom Nutzer akzeptiert).
- Englische Doku.
- Ein Web-Installer oder eine geführte Erstinstallation für Endnutzer. Kann später ergänzt werden.
- Umschreiben der Git-Historie. `secrets.yaml` liegt nur in einem lokalen Cline-Checkpoint-Ref, nicht in `main` und nicht auf GitHub, und „Anna“/„Ben“ sind Platzhalter.

## Anti-Ziele
- Secrets oder WLAN-Daten in einer öffentlich gebauten Firmware.
- Eine Box, die nach einem Update nicht mehr erreichbar ist und nur noch per USB gerettet werden kann. Deshalb bleibt `ota: platform: esphome` zusätzlich aktiv.
- Updates, die die Integration und eine ältere Firmware stillschweigend inkompatibel machen. Die Versionsprüfung macht das sichtbar.

## Ansätze (mit dem Nutzer abgewogen)
- **1, gewählt:** CI baut die Firmware, sie wird über GitHub Pages verteilt, und die Update-Entität in HA zeigt neue Versionen. Professionell, Updates mit einem Klick, keine Datei pro Box. Kostet einmal Aufbau: CI, allgemeine Firmware und einen einmaligen Umstieg der bestehenden Boxen.
- 2: Remote-Package im ESPHome Builder (`github://…@vX.Y.Z`), dazu eine kleine Datei pro Box. Wenig Aufwand, aber jede Box muss einzeln von Hand aktualisiert werden, und die Aufteilung in eine allgemeine Datei und eine Gerätedatei stört den Nutzer.
- 3: Wie heute plus Versionsprüfung. Der Aufwand pro Update bleibt.

## Entscheide
- **Lizenz:** MIT. **Sprache:** Deutsch.
- **Name: Lumibox.** Domain `lumibox`, Event `esphome.lumibox`, Firmware `lumibox-<mac>`, Repo `Simai00/lumibox`. Das Logo stammt vom Nutzer: `docs/assets/lumibox-logo.png` (1488×1488, transparent).
- **Icon in HA:** über den lokalen Ordner `custom_components/lumibox/brand/`, den HA ab 2026.3 unterstützt. Ältere HA-Versionen zeigen kein Icon, sonst ändert sich nichts. Die Mindestversion bleibt deshalb 2025.4.0.
- **Gerätename:** `lumibox` mit `name_add_mac_suffix: true`, dadurch automatisch eindeutig pro Box.
- **Firmware-Version in HA:** HA schreibt bei Geräten mit `project` den Wert `"<project_version> (ESPHome <version>)"` als `sw_version` in die Geräte-Registry (HA Core `esphome/manager.py`). Die Integration liest diesen Wert.
- **Einmaliger Umstieg der bestehenden Boxen:**
  - Der alte Schlüssel ist fest einkompiliert und geht beim Wechsel verloren, ausserdem ändert sich der Gerätename.
  - Deshalb pro Box: neue Firmware flashen (OTA aus dem Builder oder per USB), das alte ESPHome-Gerät in HA entfernen, die Box neu hinzufügen (HA setzt den Schlüssel) und in der neuen Integration einrichten.

## Dem Umsetzer überlassen
- Ob die Firmware mit `esphome/build-action` oder mit den wiederverwendbaren Workflows aus `esphome/workflows` gebaut wird.
- Aufbau der Pages-Seite, sofern das Manifest unter einer festen URL liegt.
- `verify_ssl` für `http_request` auf ESP32/Arduino: an, wenn es unterstützt wird, sonst begründet aus.
