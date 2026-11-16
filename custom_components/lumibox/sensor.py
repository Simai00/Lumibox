"""Sensoren pro Box: aktuelle Figur und letzter unbekannter Tag."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import LumiboxConfigEntry
from .box import BoxController
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LumiboxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Zwei Sensoren pro Box anlegen, jeweils dem Box-Subentry zugeordnet."""
    for controller in entry.runtime_data.controllers.values():
        async_add_entities(
            [CurrentFigureSensor(controller), LastUnknownTagSensor(controller)],
            config_subentry_id=controller.config.subentry_id,
        )


class _BoxSensor(SensorEntity):
    """Gemeinsame Basis: Gerät der Box, Aktualisierung über den Controller-Listener."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, controller: BoxController, key: str) -> None:
        self._controller = controller
        config = controller.config
        self._attr_translation_key = key
        self._attr_unique_id = f"{config.subentry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config.subentry_id)},
            name=f"Lumibox {config.name}",
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self._controller.add_listener(self._handle_update))

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()


class CurrentFigureSensor(_BoxSensor):
    """Name der aufgelegten Figur oder None."""

    def __init__(self, controller: BoxController) -> None:
        super().__init__(controller, "current_figure")

    @property
    def native_value(self) -> str | None:
        figure = self._controller.current_figure
        return figure.name if figure is not None else None


class LastUnknownTagSensor(_BoxSensor):
    """UID des zuletzt aufgelegten unbekannten Tags oder None."""

    def __init__(self, controller: BoxController) -> None:
        super().__init__(controller, "last_unknown_tag")

    @property
    def native_value(self) -> str | None:
        return self._controller.last_unknown_uid
