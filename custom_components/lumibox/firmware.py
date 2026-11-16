"""Prüfung der Box-Firmware-Version und Reparatur-Hinweis bei zu alter Firmware."""

from __future__ import annotations

from collections.abc import Callable, Iterable

from awesomeversion import AwesomeVersion, AwesomeVersionStrategy
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, issue_registry as ir

from .box import BoxConfig
from .const import DOMAIN, MIN_FIRMWARE_VERSION

_PROJECT_MARKER = " (ESPHome "
_ISSUE_PREFIX = "firmware_outdated_"


def parse_firmware_version(sw_version: str | None) -> str | None:
    """Projektversion aus dem `sw_version` des ESPHome-Geräts; None ohne Projekt."""
    if not sw_version or _PROJECT_MARKER not in sw_version:
        return None
    return sw_version.split(_PROJECT_MARKER, 1)[0]


def is_outdated(sw_version: str | None) -> bool | None:
    """True bei zu alter Firmware, None wenn keine Aussage möglich (Gerät unbekannt)."""
    if sw_version is None:
        return None
    version = parse_firmware_version(sw_version)
    if not version:
        return True
    if version == "dev":
        return False
    current = AwesomeVersion(version)
    if current.strategy is AwesomeVersionStrategy.UNKNOWN:
        return True
    try:
        return current < AwesomeVersion(MIN_FIRMWARE_VERSION)
    except Exception:  # noqa: BLE001 - nicht vergleichbar gilt als veraltet
        return True


def _issue_id(subentry_id: str) -> str:
    return f"{_ISSUE_PREFIX}{subentry_id}"


@callback
def _check_box(hass: HomeAssistant, config: BoxConfig) -> None:
    device = dr.async_get(hass).async_get(config.esphome_device_id)
    outdated = is_outdated(device.sw_version if device else None)
    issue_id = _issue_id(config.subentry_id)
    if not outdated:
        ir.async_delete_issue(hass, DOMAIN, issue_id)
        return
    current = parse_firmware_version(device.sw_version) or "unbekannt"
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=True,
        data={"device_id": config.esphome_device_id},
        severity=ir.IssueSeverity.WARNING,
        translation_key="firmware_outdated",
        translation_placeholders={
            "box": config.name,
            "current": current,
            "required": MIN_FIRMWARE_VERSION,
        },
    )


@callback
def async_setup_firmware_checks(
    hass: HomeAssistant, boxes: Iterable[BoxConfig]
) -> Callable[[], None]:
    """Boxen jetzt prüfen und bei `sw_version`-Änderungen erneut; liefert die Abmeldefunktion."""
    configs = {box.esphome_device_id: box for box in boxes}

    # Hinweise von Boxen, die nicht mehr eingerichtet sind, entfernen.
    keep = {_issue_id(box.subentry_id) for box in configs.values()}
    for domain, issue_id in list(ir.async_get(hass).issues):
        if domain == DOMAIN and issue_id.startswith(_ISSUE_PREFIX) and issue_id not in keep:
            ir.async_delete_issue(hass, DOMAIN, issue_id)

    for box in configs.values():
        _check_box(hass, box)

    @callback
    def _on_device_update(event: Event) -> None:
        if event.data.get("action") != "update" or "sw_version" not in event.data.get("changes", {}):
            return
        box = configs.get(event.data["device_id"])
        if box is not None:
            _check_box(hass, box)

    return hass.bus.async_listen(dr.EVENT_DEVICE_REGISTRY_UPDATED, _on_device_update)
