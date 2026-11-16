"""LedAdapter: steuert die LED-Anzeige der Box über die ESPHome-Action set_led."""

from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr

_LOGGER = logging.getLogger(__name__)


def esphome_node_name(hass: HomeAssistant, device_id: str) -> str | None:
    """Knotennamen des ESPHome-Geräts über die Device Registry auflösen."""
    device = dr.async_get(hass).async_get(device_id)
    if device is None:
        return None
    # Neuere HA: einzelne config_entry_id; HA 2025.4: nur das Set config_entries.
    if hasattr(device, "config_entry_id"):
        entry_ids = [device.config_entry_id] if device.config_entry_id else []
    else:
        entry_ids = list(device.config_entries)
    for entry_id in entry_ids:
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry is not None and entry.domain == "esphome":
            return entry.data.get("device_name")
    return None


class LedAdapter:
    """Ruft die ESPHome-Action ``set_led`` der Box auf."""

    def __init__(self, hass: HomeAssistant, device_id: str) -> None:
        self._hass = hass
        self._device_id = device_id
        self._warned = False

    def _warn_once(self, msg: str, *args: object) -> None:
        if not self._warned:
            self._warned = True
            _LOGGER.warning(msg, *args)

    async def show(
        self, mode: str, level: int = 0, color: tuple[int, int, int] = (0, 0, 0)
    ) -> None:
        """LED-Modus anzeigen; wirft nie."""
        node = esphome_node_name(self._hass, self._device_id)
        if not node:
            self._warn_once(
                "ESPHome-Knoten für Gerät %s nicht gefunden, LED-Action set_led nicht möglich",
                self._device_id,
            )
            return
        service = f"{node.replace('-', '_')}_set_led"
        if not self._hass.services.has_service("esphome", service):
            self._warn_once(
                "ESPHome-Action set_led fehlt auf der Box (erwartet: esphome.%s)", node.replace("-", "_")
            )
            return
        try:
            await self._hass.services.async_call(
                "esphome", service, {"mode": mode, "level": level, "r": color[0], "g": color[1], "b": color[2]}, blocking=False
            )
        except HomeAssistantError as err:
            _LOGGER.debug("set_led fehlgeschlagen: %s", err)
