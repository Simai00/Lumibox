"""Sensoren pro Box: aktuelle Figur und letzter unbekannter Tag."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import LumiboxConfigEntry
from .box import BoxController
from .connection import BoxConnection
from .const import DOMAIN

# Zustand ohne aufgelegte Figur; die Übersetzung zeigt „Keine“ bzw. „None“.
NO_FIGURE = "none"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LumiboxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Zwei Sensoren pro Box anlegen, jeweils dem Box-Subentry zugeordnet."""
    for controller in entry.runtime_data.controllers.values():
        connection = entry.runtime_data.connections[controller.config.subentry_id]
        async_add_entities(
            [CurrentFigureSensor(controller, connection), LastUnknownTagSensor(controller, connection)],
            config_subentry_id=controller.config.subentry_id,
        )


class _BoxSensor(SensorEntity):
    """Gemeinsame Basis: Gerät der Box, Aktualisierung über den Controller-Listener."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, controller: BoxController, connection: BoxConnection, key: str) -> None:
        self._controller = controller
        self._connection = connection
        config = controller.config
        self._attr_translation_key = key
        self._attr_unique_id = f"{config.subentry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config.subentry_id)},
            name=f"Lumibox {config.name}",
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self._controller.add_listener(self._handle_update))
        self.async_on_remove(self._connection.add_listener(self._handle_update))

    @property
    def available(self) -> bool:
        """Ohne Verbindung zum ESPHome-Gerät der Box nicht verfügbar."""
        return self._connection.connected

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()


class CurrentFigureSensor(_BoxSensor):
    """Name der aufgelegten Figur oder „none“ (übersetzt als „Keine“)."""

    def __init__(self, controller: BoxController, connection: BoxConnection) -> None:
        super().__init__(controller, connection, "current_figure")

    @property
    def native_value(self) -> str:
        figure = self._controller.current_figure
        return figure.name if figure is not None else NO_FIGURE


class LastUnknownTagSensor(_BoxSensor):
    """UID des zuletzt aufgelegten unbekannten Tags oder None."""

    def __init__(self, controller: BoxController, connection: BoxConnection) -> None:
        super().__init__(controller, connection, "last_unknown_tag")

    @property
    def native_value(self) -> str | None:
        return self._controller.last_unknown_uid
