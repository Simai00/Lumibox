"""Binary-Sensor pro Box: Verbindung zum ESPHome-Gerät."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import LumiboxConfigEntry
from .box import BoxController
from .connection import BoxConnection
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LumiboxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Einen Verbindungs-Sensor pro Box anlegen, dem Box-Subentry zugeordnet."""
    for controller in entry.runtime_data.controllers.values():
        subentry_id = controller.config.subentry_id
        async_add_entities(
            [ConnectedSensor(controller, entry.runtime_data.connections[subentry_id])],
            config_subentry_id=subentry_id,
        )


class ConnectedSensor(BinarySensorEntity):
    """An, solange das ESPHome-Gerät der Box erreichbar ist."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_translation_key = "connected"

    def __init__(self, controller: BoxController, connection: BoxConnection) -> None:
        self._connection = connection
        config = controller.config
        self._attr_unique_id = f"{config.subentry_id}_connected"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config.subentry_id)},
            name=f"Lumibox {config.name}",
        )

    @property
    def is_on(self) -> bool:
        return self._connection.connected

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self._connection.add_listener(self._handle_update))

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()
